"""
Dashboard renderer v2 — "Give the WHAT, sell the HOW"

Philosophy:
  FREE: Show impressive data (leads, investors, scores, hot take)
        Users see WHO to talk to but not HOW to approach them.
  STARTER ($39/mo): Full strategy, 90-day plan, personas, outreach angles
  GROWTH ($200/mo): Deep investor intel, competitor analysis, weekly updates
  ENTERPRISE: Contact emi@mckoutie.com

All server-rendered HTML. No frontend framework.
"""

import json
import logging
from html import escape
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


def render_dashboard(
    analysis: dict,
    startup_name: str,
    report_id: str,
    tier: str = "free",
    checkout_url: str = "#",
    upgrade_url: str = "#",
) -> str:
    profile = analysis.get("company_profile", {})
    bullseye = analysis.get("bullseye_ranking", {})
    channels = analysis.get("channel_analysis", [])
    plan = analysis.get("ninety_day_plan", {})
    budget = analysis.get("budget_allocation", {})
    risks = analysis.get("risk_matrix", [])
    moat = analysis.get("competitive_moat", "")
    hot_take = analysis.get("hot_take", "")
    exec_summary = analysis.get("executive_summary", "")
    leads_data = analysis.get("leads_research", {})
    investors_data = analysis.get("investor_research", {})

    # Compute stats
    top_score = 0
    top_channel = ""
    avg_score = 0
    if channels:
        scores = [(ch.get("score", 0), ch.get("channel", "")) for ch in channels]
        scores.sort(key=lambda x: x[0], reverse=True)
        top_score = scores[0][0]
        top_channel = scores[0][1]
        avg_score = round(sum(s[0] for s in scores) / len(scores), 1)

    num_leads = len(leads_data.get("leads", []))
    num_investors = len(investors_data.get("market_investors", [])) + len(investors_data.get("competitor_investors", []))
    num_competitors = len(investors_data.get("competitors", []))

    from datetime import datetime, timezone
    now_str = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mckoutie — {_e(startup_name)} Strategy Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,700;1,400&family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    {_css()}
</head>
<body>
    {_nav(startup_name, tier)}
    <main class="dash">
        {_metric_cards(top_score, top_channel, avg_score, profile, num_leads, num_investors)}
        {_hot_take(hot_take)}
        {_bullseye_compact(bullseye, channels)}
        {_channel_scores(channels, tier)}
        {_leads_section(leads_data, tier, checkout_url)}
        {_investors_section(investors_data, tier, upgrade_url)}
        {_plan_section(plan, tier, checkout_url)}
        {_budget_section(budget, tier, checkout_url)}
        {_risk_section(risks, tier, checkout_url)}
        {_moat_section(moat, tier, checkout_url)}
        {_pricing_section(report_id, tier, checkout_url, upgrade_url)}
    </main>
    <footer class="dash-foot">
        <p>mckoutie & company — McKinsey at home</p>
        <p class="sub">AI-generated analysis. Use as a starting point, not gospel. Not affiliated with McKinsey.</p>
    </footer>
</body>
</html>"""


def _e(text: str) -> str:
    return escape(str(text)) if text else ""


# ──────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────
def _css() -> str:
    return """<style>
    :root {
        --bg: #0a0e1a; --bg2: #0f1423; --card: #141a2e;
        --border: #1e2744; --border2: #2a3456;
        --text: #e0ddd5; --muted: #7a8094; --dim: #444;
        --cyan: #00d4ff; --green: #00ff88; --orange: #ff6b35;
        --red: #ff4757; --yellow: #ffd32a; --purple: #a855f7;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Space Grotesk', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
    a { color: var(--cyan); text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* NAV */
    .nav { display: flex; justify-content: space-between; align-items: center; padding: 0.8rem 2rem; border-bottom: 1px solid var(--border); background: var(--bg2); position: sticky; top: 0; z-index: 100; }
    .nav-logo { font-family: 'EB Garamond', serif; font-size: 1.2rem; color: var(--cyan); }
    .nav-logo .amp { color: var(--muted); font-style: italic; }
    .nav-logo .co { color: var(--muted); font-size: 0.7rem; font-variant: small-caps; letter-spacing: 0.1em; }
    .nav-right { display: flex; align-items: center; gap: 1rem; }
    .nav-startup { color: var(--muted); font-size: 0.85rem; }
    .badge { padding: 3px 10px; border-radius: 4px; font-family: 'Space Mono', monospace; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
    .badge-free { background: var(--border); color: var(--muted); }
    .badge-starter { background: #0a3d2a; color: var(--green); border: 1px solid var(--green); }
    .badge-growth { background: #3d2a0a; color: var(--orange); border: 1px solid var(--orange); }

    /* MAIN */
    .dash { max-width: 1100px; margin: 0 auto; padding: 2rem; }

    /* METRIC CARDS */
    .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.8rem; margin-bottom: 2rem; }
    @media (max-width: 768px) { .metrics { grid-template-columns: repeat(2, 1fr); } }
    .metric { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.2rem; text-align: center; }
    .metric-val { font-family: 'Space Mono', monospace; font-size: 1.8rem; font-weight: 700; line-height: 1.2; }
    .metric-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.2rem; }
    .metric-sub { font-size: 0.75rem; color: var(--muted); }

    /* HOT TAKE */
    .hottake { background: linear-gradient(135deg, #1a0a0a, #0a1a1a); border: 2px solid var(--orange); border-radius: 12px; padding: 2rem; margin-bottom: 2rem; }
    .hottake-label { color: var(--orange); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 0.5rem; font-weight: 700; }
    .hottake-text { font-family: 'EB Garamond', serif; font-size: 1.2rem; font-style: italic; line-height: 1.7; }

    /* SECTION */
    .section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section-title { font-family: 'EB Garamond', serif; font-size: 1.3rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
    .section-title .accent { color: var(--cyan); }
    .section-title .count { font-family: 'Space Mono', monospace; font-size: 0.8rem; color: var(--muted); }

    /* BULLSEYE */
    .bullseye-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; }
    @media (max-width: 768px) { .bullseye-row { grid-template-columns: 1fr; } }
    .ring { background: var(--bg); border-radius: 10px; padding: 1rem; text-align: center; }
    .ring-inner { border: 2px solid var(--green); }
    .ring-promising { border: 2px solid var(--yellow); }
    .ring-long { border: 1px solid var(--border); }
    .ring-title { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.6rem; font-weight: 700; }
    .ring-inner .ring-title { color: var(--green); }
    .ring-promising .ring-title { color: var(--yellow); }
    .ring-long .ring-title { color: var(--muted); }
    .ring-item { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border); font-size: 0.82rem; }
    .ring-item:last-child { border-bottom: none; }
    .ring-score { font-family: 'Space Mono', monospace; font-weight: 700; }
    .ring-inner .ring-score { color: var(--green); }
    .ring-promising .ring-score { color: var(--yellow); }

    /* CHANNEL SCORES (compact bar view) */
    .ch-list { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
    @media (max-width: 768px) { .ch-list { grid-template-columns: 1fr; } }
    .ch-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.5rem 0.8rem; background: var(--bg); border-radius: 6px; }
    .ch-name { font-size: 0.8rem; width: 180px; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ch-bar-wrap { flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
    .ch-bar { height: 100%; border-radius: 3px; transition: width 0.6s ease; }
    .ch-bar-hi { background: var(--green); }
    .ch-bar-mid { background: var(--yellow); }
    .ch-bar-lo { background: var(--muted); }
    .ch-score { font-family: 'Space Mono', monospace; font-weight: 700; font-size: 0.85rem; width: 30px; text-align: right; }
    .ch-score-hi { color: var(--green); }
    .ch-score-mid { color: var(--yellow); }
    .ch-score-lo { color: var(--muted); }

    /* Expandable channel detail (starter+) */
    .ch-detail { display: none; margin-top: 0.4rem; padding: 0.8rem; background: var(--card); border-radius: 6px; font-size: 0.8rem; }
    .ch-row.expanded .ch-detail { display: block; }
    .ch-insight { color: var(--muted); border-left: 3px solid var(--cyan); padding-left: 0.6rem; margin-bottom: 0.5rem; font-style: italic; }
    .ch-first-move { background: var(--bg); padding: 0.5rem; border-radius: 4px; margin-top: 0.4rem; }
    .ch-first-move .label { color: var(--green); font-weight: 600; font-size: 0.7rem; text-transform: uppercase; }
    .ch-ideas li { color: var(--muted); margin-left: 1rem; margin-bottom: 0.2rem; }

    /* LEADS */
    .lead-card { display: flex; justify-content: space-between; align-items: flex-start; padding: 0.8rem; background: var(--bg); border-radius: 8px; margin-bottom: 0.5rem; }
    .lead-info { flex: 1; }
    .lead-name { font-weight: 600; font-size: 0.9rem; }
    .lead-desc { font-size: 0.78rem; color: var(--muted); margin-top: 0.2rem; }
    .lead-source { font-size: 0.7rem; color: var(--dim); margin-top: 0.3rem; }
    .lead-right { display: flex; flex-direction: column; align-items: flex-end; gap: 0.3rem; }
    .lead-score-badge { font-family: 'Space Mono', monospace; font-weight: 700; font-size: 0.9rem; }
    .lead-score-hi { color: var(--green); }
    .lead-score-mid { color: var(--yellow); }
    .lead-score-lo { color: var(--muted); }
    .lead-lock { font-size: 0.7rem; color: var(--cyan); }

    /* Platform badges */
    .plat { display: inline-block; padding: 2px 7px; border-radius: 3px; font-size: 0.65rem; font-weight: 600; }
    .plat-twitter { background: #1c2733; color: #1da1f2; }
    .plat-reddit { background: #2a1500; color: #ff4500; }
    .plat-linkedin { background: #00152a; color: #0a66c2; }
    .plat-discord { background: #1a1440; color: #5865f2; }
    .plat-github { background: #161b22; color: #f0f6fc; }
    .plat-substack { background: #2a1500; color: #ff6719; }
    .plat-web { background: var(--card); color: var(--muted); }

    /* INVESTORS */
    .comp-card { background: var(--bg); border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: flex-start; }
    .comp-info h4 { font-size: 0.88rem; margin-bottom: 0.2rem; }
    .comp-info h4 a { color: var(--cyan); }
    .comp-desc { font-size: 0.73rem; color: var(--muted); }
    .comp-inv-tags { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 0.3rem; }
    .inv-tag { background: var(--card); border: 1px solid var(--border); padding: 1px 6px; border-radius: 3px; font-size: 0.65rem; color: var(--muted); }
    .fund-badge { font-family: 'Space Mono', monospace; font-weight: 700; font-size: 0.85rem; color: var(--green); padding: 4px 8px; background: #0a1a12; border: 1px solid #1a3a2a; border-radius: 5px; white-space: nowrap; }

    .inv-card { background: var(--bg); border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: flex-start; }
    .inv-info .inv-name { font-weight: 600; font-size: 0.88rem; }
    .inv-info .inv-focus { font-size: 0.73rem; color: var(--muted); margin-top: 0.15rem; }
    .inv-type { font-size: 0.65rem; padding: 2px 7px; border-radius: 3px; font-weight: 600; }
    .inv-vc { background: #1a0a33; color: var(--purple); border: 1px solid var(--purple); }
    .inv-angel { background: #1a2a0a; color: var(--green); border: 1px solid var(--green); }
    .inv-other { background: var(--card); color: var(--muted); border: 1px solid var(--border); }

    /* PERSONAS (starter+) */
    .persona { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; margin-bottom: 0.8rem; }
    .persona h4 { color: var(--cyan); font-size: 0.95rem; margin-bottom: 0.3rem; }
    .persona .who { color: var(--muted); font-size: 0.82rem; margin-bottom: 0.5rem; }
    .persona-nets { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 0.5rem; }
    .persona-signals { font-size: 0.75rem; color: var(--muted); font-style: italic; border-left: 2px solid var(--border); padding-left: 0.5rem; margin-top: 0.4rem; }

    /* 90-DAY PLAN */
    .plan-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; }
    @media (max-width: 768px) { .plan-grid { grid-template-columns: 1fr; } }
    .month { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; }
    .month h3 { color: var(--cyan); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem; }
    .month .focus { font-weight: 600; margin-bottom: 0.5rem; }
    .month .target { font-size: 0.78rem; color: var(--green); margin-bottom: 0.4rem; }
    .month .budget-amt { font-size: 0.75rem; color: var(--orange); margin-bottom: 0.4rem; }
    .month li { font-size: 0.78rem; color: var(--muted); margin-left: 1rem; margin-bottom: 0.2rem; }

    /* BUDGET TABLE */
    .budget-tbl { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    .budget-tbl th { text-align: left; color: var(--cyan); font-weight: 600; padding: 6px 10px; border-bottom: 2px solid var(--border); font-size: 0.72rem; text-transform: uppercase; }
    .budget-tbl td { padding: 6px 10px; border-bottom: 1px solid var(--border); color: var(--muted); }
    .budget-tbl tr:hover td { background: var(--bg); }
    .budget-total { text-align: center; padding: 0.8rem; font-size: 1rem; color: var(--green); font-weight: 600; }

    /* RISK TABLE */
    .risk-tbl { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    .risk-tbl th { text-align: left; color: var(--orange); font-weight: 600; padding: 6px 10px; border-bottom: 2px solid var(--border); font-size: 0.72rem; text-transform: uppercase; }
    .risk-tbl td { padding: 6px 10px; border-bottom: 1px solid var(--border); color: var(--muted); }
    .prob-hi { color: var(--red); font-weight: 600; }
    .prob-med { color: var(--yellow); }
    .prob-lo { color: var(--green); }

    /* MOAT */
    .moat-text { color: var(--muted); line-height: 1.8; }

    /* LOCKED */
    .locked { position: relative; }
    .locked-blur { filter: blur(6px); user-select: none; pointer-events: none; }
    .locked-cta { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: var(--card); border: 2px solid var(--border); border-radius: 10px; padding: 1.2rem 2rem; text-align: center; z-index: 10; min-width: 280px; }
    .locked-cta .lock-icon { font-size: 1.5rem; margin-bottom: 0.3rem; }
    .locked-cta .lock-text { color: var(--muted); font-size: 0.82rem; margin-bottom: 0.6rem; }
    .cta-btn { display: inline-block; padding: 10px 24px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; text-decoration: none; }
    .cta-primary { background: var(--green); color: var(--bg); }
    .cta-primary:hover { background: #00cc6a; text-decoration: none; }
    .cta-orange { background: var(--orange); color: #fff; }
    .cta-orange:hover { background: #e55a2a; text-decoration: none; }

    /* PRICING */
    .pricing-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
    @media (max-width: 900px) { .pricing-row { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 550px) { .pricing-row { grid-template-columns: 1fr; } }
    .price-box { border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem 1rem; text-align: center; position: relative; }
    .price-box.featured { border-color: var(--green); background: #0a1a12; }
    .price-box.upgrade { border-color: var(--orange); }
    .price-box .tier-name { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.3rem; }
    .price-box .tier-price { font-family: 'Space Mono', monospace; font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0; }
    .price-box .tier-price .per { font-size: 0.7rem; color: var(--muted); font-weight: 400; }
    .price-box .tier-desc { font-size: 0.75rem; color: var(--muted); margin-bottom: 0.8rem; }
    .price-box ul { list-style: none; text-align: left; font-size: 0.75rem; color: var(--muted); padding: 0 0.5rem; }
    .price-box ul li { padding: 0.25rem 0; border-bottom: 1px solid #1a1a2a; }
    .price-box ul li::before { content: '→ '; color: var(--cyan); }
    .price-box .pop-badge { position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: var(--green); color: var(--bg); padding: 3px 14px; border-radius: 20px; font-size: 0.65rem; font-weight: 700; text-transform: uppercase; }

    /* FOOTER */
    .dash-foot { text-align: center; padding: 2rem; border-top: 1px solid var(--border); margin-top: 2rem; }
    .dash-foot p { color: var(--muted); font-size: 0.78rem; }
    .dash-foot .sub { color: var(--dim); font-size: 0.68rem; margin-top: 0.3rem; }

    /* TOGGLE (for expandable channels) */
    .toggle-btn { cursor: pointer; }
    .toggle-btn:hover { background: var(--card); }
</style>"""


# ──────────────────────────────────────────────────
# COMPONENTS
# ──────────────────────────────────────────────────

def _nav(name: str, tier: str) -> str:
    bc = f"badge-{tier}" if tier in ("starter", "growth") else "badge-free"
    bl = tier.upper() if tier != "free" else "FREE"
    return f"""<nav class="nav">
    <div class="nav-logo">mckoutie <span class="amp">&amp;</span> <span class="co">company</span></div>
    <div class="nav-right">
        <span class="nav-startup">{_e(name)}</span>
        <span class="badge {bc}">{bl}</span>
    </div>
</nav>"""


def _metric_cards(top_score, top_channel, avg_score, profile, num_leads, num_investors) -> str:
    stage = _e(profile.get("stage", "—"))
    market = _e(profile.get("market", "—"))
    if len(market) > 40:
        market = market[:37] + "..."
    return f"""<div class="metrics">
    <div class="metric">
        <div class="metric-val" style="color: var(--green);">{avg_score}</div>
        <div class="metric-label">Avg Score</div>
        <div class="metric-sub">/10 across 19 channels</div>
    </div>
    <div class="metric">
        <div class="metric-val" style="color: var(--cyan);">{_e(str(top_score))}</div>
        <div class="metric-label">Top Channel</div>
        <div class="metric-sub">{_e(top_channel)}</div>
    </div>
    <div class="metric">
        <div class="metric-val" style="color: var(--orange);">{num_leads}</div>
        <div class="metric-label">Leads Found</div>
        <div class="metric-sub">Potential customers</div>
    </div>
    <div class="metric">
        <div class="metric-val" style="color: var(--purple);">{num_investors}</div>
        <div class="metric-label">Investors</div>
        <div class="metric-sub">In your space</div>
    </div>
</div>"""


def _hot_take(hot_take: str) -> str:
    if not hot_take:
        return ""
    return f"""<div class="hottake">
    <div class="hottake-label">Hot Take</div>
    <div class="hottake-text">{_e(hot_take)}</div>
</div>"""


def _bullseye_compact(bullseye: dict, channels: list) -> str:
    inner = bullseye.get("inner_ring", {})
    promising = bullseye.get("promising", {})
    long_shot = bullseye.get("long_shot", {})

    score_map = {ch.get("channel", ""): ch.get("score", 0) for ch in channels}

    def ring_items(ch_list):
        html = ""
        for ch in ch_list:
            s = score_map.get(ch, "?")
            html += f'<div class="ring-item"><span>{_e(ch)}</span><span class="ring-score">{s}/10</span></div>'
        return html

    return f"""<div class="section">
    <h2 class="section-title"><span class="accent">Bullseye</span> Framework</h2>
    <div class="bullseye-row">
        <div class="ring ring-inner">
            <div class="ring-title">Inner Ring — Test Now</div>
            {ring_items(inner.get("channels", []))}
        </div>
        <div class="ring ring-promising">
            <div class="ring-title">Promising</div>
            {ring_items(promising.get("channels", []))}
        </div>
        <div class="ring ring-long">
            <div class="ring-title">Long Shot</div>
            {ring_items(long_shot.get("channels", []))}
        </div>
    </div>
</div>"""


def _channel_scores(channels: list, tier: str) -> str:
    sorted_ch = sorted(channels, key=lambda c: c.get("score", 0), reverse=True)
    rows = ""
    for ch in sorted_ch:
        score = ch.get("score", 0)
        name = _e(ch.get("channel", ""))
        pct = score * 10
        if score >= 7:
            bar_cls, sc_cls = "ch-bar-hi", "ch-score-hi"
        elif score >= 5:
            bar_cls, sc_cls = "ch-bar-mid", "ch-score-mid"
        else:
            bar_cls, sc_cls = "ch-bar-lo", "ch-score-lo"

        detail = ""
        if tier in ("starter", "growth", "enterprise"):
            insight = _e(ch.get("killer_insight", ""))
            first_move = _e(ch.get("first_move", ""))
            effort = _e(ch.get("effort", ""))
            timeline = _e(ch.get("timeline", ""))
            budget = _e(ch.get("budget", ""))
            ideas_html = ""
            for idea in ch.get("specific_ideas", [])[:3]:
                ideas_html += f"<li>{_e(idea)}</li>"
            detail = f"""<div class="ch-detail">
                <div class="ch-insight">{insight}</div>
                <div style="font-size:0.72rem;color:var(--muted);margin-bottom:0.4rem;">Effort: {effort} · Timeline: {timeline} · Budget: {budget}</div>
                <ul class="ch-ideas">{ideas_html}</ul>
                <div class="ch-first-move"><div class="label">First Move</div>{first_move}</div>
            </div>"""

        clickable = ' toggle-btn onclick="this.classList.toggle(\'expanded\')"' if detail else ""
        rows += f"""<div class="ch-row{' ' if detail else ''}"{clickable}>
    <span class="ch-name">{name}</span>
    <div class="ch-bar-wrap"><div class="ch-bar {bar_cls}" style="width:{pct}%"></div></div>
    <span class="ch-score {sc_cls}">{score}</span>
    {detail}
</div>"""

    lock_note = ""
    if tier == "free":
        lock_note = '<div style="text-align:center;padding:0.8rem;font-size:0.8rem;color:var(--muted);">Click channels to see strategy details — <a href="#pricing">unlock with Starter plan</a></div>'

    return f"""<div class="section">
    <h2 class="section-title"><span class="accent">Channel</span> Scores <span class="count">{len(channels)} channels</span></h2>
    <div class="ch-list">{rows}</div>
    {lock_note}
</div>"""


def _leads_section(leads_data: dict, tier: str, checkout_url: str) -> str:
    leads = leads_data.get("leads", [])
    personas = leads_data.get("personas", [])

    if not leads and not personas:
        return f"""<div class="section">
    <h2 class="section-title">🎯 <span class="accent">Potential Leads</span></h2>
    <p style="color:var(--muted);text-align:center;padding:1rem;">Lead research in progress or not yet available.</p>
</div>"""

    # Always show leads (even on free tier — this is the hook)
    leads_html = ""
    for i, lead in enumerate(leads):
        name = _e(lead.get("name", f"Lead {i+1}"))
        url = lead.get("url", "")
        desc = _e(lead.get("relevance", lead.get("description", "")))
        source = _e(lead.get("source", ""))
        score = lead.get("score", lead.get("relevance_score", 0))
        platform = _e(lead.get("platform", ""))

        if isinstance(score, str):
            try:
                score = int(score)
            except (ValueError, TypeError):
                score = 5

        sc_cls = "lead-score-hi" if score >= 8 else ("lead-score-mid" if score >= 5 else "lead-score-lo")
        plat_cls = f"plat-{platform.lower()}" if platform.lower() in ("twitter", "reddit", "linkedin", "discord", "github", "substack") else "plat-web"

        name_html = f'<a href="{_e(url)}" target="_blank">{name}</a>' if url else name

        # On free tier, show lead but lock the outreach strategy
        lock_html = ""
        if tier == "free":
            lock_html = '<div class="lead-lock">🔒 Outreach strategy → $39/mo</div>'

        leads_html += f"""<div class="lead-card">
    <div class="lead-info">
        <div class="lead-name">{name_html}</div>
        <div class="lead-desc">{desc[:120]}{'...' if len(desc) > 120 else ''}</div>
        <div class="lead-source"><span class="plat {plat_cls}">{platform or source}</span></div>
    </div>
    <div class="lead-right">
        <div class="lead-score-badge {sc_cls}">{score}/10</div>
        {lock_html}
    </div>
</div>"""

    # Personas (shown on starter+, teaser on free)
    personas_html = ""
    if personas:
        if tier in ("starter", "growth", "enterprise"):
            for p in personas:
                pname = _e(p.get("name", ""))
                who = _e(p.get("description", p.get("who", "")))
                nets_html = ""
                for net in p.get("platforms", p.get("social_networks", [])):
                    n = _e(net) if isinstance(net, str) else _e(net.get("name", ""))
                    nc = f"plat-{n.lower()}" if n.lower() in ("twitter", "reddit", "linkedin", "discord") else "plat-web"
                    nets_html += f'<span class="plat {nc}">{n}</span> '
                signals_html = ""
                for sig in p.get("pain_signals", [])[:3]:
                    signals_html += f'<div class="persona-signals">"{_e(sig)}"</div>'
                personas_html += f"""<div class="persona">
    <h4>{pname}</h4>
    <div class="who">{who}</div>
    <div class="persona-nets">{nets_html}</div>
    {signals_html}
</div>"""
        else:
            personas_html = f"""<div class="locked">
    <div class="locked-blur">
        <div class="persona"><h4>Customer Persona 1</h4><div class="who">Detailed description of your ideal customer with pain points and behavior patterns...</div></div>
        <div class="persona"><h4>Customer Persona 2</h4><div class="who">Another key segment with different motivations and channels...</div></div>
    </div>
    <div class="locked-cta">
        <div class="lock-icon">🔒</div>
        <div class="lock-text">3 detailed personas with pain signals & platforms</div>
        <a class="cta-btn cta-primary" href="{_e(checkout_url)}">Unlock — $39/mo</a>
    </div>
</div>"""

    return f"""<div class="section" id="leads">
    <h2 class="section-title">🎯 <span class="accent">Potential Leads</span> <span class="count">{len(leads)} found</span></h2>
    {leads_html}
    {f'<h3 style="font-family:EB Garamond,serif;font-size:1.1rem;margin:1.5rem 0 0.8rem;padding-top:1rem;border-top:1px solid var(--border);">Customer Personas</h3>' + personas_html if personas else ''}
</div>"""


def _investors_section(investors_data: dict, tier: str, upgrade_url: str) -> str:
    competitors = investors_data.get("competitors", [])
    comp_investors = investors_data.get("competitor_investors", [])
    market_investors = investors_data.get("market_investors", [])

    all_investors = comp_investors + market_investors
    if not competitors and not all_investors:
        return f"""<div class="section" id="investors">
    <h2 class="section-title">💰 <span class="accent">Investors</span></h2>
    <p style="color:var(--muted);text-align:center;padding:1rem;">Investor research in progress or not yet available.</p>
</div>"""

    # Competitors — always show
    comp_html = ""
    if competitors:
        comp_html += '<h3 style="font-size:0.9rem;color:var(--muted);margin-bottom:0.6rem;">Competitors & Their Funding</h3>'
        for c in competitors:
            cname = _e(c.get("name", ""))
            curl = c.get("url", "")
            cdesc = _e(c.get("description", ""))
            cfund = _e(c.get("funding", c.get("funding_amount", "")))
            cinvs = c.get("investors", [])
            name_html = f'<a href="{_e(curl)}" target="_blank">{cname}</a>' if curl else cname
            tags = "".join(f'<span class="inv-tag">{_e(inv)}</span>' for inv in cinvs[:4])
            comp_html += f"""<div class="comp-card">
    <div class="comp-info">
        <h4>{name_html}</h4>
        <div class="comp-desc">{cdesc[:100]}</div>
        <div class="comp-inv-tags">{tags}</div>
    </div>
    {f'<div class="fund-badge">{cfund}</div>' if cfund else ''}
</div>"""

    # Investors — show names free, details on growth
    inv_html = ""
    if all_investors:
        inv_html += '<h3 style="font-size:0.9rem;color:var(--muted);margin:1rem 0 0.6rem;padding-top:0.8rem;border-top:1px solid var(--border);">Investors in This Space</h3>'
        for inv in all_investors:
            iname = _e(inv.get("name", ""))
            iurl = inv.get("url", inv.get("linkedin", ""))
            ifocus = _e(inv.get("focus", inv.get("relevance_signal", "")))
            itype = inv.get("type", "").lower()

            type_cls = "inv-vc" if "vc" in itype else ("inv-angel" if "angel" in itype else "inv-other")
            type_label = _e(inv.get("type", "Investor"))
            name_html = f'<a href="{_e(iurl)}" target="_blank">{iname}</a>' if iurl else iname

            lock_html = ""
            if tier not in ("growth", "enterprise"):
                lock_html = '<div style="font-size:0.68rem;color:var(--cyan);margin-top:0.15rem;">🔒 Full profile → $200/mo</div>'

            inv_html += f"""<div class="inv-card">
    <div class="inv-info">
        <div class="inv-name">{name_html}</div>
        <div class="inv-focus">{ifocus[:100]}</div>
        {lock_html}
    </div>
    <span class="inv-type {type_cls}">{type_label}</span>
</div>"""

    return f"""<div class="section" id="investors">
    <h2 class="section-title">💰 <span class="accent">Investors</span> <span class="count">{len(all_investors)} found</span></h2>
    {comp_html}
    {inv_html}
</div>"""


def _plan_section(plan: dict, tier: str, checkout_url: str) -> str:
    if tier == "free":
        return f"""<div class="section locked" id="plan">
    <div class="locked-blur">
        <h2 class="section-title">📋 <span class="accent">90-Day</span> Action Plan</h2>
        <div class="plan-grid">
            <div class="month"><h3>Month 1</h3><div class="focus">Build foundation + test top channels</div><ul><li>Action item 1...</li><li>Action item 2...</li></ul></div>
            <div class="month"><h3>Month 2</h3><div class="focus">Scale what works, cut what doesn't</div><ul><li>Action item 1...</li><li>Action item 2...</li></ul></div>
            <div class="month"><h3>Month 3</h3><div class="focus">Double down + optimize</div><ul><li>Action item 1...</li><li>Action item 2...</li></ul></div>
        </div>
    </div>
    <div class="locked-cta">
        <div class="lock-icon">📋</div>
        <div class="lock-text">Full 90-day plan with weekly milestones</div>
        <a class="cta-btn cta-primary" href="{_e(checkout_url)}">Unlock — $39/mo</a>
    </div>
</div>"""

    months_html = ""
    for key in ["month_1", "month_2", "month_3"]:
        m = plan.get(key, {})
        label = key.replace("_", " ").title()
        focus = _e(m.get("focus", ""))
        target = _e(m.get("target_metric", ""))
        bgt = _e(m.get("budget", ""))
        actions = "".join(f"<li>{_e(a)}</li>" for a in m.get("actions", []))
        months_html += f"""<div class="month">
    <h3>{label}</h3>
    <div class="focus">{focus}</div>
    {f'<div class="target">Target: {target}</div>' if target else ''}
    {f'<div class="budget-amt">Budget: {bgt}</div>' if bgt else ''}
    <ul>{actions}</ul>
</div>"""

    return f"""<div class="section" id="plan">
    <h2 class="section-title">📋 <span class="accent">90-Day</span> Action Plan</h2>
    <div class="plan-grid">{months_html}</div>
</div>"""


def _budget_section(budget: dict, tier: str, checkout_url: str) -> str:
    if tier == "free":
        return ""  # Don't show at all on free, keep it clean

    total = _e(budget.get("total_recommended", ""))
    rows = ""
    for item in budget.get("breakdown", []):
        rows += f"""<tr>
    <td>{_e(item.get('channel', ''))}</td>
    <td style="color:var(--green);font-family:'Space Mono',monospace;">{_e(item.get('amount', ''))}</td>
    <td>{_e(item.get('rationale', ''))}</td>
</tr>"""

    return f"""<div class="section">
    <h2 class="section-title">💵 <span class="accent">Budget</span> Allocation</h2>
    <table class="budget-tbl">
        <tr><th>Channel</th><th>Amount</th><th>Rationale</th></tr>
        {rows}
    </table>
    {f'<div class="budget-total">Total Recommended: {total}</div>' if total else ''}
</div>"""


def _risk_section(risks: list, tier: str, checkout_url: str) -> str:
    if tier == "free":
        return ""

    rows = ""
    for r in risks:
        prob = r.get("probability", "")
        pc = "prob-hi" if prob == "high" else ("prob-med" if prob == "medium" else "prob-lo")
        imp = r.get("impact", "")
        ic = "prob-hi" if imp == "high" else ("prob-med" if imp == "medium" else "prob-lo")
        rows += f"""<tr>
    <td>{_e(r.get('risk', ''))}</td>
    <td class="{pc}">{_e(prob)}</td>
    <td class="{ic}">{_e(imp)}</td>
    <td>{_e(r.get('mitigation', ''))}</td>
</tr>"""

    return f"""<div class="section">
    <h2 class="section-title">⚠️ <span class="accent">Risk</span> Matrix</h2>
    <table class="risk-tbl">
        <tr><th>Risk</th><th>Prob</th><th>Impact</th><th>Mitigation</th></tr>
        {rows}
    </table>
</div>"""


def _moat_section(moat: str, tier: str, checkout_url: str) -> str:
    if tier == "free" or not moat:
        return ""
    return f"""<div class="section">
    <h2 class="section-title">🏰 <span class="accent">Competitive</span> Moat</h2>
    <div class="moat-text">{_e(moat)}</div>
</div>"""


def _pricing_section(report_id: str, tier: str, checkout_url: str, upgrade_url: str) -> str:
    return f"""<div class="section" id="pricing">
    <h2 class="section-title" style="text-align:center;justify-content:center;"><span class="accent">Choose</span> Your Plan</h2>
    <div class="pricing-row">
        <div class="price-box{' featured' if tier == 'free' else ''}">
            <div class="tier-name">Free</div>
            <div class="tier-price">$0</div>
            <div class="tier-desc">See what we found</div>
            <ul>
                <li>Top 3 channels + scores</li>
                <li>Hot take</li>
                <li>10 potential leads (names)</li>
                <li>10 investors (names)</li>
                <li>Competitor funding data</li>
            </ul>
        </div>
        <div class="price-box{' featured' if tier == 'starter' else ''}">
            {'<div class="pop-badge">Most Popular</div>' if tier != 'starter' else ''}
            <div class="tier-name">Starter</div>
            <div class="tier-price">$39<span class="per">/mo</span></div>
            <div class="tier-desc">Full strategy playbook</div>
            <ul>
                <li>Everything in Free</li>
                <li>19 channel deep analysis</li>
                <li>90-day action plan</li>
                <li>Budget allocation</li>
                <li>Risk matrix</li>
                <li>3 customer personas</li>
                <li>Lead outreach strategies</li>
                <li>Monthly market updates</li>
            </ul>
            {f'<a class="cta-btn cta-primary" href="{_e(checkout_url)}" style="margin-top:0.8rem;">Get Started</a>' if tier == 'free' else ''}
        </div>
        <div class="price-box{' featured' if tier == 'growth' else ''} upgrade">
            <div class="tier-name">Growth</div>
            <div class="tier-price">$200<span class="per">/mo</span></div>
            <div class="tier-desc">Full intelligence suite</div>
            <ul>
                <li>Everything in Starter</li>
                <li>Investor deep profiles</li>
                <li>Competitor deep analysis</li>
                <li>Weekly market updates</li>
                <li>Custom outreach templates</li>
            </ul>
            {f'<a class="cta-btn cta-orange" href="{_e(upgrade_url)}" style="margin-top:0.8rem;">Upgrade</a>' if tier in ('free', 'starter') else ''}
        </div>
        <div class="price-box">
            <div class="tier-name">Enterprise</div>
            <div class="tier-price">Custom</div>
            <div class="tier-desc">White-glove service</div>
            <ul>
                <li>Everything in Growth</li>
                <li>Custom analysis scope</li>
                <li>Direct strategy calls</li>
                <li>Multi-product analysis</li>
            </ul>
            <a class="cta-btn" href="mailto:emi@mckoutie.com" style="margin-top:0.8rem;border:1px solid var(--border);color:var(--muted);">Contact Us</a>
        </div>
    </div>
</div>"""
