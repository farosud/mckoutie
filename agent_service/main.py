"""
mckoutie Agent Chat Service — runs on the droplet.

Each mckoutie subscriber gets a personal AI advisor that knows their startup
deeply. The agent is pre-loaded with their traction report data (channels,
leads, investors, personas) and acts as an ongoing strategic advisor.

Uses GLM-4.7 via OpenRouter for cheap inference (~$0.001/1K tokens).
Conversation history stored in Supabase.
"""

import json
import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="mckoutie-agent", description="Personal AI advisor for mckoutie subscribers")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.mckoutie.com", "https://mckoutie.com", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ────────────────────────────────────────────────────────────

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
AGENT_SECRET = os.environ.get("AGENT_SECRET", "")  # shared secret with Railway
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen/qwen3-235b-a22b:free")  # free tier model
CHAT_MODEL_FALLBACK = os.environ.get("CHAT_MODEL_FALLBACK", "google/gemini-2.5-flash-preview-05-20")
MAX_HISTORY = 40  # keep last N messages in context
REPORT_DATA_DIR = os.environ.get("REPORT_DATA_DIR", "/opt/mckoutie/reports")

# ── Supabase client ───────────────────────────────────────────────────

_supabase = None

def get_supabase():
    global _supabase
    if _supabase is not None:
        return _supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _supabase
    except Exception as e:
        logger.error(f"Supabase init failed: {e}")
        return None


# ── Conversation storage ──────────────────────────────────────────────

def get_history(report_id: str, user_id: str) -> list[dict]:
    """Load conversation history from Supabase."""
    client = get_supabase()
    if not client:
        return []
    try:
        result = (
            client.table("chat_messages")
            .select("role, content")
            .eq("report_id", report_id)
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .limit(MAX_HISTORY)
            .execute()
        )
        return [{"role": r["role"], "content": r["content"]} for r in (result.data or [])]
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        return []


def save_message(report_id: str, user_id: str, role: str, content: str):
    """Save a single message to Supabase."""
    client = get_supabase()
    if not client:
        return
    try:
        client.table("chat_messages").insert({
            "report_id": report_id,
            "user_id": user_id,
            "role": role,
            "content": content,
        }).execute()
    except Exception as e:
        logger.error(f"Failed to save message: {e}")


# ── System prompt builder ─────────────────────────────────────────────

def build_system_prompt(report_data: dict) -> str:
    """Build a rich system prompt from the traction report data."""
    company = report_data.get("company_profile", {})
    executive = report_data.get("executive_summary", "")
    channels = report_data.get("channel_analysis", [])
    bullseye = report_data.get("bullseye_ranking", {})
    plan = report_data.get("ninety_day_plan", {})
    budget = report_data.get("budget_allocation", [])
    hot_take = report_data.get("hot_take", "")
    leads = report_data.get("leads_research", {})
    investors = report_data.get("investor_research", {})
    personas = report_data.get("personas", [])

    # Build channel summary
    channel_lines = []
    for ch in channels[:19]:
        name = ch.get("channel", ch.get("name", ""))
        score = ch.get("score", "?")
        insight = ch.get("key_insight", ch.get("insight", ""))
        channel_lines.append(f"  - {name}: {score}/10 — {insight}")

    # Build leads summary
    lead_lines = []
    for lead in (leads.get("leads", []) if isinstance(leads, dict) else [])[:10]:
        name = lead.get("name", "Unknown")
        platform = lead.get("platform", "")
        reason = lead.get("relevance_reason", lead.get("reason", ""))
        lead_lines.append(f"  - {name} ({platform}): {reason}")

    # Build investor summary
    inv_lines = []
    investor_list = investors.get("market_investors", []) if isinstance(investors, dict) else []
    for inv in investor_list[:10]:
        name = inv.get("name", "Unknown")
        inv_type = inv.get("type", "")
        focus = inv.get("focus", inv.get("thesis", ""))
        inv_lines.append(f"  - {name} ({inv_type}): {focus}")

    # Build persona summary
    persona_lines = []
    for p in (personas if isinstance(personas, list) else [])[:3]:
        pname = p.get("name", "Unknown")
        desc = p.get("description", p.get("defining_trait", ""))
        persona_lines.append(f"  - {pname}: {desc}")

    # Inner ring channels
    inner = bullseye.get("inner_ring", bullseye.get("test_now", []))
    inner_names = [c.get("channel", c) if isinstance(c, dict) else str(c) for c in inner[:3]]

    return f"""You are the personal AI strategy advisor for {company.get('name', 'this startup')}.
You are part of the mckoutie advisory council — a team of AI advisors that help startups grow.

Your personality: Direct, strategic, slightly irreverent. You give advice like a seasoned founder
who's seen it all — not like a consultant reading from a playbook. Use concrete examples and
specific actions, not vague platitudes. Be honest when something is a bad idea.

ABOUT THE COMPANY:
  Name: {company.get('name', 'Unknown')}
  Stage: {company.get('stage', 'Unknown')}
  Market: {company.get('market', 'Unknown')}
  Description: {company.get('description', executive)}

HOT TAKE FROM INITIAL ANALYSIS:
  {hot_take}

TOP 3 GROWTH CHANNELS (Bullseye inner ring):
  {', '.join(inner_names) if inner_names else 'Not determined yet'}

ALL 19 CHANNEL SCORES:
{chr(10).join(channel_lines) if channel_lines else '  No channel data available yet.'}

CUSTOMER PERSONAS:
{chr(10).join(persona_lines) if persona_lines else '  No persona data available yet.'}

POTENTIAL LEADS FOUND:
{chr(10).join(lead_lines) if lead_lines else '  No leads found yet.'}

POTENTIAL INVESTORS:
{chr(10).join(inv_lines) if inv_lines else '  No investors found yet.'}

90-DAY PLAN SUMMARY:
  {json.dumps(plan, indent=2)[:2000] if plan else 'Not generated yet.'}

BUDGET ALLOCATION:
  {json.dumps(budget, indent=2)[:1000] if budget else 'Not determined yet.'}

RULES:
- Always reference specific data from the analysis above when giving advice
- If asked about something outside your knowledge, say so honestly
- Suggest specific, actionable next steps — not generic advice
- When discussing channels, reference the scores and insights from the analysis
- When discussing leads or investors, reference the specific people found
- Keep responses concise but substantive — 2-4 paragraphs max unless asked for detail
- You can use the traction framework (19 channels) as a shared language with the user
- If the user asks about something that would benefit from fresh research, suggest they
  request an updated analysis
"""


# ── LLM call ──────────────────────────────────────────────────────────

async def call_llm(messages: list[dict], model: str = None) -> str:
    """Call OpenRouter with the given messages."""
    model = model or CHAT_MODEL

    async with httpx.AsyncClient(timeout=120) as client:
        for attempt, m in enumerate([model, CHAT_MODEL_FALLBACK]):
            try:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://mckoutie.com",
                        "X-Title": "mckoutie-agent",
                    },
                    json={
                        "model": m,
                        "messages": messages,
                        "max_tokens": 2000,
                        "temperature": 0.7,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if content:
                    logger.info(f"LLM response from {m}: {len(content)} chars")
                    return content
            except Exception as e:
                logger.error(f"LLM call failed (model={m}, attempt={attempt}): {e}")
                continue

    return "I'm having trouble connecting right now. Please try again in a moment."


# ── Report data loading ───────────────────────────────────────────────

_report_cache: dict[str, dict] = {}

def load_report_data(report_id: str) -> dict | None:
    """Load report analysis data. Checks local cache, then Supabase."""
    if report_id in _report_cache:
        return _report_cache[report_id]

    # Try local filesystem
    local_path = Path(REPORT_DATA_DIR) / report_id / "analysis.json"
    if local_path.exists():
        try:
            data = json.loads(local_path.read_text())
            _report_cache[report_id] = data
            return data
        except Exception as e:
            logger.error(f"Failed to load local report {report_id}: {e}")

    # Try fetching from Railway
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"https://www.mckoutie.com/api/report-data/{report_id}")
            if resp.status_code == 200:
                data = resp.json()
                _report_cache[report_id] = data
                return data
    except Exception as e:
        logger.error(f"Failed to fetch report from Railway: {e}")

    return None


# ── API endpoints ─────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    report_id: str
    user_id: str  # twitter_id of the user


class ChatResponse(BaseModel):
    reply: str
    model: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    """Main chat endpoint. Handles a single user message and returns the advisor response."""
    # Verify shared secret
    auth = request.headers.get("X-Agent-Secret", "")
    if AGENT_SECRET and auth != AGENT_SECRET:
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    # Load report data
    report_data = load_report_data(req.report_id)
    if not report_data:
        return ChatResponse(
            reply="I don't have your startup analysis loaded yet. Make sure your report has been generated first.",
            model="none",
        )

    # Build system prompt
    system_prompt = build_system_prompt(report_data)

    # Load conversation history
    history = get_history(req.report_id, req.user_id)

    # Build messages array
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": req.message})

    # Call LLM
    reply = await call_llm(messages)

    # Save both messages to history
    save_message(req.report_id, req.user_id, "user", req.message)
    save_message(req.report_id, req.user_id, "assistant", reply)

    return ChatResponse(reply=reply, model=CHAT_MODEL)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "mckoutie-agent",
        "model": CHAT_MODEL,
        "supabase": bool(get_supabase()),
        "timestamp": int(time.time()),
    }


@app.post("/cache/load")
async def cache_load(request: Request):
    """Pre-load report data into cache (called by Railway after report generation)."""
    auth = request.headers.get("X-Agent-Secret", "")
    if AGENT_SECRET and auth != AGENT_SECRET:
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    body = await request.json()
    report_id = body.get("report_id")
    data = body.get("data")
    if report_id and data:
        _report_cache[report_id] = data
        logger.info(f"Cached report data for {report_id}")
        return {"status": "cached", "report_id": report_id}
    return JSONResponse(status_code=400, content={"error": "missing report_id or data"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3460))
    uvicorn.run(app, host="0.0.0.0", port=port)
