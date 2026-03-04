"""
Investor discovery engine — finds relevant investors via competitor analysis.

Pipeline:
  1. LLM identifies competitors in the space
  2. Exa finds which investors funded those competitors
  3. Exa finds other investors active in the space
  4. Returns structured investor intelligence
"""

import asyncio
import json
import logging
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

COMPETITOR_SYSTEM_PROMPT = """You are mckoutie's competitive intelligence engine.
Given a startup profile, identify the competitive landscape and investor targets."""

COMPETITOR_PROMPT = """Analyze this startup and identify competitors + investor landscape.

## COMPANY PROFILE
{company_profile}

## STARTUP DATA
{startup_data}

Return valid JSON:
{{
  "competitors": [
    {{
      "name": "string — competitor company name",
      "url": "string — their website URL (best guess)",
      "one_liner": "string — what they do",
      "stage": "string — seed | series-a | series-b | growth | public",
      "estimated_funding": "string — total funding estimate",
      "why_competitor": "string — how they overlap with this startup",
      "differentiation": "string — how this startup is different/better"
    }}
  ],
  "investor_search_queries": [
    "string — 5-7 Exa search queries to find investors who invest in this space. Include queries like 'invested in [competitor]', '[industry] seed round', 'VC [market] portfolio'"
  ],
  "market_category": "string — the investment category (e.g. 'AI tools', 'creator economy', 'fintech')",
  "investor_thesis_keywords": ["5-7 keywords that describe what investors in this space care about"]
}}

Be specific — name REAL competitors that exist, not hypothetical ones.
Include 5-10 competitors across direct and adjacent spaces."""


async def discover_investors(startup_data: str, company_profile: dict) -> dict:
    """
    Full investor discovery pipeline.

    Returns:
    {
        "competitors": [...],
        "competitor_investors": [...],
        "potential_investors": [...],
        "market_category": "...",
    }
    """
    # Step 1: LLM identifies competitors and search strategy
    competitor_data = await _identify_competitors(startup_data, company_profile)

    competitors = competitor_data.get("competitors", [])
    search_queries = competitor_data.get("investor_search_queries", [])
    market_category = competitor_data.get("market_category", "")

    # Step 2: Find investors who funded competitors (via Exa)
    competitor_investors = []
    if settings.exa_api_key and competitors:
        competitor_investors = await _find_competitor_investors(competitors)

    # Step 3: Find other potential investors in the space (via Exa)
    potential_investors = []
    if settings.exa_api_key and search_queries:
        potential_investors = await _find_space_investors(
            search_queries, market_category
        )

    # Deduplicate investors
    seen = set()
    deduped_competitor = []
    for inv in competitor_investors:
        key = inv.get("name", "").lower()
        if key and key not in seen:
            seen.add(key)
            deduped_competitor.append(inv)

    deduped_potential = []
    for inv in potential_investors:
        key = inv.get("name", "").lower()
        if key and key not in seen:
            seen.add(key)
            deduped_potential.append(inv)

    return {
        "competitors": competitors,
        "competitor_investors": deduped_competitor[:15],
        "potential_investors": deduped_potential[:15],
        "market_category": market_category,
        "thesis_keywords": competitor_data.get("investor_thesis_keywords", []),
    }


async def _identify_competitors(startup_data: str, company_profile: dict) -> dict:
    """Use LLM to identify competitors and investment landscape."""
    prompt = COMPETITOR_PROMPT.format(
        startup_data=startup_data[:4000],
        company_profile=json.dumps(company_profile, indent=2),
    )

    text = await _call_llm(COMPETITOR_SYSTEM_PROMPT, prompt)
    return _parse_json(text)


async def _find_competitor_investors(competitors: list[dict]) -> list[dict]:
    """Search Exa for investors who funded specific competitors."""
    investors = []

    async with httpx.AsyncClient(timeout=30) as client:
        for comp in competitors[:7]:  # Limit API calls
            name = comp.get("name", "")
            if not name:
                continue

            queries = [
                f"{name} funding round investors",
                f"{name} raised series seed investment",
            ]

            for query in queries[:1]:  # One query per competitor
                try:
                    resp = await client.post(
                        "https://api.exa.ai/search",
                        headers={
                            "x-api-key": settings.exa_api_key,
                            "Content-Type": "application/json",
                        },
                        json={
                            "query": query,
                            "numResults": 3,
                            "text": True,
                            "type": "auto",
                            "useAutoprompt": True,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for result in data.get("results", []):
                        # Extract investor info from search results
                        investor_info = _extract_investor_from_result(
                            result, comp_name=name
                        )
                        if investor_info:
                            investors.extend(investor_info)

                except Exception as e:
                    logger.warning(f"Exa investor search failed for {name}: {e}")

                await asyncio.sleep(0.3)

    return investors


async def _find_space_investors(queries: list[str], market_category: str) -> list[dict]:
    """Search Exa for investors active in the startup's space."""
    investors = []

    # Add some standard investor discovery queries
    all_queries = queries[:4]
    if market_category:
        all_queries.append(f"VC fund investing in {market_category} startups 2025 2026")
        all_queries.append(f"angel investor {market_category} portfolio")

    async with httpx.AsyncClient(timeout=30) as client:
        for query in all_queries[:5]:
            try:
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={
                        "x-api-key": settings.exa_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "numResults": 5,
                        "text": True,
                        "type": "auto",
                        "useAutoprompt": True,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for result in data.get("results", []):
                    investor_info = _extract_investor_from_result(result)
                    if investor_info:
                        investors.extend(investor_info)

            except Exception as e:
                logger.warning(f"Exa space investor search failed: {e}")

            await asyncio.sleep(0.3)

    return investors


def _extract_investor_from_result(result: dict, comp_name: str = "") -> list[dict]:
    """Extract investor names/info from an Exa search result."""
    investors = []
    title = result.get("title", "")
    text = result.get("text", "")[:2000]
    url = result.get("url", "")

    # Common VC/investor patterns in text
    # Look for "led by [Firm]", "backed by [Firm]", "[Firm] invested", etc.
    patterns = [
        r"(?:led by|backed by|from|invested by)\s+([A-Z][A-Za-z\s&]+?)(?:\s*[,.]|\s+and\s)",
        r"([A-Z][A-Za-z\s&]+?)\s+(?:led|invested|participated|joined)",
        r"investors?\s+(?:include|including)\s+([A-Z][A-Za-z\s&,]+?)(?:\s*\.)",
    ]

    found_names = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Split on commas/and for lists
            parts = re.split(r"\s*[,&]\s*|\s+and\s+", match)
            for part in parts:
                name = part.strip()
                if len(name) > 3 and len(name) < 50 and name[0].isupper():
                    found_names.add(name)

    for name in found_names:
        investors.append({
            "name": name,
            "source_url": url,
            "source_title": title,
            "funded_competitor": comp_name,
            "context": text[:200],
        })

    # If no investors extracted but it's a funding article, create a generic entry
    if not investors and any(w in title.lower() for w in ["funding", "raises", "investment", "series", "seed"]):
        investors.append({
            "name": f"See article: {title[:80]}",
            "source_url": url,
            "source_title": title,
            "funded_competitor": comp_name,
            "context": text[:200],
        })

    return investors


async def _call_llm(system: str, prompt: str) -> str:
    """Call LLM — VPS proxy first, then OpenRouter, then Anthropic direct."""
    if settings.has_vps_proxy:
        try:
            return await _call_vps_proxy(system, prompt)
        except RuntimeError as e:
            logger.warning(f"VPS proxy failed: {e}")
    if settings.openrouter_api_key:
        try:
            return await _call_openrouter(system, prompt)
        except RuntimeError as e:
            logger.warning(f"OpenRouter failed: {e}")
    if settings.anthropic_api_key:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=settings.analysis_model,
            max_tokens=6000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    raise RuntimeError("No LLM provider available")


async def _call_vps_proxy(system: str, prompt: str) -> str:
    """Call VPS Claude proxy."""
    url = f"{settings.vps_proxy_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-Proxy-Key": settings.vps_proxy_key,
            },
            json={
                "model": settings.analysis_model,
                "max_tokens": 6000,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"VPS proxy {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_openrouter(system: str, prompt: str) -> str:
    """Call OpenRouter API (fallback)."""
    model = settings.analysis_model
    if "/" not in model:
        model = re.sub(r"-\d{8}$", "", model)
        model = f"anthropic/{model}"

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://mckoutie.com",
                "X-Title": "mckoutie",
            },
            json={
                "model": model,
                "max_tokens": 6000,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        candidate = text[start:end + 1]
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return {"competitors": [], "error": "Failed to parse competitor data"}
