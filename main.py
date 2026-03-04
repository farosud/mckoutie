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
from src.modules.market_updater import update_loop
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

    poll_count = 0
    total_requests = 0

    while not _shutdown.is_set():
        poll_count += 1
        try:
            requests = poller.poll_mentions()

            if requests:
                total_requests += len(requests)
                logger.info(f"Found {len(requests)} new request(s)")

            # Heartbeat every 10 polls (~10 min) so we know it's alive
            if poll_count % 10 == 0:
                logger.info(
                    f"Heartbeat: {poll_count} polls completed, "
                    f"{total_requests} total requests processed"
                )

            # Process each request (sequentially to avoid rate limits)
            for req in requests:
                try:
                    report_id = await handle_request(req, poller)
                    if report_id:
                        logger.info(f"Completed: {report_id} for @{req.author_username}")
                except Exception as e:
                    logger.error(f"Unhandled error processing {req.tweet_id}: {e}")

        except Exception as e:
            error_msg = str(e).lower()
            if "403" in error_msg or "forbidden" in error_msg:
                logger.error(
                    "Twitter API returned 403 Forbidden. "
                    "Ensure your app has Read+Write permissions and "
                    "pay-per-use credits are available. "
                    "Check: https://developer.x.com"
                )
                # Back off longer on auth errors
                await asyncio.sleep(300)
                continue
            elif "429" in error_msg or "rate" in error_msg:
                logger.warning("Twitter rate limited — backing off 2 minutes")
                await asyncio.sleep(120)
                continue
            else:
                logger.error(f"Error in poll loop: {e}")

        # Wait for the next poll interval (or until shutdown)
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=settings.poll_interval_seconds)
            break  # Shutdown was signaled
        except asyncio.TimeoutError:
            pass  # Normal — just means it's time to poll again

    logger.info("Polling loop stopped")


def _validate_config():
    """Check configuration and report status. Returns warnings instead of exiting."""
    warnings = []
    errors = []

    if not settings.has_llm:
        errors.append("No LLM configured (need ANTHROPIC_API_KEY or OPENROUTER_API_KEY)")

    if not settings.has_scraping:
        warnings.append("No scraping service (EXA_API_KEY or FIRECRAWL_API_KEY) — will use Jina/raw fallback")

    if not settings.has_twitter_read:
        warnings.append("Missing Twitter OAuth keys — Twitter polling disabled")
    elif not settings.has_twitter_write:
        warnings.append("Missing some Twitter OAuth keys — can read mentions but can't reply")

    if not settings.has_payments:
        warnings.append("No STRIPE_SECRET_KEY — payments disabled, reports will be free")

    if errors:
        logger.error("Fatal configuration errors:")
        for e in errors:
            logger.error(f"  ✗ {e}")
        logger.error("Copy .env.example to .env and fill in the values")
        sys.exit(1)

    if warnings:
        logger.warning("Configuration warnings (running in degraded mode):")
        for w in warnings:
            logger.warning(f"  ⚠ {w}")


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
    """Start everything: web server + polling loop (if Twitter configured)."""
    _validate_config()

    logger.info("=" * 60)
    logger.info("  mckoutie — McKinsey at home")
    logger.info("=" * 60)
    logger.info(f"  Bot:      @{settings.bot_username}")
    logger.info(f"  Price:    ${settings.report_price_usd}/report")
    logger.info(f"  URL:      {settings.app_url}")
    logger.info(f"  Twitter:  {'read+write' if settings.has_twitter_write else 'read-only' if settings.has_twitter_read else 'DISABLED'}")
    logger.info(f"  LLM:      {'Anthropic' if settings.anthropic_api_key else 'OpenRouter' if settings.openrouter_api_key else 'NONE'}")
    logger.info(f"  Payments: {'Stripe' if settings.has_payments else 'DISABLED (free reports)'}")
    logger.info(f"  Scraping: {'Exa' if settings.exa_api_key else ''} {'Firecrawl' if settings.firecrawl_api_key else ''} {'(+Jina fallback)' if not settings.exa_api_key and not settings.firecrawl_api_key else ''}")
    logger.info("=" * 60)

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: _shutdown.set())

    tasks = [run_server()]

    if settings.has_twitter_read:
        poller = TwitterPoller()
        tasks.append(poll_loop(poller))
        logger.info(f"  Polling:  every {settings.poll_interval_seconds}s")
    else:
        logger.warning("Twitter polling DISABLED — use CLI mode: python main.py analyze <url>")

    # Always run the market intelligence update loop
    if settings.has_llm:
        tasks.append(update_loop())
        logger.info("  Updates:  active (checking every 6h, updating every 7d)")

    await asyncio.gather(*tasks)


# --- CLI mode: analyze a single URL without Twitter ---

async def analyze_cli(target: str):
    """Run analysis on a single target (URL or @handle) from the command line."""
    from src.modules.scraper import scrape_website
    from src.modules.twitter_analyzer import analyze_twitter_profile
    from src.modules.lead_finder import find_leads
    from src.modules.investor_finder import find_investors
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

    # Run lead + investor research in parallel (same as orchestrator)
    leads_data = {}
    investors_data = {}
    try:
        logger.info("Running lead + investor research (up to 120s)...")
        results = await asyncio.wait_for(
            asyncio.gather(
                find_leads(startup_data, analysis),
                find_investors(startup_data, analysis),
                return_exceptions=True,
            ),
            timeout=120,
        )
        if isinstance(results[0], dict):
            leads_data = results[0]
            logger.info(
                f"Leads: {len(leads_data.get('personas', []))} personas, "
                f"{len(leads_data.get('leads', []))} leads"
            )
        else:
            logger.warning(f"Lead research failed: {results[0]}")

        if isinstance(results[1], dict):
            investors_data = results[1]
            logger.info(
                f"Investors: {len(investors_data.get('competitors', []))} competitors, "
                f"{len(investors_data.get('market_investors', []))} market investors"
            )
        else:
            logger.warning(f"Investor research failed: {results[1]}")
    except asyncio.TimeoutError:
        logger.warning("Lead/investor research timed out (120s) — continuing without")
    except Exception as e:
        logger.warning(f"Lead/investor research failed (non-fatal): {e}")

    # Attach enriched data to analysis
    analysis["leads_research"] = leads_data
    analysis["investor_research"] = investors_data

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

    # Show lead/investor summary
    personas = leads_data.get("personas", [])
    leads = leads_data.get("leads", [])
    competitors = investors_data.get("competitors", [])
    market_inv = investors_data.get("market_investors", [])

    if personas or leads or competitors or market_inv:
        print("\n--- ENRICHMENT ---")
        print(f"  Personas: {len(personas)}")
        print(f"  Leads: {len(leads)}")
        print(f"  Competitors: {len(competitors)}")
        print(f"  Market investors: {len(market_inv)}")
    else:
        print("\n--- ENRICHMENT ---")
        print("  No lead/investor data (check EXA_API_KEY)")

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
