"""
Dashboard v3 — Formal consulting dashboard with spreadsheet-like tables.
Inspired by traditional BI dashboards. Tab-based navigation.
Emphasises living/ongoing intelligence updates.
"""

from html import escape
from datetime import datetime, timezone


def _e(text: str) -> str:
    return escape(str(text)) if text else ""


def render_dashboard_v3(analysis: dict, startup_name: str, report_id: str) -> str:
    profile = analysis.get("company_profile", {})
    channels = analysis.get("channel_analysis", [])
    bullseye = analysis.get("bullseye_ranking", {})
    plan = analysis.get("ninety_day_plan", {})
    budget = analysis.get("budget_allocation", {})
    risks = analysis.get("risk_matrix", [])
    moat = analysis.get("competitive_moat", "")
    hot_take = analysis.get("hot_take", "")
    exec_summary = analysis.get("executive_summary", "")
    leads_data = analysis.get("leads_research", {})
    investors_data = analysis.get("investor_research", {})

    sorted_channels = sorted(channels, key=lambda c: c.get("score", 0), reverse=True)
    leads = leads_data.get("leads", [])
    personas = leads_data.get("personas", [])
    competitors = investors_data.get("competitors", [])
    comp_investors = investors_data.get("competitor_investors", [])
    market_investors = investors_data.get("market_investors", [])
    all_investors = comp_investors + market_investors

    scores = [ch.get("score", 0) for ch in channels]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    top_channel = sorted_channels[0].get("channel", "") if sorted_channels else ""
    top_score = sorted_channels[0].get("score", 0) if sorted_channels else 0

    now = datetime.now(tz=timezone.utc)
    now_str = now.strftime("%B %d, %Y")
    now_time = now.strftime("%H:%M UTC")

    inner = bullseye.get("inner_ring", {}).get("channels", [])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>mckoutie — {_e(startup_name)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=EB+Garamond:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root {{
    --bg: #09090b; --bg2: #0f0f12; --card: #141418; --card2: #1a1a1f;
    --border: #27272a; --border2: #3f3f46;
    --text: #fafafa; --text2: #d4d4d8; --muted: #71717a; --dim: #52525b;
    --accent: #06b6d4; --accent2: #22d3ee;
    --green: #10b981; --green2: #059669; --green-bg: #052e16;
    --orange: #f97316; --orange-bg: #431407;
    --red: #ef4444; --red-bg: #450a0a;
    --yellow: #eab308; --yellow-bg: #422006;
    --purple: #a78bfa;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); font-size:14px; line-height:1.5; -webkit-font-smoothing:antialiased; }}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ color:var(--accent2); text-decoration:underline; }}

/* ─── TOPBAR ─── */
.topbar {{ display:flex; align-items:center; justify-content:space-between; padding:12px 24px; background:var(--bg2); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:100; }}
.topbar-left {{ display:flex; align-items:center; gap:16px; }}
.logo {{ font-family:'EB Garamond',serif; font-size:18px; letter-spacing:-0.02em; }}
.logo-name {{ color:var(--accent); }}
.logo-co {{ color:var(--dim); font-size:11px; font-variant:small-caps; }}
.divider {{ width:1px; height:20px; background:var(--border); }}
.company-name {{ font-weight:600; font-size:15px; }}
.topbar-right {{ display:flex; align-items:center; gap:12px; }}
.live-badge {{ display:flex; align-items:center; gap:6px; padding:4px 10px; background:var(--green-bg); border:1px solid var(--green2); border-radius:999px; font-size:11px; font-weight:600; color:var(--green); }}
.live-dot {{ width:6px; height:6px; border-radius:50%; background:var(--green); animation:pulse 2s ease-in-out infinite; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.3}} }}
.report-date {{ font-size:12px; color:var(--muted); font-family:'JetBrains Mono',monospace; }}

/* ─── TABS ─── */
.tabs {{ display:flex; gap:0; border-bottom:1px solid var(--border); background:var(--bg2); padding:0 24px; overflow-x:auto; }}
.tab {{ padding:10px 20px; font-size:13px; font-weight:500; color:var(--muted); cursor:pointer; border-bottom:2px solid transparent; transition:all 0.15s; white-space:nowrap; }}
.tab:hover {{ color:var(--text2); background:var(--card); }}
.tab.active {{ color:var(--accent); border-bottom-color:var(--accent); }}
.tab-count {{ font-family:'JetBrains Mono',monospace; font-size:11px; background:var(--card2); padding:1px 6px; border-radius:99px; margin-left:6px; color:var(--dim); }}
.tab.active .tab-count {{ background:rgba(6,182,212,0.15); color:var(--accent); }}

/* ─── PANELS ─── */
.panel {{ display:none; }}
.panel.active {{ display:block; }}
.content {{ max-width:1280px; margin:0 auto; padding:24px; }}

/* ─── KPI ROW ─── */
.kpi-row {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }}
@media(max-width:900px) {{ .kpi-row {{ grid-template-columns:repeat(3,1fr); }} }}
@media(max-width:600px) {{ .kpi-row {{ grid-template-columns:repeat(2,1fr); }} }}
.kpi {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; }}
.kpi-label {{ font-size:11px; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px; }}
.kpi-val {{ font-family:'JetBrains Mono',monospace; font-size:24px; font-weight:700; line-height:1.2; }}
.kpi-sub {{ font-size:12px; color:var(--dim); margin-top:2px; }}

/* ─── EXEC SUMMARY ─── */
.exec {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:20px 24px; margin-bottom:24px; }}
.exec-label {{ font-size:11px; font-weight:700; color:var(--orange); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:8px; }}
.exec-text {{ font-family:'EB Garamond',serif; font-size:16px; line-height:1.7; color:var(--text2); font-style:italic; }}

/* ─── SECTION HEADERS ─── */
.sh {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }}
.sh-title {{ font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--muted); }}
.sh-badge {{ font-size:11px; padding:3px 8px; border-radius:4px; font-weight:600; }}
.sh-badge-live {{ background:var(--green-bg); color:var(--green); border:1px solid var(--green2); }}

/* ─── TABLE STYLES ─── */
.tbl-wrap {{ background:var(--card); border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:24px; }}
.tbl {{ width:100%; border-collapse:collapse; }}
.tbl thead {{ background:var(--card2); }}
.tbl th {{ text-align:left; padding:10px 14px; font-size:11px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:0.06em; border-bottom:1px solid var(--border); white-space:nowrap; }}
.tbl td {{ padding:10px 14px; border-bottom:1px solid var(--border); font-size:13px; color:var(--text2); }}
.tbl tbody tr {{ transition:background 0.1s; }}
.tbl tbody tr:hover {{ background:var(--card2); }}
.tbl tbody tr:last-child td {{ border-bottom:none; }}

/* Score cells */
.score-cell {{ font-family:'JetBrains Mono',monospace; font-weight:700; font-size:14px; }}
.score-hi {{ color:var(--green); }}
.score-mid {{ color:var(--yellow); }}
.score-lo {{ color:var(--dim); }}
.score-bar {{ display:inline-block; height:4px; border-radius:2px; margin-left:8px; vertical-align:middle; }}
.score-bar-hi {{ background:var(--green); }}
.score-bar-mid {{ background:var(--yellow); }}
.score-bar-lo {{ background:var(--dim); }}

/* Platform pill */
.pill {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
.pill-twitter {{ background:#1c2733; color:#1da1f2; }}
.pill-linkedin {{ background:#00152a; color:#0a66c2; }}
.pill-reddit {{ background:#2a1500; color:#ff4500; }}
.pill-discord {{ background:#1a1440; color:#5865f2; }}
.pill-github {{ background:#161b22; color:#f0f6fc; }}
.pill-substack {{ background:#2a1500; color:#ff6719; }}
.pill-web {{ background:var(--card2); color:var(--muted); }}

/* Investor type pill */
.type-vc {{ background:#1e1b4b; color:var(--purple); }}
.type-angel {{ background:var(--green-bg); color:var(--green); }}
.type-other {{ background:var(--card2); color:var(--muted); }}

/* Fund badge */
.fund {{ font-family:'JetBrains Mono',monospace; font-weight:700; color:var(--green); white-space:nowrap; }}

/* Relevance bar */
.rel-bar {{ width:60px; height:6px; background:var(--border); border-radius:3px; display:inline-block; overflow:hidden; vertical-align:middle; }}
.rel-fill {{ height:100%; border-radius:3px; }}

/* ─── BULLSEYE MINI ─── */
.bullseye-mini {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:24px; }}
@media(max-width:768px) {{ .bullseye-mini {{ grid-template-columns:1fr; }} }}
.ring-box {{ background:var(--card); border-radius:8px; padding:14px; }}
.ring-box-inner {{ border:1px solid var(--green); }}
.ring-box-prom {{ border:1px solid var(--yellow); }}
.ring-box-long {{ border:1px solid var(--border); }}
.ring-label {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px; }}
.ring-label-inner {{ color:var(--green); }}
.ring-label-prom {{ color:var(--yellow); }}
.ring-label-long {{ color:var(--dim); }}
.ring-ch {{ display:flex; justify-content:space-between; padding:3px 0; font-size:12px; color:var(--text2); }}
.ring-ch-score {{ font-family:'JetBrains Mono',monospace; font-weight:700; }}

/* ─── CHANNEL DETAIL ─── */
.ch-expand {{ display:none; background:var(--bg2); border-top:1px solid var(--border); }}
.ch-expand.open {{ display:table-row; }}
.ch-expand td {{ padding:16px 14px; }}
.ch-detail-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
@media(max-width:768px) {{ .ch-detail-grid {{ grid-template-columns:1fr; }} }}
.ch-insight-box {{ background:var(--card2); border-radius:6px; padding:12px; font-size:12px; }}
.ch-insight-label {{ font-size:10px; font-weight:700; color:var(--accent); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px; }}
.ch-idea {{ font-size:12px; color:var(--text2); padding:3px 0; padding-left:12px; position:relative; }}
.ch-idea::before {{ content:'→'; position:absolute; left:0; color:var(--accent); }}

/* ─── UPGRADE BANNER ─── */
.upgrade-bar {{ background:linear-gradient(90deg,var(--card),var(--card2)); border:1px solid var(--border); border-radius:8px; padding:20px 24px; display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }}
.upgrade-bar-text {{ max-width:600px; }}
.upgrade-bar-title {{ font-weight:600; font-size:15px; margin-bottom:4px; }}
.upgrade-bar-sub {{ font-size:12px; color:var(--muted); }}
.btn {{ display:inline-block; padding:8px 20px; border-radius:6px; font-weight:600; font-size:13px; cursor:pointer; text-decoration:none; }}
.btn:hover {{ text-decoration:none; }}
.btn-green {{ background:var(--green); color:#000; }}
.btn-green:hover {{ background:#34d399; color:#000; }}
.btn-orange {{ background:var(--orange); color:#fff; }}
.btn-orange:hover {{ background:#fb923c; color:#fff; }}
.btn-outline {{ border:1px solid var(--border); color:var(--muted); background:transparent; }}
.btn-outline:hover {{ border-color:var(--accent); color:var(--accent); }}

/* ─── PERSONA CARDS ─── */
.persona-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:24px; }}
@media(max-width:900px) {{ .persona-row {{ grid-template-columns:1fr; }} }}
.p-card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; }}
.p-name {{ font-weight:600; color:var(--accent); margin-bottom:4px; }}
.p-desc {{ font-size:12px; color:var(--muted); margin-bottom:10px; line-height:1.5; }}
.p-nets {{ display:flex; flex-wrap:wrap; gap:4px; margin-bottom:8px; }}
.p-signal {{ font-size:11px; color:var(--dim); font-style:italic; padding:4px 0; border-top:1px solid var(--border); }}
.p-signal::before {{ content:'"'; color:var(--accent); }}
.p-signal::after {{ content:'"'; color:var(--accent); }}

/* ─── PLAN ─── */
.plan-cols {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:24px; }}
@media(max-width:768px) {{ .plan-cols {{ grid-template-columns:1fr; }} }}
.plan-box {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; }}
.plan-month {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:var(--accent); margin-bottom:4px; }}
.plan-focus {{ font-weight:600; font-size:14px; margin-bottom:8px; }}
.plan-metric {{ font-size:12px; color:var(--green); margin-bottom:4px; }}
.plan-budget {{ font-size:12px; color:var(--orange); margin-bottom:8px; }}
.plan-action {{ font-size:12px; color:var(--muted); padding:3px 0 3px 12px; position:relative; }}
.plan-action::before {{ content:'•'; position:absolute; left:0; color:var(--dim); }}

/* ─── PRICING ─── */
.pricing-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
@media(max-width:900px) {{ .pricing-grid {{ grid-template-columns:repeat(2,1fr); }} }}
@media(max-width:550px) {{ .pricing-grid {{ grid-template-columns:1fr; }} }}
.price-card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:20px; text-align:center; position:relative; }}
.price-card.pop {{ border-color:var(--green); background:linear-gradient(180deg,var(--green-bg),var(--card)); }}
.price-card.ug {{ border-color:var(--orange); }}
.price-tier {{ font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--muted); margin-bottom:4px; }}
.price-amt {{ font-family:'JetBrains Mono',monospace; font-size:32px; font-weight:700; margin:4px 0; }}
.price-per {{ font-size:12px; color:var(--dim); }}
.price-desc {{ font-size:12px; color:var(--muted); margin:8px 0 12px; }}
.price-feat {{ text-align:left; font-size:12px; color:var(--muted); padding:4px 0; border-bottom:1px solid var(--border); }}
.price-feat:last-of-type {{ border-bottom:none; }}
.price-feat::before {{ content:'✓ '; color:var(--green); font-weight:700; }}
.pop-tag {{ position:absolute; top:-10px; left:50%; transform:translateX(-50%); background:var(--green); color:#000; padding:3px 12px; border-radius:99px; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; }}

/* ─── FOOTER ─── */
.foot {{ text-align:center; padding:24px; border-top:1px solid var(--border); margin-top:32px; }}
.foot p {{ color:var(--dim); font-size:12px; }}

/* ─── TWO COL ─── */
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:24px; }}
@media(max-width:768px) {{ .two-col {{ grid-template-columns:1fr; }} }}

/* ─── UPDATES TIMELINE ─── */
.timeline {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:24px; }}
.tl-item {{ display:flex; gap:12px; padding:8px 0; border-bottom:1px solid var(--border); }}
.tl-item:last-child {{ border-bottom:none; }}
.tl-dot {{ width:8px; height:8px; border-radius:50%; margin-top:5px; flex-shrink:0; }}
.tl-dot-new {{ background:var(--green); box-shadow:0 0 6px var(--green); }}
.tl-dot-old {{ background:var(--dim); }}
.tl-date {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--dim); width:90px; flex-shrink:0; }}
.tl-text {{ font-size:12px; color:var(--text2); }}
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
    <div class="topbar-left">
        <div class="logo"><span class="logo-name">mckoutie</span> <span class="logo-co">&amp; company</span></div>
        <div class="divider"></div>
        <div class="company-name">{_e(startup_name)}</div>
    </div>
    <div class="topbar-right">
        <div class="live-badge"><span class="live-dot"></span> Living Report</div>
        <div class="report-date">{now_str} · {now_time}</div>
    </div>
</div>

<!-- TABS -->
<div class="tabs" id="tabs">
    <div class="tab active" data-tab="overview">Overview</div>
    <div class="tab" data-tab="channels">Channels <span class="tab-count">{len(channels)}</span></div>
    <div class="tab" data-tab="leads">Leads <span class="tab-count">{len(leads)}</span></div>
    <div class="tab" data-tab="investors">Investors <span class="tab-count">{len(all_investors)}</span></div>
    <div class="tab" data-tab="strategy">Strategy</div>
    <div class="tab" data-tab="pricing">Pricing</div>
</div>

<!-- ═══════════ OVERVIEW PANEL ═══════════ -->
<div class="panel active" id="panel-overview">
<div class="content">

    <!-- KPIs -->
    <div class="kpi-row">
        <div class="kpi">
            <div class="kpi-label">Avg Channel Score</div>
            <div class="kpi-val" style="color:var(--green)">{avg_score}</div>
            <div class="kpi-sub">across {len(channels)} channels</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Top Channel</div>
            <div class="kpi-val" style="color:var(--accent);font-size:18px">{_e(top_channel)}</div>
            <div class="kpi-sub">score: {top_score}/10</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Leads Found</div>
            <div class="kpi-val" style="color:var(--orange)">{len(leads)}</div>
            <div class="kpi-sub">potential customers</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Investors</div>
            <div class="kpi-val" style="color:var(--purple)">{len(all_investors)}</div>
            <div class="kpi-sub">in your space</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Competitors</div>
            <div class="kpi-val" style="color:var(--red)">{len(competitors)}</div>
            <div class="kpi-sub">tracked</div>
        </div>
    </div>

    <!-- Exec Summary / Hot Take -->
    <div class="exec">
        <div class="exec-label">Executive Summary</div>
        <div class="exec-text">{_e(hot_take)}</div>
    </div>

    <!-- Bullseye -->
    {_bullseye_mini(bullseye, channels)}

    <!-- Top leads preview -->
    <div class="sh">
        <div class="sh-title">Top Leads</div>
        <div class="sh-badge sh-badge-live">Updating</div>
    </div>
    {_leads_preview_table(leads[:5])}

    <!-- Top investors preview -->
    <div class="sh">
        <div class="sh-title">Top Investors in Your Space</div>
        <div class="sh-badge sh-badge-live">Updating</div>
    </div>
    {_investors_preview_table(all_investors[:5])}

    <!-- Updates timeline -->
    <div class="sh"><div class="sh-title">Intelligence Updates</div></div>
    <div class="timeline">
        <div class="tl-item">
            <div class="tl-dot tl-dot-new"></div>
            <div class="tl-date">{now_str}</div>
            <div class="tl-text">Initial analysis complete — {len(channels)} channels scored, {len(leads)} leads identified, {len(all_investors)} investors mapped</div>
        </div>
        <div class="tl-item">
            <div class="tl-dot tl-dot-new"></div>
            <div class="tl-date">Next: 7 days</div>
            <div class="tl-text">Market intelligence update — competitor moves, new funding rounds, fresh lead signals</div>
        </div>
        <div class="tl-item">
            <div class="tl-dot tl-dot-old"></div>
            <div class="tl-date">Ongoing</div>
            <div class="tl-text">Continuous monitoring for mentions, competitor launches, investor activity in your space</div>
        </div>
    </div>

    <!-- Upgrade banner -->
    <div class="upgrade-bar">
        <div class="upgrade-bar-text">
            <div class="upgrade-bar-title">Get the full playbook with outreach strategies</div>
            <div class="upgrade-bar-sub">Unlock detailed channel tactics, outreach templates for every lead, and investor approach strategies. Updated weekly.</div>
        </div>
        <a href="#" class="btn btn-green" onclick="switchTab('pricing');return false;">View Plans</a>
    </div>

</div>
</div>

<!-- ═══════════ CHANNELS PANEL ═══════════ -->
<div class="panel" id="panel-channels">
<div class="content">
    <div class="sh"><div class="sh-title">Channel Analysis — {len(channels)} Channels Scored</div></div>
    {_channels_table(sorted_channels)}
</div>
</div>

<!-- ═══════════ LEADS PANEL ═══════════ -->
<div class="panel" id="panel-leads">
<div class="content">

    <!-- Personas -->
    <div class="sh"><div class="sh-title">Customer Personas</div></div>
    {_personas_section(personas)}

    <!-- Full leads table -->
    <div class="sh">
        <div class="sh-title">Identified Leads <span style="color:var(--dim);font-weight:400;text-transform:none;">— {len(leads)} found</span></div>
        <div class="sh-badge sh-badge-live">Updating weekly</div>
    </div>
    {_leads_full_table(leads)}

    <div class="upgrade-bar">
        <div class="upgrade-bar-text">
            <div class="upgrade-bar-title">Unlock outreach strategies for every lead</div>
            <div class="upgrade-bar-sub">Get personalised approach angles, message templates, and timing recommendations for each lead.</div>
        </div>
        <a href="#" class="btn btn-green" onclick="switchTab('pricing');return false;">Upgrade — $39/mo</a>
    </div>

</div>
</div>

<!-- ═══════════ INVESTORS PANEL ═══════════ -->
<div class="panel" id="panel-investors">
<div class="content">

    <!-- Competitors -->
    <div class="sh"><div class="sh-title">Competitor Landscape</div></div>
    {_competitors_table(competitors)}

    <!-- Investors -->
    <div class="sh">
        <div class="sh-title">Investors Active in Your Space <span style="color:var(--dim);font-weight:400;text-transform:none;">— {len(all_investors)} found</span></div>
        <div class="sh-badge sh-badge-live">Updating weekly</div>
    </div>
    {_investors_full_table(comp_investors, market_investors)}

    <div class="upgrade-bar">
        <div class="upgrade-bar-text">
            <div class="upgrade-bar-title">Unlock investor deep profiles & intro paths</div>
            <div class="upgrade-bar-sub">Get thesis analysis, portfolio overlap, warm intro paths, and approach strategies for each investor.</div>
        </div>
        <a href="#" class="btn btn-orange" onclick="switchTab('pricing');return false;">Upgrade — $200/mo</a>
    </div>

</div>
</div>

<!-- ═══════════ STRATEGY PANEL ═══════════ -->
<div class="panel" id="panel-strategy">
<div class="content">

    <!-- 90-day plan -->
    <div class="sh"><div class="sh-title">90-Day Action Plan</div></div>
    {_plan_section(plan)}

    <!-- Budget -->
    <div class="sh"><div class="sh-title">Budget Allocation</div></div>
    {_budget_table(budget)}

    <!-- Risk matrix -->
    <div class="sh"><div class="sh-title">Risk Matrix</div></div>
    {_risk_table(risks)}

    <!-- Moat -->
    {_moat_box(moat)}

</div>
</div>

<!-- ═══════════ PRICING PANEL ═══════════ -->
<div class="panel" id="panel-pricing">
<div class="content">
    <div style="text-align:center;margin-bottom:24px;">
        <div style="font-family:'EB Garamond',serif;font-size:28px;margin-bottom:4px;">Choose Your Plan</div>
        <div style="color:var(--muted);font-size:13px;">Your report keeps updating. The longer you're subscribed, the smarter it gets.</div>
    </div>
    {_pricing_cards()}
</div>
</div>

<footer class="foot">
    <p>mckoutie &amp; company — AI strategy consulting</p>
    <p style="margin-top:4px;">Not affiliated with McKinsey. Powered by questionable AI. Reports are starting points, not gospel.</p>
</footer>

<script>
function switchTab(name) {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelector('[data-tab="'+name+'"]').classList.add('active');
    document.getElementById('panel-'+name).classList.add('active');
    window.scrollTo(0,0);
}}
document.querySelectorAll('.tab').forEach(tab => {{
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
}});
function toggleRow(id) {{
    document.getElementById(id).classList.toggle('open');
}}
</script>
</body>
</html>"""


# ─── COMPONENT BUILDERS ───

def _bullseye_mini(bullseye: dict, channels: list) -> str:
    score_map = {ch.get("channel", ""): ch.get("score", 0) for ch in channels}

    def ring(key, label, css_class, label_class):
        chs = bullseye.get(key, {}).get("channels", [])
        items = ""
        for ch in chs:
            s = score_map.get(ch, "?")
            items += f'<div class="ring-ch"><span>{_e(ch)}</span><span class="ring-ch-score">{s}/10</span></div>'
        return f"""<div class="ring-box {css_class}">
    <div class="ring-label {label_class}">{label}</div>
    {items}
</div>"""

    return f"""<div class="bullseye-mini">
    {ring("inner_ring", "Inner Ring — Test Now", "ring-box-inner", "ring-label-inner")}
    {ring("promising", "Promising", "ring-box-prom", "ring-label-prom")}
    {ring("long_shot", "Long Shot", "ring-box-long", "ring-label-long")}
</div>"""


def _leads_preview_table(leads: list) -> str:
    rows = ""
    for l in leads:
        name = _e(l.get("name", ""))
        title = _e(l.get("title", ""))
        platform = l.get("platform", "").lower()
        pill_cls = f"pill-{platform}" if platform in ("twitter", "linkedin", "reddit", "discord", "github", "substack") else "pill-web"
        score = l.get("score", 0)
        sc_cls = "score-hi" if score >= 8 else ("score-mid" if score >= 5 else "score-lo")
        bar_cls = "score-bar-hi" if score >= 8 else ("score-bar-mid" if score >= 5 else "score-bar-lo")
        url = l.get("url", "")
        name_html = f'<a href="{_e(url)}" target="_blank">{name}</a>' if url else name
        rows += f"""<tr>
    <td style="font-weight:500;">{name_html}</td>
    <td style="color:var(--muted);font-size:12px;">{title}</td>
    <td><span class="pill {pill_cls}">{_e(l.get("platform", ""))}</span></td>
    <td class="score-cell {sc_cls}">{score}<span class="score-bar {bar_cls}" style="width:{score*6}px"></span></td>
</tr>"""

    return f"""<div class="tbl-wrap">
<table class="tbl">
<thead><tr><th>Name</th><th>Title</th><th>Platform</th><th>Relevance</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _leads_full_table(leads: list) -> str:
    rows = ""
    for i, l in enumerate(leads):
        name = _e(l.get("name", ""))
        title = _e(l.get("title", ""))
        platform = l.get("platform", "").lower()
        pill_cls = f"pill-{platform}" if platform in ("twitter", "linkedin", "reddit", "discord", "github", "substack") else "pill-web"
        score = l.get("score", 0)
        sc_cls = "score-hi" if score >= 8 else ("score-mid" if score >= 5 else "score-lo")
        bar_cls = "score-bar-hi" if score >= 8 else ("score-bar-mid" if score >= 5 else "score-bar-lo")
        url = l.get("url", "")
        handle = _e(l.get("handle", ""))
        relevance = _e(l.get("relevance", ""))
        name_html = f'<a href="{_e(url)}" target="_blank">{name}</a>' if url else name
        rows += f"""<tr>
    <td style="font-weight:500;">{name_html}</td>
    <td style="color:var(--muted);font-size:12px;">{title}</td>
    <td><span class="pill {pill_cls}">{_e(l.get("platform", ""))}</span> <span style="color:var(--dim);font-size:11px;">{handle}</span></td>
    <td class="score-cell {sc_cls}">{score}<span class="score-bar {bar_cls}" style="width:{score*6}px"></span></td>
    <td style="font-size:12px;color:var(--muted);max-width:280px;">{relevance[:120]}{'...' if len(relevance)>120 else ''}</td>
</tr>"""

    return f"""<div class="tbl-wrap">
<table class="tbl">
<thead><tr><th>Name</th><th>Title</th><th>Platform</th><th>Score</th><th>Why They're a Lead</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _investors_preview_table(investors: list) -> str:
    rows = ""
    for inv in investors:
        name = _e(inv.get("name", ""))
        url = inv.get("url", inv.get("linkedin", ""))
        itype = inv.get("type", "").lower()
        type_cls = "type-vc" if "vc" in itype else ("type-angel" if "angel" in itype else "type-other")
        focus = _e(inv.get("focus", inv.get("relevance_signal", "")))
        name_html = f'<a href="{_e(url)}" target="_blank">{name}</a>' if url else name
        rows += f"""<tr>
    <td style="font-weight:500;">{name_html}</td>
    <td><span class="pill {type_cls}">{_e(inv.get("type", "Investor"))}</span></td>
    <td style="color:var(--muted);font-size:12px;">{focus[:80]}{'...' if len(focus)>80 else ''}</td>
</tr>"""

    return f"""<div class="tbl-wrap">
<table class="tbl">
<thead><tr><th>Investor</th><th>Type</th><th>Focus</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _competitors_table(competitors: list) -> str:
    if not competitors:
        return ""
    rows = ""
    for c in competitors:
        name = _e(c.get("name", ""))
        url = c.get("url", "")
        desc = _e(c.get("description", ""))
        funding = _e(c.get("funding", ""))
        investors = c.get("investors", [])
        inv_html = " ".join(f'<span class="pill pill-web">{_e(i)}</span>' for i in investors[:4])
        name_html = f'<a href="{_e(url)}" target="_blank">{name}</a>' if url else name
        rows += f"""<tr>
    <td style="font-weight:500;">{name_html}</td>
    <td style="font-size:12px;color:var(--muted);">{desc[:80]}</td>
    <td class="fund">{funding}</td>
    <td>{inv_html}</td>
</tr>"""

    return f"""<div class="tbl-wrap" style="margin-bottom:24px;">
<table class="tbl">
<thead><tr><th>Competitor</th><th>Description</th><th>Funding</th><th>Investors</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _investors_full_table(comp_investors: list, market_investors: list) -> str:
    rows = ""
    for inv in comp_investors:
        name = _e(inv.get("name", ""))
        url = inv.get("url", inv.get("linkedin", ""))
        itype = inv.get("type", "").lower()
        type_cls = "type-vc" if "vc" in itype else ("type-angel" if "angel" in itype else "type-other")
        focus = _e(inv.get("focus", ""))
        name_html = f'<a href="{_e(url)}" target="_blank">{name}</a>' if url else name
        rows += f"""<tr>
    <td style="font-weight:500;">{name_html}</td>
    <td><span class="pill {type_cls}">{_e(inv.get("type", ""))}</span></td>
    <td style="color:var(--muted);font-size:12px;">{focus[:120]}</td>
    <td><span class="pill pill-web">Competitor Investor</span></td>
</tr>"""

    for inv in market_investors:
        name = _e(inv.get("name", ""))
        url = inv.get("url", inv.get("linkedin", ""))
        itype = inv.get("type", "").lower()
        type_cls = "type-vc" if "vc" in itype else ("type-angel" if "angel" in itype else "type-other")
        focus = _e(inv.get("focus", ""))
        name_html = f'<a href="{_e(url)}" target="_blank">{name}</a>' if url else name
        rows += f"""<tr>
    <td style="font-weight:500;">{name_html}</td>
    <td><span class="pill {type_cls}">{_e(inv.get("type", ""))}</span></td>
    <td style="color:var(--muted);font-size:12px;">{focus[:120]}</td>
    <td><span class="pill" style="background:var(--orange-bg);color:var(--orange);">Market Investor</span></td>
</tr>"""

    return f"""<div class="tbl-wrap">
<table class="tbl">
<thead><tr><th>Investor</th><th>Type</th><th>Focus / Thesis</th><th>Source</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _channels_table(channels: list) -> str:
    rows = ""
    for i, ch in enumerate(channels):
        name = _e(ch.get("channel", ""))
        score = ch.get("score", 0)
        effort = _e(ch.get("effort", ""))
        timeline = _e(ch.get("timeline", ""))
        budget = _e(ch.get("budget", ""))
        sc_cls = "score-hi" if score >= 7 else ("score-mid" if score >= 5 else "score-lo")
        bar_cls = "score-bar-hi" if score >= 7 else ("score-bar-mid" if score >= 5 else "score-bar-lo")

        insight = _e(ch.get("killer_insight", ""))
        first_move = _e(ch.get("first_move", ""))
        ideas = ch.get("specific_ideas", [])
        why = _e(ch.get("why_or_why_not", ""))

        ideas_html = ""
        for idea in ideas[:3]:
            ideas_html += f'<div class="ch-idea">{_e(idea)}</div>'

        detail_id = f"ch-detail-{i}"

        rows += f"""<tr style="cursor:pointer;" onclick="toggleRow('{detail_id}')">
    <td style="font-weight:500;">{name}</td>
    <td class="score-cell {sc_cls}">{score}/10 <span class="score-bar {bar_cls}" style="width:{score*8}px"></span></td>
    <td style="font-size:12px;color:var(--muted);">{effort}</td>
    <td style="font-size:12px;color:var(--muted);">{timeline}</td>
    <td style="font-size:12px;color:var(--muted);">{budget}</td>
    <td style="font-size:11px;color:var(--dim);">▼</td>
</tr>
<tr class="ch-expand" id="{detail_id}">
    <td colspan="6">
        <div class="ch-detail-grid">
            <div>
                <div class="ch-insight-box">
                    <div class="ch-insight-label">Key Insight</div>
                    {insight}
                </div>
                <div style="margin-top:8px;">
                    <div class="ch-insight-label" style="font-size:10px;font-weight:700;color:var(--green);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">First Move</div>
                    <div style="font-size:12px;color:var(--text2);">{first_move}</div>
                </div>
            </div>
            <div>
                <div class="ch-insight-label" style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">Ideas</div>
                {ideas_html}
                <div style="margin-top:8px;font-size:12px;color:var(--dim);">{why}</div>
            </div>
        </div>
    </td>
</tr>"""

    return f"""<div class="tbl-wrap">
<table class="tbl">
<thead><tr><th>Channel</th><th>Score</th><th>Effort</th><th>Timeline</th><th>Budget</th><th></th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _personas_section(personas: list) -> str:
    if not personas:
        return ""
    cards = ""
    for p in personas:
        name = _e(p.get("name", ""))
        desc = _e(p.get("description", p.get("who", "")))
        platforms = p.get("platforms", p.get("social_networks", []))
        nets_html = ""
        for net in platforms:
            n = _e(net) if isinstance(net, str) else _e(net.get("name", ""))
            nc = f"pill-{n.lower()}" if n.lower() in ("twitter", "linkedin", "reddit", "discord", "github", "substack") else "pill-web"
            nets_html += f'<span class="pill {nc}">{n}</span> '
        signals = ""
        for sig in p.get("pain_signals", [])[:3]:
            signals += f'<div class="p-signal">{_e(sig)}</div>'
        cards += f"""<div class="p-card">
    <div class="p-name">{name}</div>
    <div class="p-desc">{desc}</div>
    <div class="p-nets">{nets_html}</div>
    {signals}
</div>"""

    return f'<div class="persona-row">{cards}</div>'


def _plan_section(plan: dict) -> str:
    boxes = ""
    for key in ["month_1", "month_2", "month_3"]:
        m = plan.get(key, {})
        label = key.replace("_", " ").title()
        focus = _e(m.get("focus", ""))
        target = _e(m.get("target_metric", ""))
        bgt = _e(m.get("budget", ""))
        actions = ""
        for a in m.get("actions", []):
            actions += f'<div class="plan-action">{_e(a)}</div>'
        boxes += f"""<div class="plan-box">
    <div class="plan-month">{label}</div>
    <div class="plan-focus">{focus}</div>
    {f'<div class="plan-metric">Target: {target}</div>' if target else ''}
    {f'<div class="plan-budget">Budget: {bgt}</div>' if bgt else ''}
    {actions}
</div>"""

    return f'<div class="plan-cols">{boxes}</div>'


def _budget_table(budget: dict) -> str:
    total = _e(budget.get("total_recommended", ""))
    rows = ""
    for item in budget.get("breakdown", []):
        rows += f"""<tr>
    <td style="font-weight:500;">{_e(item.get('channel', ''))}</td>
    <td class="fund">{_e(item.get('amount', ''))}</td>
    <td style="font-size:12px;color:var(--muted);">{_e(item.get('rationale', ''))}</td>
</tr>"""

    return f"""<div class="tbl-wrap" style="margin-bottom:24px;">
<table class="tbl">
<thead><tr><th>Channel</th><th>Amount</th><th>Rationale</th></tr></thead>
<tbody>{rows}</tbody>
</table>
{f'<div style="text-align:center;padding:10px;font-size:13px;color:var(--green);font-weight:600;border-top:1px solid var(--border);">Total Recommended: {total}</div>' if total else ''}
</div>"""


def _risk_table(risks: list) -> str:
    if not risks:
        return ""
    rows = ""
    for r in risks:
        prob = r.get("probability", "")
        impact = r.get("impact", "")
        pc = "score-hi" if prob == "high" else ("score-mid" if prob == "medium" else "score-lo")
        ic = "score-hi" if impact == "high" else ("score-mid" if impact == "medium" else "score-lo")
        # Use red for high probability/impact
        pc_style = "color:var(--red)" if prob == "high" else ("color:var(--yellow)" if prob == "medium" else "color:var(--green)")
        ic_style = "color:var(--red)" if impact == "high" else ("color:var(--yellow)" if impact == "medium" else "color:var(--green)")
        rows += f"""<tr>
    <td style="font-size:12px;">{_e(r.get('risk', ''))}</td>
    <td style="font-weight:600;{pc_style}">{_e(prob)}</td>
    <td style="font-weight:600;{ic_style}">{_e(impact)}</td>
    <td style="font-size:12px;color:var(--muted);">{_e(r.get('mitigation', ''))}</td>
</tr>"""

    return f"""<div class="tbl-wrap" style="margin-bottom:24px;">
<table class="tbl">
<thead><tr><th>Risk</th><th>Probability</th><th>Impact</th><th>Mitigation</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _moat_box(moat: str) -> str:
    if not moat:
        return ""
    return f"""<div class="sh"><div class="sh-title">Competitive Moat</div></div>
<div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:20px;margin-bottom:24px;">
    <div style="font-family:'EB Garamond',serif;font-size:15px;line-height:1.7;color:var(--text2);font-style:italic;">{_e(moat)}</div>
</div>"""


def _pricing_cards() -> str:
    return """<div class="pricing-grid">
    <div class="price-card">
        <div class="price-tier">Free</div>
        <div class="price-amt">$0</div>
        <div class="price-desc">See what we found</div>
        <div class="price-feat">Top channels + scores</div>
        <div class="price-feat">Executive summary</div>
        <div class="price-feat">10 leads (names + platforms)</div>
        <div class="price-feat">10 investors (names + type)</div>
        <div class="price-feat">Competitor funding data</div>
    </div>
    <div class="price-card pop">
        <div class="pop-tag">Most Popular</div>
        <div class="price-tier">Starter</div>
        <div class="price-amt">$39<span class="price-per">/mo</span></div>
        <div class="price-desc">Full strategy playbook</div>
        <div class="price-feat">Everything in Free</div>
        <div class="price-feat">19-channel deep analysis</div>
        <div class="price-feat">90-day action plan</div>
        <div class="price-feat">Budget allocation</div>
        <div class="price-feat">Risk matrix</div>
        <div class="price-feat">3 customer personas</div>
        <div class="price-feat">Lead outreach strategies</div>
        <div class="price-feat">Monthly market updates</div>
        <div style="margin-top:12px;"><a href="#" class="btn btn-green">Get Started</a></div>
    </div>
    <div class="price-card ug">
        <div class="price-tier">Growth</div>
        <div class="price-amt">$200<span class="price-per">/mo</span></div>
        <div class="price-desc">Full intelligence suite</div>
        <div class="price-feat">Everything in Starter</div>
        <div class="price-feat">Investor deep profiles</div>
        <div class="price-feat">Competitor deep analysis</div>
        <div class="price-feat">Weekly market updates</div>
        <div class="price-feat">Custom outreach templates</div>
        <div class="price-feat">Warm intro path mapping</div>
        <div style="margin-top:12px;"><a href="#" class="btn btn-orange">Upgrade</a></div>
    </div>
    <div class="price-card">
        <div class="price-tier">Enterprise</div>
        <div class="price-amt" style="font-size:22px;">Custom</div>
        <div class="price-desc">White-glove service</div>
        <div class="price-feat">Everything in Growth</div>
        <div class="price-feat">Custom analysis scope</div>
        <div class="price-feat">Direct strategy calls</div>
        <div class="price-feat">Multi-product analysis</div>
        <div class="price-feat">Dedicated analyst</div>
        <div style="margin-top:12px;"><a href="mailto:emi@mckoutie.com" class="btn btn-outline">Contact Us</a></div>
    </div>
</div>"""
