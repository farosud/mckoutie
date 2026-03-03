"""
Orchestrator — the glue that connects all pieces end-to-end.

Flow:
  1. Twitter mention comes in (AnalysisRequest)
  2. Acknowledge the request (reply to tweet)
  3. Scrape the target (website or Twitter profile)
  4. Run traction analysis via Claude
  5. Generate teaser thread + full report
  6. Create Stripe checkout session
  7. Post teaser thread on Twitter
  8. Save everything to disk
"""

import asyncio
import logging
import time

from src.config import settings
from src.modules.twitter_poller import AnalysisRequest, TwitterPoller
from src.modules.scraper import scrape_website
from src.modules.twitter_analyzer import analyze_twitter_profile
from src.modules.payments import create_checkout_session
from src.modules.report_store import ReportRecord, save_record, update_status
from src.analysis.traction_engine import run_traction_analysis
from src.analysis.report_generator import (
    generate_report_id,
    generate_teaser_thread,
    generate_full_report_markdown,
    save_report,
)

logger = logging.getLogger(__name__)

# Track processed tweet IDs to avoid double-processing
_processed_tweets: set[str] = set()
MAX_PROCESSED_CACHE = 5000


async def handle_request(request: AnalysisRequest, poller: TwitterPoller) -> str | None:
    """
    Handle a single analysis request end-to-end.

    Returns the report_id on success, None on failure.
    """
    if request.tweet_id in _processed_tweets:
        logger.debug(f"Skipping already-processed tweet {request.tweet_id}")
        return None

    _processed_tweets.add(request.tweet_id)
    # Evict old entries to prevent memory leak
    if len(_processed_tweets) > MAX_PROCESSED_CACHE:
        to_remove = list(_processed_tweets)[:1000]
        for t in to_remove:
            _processed_tweets.discard(t)

    report_id = generate_report_id(request.target_display)
    startup_name = request.target_display  # will be updated after analysis

    logger.info(f"Processing request from @{request.author_username} for {request.target_display}")

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

    # 2. Acknowledge the request on Twitter (if we can write)
    if settings.has_twitter_write:
        ack_text = (
            f"On it, @{request.author_username}. "
            f"Running full 19-channel traction analysis on {request.target_display}.\n\n"
            f"This takes about 60 seconds. Thread incoming."
        )
        poller.reply_to_tweet(request.tweet_id, ack_text)
    else:
        logger.info("Twitter write disabled — skipping acknowledgment tweet")

    try:
        # 3. Gather intelligence
        startup_data = await _gather_intelligence(request, poller)

        if not startup_data or len(startup_data) < 50:
            raise ValueError(f"Insufficient data gathered for {request.target_display}")

        # 4. Run traction analysis
        analysis = await run_traction_analysis(startup_data)

        if "error" in analysis:
            raise ValueError(f"Analysis failed: {analysis.get('error', 'unknown')}")

        # Update startup name from analysis
        profile = analysis.get("company_profile", {})
        startup_name = profile.get("name", request.target_display)
        update_status(report_id, "analyzing", startup_name=startup_name)

        # 5. Generate outputs
        teaser_tweets = generate_teaser_thread(analysis)
        full_markdown = generate_full_report_markdown(analysis)
        save_report(report_id, analysis, full_markdown)

        # 6. Create Stripe checkout session (or skip if no Stripe)
        report_url = f"{settings.app_url}/report/{report_id}"
        checkout_url = None

        if settings.has_payments:
            checkout_url = create_checkout_session(
                report_id=report_id,
                startup_name=startup_name,
                tweet_author=request.author_username,
            )

        # 7. Fill in payment link in the last teaser tweet
        link = checkout_url or report_url
        if teaser_tweets:
            teaser_tweets[-1] = teaser_tweets[-1].replace("{payment_link}", link)

        # 8. Post teaser thread on Twitter (if we can write)
        if settings.has_twitter_write:
            _post_teaser_thread(poller, request.tweet_id, teaser_tweets)
        else:
            logger.info("Twitter write disabled — teaser thread saved but not posted")

        # 9. Update report status to ready
        update_status(
            report_id,
            "ready",
            startup_name=startup_name,
            checkout_url=checkout_url or report_url,
        )

        logger.info(f"Report {report_id} complete for {startup_name}")
        return report_id

    except Exception as e:
        logger.error(f"Failed to process request {request.tweet_id}: {e}")
        update_status(report_id, "failed", error=str(e))

        # Notify the user on Twitter (if we can write)
        if settings.has_twitter_write:
            error_text = (
                f"Sorry @{request.author_username}, I hit an issue analyzing {request.target_display}. "
                f"I'll look into it. Try again in a few minutes."
            )
            poller.reply_to_tweet(request.tweet_id, error_text)
        return None


async def _gather_intelligence(request: AnalysisRequest, poller: TwitterPoller) -> str:
    """
    Gather all available data about the target startup.
    Combines website scraping + Twitter profile analysis.
    """
    parts = []

    # If we have a URL, scrape the website
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

    # If we have a Twitter handle, analyze their profile
    if request.target_twitter_handle:
        logger.info(f"Analyzing Twitter profile: @{request.target_twitter_handle}")
        profile = await analyze_twitter_profile(request.target_twitter_handle)

        parts.append("\n## TWITTER PROFILE DATA")
        parts.append(profile.get("profile_summary", ""))

        # If the profile has a website and we don't have a URL yet, scrape it
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

    # Also analyze the requester's tweet for additional context
    parts.append(f"\n## REQUEST CONTEXT")
    parts.append(f"Requested by: @{request.author_username}")
    parts.append(f"Original tweet: {request.text}")

    return "\n".join(parts)


def _post_teaser_thread(poller: TwitterPoller, tweet_id: str, tweets: list[str]) -> list[str]:
    """Post the teaser thread with rate-limit-safe delays between tweets."""
    reply_ids = []
    parent_id = tweet_id

    for i, text in enumerate(tweets):
        if not text:
            continue

        reply_id = poller.reply_to_tweet(parent_id, text)
        if reply_id:
            reply_ids.append(reply_id)
            parent_id = reply_id
        else:
            logger.warning(f"Failed to post tweet {i+1} of thread")
            break

        # Small delay between tweets to avoid rate limits
        if i < len(tweets) - 1:
            time.sleep(1.5)

    return reply_ids
