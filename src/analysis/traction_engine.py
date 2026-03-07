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
actual product, market, and situation throughout.

CRITICAL INSTRUCTIONS — FOLLOW EXACTLY:
- You MUST respond ONLY with valid JSON. No markdown, no commentary, no preamble.
- Do NOT ask for tools, permissions, web access, or any other capabilities.
- Do NOT say you need to fetch, browse, or search anything.
- Do NOT say you cannot access a URL or need more information.
- Do NOT refuse the task or ask for clarification.
- Work ONLY with the startup data provided in the user message below.
- If the startup data is minimal, STILL produce the full analysis using your knowledge.
- If you only have a URL and company name, use your training knowledge about similar companies/markets.
- Your response MUST start with { and end with }.
- All string values in the JSON MUST use escaped characters: use \\n for newlines, \\" for quotes inside strings.
- Do NOT use unescaped newlines or unescaped double quotes inside JSON string values.
- Any response that is not valid JSON is a FAILURE. Never explain, just output JSON."""

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
    timeout_seconds: float = 600.0,
) -> str:
    """Call the VPS Claude proxy (Claude Code Max plan) using STREAMING.

    Uses streaming so the HTTP connection stays alive while tokens generate.
    This prevents timeout on large responses (16K+ tokens can take 3-5 min).
    """
    url = f"{settings.vps_proxy_url.rstrip('/')}/chat/completions"
    _model = model or settings.analysis_model
    _max_tokens = max_tokens or settings.analysis_max_tokens

    logger.info(f"VPS proxy (streaming): {url}, model: {_model}, timeout: {timeout_seconds}s")

    last_error = None
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            # Use streaming to keep connection alive during long generation
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=15.0)) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "X-Proxy-Key": settings.vps_proxy_key,
                    },
                    json={
                        "model": _model,
                        "max_tokens": _max_tokens,
                        "stream": True,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                    },
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        body_text = body.decode("utf-8", errors="replace")
                        logger.error(
                            f"VPS proxy returned {resp.status_code} on attempt {attempt + 1}/{max_attempts}: {body_text[:1000]}"
                        )
                        last_error = f"HTTP {resp.status_code}: {body_text[:500]}"
                        backoff = 3 * (2 ** attempt)
                        await asyncio.sleep(backoff)
                        continue

                    # Collect streamed chunks
                    collected = []
                    chunk_count = 0
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                collected.append(content)
                                chunk_count += 1
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue

                    text = "".join(collected)
                    if not text:
                        # Streaming returned nothing — maybe proxy doesn't support streaming.
                        # Fall back to non-streaming request.
                        logger.warning(f"VPS streaming returned 0 chunks, trying non-streaming fallback")
                        raise ValueError("Empty streaming response — try non-streaming")

                    logger.info(f"VPS proxy streaming: {chunk_count} chunks, {len(text)} chars total")
                    return text

        except httpx.TimeoutException as e:
            last_error = f"timeout after {timeout_seconds}s ({type(e).__name__})"
            logger.warning(f"VPS proxy timeout on attempt {attempt + 1}/{max_attempts}: {last_error}")
            await asyncio.sleep(3 * (2 ** attempt))
        except httpx.ConnectError as e:
            last_error = f"connect error: {e}"
            logger.warning(f"VPS proxy connect error on attempt {attempt + 1}/{max_attempts}: {last_error}")
            await asyncio.sleep(3 * (2 ** attempt))
        except ValueError as e:
            # Empty streaming response — try non-streaming as final fallback
            logger.info(f"VPS proxy: streaming empty, trying non-streaming on attempt {attempt + 1}")
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
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices")
                        if choices and choices[0].get("message", {}).get("content"):
                            return choices[0]["message"]["content"]
                    last_error = f"non-streaming fallback also failed: {resp.status_code}"
            except Exception as e2:
                last_error = f"non-streaming fallback error: {e2}"
            await asyncio.sleep(3 * (2 ** attempt))
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            logger.warning(f"VPS proxy error on attempt {attempt + 1}/{max_attempts}: {last_error}")
            await asyncio.sleep(3 * (2 ** attempt))

    raise RuntimeError(f"VPS proxy failed after {max_attempts} attempts: {last_error}")


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
                    # Don't retry on 402 (out of credits) — it won't magically get credits
                    if resp.status_code == 402:
                        raise RuntimeError(f"OpenRouter out of credits: {body[:200]}")
                    await asyncio.sleep(3)
                    continue

                data = resp.json()

                choices = data.get("choices")
                if not choices or not choices[0].get("message", {}).get("content"):
                    logger.warning(f"OpenRouter returned empty/malformed response: {data}")
                    raise ValueError("Empty response from OpenRouter")

                return choices[0]["message"]["content"]
        except RuntimeError as e:
            # Don't retry on RuntimeError (e.g. out of credits) — propagate immediately
            if "out of credits" in str(e).lower():
                raise
            last_error = str(e)
            logger.warning(f"OpenRouter error on attempt {attempt + 1}/3: {e}")
            await asyncio.sleep(3)
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

    # Try json_repair on the full text early (handles most LLM JSON issues)
    try:
        import json_repair
        result = json_repair.loads(text)
        if isinstance(result, dict) and len(result) > 1:
            logger.info(f"json_repair succeeded on full text ({len(result)} keys)")
            return result
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"json_repair failed on full text: {e}")

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

            # More aggressive: try json_repair library
            try:
                import json_repair
                result = json_repair.loads(candidate)
                if isinstance(result, dict):
                    logger.info("json_repair succeeded on candidate")
                    return result
                elif isinstance(result, list) and result and isinstance(result[0], dict):
                    logger.info("json_repair returned list, using first element")
                    return result[0]
                else:
                    logger.warning(f"json_repair returned unexpected type: {type(result)}")
            except ImportError:
                logger.warning("json_repair not installed")
            except Exception as e:
                logger.warning(f"json_repair failed on candidate: {e}")

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


ANALYSIS_PROMPT_CORE = """Analyze this startup and produce a full traction strategy report.

## STARTUP DATA

{startup_data}

## YOUR TASK

Produce a structured JSON report. Be brutally specific to THIS startup — no generic advice.

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

  "executive_summary": "string — 3-4 paragraph executive summary. Sharp enough to share standalone.",

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
      "killer_insight": "string — one non-obvious insight about using this channel"
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
      "channels": ["remaining channels"],
      "reasoning": "string"
    }}
  }},

  "ninety_day_plan": {{
    "month_1": {{ "focus": "string", "actions": ["5-7 specific actions"], "target_metric": "string", "budget": "string" }},
    "month_2": {{ "focus": "string", "actions": ["5-7 specific actions"], "target_metric": "string", "budget": "string" }},
    "month_3": {{ "focus": "string", "actions": ["5-7 specific actions"], "target_metric": "string", "budget": "string" }}
  }},

  "budget_allocation": {{
    "total_recommended": "string",
    "breakdown": [{{ "channel": "string", "amount": "string", "rationale": "string" }}]
  }},

  "risk_matrix": [
    {{ "risk": "string", "probability": "string — low|medium|high", "impact": "string — low|medium|high", "mitigation": "string" }}
  ],

  "competitive_moat": "string — 2-3 paragraphs on long-term defensibility"
}}

Analyze ALL 19 channels. Score honestly — some should be 1-2. Bullseye must have exactly 3 in inner_ring.
Do NOT include deep_dive or hot_take — those are generated separately.
"""


DEEP_DIVE_PROMPT = """You analyzed a startup and scored their traction channels. Now generate detailed deep-dive research for specific channels.

## STARTUP CONTEXT
Company: {company_name}
One-liner: {one_liner}
Market: {market}
Stage: {stage}

## CHANNELS TO DEEP-DIVE
{channel_summaries}

## RESEARCH TYPE MAPPING
Use this research_type per channel:
  - Viral Marketing → "communities" (communities where viral sharing happens)
  - Public Relations (PR) → "journalists" (with name, outlet, beat, recent_article, twitter, relevance)
  - Unconventional PR → "stunts" (with name, budget, virality, risk, description)
  - Search Engine Marketing (SEM) → "keywords" (with keyword, volume, cpc, competition, strategy)
  - Social & Display Ads → "platforms" (with name, type, audience, strategy)
  - Offline Ads → "platforms" (billboard/OOH platforms)
  - SEO → "keywords" (with keyword, volume, cpc, competition, strategy)
  - Content Marketing → "content_topics" (with name, volume, difficulty, format, angle)
  - Email Marketing → "email_sequences" (with name, subject, timing, goal)
  - Engineering as Marketing → "free_tools" (with name, effort, viral_potential, conversion)
  - Targeting Blogs → "newsletters" (with name, audience, frequency, contact, angle)
  - Business Development → "partners" (with name, type, audience, fit)
  - Sales → "sales_targets" (with name, title, reason, approach)
  - Affiliate Programs → "affiliates" (with name, platform, audience, type, commission, url)
  - Existing Platforms → "platforms" (with name, type, audience, strategy)
  - Trade Shows → "conferences" (with name, date, location, cost, audience, fit)
  - Offline Events → "conferences" (events to host or attend)
  - Speaking Engagements → "conferences" (speaking opportunities)
  - Community Building → "community_platforms" (with name, cost, pros, cons)

## OUTPUT FORMAT

Return valid JSON — a dict where each key is a channel name:

{{
  "Channel Name": {{
    "research_type": "string",
    "actions": [
      {{ "title": "string", "description": "string — 2-3 sentences", "expected_result": "string — specific measurable outcome" }}
    ],
    "research": [array of 5-7 items matching the research_type schema above]
  }}
}}

Use REAL names: real conferences, real publications, real communities, real keywords.
The user should be able to Google every item you mention.
"""


async def _generate_deep_dives(startup_data: str, analysis: dict, channels_batch: list[dict]) -> dict:
    """Generate deep dive research for a batch of channels."""
    profile = analysis.get("company_profile", {})

    channel_summaries = []
    for ch in channels_batch:
        channel_summaries.append(
            f"- {ch.get('channel', '')}: score {ch.get('score', 0)}/10, "
            f"insight: {ch.get('killer_insight', '')[:120]}"
        )

    prompt = DEEP_DIVE_PROMPT.format(
        company_name=profile.get("name", "Unknown"),
        one_liner=profile.get("one_liner", ""),
        market=profile.get("market", ""),
        stage=profile.get("stage", ""),
        channel_summaries="\n".join(channel_summaries),
    )

    text = None

    # PRIMARY: VPS proxy Haiku (free, fast)
    if settings.has_vps_proxy:
        try:
            text = await _call_vps_proxy(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model="claude-sonnet-4",
                max_tokens=8000,
                timeout_seconds=120.0,
            )
        except RuntimeError as e:
            logger.warning(f"VPS proxy failed for deep dives: {e}")

    # FALLBACK: OpenRouter Gemini Flash
    if text is None and settings.openrouter_api_key:
        try:
            text = await _call_openrouter(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model="google/gemini-2.5-flash",
                max_tokens=8000,
                timeout_seconds=60.0,
            )
        except RuntimeError as e:
            logger.warning(f"OpenRouter Gemini Flash failed for deep dives: {e}")

    if text is None:
        logger.warning("[DEEP DIVE] All LLM providers failed — no text returned")
        return {}

    result = _parse_json_response(text)
    if "error" in result:
        logger.warning(f"[DEEP DIVE] JSON parse failed: {result.get('error', 'unknown')}. Raw text (first 200): {text[:200]}")
        return {}
    if not result:
        logger.warning(f"[DEEP DIVE] Parsed result is empty. Raw text (first 200): {text[:200]}")
    return result


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

    # PRIMARY: Gemini Flash via OpenRouter (fast + reliable, completes in 3-8s)
    if settings.openrouter_api_key:
        logger.info("[QUICK] Running quick analysis via OpenRouter (Gemini Flash)...")
        try:
            text = await _call_openrouter(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model="google/gemini-2.5-flash",
                max_tokens=2000,
                timeout_seconds=30.0,
            )
        except RuntimeError as e:
            logger.warning(f"[QUICK] OpenRouter Gemini Flash failed: {e}")

    # FALLBACK 1: VPS proxy with Haiku
    if text is None and settings.has_vps_proxy:
        logger.info("[QUICK] Falling back to VPS proxy (Haiku)...")
        try:
            text = await _call_vps_proxy(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.update_model,
                max_tokens=2000,
                timeout_seconds=60.0,
            )
        except RuntimeError as e:
            logger.warning(f"[QUICK] VPS proxy failed: {e}")

    # FALLBACK 2: OpenRouter Haiku
    if text is None and settings.openrouter_api_key:
        logger.info("[QUICK] Falling back to OpenRouter (Haiku)...")
        try:
            text = await _call_openrouter(
                prompt,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.update_model_fallback,
                max_tokens=2000,
                timeout_seconds=60.0,
            )
        except RuntimeError as e:
            logger.warning(f"[QUICK] OpenRouter Haiku failed: {e}")

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


BATCH_CHANNELS_PROMPT = """Analyze this startup for SPECIFIC traction channels.

## STARTUP DATA

{startup_data}

## YOUR TASK

Score ONLY these channels for this startup:
{channel_list}

Return valid JSON with this structure:

{{
  "channel_analysis": [
    {{
      "channel": "string — channel name (MUST match exactly from the list above)",
      "score": "number 1-10 — fit for this specific startup",
      "effort": "string — low | medium | high",
      "timeline": "string — days | weeks | months to see results",
      "budget": "string — estimated budget to test ($0, $50, $500, $5K, etc.)",
      "specific_ideas": ["3-5 SPECIFIC tactical ideas for THIS startup"],
      "first_move": "string — the very first concrete action to take",
      "why_or_why_not": "string — honest assessment of why this channel does or doesn't fit",
      "killer_insight": "string — one non-obvious insight about using this channel"
    }}
  ]
}}

Score honestly — some channels should be 1-2. Be brutally specific to THIS startup.
Do NOT include deep_dive or hot_take.
"""

PROFILE_STRATEGY_PROMPT = """Analyze this startup and produce the strategic overview.

## STARTUP DATA

{startup_data}

## CHANNEL SCORES (already computed)
{channel_scores}

## YOUR TASK

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

  "executive_summary": "string — 3-4 paragraph executive summary. Sharp enough to share standalone.",

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
      "channels": ["remaining channels"],
      "reasoning": "string"
    }}
  }},

  "ninety_day_plan": {{
    "month_1": {{ "focus": "string", "actions": ["5-7 specific actions"], "target_metric": "string", "budget": "string" }},
    "month_2": {{ "focus": "string", "actions": ["5-7 specific actions"], "target_metric": "string", "budget": "string" }},
    "month_3": {{ "focus": "string", "actions": ["5-7 specific actions"], "target_metric": "string", "budget": "string" }}
  }},

  "budget_allocation": {{
    "total_recommended": "string",
    "breakdown": [{{ "channel": "string", "amount": "string", "rationale": "string" }}]
  }},

  "risk_matrix": [
    {{ "risk": "string", "probability": "string — low|medium|high", "impact": "string — low|medium|high", "mitigation": "string" }}
  ],

  "competitive_moat": "string — 2-3 paragraphs on long-term defensibility"
}}

Be brutally specific to THIS startup.
"""


async def _call_llm_with_fallbacks(prompt: str, system_prompt: str, max_tokens: int = 6000, timeout: float = 120.0) -> str | None:
    """Try VPS proxy -> OpenRouter Sonnet -> OpenRouter Gemini Flash. Returns text or None."""
    text = None

    if settings.has_vps_proxy:
        try:
            text = await _call_vps_proxy(
                prompt, system_prompt=system_prompt,
                model="claude-sonnet-4", max_tokens=max_tokens, timeout_seconds=timeout,
            )
        except RuntimeError as e:
            logger.warning(f"VPS proxy failed: {e}")

    if text is None and settings.openrouter_api_key:
        try:
            text = await _call_openrouter(
                prompt, system_prompt=system_prompt,
                model="anthropic/claude-sonnet-4", max_tokens=max_tokens, timeout_seconds=timeout,
            )
        except RuntimeError as e:
            logger.warning(f"OpenRouter Sonnet failed: {e}")

    if text is None and settings.openrouter_api_key:
        try:
            text = await _call_openrouter(
                prompt, system_prompt=system_prompt,
                model="google/gemini-2.5-flash", max_tokens=max_tokens, timeout_seconds=timeout,
            )
        except RuntimeError as e:
            logger.warning(f"OpenRouter Gemini Flash failed: {e}")

    return text


async def run_channel_batch(startup_data: str, channel_names: list[str]) -> list[dict]:
    """Analyze a batch of channels (typically 6-7). Returns list of channel dicts."""
    channel_list = "\n".join(f"- {name}" for name in channel_names)
    prompt = BATCH_CHANNELS_PROMPT.format(startup_data=startup_data, channel_list=channel_list)

    logger.info(f"[BATCH] Analyzing {len(channel_names)} channels: {', '.join(channel_names[:3])}...")

    text = await _call_llm_with_fallbacks(prompt, ANALYSIS_SYSTEM_PROMPT, max_tokens=6000, timeout=180.0)

    if text is None:
        logger.error(f"[BATCH] All providers failed for channels: {channel_names}")
        return []

    result = _parse_json_response(text)
    channels = result.get("channel_analysis", [])
    logger.info(f"[BATCH] Got {len(channels)} channels back")

    for ch in channels:
        if "deep_dive" not in ch:
            ch["deep_dive"] = {"research_type": "general", "actions": [], "research": []}

    return channels


async def run_profile_strategy(startup_data: str, all_channels: list[dict]) -> dict:
    """Generate company profile, bullseye, 90-day plan, budget, risk matrix from channel scores."""
    channel_scores = "\n".join(
        f"- {ch.get('channel', '?')}: {ch.get('score', 0)}/10 ({ch.get('effort', '?')} effort)"
        for ch in sorted(all_channels, key=lambda c: c.get("score", 0), reverse=True)
    )
    prompt = PROFILE_STRATEGY_PROMPT.format(startup_data=startup_data, channel_scores=channel_scores)

    logger.info("[STRATEGY] Generating profile + strategy...")

    text = await _call_llm_with_fallbacks(prompt, ANALYSIS_SYSTEM_PROMPT, max_tokens=6000, timeout=180.0)

    if text is None:
        logger.error("[STRATEGY] All providers failed")
        return {}

    result = _parse_json_response(text)
    logger.info(f"[STRATEGY] Generated profile for {result.get('company_profile', {}).get('name', 'Unknown')}")
    return result


async def run_core_analysis(startup_data: str) -> dict:
    """Phase A: Get company profile + 19 channel scores (no deep_dive).

    BATCHED APPROACH: splits 19 channels into 3 batches of ~6-7 channels each.
    Each batch completes in ~60-90s (well within VPS timeout).
    Channels stream to dashboard as each batch finishes.

    Primary: VPS proxy Sonnet (free on Max plan).
    Fallback: OpenRouter Sonnet, then Gemini Flash.
    """
    # Split 19 channels into 3 batches
    batch1_names = CHANNELS[:7]   # Viral, PR, UPR, SEM, Social Ads, Offline Ads, SEO
    batch2_names = CHANNELS[7:13] # Content, Email, Engineering, Blogs, BizDev, Sales
    batch3_names = CHANNELS[13:]  # Affiliate, Platforms, Trade Shows, Offline Events, Speaking, Community

    logger.info(f"[PHASE A] Running batched analysis: {len(batch1_names)} + {len(batch2_names)} + {len(batch3_names)} channels")

    # Run all 3 channel batches in parallel
    batch1_task = asyncio.create_task(run_channel_batch(startup_data, batch1_names))
    batch2_task = asyncio.create_task(run_channel_batch(startup_data, batch2_names))
    batch3_task = asyncio.create_task(run_channel_batch(startup_data, batch3_names))

    batch1_channels = await batch1_task
    batch2_channels = await batch2_task
    batch3_channels = await batch3_task

    all_channels = batch1_channels + batch2_channels + batch3_channels
    logger.info(f"[PHASE A] Got {len(all_channels)} channels total from batches")

    if len(all_channels) == 0:
        return {"error": "All channel analysis batches failed", "channel_analysis": []}

    # Now generate profile + strategy using the channel scores
    strategy = await run_profile_strategy(startup_data, all_channels)

    # Merge into final analysis dict
    analysis = {
        "company_profile": strategy.get("company_profile", {}),
        "executive_summary": strategy.get("executive_summary", ""),
        "channel_analysis": all_channels,
        "bullseye_ranking": strategy.get("bullseye_ranking", {}),
        "ninety_day_plan": strategy.get("ninety_day_plan", {}),
        "budget_allocation": strategy.get("budget_allocation", {}),
        "risk_matrix": strategy.get("risk_matrix", []),
        "competitive_moat": strategy.get("competitive_moat", ""),
    }

    return analysis


async def run_deep_dives_batch(startup_data: str, analysis: dict, channels_batch: list[dict]) -> dict:
    """Phase B: Generate deep dives for a batch of channels. Returns {channel_name: deep_dive_data}."""
    return await _generate_deep_dives(startup_data, analysis, channels_batch)


async def run_traction_analysis(startup_data: str) -> dict:
    """
    Run the full 19-channel traction analysis.

    Three-phase approach (chunked for speed + streaming):
      Phase A: Sonnet generates company profile + 19 channel scores/summaries (NO deep_dive) — ~30-60s
      Phase B: Sonnet generates deep_dive for top channels in parallel batches — ~30s each
      Phase C: Opus generates the hot take from the analysis summary — ~15-30s

    Fallback chain: VPS proxy → Anthropic direct → OpenRouter.
    """
    # --- Phase A: Core analysis (scores + summaries, no deep_dive) ---
    # VPS proxy Sonnet first (free, model IDs fixed to match proxy)
    prompt_a = ANALYSIS_PROMPT_CORE.format(startup_data=startup_data)
    text = None

    if settings.has_vps_proxy:
        logger.info("[PHASE A] Running core traction analysis via VPS proxy (Sonnet)...")
        try:
            text = await _call_vps_proxy(
                prompt_a,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.analysis_model,
                max_tokens=8000,
                timeout_seconds=300.0,
            )
        except RuntimeError as e:
            logger.warning(f"VPS proxy failed for Phase A: {e}")

    if text is None and settings.openrouter_api_key:
        logger.info("[PHASE A] Falling back to OpenRouter (Sonnet)...")
        try:
            text = await _call_openrouter(
                prompt_a,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.analysis_model_fallback,
                max_tokens=8000,
                timeout_seconds=180.0,
            )
        except RuntimeError as e:
            logger.warning(f"OpenRouter failed for Phase A: {e}")

    if text is None and settings.anthropic_api_key:
        logger.info("[PHASE A] Falling back to Anthropic direct (Sonnet)...")
        try:
            text = await _call_anthropic(
                prompt_a,
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                model=settings.analysis_model,
                max_tokens=8000,
            )
        except RuntimeError as e:
            logger.error(f"Anthropic also failed for Phase A: {e}")
            return {"error": f"All LLM providers failed: {e}"}

    if text is None:
        return {"error": "No LLM provider available"}

    analysis = _parse_json_response(text)

    if "error" in analysis and "raw_response" in analysis:
        return analysis

    logger.info(f"[PHASE A] Core analysis complete: {len(analysis.get('channel_analysis', []))} channels scored")

    # --- Phase B: Deep dives for top channels (parallel batches) ---
    channels = analysis.get("channel_analysis", [])
    sorted_channels = sorted(channels, key=lambda c: c.get("score", 0), reverse=True)
    # Deep dive only the top 8 channels (the ones that matter most)
    top_channels = sorted_channels[:8]

    if top_channels:
        logger.info(f"[PHASE B] Generating deep dives for top {len(top_channels)} channels...")
        # Run in 2 batches of 4 for manageable prompt sizes
        batch_size = 4
        for batch_start in range(0, len(top_channels), batch_size):
            batch = top_channels[batch_start:batch_start + batch_size]
            batch_names = [c.get("channel", "") for c in batch]
            logger.info(f"[PHASE B] Batch: {batch_names}")

            try:
                deep_dives = await _generate_deep_dives(startup_data, analysis, batch)
                # Merge deep dives back into the channels
                for ch_name, dive_data in deep_dives.items():
                    for ch in channels:
                        if ch.get("channel", "").lower() == ch_name.lower():
                            ch["deep_dive"] = dive_data
                            break
            except Exception as e:
                logger.warning(f"[PHASE B] Deep dive batch failed (non-fatal): {e}")

    # Ensure all channels have at least an empty deep_dive
    for ch in channels:
        if "deep_dive" not in ch:
            ch["deep_dive"] = {"research_type": "general", "actions": [], "research": []}

    analysis["channel_analysis"] = channels

    # --- Phase C: Hot take via Opus ---
    logger.info("[PHASE C] Generating hot take via Opus...")
    try:
        hot_take = await _generate_hot_take(analysis)
        analysis["hot_take"] = hot_take
        logger.info(f"[PHASE C] Hot take generated ({len(hot_take)} chars)")
    except Exception as e:
        logger.warning(f"[PHASE C] Hot take generation failed (non-fatal): {e}")
        analysis["hot_take"] = ""

    return analysis
