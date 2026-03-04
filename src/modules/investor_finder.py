"""
Investor finder module — discovers relevant investors via competitor analysis.

Two-phase approach:
1. Find competitors in the space -> identify who funded them
2. Search for investors active in this market/vertical

Both phases run Exa queries in parallel (throttled via semaphore).
"""

import asyncio
import json
import logging
import random
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# Semaphore to avoid blasting Exa with too many concurrent requests
_EXA_SEMAPHORE = asyncio.Semaphore(3)

# Shared Exa timeout config — 15s per request, 5s connect
# Exa typically responds in <2s; anything over 15s is hung
_EXA_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


async def find_investors(startup_data: str, analysis: dict) -> dict:
    """
    Find relevant investors for a startup by analyzing competitors' funding
    and searching for active investors in the space.

    This function NEVER raises — all errors are caught and logged.
    Returns a dict with competitors, competitor_investors, and market_investors.
    """
    profile = analysis.get("company_profile", {})
    market = profile.get("market", "")
    name = profile.get("name", "")
    one_liner = profile.get("one_liner", "")

    result = {
        "competitors": [],
        "competitor_investors": [],
        "market_investors": [],
    }

    if not settings.exa_api_key:
        logger.warning("[INVESTORS] No EXA_API_KEY set — skipping investor search")
        return result

    logger.info(
        f"[INVESTORS] Starting investor finder for '{name or 'unknown startup'}' "
        f"| market='{market[:60]}' | one_liner='{one_liner[:60]}' "
        f"| exa_key_starts={settings.exa_api_key[:8]}..."
    )

    # Run both phases in parallel with independent error handling
    comp_task = _find_competitors(name, one_liner, market)
    market_inv_task = _find_market_investors(name, market, one_liner)

    comp_result, market_result = await asyncio.gather(
        comp_task, market_inv_task, return_exceptions=True
    )

    # Handle competitors
    if isinstance(comp_result, Exception):
        logger.error(
            f"[INVESTORS] Competitor search failed: {type(comp_result).__name__}: {comp_result}",
            exc_info=comp_result,
        )
        competitors = []
    else:
        competitors = comp_result
        logger.info(f"[INVESTORS] Found {len(competitors)} competitors")

    result["competitors"] = competitors
    result["competitor_investors"] = _extract_competitor_investors(competitors)

    # Handle market investors
    if isinstance(market_result, Exception):
        logger.error(
            f"[INVESTORS] Market investor search failed: {type(market_result).__name__}: {market_result}",
            exc_info=market_result,
        )
    else:
        result["market_investors"] = market_result
        logger.info(f"[INVESTORS] Found {len(market_result)} market investors")

    logger.info(
        f"[INVESTORS] Complete — "
        f"{len(result['competitors'])} competitors, "
        f"{len(result['competitor_investors'])} competitor investors, "
        f"{len(result['market_investors'])} market investors"
    )
    return result


async def _find_competitors(name: str, one_liner: str, market: str) -> list[dict]:
    """Find competitors via parallel Exa searches."""
    competitors = []
    seen = set()

    # Build targeted queries using one_liner for context when market is vague
    context = one_liner if one_liner else market
    if not context:
        context = name

    queries = []
    # Query 1: competitors with funding (use one_liner for specificity)
    if market and len(market.split()) > 2:
        queries.append(f"{market} startup raised funding round"[:100])
    else:
        queries.append(f"{context} competitors startup funding"[:100])

    # Query 2: direct competitor search
    if name and name.lower() not in ("unknown", ""):
        queries.append(f"{name} alternatives competitors {market}"[:100])
    else:
        queries.append(f"startups like {context} raised seed series A"[:100])

    # Query 3: add a crunchbase/techcrunch style query for better funding data
    queries.append(f"{market} startup funding announcement 2024 2025"[:100])

    for q in queries:
        logger.info(f"[INVESTORS] Competitor query: {q}")

    # Run competitor queries in parallel
    tasks = [_exa_search_throttled(q, num_results=5) for q in queries]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    fail_count = 0
    for i, results in enumerate(results_list):
        if isinstance(results, Exception):
            fail_count += 1
            logger.warning(
                f"[INVESTORS] Competitor search query {i} failed: "
                f"{type(results).__name__}: {results}"
            )
            continue
        success_count += 1
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            if url in seen or not title:
                continue
            seen.add(url)

            text = r.get("text", "")[:500]
            funding = _extract_funding(text)
            investors = _extract_investor_names(text)

            competitors.append({
                "name": title[:60],
                "url": url,
                "description": text[:200],
                "funding": funding,
                "investors": investors,
            })

    logger.info(
        f"[INVESTORS] Competitor searches: {success_count} succeeded, "
        f"{fail_count} failed, {len(competitors)} competitors found"
    )
    return competitors[:8]


async def _find_market_investors(name: str, market: str, one_liner: str) -> list[dict]:
    """Find investors active in this market via parallel Exa searches."""
    investors = []
    seen_urls = set()

    # Build specific investor queries
    context = one_liner if one_liner else market
    if not context:
        context = name

    queries = [
        f"venture capital investing in {context}"[:100],
        f"VC fund {market} portfolio companies startups"[:100],
        f"angel investor {market} seed round investment"[:100],
    ]

    for q in queries:
        logger.info(f"[INVESTORS] Market investor query: {q}")

    # Run investor queries in parallel
    tasks = [_exa_search_throttled(q, num_results=5) for q in queries]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    fail_count = 0
    for i, results in enumerate(results_list):
        if isinstance(results, Exception):
            fail_count += 1
            logger.warning(
                f"[INVESTORS] Market investor search query {i} failed: "
                f"{type(results).__name__}: {results}"
            )
            continue
        success_count += 1
        for r in results:
            url = r.get("url", "")
            if url in seen_urls or not url:
                continue
            seen_urls.add(url)

            title = r.get("title", "")
            text = r.get("text", "")[:300]

            # Determine type
            inv_type = "Unknown"
            source = "web"
            if "linkedin.com" in url:
                inv_type = "Individual"
                source = "linkedin"
            elif any(w in text.lower() for w in ["venture", "capital", "fund", "vc"]):
                inv_type = "VC"
            elif any(w in text.lower() for w in ["angel", "seed"]):
                inv_type = "Angel"

            # Score relevance
            score = 5
            market_words = set(market.lower().split())
            text_words = set(text.lower().split())
            overlap = len(market_words & text_words)
            score = min(5 + overlap, 10)

            investors.append({
                "name": title[:80],
                "title": inv_type,
                "url": url,
                "source": source,
                "focus": market[:100],
                "relevance_signal": text[:150],
                "score": score,
            })

    logger.info(
        f"[INVESTORS] Market investor searches: {success_count} succeeded, "
        f"{fail_count} failed, {len(investors)} investors found"
    )
    investors.sort(key=lambda x: x.get("score", 0), reverse=True)
    return investors[:10]


def _extract_competitor_investors(competitors: list[dict]) -> list[dict]:
    """Extract unique investors mentioned across competitors."""
    investor_map = {}
    for comp in competitors:
        for inv_name in comp.get("investors", []):
            if inv_name not in investor_map:
                investor_map[inv_name] = {
                    "name": inv_name,
                    "type": "VC/Angel",
                    "portfolio_company": comp.get("name", ""),
                    "url": "",
                    "relevance": f"Invested in {comp.get('name', 'competitor')}",
                }
    return list(investor_map.values())[:10]


def _extract_funding(text: str) -> str:
    """Try to find funding amounts in text."""
    patterns = [
        r"\$[\d,.]+\s*[MBK]\b",                                    # $10M, $2.5B, $500K
        r"\$[\d,.]+\s*(?:million|billion)",                         # $10 million
        r"(?:raised|secured|closed)\s+\$[\d,.]+\s*[MBK]?",         # raised $10M
        r"\$[\d,.]+[MBK]?\s*(?:series\s*[A-Z]|seed|round|funding|raised)",
        r"(?:raised|funding|series\s*[A-Z]|seed)\s*(?:of\s*)?\$[\d,.]+[MBK]?",
        r"(?:USD|US\$)\s*[\d,.]+\s*(?:million|billion|[MBK])",     # USD 10 million
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ""


def _extract_investor_names(text: str) -> list[str]:
    """Try to find investor/VC names in text."""
    patterns = [
        r"(?:led by|from|backed by|invested by)\s+([A-Z][A-Za-z\s&]+?)(?:\s*[,.]|\s+and\b)",
        r"([A-Z][a-z]+\s+(?:Capital|Ventures|Partners|Labs|Fund|Group))",
    ]
    names = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            name = m.strip()
            if 3 < len(name) < 50:
                names.append(name)
    return list(set(names))[:5]


async def _exa_search_throttled(query: str, num_results: int = 5) -> list[dict]:
    """Exa search with concurrency throttle via semaphore."""
    async with _EXA_SEMAPHORE:
        return await _exa_search(query, num_results)


async def _exa_search(query: str, num_results: int = 5) -> list[dict]:
    """Run an Exa semantic search with text content. Retries once on 429/5xx."""
    if not settings.exa_api_key:
        logger.warning("[INVESTORS] Exa search skipped — no API key")
        return []

    last_error = None
    # Create client ONCE outside the retry loop to reuse connections
    async with httpx.AsyncClient(timeout=_EXA_TIMEOUT) as client:
        for attempt in range(2):  # 2 attempts max (down from 3)
            try:
                logger.info(
                    f"[INVESTORS] Exa search attempt {attempt+1}/2: {query[:80]}"
                )
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={
                        "x-api-key": settings.exa_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "numResults": num_results,
                        "type": "auto",
                        "contents": {
                            "text": {"maxCharacters": 1200},  # more text = better funding/investor extraction
                        },
                    },
                )

                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1) + random.uniform(0, 1)
                    logger.warning(
                        f"[INVESTORS] Exa rate limited (429), backing off {wait:.1f}s "
                        f"(attempt {attempt+1}/2) — query: {query[:60]}"
                    )
                    await asyncio.sleep(wait)
                    last_error = "rate limited (429)"
                    continue

                if resp.status_code == 401:
                    logger.error(
                        f"[INVESTORS] Exa API 401 Unauthorized — check EXA_API_KEY. "
                        f"Key starts with: {settings.exa_api_key[:8]}..."
                    )
                    return []

                if resp.status_code >= 500:
                    body = resp.text[:300]
                    logger.warning(
                        f"[INVESTORS] Exa server error {resp.status_code} "
                        f"(attempt {attempt+1}/2): {body}"
                    )
                    last_error = f"HTTP {resp.status_code}: {body}"
                    if attempt < 1:
                        await asyncio.sleep(2)
                    continue

                if resp.status_code >= 400:
                    body = resp.text[:300]
                    logger.error(
                        f"[INVESTORS] Exa API {resp.status_code}: {body} — "
                        f"query: {query[:60]}"
                    )
                    last_error = f"HTTP {resp.status_code}: {body}"
                    return []

                data = resp.json()
                results = data.get("results", [])
                logger.info(
                    f"[INVESTORS] Exa returned {len(results)} results for: {query[:60]}"
                )
                return results

            except httpx.TimeoutException:
                last_error = "timeout"
                logger.warning(
                    f"[INVESTORS] Exa search timeout (attempt {attempt+1}/2): {query[:60]}"
                )
                if attempt < 1:
                    await asyncio.sleep(1)
            except httpx.ConnectError as e:
                last_error = f"connect error: {e}"
                logger.warning(
                    f"[INVESTORS] Exa connect error (attempt {attempt+1}/2): {e}"
                )
                if attempt < 1:
                    await asyncio.sleep(1)
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[INVESTORS] Exa search error (attempt {attempt+1}/2): "
                    f"{type(e).__name__}: {e}"
                )
                if attempt < 1:
                    await asyncio.sleep(1)

    logger.error(
        f"[INVESTORS] Exa search failed after 2 attempts: {last_error} — "
        f"query: {query[:80]}"
    )
    return []
