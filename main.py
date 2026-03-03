"""
mckoutie — McKinsey at home.

Entry point: starts the web server + Twitter mention polling loop.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn

from src.config import settings
from src.modules.twitter_poller import TwitterPoller
from src.orchestrator import handle_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mckoutie")

# Suppress noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("tweepy").setLevel(logging.WARNING)

_shutdown = asyncio.Event()


async def poll_loop(poller: TwitterPoller):
    """Background loop that polls Twitter for mentions and processes them."""
    logger.info(
        f"Polling loop started — checking @{settings.bot_username} "
        f"mentions every {settings.poll_interval_seconds}s"
    )

    while not _shutdown.is_set():
        try:
            requests = poller.poll_mentions()

            if requests:
                logger.info(f"Found {len(requests)} new request(s)")

            # Process each request (sequentially to avoid rate limits)
            for req in requests:
                try:
                    report_id = await handle_request(req, poller)
                    if report_id:
                        logger.info(f"Completed: {report_id} for @{req.author_username}")
                except Exception as e:
                    logger.error(f"Unhandled error processing {req.tweet_id}: {e}")

        except Exception as e:
            logger.error(f"Error in poll loop: {e}")

        # Wait for the next poll interval (or until shutdown)
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=settings.poll_interval_seconds)
            break  # Shutdown was signaled
        except asyncio.TimeoutError:
            pass  # Normal — just means it's time to poll again

    logger.info("Polling loop stopped")


def _validate_config():
    """Check that we have the minimum required configuration."""
    errors = []

    if not settings.twitter_bearer_token:
        errors.append("TWITTER_BEARER_TOKEN is required")
    if not settings.twitter_api_key:
        errors.append("TWITTER_API_KEY is required")
    if not settings.twitter_api_secret:
        errors.append("TWITTER_API_SECRET is required")
    if not settings.twitter_access_token:
        errors.append("TWITTER_ACCESS_TOKEN is required")
    if not settings.twitter_access_token_secret:
        errors.append("TWITTER_ACCESS_TOKEN_SECRET is required")
    if not settings.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY is required")
    if not settings.stripe_secret_key:
        errors.append("STRIPE_SECRET_KEY is required")

    # At least one scraping service
    if not (settings.exa_api_key or settings.firecrawl_api_key):
        errors.append("At least one of EXA_API_KEY or FIRECRAWL_API_KEY is required")

    if errors:
        logger.error("Configuration errors:")
        for e in errors:
            logger.error(f"  - {e}")
        logger.error("Copy .env.example to .env and fill in the values")
        sys.exit(1)


async def run_server():
    """Run the FastAPI server."""
    config = uvicorn.Config(
        "src.server:app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Start everything: web server + polling loop."""
    _validate_config()

    logger.info("=" * 60)
    logger.info("  mckoutie — McKinsey at home")
    logger.info("=" * 60)
    logger.info(f"  Bot:      @{settings.bot_username}")
    logger.info(f"  Price:    ${settings.report_price_usd}/report")
    logger.info(f"  URL:      {settings.app_url}")
    logger.info(f"  Polling:  every {settings.poll_interval_seconds}s")
    logger.info("=" * 60)

    poller = TwitterPoller()

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: _shutdown.set())

    # Run web server and polling loop concurrently
    await asyncio.gather(
        run_server(),
        poll_loop(poller),
    )


# --- CLI mode: analyze a single URL without Twitter ---

async def analyze_cli(target: str):
    """Run analysis on a single target (URL or @handle) from the command line."""
    from src.modules.scraper import scrape_website
    from src.modules.twitter_analyzer import analyze_twitter_profile
    from src.analysis.traction_engine import run_traction_analysis
    from src.analysis.report_generator import (
        generate_report_id,
        generate_teaser_thread,
        generate_full_report_markdown,
        save_report,
    )

    logger.info(f"CLI mode: analyzing {target}")

    parts = []

    if target.startswith("@"):
        handle = target.lstrip("@")
        logger.info(f"Analyzing Twitter profile: @{handle}")
        profile = await analyze_twitter_profile(handle)
        parts.append("## TWITTER PROFILE DATA")
        parts.append(profile.get("profile_summary", ""))

        if profile.get("website"):
            logger.info(f"Also scraping website: {profile['website']}")
            site = await scrape_website(profile["website"])
            if site.get("content") and len(site["content"]) > 100:
                parts.append("\n## WEBSITE DATA")
                parts.append(f"URL: {site['url']}")
                parts.append(f"Title: {site.get('title', '')}")
                parts.append(f"Content:\n{site['content'][:8000]}")
    else:
        logger.info(f"Scraping website: {target}")
        site = await scrape_website(target)
        if site.get("content") and len(site["content"]) > 100:
            parts.append("## WEBSITE DATA")
            parts.append(f"URL: {site['url']}")
            parts.append(f"Title: {site.get('title', '')}")
            parts.append(f"Description: {site.get('description', '')}")
            parts.append(f"Content:\n{site['content'][:8000]}")

    startup_data = "\n".join(parts)

    if len(startup_data) < 50:
        logger.error("Could not gather enough data. Check the URL/handle.")
        sys.exit(1)

    logger.info("Running traction analysis...")
    analysis = await run_traction_analysis(startup_data)

    if "error" in analysis:
        logger.error(f"Analysis failed: {analysis}")
        sys.exit(1)

    report_id = generate_report_id(target)
    name = analysis.get("company_profile", {}).get("name", target)

    teaser = generate_teaser_thread(analysis)
    markdown = generate_full_report_markdown(analysis)
    report_dir = save_report(report_id, analysis, markdown)

    print("\n" + "=" * 60)
    print(f"  REPORT: {name}")
    print(f"  ID: {report_id}")
    print(f"  Saved to: {report_dir}")
    print("=" * 60)

    print("\n--- TEASER THREAD ---")
    for i, tweet in enumerate(teaser, 1):
        print(f"\nTweet {i}:")
        print(tweet)

    print(f"\n--- FULL REPORT ---")
    print(f"See: {report_dir}/report.md")
    print(f"Or run the server and visit: {settings.app_url}/report/{report_id}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "analyze":
        # CLI mode: python main.py analyze https://example.com
        if len(sys.argv) < 3:
            print("Usage: python main.py analyze <url-or-@handle>")
            sys.exit(1)
        asyncio.run(analyze_cli(sys.argv[2]))
    else:
        # Server + polling mode
        asyncio.run(main())
