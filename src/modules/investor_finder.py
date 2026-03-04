"""
Investor finder module — discovers relevant investors via competitor analysis.

Two-phase approach:
1. Find competitors in the space → identify who funded them
2. Search for investors active in this market/vertical
"""

import json
import logging
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def find_investors(startup_data: str, analysis: dict) -> dict:
    """
    Find relevant investors for a startup by analyzing competitors' funding
    and searching for active investors in the space.

    Returns:
        {
            "competitors": [
                {
                    "name": "CompetitorX",
                    "url": "https://...",
                    "description": "What they do",
                    "funding": "$5M Series A",
                    "investors": ["Investor A", "Investor B"]
                }
            ],
            "competitor_investors": [
                {
                    "name": "Sequoia Capital",
                    "type": "VC",
                    "portfolio_company": "CompetitorX",
                    "url": "https://...",
                    "relevance": "Invested in direct competitor"
                }
            ],
            "market_investors": [
                {
                    "name": "Jane Smith",
                    "title": "Angel Investor",
                    "url": "https://linkedin.com/...",
                    "focus": "AI/SaaS",
                    "relevance_signal": "Recently invested in AI tools",
                    "score": 8
                }
            ]
        }
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
        logger.warning("No Exa API key — skipping investor research")
        return result

    # Phase 1: Find competitors and their investors
    competitors = await _find_competitors(name, one_liner, market)
    result["competitors"] = competitors

    # Extract unique investors from competitors
    comp_investors = _extract_competitor_investors(competitors)
    result["competitor_investors"] = comp_investors

    # Phase 2: Find active investors in this market
    market_investors = await _find_market_investors(name, market, one_liner)
    result["market_investors"] = market_investors

    return result


async def _find_competitors(name: str, one_liner: str, market: str) -> list[dict]:
    """Find competitors via Exa search."""
    competitors = []
    seen = set()

    queries = [
        f"{market} startup raised funding round investors",
        f"{name} competitors funding series seed raised",
        f"{one_liner} startups venture capital investment",
    ]

    for query in queries[:3]:
        try:
            results = await _exa_search(query, num_results=5)
            for r in results:
                url = r.get("url", "")
                title = r.get("title", "")
                if url in seen or not title:
                    continue
                seen.add(url)

                text = r.get("text", "")[:500]

                # Try to extract funding info from text
                funding = _extract_funding(text)
                investors = _extract_investor_names(text)

                competitors.append({
                    "name": title[:60],
                    "url": url,
                    "description": text[:200],
                    "funding": funding,
                    "investors": investors,
                })
        except Exception as e:
            logger.warning(f"Competitor search failed: {e}")

    return competitors[:8]


async def _find_market_investors(name: str, market: str, one_liner: str) -> list[dict]:
    """Find investors active in this market via Exa."""
    investors = []
    seen_urls = set()

    queries = [
        f"investors funding {market} startups",
        f"angel investors {market} portfolio",
        f"VC firm investing in {one_liner[:50]}",
        f"seed investor {market} 2024 2025",
    ]

    for query in queries[:3]:
        try:
            results = await _exa_search(query, num_results=5)
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
        except Exception as e:
            logger.warning(f"Investor search failed: {e}")

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
        r"\$[\d,.]+[MBK]\s*(?:series\s*[A-Z]|seed|round|funding|raised)",
        r"(?:raised|funding|series\s*[A-Z]|seed)\s*(?:of\s*)?\$[\d,.]+[MBK]?",
        r"\$[\d,.]+\s*(?:million|billion)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ""


def _extract_investor_names(text: str) -> list[str]:
    """Try to find investor/VC names in text."""
    # Common VC name patterns
    patterns = [
        r"(?:led by|from|backed by|invested by)\s+([A-Z][A-Za-z\s&]+?)(?:\s*[,.]|\s+and\b)",
        r"([A-Z][a-z]+\s+(?:Capital|Ventures|Partners|Labs|Fund|Group))",
    ]
    names = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            name = m.strip()
            if len(name) > 3 and len(name) < 50:
                names.append(name)
    return list(set(names))[:5]


async def _exa_search(query: str, num_results: int = 5) -> list[dict]:
    """Run an Exa semantic search with text content."""
    async with httpx.AsyncClient(timeout=30) as client:
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
                    "text": {"maxCharacters": 1000},
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
