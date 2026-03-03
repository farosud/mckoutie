"""
FastAPI server — serves reports and handles Stripe webhooks.

Endpoints:
  GET  /                        — landing page
  GET  /report/{report_id}      — view report (teaser or full depending on payment)
  POST /webhook/stripe          — Stripe payment webhook
  GET  /health                  — health check
  GET  /stats                   — basic stats
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.modules import payments, report_store
from src.analysis.report_generator import generate_report_html

REPORTS_DIR = Path(__file__).parent.parent / "reports"

logger = logging.getLogger(__name__)

app = FastAPI(title="mckoutie", description="McKinsey at home")

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def landing():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mckoutie — McKinsey at home</title>
    <style>
        :root { --bg: #0a0a0a; --text: #e0e0e0; --accent: #00ff88; --muted: #666; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'SF Mono', 'Fira Code', monospace;
            background: var(--bg); color: var(--text);
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; padding: 2rem;
        }
        .container { max-width: 600px; text-align: center; }
        h1 { color: var(--accent); font-size: 3rem; margin-bottom: 0.5rem; }
        .tagline { color: var(--muted); font-size: 1.2rem; margin-bottom: 2rem; }
        .how {
            text-align: left; background: #111; padding: 1.5rem;
            border: 1px solid #222; border-radius: 8px; margin: 1.5rem 0;
        }
        .how h2 { color: var(--accent); font-size: 1rem; margin-bottom: 1rem; }
        .how p { margin: 0.5rem 0; color: var(--text); font-size: 0.9rem; }
        .how code { color: var(--accent); background: #1a1a1a; padding: 2px 6px; border-radius: 3px; }
        .price { color: #ff6b35; font-size: 1.4rem; margin: 1.5rem 0; }
        a { color: var(--accent); text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>mckoutie</h1>
        <p class="tagline">McKinsey at home</p>
        <p>AI startup consulting for $100 instead of $100K.</p>

        <div class="how">
            <h2>How it works</h2>
            <p>1. Tweet <code>@mckoutie analyse my startup https://yoursite.com</code></p>
            <p>2. Or tag a company: <code>@mckoutie analyse my startup @company</code></p>
            <p>3. Get a free teaser thread with your top 3 growth channels</p>
            <p>4. Pay $100 for the full 19-channel strategy brief</p>
        </div>

        <p class="price">Full brief: $100 (you'd pay a consultant $5K+ for this)</p>

        <p>What you get:</p>
        <div class="how">
            <p>- 19-channel traction analysis scored for YOUR startup</p>
            <p>- Bullseye framework: top 3 channels to test NOW</p>
            <p>- 90-day action plan with weekly milestones</p>
            <p>- Budget allocation recommendations</p>
            <p>- Risk matrix with mitigations</p>
            <p>- Competitive moat analysis</p>
            <p>- A brutally honest hot take</p>
        </div>

        <p style="color: var(--muted); margin-top: 2rem; font-size: 0.8rem;">
            Built with vibes. Not affiliated with McKinsey (obviously).
        </p>
    </div>
</body>
</html>"""


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def view_report(report_id: str, paid: str | None = None):
    """View a report — shows teaser or full based on payment status."""
    record = report_store.load_record(report_id)

    if not record:
        return HTMLResponse(
            content="<h1>Report not found</h1><p>This report doesn't exist.</p>",
            status_code=404,
        )

    if record.status == "analyzing":
        return HTMLResponse(content=_processing_page(record))

    if record.status == "failed":
        return HTMLResponse(
            content=f"<h1>Analysis failed</h1><p>{record.error}</p>",
            status_code=500,
        )

    # Check if paid
    if record.status == "paid":
        # Serve full report
        report_path = REPORTS_DIR / report_id / "report.md"
        if report_path.exists():
            md_content = report_path.read_text()
            html = generate_report_html(md_content, record.startup_name)
            return HTMLResponse(content=html)

    # Not paid — show teaser/paywall
    return HTMLResponse(content=_paywall_page(record))


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe payment webhooks."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    event = payments.verify_webhook(payload, sig)
    if not event:
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        report_id = session.get("metadata", {}).get("report_id")

        if report_id:
            report_store.update_status(
                report_id,
                "paid",
                paid_at=datetime.now(tz=timezone.utc).isoformat(),
            )
            logger.info(f"Payment received for report {report_id}")

    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mckoutie", "version": "0.1.0"}


@app.get("/stats")
async def stats():
    all_reports = report_store.list_reports()
    return {
        "total_reports": len(all_reports),
        "paid": len([r for r in all_reports if r.status == "paid"]),
        "ready": len([r for r in all_reports if r.status == "ready"]),
        "analyzing": len([r for r in all_reports if r.status == "analyzing"]),
        "failed": len([r for r in all_reports if r.status == "failed"]),
    }


def _processing_page(record: report_store.ReportRecord) -> str:
    return f"""<!DOCTYPE html>
<html><head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="15">
    <title>mckoutie — Analyzing...</title>
    <style>
        body {{ font-family: monospace; background: #0a0a0a; color: #e0e0e0;
               display: flex; justify-content: center; align-items: center;
               min-height: 100vh; }}
        .container {{ text-align: center; max-width: 500px; }}
        h1 {{ color: #00ff88; }}
        .spinner {{ font-size: 2rem; animation: spin 1s linear infinite; display: inline-block; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        p {{ color: #666; margin: 1rem 0; }}
    </style>
</head><body>
    <div class="container">
        <div class="spinner">&#9881;</div>
        <h1>Analyzing {record.startup_name}...</h1>
        <p>Running full 19-channel traction analysis.</p>
        <p>This takes 30-60 seconds. Page refreshes automatically.</p>
        <p style="color: #333; font-size: 0.8rem;">Report ID: {record.report_id}</p>
    </div>
</body></html>"""


def _paywall_page(record: report_store.ReportRecord) -> str:
    checkout_url = record.checkout_url or "#"

    # Try to load real analysis data for a richer teaser
    teaser_html = ""
    blurred_html = ""
    analysis_path = REPORTS_DIR / record.report_id / "analysis.json"
    if analysis_path.exists():
        try:
            analysis = json.loads(analysis_path.read_text())
            profile = analysis.get("company_profile", {})
            bullseye = analysis.get("bullseye_ranking", {})
            inner = bullseye.get("inner_ring", {})
            exec_summary = analysis.get("executive_summary", "")

            # Real teaser: exec summary first paragraph + top 3 channels
            first_para = exec_summary.split("\n\n")[0] if exec_summary else ""
            if first_para:
                teaser_html += f"<p>{first_para}</p>"

            inner_channels = inner.get("channels", [])
            channel_scores = {
                ch["channel"]: ch.get("score", "?")
                for ch in analysis.get("channel_analysis", [])
            }
            if inner_channels:
                teaser_html += "<h3 style='color: #00ff88; margin-top: 1rem;'>Top 3 Channels</h3>"
                for i, ch in enumerate(inner_channels[:3], 1):
                    score = channel_scores.get(ch, "?")
                    teaser_html += f"<p>{i}. {ch} — {score}/10</p>"

            # Blurred section: show real channel names but blur the details
            blurred_items = ""
            for ch in analysis.get("channel_analysis", [])[:6]:
                name = ch.get("channel", "")
                score = ch.get("score", "?")
                insight = ch.get("killer_insight", "The specific insight for this channel...")
                blurred_items += f"<p><strong>{name}</strong> ({score}/10) — {insight[:80]}...</p>"
            if blurred_items:
                blurred_html = blurred_items

        except Exception:
            pass  # Fall back to generic content

    if not teaser_html:
        teaser_html = (
            "<p>Your 19-channel analysis is ready. Here's a taste:</p>"
            "<p>Executive summary, bullseye framework, and top 3 channels "
            "are in the free teaser thread on Twitter.</p>"
        )

    if not blurred_html:
        blurred_html = (
            "<p>1. Viral Marketing (8/10) — Your product has a natural sharing moment when...</p>"
            "<p>2. Content Marketing (9/10) — The obvious play is to create a series of...</p>"
            "<p>3. Community Building (7/10) — Your audience already gathers in...</p>"
            "<p>4. SEO (6/10) — Long-tail keywords around your problem space include...</p>"
        )

    return f"""<!DOCTYPE html>
<html><head>
    <meta charset="UTF-8">
    <title>mckoutie — {record.startup_name} Brief</title>
    <style>
        body {{ font-family: monospace; background: #0a0a0a; color: #e0e0e0;
               max-width: 700px; margin: 0 auto; padding: 2rem; }}
        h1 {{ color: #00ff88; }}
        h2 {{ color: #ff6b35; margin-top: 2rem; }}
        h3 {{ color: #00ff88; }}
        .teaser {{ background: #111; padding: 1.5rem; border: 1px solid #222;
                   border-radius: 8px; margin: 1rem 0; }}
        .blurred {{ filter: blur(5px); user-select: none; pointer-events: none;
                    background: #111; padding: 1.5rem; border: 1px solid #222;
                    border-radius: 8px; margin: 1rem 0; }}
        .cta {{ display: inline-block; background: #00ff88; color: #0a0a0a;
                padding: 1rem 2rem; font-size: 1.1rem; font-weight: bold;
                text-decoration: none; border-radius: 6px; margin: 2rem 0;
                font-family: monospace; }}
        .cta:hover {{ background: #00cc6a; }}
        .price {{ color: #ff6b35; font-size: 1.2rem; }}
        strong {{ color: #00ff88; }}
    </style>
</head><body>
    <h1>mckoutie</h1>
    <p>Strategy Brief for <strong>{record.startup_name}</strong></p>

    <div class="teaser">
        <h2>Preview</h2>
        {teaser_html}
    </div>

    <h2>Full Brief Includes:</h2>
    <div class="teaser">
        <p>&#10003; 19-channel deep analysis with specific tactics</p>
        <p>&#10003; 90-day action plan with weekly milestones</p>
        <p>&#10003; Budget allocation recommendations</p>
        <p>&#10003; Risk matrix with mitigations</p>
        <p>&#10003; Competitive moat analysis</p>
        <p>&#10003; The hot take (the thing nobody will tell you)</p>
    </div>

    <div class="blurred">
        <h2>Channel Analysis</h2>
        {blurred_html}
    </div>

    <div style="text-align: center;">
        <p class="price">${settings.report_price_usd} — one-time payment</p>
        <p style="color: #666;">You'd pay a consultant $5,000+ for this.</p>
        <a class="cta" href="{checkout_url}">Unlock Full Brief</a>
    </div>

    <p style="color: #333; font-size: 0.8rem; margin-top: 3rem;">
        Report ID: {record.report_id} | Not affiliated with McKinsey.
    </p>
</body></html>"""
