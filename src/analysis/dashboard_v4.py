"""
Dashboard v4 — Formal BI-style dashboard with spreadsheet tabs.

Design language:
  - Dark but structured (not flashy)
  - Tab-based navigation: Overview | Channels | Leads | Investors | Strategy
  - Spreadsheet-like tables for leads & investors
  - Emphasis on "living intelligence" — data updates over time
  - Clean metric cards, minimal prose, data-forward
"""

from html import escape
from datetime import datetime, timezone


def render_dashboard_v4(
    analysis: dict,
    startup_name: str,
    report_id: str,
    tier: str = "free",
    checkout_url: str = "#",
    upgrade_url: str = "#",
) -> str:
    profile = analysis.get("company_profile", {})
    channels = analysis.get("channel_analysis", [])
    bullseye = analysis.get("bullseye_ranking", {})
    plan = analysis.get("ninety_day_plan", {})
    budget = analysis.get("budget_allocation", {})
    risks = analysis.get("risk_matrix", [])
    moat = analysis.get("competitive_moat", "")
    hot_take = analysis.get("hot_take", "")
    leads_data = analysis.get("leads_research", {})
    investors_data = analysis.get("investor_research", {})

    # Stats
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

    now_str = datetime.now(tz=timezone.utc).strftime("%b %d, %Y %H:%M UTC")

    inner = bullseye.get("inner_ring", {}).get("channels", [])
    promising = bullseye.get("promising", {}).get("channels", [])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>mckoutie — {_e(startup_name)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{_css_v4()}
</style>
</head>
<body>

{_topbar(startup_name, now_str, tier)}

<div class="layout">
  {_sidebar(startup_name, profile, top_score, top_channel, avg_score, len(leads), len(all_investors), len(competitors))}
  <main class="main">
    <div class="tabs" id="tabs">
      <button class="tab active" data-tab="overview">Overview</button>
      <button class="tab" data-tab="channels">Channels <span class="badge">{len(channels)}</span></button>
      <button class="tab" data-tab="leads">Leads <span class="badge">{len(leads)}</span></button>
      <button class="tab" data-tab="investors">Investors <span class="badge">{len(all_investors)}</span></button>
      <button class="tab" data-tab="strategy">Strategy</button>
    </div>

    <div class="tab-content active" id="tab-overview">
      {_overview_tab(profile, hot_take, sorted_ch, inner, promising, personas, tier)}
    </div>

    <div class="tab-content" id="tab-channels">
      {_channels_tab(sorted_ch, tier)}
    </div>

    <div class="tab-content" id="tab-leads">
      {_leads_tab(leads, personas, tier, checkout_url)}
    </div>

    <div class="tab-content" id="tab-investors">
      {_investors_tab(competitors, comp_investors, mkt_investors, tier, upgrade_url)}
    </div>

    <div class="tab-content" id="tab-strategy">
      {_strategy_tab(plan, budget, risks, moat, tier, checkout_url)}
    </div>
  </main>
</div>

{_pricing_bar(tier, checkout_url, upgrade_url)}

<script>
{_js()}
</script>
</body>
</html>"""


def _e(t):
    return escape(str(t)) if t else ""


# ────────────────────────────────────────────
# CSS
# ────────────────────────────────────────────
def _css_v4():
    return """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0c0f14;
  --surface:#12161e;
  --surface2:#1a1f2b;
  --surface3:#232a38;
  --border:#2a3040;
  --border2:#363f52;
  --text:#d4d8e0;
  --text2:#8a92a4;
  --text3:#5a6478;
  --white:#f0f2f5;
  --accent:#3b82f6;
  --accent2:#60a5fa;
  --green:#22c55e;
  --green2:#16a34a;
  --amber:#f59e0b;
  --red:#ef4444;
  --cyan:#06b6d4;
  --purple:#a855f7;
  --radius:6px;
  --mono:'JetBrains Mono',monospace;
  --sans:'Inter',system-ui,sans-serif;
}
body{font-family:var(--sans);background:var(--bg);color:var(--text);line-height:1.5;font-size:13px}
a{color:var(--accent2);text-decoration:none}a:hover{text-decoration:underline}

/* Top bar */
.topbar{display:flex;align-items:center;justify-content:space-between;padding:0 20px;height:44px;background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}
.topbar-left{display:flex;align-items:center;gap:12px}
.topbar-logo{font-family:var(--mono);font-weight:700;font-size:14px;color:var(--white);letter-spacing:-0.5px}
.topbar-logo span{color:var(--accent)}
.topbar-sep{color:var(--border2);font-size:18px}
.topbar-name{color:var(--text2);font-size:13px;font-weight:500}
.topbar-right{display:flex;align-items:center;gap:16px}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--green);display:inline-block;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.live-label{font-size:11px;color:var(--green);font-weight:500;display:flex;align-items:center;gap:5px}
.topbar-time{font-size:11px;color:var(--text3);font-family:var(--mono)}
.topbar-tier{font-size:10px;padding:2px 8px;border-radius:3px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.tier-free{background:#1e293b;color:var(--text2)}
.tier-starter{background:#1e3a5f;color:var(--accent2)}
.tier-growth{background:#2d1b4e;color:var(--purple)}

/* Layout */
.layout{display:flex;min-height:calc(100vh - 44px)}
.sidebar{width:260px;background:var(--surface);border-right:1px solid var(--border);padding:20px 16px;flex-shrink:0;position:sticky;top:44px;height:calc(100vh - 44px);overflow-y:auto}
.main{flex:1;padding:20px 24px;overflow-y:auto}

/* Sidebar */
.sb-section{margin-bottom:24px}
.sb-label{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--text3);margin-bottom:8px;font-weight:600}
.sb-company{font-size:16px;font-weight:700;color:var(--white);margin-bottom:4px}
.sb-oneliner{font-size:12px;color:var(--text2);line-height:1.4}
.sb-stat{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border)}
.sb-stat:last-child{border-bottom:none}
.sb-stat-label{font-size:12px;color:var(--text2)}
.sb-stat-value{font-size:13px;font-weight:600;color:var(--white);font-family:var(--mono)}
.sb-score-big{font-size:36px;font-weight:700;color:var(--accent);font-family:var(--mono);line-height:1}
.sb-score-label{font-size:11px;color:var(--text3);margin-top:2px}
.sb-tag{display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:500;margin:2px;background:var(--surface3);color:var(--text2)}

/* Tabs */
.tabs{display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:20px;position:sticky;top:44px;background:var(--bg);z-index:50;padding-top:4px}
.tab{padding:10px 18px;background:none;border:none;color:var(--text2);font-size:13px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;font-family:var(--sans);transition:all .15s}
.tab:hover{color:var(--text)}
.tab.active{color:var(--white);border-bottom-color:var(--accent)}
.tab .badge{font-size:10px;background:var(--surface3);color:var(--text2);padding:1px 6px;border-radius:10px;margin-left:4px}
.tab.active .badge{background:var(--accent);color:var(--white)}
.tab-content{display:none}
.tab-content.active{display:block}

/* Cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px}
.card-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--text3);margin-bottom:6px;font-weight:600}
.card-value{font-size:22px;font-weight:700;color:var(--white);font-family:var(--mono)}
.card-sub{font-size:11px;color:var(--text2);margin-top:4px}
.card-green .card-value{color:var(--green)}
.card-blue .card-value{color:var(--accent2)}
.card-amber .card-value{color:var(--amber)}

/* Section headers */
.section{margin-bottom:28px}
.section-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.section-title{font-size:14px;font-weight:600;color:var(--white)}
.section-badge{font-size:10px;padding:2px 8px;border-radius:3px;font-weight:500}
.badge-live{background:rgba(34,197,94,.15);color:var(--green)}
.badge-locked{background:rgba(239,68,68,.15);color:var(--red)}

/* Tables (spreadsheet style) */
.table-wrap{border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{background:var(--surface2)}
th{padding:8px 12px;text-align:left;font-weight:600;color:var(--text2);font-size:11px;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:8px 12px;border-bottom:1px solid var(--border);color:var(--text);vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--surface2)}
.td-name{font-weight:600;color:var(--white)}
.td-score{font-family:var(--mono);font-weight:600}
.td-platform{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:500}
.p-twitter{background:#1d3a5c;color:#60a5fa}
.p-linkedin{background:#1a3a5c;color:#38bdf8}
.p-reddit{background:#4a2020;color:#f87171}
.p-discord{background:#3b2d60;color:#c084fc}
.p-github{background:#2a2a2a;color:#d4d4d4}
.p-substack{background:#4a3020;color:#fb923c}
.p-vc{background:#1e3a2e;color:#4ade80}
.p-angel{background:#3a3a1e;color:#facc15}

/* Score bar (mini) */
.score-bar{display:flex;align-items:center;gap:6px}
.score-fill{height:6px;border-radius:3px;background:var(--accent)}
.score-track{flex:1;height:6px;border-radius:3px;background:var(--surface3)}
.score-num{font-family:var(--mono);font-size:12px;font-weight:600;width:20px;text-align:right}

/* Hot take */
.hottake{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--amber);border-radius:var(--radius);padding:16px;margin-bottom:20px}
.hottake-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--amber);margin-bottom:6px;font-weight:600}
.hottake-text{font-size:13px;color:var(--text);line-height:1.6}

/* Bullseye compact */
.bullseye{display:flex;gap:12px;margin-bottom:20px}
.ring{flex:1;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:14px}
.ring-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.ring-inner .ring-label{color:var(--green)}
.ring-promising .ring-label{color:var(--amber)}
.ring-longshot .ring-label{color:var(--text3)}
.ring-dot{width:8px;height:8px;border-radius:50%}
.ring-inner .ring-dot{background:var(--green)}
.ring-promising .ring-dot{background:var(--amber)}
.ring-longshot .ring-dot{background:var(--text3)}
.ring-list{list-style:none;font-size:12px;color:var(--text2)}
.ring-list li{padding:2px 0}

/* Persona cards */
.persona-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:20px}
.persona{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:14px}
.persona-name{font-size:13px;font-weight:600;color:var(--white);margin-bottom:4px}
.persona-desc{font-size:11px;color:var(--text2);line-height:1.4;margin-bottom:8px}
.persona-platforms{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px}
.persona-signals{list-style:none;font-size:11px;color:var(--text3)}
.persona-signals li{padding:1px 0}
.persona-signals li::before{content:'"';color:var(--text3)}
.persona-signals li::after{content:'"'}

/* Competitor row */
.comp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:16px}
.comp-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:12px}
.comp-name{font-size:13px;font-weight:600;color:var(--white)}
.comp-funding{font-size:16px;font-weight:700;color:var(--green);font-family:var(--mono);margin:4px 0}
.comp-desc{font-size:11px;color:var(--text3);margin-bottom:6px}
.comp-investors{font-size:11px;color:var(--text2)}

/* Strategy section */
.plan-months{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.plan-month{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:14px}
.plan-month-title{font-size:12px;font-weight:600;color:var(--accent2);margin-bottom:4px}
.plan-month-focus{font-size:13px;font-weight:600;color:var(--white);margin-bottom:8px}
.plan-month-actions{list-style:none;font-size:11px;color:var(--text2)}
.plan-month-actions li{padding:2px 0;padding-left:12px;position:relative}
.plan-month-actions li::before{content:'→';position:absolute;left:0;color:var(--text3)}
.plan-metric{font-size:11px;color:var(--green);margin-top:8px;font-weight:500}
.plan-budget{font-size:11px;color:var(--text3);font-family:var(--mono)}

/* Pricing bar */
.pricing-bar{position:fixed;bottom:0;left:0;right:0;background:var(--surface);border-top:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;justify-content:center;gap:24px;z-index:100}
.pricing-bar.hidden{display:none}
.pricing-option{display:flex;align-items:center;gap:8px;padding:6px 16px;border-radius:var(--radius);border:1px solid var(--border);font-size:12px;cursor:pointer;transition:all .15s}
.pricing-option:hover{border-color:var(--accent);background:var(--surface2)}
.pricing-option.current{border-color:var(--green);background:rgba(34,197,94,.08)}
.pricing-price{font-weight:700;color:var(--white);font-family:var(--mono)}
.pricing-name{font-weight:600;color:var(--text)}
.pricing-desc{color:var(--text3);font-size:11px}
.cta-btn{padding:8px 20px;background:var(--accent);color:var(--white);border:none;border-radius:var(--radius);font-size:12px;font-weight:600;cursor:pointer;font-family:var(--sans);transition:background .15s}
.cta-btn:hover{background:#2563eb;text-decoration:none}

/* Lock overlay */
.locked{position:relative;overflow:hidden}
.locked::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,transparent 30%,var(--bg) 90%);pointer-events:none}
.lock-msg{text-align:center;padding:16px;color:var(--text2);font-size:12px}
.lock-msg a{color:var(--accent2);font-weight:500}

/* Responsive */
@media(max-width:900px){
  .layout{flex-direction:column}
  .sidebar{width:100%;height:auto;position:static;border-right:none;border-bottom:1px solid var(--border)}
  .bullseye{flex-direction:column}
  .plan-months{grid-template-columns:1fr}
  .tabs{overflow-x:auto;white-space:nowrap}
}
@media(max-width:600px){
  .main{padding:12px}
  .cards{grid-template-columns:1fr 1fr}
  .comp-grid{grid-template-columns:1fr}
  .persona-grid{grid-template-columns:1fr}
}

/* Utility */
.muted{color:var(--text3)}
.mono{font-family:var(--mono)}
.mt-4{margin-top:16px}
.mb-2{margin-bottom:8px}
.text-sm{font-size:11px}
"""


# ────────────────────────────────────────────
# Components
# ────────────────────────────────────────────

def _topbar(name, now_str, tier):
    tier_class = f"tier-{tier}"
    tier_label = tier.upper()
    return f"""
<div class="topbar">
  <div class="topbar-left">
    <div class="topbar-logo">mckoutie<span>&</span>co</div>
    <span class="topbar-sep">|</span>
    <span class="topbar-name">{_e(name)}</span>
  </div>
  <div class="topbar-right">
    <span class="live-label"><span class="live-dot"></span> Live Intelligence</span>
    <span class="topbar-time">{_e(now_str)}</span>
    <span class="topbar-tier {tier_class}">{tier_label}</span>
  </div>
</div>"""


def _sidebar(name, profile, top_score, top_channel, avg_score, n_leads, n_investors, n_competitors):
    stage = _e(profile.get("stage", "—"))
    size = _e(profile.get("estimated_size", "—"))
    market = _e(profile.get("market", "—"))
    model = _e(profile.get("business_model", "—"))

    strengths = profile.get("strengths", [])
    weaknesses = profile.get("weaknesses", [])

    strengths_html = "".join(f'<span class="sb-tag" style="border-left:2px solid var(--green)">{_e(s[:50])}</span>' for s in strengths[:4])
    weaknesses_html = "".join(f'<span class="sb-tag" style="border-left:2px solid var(--red)">{_e(w[:50])}</span>' for w in weaknesses[:3])

    return f"""
<aside class="sidebar">
  <div class="sb-section">
    <div class="sb-label">Company</div>
    <div class="sb-company">{_e(name)}</div>
    <div class="sb-oneliner">{_e(profile.get("one_liner", ""))}</div>
  </div>

  <div class="sb-section">
    <div class="sb-label">Top Score</div>
    <div class="sb-score-big">{top_score}</div>
    <div class="sb-score-label">{_e(top_channel)}</div>
  </div>

  <div class="sb-section">
    <div class="sb-stat"><span class="sb-stat-label">Avg Score</span><span class="sb-stat-value">{avg_score}</span></div>
    <div class="sb-stat"><span class="sb-stat-label">Stage</span><span class="sb-stat-value">{stage}</span></div>
    <div class="sb-stat"><span class="sb-stat-label">Size</span><span class="sb-stat-value">{size}</span></div>
    <div class="sb-stat"><span class="sb-stat-label">Leads Found</span><span class="sb-stat-value" style="color:var(--green)">{n_leads}</span></div>
    <div class="sb-stat"><span class="sb-stat-label">Investors</span><span class="sb-stat-value" style="color:var(--cyan)">{n_investors}</span></div>
    <div class="sb-stat"><span class="sb-stat-label">Competitors</span><span class="sb-stat-value" style="color:var(--amber)">{n_competitors}</span></div>
  </div>

  <div class="sb-section">
    <div class="sb-label">Market</div>
    <div style="font-size:11px;color:var(--text2);line-height:1.4">{market}</div>
  </div>

  <div class="sb-section">
    <div class="sb-label">Model</div>
    <div style="font-size:11px;color:var(--text2);line-height:1.4">{model}</div>
  </div>

  <div class="sb-section">
    <div class="sb-label">Strengths</div>
    <div>{strengths_html}</div>
  </div>

  <div class="sb-section">
    <div class="sb-label">Risks</div>
    <div>{weaknesses_html}</div>
  </div>
</aside>"""


# ────────────────────────────────────────────
# Overview Tab
# ────────────────────────────────────────────
def _overview_tab(profile, hot_take, channels, inner, promising, personas, tier):
    # Top 4 metric cards
    top3 = channels[:3] if channels else []
    cards = f"""
<div class="cards">
  <div class="card card-green">
    <div class="card-label">Top Channel</div>
    <div class="card-value">{channels[0].get("score",0) if channels else 0}</div>
    <div class="card-sub">{_e(channels[0].get("channel","") if channels else "")}</div>
  </div>
  <div class="card card-blue">
    <div class="card-label">Inner Ring</div>
    <div class="card-value">{len(inner)}</div>
    <div class="card-sub">high-priority channels</div>
  </div>
  <div class="card card-amber">
    <div class="card-label">Promising</div>
    <div class="card-value">{len(promising)}</div>
    <div class="card-sub">worth testing</div>
  </div>
  <div class="card">
    <div class="card-label">Total Channels</div>
    <div class="card-value">{len(channels)}</div>
    <div class="card-sub">analyzed</div>
  </div>
</div>"""

    # Hot take
    ht = f"""
<div class="hottake">
  <div class="hottake-label">Hot Take</div>
  <div class="hottake-text">{_e(hot_take)}</div>
</div>""" if hot_take else ""

    # Bullseye
    inner_items = "".join(f"<li>{_e(c)}</li>" for c in inner)
    prom_items = "".join(f"<li>{_e(c)}</li>" for c in promising)
    longshot = [c.get("channel", "") for c in channels if c.get("channel", "") not in inner and c.get("channel", "") not in promising]
    long_items = "".join(f"<li>{_e(c)}</li>" for c in longshot[:6])

    bullseye = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Bullseye Framework</span></div>
  <div class="bullseye">
    <div class="ring ring-inner">
      <div class="ring-label"><span class="ring-dot"></span> Inner Ring</div>
      <ul class="ring-list">{inner_items}</ul>
    </div>
    <div class="ring ring-promising">
      <div class="ring-label"><span class="ring-dot"></span> Promising</div>
      <ul class="ring-list">{prom_items}</ul>
    </div>
    <div class="ring ring-longshot">
      <div class="ring-label"><span class="ring-dot"></span> Long Shot</div>
      <ul class="ring-list">{long_items}</ul>
    </div>
  </div>
</div>"""

    # Top channels mini-table
    top5_rows = ""
    for ch in channels[:5]:
        score = ch.get("score", 0)
        color = "var(--green)" if score >= 8 else "var(--amber)" if score >= 6 else "var(--text3)"
        pct = score * 10
        top5_rows += f"""
<tr>
  <td class="td-name">{_e(ch.get("channel",""))}</td>
  <td><div class="score-bar"><span class="score-num" style="color:{color}">{score}</span><div class="score-track"><div class="score-fill" style="width:{pct}%;background:{color}"></div></div></div></td>
  <td class="muted">{_e(ch.get("effort",""))}</td>
  <td class="muted">{_e(ch.get("timeline",""))}</td>
  <td style="font-size:11px;color:var(--text2);max-width:300px">{_e(ch.get("killer_insight","")[:120])}</td>
</tr>"""

    top_table = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Top Channels</span></div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Channel</th><th style="width:140px">Score</th><th>Effort</th><th>Timeline</th><th>Key Insight</th></tr></thead>
      <tbody>{top5_rows}</tbody>
    </table>
  </div>
</div>"""

    # Personas mini-view
    personas_html = ""
    if personas:
        persona_cards = ""
        for p in personas[:3]:
            platforms = "".join(f'<span class="td-platform {_platform_class(pl)}">{_e(pl)}</span>' for pl in p.get("platforms", []))
            signals = "".join(f"<li>{_e(s[:80])}</li>" for s in p.get("pain_signals", [])[:2])
            persona_cards += f"""
<div class="persona">
  <div class="persona-name">{_e(p.get("name",""))}</div>
  <div class="persona-desc">{_e(p.get("description","")[:150])}</div>
  <div class="persona-platforms">{platforms}</div>
  <div class="persona-signals"><ul class="persona-signals">{signals}</ul></div>
</div>"""
        personas_html = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Target Personas</span></div>
  <div class="persona-grid">{persona_cards}</div>
</div>"""

    return cards + ht + bullseye + top_table + personas_html


# ────────────────────────────────────────────
# Channels Tab
# ────────────────────────────────────────────
def _channels_tab(channels, tier):
    rows = ""
    for i, ch in enumerate(channels):
        score = ch.get("score", 0)
        color = "var(--green)" if score >= 8 else "var(--amber)" if score >= 6 else "var(--text3)"
        pct = score * 10

        ideas = ch.get("specific_ideas", [])
        ideas_html = ""
        if tier in ("starter", "growth"):
            ideas_html = "<br>".join(f"<span style='color:var(--text2);font-size:11px'>• {_e(idea[:100])}</span>" for idea in ideas[:3])
        else:
            ideas_html = "<span style='color:var(--text3);font-size:11px'>Unlock with Starter plan →</span>" if ideas else ""

        first_move = ""
        if tier in ("starter", "growth"):
            first_move = f"<span style='font-size:11px;color:var(--text)'>{_e(ch.get('first_move','')[:120])}</span>"
        else:
            first_move = "<span style='color:var(--text3);font-size:11px'>—</span>"

        rows += f"""
<tr>
  <td style="width:28px;color:var(--text3);font-family:var(--mono);font-size:11px">{i+1}</td>
  <td class="td-name">{_e(ch.get("channel",""))}</td>
  <td><div class="score-bar"><span class="score-num" style="color:{color}">{score}</span><div class="score-track"><div class="score-fill" style="width:{pct}%;background:{color}"></div></div></div></td>
  <td class="muted">{_e(ch.get("effort",""))}</td>
  <td class="muted">{_e(ch.get("timeline",""))}</td>
  <td class="mono muted">{_e(ch.get("budget",""))}</td>
  <td style="max-width:250px">{first_move}</td>
  <td style="max-width:250px">{ideas_html}</td>
</tr>"""

    return f"""
<div class="section">
  <div class="section-head">
    <span class="section-title">All Channels — Ranked by Score</span>
    <span class="section-badge badge-live">Live</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>#</th><th>Channel</th><th style="width:140px">Score</th><th>Effort</th><th>Timeline</th><th>Budget</th>
        <th>First Move</th><th>Ideas</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


# ────────────────────────────────────────────
# Leads Tab
# ────────────────────────────────────────────
def _leads_tab(leads, personas, tier, checkout_url):
    # Personas section
    persona_cards = ""
    for p in personas[:3]:
        platforms = "".join(f'<span class="td-platform {_platform_class(pl)}">{_e(pl)}</span>' for pl in p.get("platforms", []))
        signals = "".join(f"<li>{_e(s[:100])}</li>" for s in p.get("pain_signals", [])[:3])
        persona_cards += f"""
<div class="persona">
  <div class="persona-name">{_e(p.get("name",""))}</div>
  <div class="persona-desc">{_e(p.get("description",""))}</div>
  <div class="persona-platforms">{platforms}</div>
  <ul class="persona-signals">{signals}</ul>
</div>"""

    personas_section = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Customer Personas</span></div>
  <div class="persona-grid">{persona_cards}</div>
</div>""" if personas else ""

    # Leads table (always visible)
    lead_rows = ""
    for i, lead in enumerate(leads):
        score = lead.get("score", 0)
        color = "var(--green)" if score >= 8 else "var(--amber)" if score >= 6 else "var(--text3)"
        platform = lead.get("platform", "")
        handle = lead.get("handle", "")
        url = lead.get("url", "#")

        # Relevance always shown (it's the hook)
        relevance = _e(lead.get("relevance", "")[:150])

        lead_rows += f"""
<tr>
  <td style="width:28px;color:var(--text3);font-family:var(--mono);font-size:11px">{i+1}</td>
  <td class="td-name"><a href="{_e(url)}" target="_blank">{_e(lead.get("name",""))}</a></td>
  <td style="font-size:11px;color:var(--text2)">{_e(lead.get("title",""))}</td>
  <td><span class="td-platform {_platform_class(platform)}">{_e(platform)}</span></td>
  <td style="font-family:var(--mono);font-size:11px;color:var(--text2)">{_e(handle)}</td>
  <td class="td-score" style="color:{color}">{score}/10</td>
  <td style="font-size:11px;color:var(--text2);max-width:300px">{relevance}</td>
</tr>"""

    leads_table = f"""
<div class="section">
  <div class="section-head">
    <span class="section-title">Potential Leads</span>
    <span class="section-badge badge-live">Updating Weekly</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>#</th><th>Name</th><th>Title</th><th>Platform</th><th>Handle</th><th>Score</th><th>Why They're a Lead</th></tr></thead>
      <tbody>{lead_rows}</tbody>
    </table>
  </div>
</div>"""

    # Outreach strategies (locked for free)
    outreach = ""
    if tier == "free" and leads:
        outreach = f"""
<div class="section">
  <div class="card" style="text-align:center;padding:24px;border:1px dashed var(--border2)">
    <div style="font-size:13px;color:var(--text2);margin-bottom:8px">Outreach strategies, personalized messaging, and approach angles for each lead</div>
    <a href="{_e(checkout_url)}" class="cta-btn" style="display:inline-block;text-decoration:none">Unlock with Starter — $39/mo</a>
  </div>
</div>"""

    return personas_section + leads_table + outreach


# ────────────────────────────────────────────
# Investors Tab
# ────────────────────────────────────────────
def _investors_tab(competitors, comp_investors, mkt_investors, tier, upgrade_url):
    # Competitors grid
    comp_cards = ""
    for c in competitors:
        inv_list = ", ".join(c.get("investors", [])[:3])
        comp_cards += f"""
<div class="comp-card">
  <div class="comp-name"><a href="{_e(c.get('url','#'))}" target="_blank">{_e(c.get("name",""))}</a></div>
  <div class="comp-funding">{_e(c.get("funding","—"))}</div>
  <div class="comp-desc">{_e(c.get("description","")[:80])}</div>
  <div class="comp-investors">Investors: {_e(inv_list)}</div>
</div>"""

    comp_section = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Competitor Landscape</span></div>
  <div class="comp-grid">{comp_cards}</div>
</div>""" if competitors else ""

    # All investors table
    all_investors = []
    for inv in comp_investors:
        all_investors.append({**inv, "_source": "Competitor Portfolio"})
    for inv in mkt_investors:
        all_investors.append({**inv, "_source": "Market Search"})

    inv_rows = ""
    for i, inv in enumerate(all_investors):
        inv_type = inv.get("type", "VC")
        type_class = "p-vc" if inv_type == "VC" else "p-angel" if inv_type == "Angel" else "p-vc"
        url = inv.get("url", "#")
        source = inv.get("_source", "")

        inv_rows += f"""
<tr>
  <td style="width:28px;color:var(--text3);font-family:var(--mono);font-size:11px">{i+1}</td>
  <td class="td-name"><a href="{_e(url)}" target="_blank">{_e(inv.get("name",""))}</a></td>
  <td><span class="td-platform {type_class}">{_e(inv_type)}</span></td>
  <td style="font-size:11px;color:var(--text2);max-width:350px">{_e(inv.get("focus","")[:150])}</td>
  <td style="font-size:11px"><span class="td-platform" style="background:var(--surface3)">{_e(source)}</span></td>
</tr>"""

    inv_table = f"""
<div class="section">
  <div class="section-head">
    <span class="section-title">Investor Intelligence</span>
    <span class="section-badge badge-live">Updating Weekly</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>#</th><th>Investor</th><th>Type</th><th>Focus / Thesis</th><th>Source</th></tr></thead>
      <tbody>{inv_rows}</tbody>
    </table>
  </div>
</div>"""

    # Locked deep-dive for non-growth
    deep_dive = ""
    if tier in ("free", "starter"):
        deep_dive = f"""
<div class="section">
  <div class="card" style="text-align:center;padding:24px;border:1px dashed var(--border2)">
    <div style="font-size:13px;color:var(--text2);margin-bottom:8px">Portfolio analysis, warm intro paths, thesis alignment scores, and outreach templates</div>
    <a href="{_e(upgrade_url)}" class="cta-btn" style="display:inline-block;text-decoration:none;background:var(--purple)">Unlock with Growth — $200/mo</a>
  </div>
</div>"""

    return comp_section + inv_table + deep_dive


# ────────────────────────────────────────────
# Strategy Tab
# ────────────────────────────────────────────
def _strategy_tab(plan, budget, risks, moat, tier, checkout_url):
    if tier == "free":
        return f"""
<div class="section">
  <div class="card" style="text-align:center;padding:40px 24px;border:1px dashed var(--border2)">
    <div style="font-size:18px;font-weight:600;color:var(--white);margin-bottom:8px">90-Day Action Plan</div>
    <div style="font-size:13px;color:var(--text2);margin-bottom:4px">Month-by-month breakdown with specific actions, budgets, and target metrics</div>
    <div style="font-size:13px;color:var(--text2);margin-bottom:16px">Plus: budget allocation, risk matrix, and competitive moat analysis</div>
    <a href="{_e(checkout_url)}" class="cta-btn" style="display:inline-block;text-decoration:none">Unlock Strategy — $39/mo</a>
  </div>
</div>"""

    # 90-day plan
    months_html = ""
    for key, label in [("month_1", "Month 1"), ("month_2", "Month 2"), ("month_3", "Month 3")]:
        m = plan.get(key, {})
        actions = "".join(f"<li>{_e(a[:100])}</li>" for a in m.get("actions", []))
        months_html += f"""
<div class="plan-month">
  <div class="plan-month-title">{label}</div>
  <div class="plan-month-focus">{_e(m.get("focus",""))}</div>
  <ul class="plan-month-actions">{actions}</ul>
  <div class="plan-metric">Target: {_e(m.get("target_metric",""))}</div>
  <div class="plan-budget">Budget: {_e(m.get("budget",""))}</div>
</div>"""

    plan_section = f"""
<div class="section">
  <div class="section-head"><span class="section-title">90-Day Action Plan</span></div>
  <div class="plan-months">{months_html}</div>
</div>"""

    # Budget
    budget_rows = ""
    for b in budget.get("breakdown", []):
        budget_rows += f"""
<tr>
  <td class="td-name">{_e(b.get("channel",""))}</td>
  <td class="mono" style="color:var(--green)">{_e(b.get("amount",""))}</td>
  <td style="font-size:11px;color:var(--text2)">{_e(b.get("rationale",""))}</td>
</tr>"""

    budget_section = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Budget Allocation</span><span style="font-size:12px;color:var(--text2);font-family:var(--mono)">{_e(budget.get("total_recommended",""))}</span></div>
  <div class="table-wrap">
    <table>
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
        prob_color = "var(--red)" if prob == "high" else "var(--amber)" if prob == "medium" else "var(--text2)"
        impact_color = "var(--red)" if impact == "high" else "var(--amber)" if impact == "medium" else "var(--text2)"
        risk_rows += f"""
<tr>
  <td style="font-size:12px;color:var(--text)">{_e(r.get("risk",""))}</td>
  <td style="color:{prob_color};font-weight:500;font-size:11px;text-transform:uppercase">{_e(prob)}</td>
  <td style="color:{impact_color};font-weight:500;font-size:11px;text-transform:uppercase">{_e(impact)}</td>
  <td style="font-size:11px;color:var(--text2)">{_e(r.get("mitigation",""))}</td>
</tr>"""

    risk_section = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Risk Matrix</span></div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Risk</th><th>Probability</th><th>Impact</th><th>Mitigation</th></tr></thead>
      <tbody>{risk_rows}</tbody>
    </table>
  </div>
</div>"""

    # Moat
    moat_section = f"""
<div class="section">
  <div class="section-head"><span class="section-title">Competitive Moat</span></div>
  <div class="card">
    <div style="font-size:13px;color:var(--text);line-height:1.6">{_e(moat)}</div>
  </div>
</div>""" if moat else ""

    return plan_section + budget_section + risk_section + moat_section


# ────────────────────────────────────────────
# Pricing Bar
# ────────────────────────────────────────────
def _pricing_bar(tier, checkout_url, upgrade_url):
    if tier == "growth":
        return '<div class="pricing-bar hidden"></div>'

    if tier == "starter":
        return f"""
<div class="pricing-bar">
  <div class="pricing-option current">
    <span class="pricing-name">Starter</span>
    <span class="pricing-price">$39/mo</span>
  </div>
  <div class="pricing-option" style="border-color:var(--purple)">
    <div>
      <span class="pricing-name">Growth</span>
      <span class="pricing-price" style="color:var(--purple)">$200/mo</span>
    </div>
    <span class="pricing-desc">Deep investor intel + weekly updates</span>
  </div>
  <a href="{_e(upgrade_url)}" class="cta-btn" style="background:var(--purple)">Upgrade</a>
  <div class="pricing-option">
    <span class="pricing-name">Enterprise</span>
    <span class="pricing-desc">emi@mckoutie.com</span>
  </div>
</div>"""

    # Free tier
    return f"""
<div class="pricing-bar">
  <div class="pricing-option current">
    <span class="pricing-name">Free</span>
    <span class="pricing-desc">You're here</span>
  </div>
  <div class="pricing-option" style="border-color:var(--accent)">
    <div>
      <span class="pricing-name">Starter</span>
      <span class="pricing-price">$39/mo</span>
    </div>
    <span class="pricing-desc">Full strategy + 90-day plan</span>
  </div>
  <a href="{_e(checkout_url)}" class="cta-btn">Get Full Strategy</a>
  <div class="pricing-option">
    <div>
      <span class="pricing-name">Growth</span>
      <span class="pricing-price" style="color:var(--purple)">$200/mo</span>
    </div>
    <span class="pricing-desc">Deep investor intel</span>
  </div>
  <div class="pricing-option">
    <span class="pricing-name">Enterprise</span>
    <span class="pricing-desc">emi@mckoutie.com</span>
  </div>
</div>"""


# ────────────────────────────────────────────
# JS (tab switching)
# ────────────────────────────────────────────
def _js():
    return """
document.querySelectorAll('.tab').forEach(function(tab){
  tab.addEventListener('click',function(){
    document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('active')});
    document.querySelectorAll('.tab-content').forEach(function(c){c.classList.remove('active')});
    tab.classList.add('active');
    document.getElementById('tab-'+tab.dataset.tab).classList.add('active');
  });
});

// Deep link from hash
var hash=window.location.hash.replace('#','');
if(hash){
  var t=document.querySelector('.tab[data-tab="'+hash+'"]');
  if(t) t.click();
}
"""


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────
def _platform_class(platform):
    p = (platform or "").lower()
    if "twitter" in p or "x" in p:
        return "p-twitter"
    if "linkedin" in p:
        return "p-linkedin"
    if "reddit" in p:
        return "p-reddit"
    if "discord" in p:
        return "p-discord"
    if "github" in p:
        return "p-github"
    if "substack" in p:
        return "p-substack"
    return ""
