"""
mckoutie Advisor Service — per-user AI advisor agents

Each mckoutie report gets a dedicated AI advisor that:
- Knows the startup's traction analysis, leads, investors
- Can discuss strategy, answer questions, brainstorm
- Maintains conversation history per session
- Uses GLM 4.5 Air (free) for free users, GLM 4.7 for paid

Runs on VPS at port 3460.
"""

import asyncio
import json
import os
import sys
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("advisor")

# ── Config ──────────────────────────────────────────────────────────

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FREE_MODEL = "z-ai/glm-4.5-air:free"
PAID_MODEL = "z-ai/glm-4.7"
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/root/.mckoutie/reports"))
ADVISORS_DIR = Path(os.getenv("ADVISORS_DIR", "/root/.mckoutie/advisors"))
SERVICE_SECRET = os.getenv("ADVISOR_SERVICE_SECRET", "mck-advisor-2026")
MAX_HISTORY = 40  # max messages per conversation

# ── In-memory state ─────────────────────────────────────────────────

# conversations[report_id][session_id] = [messages]
conversations: Dict[str, Dict[str, List[dict]]] = {}
# soul_cache[report_id] = system_prompt
soul_cache: Dict[str, str] = {}

app = FastAPI(title="mckoutie Advisor Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Soul generation ─────────────────────────────────────────────────

def build_soul(report_data: dict) -> str:
    """Build a system prompt from a mckoutie report."""
    startup = report_data.get("startup_name", "the startup")
    target = report_data.get("target", "")

    # Extract key sections
    analysis = report_data.get("traction_analysis", {})
    leads = report_data.get("leads_research", {})
    investors = report_data.get("investor_research", {})

    # Channel summary
    channels = analysis.get("channels", [])
    channel_summary = ""
    if channels:
        top = sorted(channels, key=lambda c: c.get("score", 0), reverse=True)[:5]
        channel_summary = "Top channels:\n" + "\n".join(
            f"  - {c.get('name', '?')} (score: {c.get('score', '?')}/10): {c.get('one_liner', '')}"
            for c in top
        )

    # Leads summary
    personas = leads.get("personas", [])
    persona_text = ""
    if personas:
        persona_text = "Customer personas:\n" + "\n".join(
            f"  - {p.get('name', '?')}: {p.get('description', '')}"
            for p in personas[:3]
        )

    lead_list = leads.get("leads", [])
    leads_text = ""
    if lead_list:
        leads_text = "Potential leads found:\n" + "\n".join(
            f"  - {l.get('name', '?')} ({l.get('platform', '?')}): {l.get('relevance_reason', '')}"
            for l in lead_list[:10]
        )

    # Investors summary
    competitors = investors.get("competitors", [])
    comp_text = ""
    if competitors:
        comp_text = "Competitors:\n" + "\n".join(
            f"  - {c.get('name', '?')}: {c.get('funding', 'unknown funding')}"
            for c in competitors[:5]
        )

    investor_list = investors.get("competitor_investors", []) + investors.get("market_investors", [])
    inv_text = ""
    if investor_list:
        inv_text = "Relevant investors:\n" + "\n".join(
            f"  - {i.get('name', '?')} ({i.get('type', '?')}): {i.get('focus', '')}"
            for i in investor_list[:10]
        )

    hot_take = analysis.get("hot_take", "")
    exec_summary = analysis.get("executive_summary", "")
    stage = analysis.get("stage", "")
    market = analysis.get("market", "")

    soul = f"""You are the mckoutie advisor for {startup}.
You are a sharp, direct startup strategy advisor. You combine McKinsey-level analysis with indie hacker pragmatism.

Your personality:
- Direct but warm. No corporate BS.
- You give specific, actionable advice — not vague platitudes
- You challenge assumptions respectfully
- You think in terms of experiments: "test this for 2 weeks, measure X"
- You know this startup inside out from your analysis

== STARTUP CONTEXT ==
Name: {startup}
Website/Target: {target}
Stage: {stage}
Market: {market}

Executive Summary: {exec_summary}

Hot Take: {hot_take}

{channel_summary}

{persona_text}

{leads_text}

{comp_text}

{inv_text}

== YOUR ROLE ==
You are this startup's dedicated strategy advisor. You:
1. Answer questions about their traction strategy
2. Help them prioritize channels and actions
3. Brainstorm outreach approaches for specific leads/investors
4. Debate strategic decisions (pricing, positioning, pivots)
5. Give honest feedback — if something is a bad idea, say so

Keep responses concise. Use plain text, not markdown. Think like a board advisor who has 5 minutes to give sharp advice.

When the user asks about specific channels, leads, or investors, reference the data you know about their startup.
"""
    return soul


def load_report(report_id: str) -> Optional[dict]:
    """Load a report from the reports directory."""
    # Try multiple possible locations
    for pattern in [
        REPORTS_DIR / report_id / "report.json",
        REPORTS_DIR / f"{report_id}.json",
    ]:
        if pattern.exists():
            try:
                return json.loads(pattern.read_text())
            except Exception as e:
                logger.error(f"Failed to load {pattern}: {e}")
    return None


def get_soul(report_id: str) -> str:
    """Get or build the soul prompt for a report."""
    if report_id in soul_cache:
        return soul_cache[report_id]

    report = load_report(report_id)
    if not report:
        # Fallback generic advisor
        soul = """You are a mckoutie startup advisor. You help startups with traction strategy across 19 channels (from the book Traction by Gabriel Weinberg). You're direct, specific, and action-oriented. No corporate BS."""
        soul_cache[report_id] = soul
        return soul

    soul = build_soul(report)
    soul_cache[report_id] = soul
    return soul


# ── Chat endpoint ───────────────────────────────────────────────────

@app.post("/chat/{report_id}")
async def chat(report_id: str, request: Request):
    """Chat with the advisor for a specific report."""
    body = await request.json()
    message = body.get("message", "").strip()
    session_id = body.get("session_id", "default")
    tier = body.get("tier", "free")  # free | starter | growth
    stream = body.get("stream", True)

    if not message:
        raise HTTPException(400, "message required")

    # Get or create conversation
    if report_id not in conversations:
        conversations[report_id] = {}
    if session_id not in conversations[report_id]:
        conversations[report_id][session_id] = []

    history = conversations[report_id][session_id]

    # Add user message
    history.append({"role": "user", "content": message})

    # Trim history if too long
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    # Build messages
    soul = get_soul(report_id)
    messages = [{"role": "system", "content": soul}] + history

    # Select model based on tier
    model = PAID_MODEL if tier in ("starter", "growth") else FREE_MODEL

    if stream:
        return StreamingResponse(
            stream_response(messages, model, history),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        # Non-streaming response
        full_response = await get_response(messages, model)
        history.append({"role": "assistant", "content": full_response})
        return JSONResponse({"response": full_response, "model": model})


async def stream_response(messages: list, model: str, history: list):
    """Stream chat completion from OpenRouter."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mckoutie.com",
        "X-Title": "mckoutie advisor",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048,
        "temperature": 0.7,
    }

    full_response = ""

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            async with client.stream(
                "POST", OPENROUTER_URL, json=payload, headers=headers
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    logger.error(f"OpenRouter error {resp.status_code}: {error_body[:500]}")
                    yield f"data: {json.dumps({'error': 'Model unavailable, try again'})}\n\n"
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_response += content
                            yield f"data: {json.dumps({'content': content})}\n\n"
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    # Save assistant response to history
    if full_response:
        history.append({"role": "assistant", "content": full_response})

    yield f"data: {json.dumps({'done': True})}\n\n"


async def get_response(messages: list, model: str) -> str:
    """Non-streaming chat completion."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mckoutie.com",
        "X-Title": "mckoutie advisor",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error(f"OpenRouter error: {resp.text[:500]}")
            return "Sorry, I'm having trouble connecting. Try again in a moment."

        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


# ── Session management ──────────────────────────────────────────────

@app.get("/sessions/{report_id}")
async def list_sessions(report_id: str):
    """List active sessions for a report."""
    if report_id not in conversations:
        return {"sessions": []}
    return {"sessions": list(conversations[report_id].keys())}


@app.delete("/sessions/{report_id}/{session_id}")
async def clear_session(report_id: str, session_id: str):
    """Clear a conversation session."""
    if report_id in conversations and session_id in conversations[report_id]:
        del conversations[report_id][session_id]
    return {"status": "cleared"}


@app.post("/soul/{report_id}")
async def update_soul(report_id: str, request: Request):
    """Update the soul/report data for an advisor. Called by Railway when a report is generated."""
    body = await request.json()
    secret = body.get("secret", "")
    if secret != SERVICE_SECRET:
        raise HTTPException(403, "unauthorized")

    report_data = body.get("report_data", {})
    if report_data:
        # Save report to disk
        report_dir = REPORTS_DIR / report_id
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "report.json").write_text(json.dumps(report_data, indent=2))

        # Rebuild soul
        soul = build_soul(report_data)
        soul_cache[report_id] = soul

        # Clear existing conversations (new data = fresh start)
        if report_id in conversations:
            del conversations[report_id]

        logger.info(f"Updated soul for report {report_id}")

    return {"status": "updated"}


# ── Health ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "active_reports": len(conversations),
        "total_sessions": sum(len(s) for s in conversations.values()),
        "free_model": FREE_MODEL,
        "paid_model": PAID_MODEL,
    }


if __name__ == "__main__":
    port = int(os.getenv("ADVISOR_PORT", 3460))
    logger.info(f"Starting mckoutie advisor service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
