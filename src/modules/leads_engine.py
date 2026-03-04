"""
Leads discovery engine — generates customer personas and finds real leads via Exa.

Pipeline:
  1. LLM generates 3 customer personas from the startup analysis
  2. For each persona, Exa semantic search finds 10 real potential customers
  3. Returns structured data for the dashboard
"""

import asyncio
import json
import logging
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

PERSONA_SYSTEM_PROMPT = """You are mckoutie's lead intelligence engine.
Given a startup profile and analysis, generate 3 detailed customer personas
representing the lowest-hanging-fruit, highest-impact potential customers.

Be SPECIFIC — not generic marketing personas. These should feel like real
people with real problems that this specific startup solves."""

PERSONA_PROMPT = """Based on this startup data, generate 3 customer personas.

## STARTUP DATA
{startup_data}

## COMPANY PROFILE
{company_profile}

Return valid JSON:
{{
  "personas": [
    {{
      "name": "string — archetype name (e.g. 'The Overwhelmed SaaS Founder')",
      "title": "string — typical job title",
      "age_range": "string — e.g. '28-38'",
      "income_range": "string — e.g. '$80K-150K'",
      "company_size": "string — e.g. 'Solo founder' or '5-20 employees'",
      "industry": "string — their industry",
      "defining_trait": "string — the ONE thing that defines this person's relationship to the problem",
      "pain_points": ["3-5 specific pain points this startup solves for them"],
      "trigger_events": ["3-4 events that make them ready to buy RIGHT NOW"],
      "where_they_live_online": {{
        "primary": ["2-3 platforms where they're MOST active — be specific (subreddit names, Discord servers, Twitter communities)"],
        "secondary": ["2-3 secondary platforms"],
        "passive": ["1-2 platforms they consume but don't post on"]
      }},
      "pain_signals": ["5-7 exact phrases they would type/say when experiencing the problem — these become search queries"],
      "current_solutions": ["2-3 things they currently pay for that partially solve this"],
      "objections": ["2-3 reasons they might NOT buy, with counter-arguments"],
      "network_value": "number 1-10 — how valuable is this person for word-of-mouth",
      "reachability": "number 1-10 — how easy to reach via cold outreach",
      "search_queries": ["5-7 Exa semantic search queries to find this type of person online — these should find their blog posts, tweets, forum posts, etc."]
    }}
  ]
}}

Make personas SPECIFIC to this startup. Each should represent a distinct
segment with different pain points and channels."""


async def generate_personas(startup_data: str, company_profile: dict) -> dict:
    """Generate 3 customer personas via LLM."""
    prompt = PERSONA_PROMPT.format(
        startup_data=startup_data[:4000],
        company_profile=json.dumps(company_profile, indent=2),
    )

    text = await _call_llm(PERSONA_SYSTEM_PROMPT, prompt)
    return _parse_json(text)


async def find_leads_for_persona(persona: dict, startup_context: str) -> list[dict]:
    """Use Exa to find 10 real potential leads matching a persona."""
    if not settings.exa_api_key:
        logger.warning("No Exa API key — skipping lead discovery")
        return []

    search_queries = persona.get("search_queries", [])
    pain_signals = persona.get("pain_signals", [])

    # Use a mix of semantic queries and pain signal searches
    queries = search_queries[:4] + pain_signals[:3]
    if not queries:
        queries = [f"{persona.get('title', '')} {persona.get('defining_trait', '')}"]

    all_leads = []
    seen_urls = set()

    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        for query in queries[:4]:  # Limit API calls
            try:
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={
                        "x-api-key": settings.exa_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query[:120],  # Truncate long queries
                        "numResults": 5,
                        "type": "auto",
                        "contents": {
                            "text": {"maxCharacters": 500},
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for result in data.get("results", []):
                    url = result.get("url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    lead = {
                        "url": url,
                        "title": result.get("title", ""),
                        "snippet": (result.get("text", "") or "")[:300],
                        "source_query": query,
                        "published_date": result.get("publishedDate", ""),
                        "author": result.get("author", ""),
                        "score": result.get("score", 0),
                    }
                    all_leads.append(lead)

            except Exception as e:
                logger.warning(f"Exa search failed for query '{query[:50]}': {e}")
                continue

            # Small delay between API calls
            await asyncio.sleep(0.3)

    # Score and sort leads
    scored = _score_leads(all_leads, persona)
    return scored[:10]


async def run_leads_pipeline(startup_data: str, company_profile: dict) -> dict:
    """
    Full pipeline: generate personas → find leads for each.

    Returns:
    {
        "personas": [...],
        "leads_by_persona": {
            "persona_name": [leads...],
            ...
        }
    }
    """
    # Step 1: Generate personas
    persona_result = await generate_personas(startup_data, company_profile)
    personas = persona_result.get("personas", [])

    if not personas:
        logger.warning("No personas generated")
        return {"personas": [], "leads_by_persona": {}}

    # Step 2: Find leads for each persona (in parallel)
    leads_by_persona = {}
    tasks = []
    for persona in personas[:3]:
        name = persona.get("name", "Unknown")
        tasks.append((name, find_leads_for_persona(persona, startup_data)))

    results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.warning(f"Lead search failed for {name}: {result}")
            leads_by_persona[name] = []
        else:
            leads_by_persona[name] = result

    return {
        "personas": personas,
        "leads_by_persona": leads_by_persona,
    }


def _score_leads(leads: list[dict], persona: dict) -> list[dict]:
    """Score leads by relevance to persona."""
    pain_signals = set(s.lower() for s in persona.get("pain_signals", []))

    for lead in leads:
        score = lead.get("score", 0) * 5  # Base Exa relevance score

        snippet = (lead.get("snippet", "") + lead.get("title", "")).lower()

        # Boost if snippet contains pain signals
        for signal in pain_signals:
            words = signal.lower().split()
            if any(w in snippet for w in words if len(w) > 4):
                score += 2

        # Boost if recent
        date = lead.get("published_date", "")
        if "2026" in date or "2025" in date:
            score += 3

        # Boost if it has an author (identifiable person)
        if lead.get("author"):
            score += 2

        lead["lead_score"] = round(min(score, 10), 1)

    return sorted(leads, key=lambda x: x.get("lead_score", 0), reverse=True)


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
        # Fix trailing commas
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return {"personas": [], "error": "Failed to parse personas"}
