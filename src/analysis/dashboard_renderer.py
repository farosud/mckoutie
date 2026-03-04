"""
Dashboard renderer — generates a rich, interactive report dashboard from analysis JSON.

Three views:
  1. PAYWALL (free)   — teaser with blurred sections + tier pricing
  2. STARTER ($39/mo) — full traction analysis, 90-day plan, risk matrix
  3. GROWTH ($200/mo) — everything in starter + leads + investors

All server-rendered HTML. No frontend framework needed.
"""

import json
import logging
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
    """
    Render the full dashboard HTML based on the user's tier.

    tier: "free" | "starter" | "growth" | "enterprise"
    """
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

    # Compute quick stats for summary
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
    num_personas = len(leads_data.get("personas", []))
    num_investors = len(investors_data.get("market_investors", [])) + len(investors_data.get("competitor_investors", []))
    num_competitors = len(investors_data.get("competitors", []))

    # Build sections
    nav_html = _render_nav(startup_name, tier)
    section_nav_html = _render_section_nav(tier)
    hero_html = _render_hero(profile, exec_summary, tier)
    stats_html = _render_quick_stats(
        top_score, top_channel, avg_score, len(channels),
        num_leads, num_investors, profile.get("stage", ""), tier
    )
    bullseye_html = _render_bullseye(bullseye, channels, tier)
    channels_html = _render_channels(channels, tier)
    plan_html = _render_plan(plan, tier)
    budget_html = _render_budget(budget, tier)
    risk_html = _render_risks(risks, tier)
    moat_html = _render_moat(moat, tier)
    hottake_html = _render_hottake(hot_take, tier)
    leads_html = _render_leads(leads_data, tier)
    investors_html = _render_investors(investors_data, tier)
    updates_html = _render_updates(tier)
    pricing_html = _render_pricing(
        report_id, tier, checkout_url, upgrade_url
    )

    # Living report indicator
    from datetime import datetime, timezone
    now_str = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    living_badge = ""
    if tier in ("starter", "growth", "enterprise"):
        living_badge = f"""
        <div class="living-badge">
            <span class="pulse"></span>
            <span>Living Report — Last updated {now_str}</span>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mckoutie — {startup_name} Strategy Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,700;1,400&family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    {_dashboard_css()}
</head>
<body>
    {nav_html}
    {section_nav_html}
    <main class="dashboard">
        {living_badge}
        {hero_html}
        {stats_html}
        <div class="dashboard-grid">
            <div class="main-content">
                {hottake_html}
                <div id="channels">
                    {bullseye_html}
                    {channels_html}
                </div>
                <div id="plan">
                    {plan_html}
                    {budget_html}
                    {risk_html}
                    {moat_html}
                </div>
                <div id="leads">
                    {leads_html}
                </div>
                <div id="investors">
                    {investors_html}
                </div>
                <div id="updates">
                    {updates_html}
                </div>
            </div>
            <div class="sidebar">
                {pricing_html}
            </div>
        </div>
    </main>
    <footer class="dash-footer">
        <p>mckoutie &amp; company — McKinsey at home</p>
        <p class="muted">AI-generated analysis. Use as a starting point, not gospel. Not affiliated with McKinsey.</p>
    </footer>
    <script>
    // Smooth scroll for section nav
    document.querySelectorAll('.section-nav a').forEach(a => {{
        a.addEventListener('click', e => {{
            e.preventDefault();
            const target = document.querySelector(a.getAttribute('href'));
            if (target) {{
                target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                // Update active state
                document.querySelectorAll('.section-nav a').forEach(x => x.classList.remove('active'));
                a.classList.add('active');
            }}
        }});
    }});
    // Highlight active section on scroll
    const sections = ['channels', 'plan', 'leads', 'investors', 'updates'];
    window.addEventListener('scroll', () => {{
        const scrollY = window.scrollY + 120;
        for (const id of sections.reverse()) {{
            const el = document.getElementById(id);
            if (el && el.offsetTop <= scrollY) {{
                document.querySelectorAll('.section-nav a').forEach(a => {{
                    a.classList.toggle('active', a.getAttribute('href') === '#' + id);
                }});
                break;
            }}
        }}
        sections.reverse();
    }});
    </script>
</body>
</html>"""


def _dashboard_css() -> str:
    return """<style>
    :root {
        --bg: #0a0e1a;
        --bg2: #0f1423;
        --card: #141a2e;
        --card-hover: #1a2240;
        --border: #1e2744;
        --border-light: #2a3456;
        --text: #e0ddd5;
        --text-muted: #7a8094;
        --cyan: #00d4ff;
        --green: #00ff88;
        --orange: #ff6b35;
        --red: #ff4757;
        --yellow: #ffd32a;
        --purple: #a855f7;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Space Grotesk', -apple-system, sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.6;
    }

    /* NAV */
    .dash-nav {
        display: flex; justify-content: space-between; align-items: center;
        padding: 1rem 2rem;
        border-bottom: 1px solid var(--border);
        background: var(--bg2);
        position: sticky; top: 0; z-index: 100;
    }
    .dash-nav .logo {
        font-family: 'EB Garamond', serif;
        font-size: 1.3rem;
        color: var(--cyan);
    }
    .dash-nav .logo span { color: var(--text-muted); font-size: 0.8rem; }
    .dash-nav .tier-badge {
        padding: 4px 12px;
        border-radius: 4px;
        font-family: 'Space Mono', monospace;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .tier-free { background: var(--border); color: var(--text-muted); }
    .tier-starter { background: #0a3d2a; color: var(--green); border: 1px solid var(--green); }
    .tier-growth { background: #3d2a0a; color: var(--orange); border: 1px solid var(--orange); }
    .tier-enterprise { background: #2a0a3d; color: var(--purple); border: 1px solid var(--purple); }

    /* MAIN */
    .dashboard { max-width: 1400px; margin: 0 auto; padding: 2rem; }
    .dashboard-grid {
        display: grid;
        grid-template-columns: 1fr 380px;
        gap: 2rem;
        margin-top: 2rem;
    }
    @media (max-width: 1024px) {
        .dashboard-grid { grid-template-columns: 1fr; }
        .sidebar { order: -1; }
    }

    /* HERO */
    .hero-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    .hero-card h1 {
        font-family: 'EB Garamond', serif;
        font-size: 2rem;
        color: var(--cyan);
        margin-bottom: 0.25rem;
    }
    .hero-card .one-liner {
        color: var(--text-muted);
        font-size: 1.1rem;
        margin-bottom: 1.5rem;
    }
    .hero-meta {
        display: flex; flex-wrap: wrap; gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .meta-tag {
        background: var(--bg);
        border: 1px solid var(--border);
        padding: 6px 14px;
        border-radius: 6px;
        font-size: 0.85rem;
    }
    .meta-tag .label { color: var(--text-muted); }
    .meta-tag .value { color: var(--cyan); font-weight: 600; }
    .exec-summary {
        border-top: 1px solid var(--border);
        padding-top: 1.5rem;
        color: var(--text);
        line-height: 1.8;
    }
    .strengths-weaknesses {
        display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
        margin-top: 1.5rem;
    }
    .sw-list h3 { font-size: 0.9rem; margin-bottom: 0.5rem; }
    .sw-list h3.strength { color: var(--green); }
    .sw-list h3.weakness { color: var(--orange); }
    .sw-list li { font-size: 0.85rem; color: var(--text-muted); margin-left: 1.2rem; margin-bottom: 0.3rem; }

    /* CARDS */
    .section-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .section-card h2 {
        font-family: 'EB Garamond', serif;
        font-size: 1.4rem;
        color: var(--text);
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
    }
    .section-card h2 .accent { color: var(--cyan); }

    /* BULLSEYE */
    .bullseye-rings {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;
    }
    @media (max-width: 768px) { .bullseye-rings { grid-template-columns: 1fr; } }
    .ring {
        background: var(--bg);
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
    }
    .ring-inner { border: 2px solid var(--green); }
    .ring-promising { border: 2px solid var(--yellow); }
    .ring-longshot { border: 2px solid var(--text-muted); }
    .ring h3 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.8rem; }
    .ring-inner h3 { color: var(--green); }
    .ring-promising h3 { color: var(--yellow); }
    .ring-longshot h3 { color: var(--text-muted); }
    .ring-channel {
        display: flex; justify-content: space-between; align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid var(--border);
        font-size: 0.85rem;
    }
    .ring-channel:last-child { border-bottom: none; }
    .ring-channel .score { font-family: 'Space Mono', monospace; font-weight: 700; }
    .ring-inner .score { color: var(--green); }
    .ring-promising .score { color: var(--yellow); }

    /* CHANNEL CARDS */
    .channel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
    .channel-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.2rem;
        transition: border-color 0.2s;
    }
    .channel-card:hover { border-color: var(--border-light); }
    .channel-header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 0.8rem;
    }
    .channel-name { font-weight: 600; font-size: 0.95rem; }
    .channel-score {
        font-family: 'Space Mono', monospace;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .score-high { color: var(--green); }
    .score-mid { color: var(--yellow); }
    .score-low { color: var(--text-muted); }
    .channel-meta {
        display: flex; gap: 0.8rem;
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-bottom: 0.8rem;
    }
    .channel-insight {
        font-size: 0.85rem;
        color: var(--text-muted);
        border-left: 3px solid var(--cyan);
        padding-left: 0.8rem;
        margin-bottom: 0.8rem;
    }
    .channel-ideas {
        font-size: 0.8rem;
        color: var(--text-muted);
    }
    .channel-ideas li {
        margin-left: 1rem;
        margin-bottom: 0.2rem;
    }
    .channel-first-move {
        margin-top: 0.8rem;
        padding: 0.6rem;
        background: var(--card);
        border-radius: 6px;
        font-size: 0.8rem;
    }
    .channel-first-move .label { color: var(--green); font-weight: 600; font-size: 0.7rem; text-transform: uppercase; }

    /* 90-DAY PLAN */
    .plan-months { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
    @media (max-width: 768px) { .plan-months { grid-template-columns: 1fr; } }
    .month-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.2rem;
    }
    .month-card h3 {
        color: var(--cyan);
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }
    .month-card .focus {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .month-card .metric {
        font-size: 0.8rem;
        color: var(--green);
        margin-bottom: 0.5rem;
    }
    .month-card li {
        font-size: 0.8rem;
        color: var(--text-muted);
        margin-left: 1rem;
        margin-bottom: 0.3rem;
    }

    /* BUDGET TABLE */
    .budget-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .budget-table th {
        text-align: left;
        color: var(--cyan);
        font-weight: 600;
        padding: 8px 12px;
        border-bottom: 2px solid var(--border);
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .budget-table td {
        padding: 8px 12px;
        border-bottom: 1px solid var(--border);
        color: var(--text-muted);
    }
    .budget-table tr:hover td { background: var(--bg); }
    .budget-total {
        text-align: center;
        padding: 1rem;
        font-size: 1.1rem;
        color: var(--green);
        font-weight: 600;
    }

    /* RISK MATRIX */
    .risk-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .risk-table th {
        text-align: left;
        color: var(--orange);
        font-weight: 600;
        padding: 8px 12px;
        border-bottom: 2px solid var(--border);
        font-size: 0.75rem;
        text-transform: uppercase;
    }
    .risk-table td {
        padding: 8px 12px;
        border-bottom: 1px solid var(--border);
        color: var(--text-muted);
    }
    .risk-table tr:hover td { background: var(--bg); }

    /* MOAT + HOT TAKE */
    .moat-text { color: var(--text-muted); line-height: 1.8; }
    .hottake-box {
        background: linear-gradient(135deg, #1a0a0a 0%, #0a1a1a 100%);
        border: 2px solid var(--orange);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
    }
    .hottake-box .label {
        color: var(--orange);
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 0.5rem;
    }
    .hottake-box .take {
        font-family: 'EB Garamond', serif;
        font-size: 1.3rem;
        font-style: italic;
        color: var(--text);
        line-height: 1.6;
    }

    /* SIDEBAR CARDS */
    .sidebar .section-card { margin-bottom: 1.5rem; }

    /* LEADS */
    .persona-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }
    .persona-card h4 { color: var(--cyan); font-size: 0.95rem; margin-bottom: 0.3rem; }
    .persona-card .who { color: var(--text-muted); font-size: 0.8rem; margin-bottom: 0.5rem; }
    .persona-networks {
        display: flex; flex-wrap: wrap; gap: 4px;
        margin-bottom: 0.5rem;
    }
    .network-tag {
        background: var(--card);
        border: 1px solid var(--border);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        color: var(--text-muted);
    }
    .persona-signals { font-size: 0.75rem; color: var(--text-muted); font-style: italic; }

    .lead-item {
        display: flex; justify-content: space-between; align-items: flex-start;
        padding: 0.6rem 0;
        border-bottom: 1px solid var(--border);
        font-size: 0.8rem;
    }
    .lead-item:last-child { border-bottom: none; }
    .lead-name { color: var(--text); font-weight: 500; }
    .lead-name a { color: var(--cyan); text-decoration: none; }
    .lead-name a:hover { text-decoration: underline; }
    .lead-source {
        font-size: 0.7rem;
        color: var(--text-muted);
    }
    .lead-score {
        font-family: 'Space Mono', monospace;
        font-weight: 700;
        font-size: 0.85rem;
    }

    /* INVESTORS */
    .competitor-item {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.6rem;
    }
    .competitor-item h4 { font-size: 0.85rem; color: var(--text); margin-bottom: 0.2rem; }
    .competitor-item .funding { color: var(--green); font-family: 'Space Mono', monospace; font-size: 0.8rem; }
    .competitor-item .investors-list { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.3rem; }
    .investor-item {
        display: flex; justify-content: space-between; align-items: flex-start;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border);
        font-size: 0.8rem;
    }
    .investor-item:last-child { border-bottom: none; }
    .investor-name a { color: var(--cyan); text-decoration: none; }
    .investor-name a:hover { text-decoration: underline; }
    .investor-type {
        font-size: 0.7rem;
        padding: 2px 6px;
        border-radius: 3px;
        background: var(--bg);
        color: var(--text-muted);
    }

    /* PRICING */
    .pricing-cards { display: flex; flex-direction: column; gap: 0.8rem; }
    .price-card {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        transition: border-color 0.2s;
    }
    .price-card:hover { border-color: var(--border-light); }
    .price-card.active { border-color: var(--green); background: #0a1a12; }
    .price-card.recommended { border-color: var(--orange); }
    .price-card h4 { font-size: 0.9rem; margin-bottom: 0.3rem; }
    .price-card .price {
        font-family: 'Space Mono', monospace;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0.3rem 0;
    }
    .price-card .price .period { font-size: 0.7rem; color: var(--text-muted); font-weight: 400; }
    .price-card .features { font-size: 0.75rem; color: var(--text-muted); text-align: left; padding: 0.5rem 0; }
    .price-card .features li { margin-left: 1rem; margin-bottom: 0.2rem; }
    .price-card .features li.locked { color: #444; text-decoration: line-through; }
    .price-btn {
        display: inline-block;
        padding: 10px 24px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        text-decoration: none;
        margin-top: 0.5rem;
        font-family: 'Space Grotesk', sans-serif;
    }
    .price-btn-primary { background: var(--green); color: var(--bg); }
    .price-btn-primary:hover { background: #00cc6a; }
    .price-btn-secondary { background: var(--orange); color: #fff; }
    .price-btn-secondary:hover { background: #e55a2a; }
    .price-btn-outline {
        background: transparent;
        color: var(--text-muted);
        border: 1px solid var(--border);
    }
    .price-btn-outline:hover { border-color: var(--text-muted); }

    /* SCORE BAR */
    .score-bar-wrap {
        width: 100%;
        height: 6px;
        background: var(--border);
        border-radius: 3px;
        margin: 6px 0 10px;
        overflow: hidden;
    }
    .score-bar {
        height: 100%;
        border-radius: 3px;
        transition: width 0.6s ease;
    }
    .score-bar-green { background: var(--green); }
    .score-bar-yellow { background: var(--yellow); }
    .score-bar-red { background: var(--orange); }

    /* PLATFORM BADGES */
    .platform-twitter { background: #1c2733; color: #1da1f2; border: 1px solid #1da1f233; }
    .platform-reddit { background: #2a1500; color: #ff4500; border: 1px solid #ff450033; }
    .platform-linkedin { background: #00152a; color: #0a66c2; border: 1px solid #0a66c233; }
    .platform-discord { background: #1a1440; color: #5865f2; border: 1px solid #5865f233; }
    .platform-telegram { background: #0a1e2a; color: #0088cc; border: 1px solid #0088cc33; }
    .platform-youtube { background: #2a0a0a; color: #ff0000; border: 1px solid #ff000033; }
    .platform-instagram { background: #2a0a1e; color: #e4405f; border: 1px solid #e4405f33; }
    .platform-tiktok { background: #0a0a0a; color: #ee1d52; border: 1px solid #ee1d5233; }
    .platform-facebook { background: #0a1333; color: #1877f2; border: 1px solid #1877f233; }
    .platform-substack { background: #2a1500; color: #ff6719; border: 1px solid #ff671933; }
    .platform-hn { background: #1a1000; color: #ff6600; border: 1px solid #ff660033; }
    .platform-default { background: var(--card); color: var(--text-muted); border: 1px solid var(--border); }

    /* PERSONA ENHANCED */
    .persona-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s;
    }
    .persona-card:hover { border-color: var(--border-light); }
    .persona-card h4 { color: var(--cyan); font-size: 1rem; margin-bottom: 0.3rem; }
    .persona-card .who { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem; line-height: 1.5; }
    .persona-meta-row {
        display: flex; flex-wrap: wrap; gap: 0.6rem;
        margin-bottom: 0.6rem;
        font-size: 0.75rem;
    }
    .persona-meta-item {
        background: var(--card);
        border: 1px solid var(--border);
        padding: 3px 10px;
        border-radius: 4px;
        color: var(--text-muted);
    }
    .persona-meta-item .pm-label { color: #555; }
    .persona-meta-item .pm-value { color: var(--cyan); font-weight: 600; }
    .persona-signals-list {
        margin-top: 0.5rem;
        border-top: 1px solid var(--border);
        padding-top: 0.5rem;
    }
    .persona-signal-item {
        font-size: 0.78rem;
        color: var(--text-muted);
        font-style: italic;
        padding: 3px 0;
        border-left: 2px solid var(--border);
        padding-left: 8px;
        margin-bottom: 3px;
    }
    .persona-triggers {
        margin-top: 0.5rem;
        font-size: 0.75rem;
    }
    .persona-triggers .trigger-label {
        color: var(--orange);
        font-weight: 600;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 3px;
    }
    .persona-triggers li { color: var(--text-muted); margin-left: 1rem; margin-bottom: 2px; }

    /* INVESTOR ENHANCED */
    .competitor-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        transition: border-color 0.2s;
    }
    .competitor-card:hover { border-color: var(--border-light); }
    .competitor-info h4 { font-size: 0.9rem; color: var(--text); margin-bottom: 0.2rem; }
    .competitor-info h4 a { color: var(--cyan); text-decoration: none; }
    .competitor-info h4 a:hover { text-decoration: underline; }
    .competitor-desc { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.4rem; }
    .competitor-investors-tags { display: flex; flex-wrap: wrap; gap: 4px; }
    .investor-tag {
        background: var(--card);
        border: 1px solid var(--border);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.68rem;
        color: var(--text-muted);
    }
    .funding-badge {
        font-family: 'Space Mono', monospace;
        font-weight: 700;
        font-size: 0.9rem;
        color: var(--green);
        white-space: nowrap;
        padding: 4px 10px;
        background: #0a1a12;
        border: 1px solid #1a3a2a;
        border-radius: 6px;
    }

    .investor-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.6rem;
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        transition: border-color 0.2s;
    }
    .investor-card:hover { border-color: var(--border-light); }
    .investor-card .inv-name a { color: var(--cyan); text-decoration: none; font-weight: 500; font-size: 0.88rem; }
    .investor-card .inv-name a:hover { text-decoration: underline; }
    .investor-card .inv-signal { font-size: 0.73rem; color: var(--text-muted); margin-top: 2px; }
    .inv-type-badge {
        font-size: 0.68rem;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        white-space: nowrap;
    }
    .inv-type-vc { background: #1a0a33; color: var(--purple); border: 1px solid var(--purple); }
    .inv-type-angel { background: #1a2a0a; color: var(--green); border: 1px solid var(--green); }
    .inv-type-default { background: var(--card); color: var(--text-muted); border: 1px solid var(--border); }

    /* RADAR CHART */
    .radar-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 1rem 0;
    }
    .radar-container svg text {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 9px;
        fill: var(--text-muted);
    }

    /* LOCKED OVERLAY */
    .locked-section {
        position: relative;
    }
    .locked-section .locked-content {
        filter: blur(6px);
        user-select: none;
        pointer-events: none;
    }
    .locked-overlay {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: var(--card);
        border: 2px solid var(--border);
        border-radius: 10px;
        padding: 1.5rem 2rem;
        text-align: center;
        z-index: 10;
    }
    .locked-overlay .lock-icon { font-size: 2rem; margin-bottom: 0.5rem; }
    .locked-overlay .lock-text { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.8rem; }

    /* SECTION NAV */
    .section-nav {
        display: flex;
        gap: 0;
        background: var(--bg2);
        border-bottom: 1px solid var(--border);
        padding: 0 2rem;
        position: sticky;
        top: 54px;
        z-index: 99;
        overflow-x: auto;
    }
    .section-nav a {
        padding: 10px 18px;
        color: var(--text-muted);
        text-decoration: none;
        font-size: 0.8rem;
        font-weight: 500;
        border-bottom: 2px solid transparent;
        white-space: nowrap;
        transition: all 0.2s;
    }
    .section-nav a:hover { color: var(--text); border-bottom-color: var(--border-light); }
    .section-nav a.active { color: var(--cyan); border-bottom-color: var(--cyan); }
    .section-nav .nav-locked {
        color: #333;
        cursor: default;
    }
    .section-nav .nav-locked:hover { color: #333; border-bottom-color: transparent; }

    /* QUICK STATS */
    .quick-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 0.8rem;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .stat-card .stat-value {
        font-family: 'Space Mono', monospace;
        font-size: 1.6rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .stat-card .stat-label {
        font-size: 0.7rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 0.3rem;
    }
    .stat-card .stat-sub {
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 0.2rem;
    }

    /* UPDATES SECTION */
    .update-item {
        display: flex;
        gap: 1rem;
        padding: 0.8rem 0;
        border-bottom: 1px solid var(--border);
    }
    .update-item:last-child { border-bottom: none; }
    .update-date {
        font-family: 'Space Mono', monospace;
        font-size: 0.75rem;
        color: var(--cyan);
        min-width: 80px;
    }
    .update-content {
        font-size: 0.85rem;
        color: var(--text-muted);
    }

    /* LIVING BADGE */
    .living-badge {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        background: #0a1a12;
        border: 1px solid #1a3a2a;
        border-radius: 6px;
        font-size: 0.8rem;
        color: var(--green);
        margin-bottom: 1.5rem;
    }
    .pulse {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--green);
        animation: pulse-anim 2s ease-in-out infinite;
    }
    @keyframes pulse-anim {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }

    /* FOOTER */
    .dash-footer {
        text-align: center;
        padding: 2rem;
        border-top: 1px solid var(--border);
        margin-top: 2rem;
    }
    .dash-footer p { color: var(--text-muted); font-size: 0.8rem; }
    .dash-footer .muted { color: #444; font-size: 0.7rem; margin-top: 0.3rem; }
</style>"""


def _render_nav(startup_name: str, tier: str) -> str:
    tier_class = f"tier-{tier}" if tier in ("starter", "growth", "enterprise") else "tier-free"
    tier_label = tier.upper() if tier != "free" else "FREE PREVIEW"
    return f"""
    <nav class="dash-nav">
        <div class="logo">mckoutie <span>&amp; company</span></div>
        <div>
            <span style="color: var(--text-muted); font-size: 0.85rem; margin-right: 1rem;">{startup_name}</span>
            <span class="tier-badge {tier_class}">{tier_label}</span>
        </div>
    </nav>"""


def _render_section_nav(tier: str) -> str:
    """Sticky section navigation bar with anchor links."""
    leads_class = "" if tier != "free" else "nav-locked"
    investors_class = "" if tier in ("growth", "enterprise") else "nav-locked"
    leads_label = "Leads" if tier != "free" else "Leads &#128274;"
    investors_label = "Investors" if tier in ("growth", "enterprise") else "Investors &#128274;"

    return f"""
    <div class="section-nav">
        <a href="#overview" class="active">Overview</a>
        <a href="#channels">Channels</a>
        <a href="#plan">90-Day Plan</a>
        <a href="#leads" class="{leads_class}">{leads_label}</a>
        <a href="#investors" class="{investors_class}">{investors_label}</a>
        <a href="#updates">Updates</a>
    </div>"""


def _render_quick_stats(
    top_score: int, top_channel: str, avg_score: float,
    num_channels: int, num_leads: int, num_investors: int,
    stage: str, tier: str,
) -> str:
    """Render quick stats cards row."""
    score_color = "var(--green)" if avg_score >= 6 else ("var(--yellow)" if avg_score >= 4 else "var(--orange)")
    top_color = "var(--green)" if top_score >= 7 else ("var(--yellow)" if top_score >= 5 else "var(--orange)")

    leads_val = f"{num_leads}" if tier != "free" else "&#128274;"
    investors_val = f"{num_investors}" if tier in ("growth", "enterprise") else "&#128274;"

    return f"""
    <div class="quick-stats" id="overview">
        <div class="stat-card">
            <div class="stat-value" style="color:{score_color};">{avg_score}</div>
            <div class="stat-label">Avg Channel Score</div>
            <div class="stat-sub">{num_channels} channels analyzed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:{top_color};">{top_score}/10</div>
            <div class="stat-label">Top Channel</div>
            <div class="stat-sub">{top_channel[:25]}</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--cyan);">{stage or '?'}</div>
            <div class="stat-label">Stage</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--cyan);">{leads_val}</div>
            <div class="stat-label">Leads Found</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--purple);">{investors_val}</div>
            <div class="stat-label">Investors Mapped</div>
        </div>
    </div>"""


def _render_updates(tier: str) -> str:
    """Render market intelligence updates section."""
    if tier == "free":
        return f"""
    <div class="section-card locked-section" style="min-height: 120px;">
        <h2><span class="accent">Market</span> Intelligence Updates</h2>
        <div class="locked-content">
            <div class="update-item">
                <span class="update-date">Weekly</span>
                <span class="update-content">Market shifts, competitor moves, new opportunities...</span>
            </div>
        </div>
        <div class="locked-overlay">
            <div class="lock-icon">&#128274;</div>
            <div class="lock-text">Living intelligence — updated weekly for Growth subscribers</div>
            <a class="price-btn price-btn-secondary" href="#pricing">Unlock for $200/mo</a>
        </div>
    </div>"""

    from datetime import datetime, timezone
    now_str = datetime.now(tz=timezone.utc).strftime("%b %d, %Y")

    update_freq = "weekly" if tier in ("growth", "enterprise") else "monthly"

    return f"""
    <div class="section-card">
        <h2><span class="accent">Market</span> Intelligence Updates</h2>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem;">
            Your report updates {update_freq} with fresh competitive intelligence,
            market shifts, and new opportunities.
        </p>
        <div class="update-item">
            <span class="update-date">{now_str}</span>
            <span class="update-content">Initial analysis completed. Full 19-channel traction assessment with leads and investor intelligence.</span>
        </div>
        <div style="text-align:center;padding:1rem;color:var(--text-muted);font-size:0.8rem;border-top:1px solid var(--border);margin-top:0.5rem;">
            Next update scheduled {update_freq}. Market changes will appear here automatically.
        </div>
    </div>"""


def _render_hero(profile: dict, exec_summary: str, tier: str) -> str:
    name = profile.get("name", "Startup")
    one_liner = profile.get("one_liner", "")
    stage = profile.get("stage", "unknown")
    market = profile.get("market", "")
    model = profile.get("business_model", "")
    angle = profile.get("unique_angle", "")
    strengths = profile.get("strengths", [])
    weaknesses = profile.get("weaknesses", [])

    strengths_html = "".join(f"<li>{s}</li>" for s in strengths[:4])
    weaknesses_html = "".join(f"<li>{w}</li>" for w in weaknesses[:4])

    return f"""
    <div class="hero-card">
        <h1>{name}</h1>
        <div class="one-liner">{one_liner}</div>
        <div class="hero-meta">
            <div class="meta-tag"><span class="label">Stage</span> <span class="value">{stage}</span></div>
            <div class="meta-tag"><span class="label">Market</span> <span class="value">{market[:60]}</span></div>
            <div class="meta-tag"><span class="label">Model</span> <span class="value">{model[:60]}</span></div>
        </div>
        {f'<div class="meta-tag" style="margin-bottom:1rem;"><span class="label">Edge</span> <span class="value">{angle[:120]}</span></div>' if angle else ''}
        <div class="exec-summary">{exec_summary}</div>
        <div class="strengths-weaknesses">
            <div class="sw-list">
                <h3 class="strength">Strengths</h3>
                <ul>{strengths_html}</ul>
            </div>
            <div class="sw-list">
                <h3 class="weakness">Weaknesses &amp; Risks</h3>
                <ul>{weaknesses_html}</ul>
            </div>
        </div>
    </div>"""


def _render_bullseye(bullseye: dict, channels: list, tier: str) -> str:
    inner = bullseye.get("inner_ring", {})
    promising = bullseye.get("promising", {})
    longshot = bullseye.get("long_shot", {})

    channel_scores = {ch["channel"]: ch.get("score", 0) for ch in channels}

    def _ring_html(ring_data, css_class, label):
        chs = ring_data.get("channels", [])
        items = ""
        for ch in chs[:6]:
            score = channel_scores.get(ch, "?")
            items += f'<div class="ring-channel"><span>{ch}</span><span class="score">{score}/10</span></div>'
        return f"""
        <div class="ring {css_class}">
            <h3>{label}</h3>
            {items}
        </div>"""

    return f"""
    <div class="section-card">
        <h2><span class="accent">Bullseye</span> Framework</h2>
        <div class="bullseye-rings">
            {_ring_html(inner, 'ring-inner', 'Test NOW')}
            {_ring_html(promising, 'ring-promising', 'Promising')}
            {_ring_html(longshot, 'ring-longshot', 'Long Shot')}
        </div>
    </div>"""


def _render_channels(channels: list, tier: str) -> str:
    if tier == "free":
        # Show first 3, lock the rest
        visible = channels[:3]
        locked_count = len(channels) - 3
        visible_html = _channels_grid(visible, tier)
        return f"""
    <div class="section-card">
        <h2><span class="accent">19-Channel</span> Deep Analysis</h2>
        {visible_html}
        <div class="locked-section" style="margin-top:1rem; min-height: 200px;">
            <div class="locked-content">
                {_channels_grid(channels[3:6], tier)}
            </div>
            <div class="locked-overlay">
                <div class="lock-icon">&#128274;</div>
                <div class="lock-text">{locked_count} more channels analyzed</div>
                <a class="price-btn price-btn-primary" href="#pricing">Unlock for $39/mo</a>
            </div>
        </div>
    </div>"""
    else:
        return f"""
    <div class="section-card">
        <h2><span class="accent">19-Channel</span> Deep Analysis</h2>
        {_channels_grid(channels, tier)}
    </div>"""


def _channels_grid(channels: list, tier: str) -> str:
    cards = ""
    for ch in channels:
        name = ch.get("channel", "")
        score = ch.get("score", 0)
        effort = ch.get("effort", "?")
        timeline = ch.get("timeline", "?")
        budget = ch.get("budget", "?")
        insight = ch.get("killer_insight", "")
        first_move = ch.get("first_move", "")
        ideas = ch.get("specific_ideas", [])
        why = ch.get("why_or_why_not", "")

        score_class = "score-high" if score >= 7 else ("score-mid" if score >= 5 else "score-low")
        bar_class = "score-bar-green" if score >= 7 else ("score-bar-yellow" if score >= 5 else "score-bar-red")
        bar_width = max(score * 10, 5)

        ideas_html = ""
        if ideas and tier != "free":
            ideas_items = "".join(f"<li>{idea}</li>" for idea in ideas[:3])
            ideas_html = f'<ul class="channel-ideas">{ideas_items}</ul>'

        first_move_html = ""
        if first_move and tier != "free":
            first_move_html = f'''
            <div class="channel-first-move">
                <div class="label">First Move</div>
                {first_move[:150]}
            </div>'''

        why_html = ""
        if why and tier != "free":
            why_html = f'<div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.6rem;line-height:1.5;">{why[:200]}</div>'

        cards += f"""
        <div class="channel-card">
            <div class="channel-header">
                <span class="channel-name">{name}</span>
                <span class="channel-score {score_class}">{score}/10</span>
            </div>
            <div class="score-bar-wrap"><div class="score-bar {bar_class}" style="width:{bar_width}%"></div></div>
            <div class="channel-meta">
                <span>Effort: {effort}</span>
                <span>Timeline: {timeline}</span>
                <span>Budget: {budget}</span>
            </div>
            {why_html}
            {f'<div class="channel-insight">{insight[:200]}</div>' if insight else ''}
            {ideas_html}
            {first_move_html}
        </div>"""

    return f'<div class="channel-grid">{cards}</div>'


def _render_plan(plan: dict, tier: str) -> str:
    if tier == "free":
        return f"""
    <div class="section-card locked-section" style="min-height: 180px;" id="plan">
        <h2><span class="accent">90-Day</span> Action Plan</h2>
        <div class="locked-content">
            <div class="plan-months">
                <div class="month-card"><h3>Month 1</h3><div class="focus">Loading...</div></div>
                <div class="month-card"><h3>Month 2</h3><div class="focus">Loading...</div></div>
                <div class="month-card"><h3>Month 3</h3><div class="focus">Loading...</div></div>
            </div>
        </div>
        <div class="locked-overlay">
            <div class="lock-icon">&#128274;</div>
            <div class="lock-text">Full action plan with weekly milestones</div>
            <a class="price-btn price-btn-primary" href="#pricing">Unlock for $39/mo</a>
        </div>
    </div>"""

    months_html = ""
    for key, label in [("month_1", "Month 1"), ("month_2", "Month 2"), ("month_3", "Month 3")]:
        m = plan.get(key, {})
        focus = m.get("focus", "TBD")
        metric = m.get("target_metric", "")
        budget = m.get("budget", "")
        actions = m.get("actions", [])
        actions_html = "".join(f"<li>{a}</li>" for a in actions[:5])
        months_html += f"""
        <div class="month-card">
            <h3>{label}</h3>
            <div class="focus">{focus}</div>
            {f'<div class="metric">Target: {metric}</div>' if metric else ''}
            {f'<div style="font-size:0.75rem;color:var(--text-muted);">Budget: {budget}</div>' if budget else ''}
            <ul>{actions_html}</ul>
        </div>"""

    return f"""
    <div class="section-card">
        <h2><span class="accent">90-Day</span> Action Plan</h2>
        <div class="plan-months">{months_html}</div>
    </div>"""


def _render_budget(budget: dict, tier: str) -> str:
    if tier == "free":
        return ""

    total = budget.get("total_recommended", "")
    breakdown = budget.get("breakdown", [])

    rows = ""
    for b in breakdown:
        rows += f"""<tr>
            <td>{b.get('channel', '')}</td>
            <td style="color:var(--green);">{b.get('amount', '')}</td>
            <td>{b.get('rationale', '')}</td>
        </tr>"""

    return f"""
    <div class="section-card">
        <h2><span class="accent">Budget</span> Allocation</h2>
        {f'<div class="budget-total">Recommended (90 days): {total}</div>' if total else ''}
        <table class="budget-table">
            <thead><tr><th>Channel</th><th>Amount</th><th>Rationale</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>"""


def _render_risks(risks: list, tier: str) -> str:
    if tier == "free":
        return ""

    rows = ""
    for r in risks:
        rows += f"""<tr>
            <td>{r.get('risk', '')}</td>
            <td>{r.get('probability', '')}</td>
            <td>{r.get('impact', '')}</td>
            <td>{r.get('mitigation', '')}</td>
        </tr>"""

    return f"""
    <div class="section-card">
        <h2><span class="accent">Risk</span> Matrix</h2>
        <table class="risk-table">
            <thead><tr><th>Risk</th><th>Probability</th><th>Impact</th><th>Mitigation</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>"""


def _render_moat(moat: str, tier: str) -> str:
    if tier == "free" or not moat:
        return ""
    return f"""
    <div class="section-card">
        <h2><span class="accent">Competitive</span> Moat Analysis</h2>
        <div class="moat-text">{moat}</div>
    </div>"""


def _render_hottake(hot_take: str, tier: str) -> str:
    if not hot_take:
        return ""
    # Hot take is always visible — it's the teaser that makes people want more
    return f"""
    <div class="hottake-box" style="margin-bottom:1.5rem;">
        <div class="label">The Hot Take</div>
        <div class="take">{hot_take}</div>
    </div>"""


def _render_leads(leads_data: dict, tier: str) -> str:
    personas = leads_data.get("personas", [])
    leads = leads_data.get("leads", [])
    error = leads_data.get("_error", "")

    if not personas and not leads:
        if error == "timeout":
            msg = "Lead research timed out — our AI took too long thinking about your customers. The report will auto-update when results come in."
        elif error:
            msg = f"Lead research hit a snag: {error[:80]}. We'll retry on the next update cycle."
        else:
            msg = "Lead research is processing. Check back shortly for customer personas and potential leads."
        return f"""
    <div class="section-card">
        <h2><span class="accent">Potential</span> Leads</h2>
        <p style="color:var(--text-muted);font-size:0.85rem;">{msg}</p>
    </div>"""

    # Personas (show 1 in free, all in starter+)
    personas_html = ""
    visible_personas = personas[:1] if tier == "free" else personas[:3]
    for p in visible_personas:
        networks = p.get("social_networks", {})
        primary = networks.get("primary", [])
        secondary = networks.get("secondary", [])

        def _network_class(name):
            n = name.lower().replace("/x", "").replace("twitter", "twitter").strip()
            platform_map = {
                "twitter": "platform-twitter", "x": "platform-twitter",
                "reddit": "platform-reddit", "linkedin": "platform-linkedin",
                "discord": "platform-discord", "telegram": "platform-telegram",
                "youtube": "platform-youtube", "instagram": "platform-instagram",
                "tiktok": "platform-tiktok", "facebook": "platform-facebook",
                "substack": "platform-substack", "hacker news": "platform-hn",
            }
            for key, cls in platform_map.items():
                if key in n:
                    return cls
            return "platform-default"

        primary_tags = "".join(
            f'<span class="network-tag {_network_class(n)}">{n}</span>'
            for n in primary[:4]
        )
        secondary_tags = "".join(
            f'<span class="network-tag {_network_class(n)}" style="opacity:0.7;">{n}</span>'
            for n in secondary[:3]
        )

        signals = p.get("pain_signals", [])
        signals_html = ""
        if signals:
            items = "".join(
                f'<div class="persona-signal-item">&ldquo;{s}&rdquo;</div>'
                for s in signals[:4]
            )
            signals_html = f'<div class="persona-signals-list">{items}</div>'

        triggers = p.get("trigger_events", [])
        triggers_html = ""
        if triggers and tier != "free":
            trigger_items = "".join(f"<li>{t}</li>" for t in triggers[:4])
            triggers_html = f"""
            <div class="persona-triggers">
                <div class="trigger-label">Trigger Events</div>
                <ul>{trigger_items}</ul>
            </div>"""

        subreddits = p.get("subreddits", [])
        subs_html = ""
        if subreddits and tier != "free":
            sub_tags = "".join(
                f'<span class="network-tag platform-reddit">r/{s.replace("r/", "")}</span>'
                for s in subreddits[:4]
            )
            subs_html = f'<div style="margin-top:0.5rem;">{sub_tags}</div>'

        reach = p.get("reachability", "?")
        net_val = p.get("network_value", "?")
        age = p.get("age_range", "")
        income = p.get("income", "")
        wtp = p.get("willingness_to_pay", "")

        meta_items = ""
        if age:
            meta_items += f'<span class="persona-meta-item"><span class="pm-label">Age </span><span class="pm-value">{age}</span></span>'
        if income and tier != "free":
            meta_items += f'<span class="persona-meta-item"><span class="pm-label">Income </span><span class="pm-value">{income}</span></span>'
        if wtp and tier != "free":
            meta_items += f'<span class="persona-meta-item"><span class="pm-label">WTP </span><span class="pm-value">{wtp}</span></span>'
        meta_items += f'<span class="persona-meta-item"><span class="pm-label">Reach </span><span class="pm-value">{reach}/10</span></span>'
        meta_items += f'<span class="persona-meta-item"><span class="pm-label">Network </span><span class="pm-value">{net_val}/10</span></span>'

        personas_html += f"""
        <div class="persona-card">
            <h4>{p.get('name', 'Unknown')}</h4>
            <div class="who">{p.get('who', '')}</div>
            <div class="persona-meta-row">{meta_items}</div>
            <div style="margin-bottom:0.4rem;">
                <div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:3px;">Primary</div>
                <div class="persona-networks">{primary_tags}</div>
            </div>
            <div style="margin-bottom:0.4rem;">
                <div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:3px;">Secondary</div>
                <div class="persona-networks">{secondary_tags}</div>
            </div>
            {subs_html}
            {signals_html}
            {triggers_html}
        </div>"""

    if tier == "free" and len(personas) > 1:
        personas_html += f"""
        <div style="text-align:center;padding:0.8rem;color:var(--text-muted);font-size:0.8rem;">
            + {len(personas) - 1} more personas with full pain signals, trigger events &amp; subreddits
            <br><a href="#pricing" style="color:var(--cyan);text-decoration:none;">Unlock with Starter — $39/mo</a>
        </div>"""

    # Leads (show 3 in starter, all in growth, none in free)
    leads_html = ""

    def _source_badge(source):
        source_map = {
            "twitter": ("platform-twitter", "Twitter/X"),
            "linkedin": ("platform-linkedin", "LinkedIn"),
            "reddit": ("platform-reddit", "Reddit"),
            "substack": ("platform-substack", "Substack"),
            "blog": ("platform-default", "Blog"),
            "web": ("platform-default", "Web"),
        }
        cls, label = source_map.get(source, ("platform-default", source))
        return f'<span class="network-tag {cls}" style="font-size:0.65rem;">{label}</span>'

    def _render_lead_item(lead, show_signal=False):
        score = lead.get("score", 0)
        score_class = "score-high" if score >= 7 else ("score-mid" if score >= 5 else "score-low")
        name = lead.get("name", "Unknown")[:60]
        url = lead.get("url", "#")
        source = lead.get("source", "web")
        persona = lead.get("persona_match", "")
        signal = lead.get("relevance_signal", "")[:100]
        return f"""
            <div class="lead-item">
                <div style="flex:1;">
                    <div class="lead-name"><a href="{url}" target="_blank">{name}</a></div>
                    <div class="lead-source" style="display:flex;align-items:center;gap:6px;margin-top:3px;">
                        {_source_badge(source)}
                        {f'<span style="color:var(--text-muted);font-size:0.7rem;">{persona}</span>' if persona else ''}
                    </div>
                    {f'<div style="font-size:0.72rem;color:#555;margin-top:4px;line-height:1.4;">{signal}</div>' if show_signal and signal else ''}
                </div>
                <span class="lead-score {score_class}">{score}/10</span>
            </div>"""

    if tier == "free":
        leads_html = f"""
        <div class="locked-section" style="min-height: 120px;">
            <div class="locked-content">
                {''.join(_render_lead_item(l) for l in leads[:3])}
            </div>
            <div class="locked-overlay">
                <div class="lock-icon">&#128274;</div>
                <div class="lock-text">{len(leads)} leads found across Twitter, LinkedIn, Reddit &amp; more</div>
                <a class="price-btn price-btn-secondary" href="#pricing">Unlock in Growth — $200/mo</a>
            </div>
        </div>"""
    elif tier == "starter":
        for lead in leads[:3]:
            leads_html += _render_lead_item(lead, show_signal=True)
        if len(leads) > 3:
            leads_html += f"""
            <div style="text-align:center;padding:0.8rem;color:var(--text-muted);font-size:0.8rem;">
                + {len(leads) - 3} more leads with relevance signals
                <br><a href="#pricing" style="color:var(--orange);text-decoration:none;">Upgrade to Growth — $200/mo</a>
            </div>"""
    else:
        for lead in leads[:10]:
            leads_html += _render_lead_item(lead, show_signal=True)

    return f"""
    <div class="section-card">
        <h2><span class="accent">Potential</span> Leads</h2>
        <h3 style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.8rem;">Customer Personas</h3>
        {personas_html}
        {f'<h3 style="font-size:0.8rem;color:var(--text-muted);margin:0.8rem 0;">Identified Leads</h3>{leads_html}' if leads_html else ''}
    </div>"""


def _render_investors(investors_data: dict, tier: str) -> str:
    competitors = investors_data.get("competitors", [])
    comp_investors = investors_data.get("competitor_investors", [])
    market_investors = investors_data.get("market_investors", [])
    error = investors_data.get("_error", "")

    if not competitors and not market_investors:
        if error == "timeout":
            msg = "Investor research timed out — competitor analysis took too long. Results will appear on the next update cycle."
        elif error:
            msg = f"Investor research hit a snag: {error[:80]}. We'll retry on the next update."
        else:
            msg = "Investor intelligence is processing. Check back shortly for competitor and investor data."
        return f"""
    <div class="section-card">
        <h2><span class="accent">Investor</span> Intelligence</h2>
        <p style="color:var(--text-muted);font-size:0.85rem;">{msg}</p>
    </div>"""

    # Competitors (show 2 in free, all in starter+)
    comp_html = ""
    visible_comp = competitors[:2] if tier == "free" else competitors[:6]
    for c in visible_comp:
        name = c.get("name", "")[:50]
        url = c.get("url", "#")
        desc = c.get("description", "")[:150]
        funding = c.get("funding", "")
        inv_names = c.get("investors", [])[:4]
        inv_tags = "".join(f'<span class="investor-tag">{i}</span>' for i in inv_names) if inv_names else ""

        comp_html += f"""
        <div class="competitor-card">
            <div class="competitor-info">
                <h4><a href="{url}" target="_blank">{name}</a></h4>
                {f'<div class="competitor-desc">{desc}</div>' if desc else ''}
                {f'<div class="competitor-investors-tags">{inv_tags}</div>' if inv_tags else ''}
            </div>
            {f'<span class="funding-badge">{funding}</span>' if funding else ''}
        </div>"""

    if tier == "free" and len(competitors) > 2:
        comp_html += f"""
        <div style="text-align:center;padding:0.5rem;color:var(--text-muted);font-size:0.75rem;">
            + {len(competitors) - 2} more competitors mapped
        </div>"""

    # Investors (locked in free, show 3 in starter, all in growth)
    inv_html = ""
    all_investors = comp_investors + market_investors

    def _inv_type_class(t):
        tl = (t or "").lower()
        if "vc" in tl or "venture" in tl or "capital" in tl:
            return "inv-type-vc"
        if "angel" in tl:
            return "inv-type-angel"
        return "inv-type-default"

    def _render_investor_card(inv, show_signal=False):
        name = inv.get("name", "")[:50]
        url = inv.get("url", "#")
        inv_type = inv.get("type", inv.get("title", "Unknown"))
        signal = inv.get("relevance", inv.get("relevance_signal", ""))[:100]
        source = inv.get("source", "web")
        type_class = _inv_type_class(inv_type)

        linkedin_icon = ""
        if "linkedin.com" in url:
            linkedin_icon = ' <span style="font-size:0.65rem;color:#0a66c2;">LinkedIn</span>'

        return f"""
        <div class="investor-card">
            <div>
                <div class="inv-name"><a href="{url}" target="_blank">{name}</a>{linkedin_icon}</div>
                {f'<div class="inv-signal">{signal}</div>' if show_signal and signal else ''}
            </div>
            <span class="inv-type-badge {type_class}">{inv_type}</span>
        </div>"""

    if tier == "free":
        inv_html = f"""
        <div class="locked-section" style="min-height: 120px;">
            <div class="locked-content">
                {''.join(_render_investor_card(inv) for inv in all_investors[:3])}
            </div>
            <div class="locked-overlay">
                <div class="lock-icon">&#128274;</div>
                <div class="lock-text">{len(all_investors)} investors identified — with LinkedIn profiles, fund focus &amp; relevance signals</div>
                <a class="price-btn price-btn-secondary" href="#pricing">Unlock in Growth — $200/mo</a>
            </div>
        </div>"""
    elif tier == "starter":
        for inv in all_investors[:3]:
            inv_html += _render_investor_card(inv, show_signal=True)
        if len(all_investors) > 3:
            inv_html += f"""
            <div style="text-align:center;padding:0.8rem;color:var(--text-muted);font-size:0.8rem;">
                + {len(all_investors) - 3} more investors with LinkedIn &amp; fund details
                <br><a href="#pricing" style="color:var(--orange);text-decoration:none;">Upgrade to Growth — $200/mo</a>
            </div>"""
    else:
        for inv in all_investors[:15]:
            inv_html += _render_investor_card(inv, show_signal=True)

    return f"""
    <div class="section-card">
        <h2><span class="accent">Investor</span> Intelligence</h2>
        <h3 style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.8rem;">Competitors &amp; Their Funding</h3>
        {comp_html}
        <h3 style="font-size:0.8rem;color:var(--text-muted);margin:1rem 0 0.8rem;">Potential Investors for You</h3>
        {inv_html}
    </div>"""


def _render_pricing(
    report_id: str,
    tier: str,
    checkout_url: str,
    upgrade_url: str,
) -> str:
    starter_active = "active" if tier == "starter" else ""
    growth_active = "active" if tier == "growth" else ""
    enterprise_active = "active" if tier == "enterprise" else ""

    starter_btn = ""
    growth_btn = ""

    if tier == "free":
        starter_btn = f'<a class="price-btn price-btn-primary" href="{checkout_url}">Subscribe — $39/mo</a>'
        growth_btn = f'<a class="price-btn price-btn-secondary" href="{checkout_url}">Subscribe — $200/mo</a>'
    elif tier == "starter":
        starter_btn = '<span style="color:var(--green);font-size:0.85rem;">Current Plan</span>'
        growth_btn = f'<a class="price-btn price-btn-secondary" href="{upgrade_url}">Upgrade — $200/mo</a>'
    elif tier in ("growth", "enterprise"):
        starter_btn = '<span style="color:var(--text-muted);font-size:0.8rem;">—</span>'
        growth_btn = '<span style="color:var(--green);font-size:0.85rem;">Current Plan</span>'

    return f"""
    <div class="section-card" id="pricing">
        <h2><span class="accent">Plans</span></h2>
        <div class="pricing-cards">
            <div class="price-card {starter_active}">
                <h4 style="color:var(--green);">Starter</h4>
                <div class="price" style="color:var(--green);">$39<span class="period">/mo</span></div>
                <ul class="features">
                    <li>Full 19-channel analysis</li>
                    <li>90-day action plan</li>
                    <li>Budget allocation</li>
                    <li>Risk matrix</li>
                    <li>Competitive moat analysis</li>
                    <li>Monthly market updates</li>
                    <li>3 customer personas</li>
                    <li class="locked">3 of 10 leads shown</li>
                    <li class="locked">3 of 10+ investors shown</li>
                </ul>
                {starter_btn}
            </div>
            <div class="price-card {growth_active} {'recommended' if tier == 'free' else ''}">
                <h4 style="color:var(--orange);">Growth</h4>
                <div class="price" style="color:var(--orange);">$200<span class="period">/mo</span></div>
                <ul class="features">
                    <li>Everything in Starter</li>
                    <li>Full lead discovery (10+ leads)</li>
                    <li>Full investor intelligence</li>
                    <li>Competitor funding analysis</li>
                    <li>Weekly market updates</li>
                    <li>Lead enrichment with signals</li>
                </ul>
                {growth_btn}
            </div>
            <div class="price-card {enterprise_active}">
                <h4 style="color:var(--purple);">Enterprise</h4>
                <div class="price" style="color:var(--purple);">Custom</div>
                <ul class="features">
                    <li>Everything in Growth</li>
                    <li>Custom analysis depth</li>
                    <li>Dedicated strategy sessions</li>
                    <li>Priority support</li>
                    <li>Custom integrations</li>
                </ul>
                <a class="price-btn price-btn-outline" href="mailto:{settings.enterprise_email}">Contact Us</a>
            </div>
        </div>
    </div>"""
