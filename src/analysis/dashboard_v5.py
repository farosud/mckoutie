"""
Dashboard v5 — Formal BI-style consulting dashboard.

Design language:
  - Clean, data-dense, spreadsheet-forward
  - No tabs — single scrollable page, sections anchored in a left nav
  - Spreadsheet-like tables for leads & investors (the star of the show)
  - "Living report" emphasis — timestamps, update indicators, activity feed
  - Muted palette: charcoal + slate + accent green for scores
  - Inter for text, JetBrains Mono for numbers
"""

from html import escape
from datetime import datetime, timezone
import json as _json


def render_dashboard_v5(
    analysis: dict,
    startup_name: str,
    report_id: str,
    tier: str = "free",
    checkout_url: str = "#",
    upgrade_url: str = "#",
    logged_in: bool = True,
    login_url: str = "",
    streaming: bool = False,
    sse_base_url: str = "",
) -> str:
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

    sorted_ch = sorted(channels, key=lambda c: c.get("score", 0), reverse=True)
    top_score = sorted_ch[0].get("score", 0) if sorted_ch else 0
    top_channel = sorted_ch[0].get("channel", "") if sorted_ch else ""
    avg_score = round(sum(c.get("score", 0) for c in channels) / max(len(channels), 1), 1)
    leads = leads_data.get("leads", [])
    personas = leads_data.get("personas", [])
    competitors = investors_data.get("competitors", [])
    comp_investors = investors_data.get("competitor_investors", [])
    mkt_investors = investors_data.get("market_investors", [])
    all_investors = comp_investors + mkt_investors

    inner = bullseye.get("inner_ring", {}).get("channels", [])
    promising = bullseye.get("promising", {}).get("channels", [])

    # For skeleton reports with quick analysis, extract top channels
    top_3 = analysis.get("top_3_channels", [])

    now = datetime.now(tz=timezone.utc)
    now_str = now.strftime("%b %d, %Y · %H:%M UTC")
    date_short = now.strftime("%b %d")

    streaming_banner = ""
    if streaming:
        streaming_banner = """
<div id="streaming-banner" style="
    position:fixed; top:0; left:0; right:0; z-index:9999;
    background:linear-gradient(90deg,#0d1117,#1a2332,#0d1117);
    border-bottom:2px solid #00d4ff;
    padding:10px 24px;
    font-family:'Inter',sans-serif;
    animation:banner-glow 2s ease-in-out infinite;
">
    <div style="display:flex;align-items:center;gap:12px;">
        <div style="
            width:12px;height:12px;border-radius:50%;
            background:#00d4ff;
            animation:pulse-dot 1.5s ease-in-out infinite;
        "></div>
        <span id="streaming-status" style="color:#e0e0e0;font-size:13px;font-weight:500;flex:1;">
            Connecting to deep analysis engine...
        </span>
        <div style="display:flex;gap:6px;align-items:center;" id="streaming-progress">
            <span class="pip-label" style="font-size:10px;color:#666;margin-right:2px;">CH</span>
            <span class="progress-pip" data-section="channels" style="width:8px;height:8px;border-radius:50%;background:#333;transition:all 0.3s;"></span>
            <span class="pip-label" style="font-size:10px;color:#666;margin-left:4px;margin-right:2px;">LEADS</span>
            <span class="progress-pip" data-section="leads" style="width:8px;height:8px;border-radius:50%;background:#333;transition:all 0.3s;"></span>
            <span class="pip-label" style="font-size:10px;color:#666;margin-left:4px;margin-right:2px;">INV</span>
            <span class="progress-pip" data-section="investors" style="width:8px;height:8px;border-radius:50%;background:#333;transition:all 0.3s;"></span>
            <span class="pip-label" style="font-size:10px;color:#666;margin-left:4px;margin-right:2px;">PLAN</span>
            <span class="progress-pip" data-section="strategy" style="width:8px;height:8px;border-radius:50%;background:#333;transition:all 0.3s;"></span>
            <span class="pip-label" style="font-size:10px;color:#666;margin-left:4px;margin-right:2px;">AI</span>
            <span class="progress-pip" data-section="advisor" style="width:8px;height:8px;border-radius:50%;background:#333;transition:all 0.3s;"></span>
        </div>
    </div>
    <div id="thinking-detail" style="
        margin-top:4px; padding-left:24px;
        font-size:11px; color:#555; font-style:italic;
        height:16px; overflow:hidden; transition:all 0.3s;
    "></div>
    <div id="activity-log" style="
        margin-top:2px; padding-left:24px;
        max-height:0; overflow:hidden; transition:max-height 0.4s ease;
    "></div>
</div>
<style>
@keyframes banner-glow {
    0%,100% { box-shadow: 0 2px 20px rgba(0,212,255,0.1); }
    50% { box-shadow: 0 2px 30px rgba(0,212,255,0.25); }
}
@keyframes pulse-dot {
    0%,100% { opacity:1; transform:scale(1); }
    50% { opacity:0.5; transform:scale(0.8); }
}
@keyframes fade-in-row {
    from { opacity:0; transform:translateY(8px); }
    to { opacity:1; transform:translateY(0); }
}
.row-animate { animation: fade-in-row 0.4s ease-out forwards; }
body { padding-top: 60px !important; }
</style>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_e(startup_name)} — mckoutie & company</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{_css()}</style>
{_login_overlay_css() if not logged_in else ""}
</head>
<body{' class="login-gated"' if not logged_in else ''}>

{streaming_banner}
{_login_overlay(startup_name, login_url) if not logged_in else ""}
{_header(startup_name, now_str, tier, report_id)}

<div class="shell">
  {_nav(len(leads), len(all_investors), len(sorted_ch))}
  <main class="content">
    {_section_kpis(top_score, top_channel, avg_score, len(leads), len(all_investors), len(competitors))}
    {_section_executive(exec_summary, hot_take)}
    {_section_bullseye(inner, promising, sorted_ch)}
    {_section_channels(sorted_ch, tier)}
    {_section_leads(leads, personas, tier, checkout_url, date_short)}
    {_section_investors(competitors, comp_investors, mkt_investors, tier, upgrade_url, date_short)}
    {_section_strategy(plan, budget, risks, moat, tier, checkout_url)}
    {_section_footer(startup_name)}
  </main>
</div>

{_chat_widget_html(report_id)}

<script>
var __REPORT_DATA__={_report_json(analysis, startup_name, report_id, tier)};
var __STREAMING__={'true' if streaming else 'false'};
var __REPORT_ID__="{report_id}";
var __TIER__="{tier}";
var __SSE_BASE__="{sse_base_url}";
{_js()}
{_streaming_js() if streaming else ""}
{_chat_widget_js(report_id)}
</script>
</body>
</html>"""


def _e(t):
    return escape(str(t)) if t else ""


def _login_overlay_css():
    return """<style>
body.login-gated .shell, body.login-gated > header {
    filter: blur(6px);
    pointer-events: none;
    user-select: none;
}
.login-overlay {
    position: fixed; inset: 0; z-index: 9999;
    display: flex; align-items: center; justify-content: center;
    background: rgba(11,13,16,.7);
    backdrop-filter: blur(2px);
}
.login-box {
    background: var(--panel, #111318);
    border: 1px solid var(--border2, #2a2f3d);
    border-radius: 16px;
    padding: 48px 40px 40px;
    max-width: 440px; width: 90%;
    text-align: center;
    box-shadow: 0 24px 80px rgba(0,0,0,.6);
    animation: loginSlide .4s ease-out;
}
@keyframes loginSlide {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
}
.login-box .logo {
    font-family: 'EB Garamond', 'Georgia', serif;
    font-size: 1.6rem; font-weight: 600;
    color: var(--white, #eaedf3);
    letter-spacing: .02em;
    margin-bottom: 4px;
}
.login-box .logo span { color: var(--cyan, #17c3b2); font-style: italic; }
.login-box .subtitle {
    font-family: 'Inter', sans-serif;
    font-size: .75rem; text-transform: uppercase;
    letter-spacing: .12em; color: var(--text3, #4e5568);
    margin-bottom: 28px;
}
.login-box .brief-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem; font-weight: 600;
    color: var(--accent, #4f8af7);
    margin-bottom: 8px;
}
.login-box .brief-desc {
    font-family: 'Inter', sans-serif;
    font-size: .88rem; color: var(--text2, #7d849a);
    line-height: 1.5; margin-bottom: 32px;
}
.login-box .twitter-btn {
    display: inline-flex; align-items: center; gap: 10px;
    background: #1d9bf0; color: #fff;
    font-family: 'Inter', sans-serif;
    font-size: .95rem; font-weight: 600;
    padding: 14px 36px;
    border: none; border-radius: 8px;
    text-decoration: none; cursor: pointer;
    transition: background .15s, transform .1s;
}
.login-box .twitter-btn:hover { background: #0c85d0; transform: translateY(-1px); }
.login-box .twitter-btn svg { width: 20px; height: 20px; fill: currentColor; }
.login-box .fine-print {
    margin-top: 20px;
    font-family: 'Inter', sans-serif;
    font-size: .72rem; color: var(--text3, #4e5568);
    line-height: 1.4;
}
</style>"""


def _login_overlay(startup_name: str, login_url: str):
    return f"""<div class="login-overlay">
  <div class="login-box">
    <div class="logo">mckoutie <span>&amp;</span> company</div>
    <div class="subtitle">strategy intelligence</div>
    <div class="brief-name">Strategy Brief: {_e(startup_name)}</div>
    <div class="brief-desc">Your full traction analysis is ready.<br>Sign in with X to view your report.</div>
    <a class="twitter-btn" href="{_e(login_url)}">
      <svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
      Sign in with X
    </a>
    <div class="fine-print">We only verify your identity. We don't post or read your DMs.<br>Your data stays private.</div>
  </div>
</div>"""


# ═══════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════
def _css():
    return """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0b0d10;
  --panel:#111318;
  --surface:#161920;
  --surface2:#1c2028;
  --surface3:#22262e;
  --border:#1e2230;
  --border2:#2a2f3d;
  --border3:#353b4a;
  --text:#c8cdd8;
  --text2:#7d849a;
  --text3:#4e5568;
  --white:#eaedf3;
  --accent:#4f8af7;
  --accent-soft:rgba(79,138,247,.12);
  --green:#2ecc71;
  --green-soft:rgba(46,204,113,.1);
  --amber:#e6a23c;
  --amber-soft:rgba(230,162,60,.1);
  --red:#e74c3c;
  --red-soft:rgba(231,76,60,.1);
  --cyan:#17c3b2;
  --purple:#a78bfa;
  --radius:4px;
  --mono:'JetBrains Mono',monospace;
  --sans:'Inter',-apple-system,system-ui,sans-serif;
}
html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg);color:var(--text);line-height:1.5;font-size:13px;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
::selection{background:var(--accent);color:var(--white)}

/* ── Header ── */
.header{
  display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;height:48px;
  background:var(--panel);border-bottom:1px solid var(--border);
  position:sticky;top:0;z-index:200;
}
.header-left{display:flex;align-items:center;gap:16px}
.logo{font-family:var(--mono);font-weight:600;font-size:13px;color:var(--text2);letter-spacing:-.3px}
.logo b{color:var(--white);font-weight:700}
.logo span{color:var(--accent)}
.hdr-sep{width:1px;height:20px;background:var(--border2)}
.hdr-company{font-weight:600;font-size:14px;color:var(--white)}
.header-right{display:flex;align-items:center;gap:16px}
.live-badge{
  display:flex;align-items:center;gap:6px;
  padding:3px 10px;border-radius:12px;
  background:var(--green-soft);font-size:11px;font-weight:500;color:var(--green);
}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.hdr-time{font-size:11px;color:var(--text3);font-family:var(--mono)}
.hdr-id{font-size:10px;color:var(--text3);font-family:var(--mono);padding:2px 6px;background:var(--surface);border-radius:3px}
.tier-badge{font-size:10px;padding:2px 8px;border-radius:3px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.tier-free{background:var(--surface3);color:var(--text2)}
.tier-starter{background:var(--accent-soft);color:var(--accent)}
.tier-growth{background:rgba(167,139,250,.12);color:var(--purple)}

/* ── Shell ── */
.shell{display:flex;min-height:calc(100vh - 48px)}

/* ── Nav ── */
.nav{
  width:200px;background:var(--panel);border-right:1px solid var(--border);
  padding:16px 0;position:sticky;top:48px;height:calc(100vh - 48px);
  overflow-y:auto;flex-shrink:0;display:flex;flex-direction:column;
}
.nav-group{margin-bottom:20px}
.nav-label{font-size:9px;text-transform:uppercase;letter-spacing:1.2px;color:var(--text3);padding:0 16px;margin-bottom:6px;font-weight:600}
.nav-link{
  display:flex;align-items:center;justify-content:space-between;
  padding:6px 16px;font-size:12px;color:var(--text2);cursor:pointer;
  border-left:2px solid transparent;transition:all .1s;text-decoration:none;
}
.nav-link:hover{color:var(--white);background:var(--surface);text-decoration:none}
.nav-link.active{color:var(--white);border-left-color:var(--accent);background:var(--surface)}
.nav-count{font-size:10px;font-family:var(--mono);color:var(--text3);background:var(--surface2);padding:1px 5px;border-radius:3px}

/* ── Content ── */
.content{flex:1;padding:24px 32px;max-width:1200px;overflow-y:auto}

/* ── KPI Row ── */
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:28px}
.kpi{
  background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px;position:relative;
}
.kpi-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--text3);margin-bottom:8px;font-weight:500}
.kpi-value{font-size:28px;font-weight:700;font-family:var(--mono);color:var(--white);line-height:1}
.kpi-sub{font-size:11px;color:var(--text2);margin-top:4px}
.kpi-accent .kpi-value{color:var(--green)}
.kpi-blue .kpi-value{color:var(--accent)}
.kpi-amber .kpi-value{color:var(--amber)}
.kpi-cyan .kpi-value{color:var(--cyan)}

/* ── Section ── */
.section{margin-bottom:36px;scroll-margin-top:64px}
.section-header{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border);
}
.section-title{font-size:15px;font-weight:600;color:var(--white);display:flex;align-items:center;gap:8px}
.section-title .icon{font-size:14px;opacity:.6}
.update-badge{
  display:inline-flex;align-items:center;gap:5px;
  font-size:10px;color:var(--green);font-weight:500;
  padding:2px 8px;border-radius:10px;background:var(--green-soft);
}
.update-badge .dot{width:5px;height:5px;border-radius:50%;background:var(--green)}

/* ── Executive / Hot Take ── */
.exec-grid{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:28px}
.exec-box{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:20px}
.exec-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--text3);margin-bottom:10px;font-weight:500}
.exec-text{font-size:13px;color:var(--text);line-height:1.7}
.hottake-box{
  background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
  padding:20px;border-left:3px solid var(--amber);
}
.hottake-box .exec-label{color:var(--amber)}
.hottake-box .exec-text{color:var(--text);font-style:italic}

/* ── Bullseye ── */
.bullseye-row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.ring-card{
  background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px;border-top:3px solid var(--border2);
}
.ring-card.inner{border-top-color:var(--green)}
.ring-card.promising{border-top-color:var(--amber)}
.ring-card.longshot{border-top-color:var(--text3)}
.ring-title{font-size:11px;text-transform:uppercase;letter-spacing:.8px;font-weight:600;margin-bottom:10px}
.ring-card.inner .ring-title{color:var(--green)}
.ring-card.promising .ring-title{color:var(--amber)}
.ring-card.longshot .ring-title{color:var(--text3)}
.ring-items{list-style:none;font-size:12px;color:var(--text2)}
.ring-items li{padding:3px 0;display:flex;align-items:center;gap:6px}
.ring-items li::before{content:'';width:4px;height:4px;border-radius:50%;flex-shrink:0}
.ring-card.inner .ring-items li::before{background:var(--green)}
.ring-card.promising .ring-items li::before{background:var(--amber)}
.ring-card.longshot .ring-items li::before{background:var(--text3)}

/* ── Data Table (spreadsheet) ── */
.data-table-wrap{
  background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
  overflow:hidden;
}
.data-table{width:100%;border-collapse:collapse;font-size:12px}
.data-table thead{background:var(--surface2)}
.data-table th{
  padding:10px 14px;text-align:left;font-weight:600;color:var(--text2);
  font-size:10px;text-transform:uppercase;letter-spacing:.6px;
  border-bottom:1px solid var(--border2);white-space:nowrap;
  position:sticky;top:0;background:var(--surface2);
  user-select:none;cursor:default;
}
.data-table th.sortable{cursor:pointer}
.data-table th.sortable:hover{color:var(--white)}
.data-table td{
  padding:10px 14px;border-bottom:1px solid var(--border);
  color:var(--text);vertical-align:middle;
}
.data-table tbody tr{transition:background .08s}
.data-table tbody tr:hover{background:var(--surface)}
.data-table tbody tr:last-child td{border-bottom:none}

/* Cell types */
.cell-rank{font-family:var(--mono);font-size:11px;color:var(--text3);width:36px;text-align:center}
.cell-name{font-weight:600;color:var(--white);white-space:nowrap}
.cell-name a{color:var(--white)}
.cell-name a:hover{color:var(--accent)}
.cell-score{font-family:var(--mono);font-weight:600}
.cell-tag{
  display:inline-block;padding:2px 8px;border-radius:3px;
  font-size:10px;font-weight:500;white-space:nowrap;
}
.cell-muted{color:var(--text2);font-size:11px}
.cell-desc{color:var(--text2);font-size:11px;max-width:320px;line-height:1.4}

/* Score bar */
.score-bar{display:flex;align-items:center;gap:8px;min-width:120px}
.score-track{flex:1;height:5px;border-radius:3px;background:var(--surface3);overflow:hidden}
.score-fill{height:100%;border-radius:3px;transition:width .3s}
.score-label{font-family:var(--mono);font-size:12px;font-weight:600;min-width:22px;text-align:right}

/* Platform tags */
.tag-twitter{background:#1a2d4a;color:#5b9aef}
.tag-linkedin{background:#1a2d4a;color:#4a9be8}
.tag-reddit{background:#3a1e1e;color:#e87461}
.tag-discord{background:#2d1f4a;color:#9b8be0}
.tag-github{background:#1e2428;color:#b0b8c4}
.tag-substack{background:#3a2a1a;color:#e8a04a}
.tag-vc{background:#1a3a2a;color:#4ade80}
.tag-angel{background:#3a3a1a;color:#e8d04a}
.tag-market{background:#1a2a3a;color:#4abce8}
.tag-competitor{background:#3a1a2a;color:#e84a8a}

/* ── Persona Strip ── */
.persona-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.persona-card{
  background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px;
}
.persona-name{font-size:13px;font-weight:600;color:var(--white);margin-bottom:4px}
.persona-desc{font-size:11px;color:var(--text2);line-height:1.5;margin-bottom:10px}
.persona-tags{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px}
.persona-signals{list-style:none;font-size:11px;color:var(--text3)}
.persona-signals li{padding:2px 0}
.persona-signals li::before{content:'→ ';color:var(--text3)}

/* ── Competitor Cards ── */
.comp-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px}
.comp-card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:14px}
.comp-name{font-size:13px;font-weight:600;color:var(--white);margin-bottom:2px}
.comp-name a{color:var(--white)}
.comp-funding{font-size:18px;font-weight:700;font-family:var(--mono);color:var(--green);margin:4px 0}
.comp-desc{font-size:11px;color:var(--text3);margin-bottom:6px}
.comp-investors-list{font-size:11px;color:var(--text2)}

/* ── Strategy ── */
.plan-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px}
.plan-card{
  background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
  padding:18px;position:relative;
}
.plan-month-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--accent);font-weight:600;margin-bottom:4px}
.plan-focus{font-size:14px;font-weight:600;color:var(--white);margin-bottom:10px;line-height:1.3}
.plan-actions{list-style:none;font-size:11px;color:var(--text2);margin-bottom:10px}
.plan-actions li{padding:3px 0;padding-left:14px;position:relative}
.plan-actions li::before{content:'›';position:absolute;left:0;color:var(--text3);font-weight:700}
.plan-metric{font-size:11px;color:var(--green);font-weight:500;margin-bottom:2px}
.plan-budget{font-size:11px;color:var(--text3);font-family:var(--mono)}

/* ── Lock/CTA ── */
.lock-card{
  background:var(--surface);border:1px dashed var(--border2);border-radius:var(--radius);
  padding:28px;text-align:center;
}
.lock-title{font-size:14px;font-weight:600;color:var(--white);margin-bottom:6px}
.lock-desc{font-size:12px;color:var(--text2);margin-bottom:14px;max-width:400px;margin-left:auto;margin-right:auto}
.cta-btn{
  display:inline-block;padding:8px 24px;background:var(--accent);color:var(--white);
  border:none;border-radius:var(--radius);font-size:12px;font-weight:600;
  cursor:pointer;font-family:var(--sans);transition:all .12s;text-decoration:none;
}
.cta-btn:hover{background:#3a75e0;text-decoration:none}
.cta-btn.purple{background:var(--purple)}
.cta-btn.purple:hover{background:#8b6ce0}

/* ── Footer ── */
.footer{
  margin-top:40px;padding:24px 0;border-top:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
}
.footer-left{font-size:11px;color:var(--text3)}
.footer-right{font-size:11px;color:var(--text3);font-family:var(--mono)}

/* ── Responsive ── */
@media(max-width:1024px){
  .nav{display:none}
  .kpis{grid-template-columns:repeat(3,1fr)}
  .exec-grid{grid-template-columns:1fr}
  .bullseye-row{grid-template-columns:1fr}
  .plan-grid{grid-template-columns:1fr}
  .persona-strip{grid-template-columns:1fr}
  .content{padding:16px}
}
@media(max-width:640px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .header{padding:0 12px}
  .hdr-id,.hdr-time{display:none}
}

/* ── Channel Accordion ── */
.ch-row{cursor:pointer;transition:background .08s}
.ch-row:hover{background:var(--surface)}
.ch-row td:first-child::before{content:'';display:inline-block;width:0;height:0;border:4px solid transparent;border-left:5px solid var(--text3);margin-right:6px;transition:transform .2s;vertical-align:middle}
.ch-row.open td:first-child::before{transform:rotate(90deg)}
.ch-expand{display:none;background:var(--surface)}
.ch-expand.open{display:table-row}
.ch-expand-inner{padding:20px 24px}
.ch-actions-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:20px}
.ch-action-card{
  background:var(--panel);border:1px solid var(--border2);border-radius:var(--radius);
  padding:16px;border-top:2px solid var(--accent);
}
.ch-action-num{font-size:10px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.ch-action-title{font-size:13px;font-weight:600;color:var(--white);margin-bottom:8px;line-height:1.3}
.ch-action-desc{font-size:11px;color:var(--text2);line-height:1.5;margin-bottom:10px}
.ch-action-result{font-size:10px;color:var(--green);font-weight:500;padding:6px 10px;background:var(--green-soft);border-radius:var(--radius)}
.ch-research-title{font-size:11px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:10px}
.ch-research-table{width:100%;border-collapse:collapse;font-size:11px;margin-bottom:0}
.ch-research-table th{
  padding:8px 12px;text-align:left;font-weight:600;color:var(--text3);
  font-size:10px;text-transform:uppercase;letter-spacing:.5px;
  border-bottom:1px solid var(--border2);background:var(--surface2);
}
.ch-research-table td{
  padding:8px 12px;border-bottom:1px solid var(--border);color:var(--text);
}
.ch-research-table tbody tr:last-child td{border-bottom:none}
.ch-research-table tbody tr:hover{background:var(--surface2)}
.ch-research-wrap{background:var(--panel);border:1px solid var(--border2);border-radius:var(--radius);overflow:hidden}
@media(max-width:1024px){.ch-actions-grid{grid-template-columns:1fr}}

/* ── Download button ── */
.dl-btn{
  display:flex;align-items:center;gap:6px;width:calc(100% - 24px);margin:0 12px;
  padding:8px 12px;background:var(--surface2);border:1px solid var(--border2);
  border-radius:var(--radius);color:var(--text2);font-size:11px;font-weight:500;
  font-family:var(--sans);cursor:pointer;transition:all .12s;
}
.dl-btn:hover{background:var(--surface3);color:var(--white);border-color:var(--accent)}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--border3)}
"""


# ═══════════════════════════════════════════════
# Components
# ═══════════════════════════════════════════════

def _header(name, now_str, tier, report_id):
    tc = f"tier-{tier}"
    return f"""
<div class="header">
  <div class="header-left">
    <div class="logo"><b>mckoutie</b><span>&</span>company</div>
    <div class="hdr-sep"></div>
    <div class="hdr-company">{_e(name)}</div>
  </div>
  <div class="header-right">
    <div class="live-badge"><span class="live-dot"></span> Living Report</div>
    <span class="hdr-time">{_e(now_str)}</span>
    <span class="hdr-id">{_e(report_id[:12])}</span>
    <span class="tier-badge {tc}">{_e(tier)}</span>
  </div>
</div>"""


def _nav(n_leads, n_investors, n_channels):
    return f"""
<nav class="nav">
  <div class="nav-group">
    <div class="nav-label">Report</div>
    <a href="#kpis" class="nav-link active">Dashboard</a>
    <a href="#executive" class="nav-link">Executive Summary</a>
    <a href="#bullseye" class="nav-link">Bullseye</a>
  </div>
  <div class="nav-group">
    <div class="nav-label">Analysis</div>
    <a href="#channels" class="nav-link">Channels <span class="nav-count">{n_channels}</span></a>
    <a href="#leads" class="nav-link">Leads <span class="nav-count">{n_leads}</span></a>
    <a href="#investors" class="nav-link">Investors <span class="nav-count">{n_investors}</span></a>
  </div>
  <div class="nav-group">
    <div class="nav-label">Strategy</div>
    <a href="#plan" class="nav-link">90-Day Plan</a>
    <a href="#budget" class="nav-link">Budget</a>
    <a href="#risks" class="nav-link">Risk Matrix</a>
  </div>
  <div class="nav-group" style="margin-top:auto;padding-top:16px;border-top:1px solid var(--border)">
    <button class="dl-btn" onclick="downloadMd()" title="Download full report as Markdown">
      <span style="font-size:14px">&#8615;</span> Download .md
    </button>
  </div>
</nav>"""


def _section_kpis(top_score, top_channel, avg, n_leads, n_inv, n_comp):
    return f"""
<div class="section" id="kpis">
  <div class="kpis">
    <div class="kpi kpi-accent">
      <div class="kpi-label">Top Score</div>
      <div class="kpi-value">{top_score}<span style="font-size:14px;color:var(--text3)">/10</span></div>
      <div class="kpi-sub">{_e(top_channel)}</div>
    </div>
    <div class="kpi kpi-blue">
      <div class="kpi-label">Avg Score</div>
      <div class="kpi-value">{avg}</div>
      <div class="kpi-sub">across all channels</div>
    </div>
    <div class="kpi kpi-cyan">
      <div class="kpi-label">Leads Found</div>
      <div class="kpi-value">{n_leads}</div>
      <div class="kpi-sub">potential customers</div>
    </div>
    <div class="kpi kpi-amber">
      <div class="kpi-label">Investors</div>
      <div class="kpi-value">{n_inv}</div>
      <div class="kpi-sub">relevant to your space</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Competitors</div>
      <div class="kpi-value">{n_comp}</div>
      <div class="kpi-sub">mapped</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Channels</div>
      <div class="kpi-value">19</div>
      <div class="kpi-sub">analyzed</div>
    </div>
  </div>
</div>"""


def _section_executive(summary, hot_take):
    return f"""
<div class="section" id="executive">
  <div class="section-header">
    <div class="section-title">Executive Summary</div>
  </div>
  <div class="exec-grid">
    <div class="exec-box">
      <div class="exec-label">Analysis</div>
      <div class="exec-text">{_e(summary)}</div>
    </div>
    <div class="hottake-box">
      <div class="exec-label">Hot Take</div>
      <div class="exec-text">{_e(hot_take)}</div>
    </div>
  </div>
</div>"""


def _section_bullseye(inner, promising, channels):
    longshot = [c.get("channel", "") for c in channels
                if c.get("channel", "") not in inner and c.get("channel", "") not in promising]

    def _items(lst):
        return "".join(f"<li>{_e(c)}</li>" for c in lst)

    return f"""
<div class="section" id="bullseye">
  <div class="section-header">
    <div class="section-title">Bullseye Framework</div>
  </div>
  <div class="bullseye-row">
    <div class="ring-card inner">
      <div class="ring-title">Inner Ring — Do Now</div>
      <ul class="ring-items">{_items(inner)}</ul>
    </div>
    <div class="ring-card promising">
      <div class="ring-title">Promising — Test Next</div>
      <ul class="ring-items">{_items(promising)}</ul>
    </div>
    <div class="ring-card longshot">
      <div class="ring-title">Long Shot — Later</div>
      <ul class="ring-items">{_items(longshot[:6])}</ul>
    </div>
  </div>
</div>"""


def _section_channels(channels, tier):
    rows = ""
    for i, ch in enumerate(channels):
        score = ch.get("score", 0)
        color = "var(--green)" if score >= 8 else "var(--amber)" if score >= 6 else "var(--text3)"
        pct = score * 10
        ch_id = f"ch-{i}"

        insight = ch.get("killer_insight", "")
        first_move = ch.get("first_move", "")

        if tier in ("starter", "growth"):
            move_html = f'<span class="cell-muted">{_e(first_move[:120])}</span>'
        else:
            move_html = '<span style="color:var(--text3);font-size:10px">Starter plan</span>'

        rows += f"""
<tr class="ch-row" data-target="{ch_id}" onclick="toggleChannel('{ch_id}')">
  <td class="cell-rank">{i+1}</td>
  <td class="cell-name">{_e(ch.get("channel",""))}</td>
  <td>
    <div class="score-bar">
      <span class="score-label" style="color:{color}">{score}</span>
      <div class="score-track"><div class="score-fill" style="width:{pct}%;background:{color}"></div></div>
    </div>
  </td>
  <td class="cell-muted">{_e(ch.get("effort",""))}</td>
  <td class="cell-muted">{_e(ch.get("timeline",""))}</td>
  <td style="font-family:var(--mono);font-size:11px;color:var(--text2)">{_e(ch.get("budget",""))}</td>
  <td class="cell-desc">{_e(insight[:100])}</td>
  <td>{move_html}</td>
</tr>"""

        # Expandable accordion row
        deep = ch.get("deep_dive", {})
        expand_content = _render_channel_accordion(ch, deep, tier)
        rows += f"""
<tr class="ch-expand" id="{ch_id}">
  <td colspan="8">{expand_content}</td>
</tr>"""

    return f"""
<div class="section" id="channels">
  <div class="section-header">
    <div class="section-title">Channel Analysis</div>
    <div class="update-badge"><span class="dot"></span> Updated today</div>
  </div>
  <div style="font-size:11px;color:var(--text3);margin-bottom:10px">Click any channel to expand actions and research</div>
  <div class="data-table-wrap">
    <table class="data-table">
      <thead><tr>
        <th>#</th><th>Channel</th><th style="min-width:130px">Score</th>
        <th>Effort</th><th>Timeline</th><th>Budget</th>
        <th>Key Insight</th><th>First Move</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


def _render_channel_accordion(ch, deep, tier):
    """Render expandable accordion content for a channel."""
    actions = deep.get("actions", [])
    research = deep.get("research", [])
    research_type = deep.get("research_type", "general")

    if not actions and not research:
        ideas = ch.get("specific_ideas", [])
        why = ch.get("why_or_why_not", "")
        if not ideas and not why:
            return '<div class="ch-expand-inner" style="color:var(--text3);font-size:12px">Detailed analysis available in future updates.</div>'
        ideas_html = ""
        for j, idea in enumerate(ideas[:3]):
            ideas_html += f"""
<div class="ch-action-card">
  <div class="ch-action-num">Idea {j+1}</div>
  <div class="ch-action-title">{_e(idea)}</div>
</div>"""
        why_html = f'<div style="margin-top:12px;font-size:12px;color:var(--text2);line-height:1.6"><strong style="color:var(--white)">Why:</strong> {_e(why)}</div>' if why else ""
        return f'<div class="ch-expand-inner"><div class="ch-actions-grid">{ideas_html}</div>{why_html}</div>'

    # Action cards
    actions_html = ""
    for j, action in enumerate(actions[:3]):
        result = action.get("expected_result", "")
        result_html = f'<div class="ch-action-result">{_e(result)}</div>' if result else ""
        actions_html += f"""
<div class="ch-action-card">
  <div class="ch-action-num">Action {j+1}</div>
  <div class="ch-action-title">{_e(action.get("title",""))}</div>
  <div class="ch-action-desc">{_e(action.get("description","")[:300])}</div>
  {result_html}
</div>"""

    # Research table
    research_html = _render_research_table(research, research_type) if research else ""

    return f"""<div class="ch-expand-inner">
  <div class="ch-actions-grid">{actions_html}</div>
  {research_html}
</div>"""


def _render_research_table(research, research_type):
    """Render research data table, adapting columns to the research type."""

    if research_type == "conferences":
        headers = "<th>Event</th><th>Date</th><th>Location</th><th>Cost</th><th>Audience</th><th>Fit</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--amber);white-space:nowrap">{_e(r.get('date',''))}</td>
<td class="cell-muted">{_e(r.get('location',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--text2)">{_e(r.get('cost',''))}</td>
<td class="cell-muted">{_e(r.get('audience',''))}</td>
<td class="cell-desc">{_e(r.get('fit','')[:120])}</td>
</tr>""" for r in research)

    elif research_type == "keywords":
        headers = "<th>Keyword</th><th>Volume</th><th>CPC</th><th>Competition</th><th>Strategy</th>"
        rows = ""
        for r in research:
            comp = r.get("competition", "")
            cc = "var(--green)" if comp == "Low" else "var(--amber)" if comp == "Medium" else "var(--red)"
            rows += f"""<tr>
<td class="cell-name">{_e(r.get('keyword',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--cyan)">{_e(r.get('volume',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--green)">{_e(r.get('cpc',''))}</td>
<td><span class="cell-tag" style="background:{cc}20;color:{cc}">{_e(comp)}</span></td>
<td class="cell-desc">{_e(r.get('strategy','')[:120])}</td>
</tr>"""

    elif research_type == "content_topics":
        headers = "<th>Topic</th><th>Volume</th><th>Difficulty</th><th>Format</th><th>Angle</th>"
        rows = ""
        for r in research:
            diff = r.get("difficulty", "")
            dc = "var(--green)" if diff == "Low" else "var(--amber)" if diff == "Medium" else "var(--red)"
            rows += f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--cyan)">{_e(r.get('volume',''))}</td>
<td><span class="cell-tag" style="background:{dc}20;color:{dc}">{_e(diff)}</span></td>
<td class="cell-muted">{_e(r.get('format',''))}</td>
<td class="cell-desc">{_e(r.get('angle','')[:120])}</td>
</tr>"""

    elif research_type == "communities":
        headers = "<th>Community</th><th>Members</th><th>Relevance</th>"
        rows = "".join(f"""<tr>
<td class="cell-name"><a href="{_e(r.get('url','#'))}" target="_blank">{_e(r.get('name',''))}</a></td>
<td style="font-family:var(--mono);font-size:11px;color:var(--cyan)">{_e(r.get('members',''))}</td>
<td class="cell-desc">{_e(r.get('relevance','')[:180])}</td>
</tr>""" for r in research)

    elif research_type == "partners":
        headers = "<th>Partner</th><th>Type</th><th>Audience</th><th>Strategic Fit</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td><span class="cell-tag tag-market">{_e(r.get('type',''))}</span></td>
<td class="cell-muted">{_e(r.get('audience',''))}</td>
<td class="cell-desc">{_e(r.get('fit','')[:180])}</td>
</tr>""" for r in research)

    elif research_type == "sales_targets":
        headers = "<th>Company</th><th>Target Role</th><th>Why</th><th>Approach</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td class="cell-muted">{_e(r.get('title',''))}</td>
<td class="cell-desc">{_e(r.get('reason','')[:140])}</td>
<td class="cell-desc">{_e(r.get('approach','')[:120])}</td>
</tr>""" for r in research)

    elif research_type == "outreach":
        headers = "<th>Template</th><th>Subject Line</th><th>Preview</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td style="color:var(--white);font-size:12px">{_e(r.get('subject',''))}</td>
<td class="cell-desc">{_e(r.get('preview','')[:180])}</td>
</tr>""" for r in research)

    elif research_type == "platforms":
        headers = "<th>Platform</th><th>Type</th><th>Audience</th><th>Strategy</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td><span class="cell-tag tag-market">{_e(r.get('type',''))}</span></td>
<td class="cell-muted">{_e(r.get('audience',''))}</td>
<td class="cell-desc">{_e(r.get('strategy','')[:160])}</td>
</tr>""" for r in research)

    elif research_type == "community_platforms":
        headers = "<th>Platform</th><th>Cost</th><th>Pros</th><th>Cons</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--green)">{_e(r.get('cost',''))}</td>
<td class="cell-desc">{_e(r.get('pros','')[:140])}</td>
<td class="cell-desc" style="color:var(--amber)">{_e(r.get('cons','')[:140])}</td>
</tr>""" for r in research)

    elif research_type == "journalists":
        headers = "<th>Journalist</th><th>Outlet</th><th>Beat</th><th>Recent Article</th><th>Twitter</th><th>Relevance</th>"
        rows = "".join(f"""<tr>
<td class="cell-name"><a href="https://twitter.com/{_e((r.get('twitter','')or'').lstrip('@'))}" target="_blank">{_e(r.get('name',''))}</a></td>
<td style="color:var(--white);font-size:12px">{_e(r.get('outlet',''))}</td>
<td class="cell-muted">{_e(r.get('beat',''))}</td>
<td class="cell-desc" style="max-width:200px">{_e(r.get('recent_article','')[:120])}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--accent)">{_e(r.get('twitter',''))}</td>
<td class="cell-desc">{_e(r.get('relevance','')[:140])}</td>
</tr>""" for r in research)

    elif research_type == "influencers":
        headers = "<th>Influencer</th><th>Platform</th><th>Audience</th><th>Engagement</th><th>Why Relevant</th>"
        rows = "".join(f"""<tr>
<td class="cell-name"><a href="{_e(r.get('url','#'))}" target="_blank">{_e(r.get('name',''))}</a></td>
<td><span class="cell-tag {_tag_class(r.get('platform',''))}">{_e(r.get('platform',''))}</span></td>
<td style="font-family:var(--mono);font-size:11px;color:var(--cyan)">{_e(r.get('audience',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--green)">{_e(r.get('engagement',''))}</td>
<td class="cell-desc">{_e(r.get('relevance','')[:140])}</td>
</tr>""" for r in research)

    elif research_type == "newsletters":
        headers = "<th>Publication</th><th>Audience</th><th>Frequency</th><th>Contact</th><th>Pitch Angle</th>"
        rows = "".join(f"""<tr>
<td class="cell-name"><a href="{_e(r.get('url','#'))}" target="_blank">{_e(r.get('name',''))}</a></td>
<td style="font-family:var(--mono);font-size:11px;color:var(--cyan)">{_e(r.get('audience',''))}</td>
<td class="cell-muted">{_e(r.get('frequency',''))}</td>
<td class="cell-muted">{_e(r.get('contact',''))}</td>
<td class="cell-desc">{_e(r.get('angle','')[:140])}</td>
</tr>""" for r in research)

    elif research_type == "email_sequences":
        headers = "<th>Email</th><th>Subject</th><th>Timing</th><th>Goal</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td style="color:var(--white);font-size:12px">{_e(r.get('subject',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--amber)">{_e(r.get('timing',''))}</td>
<td class="cell-desc">{_e(r.get('goal','')[:140])}</td>
</tr>""" for r in research)

    elif research_type == "free_tools":
        headers = "<th>Tool Idea</th><th>Effort</th><th>Viral Potential</th><th>Conversion Path</th>"
        rows = "".join(f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td><span class="cell-tag" style="background:var(--amber-soft);color:var(--amber)">{_e(r.get('effort',''))}</span></td>
<td style="font-family:var(--mono);font-size:11px;color:var(--green)">{_e(r.get('viral_potential',''))}</td>
<td class="cell-desc">{_e(r.get('conversion','')[:160])}</td>
</tr>""" for r in research)

    elif research_type == "stunts":
        headers = "<th>Stunt Idea</th><th>Budget</th><th>Virality</th><th>Risk</th><th>Description</th>"
        rows = ""
        for r in research:
            risk = r.get("risk", "")
            rc = "var(--green)" if risk == "Low" else "var(--amber)" if risk == "Medium" else "var(--red)"
            rows += f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--text2)">{_e(r.get('budget',''))}</td>
<td style="font-family:var(--mono);font-size:11px;color:var(--green)">{_e(r.get('virality',''))}</td>
<td><span class="cell-tag" style="background:{rc}20;color:{rc}">{_e(risk)}</span></td>
<td class="cell-desc">{_e(r.get('description','')[:160])}</td>
</tr>"""

    elif research_type == "affiliates":
        headers = "<th>Affiliate</th><th>Platform</th><th>Audience</th><th>Type</th><th>Commission Model</th>"
        rows = "".join(f"""<tr>
<td class="cell-name"><a href="{_e(r.get('url','#'))}" target="_blank">{_e(r.get('name',''))}</a></td>
<td><span class="cell-tag {_tag_class(r.get('platform',''))}">{_e(r.get('platform',''))}</span></td>
<td style="font-family:var(--mono);font-size:11px;color:var(--cyan)">{_e(r.get('audience',''))}</td>
<td class="cell-muted">{_e(r.get('type',''))}</td>
<td class="cell-desc">{_e(r.get('commission','')[:120])}</td>
</tr>""" for r in research)

    else:
        # Generic fallback
        headers = "<th>Item</th><th>Details</th>"
        rows = ""
        for r in research:
            details = " | ".join(f"{k}: {v}" for k, v in r.items() if k not in ("name", "url") and v)
            rows += f"""<tr>
<td class="cell-name">{_e(r.get('name',''))}</td>
<td class="cell-desc">{_e(details[:300])}</td>
</tr>"""

    return f"""
<div style="margin-top:4px">
  <div class="ch-research-title">Research & Data</div>
  <div class="ch-research-wrap">
    <table class="ch-research-table">
      <thead><tr>{headers}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


def _section_leads(leads, personas, tier, checkout_url, date_short):
    # Personas
    persona_html = ""
    if personas:
        cards = ""
        for p in personas[:3]:
            tags = "".join(
                f'<span class="cell-tag {_tag_class(pl)}">{_e(pl)}</span> '
                for pl in p.get("platforms", [])
            )
            sigs = "".join(f"<li>{_e(s[:90])}</li>" for s in p.get("pain_signals", [])[:3])
            cards += f"""
<div class="persona-card">
  <div class="persona-name">{_e(p.get("name",""))}</div>
  <div class="persona-desc">{_e(p.get("description","")[:180])}</div>
  <div class="persona-tags">{tags}</div>
  <ul class="persona-signals">{sigs}</ul>
</div>"""
        persona_html = f'<div class="persona-strip">{cards}</div>'

    # Leads table
    lead_rows = ""
    for i, lead in enumerate(leads):
        score = lead.get("score", 0)
        color = "var(--green)" if score >= 8 else "var(--amber)" if score >= 6 else "var(--text3)"
        platform = lead.get("platform", "")
        handle = lead.get("handle", "")
        url = lead.get("url", "#")
        name = lead.get("name", "")
        title = lead.get("title", "")
        relevance = lead.get("relevance", "")

        lead_rows += f"""
<tr>
  <td class="cell-rank">{i+1}</td>
  <td class="cell-name"><a href="{_e(url)}" target="_blank" rel="noopener">{_e(name)}</a></td>
  <td class="cell-muted">{_e(title)}</td>
  <td><span class="cell-tag {_tag_class(platform)}">{_e(platform)}</span></td>
  <td style="font-family:var(--mono);font-size:11px;color:var(--text2)">{_e(handle)}</td>
  <td class="cell-score" style="color:{color}">{score}/10</td>
  <td class="cell-desc">{_e(relevance[:160])}</td>
</tr>"""

    # Outreach lock
    outreach_cta = ""
    if tier == "free" and leads:
        outreach_cta = f"""
<div class="lock-card" style="margin-top:16px">
  <div class="lock-title">Outreach Playbook</div>
  <div class="lock-desc">Personalized messaging templates, approach angles, and timing strategy for each lead</div>
  <a href="{_e(checkout_url)}" class="cta-btn">Unlock with Starter — $39/mo</a>
</div>"""

    return f"""
<div class="section" id="leads">
  <div class="section-header">
    <div class="section-title">Potential Leads</div>
    <div class="update-badge"><span class="dot"></span> Updating weekly · Last: {date_short}</div>
  </div>
  {persona_html}
  <div class="data-table-wrap">
    <table class="data-table">
      <thead><tr>
        <th>#</th><th>Name</th><th>Title / Role</th><th>Platform</th>
        <th>Handle</th><th>Score</th><th>Why They're a Lead</th>
      </tr></thead>
      <tbody>{lead_rows}</tbody>
    </table>
  </div>
  {outreach_cta}
</div>"""


def _section_investors(competitors, comp_investors, mkt_investors, tier, upgrade_url, date_short):
    # Competitor cards
    comp_html = ""
    if competitors:
        cards = ""
        for c in competitors:
            inv = ", ".join(c.get("investors", [])[:4])
            cards += f"""
<div class="comp-card">
  <div class="comp-name"><a href="{_e(c.get('url','#'))}" target="_blank" rel="noopener">{_e(c.get("name",""))}</a></div>
  <div class="comp-funding">{_e(c.get("funding","—"))}</div>
  <div class="comp-desc">{_e(c.get("description","")[:80])}</div>
  <div class="comp-investors-list">{_e(inv)}</div>
</div>"""
        comp_html = f"""
<div style="margin-bottom:20px">
  <div style="font-size:12px;font-weight:600;color:var(--text2);margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px">Competitor Landscape</div>
  <div class="comp-row">{cards}</div>
</div>"""

    # Investor table
    all_inv = []
    for inv in comp_investors:
        all_inv.append({**inv, "_source": "Competitor Portfolio"})
    for inv in mkt_investors:
        all_inv.append({**inv, "_source": "Market Search"})

    inv_rows = ""
    for i, inv in enumerate(all_inv):
        inv_type = inv.get("type", "VC")
        source = inv.get("_source", "")
        type_tag = "tag-vc" if inv_type == "VC" else "tag-angel" if inv_type == "Angel" else "tag-vc"
        source_tag = "tag-competitor" if "Competitor" in source else "tag-market"
        url = inv.get("url", "#")

        inv_rows += f"""
<tr>
  <td class="cell-rank">{i+1}</td>
  <td class="cell-name"><a href="{_e(url)}" target="_blank" rel="noopener">{_e(inv.get("name",""))}</a></td>
  <td><span class="cell-tag {type_tag}">{_e(inv_type)}</span></td>
  <td class="cell-desc">{_e(inv.get("focus","")[:180])}</td>
  <td><span class="cell-tag {source_tag}">{_e(source)}</span></td>
</tr>"""

    # Deep dive lock
    deep_cta = ""
    if tier in ("free", "starter"):
        deep_cta = f"""
<div class="lock-card" style="margin-top:16px">
  <div class="lock-title">Investor Deep Dive</div>
  <div class="lock-desc">Portfolio analysis, warm intro paths, thesis alignment scores, and personalized outreach templates</div>
  <a href="{_e(upgrade_url)}" class="cta-btn purple">Unlock with Growth — $200/mo</a>
</div>"""

    return f"""
<div class="section" id="investors">
  <div class="section-header">
    <div class="section-title">Investor Intelligence</div>
    <div class="update-badge"><span class="dot"></span> Updating weekly · Last: {date_short}</div>
  </div>
  {comp_html}
  <div class="data-table-wrap">
    <table class="data-table">
      <thead><tr>
        <th>#</th><th>Investor</th><th>Type</th><th>Focus / Thesis</th><th>Source</th>
      </tr></thead>
      <tbody>{inv_rows}</tbody>
    </table>
  </div>
  {deep_cta}
</div>"""


def _section_strategy(plan, budget, risks, moat, tier, checkout_url):
    if tier == "free":
        return f"""
<div class="section" id="plan">
  <div class="section-header">
    <div class="section-title">Strategy & Execution</div>
  </div>
  <div class="lock-card">
    <div class="lock-title">90-Day Action Plan</div>
    <div class="lock-desc">Month-by-month breakdown with specific actions, budget allocation, risk matrix, and competitive moat analysis</div>
    <a href="{_e(checkout_url)}" class="cta-btn">Unlock Strategy — $39/mo</a>
  </div>
</div>"""

    # 90-day plan
    months_html = ""
    for key, label in [("month_1", "Month 1"), ("month_2", "Month 2"), ("month_3", "Month 3")]:
        m = plan.get(key, {})
        actions = "".join(f"<li>{_e(a[:110])}</li>" for a in m.get("actions", []))
        months_html += f"""
<div class="plan-card">
  <div class="plan-month-label">{label}</div>
  <div class="plan-focus">{_e(m.get("focus",""))}</div>
  <ul class="plan-actions">{actions}</ul>
  <div class="plan-metric">{_e(m.get("target_metric",""))}</div>
  <div class="plan-budget">Budget: {_e(m.get("budget",""))}</div>
</div>"""

    plan_html = f"""
<div class="section" id="plan">
  <div class="section-header"><div class="section-title">90-Day Action Plan</div></div>
  <div class="plan-grid">{months_html}</div>
</div>"""

    # Budget
    budget_rows = ""
    for b in budget.get("breakdown", []):
        budget_rows += f"""
<tr>
  <td class="cell-name">{_e(b.get("channel",""))}</td>
  <td style="font-family:var(--mono);font-weight:600;color:var(--green)">{_e(b.get("amount",""))}</td>
  <td class="cell-desc">{_e(b.get("rationale",""))}</td>
</tr>"""

    budget_html = f"""
<div class="section" id="budget">
  <div class="section-header">
    <div class="section-title">Budget Allocation</div>
    <span style="font-size:12px;color:var(--text2);font-family:var(--mono)">{_e(budget.get("total_recommended",""))}</span>
  </div>
  <div class="data-table-wrap">
    <table class="data-table">
      <thead><tr><th>Channel</th><th>Amount</th><th>Rationale</th></tr></thead>
      <tbody>{budget_rows}</tbody>
    </table>
  </div>
</div>"""

    # Risks
    risk_rows = ""
    for r in risks:
        prob = r.get("probability", "")
        impact = r.get("impact", "")
        pc = "var(--red)" if prob == "high" else "var(--amber)" if prob == "medium" else "var(--text2)"
        ic = "var(--red)" if impact == "high" else "var(--amber)" if impact == "medium" else "var(--text2)"
        risk_rows += f"""
<tr>
  <td style="color:var(--text)">{_e(r.get("risk",""))}</td>
  <td><span class="cell-tag" style="background:{pc}20;color:{pc}">{_e(prob)}</span></td>
  <td><span class="cell-tag" style="background:{ic}20;color:{ic}">{_e(impact)}</span></td>
  <td class="cell-desc">{_e(r.get("mitigation",""))}</td>
</tr>"""

    risk_html = f"""
<div class="section" id="risks">
  <div class="section-header"><div class="section-title">Risk Matrix</div></div>
  <div class="data-table-wrap">
    <table class="data-table">
      <thead><tr><th>Risk</th><th>Probability</th><th>Impact</th><th>Mitigation</th></tr></thead>
      <tbody>{risk_rows}</tbody>
    </table>
  </div>
</div>"""

    # Moat
    moat_html = ""
    if moat:
        moat_html = f"""
<div class="section">
  <div class="section-header"><div class="section-title">Competitive Moat</div></div>
  <div class="exec-box">
    <div class="exec-text">{_e(moat)}</div>
  </div>
</div>"""

    return plan_html + budget_html + risk_html + moat_html


def _section_footer(name):
    return f"""
<div class="footer">
  <div class="footer-left">
    mckoutie & company · Analysis for {_e(name)} · This is a living report — data updates automatically
  </div>
  <div class="footer-right">
    mckoutie.com
  </div>
</div>"""


# ═══════════════════════════════════════════════
# JS
# ═══════════════════════════════════════════════
def _js():
    return """
// Channel accordion toggle
function toggleChannel(id){
  var row=document.getElementById(id);
  var trigger=document.querySelector('[data-target="'+id+'"]');
  if(!row||!trigger)return;
  row.classList.toggle('open');
  trigger.classList.toggle('open');
}

// Download as .md
function downloadMd(){
  var d=__REPORT_DATA__;
  var md='# '+d.name+' — mckoutie & company Strategy Brief\\n\\n';
  md+='**Report ID:** '+d.id+'\\n';
  md+='**Generated:** '+new Date().toISOString().slice(0,10)+'\\n\\n';

  // Executive summary
  md+='## Executive Summary\\n\\n'+d.summary+'\\n\\n';
  if(d.hot_take) md+='> **Hot Take:** '+d.hot_take+'\\n\\n';

  // Bullseye
  var b=d.bullseye||{};
  md+='## Bullseye Framework\\n\\n';
  if(b.inner_ring){md+='### Inner Ring (Do Now)\\n';(b.inner_ring.channels||[]).forEach(function(c){md+='- '+c+'\\n'});md+='\\n';}
  if(b.promising){md+='### Promising (Test Next)\\n';(b.promising.channels||[]).forEach(function(c){md+='- '+c+'\\n'});md+='\\n';}

  // Channel analysis
  var ch=(d.channels||[]).slice().sort(function(a,b){return(b.score||0)-(a.score||0)});
  md+='## Channel Analysis\\n\\n';
  md+='| # | Channel | Score | Effort | Timeline | Budget | Insight |\\n';
  md+='|---|---------|-------|--------|----------|--------|---------|\\n';
  ch.forEach(function(c,i){
    md+='| '+(i+1)+' | '+(c.channel||'')+' | '+(c.score||0)+'/10 | '+(c.effort||'')+' | '+(c.timeline||'')+' | '+(c.budget||'')+' | '+(c.killer_insight||'').slice(0,100)+' |\\n';
  });
  md+='\\n';

  // Leads
  var lr=d.leads||{};
  var personas=lr.personas||[];
  var leads=lr.leads||[];
  if(personas.length){
    md+='## Customer Personas\\n\\n';
    personas.forEach(function(p){
      md+='### '+p.name+'\\n';
      md+=(p.description||'')+'\\n\\n';
      if(p.platforms&&p.platforms.length) md+='**Platforms:** '+ p.platforms.join(', ')+'\\n\\n';
      if(p.pain_signals&&p.pain_signals.length){md+='**Pain signals:**\\n';p.pain_signals.forEach(function(s){md+='- '+s+'\\n'});md+='\\n';}
    });
  }
  if(leads.length){
    md+='## Potential Leads\\n\\n';
    md+='| # | Name | Title | Platform | Handle | Score | Why |\\n';
    md+='|---|------|-------|----------|--------|-------|-----|\\n';
    leads.forEach(function(l,i){
      md+='| '+(i+1)+' | '+(l.name||'')+' | '+(l.title||'')+' | '+(l.platform||'')+' | '+(l.handle||'')+' | '+(l.score||0)+'/10 | '+(l.relevance||'').slice(0,120)+' |\\n';
    });
    md+='\\n';
  }

  // Investors
  var ir=d.investors||{};
  var comps=ir.competitors||[];
  var ci=ir.competitor_investors||[];
  var mi=ir.market_investors||[];
  if(comps.length){
    md+='## Competitor Landscape\\n\\n';
    md+='| Company | Funding | Description |\\n';
    md+='|---------|---------|-------------|\\n';
    comps.forEach(function(c){md+='| '+(c.name||'')+' | '+(c.funding||'—')+' | '+(c.description||'').slice(0,100)+' |\\n'});
    md+='\\n';
  }
  var allInv=ci.concat(mi);
  if(allInv.length){
    md+='## Investors\\n\\n';
    md+='| # | Investor | Type | Focus |\\n';
    md+='|---|----------|------|-------|\\n';
    allInv.forEach(function(inv,i){md+='| '+(i+1)+' | '+(inv.name||'')+' | '+(inv.type||'')+' | '+(inv.focus||'').slice(0,120)+' |\\n'});
    md+='\\n';
  }

  // Strategy (only if tier allows)
  var plan=d.plan||{};
  if(plan.month_1){
    md+='## 90-Day Action Plan\\n\\n';
    ['month_1','month_2','month_3'].forEach(function(k,i){
      var m=plan[k]||{};
      md+='### Month '+(i+1)+': '+(m.focus||'')+'\\n';
      (m.actions||[]).forEach(function(a){md+='- '+a+'\\n'});
      if(m.target_metric) md+='**Target:** '+m.target_metric+'\\n';
      if(m.budget) md+='**Budget:** '+m.budget+'\\n';
      md+='\\n';
    });
  }

  var budget=d.budget||{};
  if(budget.breakdown&&budget.breakdown.length){
    md+='## Budget Allocation\\n\\n';
    if(budget.total_recommended) md+='**Total recommended:** '+budget.total_recommended+'\\n\\n';
    md+='| Channel | Amount | Rationale |\\n';
    md+='|---------|--------|-----------|\\n';
    budget.breakdown.forEach(function(b){md+='| '+(b.channel||'')+' | '+(b.amount||'')+' | '+(b.rationale||'')+' |\\n'});
    md+='\\n';
  }

  var risks=d.risks||[];
  if(risks.length){
    md+='## Risk Matrix\\n\\n';
    md+='| Risk | Probability | Impact | Mitigation |\\n';
    md+='|------|-------------|--------|------------|\\n';
    risks.forEach(function(r){md+='| '+(r.risk||'')+' | '+(r.probability||'')+' | '+(r.impact||'')+' | '+(r.mitigation||'')+' |\\n'});
    md+='\\n';
  }

  if(d.moat){md+='## Competitive Moat\\n\\n'+d.moat+'\\n\\n';}

  md+='---\\n*Generated by [mckoutie & company](https://mckoutie.com)*\\n';

  // Trigger download
  var blob=new Blob([md],{type:'text/markdown;charset=utf-8'});
  var url=URL.createObjectURL(blob);
  var a=document.createElement('a');
  a.href=url;
  a.download=(d.name||'report').replace(/[^a-zA-Z0-9]/g,'-').toLowerCase()+'-mckoutie.md';
  document.body.appendChild(a);a.click();document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Active nav link on scroll
(function(){
  var links=document.querySelectorAll('.nav-link');
  var sections=[];
  links.forEach(function(l){
    var id=l.getAttribute('href');
    if(id&&id.startsWith('#')){
      var el=document.getElementById(id.slice(1));
      if(el) sections.push({link:l,el:el});
    }
  });
  function update(){
    var scrollY=window.scrollY+100;
    var current=null;
    sections.forEach(function(s){
      if(s.el.offsetTop<=scrollY) current=s;
    });
    links.forEach(function(l){l.classList.remove('active')});
    if(current) current.link.classList.add('active');
  }
  window.addEventListener('scroll',update,{passive:true});
  update();
})();
"""


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════
def _report_json(analysis, name, report_id, tier):
    """Serialize report data for client-side .md generation."""
    safe = {
        "name": name,
        "id": report_id,
        "tier": tier,
        "summary": analysis.get("executive_summary", ""),
        "hot_take": analysis.get("hot_take", ""),
        "channels": analysis.get("channel_analysis", []),
        "bullseye": analysis.get("bullseye_ranking", {}),
        "plan": analysis.get("ninety_day_plan", {}),
        "budget": analysis.get("budget_allocation", {}),
        "risks": analysis.get("risk_matrix", []),
        "moat": analysis.get("competitive_moat", ""),
        "leads": analysis.get("leads_research", {}),
        "investors": analysis.get("investor_research", {}),
    }
    return _json.dumps(safe, default=str)


def _tag_class(platform):
    p = (platform or "").lower()
    if "twitter" in p or "x" in p:
        return "tag-twitter"
    if "linkedin" in p:
        return "tag-linkedin"
    if "reddit" in p:
        return "tag-reddit"
    if "discord" in p:
        return "tag-discord"
    if "github" in p:
        return "tag-github"
    if "substack" in p:
        return "tag-substack"
    return ""


# ═══════════════════════════════════════════════
# Streaming SSE JavaScript
# ═══════════════════════════════════════════════
def _streaming_js():
    """Client-side SSE listener that connects to /report/{id}/stream
    and dynamically updates dashboard sections as data arrives in real-time."""
    return """
(function(){
  if(!__STREAMING__) return;

  var rid = __REPORT_ID__;
  var tier = __TIER__;
  var banner = document.getElementById('streaming-banner');
  var statusEl = document.getElementById('streaming-status');
  var thinkingEl = document.getElementById('thinking-detail');
  var pips = document.querySelectorAll('.progress-pip');

  // Accumulated data as items stream in
  var channels = [];
  var personas = [];
  var leads = [];
  var competitors = [];
  var investors = [];
  var channelsMeta = null;
  var strategyData = null;
  var channelCount = 0;

  function setPip(section, state){
    var pip = document.querySelector('.progress-pip[data-section="'+section+'"]');
    if(!pip) return;
    if(state==='active') { pip.style.background='#00d4ff'; pip.style.animation='pulse-dot 1s ease-in-out infinite'; }
    else if(state==='done') { pip.style.background='#00ff88'; pip.style.animation='none'; }
    else { pip.style.background='#333'; pip.style.animation='none'; }
  }

  var activityLog = document.getElementById('activity-log');
  var logEntries = [];
  var MAX_LOG = 4;

  function setStatus(msg){ if(statusEl) statusEl.textContent = msg; }
  function setThinking(msg){
    if(thinkingEl) thinkingEl.textContent = msg || '';
    if(msg && activityLog){
      var ts = new Date().toLocaleTimeString('en-US',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
      logEntries.push({time:ts, msg:msg});
      if(logEntries.length > MAX_LOG) logEntries.shift();
      activityLog.innerHTML = logEntries.map(function(e){
        return '<div style="font-size:10px;color:#444;font-family:var(--mono);padding:1px 0;opacity:0.7">'+
          '<span style="color:#555">'+e.time+'</span> '+escHtml(e.msg)+'</div>';
      }).join('');
      activityLog.style.maxHeight = (logEntries.length * 18 + 4) + 'px';
    }
  }

  function escHtml(s){
    if(!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function tagClass(p){
    p=(p||'').toLowerCase();
    if(p.indexOf('twitter')>=0||p.indexOf('x')>=0) return 'tag-twitter';
    if(p.indexOf('linkedin')>=0) return 'tag-linkedin';
    if(p.indexOf('reddit')>=0) return 'tag-reddit';
    if(p.indexOf('discord')>=0) return 'tag-discord';
    if(p.indexOf('github')>=0) return 'tag-github';
    if(p.indexOf('substack')>=0) return 'tag-substack';
    return '';
  }

  // ---------- INDIVIDUAL ITEM RENDERERS ----------

  function addChannelRow(ch, idx){
    var chSection = document.getElementById('channels');
    if(!chSection) return;
    var tableBody = chSection.querySelector('.data-table tbody');
    if(!tableBody) return;

    // Remove skeleton on first channel
    if(idx === 0){
      var skel = chSection.querySelector('.streaming-skeleton');
      if(skel) skel.remove();
    }

    var score = ch.score||0;
    var color = score>=8?'var(--green)':score>=6?'var(--amber)':'var(--text3)';
    var pct = score*10;
    var chId = 'ch-'+idx;
    var insight = ch.killer_insight||'';
    var firstMove = ch.first_move||'';
    var moveHtml = tier==='starter'||tier==='growth'
      ? '<span class="cell-muted">'+escHtml(firstMove.slice(0,120))+'</span>'
      : '<span style="color:var(--text3);font-size:10px">Starter plan</span>';

    var row = document.createElement('tr');
    row.className = 'ch-row';
    row.setAttribute('data-target', chId);
    row.setAttribute('onclick', "toggleChannel('"+chId+"')");
    row.style.opacity = '0';
    row.style.transform = 'translateY(8px)';
    row.style.transition = 'all 0.4s ease';
    row.innerHTML =
      '<td class="cell-rank">'+(idx+1)+'</td>'+
      '<td class="cell-name">'+escHtml(ch.channel||'')+'</td>'+
      '<td><div class="score-bar"><span class="score-label" style="color:'+color+'">'+score+'</span>'+
      '<div class="score-track"><div class="score-fill" style="width:0%;background:'+color+'"></div></div></div></td>'+
      '<td class="cell-muted">'+escHtml(ch.effort||'')+'</td>'+
      '<td class="cell-muted">'+escHtml(ch.timeline||'')+'</td>'+
      '<td style="font-family:var(--mono);font-size:11px;color:var(--text2)">'+escHtml(ch.budget||'')+'</td>'+
      '<td class="cell-desc">'+escHtml(insight.slice(0,100))+'</td>'+
      '<td>'+moveHtml+'</td>';
    tableBody.appendChild(row);

    // Accordion expand row
    var deep = ch.deep_dive||{};
    var actions = deep.actions||[];
    var expandInner = '';
    if(actions.length){
      expandInner += '<div class="action-grid">';
      actions.forEach(function(a){
        expandInner += '<div class="action-card"><div class="action-title">'+escHtml(a.title||'')+'</div>'+
          '<div class="action-desc">'+escHtml(a.description||'')+'</div>'+
          '<div class="action-result">'+escHtml(a.expected_result||'')+'</div></div>';
      });
      expandInner += '</div>';
    }
    var expandRow = document.createElement('tr');
    expandRow.className = 'ch-expand';
    expandRow.id = chId;
    expandRow.innerHTML = '<td colspan="8">'+expandInner+'</td>';
    tableBody.appendChild(expandRow);

    // Animate in
    requestAnimationFrame(function(){
      row.style.opacity = '1';
      row.style.transform = 'translateY(0)';
      // Animate score bar fill
      var fill = row.querySelector('.score-fill');
      if(fill) setTimeout(function(){ fill.style.transition='width 0.6s ease'; fill.style.width=pct+'%'; }, 100);
    });

    // Update KPI counters progressively
    updateKPIs();
  }

  function updateKPIs(){
    var sorted = channels.slice().sort(function(a,b){return(b.score||0)-(a.score||0)});
    var topScore = sorted.length?sorted[0].score:0;
    var topName = sorted.length?sorted[0].channel:'';
    var avg = sorted.length?Math.round(sorted.reduce(function(s,c){return s+(c.score||0)},0)/sorted.length*10)/10:0;

    var kpis = document.getElementById('kpis');
    if(kpis){
      var vals = kpis.querySelectorAll('.kpi-value');
      var subs = kpis.querySelectorAll('.kpi-sub');
      if(vals[0]) vals[0].innerHTML = topScore+'<span style="font-size:14px;color:var(--text3)">/10</span>';
      if(subs[0]) subs[0].textContent = topName;
      if(vals[1]) vals[1].textContent = avg;
    }

    // Update __REPORT_DATA__ for .md download
    __REPORT_DATA__.channels = channels;
  }

  function addPersonaCard(p, idx){
    var section = document.getElementById('leads');
    if(!section) return;
    // Remove skeleton on first persona
    if(idx === 0){
      var skel = section.querySelector('.streaming-skeleton');
      if(skel) skel.remove();
    }
    var strip = section.querySelector('.persona-strip');
    if(!strip){
      strip = document.createElement('div');
      strip.className = 'persona-strip';
      var header = section.querySelector('.section-header');
      if(header) header.insertAdjacentElement('afterend', strip);
    }
    var card = document.createElement('div');
    card.className = 'persona-card';
    card.style.opacity = '0';
    card.style.transform = 'scale(0.95)';
    card.style.transition = 'all 0.4s ease';
    var tags = (p.platforms||[]).map(function(pl){return '<span class="cell-tag '+tagClass(pl)+'">'+escHtml(pl)+'</span> '}).join('');
    var sigs = (p.pain_signals||[]).slice(0,3).map(function(s){return '<li>'+escHtml(s.slice(0,90))+'</li>'}).join('');
    card.innerHTML = '<div class="persona-name">'+escHtml(p.name||'')+'</div>'+
      '<div class="persona-desc">'+escHtml((p.description||'').slice(0,180))+'</div>'+
      '<div class="persona-tags">'+tags+'</div>'+
      '<ul class="persona-signals">'+sigs+'</ul>';
    strip.appendChild(card);
    requestAnimationFrame(function(){ card.style.opacity='1'; card.style.transform='scale(1)'; });
  }

  function addLeadRow(l, idx){
    var section = document.getElementById('leads');
    if(!section) return;
    var tableBody = section.querySelector('.data-table tbody');
    if(!tableBody) return;
    var score = l.score||0;
    var color = score>=8?'var(--green)':score>=6?'var(--amber)':'var(--text3)';
    var row = document.createElement('tr');
    row.style.opacity = '0';
    row.style.transform = 'translateX(-12px)';
    row.style.transition = 'all 0.4s ease';
    row.innerHTML = '<td class="cell-rank">'+(idx+1)+'</td>'+
      '<td class="cell-name"><a href="'+escHtml(l.url||'#')+'" target="_blank" rel="noopener">'+escHtml(l.name||'')+'</a></td>'+
      '<td class="cell-muted">'+escHtml(l.title||'')+'</td>'+
      '<td><span class="cell-tag '+tagClass(l.platform||'')+'">'+escHtml(l.platform||'')+'</span></td>'+
      '<td style="font-family:var(--mono);font-size:11px;color:var(--text2)">'+escHtml(l.handle||'')+'</td>'+
      '<td class="cell-score" style="color:'+color+'">'+score+'/10</td>'+
      '<td class="cell-desc">'+escHtml((l.relevance||'').slice(0,160))+'</td>';
    tableBody.appendChild(row);
    requestAnimationFrame(function(){ row.style.opacity='1'; row.style.transform='translateX(0)'; });
    // Update KPI
    var kpis = document.getElementById('kpis');
    if(kpis){ var vals = kpis.querySelectorAll('.kpi-value'); if(vals[2]) vals[2].textContent = leads.length; }
    __REPORT_DATA__.leads = { personas: personas, leads: leads };
  }

  function addCompetitorCard(c, idx){
    var section = document.getElementById('investors');
    if(!section) return;
    if(idx === 0){
      var skel = section.querySelector('.streaming-skeleton');
      if(skel) skel.remove();
    }
    var strip = section.querySelector('.comp-strip');
    if(!strip){
      strip = document.createElement('div');
      strip.className = 'comp-strip';
      var header = section.querySelector('.section-header');
      if(header) header.insertAdjacentElement('afterend', strip);
    }
    var card = document.createElement('div');
    card.className = 'comp-card';
    card.style.opacity = '0';
    card.style.transform = 'scale(0.95)';
    card.style.transition = 'all 0.4s ease';
    var inv = (c.investors||[]).slice(0,4).join(', ');
    card.innerHTML = '<div class="comp-name">'+escHtml(c.name||'')+'</div>'+
      '<div class="comp-funding">'+escHtml(c.funding||'Unknown')+'</div>'+
      '<div class="comp-desc">'+escHtml((c.description||'').slice(0,120))+'</div>'+
      (inv?'<div class="comp-investors">Investors: '+escHtml(inv)+'</div>':'');
    strip.appendChild(card);
    requestAnimationFrame(function(){ card.style.opacity='1'; card.style.transform='scale(1)'; });
    var kpis = document.getElementById('kpis');
    if(kpis){ var vals = kpis.querySelectorAll('.kpi-value'); if(vals[4]) vals[4].textContent = competitors.length; }
  }

  function addInvestorRow(inv, idx){
    var section = document.getElementById('investors');
    if(!section) return;
    var tableBody = section.querySelector('.data-table tbody');
    if(!tableBody) return;
    var typeClass = (inv.type||'').toLowerCase().indexOf('vc')>=0?'tag-linkedin':
                    (inv.type||'').toLowerCase().indexOf('angel')>=0?'tag-twitter':'';
    var row = document.createElement('tr');
    row.style.opacity = '0';
    row.style.transform = 'translateX(-12px)';
    row.style.transition = 'all 0.4s ease';
    row.innerHTML = '<td class="cell-rank">'+(idx+1)+'</td>'+
      '<td class="cell-name">'+(inv.linkedin?'<a href="'+escHtml(inv.linkedin)+'" target="_blank" rel="noopener">':'')+
      escHtml(inv.name||'')+(inv.linkedin?'</a>':'')+'</td>'+
      '<td><span class="cell-tag '+typeClass+'">'+escHtml(inv.type||'')+'</span></td>'+
      '<td class="cell-desc">'+escHtml((inv.focus||inv.thesis||'').slice(0,180))+'</td>'+
      '<td><span class="cell-tag">'+(inv.source||'Market')+'</span></td>';
    tableBody.appendChild(row);
    requestAnimationFrame(function(){ row.style.opacity='1'; row.style.transform='translateX(0)'; });
    var kpis = document.getElementById('kpis');
    if(kpis){ var vals = kpis.querySelectorAll('.kpi-value'); if(vals[3]) vals[3].textContent = investors.length; }
    __REPORT_DATA__.investors = { competitors: competitors, competitor_investors: investors, market_investors: [] };
  }

  function updateChannelsMeta(payload){
    var bullseye = payload.bullseye_ranking||{};
    var summary = payload.executive_summary||'';
    var hotTake = payload.hot_take||'';
    var profile = payload.company_profile||{};

    var execEl = document.getElementById('executive');
    if(execEl){
      var sumBox = execEl.querySelector('.exec-text');
      var htBox = execEl.querySelector('.hottake-box .exec-text');
      if(sumBox && summary) sumBox.textContent = summary;
      if(htBox && hotTake) htBox.textContent = hotTake;
    }
    var bEl = document.getElementById('bullseye');
    if(bEl && bullseye){
      var inner = (bullseye.inner_ring||{}).channels||[];
      var promising = (bullseye.promising||{}).channels||[];
      var rings = bEl.querySelectorAll('.ring-items');
      if(rings[0]) rings[0].innerHTML = inner.map(function(c){return '<li>'+escHtml(c)+'</li>'}).join('');
      if(rings[1]) rings[1].innerHTML = promising.map(function(c){return '<li>'+escHtml(c)+'</li>'}).join('');
    }
    __REPORT_DATA__.bullseye = bullseye;
    __REPORT_DATA__.summary = summary;
    __REPORT_DATA__.hot_take = hotTake;
  }

  function updateStrategy(payload){
    __REPORT_DATA__.plan = payload.ninety_day_plan||{};
    __REPORT_DATA__.budget = payload.budget_allocation||{};
    __REPORT_DATA__.risks = payload.risk_matrix||[];
    __REPORT_DATA__.moat = payload.competitive_moat||'';
    var section = document.getElementById('strategy');
    if(!section) return;
    var skel = section.querySelector('.streaming-skeleton');
    if(skel) skel.remove();
    if(tier==='starter'||tier==='growth'){
      var badge = section.querySelector('.section-header .update-badge');
      if(badge) badge.innerHTML = '<span class="dot" style="background:var(--green)"></span> Complete';
    }
  }

  function finishAnalysis(){
    pips.forEach(function(p){ p.style.background='#00ff88'; p.style.animation='none'; });
    setStatus('Analysis complete — your full report is ready.');
    if(thinkingEl) thinkingEl.textContent = '';
    if(activityLog){ activityLog.style.maxHeight='0'; }
    setTimeout(function(){
      if(banner){
        banner.style.transition='all 0.5s ease';
        banner.style.borderColor='#00ff88';
        var dot = banner.querySelector('[style*="animation:pulse-dot"]');
        if(dot){ dot.style.background='#00ff88'; dot.style.animation='none'; }
      }
    }, 500);
    setTimeout(function(){
      if(banner){
        banner.style.opacity='0';
        setTimeout(function(){ banner.style.display='none'; document.body.style.paddingTop=''; }, 500);
      }
    }, 8000);
  }

  function showError(msg){
    setStatus('Analysis hit a snag: '+(msg||'unknown error')+'. Try refreshing.');
    setThinking('');
    pips.forEach(function(p){ p.style.background='#ff4444'; });
  }


  // ---------- SSE CONNECTION (true real-time streaming) ----------

  setStatus('Connecting to analysis engine...');
  setPip('channels','active');

  // Connect SSE directly to Railway (bypasses Vercel proxy which kills SSE streams)
  var sseBase = __SSE_BASE__ || '';
  var es = new EventSource(sseBase+'/report/'+rid+'/stream');
  var channelsPhaseComplete = false;
  var sseGotData = false;

  // Safety net: if SSE delivers nothing in 15s, fall back to polling.
  // Background analysis was already started by the page load, so polling will find data.
  var sseTimeout = setTimeout(function(){
    if(!sseGotData){
      console.log('[mckoutie] SSE timeout — no data in 15s, switching to polling');
      es.close();
      setStatus('Connecting via polling...');
      fallbackPoll();
    }
  }, 15000);

  es.addEventListener('thinking', function(e){
    sseGotData = true;
    var d = JSON.parse(e.data);
    setStatus(d.message||'');
    setThinking(d.detail||'');
  });

  es.addEventListener('channel', function(e){
    sseGotData = true;
    var d = JSON.parse(e.data);
    var ch = d.channel;
    if(!ch) return;
    channels.push(ch);
    channelCount++;
    addChannelRow(ch, d.index != null ? d.index : channels.length-1);
    setStatus('Analyzing channels... ('+channelCount+'/19)');
  });

  es.addEventListener('section', function(e){
    var d = JSON.parse(e.data);
    var section = d.section;
    var payload = d.payload||{};

    if(section === 'channels_meta'){
      channelsPhaseComplete = true;
      setPip('channels','done');
      setPip('leads','active');
      updateChannelsMeta(payload);
      setStatus('Channels complete. Searching for potential customers...');
    }
    if(section === 'leads_complete'){
      setPip('leads','done');
      setPip('investors','active');
      setStatus('Found '+((payload||{}).count||0)+' potential leads. Mapping investor landscape...');
    }
    if(section === 'investors_complete'){
      setPip('investors','done');
      setPip('strategy','active');
      setStatus('Found '+((payload||{}).count||0)+' investors. Generating strategy...');
    }
    if(section === 'strategy'){
      setPip('strategy','done');
      updateStrategy(payload);
    }
  });

  es.addEventListener('persona', function(e){
    var d = JSON.parse(e.data);
    var p = d.persona;
    if(!p) return;
    personas.push(p);
    addPersonaCard(p, d.index != null ? d.index : personas.length-1);
  });

  es.addEventListener('lead', function(e){
    var d = JSON.parse(e.data);
    var l = d.lead;
    if(!l) return;
    leads.push(l);
    addLeadRow(l, d.index != null ? d.index : leads.length-1);
  });

  es.addEventListener('channel_update', function(e){
    var d = JSON.parse(e.data);
    var idx = d.index;
    var deepDive = d.deep_dive;
    if(idx == null || !deepDive) return;
    // Update the accordion content for this channel
    var expandRow = document.getElementById('ch-'+idx);
    if(!expandRow) return;
    var actions = deepDive.actions||[];
    var html = '';
    if(actions.length){
      html += '<div class="action-grid">';
      actions.forEach(function(a){
        html += '<div class="action-card"><div class="action-title">'+escHtml(a.title||'')+'</div>'+
          '<div class="action-desc">'+escHtml(a.description||'')+'</div>'+
          '<div class="action-result">'+escHtml(a.expected_result||'')+'</div></div>';
      });
      html += '</div>';
    }
    var research = deepDive.research||[];
    if(research.length){
      html += '<div style="margin-top:12px;font-size:11px;color:var(--text2)">'+research.length+' research items available</div>';
    }
    expandRow.querySelector('td').innerHTML = html;
    // Flash the row to indicate update
    var chRow = document.querySelector('tr.ch-row[data-target="ch-'+idx+'"]');
    if(chRow){
      chRow.style.borderLeft = '3px solid var(--cyan)';
      setTimeout(function(){ chRow.style.borderLeft = ''; }, 2000);
    }
    // Update the channel object in memory
    if(channels[idx]) channels[idx].deep_dive = deepDive;
  });

  es.addEventListener('competitor', function(e){
    var d = JSON.parse(e.data);
    var c = d.competitor;
    if(!c) return;
    competitors.push(c);
    addCompetitorCard(c, d.index != null ? d.index : competitors.length-1);
    setPip('investors','active');
  });

  es.addEventListener('investor', function(e){
    var d = JSON.parse(e.data);
    var inv = d.investor;
    if(!inv) return;
    investors.push(inv);
    addInvestorRow(inv, d.index != null ? d.index : investors.length-1);
  });

  es.addEventListener('advisor_ready', function(e){
    var d = {};
    try { d = JSON.parse(e.data); } catch(ex){}
    setPip('advisor', d.partial ? 'active' : 'done');
    var msg = d.message || 'Your AI advisor is ready.';
    setThinking(msg);
    // Activate chat widget if present
    var chatWidget = document.getElementById('advisor-chat');
    if(chatWidget) {
      chatWidget.style.display = 'block';
      chatWidget.style.opacity = '0';
      chatWidget.style.transition = 'opacity 0.5s ease';
      requestAnimationFrame(function(){ chatWidget.style.opacity = '1'; });
    }
  });

  es.addEventListener('done', function(e){
    es.close();
    // Mark all leads/investors pips done
    if(leads.length || personas.length) setPip('leads','done');
    if(investors.length || competitors.length) setPip('investors','done');
    finishAnalysis();
  });

  es.addEventListener('error', function(e){
    // SSE native error — could be connection drop or server error event
    if(e.data){
      try {
        var d = JSON.parse(e.data);
        showError(d.message);
        es.close();
        return;
      } catch(ex){}
    }
    // Connection error — fall back to polling
    es.close();
    setStatus('Connection lost. Switching to polling...');
    fallbackPoll();
  });

  es.addEventListener('already_complete', function(e){
    es.close();
    // Report was already done — reload to show full data
    setStatus('Report is ready. Loading...');
    setTimeout(function(){ window.location.reload(); }, 500);
  });

  es.addEventListener('already_running', function(e){
    // Another tab/session started it — switch to polling for that
    es.close();
    setStatus('Analysis in progress — watching for results...');
    fallbackPoll();
  });

  // Fallback polling if SSE connection drops — progressively populates dashboard
  var pollChannelCount = 0;
  var pollLeadCount = 0;
  var pollInvestorCount = 0;
  var pollCompetitorCount = 0;
  var pollPersonaCount = 0;

  function fallbackPoll(){
    fetch(sseBase+'/report/'+rid+'/progress')
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(d.status==='complete'){
          window.location.reload();
          return;
        }
        if(d.status==='error'){
          showError(d.error||'unknown');
          return;
        }
        // Update status message
        if(d.status) setStatus(d.status);

        // Progressively add channels
        var pChannels = d.channels||[];
        while(pollChannelCount < pChannels.length){
          addChannelRow(pChannels[pollChannelCount], pollChannelCount);
          pollChannelCount++;
          setPip('channels','active');
        }
        if(pollChannelCount >= 19) setPip('channels','done');

        // Progressively add personas
        var pPersonas = d.personas||[];
        while(pollPersonaCount < pPersonas.length){
          addPersonaCard(pPersonas[pollPersonaCount], pollPersonaCount);
          pollPersonaCount++;
        }

        // Progressively add leads
        var pLeads = d.leads||[];
        while(pollLeadCount < pLeads.length){
          addLeadRow(pLeads[pollLeadCount], pollLeadCount);
          pollLeadCount++;
          setPip('leads','active');
        }

        // Progressively add competitors
        var pComps = d.competitors||[];
        while(pollCompetitorCount < pComps.length){
          addCompetitorCard(pComps[pollCompetitorCount], pollCompetitorCount);
          pollCompetitorCount++;
          setPip('investors','active');
        }

        // Progressively add investors
        var pInvs = d.investors||[];
        while(pollInvestorCount < pInvs.length){
          addInvestorRow(pInvs[pollInvestorCount], pollInvestorCount);
          pollInvestorCount++;
        }

        setTimeout(fallbackPoll, 3000);
      })
      .catch(function(){ setTimeout(fallbackPoll, 5000); });
  }

})();
"""


# ═══════════════════════════════════════════════
# Chat Widget (advisor agent)
# ═══════════════════════════════════════════════
def _chat_widget_html(report_id: str) -> str:
    """Floating chat widget for the AI advisor."""
    return f"""
<div id="chat-widget" style="
    position:fixed; bottom:24px; right:24px; z-index:9000;
    width:380px; max-height:520px;
    background:var(--panel,#111318); border:1px solid var(--border2,#2a2f3d);
    border-radius:16px; box-shadow:0 12px 48px rgba(0,0,0,.5);
    display:none; flex-direction:column; overflow:hidden;
    font-family:'Inter',sans-serif;
">
    <div style="
        padding:14px 18px; border-bottom:1px solid var(--border,#1e222d);
        display:flex; align-items:center; gap:10px;
        background:var(--surface,#161920);
        border-radius:16px 16px 0 0;
    ">
        <div style="width:10px;height:10px;border-radius:50%;background:#00ff88"></div>
        <span style="font-size:13px;font-weight:600;color:var(--white,#eaedf3)">mckoutie advisor</span>
        <span style="margin-left:auto;cursor:pointer;color:var(--text3,#4e5568);font-size:18px" onclick="toggleChat()">&times;</span>
    </div>
    <div id="chat-messages" style="
        flex:1; overflow-y:auto; padding:16px;
        display:flex; flex-direction:column; gap:10px;
        max-height:380px;
    ">
        <div class="chat-msg bot" style="
            background:var(--surface,#161920); padding:10px 14px;
            border-radius:12px 12px 12px 4px; font-size:13px;
            color:var(--text2,#7d849a); line-height:1.5;
        ">
            Hey! I'm your strategy advisor for this report. Ask me anything about the analysis, channels, or next steps.
        </div>
    </div>
    <div style="padding:12px; border-top:1px solid var(--border,#1e222d); display:flex; gap:8px;">
        <input id="chat-input" type="text" placeholder="Ask about your strategy..."
            style="flex:1; background:var(--surface,#161920); border:1px solid var(--border2,#2a2f3d);
            border-radius:8px; padding:10px 14px; color:var(--white,#eaedf3);
            font-size:13px; font-family:'Inter',sans-serif; outline:none;"
            onkeydown="if(event.key==='Enter')sendChat()"
        >
        <button onclick="sendChat()" style="
            background:var(--accent,#4f8af7); color:#fff; border:none;
            border-radius:8px; padding:10px 16px; font-size:13px;
            font-weight:600; cursor:pointer;
        ">Send</button>
    </div>
</div>
<button id="chat-toggle" onclick="toggleChat()" style="
    position:fixed; bottom:24px; right:24px; z-index:8999;
    width:56px; height:56px; border-radius:50%;
    background:var(--accent,#4f8af7); border:none;
    cursor:pointer; box-shadow:0 4px 20px rgba(79,138,247,.4);
    display:flex; align-items:center; justify-content:center;
    transition:transform .15s;
" onmouseover="this.style.transform='scale(1.08)'" onmouseout="this.style.transform='scale(1)'">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
    </svg>
</button>"""


def _chat_widget_js(report_id: str) -> str:
    """Chat widget JavaScript — sends messages to /advisor/chat."""
    return f"""
var chatOpen = false;
function toggleChat(){{
    chatOpen = !chatOpen;
    document.getElementById('chat-widget').style.display = chatOpen ? 'flex' : 'none';
    document.getElementById('chat-toggle').style.display = chatOpen ? 'none' : 'flex';
    if(chatOpen) document.getElementById('chat-input').focus();
}}

function sendChat(){{
    var input = document.getElementById('chat-input');
    var msg = input.value.trim();
    if(!msg) return;
    input.value = '';

    var msgs = document.getElementById('chat-messages');
    msgs.innerHTML += '<div style="background:var(--accent,#4f8af7);color:#fff;padding:10px 14px;border-radius:12px 12px 4px 12px;font-size:13px;align-self:flex-end;max-width:80%">'+msg.replace(/</g,'&lt;')+'</div>';
    msgs.scrollTop = msgs.scrollHeight;

    msgs.innerHTML += '<div id="typing" style="color:var(--text3);font-size:12px;font-style:italic">Thinking...</div>';
    msgs.scrollTop = msgs.scrollHeight;

    fetch('/advisor/chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{report_id: '{report_id}', message: msg}})
    }})
    .then(function(r){{ return r.json() }})
    .then(function(d){{
        var t = document.getElementById('typing');
        if(t) t.remove();
        var reply = d.reply || d.error || 'Sorry, I could not process that.';
        msgs.innerHTML += '<div style="background:var(--surface,#161920);padding:10px 14px;border-radius:12px 12px 12px 4px;font-size:13px;color:var(--text2,#7d849a);line-height:1.5;max-width:85%">'+reply.replace(/</g,'&lt;').replace(/\\n/g,'<br>')+'</div>';
        msgs.scrollTop = msgs.scrollHeight;
    }})
    .catch(function(){{
        var t = document.getElementById('typing');
        if(t) t.remove();
        msgs.innerHTML += '<div style="color:#ff4444;font-size:12px;padding:6px 14px">Failed to connect to advisor.</div>';
    }});
}}
"""
