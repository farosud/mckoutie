"""
mckoutie Advisor Service — Per-user AI strategy advisor agents.

Runs on the VPS (165.227.18.32:3458).
Each mckoutie subscriber gets their own agent with:
  - Personalized SOUL.md based on their startup analysis
  - Memory seeded from their traction report
  - Conversation history persisted to disk
  - Cheap LLM for ongoing chat (GLM 4.7 via OpenRouter)
  - Claude via local proxy for deep analysis (on-demand)
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("advisor")

# ─── Config ──────────────────────────────────────────────────────────────────

AGENTS_DIR = Path(os.getenv("AGENTS_DIR", "/root/.mckoutie/agents"))
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
LOCAL_PROXY_URL = os.getenv("LOCAL_PROXY_URL", "http://127.0.0.1:3456/v1")
LOCAL_PROXY_KEY = os.getenv("LOCAL_PROXY_KEY", "dummy")
PROXY_SECRET = os.getenv("ADVISOR_API_KEY", "")  # auth for Railway → this service
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen/qwen3-235b-a22b")  # cheap, good
DEEP_MODEL = os.getenv("DEEP_MODEL", "anthropic/claude-sonnet-4")  # for deep analysis
MAX_HISTORY = 50  # max messages kept in memory per agent

app = FastAPI(title="mckoutie Advisor Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── LLM Clients ────────────────────────────────────────────────────────────

def get_openrouter_client():
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_KEY,
    )

def get_local_client():
    return OpenAI(
        base_url=LOCAL_PROXY_URL,
        api_key=LOCAL_PROXY_KEY,
    )

# ─── Agent Management ───────────────────────────────────────────────────────

def get_agent_dir(agent_id: str) -> Path:
    return AGENTS_DIR / agent_id

def agent_exists(agent_id: str) -> bool:
    return (get_agent_dir(agent_id) / "SOUL.md").exists()

def load_soul(agent_id: str) -> str:
    soul_path = get_agent_dir(agent_id) / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text()
    return "You are a helpful AI strategy advisor."

def load_memory(agent_id: str) -> str:
    memory_path = get_agent_dir(agent_id) / "memory" / "report.md"
    if memory_path.exists():
        return memory_path.read_text()
    return ""

def load_history(agent_id: str) -> list:
    history_path = get_agent_dir(agent_id) / "conversation.json"
    if history_path.exists():
        try:
            return json.loads(history_path.read_text())
        except Exception:
            return []
    return []

def save_history(agent_id: str, history: list):
    history_path = get_agent_dir(agent_id) / "conversation.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep only last MAX_HISTORY messages
    trimmed = history[-MAX_HISTORY:]
    history_path.write_text(json.dumps(trimmed, indent=2))

def build_system_prompt(agent_id: str) -> str:
    soul = load_soul(agent_id)
    memory = load_memory(agent_id)

    parts = [soul]
    if memory:
        parts.append("\n\n## Startup Analysis & Context\n\n" + memory)

    return "\n".join(parts)


# ─── Provision Agent ─────────────────────────────────────────────────────────

class ProvisionRequest(BaseModel):
    agent_id: str  # typically twitter_id or report_id
    startup_name: str
    startup_url: str = ""
    industry: str = ""
    stage: str = ""
    report_summary: str = ""  # markdown summary of the traction report
    channels_data: str = ""   # JSON string of channel analysis
    leads_data: str = ""      # JSON string of leads
    investors_data: str = ""  # JSON string of investors
    hot_take: str = ""

@app.post("/provision")
async def provision_agent(req: ProvisionRequest, request: Request):
    _check_auth(request)

    agent_dir = get_agent_dir(req.agent_id)
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory").mkdir(exist_ok=True)

    # Generate SOUL.md
    soul = f"""# mckoutie Strategy Advisor

You are the dedicated AI strategy advisor for **{req.startup_name}**.

## Your Role
You are a senior strategy consultant with deep expertise in startup growth,
marketing channels, and go-to-market execution. You've analyzed {req.startup_name}
in detail and have specific, actionable recommendations.

## Your Personality
- Direct and honest — you don't sugarcoat, but you're constructive
- You think in frameworks (Bullseye, AARRR, Jobs-to-be-Done) but explain simply
- You reference specific data from your analysis, not generic advice
- You challenge assumptions when the founder is going down the wrong path
- You celebrate wins and acknowledge progress
- When asked something outside your analysis, you say so honestly

## Key Context
- Startup: {req.startup_name}
- URL: {req.startup_url}
- Industry: {req.industry}
- Stage: {req.stage}

## Communication Style
- Keep responses concise unless deep analysis is requested
- Use bullet points and structure for actionable advice
- When recommending an action, include the FIRST STEP (not just the strategy)
- Reference specific channels, leads, and investors from the analysis
- If the user asks about a channel, pull from your analysis data

## What You Can Help With
- Prioritizing growth channels
- Crafting outreach messages to specific leads/investors
- Refining positioning and messaging
- Planning sprints and 30/60/90 day strategies
- Evaluating new ideas against the traction framework
- Preparing pitch decks and investor conversations
"""

    (agent_dir / "SOUL.md").write_text(soul)

    # Generate memory/report.md from the analysis data
    report_parts = [f"# {req.startup_name} — Traction Analysis\n"]

    if req.hot_take:
        report_parts.append(f"## Hot Take\n{req.hot_take}\n")

    if req.report_summary:
        report_parts.append(f"## Summary\n{req.report_summary}\n")

    if req.channels_data:
        report_parts.append(f"## Channel Analysis\n```json\n{req.channels_data}\n```\n")

    if req.leads_data:
        report_parts.append(f"## Potential Leads\n```json\n{req.leads_data}\n```\n")

    if req.investors_data:
        report_parts.append(f"## Investors\n```json\n{req.investors_data}\n```\n")

    (agent_dir / "memory" / "report.md").write_text("\n".join(report_parts))

    # Initialize empty conversation
    save_history(req.agent_id, [])

    logger.info(f"Provisioned agent for {req.startup_name} (id={req.agent_id})")
    return {"status": "ok", "agent_id": req.agent_id}


# ─── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    agent_id: str
    message: str
    deep: bool = False  # use Claude for deep analysis instead of cheap model

class ChatResponse(BaseModel):
    reply: str
    model: str
    agent_id: str

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    _check_auth(request)

    if not agent_exists(req.agent_id):
        raise HTTPException(404, f"Agent {req.agent_id} not found. Provision it first.")

    system_prompt = build_system_prompt(req.agent_id)
    history = load_history(req.agent_id)

    # Add user message
    history.append({"role": "user", "content": req.message})

    # Build messages for LLM
    messages = [{"role": "system", "content": system_prompt}] + history

    # Choose model
    if req.deep:
        # Use local Claude proxy for deep analysis
        try:
            client = get_local_client()
            model = "claude-sonnet-4-20250514"
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=4096,
                temperature=0.7,
            )
            used_model = f"claude-sonnet (local)"
        except Exception as e:
            logger.warning(f"Local proxy failed, falling back to OpenRouter: {e}")
            client = get_openrouter_client()
            model = DEEP_MODEL
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=4096,
                temperature=0.7,
            )
            used_model = model
    else:
        # Use cheap model via OpenRouter
        try:
            client = get_openrouter_client()
            model = CHAT_MODEL
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=0.7,
            )
            used_model = model
        except Exception as e:
            logger.error(f"OpenRouter failed: {e}")
            raise HTTPException(502, f"LLM provider error: {str(e)}")

    assistant_reply = response.choices[0].message.content or ""

    # Save to history
    history.append({"role": "assistant", "content": assistant_reply})
    save_history(req.agent_id, history)

    return ChatResponse(
        reply=assistant_reply,
        model=used_model,
        agent_id=req.agent_id,
    )


# ─── Status ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agents": len(list(AGENTS_DIR.iterdir())) if AGENTS_DIR.exists() else 0}

@app.get("/agent/{agent_id}")
async def agent_status(agent_id: str, request: Request):
    _check_auth(request)
    if not agent_exists(agent_id):
        raise HTTPException(404, "Agent not found")

    history = load_history(agent_id)
    soul = load_soul(agent_id)

    return {
        "agent_id": agent_id,
        "message_count": len(history),
        "soul_length": len(soul),
        "has_memory": (get_agent_dir(agent_id) / "memory" / "report.md").exists(),
    }

@app.post("/agent/{agent_id}/reset")
async def reset_agent(agent_id: str, request: Request):
    _check_auth(request)
    if not agent_exists(agent_id):
        raise HTTPException(404, "Agent not found")
    save_history(agent_id, [])
    return {"status": "ok", "message": "Conversation reset"}


# ─── Auth ────────────────────────────────────────────────────────────────────

def _check_auth(request: Request):
    if not PROXY_SECRET:
        return  # no auth configured = dev mode
    token = request.headers.get("X-Advisor-Key", "")
    if token != PROXY_SECRET:
        raise HTTPException(403, "Invalid API key")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ADVISOR_PORT", "3458"))
    logger.info(f"Starting mckoutie advisor service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
