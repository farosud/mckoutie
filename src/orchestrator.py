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
from src.analysis.traction_engine import run_quick_analysis, run_traction_analysis
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


# =============================================================================
# PHASE 1 — Quick analysis on tweet (fast, cheap)
# =============================================================================

async def handle_request(request: AnalysisRequest, poller: TwitterPoller) -> str | None:
    """
    Handle a single analysis request — PHASE 1 ONLY.
    Does quick analysis + tweet thread. Full analysis deferred to page visit.
    Returns the report_id on success, None on failure.
    """
    if request.tweet_id in _processed_tweets:
        logger.debug(f"Skipping already-processed tweet {request.tweet_id}")
        return None

    _processed_tweets.add(request.tweet_id)
    if len(_processed_tweets) > MAX_PROCESSED_CACHE:
        to_remove = list(_processed_tweets)[:1000]
        for t in to_remove:
            _processed_tweets.discard(t)

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

        # 7. Fill in report link
        report_url = f"https://www.mckoutie.com/report/{report_id}"
        if teaser_tweets:
            teaser_tweets[-1] = teaser_tweets[-1].replace("{report_link}", report_url)

        # 8. Post teaser thread
        if settings.has_twitter_write:
            _post_teaser_thread(poller, request.tweet_id, teaser_tweets)
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

    This is an async generator that yields SSE events:
      {"event": "section", "data": {"section": "channels", "payload": {...}}}
      {"event": "section", "data": {"section": "leads", "payload": {...}}}
      {"event": "section", "data": {"section": "investors", "payload": {...}}}
      {"event": "done", "data": {}}
    """
    if report_id in _deep_analysis_in_progress:
        logger.info(f"Deep analysis already running for {report_id}, skipping duplicate")
        yield {"event": "already_running", "data": {}}
        return

    _deep_analysis_in_progress.add(report_id)

    try:
        # Load skeleton report
        from pathlib import Path
        reports_dir = Path(__file__).parent.parent / "reports"
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

        record = load_record(report_id)
        startup_name = record.startup_name if record else skeleton.get("company_profile", {}).get("name", "Unknown")

        update_status(report_id, "deep_analyzing")
        yield {"event": "status", "data": {"message": "Starting deep analysis..."}}

        # --- Run full 19-channel analysis ---
        yield {"event": "status", "data": {"message": "Analyzing 19 growth channels..."}}

        analysis = await run_traction_analysis(startup_data)

        if "error" in analysis and "raw_response" in analysis:
            yield {"event": "error", "data": {"message": f"Analysis failed: {analysis.get('error')}"}}
            return

        # Merge quick profile data if full analysis is missing some fields
        if not analysis.get("company_profile"):
            analysis["company_profile"] = skeleton.get("company_profile", {})

        # Stream the channels as they're ready
        yield {
            "event": "section",
            "data": {
                "section": "channels",
                "payload": {
                    "channel_analysis": analysis.get("channel_analysis", []),
                    "bullseye_ranking": analysis.get("bullseye_ranking", {}),
                    "executive_summary": analysis.get("executive_summary", ""),
                    "hot_take": analysis.get("hot_take", ""),
                    "company_profile": analysis.get("company_profile", {}),
                },
            },
        }

        yield {"event": "status", "data": {"message": "Channels complete. Searching for leads and investors..."}}

        # --- Run leads + investors in parallel ---
        leads_data = {}
        investors_data = {}

        async def _run_leads():
            try:
                return await asyncio.wait_for(find_leads(startup_data, analysis), timeout=300)
            except asyncio.TimeoutError:
                logger.error(f"[DEEP] Lead research timed out for {report_id}")
                return {"personas": [], "leads": [], "_error": "timeout"}
            except Exception as e:
                logger.error(f"[DEEP] Lead research failed for {report_id}: {e}")
                return {"personas": [], "leads": [], "_error": str(e)}

        async def _run_investors():
            try:
                return await asyncio.wait_for(find_investors(startup_data, analysis), timeout=120)
            except asyncio.TimeoutError:
                logger.error(f"[DEEP] Investor research timed out for {report_id}")
                return {"competitors": [], "competitor_investors": [], "market_investors": [], "_error": "timeout"}
            except Exception as e:
                logger.error(f"[DEEP] Investor research failed for {report_id}: {e}")
                return {"competitors": [], "competitor_investors": [], "market_investors": [], "_error": str(e)}

        leads_result, investors_result = await asyncio.gather(_run_leads(), _run_investors())
        leads_data = leads_result
        investors_data = investors_result

        # Stream leads
        yield {
            "event": "section",
            "data": {
                "section": "leads",
                "payload": leads_data,
            },
        }

        # Stream investors
        yield {
            "event": "section",
            "data": {
                "section": "investors",
                "payload": investors_data,
            },
        }

        yield {"event": "status", "data": {"message": "Research complete. Generating strategy..."}}

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

        # Mark as complete
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
        try:
            await _provision_advisor(
                report_id=report_id,
                startup_name=startup_name,
                target=record.target if record else "",
                analysis=analysis,
                leads_data=leads_data,
                investors_data=investors_data,
            )
        except Exception as e:
            logger.warning(f"Advisor provisioning failed (non-fatal): {e}")

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
            continue
        tweet_media = media_ids if (i == 0 and media_ids) else None
        reply_id = poller.reply_to_tweet(parent_id, text, media_ids=tweet_media)
        if reply_id:
            reply_ids.append(reply_id)
            parent_id = reply_id
        else:
            logger.warning(f"Failed to post tweet {i+1} of thread")
            break
        if i < len(tweets) - 1:
            time.sleep(1.5)

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
