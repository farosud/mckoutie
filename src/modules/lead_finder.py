"""
Lead finder module — generates customer personas and finds real potential leads via Exa.

Two-phase approach:
1. LLM generates 3 customer personas with pain signals + social network mapping
2. Exa semantic search finds 10 real people matching those personas
"""

import json
import logging
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def find_leads(startup_data: str, analysis: dict) -> dict:
    """
    Generate personas and find real potential leads for a startup.

    Returns:
        {
            "personas": [
                {
                    "name": "The Lonely Builder",
                    "who": "Solo founder, 6-18 months in",
                    "age_range": "26-38",
                    "pain_signals": ["exact phrases they use"],
                    "social_networks": {
                        "primary": ["Twitter/X", "Reddit"],
                        "secondary": ["Discord", "Telegram"]
                    },
                    "willingness_to_pay": "$20-100/mo",
                    "trigger_events": ["just launched with zero traction"],
                    "reachability": 8
                }
            ],
            "leads": [
                {
                    "name": "John Doe",
                    "title": "Founder @ StartupX",
                    "url": "https://...",
                    "source": "twitter/linkedin/blog",
                    "relevance_signal": "Posted about needing advisors",
                    "score": 8,
                    "persona_match": "The Lonely Builder"
                }
            ]
        }
    """
    profile = analysis.get("company_profile", {})
    market = profile.get("market", "")
    one_liner = profile.get("one_liner", "")
    name = profile.get("name", "")

    # Phase 1: Generate personas via LLM
    personas = await _generate_personas(startup_data, analysis)

    # Phase 2: Find real leads via Exa
    leads = []
    if settings.exa_api_key and personas:
        leads = await _find_leads_via_exa(name, one_liner, market, personas)

    return {
        "personas": personas,
        "leads": leads,
    }


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
    "search_queries": ["3-5 Exa search queries to find these people"]
  }}
]

Be SPECIFIC. Not "startup founders" but "solo SaaS founders who just launched and have <$1K MRR".
Pain signals should be REAL phrases people post online, not made-up ones."""

    try:
        text = await _call_llm(prompt)
        return _parse_json_array(text)
    except Exception as e:
        logger.error(f"Persona generation failed: {e}")
        return []


async def _find_leads_via_exa(
    startup_name: str,
    one_liner: str,
    market: str,
    personas: list[dict],
) -> list[dict]:
    """Search Exa for real people matching the personas."""
    leads = []
    seen_urls = set()

    for persona in personas[:3]:
        queries = persona.get("search_queries", [])
        pain_signals = persona.get("pain_signals", [])

        # Use search queries from persona, plus pain signals
        search_terms = queries[:2] + pain_signals[:2]

        for query in search_terms[:3]:  # max 3 searches per persona
            try:
                results = await _exa_search(
                    query=query,
                    num_results=5,
                )
                for r in results:
                    url = r.get("url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Extract person info from the result
                    lead = _extract_lead_info(r, persona)
                    if lead:
                        leads.append(lead)

            except Exception as e:
                logger.warning(f"Exa lead search failed for query '{query[:50]}': {e}")
                continue

    # Sort by score, take top 10
    leads.sort(key=lambda x: x.get("score", 0), reverse=True)
    return leads[:10]


async def _exa_search(query: str, num_results: int = 5) -> list[dict]:
    """Run an Exa semantic search."""
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
                "text": True,
                "type": "auto",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])


def _extract_lead_info(result: dict, persona: dict) -> dict | None:
    """Extract useful lead info from an Exa search result."""
    url = result.get("url", "")
    title = result.get("title", "")
    text = result.get("text", "")[:500]

    if not url or not title:
        return None

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


async def _call_llm(prompt: str) -> str:
    """Call LLM via OpenRouter or Anthropic."""
    if settings.openrouter_api_key:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://mckoutie.com",
                },
                json={
                    "model": "anthropic/claude-sonnet-4",
                    "max_tokens": 4000,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are mckoutie — a startup growth expert. Return valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]

    if settings.anthropic_api_key:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    raise RuntimeError("No LLM provider available")


def _parse_json_array(text: str) -> list[dict]:
    """Extract JSON array from LLM response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Find first [ to last ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.error(f"Failed to parse persona JSON: {text[:500]}")
    return []
