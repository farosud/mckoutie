"""
FastAPI server — serves reports, handles Stripe webhooks, and Twitter OAuth.

Endpoints:
  GET  /                            — landing page
  GET  /report/{report_id}          — view report (login-gated for subscribers)
  POST /webhook/stripe              — Stripe payment webhook
  GET  /auth/twitter                — initiate Twitter OAuth 2.0 login
  GET  /auth/twitter/callback       — handle OAuth callback
  GET  /auth/logout                 — clear session
  GET  /health                      — health check
  GET  /stats                       — basic stats
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.modules import auth, payments, report_store
from src.analysis.report_generator import generate_report_html
from src.analysis.dashboard_renderer import render_dashboard
from src.analysis.dashboard_v3 import render_dashboard_v3
from src.analysis.dashboard_v4 import render_dashboard_v4
from src.analysis.dashboard_v5 import render_dashboard_v5

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
        <p>AI startup consulting for $39/mo instead of $100K.</p>

        <div class="how">
            <h2>How it works</h2>
            <p>1. Tweet <code>@mckoutie analyse my startup https://yoursite.com</code></p>
            <p>2. Or tag a company: <code>@mckoutie analyse my startup @company</code></p>
            <p>3. Get a free teaser thread with your top 3 growth channels</p>
            <p>4. Subscribe for $39/mo for the full strategy dashboard</p>
        </div>

        <p class="price">Starter: $39/mo | Growth: $200/mo | Enterprise: custom</p>

        <p>What you get:</p>
        <div class="how">
            <p>- 19-channel traction analysis scored for YOUR startup</p>
            <p>- Bullseye framework: top 3 channels to test NOW</p>
            <p>- 90-day action plan with weekly milestones</p>
            <p>- Budget allocation + risk matrix</p>
            <p>- 3 customer personas + 10 potential leads</p>
            <p>- Investor intelligence (competitor funding + VCs in your space)</p>
            <p>- Living report with monthly market updates</p>
        </div>

        <p style="color: var(--muted); margin-top: 2rem; font-size: 0.8rem;">
            Built with vibes. Not affiliated with McKinsey (obviously).
        </p>
    </div>
</body>
</html>"""


@app.get("/AR", response_class=HTMLResponse)
async def landing_ar():
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mckoutie Argentina — Consultoría de crecimiento para startups argentinas</title>
    <meta name="description" content="Análisis de tracción con IA para startups argentinas. 19 canales de crecimiento, plan de 90 días, y estrategia real por $39/mes. Sin humo, sin chamuyo.">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
        :root {
            --bg: #0a0a0a; --bg2: #111; --card: #141414; --border: #222;
            --text: #e0e0e0; --muted: #666; --accent: #75AADB; --accent2: #F5C518;
            --green: #00ff88; --orange: #ff6b35;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Space Grotesk', -apple-system, sans-serif;
            background: var(--bg); color: var(--text);
            line-height: 1.6; overflow-x: hidden;
        }
        .mono { font-family: 'Space Mono', monospace; }

        /* Hero */
        .hero {
            display: grid; grid-template-columns: 1fr 1fr;
            min-height: 90vh; align-items: center;
            padding: 4rem 3rem; gap: 2rem;
            position: relative; overflow: hidden;
            background: url('https://images.unsplash.com/photo-1662393372595-861498121e90?w=1920&q=80&auto=format&fit=crop') center center / cover no-repeat;
        }
        .hero::before {
            content: ''; position: absolute; inset: 0;
            background: rgba(10,10,10,0.75);
            pointer-events: none;
        }
        .hero-content-box {
            position: relative; z-index: 1;
            background: rgba(10,10,10,0.85);
            border: 1px solid rgba(117,170,219,0.2);
            border-radius: 12px;
            padding: 3rem 2.5rem;
            max-width: 650px;
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
        }
        .hero-building {
            position: relative; z-index: 1;
            display: flex; justify-content: center; align-items: center;
        }
        .hero-building svg {
            max-width: 100%; height: auto; max-height: 75vh;
            filter: drop-shadow(0 0 40px rgba(117,170,219,0.15));
        }
        .flag-bar {
            width: 100%; height: 3px; position: absolute; top: 0;
            background: linear-gradient(90deg, var(--accent) 33%, #fff 33%, #fff 66%, var(--accent) 66%);
            opacity: 0.4;
        }
        .logo { font-size: 3.5rem; font-weight: 700; letter-spacing: -2px; margin-bottom: 0.3rem; }
        .logo span { color: var(--accent); }
        .tagline-main {
            font-size: 1.6rem; color: var(--accent2); font-weight: 600;
            margin-bottom: 1rem;
        }
        .tagline-sub {
            font-size: 1.15rem; color: var(--muted); max-width: 550px;
            margin-bottom: 2.5rem;
        }
        .cta-hero {
            display: inline-block; background: var(--accent2); color: #0a0a0a;
            padding: 16px 40px; font-size: 1.1rem; font-weight: 700;
            text-decoration: none; border-radius: 6px; transition: all 0.2s;
            font-family: 'Space Mono', monospace; letter-spacing: 0.5px;
        }
        .cta-hero:hover { background: #e0b200; transform: translateY(-1px); }
        .scroll-hint {
            position: absolute; bottom: 2rem; color: var(--muted);
            font-size: 0.85rem; animation: bounce 2s infinite;
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(8px); }
        }

        /* Sections */
        section { padding: 5rem 2rem; max-width: 900px; margin: 0 auto; }
        .section-title {
            font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem;
        }
        .section-title span { color: var(--accent2); }
        .section-sub { color: var(--muted); margin-bottom: 2.5rem; font-size: 1.05rem; }

        /* Problema */
        .problema-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;
        }
        .problema-card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 1.5rem;
        }
        .problema-card .emoji { font-size: 1.8rem; margin-bottom: 0.5rem; }
        .problema-card h3 { color: var(--accent2); font-size: 1rem; margin-bottom: 0.5rem; }
        .problema-card p { color: var(--muted); font-size: 0.9rem; }

        /* How it works */
        .steps { counter-reset: step; }
        .step {
            display: flex; gap: 1.5rem; align-items: flex-start;
            margin-bottom: 2rem; position: relative;
        }
        .step-num {
            flex-shrink: 0; width: 48px; height: 48px;
            background: var(--card); border: 2px solid var(--accent);
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-weight: 700; color: var(--accent);
            font-family: 'Space Mono', monospace; font-size: 1.1rem;
        }
        .step-content h3 { font-size: 1.1rem; margin-bottom: 0.3rem; }
        .step-content p { color: var(--muted); font-size: 0.95rem; }
        .step-content code {
            background: #1a1a1a; color: var(--accent); padding: 3px 8px;
            border-radius: 4px; font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
        }

        /* What you get */
        .features {
            display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
        }
        .feature {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 1.2rem;
        }
        .feature .check { color: var(--green); margin-right: 0.5rem; font-weight: 700; }
        .feature h3 { font-size: 0.95rem; margin-bottom: 0.3rem; display: flex; align-items: center; }
        .feature p { color: var(--muted); font-size: 0.85rem; padding-left: 1.5rem; }

        /* Pricing */
        .pricing-grid {
            display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem;
        }
        .price-card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 10px; padding: 2rem 1.5rem; text-align: center;
            position: relative;
        }
        .price-card.featured {
            border-color: var(--accent2);
            box-shadow: 0 0 30px rgba(245,197,24,0.08);
        }
        .price-card .badge {
            position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
            background: var(--accent2); color: #0a0a0a; padding: 4px 16px;
            border-radius: 20px; font-size: 0.75rem; font-weight: 700;
        }
        .price-card h3 { font-size: 1.2rem; margin-bottom: 0.5rem; }
        .price-amount { font-size: 2.5rem; font-weight: 700; color: var(--accent2); }
        .price-amount span { font-size: 1rem; color: var(--muted); }
        .price-card ul {
            list-style: none; text-align: left; margin: 1.5rem 0;
            font-size: 0.85rem; color: var(--muted);
        }
        .price-card ul li { padding: 0.4rem 0; border-bottom: 1px solid #1a1a1a; }
        .price-card ul li::before { content: '→ '; color: var(--accent); }

        /* Argentine context */
        .context-box {
            background: var(--card); border-left: 3px solid var(--accent2);
            padding: 1.5rem 2rem; border-radius: 0 8px 8px 0;
            margin: 2rem 0;
        }
        .context-box p { color: var(--muted); font-size: 0.95rem; margin: 0.3rem 0; }
        .context-box strong { color: var(--text); }

        /* Testimonial / credibility */
        .credibility {
            text-align: center; padding: 3rem 2rem;
            border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
            margin: 2rem 0;
        }
        .credibility p { color: var(--muted); font-size: 1rem; max-width: 600px; margin: 0.5rem auto; }
        .credibility .highlight { color: var(--accent2); font-weight: 600; }

        /* CTA bottom */
        .cta-section {
            text-align: center; padding: 5rem 2rem;
        }
        .cta-section h2 { font-size: 2rem; margin-bottom: 1rem; }
        .cta-section p { color: var(--muted); margin-bottom: 2rem; max-width: 500px; margin-left: auto; margin-right: auto; }
        .cta-bottom {
            display: inline-block; background: var(--green); color: #0a0a0a;
            padding: 16px 48px; font-size: 1.15rem; font-weight: 700;
            text-decoration: none; border-radius: 6px; transition: all 0.2s;
            font-family: 'Space Mono', monospace;
        }
        .cta-bottom:hover { background: #00cc6a; transform: translateY(-1px); }

        /* Footer */
        footer {
            text-align: center; padding: 2rem; color: #333;
            font-size: 0.8rem; border-top: 1px solid #1a1a1a;
        }
        footer a { color: var(--accent); text-decoration: none; }

        /* Responsive */
        @media (max-width: 700px) {
            .hero { grid-template-columns: 1fr; text-align: center; padding: 2rem 1.5rem; min-height: auto; }
            .hero-content-box { order: 2; }
            .hero-building { order: 1; }
            .hero-building svg { max-height: 40vh; }
            .logo { font-size: 2.5rem; }
            .tagline-main { font-size: 1.3rem; }
            .problema-grid, .features, .pricing-grid { grid-template-columns: 1fr; }
            section { padding: 3rem 1.5rem; }
        }
    </style>
</head>
<body>

<!-- Hero -->
<div class="hero">
    <div class="flag-bar"></div>
    <div class="hero-content-box">
        <div class="logo">mck<span>ou</span>tie</div>
        <p class="tagline-main">Consultoría de crecimiento para startups argentinas</p>
        <p class="tagline-sub">
            Análisis de tracción con IA. 19 canales de crecimiento rankeados para TU startup.
            Plan de 90 días. Sin chamuyo, sin PowerPoints de 200 slides. $39/mes.
        </p>
        <a class="cta-hero" href="https://x.com/intent/tweet?text=@mckoutie%20analyse%20my%20startup%20" target="_blank">
            Analizá tu startup ahora
        </a>
    </div>
    </div>
    <div class="hero-building">
        <svg viewBox="0 0 400 600" xmlns="http://www.w3.org/2000/svg" width="400" height="600">
            <!-- Sky background -->
            <defs>
                <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#0a1628"/>
                    <stop offset="100%" stop-color="#0a0a0a"/>
                </linearGradient>
                <linearGradient id="bldg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#1a2a4a"/>
                    <stop offset="100%" stop-color="#0f1a2f"/>
                </linearGradient>
                <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stop-color="#F5C518"/>
                    <stop offset="100%" stop-color="#e0a800"/>
                </linearGradient>
                <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="blur"/>
                    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
            </defs>
            <rect width="400" height="600" fill="url(#sky)"/>

            <!-- Stars -->
            <circle cx="30" cy="40" r="1.5" fill="#fff" opacity="0.6"/>
            <circle cx="90" cy="25" r="1" fill="#fff" opacity="0.4"/>
            <circle cx="350" cy="50" r="1.5" fill="#fff" opacity="0.5"/>
            <circle cx="370" cy="100" r="1" fill="#fff" opacity="0.3"/>
            <circle cx="50" cy="120" r="1" fill="#fff" opacity="0.4"/>
            <circle cx="310" cy="30" r="1.2" fill="#fff" opacity="0.5"/>

            <!-- Obelisco silhouette in background -->
            <rect x="60" y="250" width="8" height="200" fill="#1a2a4a" opacity="0.4"/>
            <polygon points="60,250 68,250 64,230" fill="#1a2a4a" opacity="0.4"/>

            <!-- Main building -->
            <rect x="120" y="80" width="160" height="480" rx="4" fill="url(#bldg)" stroke="#75AADB" stroke-width="1.5" opacity="0.95"/>

            <!-- Roof antenna -->
            <rect x="196" y="40" width="8" height="45" fill="#75AADB"/>
            <circle cx="200" cy="35" r="6" fill="#F5C518" filter="url(#glow)">
                <animate attributeName="opacity" values="1;0.4;1" dur="2s" repeatCount="indefinite"/>
            </circle>

            <!-- MCKOUTIE sign on top -->
            <rect x="135" y="82" width="130" height="28" rx="3" fill="#0a0a0a" stroke="#F5C518" stroke-width="1"/>
            <text x="200" y="101" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="14" font-weight="bold">MCKOUTIE</text>

            <!-- Argentine flag bar under sign -->
            <rect x="135" y="112" width="43" height="4" fill="#75AADB"/>
            <rect x="178" y="112" width="44" height="4" fill="#ffffff"/>
            <rect x="222" y="112" width="43" height="4" fill="#75AADB"/>

            <!-- Floor 6 — Mate & Strategy -->
            <rect x="135" y="125" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <rect x="210" y="125" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <!-- Capybara with mate -->
            <circle cx="162" cy="148" r="12" fill="#8B6914"/>
            <circle cx="157" cy="145" r="3" fill="#111"/>
            <circle cx="167" cy="145" r="3" fill="#111"/>
            <circle cx="157" cy="145" r="1.2" fill="#fff"/>
            <circle cx="167" cy="145" r="1.2" fill="#fff"/>
            <rect x="153" y="157" width="5" height="8" rx="2" fill="#2d5016"/>
            <line x1="155" y1="157" x2="155" y2="150" stroke="#999" stroke-width="1"/>
            <text x="162" y="178" text-anchor="middle" fill="#75AADB" font-family="monospace" font-size="6">ESTRATEGIA</text>
            <!-- Capybara with chart -->
            <circle cx="237" cy="148" r="12" fill="#8B6914"/>
            <circle cx="232" cy="145" r="3" fill="#111"/>
            <circle cx="242" cy="145" r="3" fill="#111"/>
            <polyline points="222,170 230,165 238,168 246,158 254,162" fill="none" stroke="#00ff88" stroke-width="1.5"/>
            <text x="237" y="178" text-anchor="middle" fill="#00ff88" font-family="monospace" font-size="6">TRACCION</text>

            <!-- Floor 5 — Asado meeting -->
            <rect x="135" y="195" width="55" height="60" rx="3" fill="#1a1008" stroke="#F5C518" stroke-width="0.8"/>
            <rect x="210" y="195" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <!-- Grill/asado -->
            <rect x="145" y="220" width="35" height="5" rx="1" fill="#444"/>
            <line x1="150" y1="220" x2="150" y2="215" stroke="#ff6b35" stroke-width="2" opacity="0.8">
                <animate attributeName="y2" values="215;212;215" dur="0.5s" repeatCount="indefinite"/>
            </line>
            <line x1="160" y1="220" x2="160" y2="213" stroke="#ff6b35" stroke-width="2" opacity="0.6">
                <animate attributeName="y2" values="213;210;213" dur="0.7s" repeatCount="indefinite"/>
            </line>
            <line x1="170" y1="220" x2="170" y2="214" stroke="#ff6b35" stroke-width="2" opacity="0.7">
                <animate attributeName="y2" values="214;211;214" dur="0.6s" repeatCount="indefinite"/>
            </line>
            <text x="162" y="247" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="6">ASADO</text>
            <!-- Capybara coding -->
            <circle cx="237" cy="218" r="12" fill="#8B6914"/>
            <circle cx="232" cy="215" r="3" fill="#111"/>
            <circle cx="242" cy="215" r="3" fill="#111"/>
            <rect x="225" y="232" width="24" height="14" rx="2" fill="#0a0a0a" stroke="#75AADB" stroke-width="0.5"/>
            <text x="237" y="241" text-anchor="middle" fill="#00ff88" font-family="monospace" font-size="5">&gt;_</text>
            <text x="237" y="247" text-anchor="middle" fill="#75AADB" font-family="monospace" font-size="6">CODIGO</text>

            <!-- Floor 4 — Tango & Growth -->
            <rect x="135" y="265" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <rect x="210" y="265" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <!-- Two capybaras dancing tango -->
            <circle cx="152" cy="288" r="10" fill="#8B6914"/>
            <circle cx="172" cy="288" r="10" fill="#a07818"/>
            <line x1="155" y1="298" x2="169" y2="298" stroke="#F5C518" stroke-width="1.5"/>
            <text x="162" y="318" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="6">TANGO</text>
            <!-- Growth rocket -->
            <polygon points="237,275 243,295 231,295" fill="#75AADB"/>
            <rect x="233" y="295" width="8" height="5" fill="#ff6b35"/>
            <line x1="237" y1="300" x2="237" y2="310" stroke="#F5C518" stroke-width="2" opacity="0.6">
                <animate attributeName="opacity" values="0.6;0.2;0.6" dur="0.4s" repeatCount="indefinite"/>
            </line>
            <text x="237" y="318" text-anchor="middle" fill="#ff6b35" font-family="monospace" font-size="6">GROWTH</text>

            <!-- Floor 3 — Dulce de leche & Analysis -->
            <rect x="135" y="335" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <rect x="210" y="335" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <!-- Alfajor -->
            <ellipse cx="162" cy="358" rx="16" ry="7" fill="#8B4513"/>
            <ellipse cx="162" cy="355" rx="16" ry="7" fill="#D2691E"/>
            <ellipse cx="162" cy="356" rx="12" ry="3" fill="#F5C518"/>
            <text x="162" y="385" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="6">ALFAJORES</text>
            <!-- 19 channels icon -->
            <text x="237" y="360" text-anchor="middle" fill="#75AADB" font-family="monospace" font-size="22" font-weight="bold">19</text>
            <text x="237" y="375" text-anchor="middle" fill="#75AADB" font-family="monospace" font-size="6">CANALES</text>
            <text x="237" y="385" text-anchor="middle" fill="#muted" font-family="monospace" font-size="5" fill="#666">de traccion</text>

            <!-- Floor 2 — Peso & Dollar -->
            <rect x="135" y="405" width="55" height="60" rx="3" fill="#111a2f" stroke="#75AADB" stroke-width="0.8"/>
            <rect x="210" y="405" width="55" height="60" rx="3" fill="#1a1008" stroke="#F5C518" stroke-width="0.8"/>
            <!-- Peso sign -->
            <text x="162" y="440" text-anchor="middle" fill="#75AADB" font-family="monospace" font-size="28" font-weight="bold">$</text>
            <text x="162" y="456" text-anchor="middle" fill="#666" font-family="monospace" font-size="6">ARS → USD</text>
            <!-- Dollar bills flying -->
            <text x="225" y="430" fill="#00ff88" font-family="monospace" font-size="10" transform="rotate(-15,225,430)">$39</text>
            <text x="245" y="445" fill="#00ff88" font-family="monospace" font-size="8" transform="rotate(10,245,445)">/mo</text>
            <text x="237" y="456" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="6">SIN CHAMUYO</text>

            <!-- Floor 1 — Entrance with doorman capybara -->
            <rect x="135" y="475" width="130" height="65" rx="3" fill="#0f1a2f" stroke="#75AADB" stroke-width="1"/>
            <!-- Door -->
            <rect x="180" y="495" width="40" height="45" rx="2" fill="#0a0a0a" stroke="#F5C518" stroke-width="1"/>
            <circle cx="214" cy="518" r="2" fill="#F5C518"/>
            <!-- Doorman capybara with suit -->
            <circle cx="155" cy="505" r="12" fill="#8B6914"/>
            <circle cx="150" cy="502" r="3" fill="#111"/>
            <circle cx="160" cy="502" r="3" fill="#111"/>
            <circle cx="150" cy="502" r="1.2" fill="#fff"/>
            <circle cx="160" cy="502" r="1.2" fill="#fff"/>
            <rect x="148" y="517" width="14" height="18" rx="2" fill="#1a1a3a"/>
            <rect x="152" y="517" width="6" height="3" fill="#fff"/>
            <!-- Welcome sign -->
            <text x="200" y="490" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="7">BIENVENIDOS</text>

            <!-- Ground / sidewalk -->
            <rect x="100" y="540" width="200" height="6" fill="#222"/>

            <!-- Floating elements -->
            <!-- Mate flying -->
            <g transform="translate(320,150)" opacity="0.7">
                <rect x="0" y="5" width="12" height="15" rx="3" fill="#2d5016"/>
                <line x1="6" y1="5" x2="6" y2="-5" stroke="#999" stroke-width="1.5"/>
                <animateTransform attributeName="transform" type="translate" values="320,150;325,145;320,150" dur="3s" repeatCount="indefinite"/>
            </g>
            <!-- Dollar sign floating -->
            <text x="90" y="180" fill="#F5C518" font-family="monospace" font-size="18" opacity="0.4">$</text>
            <text x="330" y="300" fill="#F5C518" font-family="monospace" font-size="14" opacity="0.3">$</text>
            <!-- Rocket -->
            <g transform="translate(85,350)" opacity="0.5">
                <polygon points="8,0 14,18 2,18" fill="#75AADB"/>
                <rect x="4" y="18" width="8" height="4" fill="#ff6b35"/>
                <animateTransform attributeName="transform" type="translate" values="85,350;82,340;85,350" dur="4s" repeatCount="indefinite"/>
            </g>
            <!-- Cloud -->
            <g opacity="0.15">
                <ellipse cx="330" cy="200" rx="25" ry="10" fill="#fff"/>
                <ellipse cx="345" cy="195" rx="15" ry="8" fill="#fff"/>
            </g>

            <!-- "SEDE ARGENTINA" label at bottom -->
            <rect x="130" y="555" width="140" height="22" rx="4" fill="#0a0a0a" stroke="#F5C518" stroke-width="1"/>
            <text x="200" y="570" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="9" font-weight="bold">SEDE ARGENTINA</text>
        </svg>
    </div>
    <div class="scroll-hint">↓ scrolleá para más</div>
</div>

<!-- El problema -->
<section>
    <h2 class="section-title">El <span>problema</span> que todos conocemos</h2>
    <p class="section-sub">Emprender en Argentina es un deporte extremo. Y la consultoría tradicional no está diseñada para vos.</p>

    <div class="problema-grid">
        <div class="problema-card">
            <div class="emoji">💸</div>
            <h3>McKinsey cobra USD 100K+</h3>
            <p>Y ni siquiera entienden tu mercado. ¿Vas a pagar eso con pesos? Dale.</p>
        </div>
        <div class="problema-card">
            <div class="emoji">🤷</div>
            <h3>"Hacé content marketing"</h3>
            <p>El consejo genérico que te dan todos. Pero ¿qué canal específico mueve la aguja para TU startup?</p>
        </div>
        <div class="problema-card">
            <div class="emoji">⏰</div>
            <h3>Tiempo = tu recurso más escaso</h3>
            <p>Estás haciendo de CEO, CTO, y community manager. No tenés 3 meses para un "estudio de mercado".</p>
        </div>
        <div class="problema-card">
            <div class="emoji">🌎</div>
            <h3>Pensás en global desde el día 1</h3>
            <p>Tu startup no es solo para Argentina. Necesitás una estrategia que escale a LATAM y más allá.</p>
        </div>
    </div>
</section>

<!-- Contexto argentino -->
<section>
    <h2 class="section-title">Hecho para el <span>ecosistema argentino</span></h2>
    <p class="section-sub">No es un tool gringo traducido. Entiende el contexto real.</p>

    <div class="context-box">
        <p><strong>El talento argentino es de primer nivel mundial</strong> — lo que falta no es capacidad, es estrategia de distribución.</p>
        <p>Mercado Libre, Auth0, Ualá, Mural, Pomelo — todas nacieron acá. La diferencia entre las que escalan y las que mueren no es el producto. Es la tracción.</p>
    </div>

    <div class="context-box">
        <p><strong>Mckoutie analiza tu startup con el framework Bullseye</strong> — el mismo que usaron las startups más exitosas del mundo para encontrar su canal de crecimiento principal.</p>
        <p>19 canales. Cada uno evaluado del 1 al 10 para tu caso específico. No genérico — para VOS.</p>
    </div>

    <div class="context-box">
        <p><strong>¿Tu mercado es Argentina? ¿LATAM? ¿Global?</strong> — El análisis se adapta. Si tu play es WhatsApp commerce en LATAM, te lo dice. Si es Product Hunt + SEO para el mercado US, también.</p>
    </div>
</section>

<!-- Cómo funciona -->
<section>
    <h2 class="section-title">Cómo <span>funciona</span></h2>
    <p class="section-sub">Tres pasos. Dos minutos. Cero burocracia.</p>

    <div class="steps">
        <div class="step">
            <div class="step-num">1</div>
            <div class="step-content">
                <h3>Twitteá a @mckoutie</h3>
                <p>Mandá un tweet: <code>@mckoutie analyse my startup https://tustartup.com</code></p>
                <p>También podés tagear una empresa: <code>@mckoutie analyse my startup @tuhandle</code></p>
            </div>
        </div>
        <div class="step">
            <div class="step-num">2</div>
            <div class="step-content">
                <h3>Recibí un teaser gratis</h3>
                <p>En minutos, mckoutie responde con un hilo con tus 3 canales top y un hot take. Gratis. Sin tarjeta.</p>
            </div>
        </div>
        <div class="step">
            <div class="step-num">3</div>
            <div class="step-content">
                <h3>Desbloqueá el análisis completo</h3>
                <p>Suscribite por $39/mes y accedé al dashboard interactivo con los 19 canales, plan de 90 días, leads, inversores, y actualizaciones mensuales.</p>
            </div>
        </div>
    </div>
</section>

<!-- Qué incluye -->
<section>
    <h2 class="section-title">Qué <span>incluye</span></h2>
    <p class="section-sub">Todo lo que necesitás para dejar de adivinar y empezar a crecer.</p>

    <div class="features">
        <div class="feature">
            <h3><span class="check">✓</span> 19 canales analizados</h3>
            <p>Desde SEO y content hasta partnerships y engineering as marketing. Cada uno con score y tácticas específicas.</p>
        </div>
        <div class="feature">
            <h3><span class="check">✓</span> Framework Bullseye</h3>
            <p>Tus canales rankeados en inner ring, middle ring, y outer ring. Sabé exactamente dónde apostar.</p>
        </div>
        <div class="feature">
            <h3><span class="check">✓</span> Plan de 90 días</h3>
            <p>Semana por semana. Qué hacer, cómo medirlo, y qué esperar. Nada de "defina su estrategia".</p>
        </div>
        <div class="feature">
            <h3><span class="check">✓</span> Budget allocation</h3>
            <p>Cuánto poner en cada canal con el presupuesto que tengas, ya sean $500 o $50,000.</p>
        </div>
        <div class="feature">
            <h3><span class="check">✓</span> Risk matrix</h3>
            <p>Los riesgos reales de tu modelo y cómo mitigarlos. Sin endulzar nada.</p>
        </div>
        <div class="feature">
            <h3><span class="check">✓</span> Hot take</h3>
            <p>Lo que nadie te va a decir. La verdad incómoda sobre tu startup. A veces duele, siempre sirve.</p>
        </div>
        <div class="feature">
            <h3><span class="check">✓</span> Leads + personas</h3>
            <p>3 personas de tu cliente ideal + 10 leads reales para empezar a vender hoy. (Plan Growth)</p>
        </div>
        <div class="feature">
            <h3><span class="check">✓</span> Investor intel</h3>
            <p>Quién invirtió en tu competencia, qué fondos miran tu vertical, y cómo acercarte. (Plan Growth)</p>
        </div>
    </div>
</section>

<!-- Precios -->
<section>
    <h2 class="section-title">Precios <span>reales</span></h2>
    <p class="section-sub">Sin letra chica. Sin contratos. Cancelá cuando quieras.</p>

    <div class="pricing-grid">
        <div class="price-card">
            <h3>Teaser</h3>
            <div class="price-amount">Gratis</div>
            <ul>
                <li>Top 3 canales de crecimiento</li>
                <li>Hot take sobre tu startup</li>
                <li>Hilo público en Twitter</li>
                <li>Sin tarjeta, sin registro</li>
            </ul>
        </div>
        <div class="price-card featured">
            <div class="badge">MÁS POPULAR</div>
            <h3>Starter</h3>
            <div class="price-amount">$39<span>/mes</span></div>
            <ul>
                <li>19 canales con score y tácticas</li>
                <li>Bullseye framework completo</li>
                <li>Plan de 90 días semanal</li>
                <li>Budget allocation</li>
                <li>Risk matrix + moat analysis</li>
                <li>Hot take sin filtro</li>
                <li>Updates mensuales del mercado</li>
            </ul>
        </div>
        <div class="price-card">
            <h3>Growth</h3>
            <div class="price-amount">$200<span>/mes</span></div>
            <ul>
                <li>Todo lo de Starter</li>
                <li>3 customer personas detalladas</li>
                <li>10 leads reales con contacto</li>
                <li>Investor intelligence</li>
                <li>Competitor funding data</li>
                <li>Monthly market deep dives</li>
            </ul>
        </div>
    </div>

    <div class="context-box" style="margin-top: 2rem;">
        <p><strong>¿$39 USD en Argentina?</strong> — Sí, es plata. Pero un consultor decente cobra eso por hora. Acá tenés un análisis completo que se actualiza solo, todos los meses. Un McKinsey trucho cobra $100K+ por algo peor.</p>
    </div>
</section>

<!-- Credibility -->
<div class="credibility">
    <p class="highlight">Construido por un argentino, para argentinos que piensan en grande.</p>
    <p>Basado en el framework "Traction" de Gabriel Weinberg (fundador de DuckDuckGo). Potenciado por IA. Diseñado para startups que no tienen tiempo ni presupuesto para chamuyos corporativos.</p>
    <p style="margin-top: 1rem; font-size: 0.85rem;">El mismo framework que usaron Dropbox, Hubspot, y cientos de startups YC para encontrar su canal de crecimiento.</p>
</div>

<!-- CTA final -->
<div class="cta-section">
    <h2>¿Listo para dejar de improvisar?</h2>
    <p>En 2 minutos tenés un análisis de tracción profesional. El teaser es gratis. Si no te sirve, no pagás nada.</p>
    <a class="cta-bottom" href="https://x.com/intent/tweet?text=@mckoutie%20analyse%20my%20startup%20" target="_blank">
        Analizá tu startup →
    </a>
    <p style="color: var(--muted); font-size: 0.85rem; margin-top: 1rem;">
        Twitteá a <a href="https://x.com/mckoutie" target="_blank" style="color: var(--accent); text-decoration: none;">@mckoutie</a> y arrancá.
    </p>
</div>

<!-- Footer -->
<footer>
    <p>mckoutie — McKinsey at home</p>
    <p style="margin-top: 0.5rem;">
        <a href="/">English</a> · <a href="/AR">Argentina</a> · <a href="https://x.com/mckoutie" target="_blank">Twitter</a>
    </p>
    <p style="margin-top: 1rem;">No afiliado con McKinsey (obviamente). Hecho con asado y mate.</p>
</footer>

</body>
</html>"""


@app.get("/auth/twitter")
async def auth_twitter(request: Request, redirect: str = "/"):
    """Initiate Twitter OAuth 2.0 login."""
    auth_url, state = auth.get_twitter_auth_url(redirect_after=redirect)
    return RedirectResponse(auth_url)


@app.get("/auth/twitter/callback")
async def auth_twitter_callback(request: Request, code: str = "", state: str = ""):
    """Handle Twitter OAuth callback."""
    if not code or not state:
        return HTMLResponse("<h1>Login failed</h1><p>Missing code or state.</p>", status_code=400)

    user_info = await auth.exchange_code(code, state)
    if not user_info:
        return HTMLResponse("<h1>Login failed</h1><p>Could not verify your Twitter account.</p>", status_code=400)

    # Create session JWT
    token = auth.create_jwt({
        "twitter_id": user_info["twitter_id"],
        "username": user_info["username"],
        "name": user_info["name"],
    })

    redirect_to = user_info.get("redirect_after", "/")
    response = RedirectResponse(redirect_to)
    response.set_cookie(
        "mckoutie_session",
        token,
        max_age=30 * 24 * 3600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@app.get("/auth/logout")
async def auth_logout(request: Request, redirect: str = "/"):
    """Clear session cookie."""
    response = RedirectResponse(redirect)
    response.delete_cookie("mckoutie_session")
    return response


def _mock_analysis() -> dict:
    """Comprehensive mock data for testing dashboard layout."""
    return {
        "company_profile": {
            "name": "Linear",
            "one_liner": "AI-powered project management platform purpose-built for modern product development teams",
            "stage": "scaling",
            "estimated_size": "medium (6-20)",
            "market": "Product development teams at tech companies",
            "business_model": "SaaS subscription, $8-50+ per user/month",
            "strengths": [
                "Product-market fit with 20,000+ teams",
                "First-mover advantage in AI-native project management",
                "Best-in-class design and developer experience",
                "Strong word-of-mouth in engineering communities",
                "Clear differentiation with AI agent workflows"
            ],
            "weaknesses": [
                "Competing against Jira, Asana, Monday.com",
                "Heavy dependence on technical teams",
                "AI features still feel early/experimental",
                "Pricing pressure from free alternatives"
            ],
            "unique_angle": "The only PM tool designed from the ground up for human-AI collaboration"
        },
        "executive_summary": "Linear has achieved genuine product-market fit with 20,000+ teams. But they're at a critical inflection point. Their AI-native approach is their superpower, but also their biggest risk if they can't articulate the value to mainstream buyers. The strategy should focus on: 1) Solidifying their position with engineering teams, 2) Expanding into product and design roles, and 3) Building enterprise sales motion for teams ready to go all-in on AI workflows.",
        "channel_analysis": [
            {"channel": "Developer Communities", "score": 10, "effort": "medium", "timeline": "weeks", "budget": "$2K-5K",
             "specific_ideas": ["Launch Linear API hackathon with AI agent integration prizes", "Partner with Y Combinator for portfolio onboarding", "Build open-source Linear CLI examples"],
             "first_move": "Launch a Linear API hackathon with $50K in prizes for best AI agent integrations",
             "why_or_why_not": "This is Linear's bread and butter — developers already love them",
             "killer_insight": "Focus on engineering managers, not individual devs — they mandate tool adoption"},
            {"channel": "Content Marketing", "score": 9, "effort": "high", "timeline": "months", "budget": "$10K-15K",
             "specific_ideas": ["Weekly 'AI Development' newsletter", "Case studies showing 40%+ velocity improvements", "'State of Product Development' annual report"],
             "first_move": "Launch weekly email series profiling how top companies use AI in development",
             "why_or_why_not": "Linear's audience is hungry for tactical AI workflow content",
             "killer_insight": "Don't just talk about Linear — become the thought leader on AI-human collaboration"},
            {"channel": "Community Building", "score": 9, "effort": "high", "timeline": "months", "budget": "$8K-20K",
             "specific_ideas": ["Create 'Linear AI Pioneers' community", "Monthly virtual events on AI development", "Certification program for Linear AI workflows"],
             "first_move": "Launch 'Linear AI Collective' Slack community",
             "why_or_why_not": "Perfect fit for developer-centric audience, creates retention",
             "killer_insight": "Build the definitive community for AI-powered product development"},
            {"channel": "Partnerships & Integrations", "score": 9, "effort": "high", "timeline": "months", "budget": "$5K-20K",
             "specific_ideas": ["Deep Figma integration", "Native Slack workflows", "GitHub Apps marketplace"],
             "first_move": "Build comprehensive Figma plugin for design-dev handoff",
             "why_or_why_not": "Integrations expand Linear beyond engineering",
             "killer_insight": "Focus on integrations that bring non-technical roles into Linear"},
            {"channel": "Direct Sales", "score": 8, "effort": "high", "timeline": "months", "budget": "$25K-50K",
             "specific_ideas": ["Hire enterprise AEs focused on Series B+ companies", "Create 'AI Readiness Assessment'", "Pilot program for AI development practices"],
             "first_move": "Hire one enterprise AE and create 'AI Development Maturity' assessment",
             "why_or_why_not": "Necessary for $50K+ deals",
             "killer_insight": "Sell AI transformation, not just another PM tool"},
            {"channel": "Product Hunt & Tech Publications", "score": 8, "effort": "medium", "timeline": "weeks", "budget": "$3K-8K",
             "specific_ideas": ["Launch AI features on Product Hunt", "Pitch TechCrunch", "Submit to developer tool awards"],
             "first_move": "Coordinate Product Hunt launch for next major AI feature",
             "why_or_why_not": "Tech press loves AI stories and Linear has genuine innovation",
             "killer_insight": "Time announcements with broader AI news cycles"},
            {"channel": "Conferences & Events", "score": 8, "effort": "high", "timeline": "months", "budget": "$15K-30K",
             "specific_ideas": ["Sponsor DevOps conferences", "Host 'AI in Product' meetups", "Booth at GitHub Universe"],
             "first_move": "Sponsor and speak at next major DevOps conference",
             "why_or_why_not": "High-impact for enterprise prospects",
             "killer_insight": "Create hands-on AI workflow experiences, don't just sponsor"},
            {"channel": "Sales Prospecting", "score": 8, "effort": "high", "timeline": "weeks", "budget": "$15K-30K",
             "specific_ideas": ["Cold outreach to CTOs at fast-growing companies", "LinkedIn prospecting", "Account-based marketing for top 100 targets"],
             "first_move": "Create targeted LinkedIn campaign reaching CTOs at Series B+ companies",
             "why_or_why_not": "Essential for enterprise growth",
             "killer_insight": "Lead with AI transformation consulting, not tool sales"},
            {"channel": "Search Engine Marketing", "score": 7, "effort": "medium", "timeline": "weeks", "budget": "$8K-15K",
             "specific_ideas": ["Target 'Jira alternatives for AI teams'", "Retargeting campaigns"],
             "first_move": "Launch Google Ads targeting 'Jira alternative' with AI landing page",
             "why_or_why_not": "Expensive but necessary for high-intent searches",
             "killer_insight": "Don't compete on generic PM keywords — own 'AI-powered project management'"},
            {"channel": "Email Marketing", "score": 7, "effort": "medium", "timeline": "weeks", "budget": "$3K-8K",
             "specific_ideas": ["Onboarding sequence for AI features", "Segmented campaigns by role"],
             "first_move": "Rebuild onboarding to feature AI agent setup in week 1",
             "why_or_why_not": "Essential for activation and retention",
             "killer_insight": "Most customers aren't using Linear's full AI capabilities"},
            {"channel": "Traditional PR", "score": 7, "effort": "medium", "timeline": "months", "budget": "$8K-20K",
             "specific_ideas": ["Pitch AI transforming software development", "Position founders as thought leaders"],
             "first_move": "Hire tech-focused PR agency, pitch '25,000 teams using AI' story",
             "why_or_why_not": "Important for credibility and enterprise sales",
             "killer_insight": "Pitch the broader AI development story with Linear as the example"},
            {"channel": "Business Development", "score": 7, "effort": "high", "timeline": "months", "budget": "$10K-25K",
             "specific_ideas": ["Partner with Cursor/GitHub Copilot", "Joint go-to-market with Figma"],
             "first_move": "Negotiate partnership with Cursor for bundled AI workflow",
             "why_or_why_not": "High potential but requires relationship building",
             "killer_insight": "Focus on partnerships that expand into non-technical roles"},
            {"channel": "Webinars & Online Events", "score": 7, "effort": "medium", "timeline": "weeks", "budget": "$3K-8K",
             "specific_ideas": ["Monthly 'AI Development Workshop'", "Executive briefings", "Joint webinars with Figma/GitHub"],
             "first_move": "Launch monthly 'AI Development Masterclass' webinar series",
             "why_or_why_not": "Good for lead generation and explaining AI value",
             "killer_insight": "Focus on education rather than pitching"},
            {"channel": "Social Media Marketing", "score": 6, "effort": "medium", "timeline": "weeks", "budget": "$2K-5K",
             "specific_ideas": ["Twitter threads showing AI agents in action", "LinkedIn content for CTOs"],
             "first_move": "Start weekly Twitter threads showcasing customer AI workflows",
             "why_or_why_not": "Good for brand building, won't drive immediate enterprise sales",
             "killer_insight": "Twitter for developers, LinkedIn for executives — don't spread thin"},
            {"channel": "Influencer Marketing", "score": 6, "effort": "medium", "timeline": "weeks", "budget": "$5K-15K",
             "specific_ideas": ["Partner with developer YouTubers", "Sponsor dev newsletters"],
             "first_move": "Reach out to top 10 developer YouTube channels",
             "why_or_why_not": "Effective for awareness, hard to measure direct impact",
             "killer_insight": "Focus on productivity/AI influencers, not generic tech reviewers"},
            {"channel": "Unconventional Marketing", "score": 6, "effort": "medium", "timeline": "weeks", "budget": "$3K-10K",
             "specific_ideas": ["'Productivity Olympics' comparing human vs AI+human teams", "Public real-time AI metrics dashboard"],
             "first_move": "Launch public leaderboard of AI collaboration metrics",
             "why_or_why_not": "Could create buzz if executed well",
             "killer_insight": "Make AI capabilities tangible and visible"},
            {"channel": "Viral Marketing", "score": 5, "effort": "low", "timeline": "weeks", "budget": "$1K-3K",
             "specific_ideas": ["Shareable demos of AI agents fixing bugs", "AI Development Challenge with leaderboards"],
             "first_move": "Create shareable widget showing team's AI development stats",
             "why_or_why_not": "Linear isn't naturally viral, but AI demos could be",
             "killer_insight": "Make AI workflows so impressive developers want to show them off"},
            {"channel": "Trade Shows", "score": 5, "effort": "high", "timeline": "months", "budget": "$20K-40K",
             "specific_ideas": ["Exhibit at GitHub Universe, AWS re:Invent", "Interactive AI demos for booth visitors"],
             "first_move": "Book booth space at next GitHub Universe",
             "why_or_why_not": "Expensive but good for enterprise relationships",
             "killer_insight": "Focus on developer-heavy conferences, not general business shows"},
            {"channel": "Affiliate Marketing", "score": 4, "effort": "medium", "timeline": "months", "budget": "$2K-5K",
             "specific_ideas": ["Partner with dev consultants", "Productivity review sites"],
             "first_move": "Pilot affiliate program with 5 development consultants",
             "why_or_why_not": "Not natural for B2B — most evaluate tools themselves",
             "killer_insight": "Focus on consultants/agencies, not traditional affiliates"}
        ],
        "bullseye_ranking": {
            "inner_ring": {
                "channels": ["Developer Communities", "Content Marketing", "Community Building"],
                "reasoning": "These three channels align perfectly with Linear's strengths. Developer communities provide direct access to their core market. Content marketing lets them own the AI-development narrative. Community building creates long-term retention."
            },
            "promising": {
                "channels": ["Partnerships & Integrations", "Direct Sales", "Sales Prospecting", "Conferences & Events", "Product Hunt & Tech Publications", "Traditional PR"],
                "reasoning": "Essential for scaling beyond the initial developer audience. Partnerships expand reach, sales channels enable enterprise growth."
            },
            "long_shot": {
                "channels": ["Search Engine Marketing", "Email Marketing", "Webinars & Online Events", "Social Media Marketing", "Business Development", "Influencer Marketing", "Viral Marketing", "Unconventional Marketing", "Trade Shows", "Affiliate Marketing"],
                "reasoning": "Either too expensive for uncertain returns or better as supporting channels."
            }
        },
        "ninety_day_plan": {
            "month_1": {
                "focus": "Developer community dominance and content foundation",
                "actions": ["Launch Linear API hackathon with AI agent prizes", "Start weekly 'AI Development' newsletter", "Create Linear AI Collective Slack community", "Record 5 customer case study videos", "Build Figma plugin for design-dev handoff"],
                "target_metric": "1,000 new developer signups from community channels",
                "budget": "$15K"
            },
            "month_2": {
                "focus": "Content amplification and enterprise preparation",
                "actions": ["Publish 'State of AI in Product Development' report", "Launch LinkedIn campaign targeting CTOs", "Host first 'AI Development Masterclass' webinar", "Hire enterprise Account Executive", "Build ROI calculator for enterprise prospects"],
                "target_metric": "500 qualified enterprise leads generated",
                "budget": "$25K"
            },
            "month_3": {
                "focus": "Enterprise sales activation and scale",
                "actions": ["Launch enterprise outbound to top 100 targets", "Create AI Development Maturity Assessment tool", "Host virtual Linear user conference", "Implement full PR strategy", "Create Linear certification program"],
                "target_metric": "$50K in new enterprise ARR closed",
                "budget": "$35K"
            }
        },
        "budget_allocation": {
            "total_recommended": "$75K over 90 days",
            "breakdown": [
                {"channel": "Developer Communities", "amount": "$15K", "rationale": "Hackathons, conference sponsorships, community building — highest ROI"},
                {"channel": "Content Marketing", "amount": "$12K", "rationale": "Newsletter, video production, research report — long-term authority"},
                {"channel": "Community Building", "amount": "$8K", "rationale": "Slack community, events, user-generated content programs"},
                {"channel": "Direct Sales", "amount": "$25K", "rationale": "Enterprise AE salary/commission, sales tools, marketing materials"},
                {"channel": "Conferences & Events", "amount": "$10K", "rationale": "Sponsorships and speaking at developer events"},
                {"channel": "Traditional PR", "amount": "$5K", "rationale": "PR agency retainer for thought leadership and announcements"}
            ]
        },
        "risk_matrix": [
            {"risk": "AI hype bubble bursts before enterprise foothold", "probability": "medium", "impact": "high", "mitigation": "Focus on concrete productivity metrics, not AI buzzwords"},
            {"risk": "Microsoft/Atlassian launches competitive AI features", "probability": "high", "impact": "high", "mitigation": "Lock in customers with deep AI workflows; focus on developer experience moat"},
            {"risk": "Enterprise sales dilutes developer-friendly brand", "probability": "medium", "impact": "medium", "mitigation": "Keep enterprise messaging separate; maintain bottom-up adoption"},
            {"risk": "AI features remain novelty for most customers", "probability": "medium", "impact": "high", "mitigation": "Invest in onboarding and customer success for AI adoption"}
        ],
        "competitive_moat": "Linear's moat isn't just being first to AI — it's building the deepest human-AI collaboration workflows that become impossible to replace. Every AI agent integration creates switching costs. The real defensibility comes from community and ecosystem. The long-term play is owning the interface layer between human product teams and AI agents.",
        "hot_take": "Linear's biggest risk isn't competition — it's falling in love with their own AI narrative while customers just want better project management. Most teams aren't ready for full AI collaboration yet, but they will pay premium for a tool that makes their current process 30% faster. Lead with speed and developer experience, with AI as the engine, not the headline.",
        "leads_research": {
            "personas": [
                {
                    "name": "The Engineering Manager",
                    "description": "Mid-level engineering manager at a Series B+ startup (50-200 engineers). Frustrated with Jira's complexity, looking for a tool that gets out of the way. Makes tool decisions for their team of 8-15 engineers.",
                    "platforms": ["Twitter", "LinkedIn", "Discord", "GitHub"],
                    "pain_signals": [
                        "Jira is killing our velocity",
                        "We spend more time managing tickets than writing code",
                        "Looking for a project management tool that developers actually want to use"
                    ]
                },
                {
                    "name": "The Technical Founder",
                    "description": "CTO or technical co-founder at an early-stage startup (5-30 people). Wants to set up the right tools from day one. Cares deeply about developer experience and modern tooling.",
                    "platforms": ["Twitter", "Reddit", "LinkedIn", "Substack"],
                    "pain_signals": [
                        "What PM tool should a seed-stage startup use?",
                        "Setting up our engineering stack from scratch",
                        "Need something lightweight but powerful for a small team"
                    ]
                },
                {
                    "name": "The VP of Engineering",
                    "description": "Senior engineering leader at a growth-stage company (200+ employees). Evaluating AI tools to improve team productivity. Has budget authority and cares about measurable velocity improvements.",
                    "platforms": ["LinkedIn", "Twitter", "Substack"],
                    "pain_signals": [
                        "How are engineering teams actually using AI in their workflow?",
                        "Looking to modernize our development process",
                        "Need to show the board measurable productivity gains from AI"
                    ]
                }
            ],
            "leads": [
                {"name": "Sarah Chen", "title": "Engineering Manager @ Vercel", "platform": "Twitter", "handle": "@sarahchen_dev", "url": "https://twitter.com/sarahchen_dev", "score": 9, "relevance": "Tweeted about migrating from Jira to a modern tool. Active in developer tooling discussions. Team of 12 engineers."},
                {"name": "Marcus Johnson", "title": "CTO @ Resend", "platform": "Twitter", "handle": "@marcusjdev", "url": "https://twitter.com/marcusjdev", "score": 9, "relevance": "Building in public, recently asked for PM tool recommendations. 8K followers, highly engaged in dev community."},
                {"name": "Ana Rodrigues", "title": "VP Engineering @ Lattice", "platform": "LinkedIn", "handle": "ana-rodrigues-eng", "url": "https://linkedin.com/in/ana-rodrigues-eng", "score": 8, "relevance": "Posted about AI adoption in engineering teams. Decision maker for 200+ person eng org."},
                {"name": "Dev Patel", "title": "Head of Product @ Railway", "platform": "Twitter", "handle": "@devpatel_pm", "url": "https://twitter.com/devpatel_pm", "score": 8, "relevance": "Regularly discusses dev tools and workflows. Influential in the developer platform space."},
                {"name": "Lisa Park", "title": "Engineering Director @ Stripe", "platform": "LinkedIn", "handle": "lisa-park-stripe", "url": "https://linkedin.com/in/lisa-park-stripe", "score": 8, "relevance": "Speaking at conferences about AI in software development. Enterprise decision maker."},
                {"name": "James O'Brien", "title": "Founder @ DevOps Weekly", "platform": "Substack", "handle": "devopsweekly", "url": "https://devopsweekly.substack.com", "score": 7, "relevance": "Newsletter reaches 40K+ developers. Has covered project management tools before."},
                {"name": "Priya Sharma", "title": "Staff Engineer @ Figma", "platform": "Twitter", "handle": "@priyabuilds", "url": "https://twitter.com/priyabuilds", "score": 7, "relevance": "Vocal about developer experience. Potential integration partner advocate."},
                {"name": "Tom Wilson", "title": "CTO @ Midday", "platform": "GitHub", "handle": "tomwilson", "url": "https://github.com/tomwilson", "score": 7, "relevance": "Building AI-native financial tools. Likely needs AI-compatible PM solution."},
                {"name": "Sofia Martinez", "title": "EM @ Notion", "platform": "Discord", "handle": "sofia.dev", "url": "#", "score": 6, "relevance": "Active in developer Discord communities discussing workflow optimization."},
                {"name": "Alex Kim", "title": "Tech Lead @ Supabase", "platform": "Reddit", "handle": "u/alexkim_dev", "url": "https://reddit.com/u/alexkim_dev", "score": 6, "relevance": "Commented on r/ExperiencedDevs about PM tool frustrations. Team lead evaluating options."}
            ]
        },
        "investor_research": {
            "competitors": [
                {"name": "Asana", "description": "Work management platform for enterprise teams", "url": "https://asana.com", "funding": "$450M+", "investors": ["Benchmark", "Andreessen Horowitz", "Generation Investment", "Founders Fund"]},
                {"name": "Monday.com", "description": "Work operating system for teams of all sizes", "url": "https://monday.com", "funding": "$234M", "investors": ["Sapphire Ventures", "Hamilton Lane", "Vintage Investment Partners"]},
                {"name": "Shortcut (fka Clubhouse)", "description": "Project management for software teams", "url": "https://shortcut.com", "funding": "$66M", "investors": ["Greylock Partners", "Lerer Hippeau", "Battery Ventures"]},
                {"name": "Height", "description": "AI-first project management tool", "url": "https://height.app", "funding": "$8M", "investors": ["Y Combinator", "Mike Krieger", "Calvin French-Owen"]},
                {"name": "Plane", "description": "Open-source project management alternative", "url": "https://plane.so", "funding": "$4.5M", "investors": ["OSS Capital", "Akash Bajwa"]}
            ],
            "competitor_investors": [
                {"name": "Benchmark", "type": "VC", "focus": "Enterprise SaaS, developer tools — invested in Asana, Zendesk, New Relic", "url": "https://linkedin.com/company/benchmark"},
                {"name": "Andreessen Horowitz (a16z)", "type": "VC", "focus": "Software eating the world — massive developer tools portfolio including Asana, GitHub", "url": "https://linkedin.com/company/a16z"},
                {"name": "Greylock Partners", "type": "VC", "focus": "Enterprise software, developer platforms — invested in Shortcut, Figma, Discord", "url": "https://linkedin.com/company/greylock-partners"},
                {"name": "Battery Ventures", "type": "VC", "focus": "Application software, infrastructure — invested in Shortcut, Glassdoor", "url": "https://linkedin.com/company/battery-ventures"}
            ],
            "market_investors": [
                {"name": "Accel", "type": "VC", "focus": "Enterprise SaaS at scale — Slack, Atlassian, CrowdStrike portfolio", "url": "https://linkedin.com/company/accel-partners"},
                {"name": "Sequoia Capital", "type": "VC", "focus": "AI-native companies, developer tools — recent AI fund announcements", "url": "https://linkedin.com/company/sequoia-capital"},
                {"name": "Index Ventures", "type": "VC", "focus": "Developer tools, SaaS — invested in Figma, Notion, Datadog", "url": "https://linkedin.com/company/index-ventures"},
                {"name": "Lightspeed Venture Partners", "type": "VC", "focus": "Enterprise AI, developer platforms — recent $7B fund for AI companies", "url": "https://linkedin.com/company/lightspeed-venture-partners"},
                {"name": "Mike Krieger", "type": "Angel", "focus": "Instagram co-founder — invests in developer tools and design software", "url": "https://linkedin.com/in/mikekrieger"},
                {"name": "Elad Gil", "type": "Angel", "focus": "Prolific angel investor in infrastructure and developer tools — Color, Instacart, Airbnb", "url": "https://linkedin.com/in/eladgil"}
            ]
        }
    }


@app.get("/testreport", response_class=HTMLResponse)
async def test_report(request: Request, tier: str = "free"):
    """Test report with mock data for iterating on layout. Supports ?tier=free|starter|growth"""
    mock = _mock_analysis()
    html = render_dashboard(
        analysis=mock,
        startup_name="Linear",
        report_id="test-mock-001",
        tier=tier,
        checkout_url="#pricing",
        upgrade_url="#pricing",
    )
    return HTMLResponse(content=html)


@app.get("/test2", response_class=HTMLResponse)
async def test_report_v5(request: Request, tier: str = "free"):
    """V5 dashboard — formal BI style, single scroll, spreadsheet tables. Supports ?tier=free|starter|growth"""
    mock = _mock_analysis()
    html = render_dashboard_v5(
        analysis=mock,
        startup_name="Linear",
        report_id="test-mock-001",
        tier=tier,
        checkout_url="#pricing",
        upgrade_url="#pricing",
    )
    return HTMLResponse(content=html)


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def view_report(request: Request, report_id: str, paid: str | None = None):
    """View a report — dashboard with tier-based content gating."""
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

    # Load analysis data for dashboard
    analysis = {}
    analysis_path = REPORTS_DIR / report_id / "analysis.json"
    if analysis_path.exists():
        try:
            analysis = json.loads(analysis_path.read_text())
        except Exception:
            pass

    # Determine tier based on subscription status + login
    tier = "free"
    checkout_url = record.checkout_url or "#"
    upgrade_url = "#"

    if record.status in ("active", "paid"):
        # Get logged-in user from session cookie
        session_cookie = request.cookies.get("mckoutie_session")
        user = auth.get_session_user(session_cookie)

        if not user:
            # Not logged in — show login prompt
            login_url = f"/auth/twitter?redirect={quote(f'/report/{report_id}')}"
            return HTMLResponse(content=_login_page(record, login_url))

        # Check if this user owns the report (requester or subscriber)
        user_twitter_id = user.get("twitter_id", "")
        is_owner = (
            user_twitter_id == record.author_id
            or user_twitter_id == record.subscriber_twitter_id
        )

        if not is_owner:
            return HTMLResponse(content=_not_your_report_page(record, user))

        # Authorized — determine tier from record
        tier = record.tier or "starter"

        # Generate upgrade URL for starter users
        if tier == "starter" and settings.has_payments:
            upgrade_url = payments.create_upgrade_session(
                report_id=report_id,
                startup_name=record.startup_name,
                customer_id=record.customer_id,
            ) or "#"

    # Render dashboard with appropriate tier
    html = render_dashboard(
        analysis=analysis,
        startup_name=record.startup_name,
        report_id=report_id,
        tier=tier,
        checkout_url=checkout_url,
        upgrade_url=upgrade_url,
    )
    return HTMLResponse(content=html)


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe subscription lifecycle webhooks."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    event = payments.verify_webhook(payload, sig)
    if not event:
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        # New subscription started
        metadata = obj.get("metadata", {})
        report_id = metadata.get("report_id")
        twitter_id = metadata.get("twitter_id", "")
        subscription_id = obj.get("subscription", "")
        customer_id = obj.get("customer", "")
        tier = metadata.get("tier", "starter")

        if report_id:
            report_store.update_status(
                report_id,
                "active",
                paid_at=datetime.now(tz=timezone.utc).isoformat(),
                subscription_id=subscription_id,
                customer_id=customer_id,
                subscriber_twitter_id=twitter_id,
                tier=tier,
            )
            logger.info(f"Subscription started for report {report_id} (tier={tier})")

    elif event_type == "customer.subscription.deleted":
        # Subscription canceled
        metadata = obj.get("metadata", {})
        report_id = metadata.get("report_id")
        if report_id:
            report_store.update_status(report_id, "canceled")
            logger.info(f"Subscription canceled for report {report_id}")

    elif event_type == "invoice.payment_failed":
        # Payment failed on renewal
        sub_id = obj.get("subscription", "")
        if sub_id:
            # Find report by subscription ID and mark as past_due
            for record in report_store.list_reports(status="active"):
                if record.subscription_id == sub_id:
                    report_store.update_status(record.report_id, "ready")
                    logger.warning(f"Payment failed for report {record.report_id}")
                    break

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


def _login_page(record: report_store.ReportRecord, login_url: str) -> str:
    return f"""<!DOCTYPE html>
<html><head>
    <meta charset="UTF-8">
    <title>mckoutie — Log in to view report</title>
    <style>
        body {{ font-family: 'SF Mono', monospace; background: #0a0a0a; color: #e0e0e0;
               display: flex; justify-content: center; align-items: center;
               min-height: 100vh; padding: 2rem; }}
        .container {{ text-align: center; max-width: 500px; }}
        h1 {{ color: #00d4ff; margin-bottom: 0.5rem; }}
        p {{ color: #888; margin: 1rem 0; line-height: 1.6; }}
        .login-btn {{ display: inline-block; background: #1da1f2; color: #fff;
                      padding: 14px 32px; font-size: 1rem; font-weight: bold;
                      text-decoration: none; border-radius: 6px; margin: 1.5rem 0;
                      font-family: monospace; }}
        .login-btn:hover {{ background: #0d8bd9; }}
        .note {{ color: #444; font-size: 0.8rem; margin-top: 2rem; }}
    </style>
</head><body>
    <div class="container">
        <h1>mckoutie</h1>
        <p>Strategy Brief for <strong style="color: #00d4ff;">{record.startup_name}</strong></p>
        <p>Log in with the Twitter account that requested this report to view it.</p>
        <a class="login-btn" href="{login_url}">Log in with Twitter / X</a>
        <p class="note">We only verify your identity. We don't post or read your DMs.</p>
    </div>
</body></html>"""


def _not_your_report_page(record: report_store.ReportRecord, user: dict) -> str:
    return f"""<!DOCTYPE html>
<html><head>
    <meta charset="UTF-8">
    <title>mckoutie — Access denied</title>
    <style>
        body {{ font-family: 'SF Mono', monospace; background: #0a0a0a; color: #e0e0e0;
               display: flex; justify-content: center; align-items: center;
               min-height: 100vh; padding: 2rem; }}
        .container {{ text-align: center; max-width: 500px; }}
        h1 {{ color: #ff6b35; margin-bottom: 0.5rem; }}
        p {{ color: #888; margin: 1rem 0; line-height: 1.6; }}
        a {{ color: #00d4ff; }}
    </style>
</head><body>
    <div class="container">
        <h1>Not your report</h1>
        <p>You're logged in as <strong style="color: #00d4ff;">@{user.get('username', '?')}</strong>,
           but this report belongs to <strong>@{record.author_username}</strong>.</p>
        <p>Want your own analysis?
           <a href="https://x.com/intent/tweet?text=@mckoutie%20analyse%20my%20startup%20" target="_blank">
           Tweet @mckoutie</a></p>
        <p style="margin-top: 2rem;">
            <a href="/auth/logout?redirect=/report/{record.report_id}">Log in with a different account</a>
        </p>
    </div>
</body></html>"""


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
        <p class="price">${settings.report_price_usd}/mo — ongoing market intelligence</p>
        <p style="color: #666;">Your report stays alive with fresh insights every month. Cancel anytime.</p>
        <a class="cta" href="{checkout_url}">Subscribe &amp; Unlock</a>
        <p style="color: #444; font-size: 0.75rem; margin-top: 0.5rem;">You'll log in with Twitter after payment to access your report.</p>
    </div>

    <p style="color: #333; font-size: 0.8rem; margin-top: 3rem;">
        Report ID: {record.report_id} | Not affiliated with McKinsey.
    </p>
</body></html>"""
