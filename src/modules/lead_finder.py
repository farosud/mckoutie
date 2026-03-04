"""
Lead finder module — generates customer personas and finds real potential leads via Exa.

Two-phase approach:
1. LLM generates 3 customer personas with pain signals + social network mapping
2. Exa semantic search finds 10 real people matching those personas
"""

import asyncio
import json
import logging
import random
import re
import time as _time

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# Semaphore to avoid blasting Exa with too many concurrent requests
_EXA_SEMAPHORE = asyncio.Semaphore(3)

# Shared Exa timeout config — 15s per request, 5s connect
# Exa typically responds in <2s; anything over 15s is hung
_EXA_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# LLM timeout — 120s per attempt (Opus needs more time for rich persona generation)
_LLM_TIMEOUT = httpx.Timeout(120.0, connect=15.0)

# Use Opus for persona generation — richer, more nuanced personas
_PERSONA_MODEL = "anthropic/claude-opus-4"
# Fallback to Gemini Flash if Opus fails on OpenRouter
_PERSONA_MODEL_FALLBACK = "google/gemini-2.5-flash"

# Use Opus on VPS — same model as main analysis
_VPS_PERSONA_MODEL = "claude-opus-4-20250918"


async def find_leads(startup_data: str, analysis: dict) -> dict:
    """
    Generate personas and find real potential leads for a startup.

    Returns dict with "personas" and "leads" keys (always populated, possibly empty).
    This function NEVER raises — all errors are caught and logged.
    """
    profile = analysis.get("company_profile", {})
    market = profile.get("market", "")
    one_liner = profile.get("one_liner", "")
    name = profile.get("name", "")

    logger.info(
        f"[LEADS] Starting lead finder for '{name or 'unknown startup'}' "
        f"| market='{market[:60]}' | one_liner='{one_liner[:60]}' "
        f"| exa_key_starts={settings.exa_api_key[:8] if settings.exa_api_key else 'MISSING'}..."
    )

    # Phase 1: Generate personas via LLM
    personas = []
    try:
        personas = await _generate_personas(startup_data, analysis)
        logger.info(f"[LEADS] Generated {len(personas)} personas")
    except Exception as e:
        logger.error(f"[LEADS] Persona generation failed entirely: {e}", exc_info=True)

    # Phase 1b: Fallback — if LLM failed, build simple personas from company profile
    if not personas:
        logger.warning("[LEADS] LLM personas empty — building fallback personas from profile")
        personas = _build_fallback_personas(profile, market, one_liner)
        logger.info(f"[LEADS] Built {len(personas)} fallback personas")

    # Phase 2: Find real leads via Exa
    leads = []
    if not settings.exa_api_key:
        logger.warning("[LEADS] No EXA_API_KEY set — skipping lead search")
    elif not personas:
        logger.warning("[LEADS] No personas generated — skipping lead search")
    else:
        try:
            leads = await _find_leads_via_exa(name, one_liner, market, personas)
        except Exception as e:
            logger.error(f"[LEADS] Exa lead search failed entirely: {e}", exc_info=True)

    logger.info(f"[LEADS] Complete — {len(personas)} personas, {len(leads)} leads")
    return {
        "personas": personas,
        "leads": leads,
    }


def _build_fallback_personas(profile: dict, market: str, one_liner: str) -> list[dict]:
    """Build simple fallback personas from company profile when LLM fails.

    These are less detailed than LLM-generated personas but ensure
    Exa searches always run — data is better than no data.
    """
    name = profile.get("name", "startup")
    stage = profile.get("stage", "launched")
    biz_model = profile.get("business_model", "")

    # Extract keywords from market/one_liner for search queries
    context = f"{one_liner} {market} {biz_model}".strip()
    if not context or len(context) < 10:
        context = name

    personas = [
        {
            "name": "Early Adopter",
            "who": f"People actively looking for solutions like {name}",
            "age_range": "25-45",
            "income": "varies",
            "pain_signals": [
                f"looking for {market} solution",
                f"frustrated with current {market} options",
                f"need help with {one_liner[:60]}",
            ],
            "social_networks": {
                "primary": ["Twitter/X", "Reddit"],
                "secondary": ["LinkedIn", "Discord"],
            },
            "subreddits": ["r/startups", "r/SaaS", "r/Entrepreneur"],
            "willingness_to_pay": "medium",
            "trigger_events": [f"discovered {market} is a problem"],
            "reachability": 7,
            "network_value": 6,
            "search_queries": [
                f"looking for {context[:80]}",
                f"site:reddit.com need help with {market[:60]}",
            ],
        },
        {
            "name": "Industry Insider",
            "who": f"Professionals in the {market} space discussing problems",
            "age_range": "28-50",
            "income": "varies",
            "pain_signals": [
                f"{market} is broken",
                f"there has to be a better way to {one_liner[:50]}",
            ],
            "social_networks": {
                "primary": ["LinkedIn", "Twitter/X"],
                "secondary": ["Reddit", "Substack"],
            },
            "subreddits": [],
            "willingness_to_pay": "high",
            "trigger_events": [f"pain point in {market}"],
            "reachability": 6,
            "network_value": 8,
            "search_queries": [
                f"{market} problems frustrations 2025 2026",
                f"alternatives to {name} {market}",
            ],
        },
        {
            "name": "Community Voice",
            "who": f"Active community members discussing {market} topics",
            "age_range": "22-40",
            "income": "varies",
            "pain_signals": [
                f"anyone know a good {market} tool",
                f"recommendation for {one_liner[:50]}",
            ],
            "social_networks": {
                "primary": ["Reddit", "Discord"],
                "secondary": ["Twitter/X", "Facebook Groups"],
            },
            "subreddits": ["r/startups"],
            "willingness_to_pay": "low-medium",
            "trigger_events": [f"asking for {market} recommendations"],
            "reachability": 8,
            "network_value": 5,
            "search_queries": [
                f"site:reddit.com recommend {market[:60]} tool",
                f"who is building in {market[:60]} space",
            ],
        },
    ]
    return personas


async def _generate_personas(startup_data: str, analysis: dict) -> list[dict]:
    """Use the LLM to generate 3 detailed customer personas."""
    profile = analysis.get("company_profile", {})

    prompt = f"""Based on this startup analysis, generate 3 detailed customer personas.
These are the people MOST LIKELY to pay for this product — lowest hanging fruit, highest impact.

Startup: {profile.get('name', 'Unknown')}
What they do: {profile.get('one_liner', '')}
Market: {profile.get('market', '')}
Stage: {profile.get('stage', '')}
Business model: {profile.get('business_model', '')}

Return valid JSON array with exactly 3 personas:
[
  {{
    "name": "string — catchy archetype name like 'The Lonely Builder'",
    "who": "string — 1-2 sentence description",
    "age_range": "string — e.g. '26-38'",
    "income": "string — income range or revenue range",
    "pain_signals": ["5-8 exact phrases/sentences these people actually say online when they have the problem this product solves"],
    "social_networks": {{
      "primary": ["2-3 platforms where they're MOST active"],
      "secondary": ["2-3 platforms where they also hang out"]
    }},
    "subreddits": ["3-5 specific subreddits they frequent"],
    "willingness_to_pay": "string — price range they'd pay",
    "trigger_events": ["3-5 specific moments when they become ready to buy"],
    "reachability": "number 1-10 — how easy to reach via cold outreach",
    "network_value": "number 1-10 — how much they amplify if they love the product",
    "search_queries": ["3-5 Exa search queries to find REAL PEOPLE expressing pain signals"]
  }}
]

CRITICAL RULES FOR search_queries:
- We want to find REAL PEOPLE talking about their problems, NOT articles or blog posts.
- Queries should find: Twitter/X posts, Reddit threads, LinkedIn posts, forum discussions, community posts.
- Good queries target social media content where people express frustration or ask for help.
- Examples of GOOD queries:
  - "I've been looking for a way to invest in real estate but don't have enough capital" (finds Reddit/forum posts)
  - "site:reddit.com frustrated with traditional investment options small amounts" (finds Reddit discussions)
  - "solo founder need advice on pricing my SaaS" (finds people asking for help)
  - "looking for alternatives to [competitor] that actually works" (finds people comparing solutions)
- Examples of BAD queries (DO NOT generate these):
  - "how to invest in real estate" (returns articles and guides, not people)
  - "best tools for startups" (returns listicles, not discussions)
  - "fractional ownership platform" (returns company pages, not users)
- Mix queries: some for Reddit/forums, some for Twitter/X, some for LinkedIn.
- Include at least one query with "site:reddit.com" prefix for targeted Reddit results.

Be SPECIFIC. Not "startup founders" but "solo SaaS founders who just launched and have <$1K MRR".
Pain signals should be REAL phrases people post online, not made-up ones."""

    try:
        text = await _call_llm(prompt)
        personas = _parse_json_array(text)
        if not personas:
            logger.error("[LEADS] Persona generation returned empty array")
        return personas
    except Exception as e:
        logger.error(f"[LEADS] Persona generation failed: {e}", exc_info=True)
        return []


async def _find_leads_via_exa(
    startup_name: str,
    one_liner: str,
    market: str,
    personas: list[dict],
) -> list[dict]:
    """Search Exa for real people matching the personas — throttled parallel."""
    t0 = _time.monotonic()
    leads = []
    seen_urls = set()

    # Build all search tasks upfront
    tasks = []
    task_meta = []  # track which persona each task belongs to

    for persona in personas[:3]:
        queries = persona.get("search_queries", [])
        # Use top 2 search queries per persona = max 6 total (down from 9)
        search_terms = queries[:2]

        # Fallback: if no search queries, build from pain signals
        if not search_terms:
            pain = persona.get("pain_signals", [])
            if pain:
                # Use first 2 pain signals as search queries — these are real phrases
                search_terms = [p.strip()[:120] for p in pain[:2] if p.strip()]
            if not search_terms:
                fallback = f"{persona.get('name', '')} {persona.get('who', '')}"
                search_terms = [fallback.strip()[:120]]

        for query in search_terms[:2]:
            clean_query = query.strip()[:120]
            if not clean_query:
                continue
            logger.info(f"[LEADS] Queuing Exa search for persona '{persona.get('name', '?')}': {clean_query[:80]}")
            tasks.append(_exa_search_throttled(query=clean_query, num_results=5))
            task_meta.append(persona)

    logger.info(f"[LEADS] Launching {len(tasks)} Exa searches (max 3 concurrent)")

    # Run all searches concurrently (semaphore limits actual concurrency)
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    fail_count = 0
    for i, result in enumerate(results_list):
        persona = task_meta[i]
        if isinstance(result, Exception):
            fail_count += 1
            logger.warning(f"[LEADS] Exa search {i} failed: {type(result).__name__}: {result}")
            continue
        success_count += 1
        for r in result:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            lead = _extract_lead_info(r, persona)
            if lead:
                leads.append(lead)

    elapsed = _time.monotonic() - t0
    logger.info(
        f"[LEADS] Exa searches done in {elapsed:.1f}s — "
        f"{success_count} succeeded, {fail_count} failed, {len(leads)} raw leads"
    )

    # Sort by score, take top 10
    leads.sort(key=lambda x: x.get("score", 0), reverse=True)
    return leads[:10]


async def _exa_search_throttled(query: str, num_results: int = 5) -> list[dict]:
    """Exa search with concurrency throttle via semaphore."""
    async with _EXA_SEMAPHORE:
        return await _exa_search(query, num_results)


async def _exa_search(query: str, num_results: int = 5) -> list[dict]:
    """Run an Exa semantic search with text content. Retries once on 429/5xx."""
    if not settings.exa_api_key:
        logger.warning("[LEADS] Exa search skipped — no API key")
        return []

    last_error = None

    # Determine if query targets specific domains (e.g. "site:reddit.com")
    include_domains = None
    clean_query = query
    if "site:" in query:
        # Extract domain filter from query and pass to Exa properly
        import re as _re
        domain_match = _re.search(r"site:(\S+)", query)
        if domain_match:
            include_domains = [domain_match.group(1)]
            clean_query = _re.sub(r"site:\S+\s*", "", query).strip()

    # Build request body — prefer social/community content for lead finding
    request_body = {
        "query": clean_query,
        "numResults": num_results,
        "type": "auto",
        "contents": {
            "text": {"maxCharacters": 1500},
        },
    }
    if include_domains:
        request_body["includeDomains"] = include_domains

    # Create client ONCE outside the retry loop to reuse connections
    async with httpx.AsyncClient(timeout=_EXA_TIMEOUT) as client:
        for attempt in range(2):  # 2 attempts max (down from 3)
            try:
                logger.info(
                    f"[LEADS] Exa search attempt {attempt+1}/2: {query[:80]}"
                    f"{' (domain: ' + include_domains[0] + ')' if include_domains else ''}"
                )
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={
                        "x-api-key": settings.exa_api_key,
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )

                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1) + random.uniform(0, 1)
                    logger.warning(
                        f"[LEADS] Exa rate limited (429), backing off {wait:.1f}s "
                        f"(attempt {attempt+1}/2) — query: {query[:60]}"
                    )
                    await asyncio.sleep(wait)
                    last_error = "rate limited (429)"
                    continue

                if resp.status_code == 401:
                    logger.error(
                        f"[LEADS] Exa API 401 Unauthorized — check EXA_API_KEY. "
                        f"Key starts with: {settings.exa_api_key[:8]}..."
                    )
                    return []

                if resp.status_code >= 500:
                    body = resp.text[:300]
                    logger.warning(
                        f"[LEADS] Exa server error {resp.status_code} "
                        f"(attempt {attempt+1}/2): {body}"
                    )
                    last_error = f"HTTP {resp.status_code}: {body}"
                    if attempt < 1:
                        await asyncio.sleep(2)
                    continue

                if resp.status_code >= 400:
                    body = resp.text[:300]
                    logger.error(
                        f"[LEADS] Exa API {resp.status_code}: {body} — "
                        f"query: {query[:60]}"
                    )
                    last_error = f"HTTP {resp.status_code}: {body}"
                    return []

                data = resp.json()
                results = data.get("results", [])
                logger.info(
                    f"[LEADS] Exa returned {len(results)} results for: {query[:60]}"
                )
                return results

            except httpx.TimeoutException:
                last_error = "timeout"
                logger.warning(
                    f"[LEADS] Exa search timeout (attempt {attempt+1}/2): {query[:60]}"
                )
                if attempt < 1:
                    await asyncio.sleep(1)
            except httpx.ConnectError as e:
                last_error = f"connect error: {e}"
                logger.warning(
                    f"[LEADS] Exa connect error (attempt {attempt+1}/2): {e}"
                )
                if attempt < 1:
                    await asyncio.sleep(1)
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[LEADS] Exa search error (attempt {attempt+1}/2): "
                    f"{type(e).__name__}: {e}"
                )
                if attempt < 1:
                    await asyncio.sleep(1)

    logger.error(
        f"[LEADS] Exa search failed after 2 attempts: {last_error} — "
        f"query: {query[:80]}"
    )
    return []


def _extract_lead_info(result: dict, persona: dict) -> dict | None:
    """Extract useful lead info from an Exa search result."""
    url = result.get("url", "")
    title = result.get("title", "")
    text = result.get("text", "")[:500]

    if not url:
        return None
    if not title:
        title = url.split("/")[-1][:60] or "Unknown"

    # Determine source type
    source = "web"
    if "twitter.com" in url or "x.com" in url:
        source = "twitter"
    elif "linkedin.com" in url:
        source = "linkedin"
    elif "reddit.com" in url:
        source = "reddit"
    elif "substack.com" in url:
        source = "substack"
    elif "medium.com" in url:
        source = "blog"

    # Simple relevance scoring
    score = 5  # base score
    pain_signals = persona.get("pain_signals", [])
    for signal in pain_signals:
        signal_words = set(signal.lower().split())
        text_words = set(text.lower().split())
        overlap = len(signal_words & text_words)
        if overlap > 3:
            score += 2
        elif overlap > 1:
            score += 1

    score = min(score, 10)

    return {
        "name": title[:80],
        "title": "",  # would need enrichment to get job title
        "url": url,
        "source": source,
        "relevance_signal": text[:150] if text else title,
        "score": score,
        "persona_match": persona.get("name", ""),
    }


async def _call_vps_proxy(prompt: str) -> str:
    """Call VPS Claude proxy for lead generation. Uses Opus for rich personas."""
    url = f"{settings.vps_proxy_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        t0 = _time.monotonic()
        try:
            logger.info(f"[LEADS] VPS proxy attempt with {_VPS_PERSONA_MODEL}")
            resp = await client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "X-Proxy-Key": settings.vps_proxy_key,
                },
                json={
                    "model": _VPS_PERSONA_MODEL,  # Opus for rich persona generation
                    "max_tokens": 4000,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are mckoutie — a startup growth expert. Return valid JSON only, no markdown wrapping.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            elapsed = _time.monotonic() - t0
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    logger.info(f"[LEADS] VPS proxy responded in {elapsed:.1f}s ({len(content)} chars)")
                    return content
                logger.warning(f"[LEADS] VPS proxy returned empty content after {elapsed:.1f}s")
            else:
                body = resp.text[:500]
                logger.warning(f"[LEADS] VPS proxy {resp.status_code} after {elapsed:.1f}s: {body}")
        except httpx.TimeoutException:
            elapsed = _time.monotonic() - t0
            logger.warning(f"[LEADS] VPS proxy timeout after {elapsed:.1f}s — falling back")
        except Exception as e:
            elapsed = _time.monotonic() - t0
            logger.warning(f"[LEADS] VPS proxy error after {elapsed:.1f}s: {e} — falling back")
    raise RuntimeError("VPS proxy failed for lead generation")


async def _call_llm(prompt: str) -> str:
    """Call LLM — tries VPS proxy (free Opus) first, then OpenRouter Gemini, then Claude.

    VPS proxy is free and uses Opus — best quality for persona generation.
    OpenRouter is the fallback chain.
    """
    last_error = None

    # Try VPS proxy FIRST (Claude Max — free, Opus quality)
    if settings.has_vps_proxy:
        try:
            return await _call_vps_proxy(prompt)
        except RuntimeError as e:
            last_error = str(e)
            logger.warning(f"[LEADS] VPS proxy failed: {e} — trying OpenRouter")

    # Fallback to OpenRouter
    if settings.openrouter_api_key:
        models_to_try = [_PERSONA_MODEL, _PERSONA_MODEL_FALLBACK]
        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            for model in models_to_try:
                for attempt in range(2):
                    t0 = _time.monotonic()
                    try:
                        logger.info(
                            f"[LEADS] LLM call attempt {attempt+1}/2 "
                            f"via OpenRouter ({model.split('/')[-1]})"
                        )
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
                                "max_tokens": 4000,
                                "messages": [
                                    {
                                        "role": "system",
                                        "content": "You are mckoutie — a startup growth expert. Return valid JSON only, no markdown wrapping.",
                                    },
                                    {"role": "user", "content": prompt},
                                ],
                            },
                        )
                        elapsed = _time.monotonic() - t0

                        if resp.status_code == 200:
                            data = resp.json()
                            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            if content:
                                logger.info(f"[LEADS] LLM responded in {elapsed:.1f}s ({len(content)} chars)")
                                return content
                            logger.warning(f"[LEADS] OpenRouter returned empty content after {elapsed:.1f}s")
                            last_error = "empty response"
                        elif resp.status_code == 429:
                            wait = 3 + random.uniform(0, 3) * (attempt + 1)
                            logger.warning(f"[LEADS] OpenRouter 429, backing off {wait:.1f}s")
                            await asyncio.sleep(wait)
                            last_error = "rate limited"
                        else:
                            body = resp.text[:500]
                            logger.error(f"[LEADS] OpenRouter {resp.status_code} after {elapsed:.1f}s: {body}")
                            last_error = f"HTTP {resp.status_code}: {body}"
                            await asyncio.sleep(2 + random.uniform(0, 2))
                    except httpx.TimeoutException:
                        elapsed = _time.monotonic() - t0
                        last_error = f"LLM timeout after {elapsed:.0f}s"
                        logger.warning(f"[LEADS] OpenRouter timeout after {elapsed:.1f}s (attempt {attempt+1}/2)")
                        await asyncio.sleep(2 + random.uniform(0, 2))
                    except Exception as e:
                        elapsed = _time.monotonic() - t0
                        last_error = str(e)
                        logger.warning(f"[LEADS] OpenRouter error after {elapsed:.1f}s: {e}")
                        await asyncio.sleep(2 + random.uniform(0, 2))

                if model == _PERSONA_MODEL:
                    logger.info(f"[LEADS] Fast model failed, trying fallback ({_PERSONA_MODEL_FALLBACK})")

    # Last resort: Anthropic direct
    if settings.anthropic_api_key:
        try:
            logger.info("[LEADS] Falling back to Anthropic direct API")
            import anthropic
            aclient = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await aclient.messages.create(
                model="claude-opus-4-20250918",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            last_error = str(e)
            logger.error(f"[LEADS] Anthropic direct also failed: {e}")

    raise RuntimeError(f"No LLM provider succeeded: {last_error}")


def _parse_json_array(text: str) -> list[dict]:
    """Extract JSON array from LLM response."""
    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Find first [ to last ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            # Try fixing trailing commas
            candidate = text[start : end + 1]
            cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                result = json.loads(cleaned)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

    logger.error(f"[LEADS] Failed to parse persona JSON. First 500 chars: {text[:500]}")
    return []
