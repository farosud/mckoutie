"""
Traction analysis engine — runs the full 19-channel analysis via Claude.

This is the core intelligence. Takes raw startup data (website content + twitter)
and produces a structured McKinsey-style consulting brief.
"""

import json
import logging

import anthropic

from src.config import settings

logger = logging.getLogger(__name__)

CHANNELS = [
    "Viral Marketing",
    "Public Relations (PR)",
    "Unconventional PR",
    "Search Engine Marketing (SEM)",
    "Social & Display Ads",
    "Offline Ads",
    "Search Engine Optimization (SEO)",
    "Content Marketing",
    "Email Marketing",
    "Engineering as Marketing",
    "Targeting Blogs",
    "Business Development",
    "Sales",
    "Affiliate Programs",
    "Existing Platforms",
    "Trade Shows",
    "Offline Events",
    "Speaking Engagements",
    "Community Building",
]

ANALYSIS_SYSTEM_PROMPT = """You are mckoutie — a brutally honest AI startup consultant.
You have the strategic depth of McKinsey but the tone of a sharp friend who's seen
1000 startups and knows exactly what works and what's BS.

Your job: analyze a startup and produce a comprehensive traction strategy report.

You are direct, specific, and actionable. No filler, no corporate speak.
When something is a bad idea, say it clearly. When something is the obvious
move they're missing, call it out hard.

Regional context matters — if the startup is based in Latin America, factor in
local channels, language, market size, and distribution differences.

IMPORTANT: Your analysis should feel like $10K worth of consulting,
not a generic blog post. Be SPECIFIC to THIS startup — reference their
actual product, market, and situation throughout."""

ANALYSIS_PROMPT = """Analyze this startup and produce a full traction strategy report.

## STARTUP DATA

{startup_data}

## YOUR TASK

Produce a structured JSON report with the following sections. Be brutally specific
to THIS startup — no generic advice.

Return valid JSON with this structure:

{{
  "company_profile": {{
    "name": "string — company/product name",
    "one_liner": "string — what they do in one sentence",
    "stage": "string — pre-launch | launched | growing | scaling",
    "estimated_size": "string — solo | small team (2-5) | medium (6-20) | large (20+)",
    "market": "string — target market description",
    "business_model": "string — how they make/plan to make money",
    "strengths": ["list of 3-5 key strengths"],
    "weaknesses": ["list of 3-5 key weaknesses/risks"],
    "unique_angle": "string — what makes them genuinely different"
  }},

  "executive_summary": "string — 3-4 paragraph executive summary. The 10,000 foot view. What this startup should focus on RIGHT NOW and why. This should be sharp enough to share as a standalone insight.",

  "channel_analysis": [
    {{
      "channel": "string — channel name",
      "score": "number 1-10 — fit for this specific startup",
      "effort": "string — low | medium | high",
      "timeline": "string — days | weeks | months to see results",
      "budget": "string — estimated budget to test ($0, $50, $500, $5K, etc.)",
      "specific_ideas": ["3-5 SPECIFIC tactical ideas for THIS startup"],
      "first_move": "string — the very first concrete action to take",
      "why_or_why_not": "string — honest assessment of why this channel does or doesn't fit",
      "killer_insight": "string — one non-obvious insight about using this channel for THIS startup"
    }}
  ],

  "bullseye_ranking": {{
    "inner_ring": {{
      "channels": ["top 3 channels to test RIGHT NOW"],
      "reasoning": "string — why these 3 specifically"
    }},
    "promising": {{
      "channels": ["4-6 channels worth testing next"],
      "reasoning": "string"
    }},
    "long_shot": {{
      "channels": ["remaining channels — maybe later or never"],
      "reasoning": "string"
    }}
  }},

  "ninety_day_plan": {{
    "month_1": {{
      "focus": "string — primary focus area",
      "actions": ["5-7 specific weekly actions"],
      "target_metric": "string — what to measure",
      "budget": "string — estimated spend"
    }},
    "month_2": {{
      "focus": "string",
      "actions": ["5-7 specific actions"],
      "target_metric": "string",
      "budget": "string"
    }},
    "month_3": {{
      "focus": "string",
      "actions": ["5-7 specific actions"],
      "target_metric": "string",
      "budget": "string"
    }}
  }},

  "budget_allocation": {{
    "total_recommended": "string — total 90-day budget",
    "breakdown": [
      {{"channel": "string", "amount": "string", "rationale": "string"}}
    ]
  }},

  "risk_matrix": [
    {{
      "risk": "string — what could go wrong",
      "probability": "string — low | medium | high",
      "impact": "string — low | medium | high",
      "mitigation": "string — how to prevent or handle it"
    }}
  ],

  "competitive_moat": "string — 2-3 paragraphs on what their long-term defensibility could be and how to build it through the traction channels",

  "hot_take": "string — your single most provocative, useful opinion about this startup. The thing nobody would tell them but they NEED to hear."
}}

Analyze ALL 19 channels in channel_analysis. Score each honestly — some should be 1-2 (bad fit).
The bullseye_ranking must have exactly 3 in inner_ring.
Be specific enough that they can execute on day 1 without further research.
"""


async def run_traction_analysis(startup_data: str) -> dict:
    """
    Run the full 19-channel traction analysis.

    Args:
        startup_data: Compiled text about the startup (website + twitter + any other intel)

    Returns:
        Structured analysis dict matching the JSON schema above.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = ANALYSIS_PROMPT.format(startup_data=startup_data)

    logger.info("Running traction analysis via Claude...")

    # Retry up to 3 times on transient failures
    last_error = None
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=settings.analysis_model,
                max_tokens=settings.analysis_max_tokens,
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except anthropic.RateLimitError:
            last_error = "rate limited"
            logger.warning(f"Rate limited on attempt {attempt + 1}/3, waiting 10s...")
            import asyncio
            await asyncio.sleep(10)
        except anthropic.APITimeoutError:
            last_error = "timeout"
            logger.warning(f"Timeout on attempt {attempt + 1}/3, retrying...")
        except anthropic.APIError as e:
            last_error = str(e)
            logger.warning(f"API error on attempt {attempt + 1}/3: {e}")
            import asyncio
            await asyncio.sleep(3)
    else:
        logger.error(f"All 3 attempts failed: {last_error}")
        return {"error": f"Claude API failed after 3 attempts: {last_error}"}

    # Extract JSON from response
    text = response.content[0].text

    # Try to parse JSON directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    import re

    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Last resort — find the first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse analysis response as JSON")
    return {"error": "Failed to parse analysis", "raw_response": text[:2000]}
