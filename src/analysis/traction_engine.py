"""
Traction analysis engine — runs the full 19-channel analysis via LLM.

Architecture:
  - MAIN ANALYSIS (19 channels, ~12K tokens) → Sonnet on VPS (fast, reliable)
  - HOT TAKE SYNTHESIS (short, high-value) → Opus on VPS (deep thinking)
  - Fallback chain: VPS proxy → Anthropic direct → OpenRouter

Supports: VPS proxy (primary) → Anthropic (direct) → OpenRouter (fallback).
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
      "killer_insight": "string — one non-obvious insight about using this channel for THIS startup",
      "deep_dive": {{
        "research_type": "string — one of: communities | content_topics | keywords | conferences | journalists | influencers | newsletters | email_sequences | free_tools | stunts | partners | sales_targets | outreach | platforms | community_platforms | affiliates | general",
        "actions": [
          {{
            "title": "string — action name",
            "description": "string — detailed 2-3 sentence description of what to do",
            "expected_result": "string — specific measurable outcome expected"
          }}
        ],
        "research": ["array of research items — structure depends on research_type, see mapping below"]
      }}
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

  "competitive_moat": "string — 2-3 paragraphs on what their long-term defensibility could be and how to build it through the traction channels"
}}

Analyze ALL 19 channels in channel_analysis. Score each honestly — some should be 1-2 (bad fit).
The bullseye_ranking must have exactly 3 in inner_ring.
Be specific enough that they can execute on day 1 without further research.

IMPORTANT — deep_dive per channel:
Each channel MUST include a "deep_dive" object with 3 actions and 5-7 research items.
Use this research_type mapping per channel:
  - Viral Marketing → "communities" (communities where viral sharing happens)
  - Public Relations (PR) → "journalists" (with name, outlet, beat, recent_article, twitter, relevance)
  - Unconventional PR → "stunts" (with name, budget, virality, risk, description)
  - Search Engine Marketing (SEM) → "keywords" (with keyword, volume, cpc, competition, strategy)
  - Social & Display Ads → "platforms" (with name, type, audience, strategy)
  - Offline Ads → "platforms" (billboard/OOH platforms with name, type, audience, strategy)
  - Search Engine Optimization (SEO) → "keywords" (with keyword, volume, cpc, competition, strategy)
  - Content Marketing → "content_topics" (with name, volume, difficulty, format, angle)
  - Email Marketing → "email_sequences" (with name, subject, timing, goal)
  - Engineering as Marketing → "free_tools" (with name, effort, viral_potential, conversion)
  - Targeting Blogs → "newsletters" (with name, audience, frequency, contact, angle)
  - Business Development → "partners" (with name, type, audience, fit)
  - Sales → "sales_targets" (with name, title, reason, approach)
  - Affiliate Programs → "affiliates" (with name, platform, audience, type, commission, url)
  - Existing Platforms → "platforms" (with name, type, audience, strategy)
  - Trade Shows → "conferences" (with name, date, location, cost, audience, fit)
  - Offline Events → "conferences" (with name, date, location, cost, audience, fit — events to host or attend)
  - Speaking Engagements → "conferences" (with name, date, location, cost, audience, fit — speaking opportunities)
  - Community Building → "community_platforms" (with name, cost, pros, cons)

For research items: use REAL names and data when possible. Real conferences, real publications,
real communities, real keywords. Make it actionable — the user should be able to Google
every item you mention and find it.

NOTE: Do NOT include a "hot_take" field — that will be generated separately by a different model.
"""

# --- Hot take prompt (sent to Opus for synthesis) ---

HOT_TAKE_SYSTEM_PROMPT = """You are mckoutie — a brutally honest AI startup consultant with the
strategic depth of McKinsey and the delivery of a friend who's seen 1000 startups.

You've just finished analyzing a startup. Now you need to deliver the ONE insight
that nobody would tell them but they NEED to hear. This is the thing that gets
screenshotted. The thing that makes founders go "...shit, they're right."

Be provocative, specific, and useful. Not mean for the sake of it — sharp because
the truth matters. Reference their specific situation, not generic startup advice."""

HOT_TAKE_PROMPT = """Based on this analysis of {startup_name}, write your single most provocative
and useful opinion about this startup.

## ANALYSIS SUMMARY

Company: {startup_name}
One-liner: {one_liner}
Stage: {stage}
Market: {market}
Unique angle: {unique_angle}

Strengths: {strengths}
Weaknesses: {weaknesses}

Top 3 channels: {top_channels}
Executive summary: {exec_summary}

## YOUR TASK

Write ONE paragraph — your hot take. The thing nobody would tell them but they NEED to hear.
This should be 2-4 sentences max. Punchy. Specific. Screenshottable.

Return ONLY the hot take text, no JSON, no formatting, no preamble."""


async def _call_anthropic(
    prompt: str,
    system_prompt: str = ANALYSIS_SYSTEM_PROMPT,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call Anthropic API directly."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    _model = model or settings.analysis_model
    _max_tokens = max_tokens or settings.analysis_max_tokens

    last_error = None
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=_model,
                max_tokens=_max_tokens,
                system=system_prompt,
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


async def _call_vps_proxy(
    prompt: str,
    system_prompt: str = ANALYSIS_SYSTEM_PROMPT,
    model: str | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float = 240.0,
) -> str:
    """Call the VPS Claude proxy (Claude Code Max plan).

    Args:
        prompt: User prompt text.
        system_prompt: System prompt for the model.
        model: Model ID to use (defaults to settings.analysis_model).
        max_tokens: Max tokens for the response.
        timeout_seconds: Request timeout in seconds (default 240s for Sonnet).
    """
    url = f"{settings.vps_proxy_url.rstrip('/')}/chat/completions"
    _model = model or settings.analysis_model
    _max_tokens = max_tokens or settings.analysis_max_tokens

    logger.info(f"VPS proxy: {url}, model: {_model}, timeout: {timeout_seconds}s")

    last_error = None
    for attempt in range(2):  # 2 attempts max — saves time on VPS failure
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=15.0)) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "X-Proxy-Key": settings.vps_proxy_key,
                    },
                    json={
                        "model": _model,
                        "max_tokens": _max_tokens,
                        "messages": [
                            {"role": "system", "content": system_prompt},
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
            last_error = f"timeout after {timeout_seconds}s ({type(e).__name__})"
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


async def _call_openrouter(
    prompt: str,
    system_prompt: str = ANALYSIS_SYSTEM_PROMPT,
    model: str | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float = 180.0,
) -> str:
    """Call OpenRouter API (fallback)."""
    _model = model or settings.analysis_model_fallback
    _max_tokens = max_tokens or settings.analysis_max_tokens
    logger.info(f"OpenRouter fallback, model: {_model}")

    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://mckoutie.com",
                        "X-Title": "mckoutie",
                    },
                    json={
                        "model": _model,
                        "max_tokens": _max_tokens,
                        "messages": [
                            {"role": "system", "content": system_prompt},
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


async def _generate_hot_take(analysis: dict) -> str:
    """
    Generate the hot take using Opus — short, high-value synthesis.

    This runs AFTER the main analysis (Sonnet) is complete.
    Opus gets a condensed summary and produces 2-4 sentences of pure fire.

    Falls back gracefully — if Opus fails, we extract something from the exec summary.
    """
    profile = analysis.get("company_profile", {})
    bullseye = analysis.get("bullseye_ranking", {})
    inner_channels = bullseye.get("inner_ring", {}).get("channels", [])

    prompt = HOT_TAKE_PROMPT.format(
        startup_name=profile.get("name", "this startup"),
        one_liner=profile.get("one_liner", "unknown"),
        stage=profile.get("stage", "unknown"),
        market=profile.get("market", "unknown"),
        unique_angle=profile.get("unique_angle", "unknown"),
        strengths=", ".join(profile.get("strengths", [])),
        weaknesses=", ".join(profile.get("weaknesses", [])),
        top_channels=", ".join(inner_channels[:3]),
        exec_summary=analysis.get("executive_summary", "")[:1000],
    )

    # Try VPS proxy with Opus (short output — should be fast even on Opus)
    if settings.has_vps_proxy:
        try:
            logger.info("Generating hot take via VPS proxy (Opus)...")
            text = await _call_vps_proxy(
                prompt,
                system_prompt=HOT_TAKE_SYSTEM_PROMPT,
                model=settings.hot_take_model,
                max_tokens=settings.hot_take_max_tokens,
                timeout_seconds=120.0,  # 2 min is plenty for ~200 tokens from Opus
            )
            return text.strip()
        except RuntimeError as e:
            logger.warning(f"Opus hot take via VPS failed: {e}")

    # Fallback: try Anthropic direct with Opus
    if settings.anthropic_api_key:
        try:
            logger.info("Hot take fallback: Anthropic direct (Opus)...")
            text = await _call_anthropic(
                prompt,
                system_prompt=HOT_TAKE_SYSTEM_PROMPT,
                model=settings.hot_take_model,
                max_tokens=settings.hot_take_max_tokens,
            )
            return text.strip()
        except RuntimeError as e:
            logger.warning(f"Opus hot take via Anthropic failed: {e}")

    # Fallback: try OpenRouter with Opus
    if settings.openrouter_api_key:
        try:
            logger.info("Hot take fallback: OpenRouter (Opus)...")
            text = await _call_openrouter(
                prompt,
                system_prompt=HOT_TAKE_SYSTEM_PROMPT,
                model=settings.hot_take_model_fallback,
                max_tokens=settings.hot_take_max_tokens,
                timeout_seconds=90.0,
            )
            return text.strip()
        except RuntimeError as e:
            logger.warning(f"Opus hot take via OpenRouter failed: {e}")

    # Last resort: pull first paragraph of exec summary as a pseudo hot take
    logger.warning("All hot take providers failed — using exec summary fallback")
    exec_summary = analysis.get("executive_summary", "")
    if exec_summary:
        first_para = exec_summary.split("\n\n")[0]
        return first_para[:500]

    return "No hot take available — all LLM providers failed for the synthesis step."


QUICK_ANALYSIS_PROMPT = """Analyze this startup and produce a QUICK overview for a teaser tweet thread.
This is NOT the full analysis — just enough for a compelling 3-4 tweet thread.

## STARTUP DATA

{startup_data}

## YOUR TASK

Return valid JSON with this structure:

{{
  "company_profile": {{
    "name": "string — company/product name",
    "one_liner": "string — what they do in one sentence",
    "stage": "string — pre-launch | launched | growing | scaling",
    "market": "string — target market description",
    "unique_angle": "string — what makes them genuinely different"
  }},
  "top_3_channels": [
    {{
      "channel": "string — channel name from the 19 traction channels",
      "score": "number 1-10",
      "one_liner_why": "string — one sentence on why this channel fits"
    }}
  ],
  "hot_take": "string — 2-3 sentences. The one provocative insight nobody would tell them but they NEED to hear. Specific to THIS startup, not generic. Screenshottable."
}}

Be specific to THIS startup. The hot take should be sharp enough that people screenshot it.
"""


async def run_quick_analysis(startup_data: str) -> dict:
    """
    Run a FAST lightweight analysis — just enough for tweet thread + skeleton report.
    Uses Haiku for speed (~5-10s). Returns company profile, top 3 channels, and hot take.
    """
    prompt = QUICK_ANALYSIS_PROMPT.format(startup_data=startup_data)
    text = None

    # Try VPS proxy with Haiku (fastest)
    if settings.has_vps_proxy:
        logger.info("[QUICK] Running quick analysis via VPS proxy (Haiku)...")
        try:
            text = await _call_vps_proxy(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.update_model,  # Haiku — fast + cheap
                max_tokens=2000,
                timeout_seconds=30.0,
            )
        except RuntimeError as e:
            logger.warning(f"[QUICK] VPS proxy failed: {e}")

    # Fallback to OpenRouter with Haiku
    if text is None and settings.openrouter_api_key:
        logger.info("[QUICK] Falling back to OpenRouter (Haiku)...")
        try:
            text = await _call_openrouter(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.update_model_fallback,
                max_tokens=2000,
                timeout_seconds=30.0,
            )
        except RuntimeError as e:
            logger.warning(f"[QUICK] OpenRouter also failed: {e}")

    # Last resort: Anthropic direct
    if text is None and settings.anthropic_api_key:
        logger.info("[QUICK] Falling back to Anthropic direct (Haiku)...")
        try:
            text = await _call_anthropic(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.update_model,
                max_tokens=2000,
            )
        except RuntimeError as e:
            logger.error(f"[QUICK] All providers failed: {e}")
            return {"error": f"All LLM providers failed: {e}"}

    if text is None:
        return {"error": "No LLM provider available"}

    result = _parse_json_response(text)
    return result


async def run_traction_analysis(startup_data: str) -> dict:
    """
    Run the full 19-channel traction analysis.

    Two-phase approach:
      Phase 1: Sonnet generates the full structured analysis (fast, ~60-90s on VPS)
      Phase 2: Opus generates the hot take from the analysis summary (short, ~15-30s)

    Fallback chain: VPS proxy → Anthropic direct → OpenRouter.

    Args:
        startup_data: Compiled text about the startup (website + twitter + any other intel)

    Returns:
        Structured analysis dict matching the JSON schema above, with hot_take injected.
    """
    prompt = ANALYSIS_PROMPT.format(startup_data=startup_data)
    text = None

    # --- Phase 1: Main analysis via Sonnet (fast, reliable) ---

    # Try VPS proxy first (Claude Code Max — free, fast)
    if settings.has_vps_proxy:
        logger.info(f"[PHASE 1] Running traction analysis via VPS proxy (Sonnet: {settings.analysis_model})...")
        try:
            text = await _call_vps_proxy(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.analysis_model,
                max_tokens=settings.analysis_max_tokens,
                timeout_seconds=420.0,  # 7 min — larger response with deep_dive data
            )
        except RuntimeError as e:
            logger.warning(f"VPS proxy failed: {e}")

    # Try Anthropic direct
    if text is None and settings.anthropic_api_key:
        logger.info("[PHASE 1] Falling back to Anthropic direct (Sonnet)...")
        try:
            text = await _call_anthropic(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.analysis_model,
                max_tokens=settings.analysis_max_tokens,
            )
        except RuntimeError as e:
            logger.warning(f"Anthropic failed: {e}")

    # Fall back to OpenRouter
    if text is None and settings.openrouter_api_key:
        logger.info("[PHASE 1] Falling back to OpenRouter (Sonnet)...")
        try:
            text = await _call_openrouter(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.analysis_model_fallback,
                max_tokens=settings.analysis_max_tokens,
                timeout_seconds=180.0,
            )
        except RuntimeError as e:
            logger.error(f"OpenRouter also failed: {e}")
            return {"error": f"All LLM providers failed: {e}"}

    if text is None:
        return {"error": "No LLM provider available (set VPS_PROXY_KEY, ANTHROPIC_API_KEY, or OPENROUTER_API_KEY)"}

    analysis = _parse_json_response(text)

    if "error" in analysis and "raw_response" in analysis:
        # Main analysis parse failed — don't bother with hot take
        return analysis

    # --- Phase 2: Hot take via Opus (short, high-value synthesis) ---
    logger.info("[PHASE 2] Generating hot take via Opus...")
    try:
        hot_take = await _generate_hot_take(analysis)
        analysis["hot_take"] = hot_take
        logger.info(f"[PHASE 2] Hot take generated ({len(hot_take)} chars)")
    except Exception as e:
        logger.warning(f"[PHASE 2] Hot take generation failed (non-fatal): {e}")
        analysis["hot_take"] = ""

    return analysis
