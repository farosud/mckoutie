"""
Market intelligence updater — keeps reports alive for active subscribers.

Periodically re-scrapes targets, gathers fresh market signals, and appends
an "intelligence update" section to existing reports. This is what makes
the $39/mo subscription worthwhile — your report gets smarter over time.

Update cadence: every 7 days for active subscriptions.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.config import settings
from src.modules.report_store import (
    REPORTS_DIR,
    ReportRecord,
    find_active_subscriptions,
    load_record,
    save_record,
)
from src.modules.scraper import scrape_website
from src.modules.twitter_analyzer import analyze_twitter_profile

logger = logging.getLogger(__name__)

UPDATE_INTERVAL_DAYS = 7

UPDATE_SYSTEM_PROMPT = """You are mckoutie — a brutally honest AI startup consultant providing
a market intelligence update for an existing client.

You have their ORIGINAL analysis and are now looking at FRESH data about their startup.
Your job is to identify what's CHANGED, what's NEW, and what they should ADJUST in their strategy.

Be specific, action-oriented, and concise. This is a monthly check-in, not a full re-analysis.
Flag anything urgent. Celebrate wins. Call out missed opportunities."""

UPDATE_PROMPT = """Generate a market intelligence update for this startup.

## ORIGINAL ANALYSIS (from {original_date})

Company: {company_name}
One-liner: {one_liner}
Top channels: {top_channels}
Stage: {stage}

## FRESH DATA (gathered today, {today})

{fresh_data}

## YOUR TASK

Produce a JSON object with this structure:

{{
  "update_summary": "2-3 sentence executive summary of what's changed",
  "changes_detected": [
    {{
      "area": "string — what changed (website, messaging, social presence, market, etc.)",
      "observation": "string — what you noticed",
      "implication": "string — what this means for their strategy"
    }}
  ],
  "channel_adjustments": [
    {{
      "channel": "string — channel name",
      "original_score": "number",
      "new_score": "number",
      "reason": "string — why the score changed (or stayed the same)"
    }}
  ],
  "new_opportunities": ["list of 2-3 new tactical opportunities based on fresh data"],
  "warnings": ["list of any red flags or urgent items"],
  "next_30_days": "string — what they should focus on for the next 30 days based on current state",
  "hot_take": "string — one sharp observation about their progress"
}}

Only include channels in channel_adjustments if the score actually changed.
If nothing significant changed, say so honestly — don't manufacture drama.
"""


async def _gather_fresh_data(record: ReportRecord) -> str:
    """Re-scrape the target to get current state."""
    parts = []

    # Determine what to scrape
    target = record.target
    if target.startswith("@"):
        handle = target.lstrip("@")
        try:
            profile = await analyze_twitter_profile(handle)
            parts.append("## TWITTER PROFILE (CURRENT)")
            parts.append(profile.get("profile_summary", ""))
            if profile.get("website"):
                site = await scrape_website(profile["website"])
                if site.get("content") and len(site["content"]) > 100:
                    parts.append("\n## WEBSITE (CURRENT)")
                    parts.append(f"URL: {site['url']}")
                    parts.append(f"Content:\n{site['content'][:6000]}")
        except Exception as e:
            logger.warning(f"Failed to analyze Twitter profile {handle}: {e}")
    elif target.startswith("http"):
        try:
            site = await scrape_website(target)
            if site.get("content") and len(site["content"]) > 100:
                parts.append("## WEBSITE (CURRENT)")
                parts.append(f"URL: {site['url']}")
                if site.get("title"):
                    parts.append(f"Title: {site['title']}")
                parts.append(f"Content:\n{site['content'][:6000]}")
        except Exception as e:
            logger.warning(f"Failed to scrape {target}: {e}")

    return "\n".join(parts)


async def _run_update_analysis(record: ReportRecord, fresh_data: str) -> dict:
    """Run the update analysis via LLM."""
    # Load original analysis for context
    analysis_path = REPORTS_DIR / record.report_id / "analysis.json"
    original = {}
    if analysis_path.exists():
        original = json.loads(analysis_path.read_text())

    profile = original.get("company_profile", {})
    bullseye = original.get("bullseye_ranking", {})
    inner_channels = bullseye.get("inner_ring", {}).get("channels", [])

    prompt = UPDATE_PROMPT.format(
        original_date=record.created_at[:10],
        company_name=profile.get("name", record.startup_name),
        one_liner=profile.get("one_liner", ""),
        top_channels=", ".join(inner_channels[:3]),
        stage=profile.get("stage", "unknown"),
        today=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        fresh_data=fresh_data,
    )

    import re as re_mod

    # Helper to parse LLM text response into JSON
    def _parse_update_text(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re_mod.search(r"\{.*\}", text, re_mod.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"error": "Failed to parse update", "raw": text[:2000]}

    messages = [
        {"role": "system", "content": UPDATE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    # Try VPS proxy first (Claude Max — free)
    if settings.has_vps_proxy:
        try:
            url = f"{settings.vps_proxy_url.rstrip('/')}/chat/completions"
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "X-Proxy-Key": settings.vps_proxy_key,
                    },
                    json={
                        "model": settings.update_model,  # Haiku — fast delta analysis
                        "max_tokens": 4000,
                        "messages": messages,
                    },
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"]
                    return _parse_update_text(text)
                else:
                    logger.warning(f"VPS proxy returned {resp.status_code} for update")
        except Exception as e:
            logger.warning(f"VPS proxy failed for update: {e}")

    # Fallback to OpenRouter
    if settings.openrouter_api_key:
        model = settings.update_model_fallback  # Haiku on OpenRouter

        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://mckoutie.com",
                    "X-Title": "mckoutie-update",
                },
                json={
                    "model": model,
                    "max_tokens": 4000,
                    "messages": messages,
                },
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                return _parse_update_text(text)
            else:
                return {"error": f"LLM returned {resp.status_code}"}

    return {"error": "No LLM provider available for updates"}


def _append_update_to_report(report_id: str, update: dict, update_number: int) -> None:
    """Append the intelligence update to the existing markdown report."""
    report_path = REPORTS_DIR / report_id / "report.md"
    if not report_path.exists():
        return

    now = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    existing = report_path.read_text()

    update_md = f"\n\n---\n\n## Market Intelligence Update #{update_number}\n"
    update_md += f"*{now}*\n\n"

    summary = update.get("update_summary", "")
    if summary:
        update_md += f"**Summary:** {summary}\n\n"

    # Changes detected
    changes = update.get("changes_detected", [])
    if changes:
        update_md += "### Changes Detected\n\n"
        for ch in changes:
            update_md += f"- **{ch.get('area', '')}:** {ch.get('observation', '')}\n"
            update_md += f"  - *Implication:* {ch.get('implication', '')}\n"
        update_md += "\n"

    # Channel adjustments
    adjustments = update.get("channel_adjustments", [])
    if adjustments:
        update_md += "### Channel Score Adjustments\n\n"
        update_md += "| Channel | Was | Now | Reason |\n"
        update_md += "|---------|-----|-----|--------|\n"
        for adj in adjustments:
            update_md += (
                f"| {adj.get('channel', '')} | {adj.get('original_score', '?')}/10 | "
                f"{adj.get('new_score', '?')}/10 | {adj.get('reason', '')} |\n"
            )
        update_md += "\n"

    # New opportunities
    opps = update.get("new_opportunities", [])
    if opps:
        update_md += "### New Opportunities\n\n"
        for opp in opps:
            update_md += f"- {opp}\n"
        update_md += "\n"

    # Warnings
    warnings = update.get("warnings", [])
    if warnings:
        update_md += "### Warnings\n\n"
        for w in warnings:
            update_md += f"- {w}\n"
        update_md += "\n"

    # Next 30 days
    next30 = update.get("next_30_days", "")
    if next30:
        update_md += f"### Focus for Next 30 Days\n\n{next30}\n\n"

    # Hot take
    hot = update.get("hot_take", "")
    if hot:
        update_md += f"### Hot Take\n\n*{hot}*\n"

    # Append to report
    report_path.write_text(existing + update_md)

    # Also save the raw update JSON
    updates_dir = REPORTS_DIR / report_id / "updates"
    updates_dir.mkdir(exist_ok=True)
    with open(updates_dir / f"update_{update_number}.json", "w") as f:
        json.dump(update, f, indent=2)

    logger.info(f"Update #{update_number} appended to report {report_id}")


async def update_single_report(record: ReportRecord) -> bool:
    """Run a market intelligence update for a single report."""
    logger.info(f"Updating report {record.report_id} ({record.startup_name})")

    try:
        fresh_data = await _gather_fresh_data(record)
        if len(fresh_data) < 50:
            logger.warning(f"Insufficient fresh data for {record.report_id}")
            return False

        update = await _run_update_analysis(record, fresh_data)
        if "error" in update:
            logger.error(f"Update analysis failed for {record.report_id}: {update['error']}")
            return False

        new_count = record.update_count + 1
        _append_update_to_report(record.report_id, update, new_count)

        # Update the record
        record.update_count = new_count
        record.last_updated_at = datetime.now(tz=timezone.utc).isoformat()
        save_record(record)

        logger.info(f"Report {record.report_id} updated (#{new_count})")
        return True

    except Exception as e:
        logger.error(f"Failed to update report {record.report_id}: {e}")
        return False


async def update_loop():
    """Background loop that updates active subscription reports periodically."""
    logger.info("Market intelligence update loop started")

    while True:
        try:
            active = find_active_subscriptions()
            if not active:
                logger.debug("No active subscriptions to update")
            else:
                now = datetime.now(tz=timezone.utc)
                for record in active:
                    # Check if update is due
                    last_update = record.last_updated_at or record.created_at
                    try:
                        last_dt = datetime.fromisoformat(last_update)
                        days_since = (now - last_dt).days
                    except (ValueError, TypeError):
                        days_since = UPDATE_INTERVAL_DAYS + 1  # force update

                    if days_since >= UPDATE_INTERVAL_DAYS:
                        logger.info(
                            f"Report {record.report_id} due for update "
                            f"({days_since} days since last update)"
                        )
                        await update_single_report(record)
                        # Small delay between updates to avoid rate limits
                        await asyncio.sleep(5)
                    else:
                        logger.debug(
                            f"Report {record.report_id} not due yet "
                            f"({days_since}/{UPDATE_INTERVAL_DAYS} days)"
                        )

        except Exception as e:
            logger.error(f"Error in update loop: {e}")

        # Check every 6 hours
        await asyncio.sleep(6 * 3600)
