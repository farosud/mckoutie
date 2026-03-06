"""
Orchestrator — the glue that connects all pieces end-to-end.

TWO-PHASE ARCHITECTURE (cost-optimized):

  PHASE 1 — On tweet (fast, cheap):
    1. Twitter mention comes in
    2. Acknowledge immediately
    3. Scrape the target (website or Twitter profile)
    4. Run QUICK analysis via Haiku (~5-10s, ~$0.01)
    5. Generate teaser tweet thread
    6. Post thread with report link
    7. Save skeleton report to disk
    → 90% of tweeters never click the link = 90% cost savings

  PHASE 2 — On first page visit (rich, streaming):
    1. User clicks report link and signs up with Twitter
    2. Trigger full deep analysis (Sonnet for channels, Opus for hot take)
    3. Stream results via SSE as they come in
    4. Run lead + investor research in parallel
    5. Generate capybara image
    6. Provision AI advisor agent
    → Only runs for engaged users = smart resource allocation
"""

import asyncio
import json
import logging
import random
import time

from src.config import settings
from src.modules.twitter_poller import AnalysisRequest, TwitterPoller
from src.modules.scraper import scrape_website
from src.modules.twitter_analyzer import analyze_twitter_profile
from src.modules.payments import create_checkout_session
from src.modules.report_store import ReportRecord, save_record, update_status, load_record
from src.modules.image_generator import generate_capybara_image
from src.modules.lead_finder import find_leads
from src.modules.investor_finder import find_investors
from src.analysis.traction_engine import run_quick_analysis, run_traction_analysis, run_core_analysis, run_deep_dives_batch
from src.analysis.report_generator import (
    generate_report_id,
    generate_teaser_from_quick,
    generate_teaser_thread,
    generate_full_report_markdown,
    save_report,
)
from src.modules import db

logger = logging.getLogger(__name__)

# Track processed tweet IDs to avoid double-processing
_processed_tweets: set[str] = set()
MAX_PROCESSED_CACHE = 5000

# Track reports currently running deep analysis to prevent duplicates
_deep_analysis_in_progress: set[str] = set()

# Track deep analysis progress for polling (report_id -> progress dict)
_deep_progress: dict[str, dict] = {}

# --- Anti-spam state ---
# Per-user cooldown: {author_id: last_processed_timestamp}
_user_cooldowns: dict[str, float] = {}
USER_COOLDOWN_SECONDS = 3600  # 1 hour between requests from same user

# Per-target cooldown: {normalized_target: (report_id, timestamp)}
_target_cooldowns: dict[str, tuple[str, float]] = {}
TARGET_COOLDOWN_SECONDS = 86400  # 24 hours before re-analyzing same URL

# Global rate limit: minimum seconds between starting any analysis
_last_analysis_time: float = 0.0
GLOBAL_MIN_INTERVAL = 300  # 5 minutes between analyses


# =============================================================================
# PHASE 1 — Quick analysis on tweet (fast, cheap)
# =============================================================================

def _normalize_target(target: str) -> str:
    """Normalize a target URL/handle for dedup comparison."""
    t = target.lower().strip().rstrip("/")
    for prefix in ("https://", "http://", "www.", "@"):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t


def _check_spam(request: AnalysisRequest) -> str | None:
    """
    Check anti-spam rules. Returns a reason string if blocked, None if OK.
    Also cleans up expired cooldowns.
    """
    global _last_analysis_time
    now = time.time()

    # Clean expired cooldowns periodically
    expired_users = [uid for uid, ts in _user_cooldowns.items() if now - ts > USER_COOLDOWN_SECONDS]
    for uid in expired_users:
        del _user_cooldowns[uid]
    expired_targets = [t for t, (_, ts) in _target_cooldowns.items() if now - ts > TARGET_COOLDOWN_SECONDS]
    for t in expired_targets:
        del _target_cooldowns[t]

    # 1. Global rate limit
    if now - _last_analysis_time < GLOBAL_MIN_INTERVAL:
        wait = int(GLOBAL_MIN_INTERVAL - (now - _last_analysis_time))
        return f"rate_limit:global ({wait}s remaining)"

    # 2. Per-user cooldown
    if request.author_id in _user_cooldowns:
        elapsed = now - _user_cooldowns[request.author_id]
        if elapsed < USER_COOLDOWN_SECONDS:
            wait_min = int((USER_COOLDOWN_SECONDS - elapsed) / 60)
            return f"rate_limit:user (try again in ~{wait_min}min)"

    # 3. Duplicate target
    norm = _normalize_target(request.target_display)
    if norm in _target_cooldowns:
        existing_id, _ = _target_cooldowns[norm]
        return f"duplicate_target:{existing_id}"

    return None


async def handle_request(request: AnalysisRequest, poller: TwitterPoller) -> str | None:
    """
    Handle a single analysis request — PHASE 1 ONLY.
    Does quick analysis + tweet thread. Full analysis deferred to page visit.
    Returns the report_id on success, None on failure.
    """
    global _last_analysis_time

    if request.tweet_id in _processed_tweets:
        logger.debug(f"Skipping already-processed tweet {request.tweet_id}")
        return None

    _processed_tweets.add(request.tweet_id)
    if len(_processed_tweets) > MAX_PROCESSED_CACHE:
        to_remove = list(_processed_tweets)[:1000]
        for t in to_remove:
            _processed_tweets.discard(t)

    # --- Anti-spam checks ---
    spam_reason = _check_spam(request)
    if spam_reason:
        if spam_reason.startswith("duplicate_target:"):
            existing_id = spam_reason.split(":")[1]
            logger.info(f"[ANTI-SPAM] Duplicate target from @{request.author_username} — pointing to existing report {existing_id}")
            if settings.has_twitter_write:
                report_url = f"https://www.mckoutie.com/report/{existing_id}"
                reply = (
                    f"Hey @{request.author_username}, we already analyzed that one recently!\n\n"
                    f"Check out the full dashboard here:\n{report_url}"
                )
                poller.reply_to_tweet(request.tweet_id, reply)
            return None
        elif spam_reason.startswith("rate_limit:user"):
            logger.info(f"[ANTI-SPAM] User cooldown for @{request.author_username}: {spam_reason}")
            if settings.has_twitter_write:
                reply = (
                    f"@{request.author_username} our capybaras need a coffee break between analyses. "
                    f"Try again in about an hour!"
                )
                poller.reply_to_tweet(request.tweet_id, reply)
            return None
        else:
            logger.info(f"[ANTI-SPAM] Blocked: {spam_reason} (from @{request.author_username})")
            return None

    # Record rate limit timestamps
    _last_analysis_time = time.time()
    _user_cooldowns[request.author_id] = time.time()

    report_id = generate_report_id(request.target_display)
    startup_name = request.target_display

    logger.info(f"[PHASE 1] Processing request from @{request.author_username} for {request.target_display}")

    # 1. Create initial report record
    record = ReportRecord(
        report_id=report_id,
        startup_name=startup_name,
        target=request.target_display,
        tweet_id=request.tweet_id,
        author_username=request.author_username,
        author_id=request.author_id,
        status="analyzing",
    )
    save_record(record)

    # Sync to Supabase
    try:
        db.create_report(
            report_id=report_id,
            startup_name=startup_name,
            target=request.target_display,
            tweet_id=request.tweet_id,
            author_twitter_id=request.author_id,
            author_username=request.author_username,
        )
    except Exception as e:
        logger.warning(f"Supabase report create failed (non-fatal): {e}")

    # 2. Immediate acknowledgment
    if settings.has_twitter_write:
        ack_text = _generate_ack_message(request.author_username, request.target_display)
        poller.reply_to_tweet(request.tweet_id, ack_text)
        logger.info(f"Sent immediate ack reply to @{request.author_username}")

    try:
        # 3. Gather intelligence (scrape website/twitter)
        startup_data = await _gather_intelligence(request, poller)

        if not startup_data or len(startup_data) < 50:
            raise ValueError(f"Insufficient data gathered for {request.target_display}")

        # 4. Run QUICK analysis (Haiku — ~5-10s, ~$0.01)
        logger.info("[PHASE 1] Running quick analysis via Haiku...")
        quick = await run_quick_analysis(startup_data)

        if "error" in quick:
            raise ValueError(f"Quick analysis failed: {quick.get('error', 'unknown')}")

        # Update startup name from quick analysis
        profile = quick.get("company_profile", {})
        startup_name = profile.get("name", request.target_display)
        update_status(report_id, "skeleton", startup_name=startup_name)

        # 5. Save quick analysis as skeleton (for dashboard to show while deep analysis runs)
        skeleton_data = {
            "company_profile": profile,
            "top_3_channels": quick.get("top_3_channels", []),
            "hot_take": quick.get("hot_take", ""),
            # Placeholder empty sections for the dashboard to fill via SSE
            "channel_analysis": [],
            "bullseye_ranking": {},
            "ninety_day_plan": {},
            "budget_allocation": {},
            "risk_matrix": [],
            "competitive_moat": "",
            "executive_summary": "",
            "leads_research": {},
            "investor_research": {},
            # Store the raw startup data for deep analysis later
            "_startup_data": startup_data,
            "_phase": "skeleton",
        }
        save_report(report_id, skeleton_data, "")

        # 6. Generate teaser tweets from quick analysis
        teaser_tweets = generate_teaser_from_quick(quick)
        logger.info(f"Generated {len(teaser_tweets)} teaser tweets")
        for i, t in enumerate(teaser_tweets):
            logger.info(f"  Tweet {i+1} ({len(t)} chars): {t[:80]}...")

        # 7. Fill in report link
        report_url = f"https://www.mckoutie.com/report/{report_id}"
        if teaser_tweets:
            teaser_tweets[-1] = teaser_tweets[-1].replace("{report_link}", report_url)

        # 8. Post teaser thread
        if settings.has_twitter_write:
            logger.info(f"Posting teaser thread ({len(teaser_tweets)} tweets) as reply to {request.tweet_id}")
            posted_ids = _post_teaser_thread(poller, request.tweet_id, teaser_tweets)
            logger.info(f"Thread posted: {len(posted_ids)} tweets succeeded")
        else:
            logger.info("Twitter write disabled — teaser thread saved but not posted")

        # 9. Update status to "skeleton" (ready for page visit to trigger deep analysis)
        update_status(
            report_id,
            "skeleton",
            startup_name=startup_name,
            checkout_url=report_url,
        )

        try:
            db.update_report(report_id, status="skeleton", startup_name=startup_name)
        except Exception as e:
            logger.warning(f"Supabase status update failed (non-fatal): {e}")

        # Register target cooldown so same URL isn't re-analyzed within 24h
        norm_target = _normalize_target(request.target_display)
        _target_cooldowns[norm_target] = (report_id, time.time())

        logger.info(f"[PHASE 1] Complete for {startup_name} (report={report_id}). Awaiting page visit for deep analysis.")
        return report_id

    except Exception as e:
        logger.error(f"[PHASE 1] Failed to process request {request.tweet_id}: {e}")
        update_status(report_id, "failed", error=str(e))
        try:
            db.update_report(report_id, status="failed", error=str(e)[:500])
        except Exception:
            pass

        if settings.has_twitter_write:
            error_text = (
                f"Sorry @{request.author_username}, I hit an issue analyzing {request.target_display}. "
                f"I'll look into it. Try again in a few minutes."
            )
            poller.reply_to_tweet(request.tweet_id, error_text)
        return None


# =============================================================================
# PHASE 2 — Deep analysis on page visit (rich, streaming via SSE)
# =============================================================================

async def run_deep_analysis(report_id: str):
    """
    Run the FULL deep analysis for a report. Called when user first visits the report page.
    Streams results via SSE — each section is yielded as it completes.

    Events emitted:
      {"event": "thinking",  "data": {"message": "...", "detail": "..."}}
      {"event": "channel",   "data": {"index": 0, "channel": {...}}}       # per-channel
      {"event": "section",   "data": {"section": "channels_meta", ...}}     # bullseye/summary
      {"event": "persona",   "data": {"index": 0, "persona": {...}}}       # per-persona
      {"event": "lead",      "data": {"index": 0, "lead": {...}}}          # per-lead
      {"event": "competitor", "data": {"index": 0, "competitor": {...}}}    # per-competitor
      {"event": "investor",  "data": {"index": 0, "investor": {...}}}      # per-investor
      {"event": "section",   "data": {"section": "strategy", ...}}
      {"event": "advisor_ready", "data": {}}
      {"event": "done",      "data": {}}
    """
    if report_id in _deep_analysis_in_progress:
        logger.info(f"Deep analysis already running for {report_id}, skipping duplicate")
        yield {"event": "already_running", "data": {}}
        return

    _deep_analysis_in_progress.add(report_id)

    try:
        # Load skeleton report
        from pathlib import Path
        _data_dir = Path("/data")
        reports_dir = _data_dir / "reports" if _data_dir.is_dir() else Path(__file__).parent.parent / "reports"
        analysis_path = reports_dir / report_id / "analysis.json"

        if not analysis_path.exists():
            logger.error(f"No skeleton found for {report_id}")
            yield {"event": "error", "data": {"message": "Report not found"}}
            return

        with open(analysis_path) as f:
            skeleton = json.load(f)

        # If already fully analyzed, just send done
        if skeleton.get("_phase") == "complete":
            logger.info(f"Report {report_id} already complete, skipping deep analysis")
            yield {"event": "already_complete", "data": {}}
            return

        startup_data = skeleton.get("_startup_data", "")
        if not startup_data:
            logger.error(f"No startup data in skeleton for {report_id}")
            yield {"event": "error", "data": {"message": "Missing startup data"}}
            return

        # If startup_data is just a bare URL (no scraped content), scrape it directly.
        # Don't wait 60s for a background task — just do it inline.
        if startup_data.strip().count("\n") < 3 and len(startup_data) < 200:
            logger.info(f"[DEEP] Startup data looks bare ({len(startup_data)} chars), scraping directly...")
            yield {"event": "thinking", "data": {"message": "Scraping website data...", "detail": "Fetching content from the site"}}

            # First: quick check if background task already enriched the file (give it 5s)
            for _wait in range(5):
                await asyncio.sleep(1)
                try:
                    with open(analysis_path) as f2:
                        refreshed = json.load(f2)
                    new_data = refreshed.get("_startup_data", "")
                    if new_data and new_data.strip().count("\n") >= 3 and len(new_data) > 200:
                        startup_data = new_data
                        skeleton = refreshed
                        logger.info(f"[DEEP] Background scrape finished ({len(startup_data)} chars)")
                        break
                except Exception:
                    pass

            # If still bare, scrape directly (don't wait any longer)
            if startup_data.strip().count("\n") < 3 and len(startup_data) < 200:
                logger.info(f"[DEEP] Background scrape didn't finish, scraping directly now")
                try:
                    from src.modules.scraper import scrape_website
                    import re as _re
                    # Extract URL from startup_data (format: "## WEBSITE DATA\nURL: https://...")
                    url_match = _re.search(r'https?://\S+', startup_data)
                    target_url = url_match.group(0) if url_match else startup_data.strip()
                    if target_url.startswith("http"):
                        site_data = await scrape_website(target_url)
                        if site_data.get("content") and len(site_data["content"]) > 100:
                            parts = [f"## WEBSITE DATA\nURL: {site_data['url']}"]
                            if site_data.get("title"):
                                parts.append(f"Title: {site_data['title']}")
                            if site_data.get("description"):
                                parts.append(f"Description: {site_data['description']}")
                            parts.append(f"\nContent:\n{site_data['content'][:8000]}")
                            startup_data = "\n".join(parts)
                            logger.info(f"[DEEP] Direct scrape succeeded ({len(startup_data)} chars)")
                            # Save enriched data back to skeleton so it's not bare next time
                            skeleton["_startup_data"] = startup_data
                            try:
                                analysis_path.write_text(json.dumps(skeleton))
                            except Exception:
                                pass
                except Exception as e:
                    logger.error(f"[DEEP] Direct scrape failed: {e}")

            if startup_data.strip().count("\n") < 3 and len(startup_data) < 200:
                logger.error(f"No usable startup data after scraping for {report_id}")
                yield {"event": "error", "data": {"message": "Could not retrieve website content. Please try again."}}
                return

        record = load_record(report_id)
        startup_name = record.startup_name if record else skeleton.get("company_profile", {}).get("name", "Unknown")

        update_status(report_id, "deep_analyzing")
        yield {"event": "thinking", "data": {"message": "Initializing deep analysis engine...", "detail": f"Preparing to analyze {startup_name}"}}

        # ==========================================================
        # PHASE A: Core 19-channel analysis (scores, no deep_dive)
        # ==========================================================
        yield {"event": "thinking", "data": {"message": "Scoring 19 growth channels...", "detail": "Phase 1: evaluating channel fit for your startup"}}

        # Run core analysis with heartbeat
        _hb_queue: asyncio.Queue = asyncio.Queue()
        _hb_done = asyncio.Event()

        async def _heartbeat():
            msgs = [
                "Evaluating Viral Marketing...", "Scoring PR angles...",
                "Researching SEM keywords...", "Analyzing SEO potential...",
                "Assessing content fit...", "Mapping partnerships...",
                "Scoring community building...", "Calculating budgets...",
            ]
            idx = 0
            while not _hb_done.is_set():
                await asyncio.sleep(5)
                if _hb_done.is_set():
                    break
                msg = msgs[idx % len(msgs)] if idx < len(msgs) else f"Scoring channels ({idx * 5}s)..."
                await _hb_queue.put({"event": "thinking", "data": {"message": msg, "detail": ""}})
                idx += 1

        hb_task = asyncio.create_task(_heartbeat())
        core_task = asyncio.create_task(run_core_analysis(startup_data))

        while not core_task.done():
            try:
                event = await asyncio.wait_for(_hb_queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue

        _hb_done.set()
        hb_task.cancel()
        while not _hb_queue.empty():
            yield await _hb_queue.get()

        analysis = core_task.result()

        if "error" in analysis and "raw_response" in analysis:
            yield {"event": "error", "data": {"message": f"Analysis failed: {analysis.get('error')}"}}
            return

        if not analysis.get("company_profile"):
            analysis["company_profile"] = skeleton.get("company_profile", {})

        # Stream channels immediately (scores + ideas, no deep_dive yet)
        channels = analysis.get("channel_analysis", [])
        sorted_channels = sorted(channels, key=lambda c: c.get("score", 0), reverse=True)
        for i, ch in enumerate(sorted_channels):
            yield {"event": "thinking", "data": {"message": f"Channel {i+1}/{len(sorted_channels)}: {ch.get('channel', '')} — {ch.get('score', 0)}/10", "detail": ch.get('killer_insight', '')[:80]}}
            yield {"event": "channel", "data": {"index": i, "channel": ch}}
            await asyncio.sleep(0.1)

        # Stream channels metadata
        yield {"event": "section", "data": {
            "section": "channels_meta",
            "payload": {
                "bullseye_ranking": analysis.get("bullseye_ranking", {}),
                "executive_summary": analysis.get("executive_summary", ""),
                "hot_take": "",  # hot take comes later from Opus
                "company_profile": analysis.get("company_profile", {}),
            },
        }}

        yield {"event": "thinking", "data": {"message": "Channel scores complete. Generating detailed research...", "detail": "Deep-diving top channels + searching for leads and investors"}}

        # ==========================================================
        # PHASE B: Deep dives + Leads + Investors (all in parallel)
        # ==========================================================
        top_channels = sorted_channels[:8]
        batch1 = top_channels[:4]
        batch2 = top_channels[4:8]

        _event_queue: asyncio.Queue = asyncio.Queue()

        # Deep dive tasks
        async def _deep_batch(batch, batch_num):
            try:
                names = [c.get("channel", "") for c in batch]
                await _event_queue.put({"event": "thinking", "data": {"message": f"Deep-diving: {', '.join(names[:3])}...", "detail": f"Generating actionable research for top channels (batch {batch_num})"}})
                dives = await asyncio.wait_for(
                    run_deep_dives_batch(startup_data, analysis, batch),
                    timeout=120,
                )
                # Merge into channels and emit updates
                for ch_name, dive_data in dives.items():
                    for idx, ch in enumerate(sorted_channels):
                        if ch.get("channel", "").lower() == ch_name.lower():
                            ch["deep_dive"] = dive_data
                            await _event_queue.put({"event": "channel_update", "data": {"index": idx, "deep_dive": dive_data}})
                            await _event_queue.put({"event": "thinking", "data": {"message": f"Deep dive ready: {ch_name}", "detail": f"{len(dive_data.get('actions', []))} actions, {len(dive_data.get('research', []))} research items"}})
                            break
            except Exception as e:
                logger.warning(f"Deep dive batch {batch_num} failed: {e}")

        # Lead/investor callbacks push to the shared _event_queue
        leads_data = {}
        investors_data = {}

        async def _leads_progress(event_type, data):
            if event_type == "thinking":
                await _event_queue.put({"event": "thinking", "data": data})
            elif event_type == "persona_ready":
                p = data.get("persona", {})
                platforms = p.get("platforms", p.get("social_networks", {}).get("primary", []))
                await _event_queue.put({"event": "thinking", "data": {"message": f"Built persona: {p.get('name', 'Customer')}", "detail": f"Platforms: {', '.join(platforms[:3])}"}})
                await _event_queue.put({"event": "persona", "data": data})
            elif event_type == "lead_found":
                l = data.get("lead", {})
                await _event_queue.put({"event": "thinking", "data": {"message": f"Found lead: {l.get('name', 'Someone')}", "detail": f"{l.get('platform', '')} — Score: {l.get('score', 0)}/10"}})
                await _event_queue.put({"event": "lead", "data": data})

        async def _investors_progress(event_type, data):
            if event_type == "thinking":
                await _event_queue.put({"event": "thinking", "data": data})
            elif event_type == "competitor_found":
                c = data.get("competitor", {})
                await _event_queue.put({"event": "thinking", "data": {"message": f"Found competitor: {c.get('name', 'Company')}", "detail": f"Funding: {c.get('funding', 'Unknown')}"}})
                await _event_queue.put({"event": "competitor", "data": data})
            elif event_type == "investor_found":
                inv = data.get("investor", {})
                await _event_queue.put({"event": "thinking", "data": {"message": f"Discovered investor: {inv.get('name', 'Investor')}", "detail": f"{inv.get('type', inv.get('title', ''))} — {inv.get('focus', inv.get('thesis', ''))[:60]}"}})
                await _event_queue.put({"event": "investor", "data": data})

        async def _run_leads():
            try:
                return await asyncio.wait_for(
                    find_leads(startup_data, analysis, on_progress=_leads_progress),
                    timeout=300,
                )
            except asyncio.TimeoutError:
                logger.error(f"[DEEP] Lead research timed out for {report_id}")
                return {"personas": [], "leads": [], "_error": "timeout"}
            except Exception as e:
                logger.error(f"[DEEP] Lead research failed for {report_id}: {e}")
                return {"personas": [], "leads": [], "_error": str(e)}

        async def _run_investors():
            try:
                return await asyncio.wait_for(
                    find_investors(startup_data, analysis, on_progress=_investors_progress),
                    timeout=120,
                )
            except asyncio.TimeoutError:
                logger.error(f"[DEEP] Investor research timed out for {report_id}")
                return {"competitors": [], "competitor_investors": [], "market_investors": [], "_error": "timeout"}
            except Exception as e:
                logger.error(f"[DEEP] Investor research failed for {report_id}: {e}")
                return {"competitors": [], "competitor_investors": [], "market_investors": [], "_error": str(e)}

        # Run ALL tasks in parallel: deep dives + leads + investors + hot take
        from src.analysis.traction_engine import _generate_hot_take
        deep1_task = asyncio.create_task(_deep_batch(batch1, 1)) if batch1 else None
        deep2_task = asyncio.create_task(_deep_batch(batch2, 2)) if batch2 else None
        leads_task = asyncio.create_task(_run_leads())
        investors_task = asyncio.create_task(_run_investors())
        hot_take_task = asyncio.create_task(_generate_hot_take(analysis))

        all_tasks = [t for t in [deep1_task, deep2_task, leads_task, investors_task, hot_take_task] if t]

        # Drain events from the queue while tasks run
        while not all(t.done() for t in all_tasks):
            try:
                event = await asyncio.wait_for(_event_queue.get(), timeout=0.5)
                yield event
            except asyncio.TimeoutError:
                continue

        # Drain remaining events
        while not _event_queue.empty():
            yield await _event_queue.get()

        leads_data = leads_task.result()
        investors_data = investors_task.result()

        # Get hot take
        try:
            hot_take = hot_take_task.result()
            analysis["hot_take"] = hot_take
            yield {"event": "section", "data": {"section": "channels_meta", "payload": {
                "bullseye_ranking": analysis.get("bullseye_ranking", {}),
                "executive_summary": analysis.get("executive_summary", ""),
                "hot_take": hot_take,
                "company_profile": analysis.get("company_profile", {}),
            }}}
        except Exception as e:
            logger.warning(f"Hot take failed: {e}")
            analysis["hot_take"] = ""

        # Emit section-complete markers so client pips update
        final_leads = leads_data.get("leads", [])
        final_personas = leads_data.get("personas", [])
        final_competitors = investors_data.get("competitors", [])
        final_all_investors = investors_data.get("competitor_investors", []) + investors_data.get("market_investors", [])

        yield {"event": "section", "data": {"section": "leads_complete", "payload": {"count": len(final_leads), "persona_count": len(final_personas)}}}
        yield {"event": "section", "data": {"section": "investors_complete", "payload": {"count": len(final_all_investors), "competitor_count": len(final_competitors)}}}

        yield {"event": "thinking", "data": {"message": "Research complete. Generating strategy...", "detail": f"Found {len(final_leads)} leads, {len(final_all_investors)} investors, {len(final_competitors)} competitors"}}

        # --- Merge everything and save ---
        analysis["leads_research"] = leads_data
        analysis["investor_research"] = investors_data

        # Stream strategy sections
        yield {
            "event": "section",
            "data": {
                "section": "strategy",
                "payload": {
                    "ninety_day_plan": analysis.get("ninety_day_plan", {}),
                    "budget_allocation": analysis.get("budget_allocation", {}),
                    "risk_matrix": analysis.get("risk_matrix", []),
                    "competitive_moat": analysis.get("competitive_moat", ""),
                },
            },
        }

        # Only mark as complete if we actually got meaningful data
        channels = analysis.get("channel_analysis", [])
        if len(channels) == 0:
            logger.warning(f"[PHASE 2] Analysis completed but 0 channels — keeping as skeleton for retry")
            analysis["_phase"] = "skeleton"
            yield {"event": "error", "data": {"message": "Analysis returned empty results. Please refresh to retry."}}
            return
        analysis["_phase"] = "complete"
        # Remove raw startup data from stored analysis (no longer needed, saves space)
        analysis.pop("_startup_data", None)

        full_markdown = generate_full_report_markdown(analysis)
        save_report(report_id, analysis, full_markdown)

        update_status(report_id, "ready", startup_name=startup_name)
        try:
            db.update_report(report_id, status="ready", startup_name=startup_name)
        except Exception as e:
            logger.warning(f"Supabase update failed (non-fatal): {e}")

        # Provision advisor agent
        yield {"event": "thinking", "data": {"message": "Provisioning your AI advisor...", "detail": "Creating a personalized strategy advisor for your startup"}}
        try:
            await _provision_advisor(
                report_id=report_id,
                startup_name=startup_name,
                target=record.target if record else "",
                analysis=analysis,
                leads_data=leads_data,
                investors_data=investors_data,
            )
            yield {"event": "advisor_ready", "data": {"message": "Your AI strategy advisor is ready. Ask anything about your growth plan."}}
        except Exception as e:
            logger.warning(f"Advisor provisioning failed (non-fatal): {e}")
            yield {"event": "advisor_ready", "data": {"message": "Advisor setup in progress. Chat may be available shortly.", "partial": True}}

        logger.info(f"[PHASE 2] Deep analysis complete for {startup_name} (report={report_id})")
        yield {"event": "done", "data": {}}

    except Exception as e:
        logger.error(f"[PHASE 2] Deep analysis failed for {report_id}: {e}", exc_info=True)
        update_status(report_id, "ready")  # Fall back to skeleton data
        yield {"event": "error", "data": {"message": str(e)}}
    finally:
        _deep_analysis_in_progress.discard(report_id)


def is_deep_analysis_running(report_id: str) -> bool:
    """Check if deep analysis is currently in progress for a report."""
    return report_id in _deep_analysis_in_progress


def get_deep_progress(report_id: str) -> dict:
    """Get the current progress of a deep analysis for polling."""
    return _deep_progress.get(report_id, {})


async def run_deep_analysis_background(report_id: str):
    """
    Run deep analysis as a background task (no SSE).
    Updates _deep_progress dict so clients can poll for status.
    """
    _deep_progress[report_id] = {"status": "starting", "sections": {}, "channels": [], "leads": [], "investors": [], "competitors": [], "personas": []}

    try:
        async for event in run_deep_analysis(report_id):
            ev_type = event.get("event", "")
            ev_data = event.get("data", {})

            if ev_type == "thinking":
                _deep_progress[report_id]["status"] = ev_data.get("message", "working")
            elif ev_type == "channel":
                ch = ev_data.get("channel", {})
                if ch:
                    _deep_progress[report_id]["channels"].append(ch)
                _deep_progress[report_id]["status"] = f"Analyzing channels ({len(_deep_progress[report_id]['channels'])}/19)"
            elif ev_type == "persona":
                p = ev_data.get("persona", {})
                if p:
                    _deep_progress[report_id]["personas"].append(p)
            elif ev_type == "lead":
                l = ev_data.get("lead", {})
                if l:
                    _deep_progress[report_id]["leads"].append(l)
            elif ev_type == "competitor":
                c = ev_data.get("competitor", {})
                if c:
                    _deep_progress[report_id]["competitors"].append(c)
            elif ev_type == "investor":
                inv = ev_data.get("investor", {})
                if inv:
                    _deep_progress[report_id]["investors"].append(inv)
            elif ev_type == "section":
                section = ev_data.get("section", "")
                payload = ev_data.get("payload", {})
                _deep_progress[report_id]["sections"][section] = payload
                _deep_progress[report_id]["status"] = f"{section}_complete"
            elif ev_type == "done":
                _deep_progress[report_id]["status"] = "complete"
            elif ev_type == "error":
                _deep_progress[report_id]["status"] = "error"
                _deep_progress[report_id]["error"] = ev_data.get("message", "Unknown error")
            elif ev_type == "already_complete":
                _deep_progress[report_id]["status"] = "complete"
            elif ev_type == "already_running":
                pass  # keep current status
    except Exception as e:
        logger.error(f"Background deep analysis failed for {report_id}: {e}", exc_info=True)
        _deep_progress[report_id]["status"] = "error"
        _deep_progress[report_id]["error"] = str(e)


# =============================================================================
# Shared helpers
# =============================================================================

async def _gather_intelligence(request: AnalysisRequest, poller: TwitterPoller) -> str:
    """
    Gather all available data about the target startup.
    Combines website scraping + Twitter profile analysis.
    """
    parts = []

    if request.target_url:
        logger.info(f"Scraping website: {request.target_url}")
        site_data = await scrape_website(request.target_url)

        if site_data.get("content") and len(site_data["content"]) > 100:
            parts.append("## WEBSITE DATA")
            parts.append(f"URL: {site_data['url']}")
            if site_data.get("title"):
                parts.append(f"Title: {site_data['title']}")
            if site_data.get("description"):
                parts.append(f"Description: {site_data['description']}")
            parts.append(f"\nContent:\n{site_data['content'][:8000]}")

    if request.target_twitter_handle:
        logger.info(f"Analyzing Twitter profile: @{request.target_twitter_handle}")
        profile = await analyze_twitter_profile(request.target_twitter_handle)

        parts.append("\n## TWITTER PROFILE DATA")
        parts.append(profile.get("profile_summary", ""))

        if profile.get("website") and not request.target_url:
            logger.info(f"Found website from Twitter profile: {profile['website']}")
            site_data = await scrape_website(profile["website"])
            if site_data.get("content") and len(site_data["content"]) > 100:
                parts.append("\n## WEBSITE DATA (from Twitter profile link)")
                parts.append(f"URL: {site_data['url']}")
                if site_data.get("title"):
                    parts.append(f"Title: {site_data['title']}")
                if site_data.get("description"):
                    parts.append(f"Description: {site_data['description']}")
                parts.append(f"\nContent:\n{site_data['content'][:8000]}")

    parts.append(f"\n## REQUEST CONTEXT")
    parts.append(f"Requested by: @{request.author_username}")
    parts.append(f"Original tweet: {request.text}")

    return "\n".join(parts)


def _post_teaser_thread(
    poller: TwitterPoller,
    tweet_id: str,
    tweets: list[str],
    media_ids: list[str] | None = None,
) -> list[str]:
    """Post the teaser thread with rate-limit-safe delays between tweets."""
    reply_ids = []
    parent_id = tweet_id

    for i, text in enumerate(tweets):
        if not text:
            logger.warning(f"Skipping empty tweet {i+1}")
            continue
        tweet_media = media_ids if (i == 0 and media_ids) else None
        logger.info(f"Posting tweet {i+1}/{len(tweets)} ({len(text)} chars) replying to {parent_id}")
        try:
            reply_id = poller.reply_to_tweet(parent_id, text, media_ids=tweet_media)
        except Exception as e:
            logger.error(f"Exception posting tweet {i+1}: {e}")
            break
        if reply_id:
            reply_ids.append(reply_id)
            parent_id = reply_id
            logger.info(f"Tweet {i+1} posted: {reply_id}")
        else:
            logger.warning(f"Failed to post tweet {i+1} of thread (returned None)")
            break
        if i < len(tweets) - 1:
            delay = random.uniform(2.0, 5.0)
            logger.info(f"Thread delay: {delay:.1f}s before next tweet")
            time.sleep(delay)

    return reply_ids


# --- Acknowledgment message templates ---

_ACK_TEMPLATES = [
    (
        "\U0001f50d mckoutie's analysts are suiting up... "
        "give us a minute while we research {target}\n\n"
        "Full 19-channel traction breakdown incoming. Thread soon."
    ),
    (
        "\U0001f453 *adjusts tiny capybara glasses*\n\n"
        "Researching {target} right now, @{author}. "
        "Quick thread coming in ~30 seconds. Full dashboard after."
    ),
    (
        "\U0001f4cb Copy that, @{author}.\n\n"
        "Our capybara analysts are pulling up everything on {target}. "
        "Thread dropping in seconds."
    ),
    (
        "\U0001f680 On it! Firing up the traction engine for {target}.\n\n"
        "@{author} thread incoming fast — full dashboard with 19 channels "
        "unlocks when you visit the link."
    ),
    (
        "\U0001f9e0 Engaging big brain mode for {target}...\n\n"
        "@{author} quick analysis coming in ~30s. "
        "The DEEP analysis starts when you open the dashboard."
    ),
]


def _generate_ack_message(author_username: str, target_display: str) -> str:
    template = random.choice(_ACK_TEMPLATES)
    return template.format(author=author_username, target=target_display)


# --- Advisor Provisioning ---

async def _provision_advisor(
    report_id: str,
    startup_name: str,
    target: str,
    analysis: dict,
    leads_data: dict,
    investors_data: dict,
):
    """Provision a per-user AI advisor agent on the VPS."""
    import httpx
    import json as _json

    if not settings.advisor_url or not settings.advisor_api_key:
        logger.info("Advisor service not configured — skipping provisioning")
        return

    profile = analysis.get("company_profile", {})

    payload = {
        "agent_id": report_id,
        "startup_name": startup_name,
        "startup_url": target,
        "industry": profile.get("market", "") or profile.get("industry", ""),
        "stage": profile.get("stage", "early"),
        "report_summary": analysis.get("executive_summary", ""),
        "channels_data": _json.dumps(analysis.get("channels", [])[:5]),
        "leads_data": _json.dumps(leads_data.get("leads", [])[:5]),
        "investors_data": _json.dumps(investors_data.get("market_investors", [])[:5]),
        "hot_take": analysis.get("hot_take", ""),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.advisor_url}/provision",
            json=payload,
            headers={"X-Advisor-Key": settings.advisor_api_key},
        )
        resp.raise_for_status()
        logger.info(f"Advisor provisioned for {startup_name} (report={report_id})")
