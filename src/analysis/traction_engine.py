"""
Traction analysis engine — runs the full 19-channel analysis via LLM.

Supports: Anthropic (direct) → OpenRouter (fallback).
Takes raw startup data (website content + twitter) and produces
a structured McKinsey-style consulting brief.
"""

import asyncio
import json
import logging
import re

import anthropic
import httpx

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


async def _call_anthropic(prompt: str) -> str:
    """Call Anthropic API directly."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    last_error = None
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=settings.analysis_model,
                max_tokens=settings.analysis_max_tokens,
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            last_error = "rate limited"
            logger.warning(f"Anthropic rate limited on attempt {attempt + 1}/3, waiting 10s...")
            await asyncio.sleep(10)
        except anthropic.APITimeoutError:
            last_error = "timeout"
            logger.warning(f"Anthropic timeout on attempt {attempt + 1}/3, retrying...")
        except anthropic.APIError as e:
            last_error = str(e)
            logger.warning(f"Anthropic API error on attempt {attempt + 1}/3: {e}")
            await asyncio.sleep(3)

    raise RuntimeError(f"Anthropic API failed after 3 attempts: {last_error}")


def _get_openrouter_model() -> str:
    """
    Map the configured analysis_model to a valid OpenRouter model ID.

    Anthropic native IDs (e.g. 'claude-sonnet-4-20250514') don't work on
    OpenRouter — they use 'anthropic/claude-sonnet-4' style IDs instead.
    """
    model = settings.analysis_model

    # If it already has a provider prefix (e.g. "anthropic/claude-sonnet-4"), use as-is
    if "/" in model:
        return model

    # Strip date suffixes like '-20250514' that Anthropic uses but OpenRouter doesn't
    # Pattern: strip trailing -YYYYMMDD
    clean = re.sub(r"-\d{8}$", "", model)

    return f"anthropic/{clean}"


async def _call_vps_proxy(prompt: str) -> str:
    """Call the VPS Claude proxy (Claude Code Max plan)."""
    url = f"{settings.vps_proxy_url.rstrip('/')}/chat/completions"
    logger.info(f"VPS proxy: {url}, model: {settings.analysis_model}")

    last_error = None
    for attempt in range(2):  # 2 attempts max — saves time on VPS failure
        try:
            # 180s timeout — Opus generating 12K tokens of 19-channel JSON needs time
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "X-Proxy-Key": settings.vps_proxy_key,
                    },
                    json={
                        "model": settings.analysis_model,
                        "max_tokens": settings.analysis_max_tokens,
                        "messages": [
                            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )

                if resp.status_code != 200:
                    body = resp.text
                    logger.error(
                        f"VPS proxy returned {resp.status_code} on attempt {attempt + 1}/2: {body[:1000]}"
                    )
                    last_error = f"HTTP {resp.status_code}: {body[:500]}"
                    await asyncio.sleep(3)
                    continue

                data = resp.json()

                choices = data.get("choices")
                if not choices or not choices[0].get("message", {}).get("content"):
                    logger.warning(f"VPS proxy returned empty/malformed response: {data}")
                    raise ValueError("Empty response from VPS proxy")

                return choices[0]["message"]["content"]
        except httpx.TimeoutException as e:
            last_error = f"timeout after 180s ({type(e).__name__})"
            logger.warning(f"VPS proxy timeout on attempt {attempt + 1}/2: {last_error}")
            await asyncio.sleep(3)
        except httpx.ConnectError as e:
            last_error = f"connect error: {e}"
            logger.warning(f"VPS proxy connect error on attempt {attempt + 1}/2: {last_error}")
            await asyncio.sleep(3)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            logger.warning(f"VPS proxy error on attempt {attempt + 1}/2: {last_error}")
            await asyncio.sleep(3)

    raise RuntimeError(f"VPS proxy failed after 2 attempts: {last_error}")


async def _call_openrouter(prompt: str) -> str:
    """Call OpenRouter API (fallback)."""
    model_id = _get_openrouter_model()
    logger.info(f"OpenRouter fallback, model: {model_id}")

    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://mckoutie.com",
                        "X-Title": "mckoutie",
                    },
                    json={
                        "model": model_id,
                        "max_tokens": settings.analysis_max_tokens,
                        "messages": [
                            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )

                if resp.status_code != 200:
                    body = resp.text
                    logger.error(
                        f"OpenRouter returned {resp.status_code} on attempt {attempt + 1}/3: {body[:1000]}"
                    )
                    last_error = f"HTTP {resp.status_code}: {body[:500]}"
                    await asyncio.sleep(3)
                    continue

                data = resp.json()

                choices = data.get("choices")
                if not choices or not choices[0].get("message", {}).get("content"):
                    logger.warning(f"OpenRouter returned empty/malformed response: {data}")
                    raise ValueError("Empty response from OpenRouter")

                return choices[0]["message"]["content"]
        except Exception as e:
            last_error = str(e)
            logger.warning(f"OpenRouter error on attempt {attempt + 1}/3: {e}")
            await asyncio.sleep(3)

    raise RuntimeError(f"OpenRouter API failed after 3 attempts: {last_error}")


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response text, handling various formats."""
    logger.info(f"Parsing LLM response ({len(text)} chars)")

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"Code block JSON parse failed: {e}")

    # Find first { to last } — the main extraction method
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            logger.warning(f"Brace-delimited JSON parse failed: {e}")

            # Try to repair common LLM JSON issues
            repaired = candidate
            # Fix trailing commas before } or ]
            repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
            # Fix unescaped newlines in string values
            repaired = re.sub(r'(?<=": ")(.*?)(?="[,}\]])', lambda m: m.group(0).replace("\n", "\\n"), repaired)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

            # If JSON is truncated (max_tokens hit), try to close it
            if not candidate.rstrip().endswith("}"):
                logger.info("Attempting to repair truncated JSON...")
                truncated = _repair_truncated_json(candidate)
                if truncated:
                    try:
                        return json.loads(truncated)
                    except json.JSONDecodeError:
                        pass

    # Log what we got for debugging
    logger.error(f"All JSON parse attempts failed. Response starts with: {text[:500]}")
    logger.error(f"Response ends with: {text[-500:]}")

    return {"error": "Failed to parse analysis", "raw_response": text[:3000]}


def _repair_truncated_json(text: str) -> str | None:
    """Attempt to close truncated JSON by balancing braces and brackets."""
    # Count open/close braces and brackets
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")

    if open_braces <= 0 and open_brackets <= 0:
        return None  # Not truncated in the way we can fix

    # Remove any trailing partial string/key
    # Find the last complete value (ending with , or : or ] or } or ")
    cleaned = text.rstrip()
    # Strip trailing partial content after last complete token
    last_good = max(
        cleaned.rfind(","),
        cleaned.rfind('"'),
        cleaned.rfind("]"),
        cleaned.rfind("}"),
    )
    if last_good > len(cleaned) // 2:  # sanity check — don't trim too much
        cleaned = cleaned[:last_good + 1]

    # Remove trailing comma if present
    cleaned = cleaned.rstrip().rstrip(",")

    # Close brackets then braces
    cleaned += "]" * open_brackets + "}" * open_braces

    return cleaned


async def run_traction_analysis(startup_data: str) -> dict:
    """
    Run the full 19-channel traction analysis.

    Tries Anthropic first, falls back to OpenRouter.

    Args:
        startup_data: Compiled text about the startup (website + twitter + any other intel)

    Returns:
        Structured analysis dict matching the JSON schema above.
    """
    prompt = ANALYSIS_PROMPT.format(startup_data=startup_data)
    text = None

    # Try VPS proxy first (Claude Code Max — free, fast)
    if settings.has_vps_proxy:
        logger.info("Running traction analysis via VPS proxy (Claude Max)...")
        try:
            text = await _call_vps_proxy(prompt)
        except RuntimeError as e:
            logger.warning(f"VPS proxy failed: {e}")

    # Try Anthropic direct
    if text is None and settings.anthropic_api_key:
        logger.info("Falling back to Anthropic direct...")
        try:
            text = await _call_anthropic(prompt)
        except RuntimeError as e:
            logger.warning(f"Anthropic failed: {e}")

    # Fall back to OpenRouter
    if text is None and settings.openrouter_api_key:
        logger.info("Falling back to OpenRouter...")
        try:
            text = await _call_openrouter(prompt)
        except RuntimeError as e:
            logger.error(f"OpenRouter also failed: {e}")
            return {"error": f"All LLM providers failed: {e}"}

    if text is None:
        return {"error": "No LLM provider available (set VPS_PROXY_KEY, ANTHROPIC_API_KEY, or OPENROUTER_API_KEY)"}

    return _parse_json_response(text)
