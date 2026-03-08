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

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from src.config import settings
from src.modules import auth, payments, report_store, db
from src.country_pages import COUNTRIES, render_country_page
from src.analysis.report_generator import generate_report_html
from src.analysis.dashboard_renderer import render_dashboard
from src.analysis.dashboard_v3 import render_dashboard_v3
from src.analysis.dashboard_v4 import render_dashboard_v4
from src.analysis.dashboard_v5 import render_dashboard_v5
from src.orchestrator import run_deep_analysis, is_deep_analysis_running, run_deep_analysis_background, get_deep_progress

# Use Railway persistent volume if available, else local
_data_dir = Path("/data")
REPORTS_DIR = _data_dir / "reports" if _data_dir.is_dir() else Path(__file__).parent.parent / "reports"

logger = logging.getLogger(__name__)

app = FastAPI(title="mckoutie", description="McKinsey at home")

# CORS — allow SSE from mckoutie.com to Railway directly
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.mckoutie.com", "https://mckoutie.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def _check_hermes_access(request: Request) -> tuple[bool, str]:
    key = request.headers.get("x-hermes-key", "")
    if not settings.hermes_api_key:
        return False, "Hermes API key not configured"
    if key != settings.hermes_api_key:
        return False, "Invalid Hermes API key"

    allowed_ips = settings.hermes_allowed_ip_set
    if allowed_ips:
        ip = _client_ip(request)
        if ip not in allowed_ips:
            return False, f"IP not allowed: {ip}"

    return True, ""


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
        .hero-building img {
            max-width: 100%; height: auto; max-height: 75vh;
            filter: drop-shadow(0 0 60px rgba(117,170,219,0.15));
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
    <div class="hero-building">
        <img src="/building.png" alt="mckoutie headquarters — un rascacielos lleno de memes">
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
        <a href="/">English</a> · <strong>Argentina</strong> · <a href="/BR">Brazil</a> · <a href="/CA">Canada</a> · <a href="/CL">Chile</a> · <a href="/CO">Colombia</a> · <a href="/DE">Germany</a> · <a href="/ES">Spain</a> · <a href="/FR">France</a> · <a href="/IE">Ireland</a> · <a href="/IL">Israel</a> · <a href="/IT">Italy</a> · <a href="/MX">Mexico</a> · <a href="/NL">Netherlands</a> · <a href="/PE">Peru</a> · <a href="/PL">Poland</a> · <a href="/PT">Portugal</a> · <a href="/SE">Sweden</a> · <a href="/UK">UK</a> · <a href="/UY">Uruguay</a> · <a href="https://x.com/mckoutie" target="_blank">Twitter</a>
    </p>
    <p style="margin-top: 1rem;">No afiliado con McKinsey (obviamente). Hecho con asado y mate.</p>
</footer>

</body>
</html>"""


# --- Dynamic country landing pages ---
for _code in COUNTRIES:
    def _make_handler(code: str):
        async def handler():
            return HTMLResponse(render_country_page(code))
        handler.__name__ = f"landing_{code.lower()}"
        return handler
    app.get(f"/{_code}", response_class=HTMLResponse)(_make_handler(_code))


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
    # Vercel rewrites strip Set-Cookie headers from external backends.
    # Pass the JWT as a URL parameter instead — client-side JS will set the cookie.
    separator = "&" if "?" in redirect_to else "?"
    redirect_with_token = f"{redirect_to}{separator}_token={token}"
    logger.info(f"[AUTH] Passing token via URL for @{user_info.get('username')}, redirecting to {redirect_to}")
    return RedirectResponse(redirect_with_token)


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
             "killer_insight": "Focus on engineering managers, not individual devs — they mandate tool adoption",
             "deep_dive": {
                 "research_type": "communities",
                 "actions": [
                     {"title": "Launch API Hackathon", "description": "Create a 2-week virtual hackathon focused on AI agent integrations with Linear's API. Prizes: $50K total ($20K first, $10K second, $5K third, $15K in honorable mentions). Promote through dev Discord servers and Twitter.", "expected_result": "500+ submissions, 2,000+ new API signups, viral tweets from participants"},
                     {"title": "Create 'Linear Champions' Program", "description": "Identify 50 power users in dev communities. Give them early access to features, branded swag, and a private Slack channel with the founding team. They become your evangelists.", "expected_result": "50 champions generating 10+ organic mentions/week each"},
                     {"title": "Build Open-Source Templates", "description": "Publish 20 open-source Linear workflow templates on GitHub (sprint planning, bug triage, AI-assisted backlog grooming). Each template links back to Linear.", "expected_result": "1,000+ GitHub stars, steady stream of organic traffic from developers discovering templates"}
                 ],
                 "research": [
                     {"name": "Dev.to Community", "url": "https://dev.to", "members": "1.2M+", "relevance": "Active discussions on dev tools, high engagement on PM tool comparisons"},
                     {"name": "r/ExperiencedDevs", "url": "https://reddit.com/r/ExperiencedDevs", "members": "180K", "relevance": "Senior devs discussing tool choices — high decision-maker density"},
                     {"name": "Hacker News", "url": "https://news.ycombinator.com", "members": "500K+ monthly", "relevance": "Show HN posts for dev tools regularly hit front page — massive exposure"},
                     {"name": "Discord: Reactiflux", "url": "https://discord.gg/reactiflux", "members": "230K", "relevance": "Largest React dev community — many are engineering leads choosing tools"},
                     {"name": "IndieHackers Dev Tools", "url": "https://indiehackers.com", "members": "100K+", "relevance": "Founders and solo devs evaluating PM tools — high purchase intent"}
                 ]
             }},
            {"channel": "Content Marketing", "score": 9, "effort": "high", "timeline": "months", "budget": "$10K-15K",
             "specific_ideas": ["Weekly 'AI Development' newsletter", "Case studies showing 40%+ velocity improvements", "'State of Product Development' annual report"],
             "first_move": "Launch weekly email series profiling how top companies use AI in development",
             "why_or_why_not": "Linear's audience is hungry for tactical AI workflow content",
             "killer_insight": "Don't just talk about Linear — become the thought leader on AI-human collaboration",
             "deep_dive": {
                 "research_type": "content_topics",
                 "actions": [
                     {"title": "Launch 'AI Development Weekly' Newsletter", "description": "Weekly newsletter covering how top engineering teams use AI in their workflow. Each edition profiles one company, one tool, one technique. Distribute via Substack + LinkedIn.", "expected_result": "5,000 subscribers in 90 days, 35% open rate, pipeline of enterprise leads"},
                     {"title": "Publish 'State of AI in Product Development' Report", "description": "Survey 500+ engineering leaders on AI adoption. Publish findings as a gated PDF report. Promote through press, social, and partner channels.", "expected_result": "10,000+ downloads, 50+ press mentions, definitive industry resource"},
                     {"title": "Create Video Case Study Series", "description": "Record 5-minute video case studies with 10 customers showing before/after metrics. Distribute on YouTube, embed in sales decks, use in retargeting ads.", "expected_result": "100K+ combined views, 40% increase in enterprise demo requests"}
                 ],
                 "research": [
                     {"name": "How AI Agents Are Changing Sprint Planning", "volume": "2,400/mo", "difficulty": "Medium", "format": "Long-form guide + video", "angle": "Tactical walkthrough with real Linear screenshots"},
                     {"name": "Jira vs Linear: The Definitive 2026 Comparison", "volume": "8,100/mo", "difficulty": "High", "format": "SEO comparison page", "angle": "Lead with developer experience, not feature lists"},
                     {"name": "The Engineering Manager's Guide to AI-Powered Workflows", "volume": "1,800/mo", "difficulty": "Low", "format": "Ebook + blog series", "angle": "Position Linear as the enabler, not the topic"},
                     {"name": "Why Developers Hate Jira (And What to Do About It)", "volume": "12,000/mo", "difficulty": "High", "format": "Blog post + Twitter thread", "angle": "Empathy-first content that naturally positions Linear"},
                     {"name": "Building a Zero-Meeting Development Team", "volume": "3,200/mo", "difficulty": "Medium", "format": "Case study + template", "angle": "Show how async AI workflows replace status meetings"}
                 ]
             }},
            {"channel": "Community Building", "score": 9, "effort": "high", "timeline": "months", "budget": "$8K-20K",
             "specific_ideas": ["Create 'Linear AI Pioneers' community", "Monthly virtual events on AI development", "Certification program for Linear AI workflows"],
             "first_move": "Launch 'Linear AI Collective' Slack community",
             "why_or_why_not": "Perfect fit for developer-centric audience, creates retention",
             "killer_insight": "Build the definitive community for AI-powered product development",
             "deep_dive": {
                 "research_type": "community_platforms",
                 "actions": [
                     {"title": "Launch 'Linear AI Collective' Slack", "description": "Create a curated Slack workspace. Channels: #general, #ai-workflows, #showcase, #hiring, #feedback. Invite first 50 members personally from top customers. Weekly office hours with founding team.", "expected_result": "500 members in 60 days, 40% weekly active rate, direct product feedback loop"},
                     {"title": "Monthly 'AI Dev Roundtable' Events", "description": "Virtual events where 3-4 engineering leaders share how they use AI in development. 45 min panel + 15 min Q&A. Record and publish as podcast. Use for lead gen.", "expected_result": "200+ live attendees per event, 1,000+ podcast downloads, warm enterprise leads"},
                     {"title": "Linear Certification Program", "description": "Create 'Linear AI Workflow Certified' badge. 3-module course covering setup, AI agents, advanced automation. Free for teams, badge for LinkedIn. Partners get 'Certified Linear Consultant' status.", "expected_result": "2,000 certified users in 6 months, creates switching cost and loyalty"}
                 ],
                 "research": [
                     {"name": "Slack Community", "platform": "Slack", "cost": "$0", "pros": "Developer-native, threaded discussions, integrations", "cons": "Hard to discover, message limits on free tier"},
                     {"name": "Discord Server", "platform": "Discord", "cost": "$0", "pros": "Voice channels for events, great for real-time, younger audience", "cons": "Can feel informal for enterprise"},
                     {"name": "Circle.so", "platform": "Circle", "cost": "$89/mo", "pros": "Built for communities, course integration, clean UX", "cons": "Another platform to check, less developer-native"}
                 ]
             }},
            {"channel": "Partnerships & Integrations", "score": 9, "effort": "high", "timeline": "months", "budget": "$5K-20K",
             "specific_ideas": ["Deep Figma integration", "Native Slack workflows", "GitHub Apps marketplace"],
             "first_move": "Build comprehensive Figma plugin for design-dev handoff",
             "why_or_why_not": "Integrations expand Linear beyond engineering",
             "killer_insight": "Focus on integrations that bring non-technical roles into Linear",
             "deep_dive": {
                 "research_type": "partners",
                 "actions": [
                     {"title": "Build Figma Plugin for Design-Dev Handoff", "description": "Create a Figma plugin that syncs design files directly to Linear issues. Auto-generates spec tickets from Figma frames. Two-way status sync.", "expected_result": "10,000+ plugin installs, brings design teams into Linear ecosystem"},
                     {"title": "Cursor IDE Integration", "description": "Build deep integration with Cursor (AI code editor). Let developers create/update Linear issues from inside their IDE. AI agent can auto-close tickets when PRs merge.", "expected_result": "Becomes the default PM tool in the AI-native development stack"},
                     {"title": "Notion Bi-Directional Sync", "description": "Sync Linear roadmaps and project status to Notion docs automatically. Product managers stay in Notion, engineers stay in Linear. Both see the same data.", "expected_result": "Removes the biggest blocker to enterprise adoption (non-eng teams)"}
                 ],
                 "research": [
                     {"name": "Figma", "type": "Integration", "audience": "3M+ designers", "fit": "Design-dev handoff is a major pain point — Linear can own this workflow"},
                     {"name": "Cursor", "type": "Integration", "audience": "500K+ developers", "fit": "AI-native IDE + AI-native PM = natural pairing. Co-marketing opportunity"},
                     {"name": "Vercel", "type": "Co-marketing", "audience": "1M+ developers", "fit": "Vercel's audience is Linear's audience. Joint webinars, case studies, bundled onboarding"},
                     {"name": "Notion", "type": "Integration", "audience": "30M+ users", "fit": "Notion for docs, Linear for engineering — removes adoption friction from product teams"},
                     {"name": "Anthropic/Claude", "type": "AI Partnership", "audience": "Growing rapidly", "fit": "AI agent workflows in Linear powered by Claude — differentiation play"}
                 ]
             }},
            {"channel": "Direct Sales", "score": 8, "effort": "high", "timeline": "months", "budget": "$25K-50K",
             "specific_ideas": ["Hire enterprise AEs focused on Series B+ companies", "Create 'AI Readiness Assessment'", "Pilot program for AI development practices"],
             "first_move": "Hire one enterprise AE and create 'AI Development Maturity' assessment",
             "why_or_why_not": "Necessary for $50K+ deals",
             "killer_insight": "Sell AI transformation, not just another PM tool",
             "deep_dive": {
                 "research_type": "sales_targets",
                 "actions": [
                     {"title": "Build 'AI Development Maturity' Assessment", "description": "Create a 15-question interactive assessment that scores a company's AI readiness. Results page shows where Linear fits. Gate full report behind email. Use in sales calls as discovery tool.", "expected_result": "500+ assessments/month, 30% conversion to demo request"},
                     {"title": "Launch Pilot Program for Enterprise", "description": "Offer 90-day pilot for teams of 50+. Dedicated CSM, weekly check-ins, custom onboarding. Goal: prove 30%+ velocity improvement with data. Pilot converts to annual contract.", "expected_result": "10 pilot customers, 70% conversion to paid annual contracts"},
                     {"title": "Create Sales Playbook for 'Jira Migration'", "description": "Build a complete migration playbook: data export scripts, parallel running guide, change management templates. Makes switching from Jira frictionless.", "expected_result": "Removes the #1 objection ('migration is too hard'), doubles close rate"}
                 ],
                 "research": [
                     {"name": "Vercel", "title": "VP Engineering", "reason": "150+ engineers, using Jira, publicly frustrated with tooling", "approach": "Warm intro via developer community overlap"},
                     {"name": "Stripe", "title": "Engineering Director", "reason": "Known for best-in-class tooling choices, 2,000+ engineers", "approach": "Case study opportunity — if Stripe uses it, everyone follows"},
                     {"name": "Datadog", "title": "CTO", "reason": "500+ engineers, heavy AI investment, likely evaluating modern PM tools", "approach": "Position as AI-native complement to their monitoring stack"},
                     {"name": "Ramp", "title": "Head of Engineering", "reason": "Fast-growing, 200+ engineers, modern tech stack, values developer experience", "approach": "Product-led approach — get one team to adopt, expand from there"},
                     {"name": "Anthropic", "title": "VP Engineering", "reason": "AI-native company building AI tools — perfect fit for AI-native PM", "approach": "Dogfooding narrative — AI company using AI-powered PM tool"}
                 ]
             }},
            {"channel": "Product Hunt & Tech Publications", "score": 8, "effort": "medium", "timeline": "weeks", "budget": "$3K-8K",
             "specific_ideas": ["Launch AI features on Product Hunt", "Pitch TechCrunch", "Submit to developer tool awards"],
             "first_move": "Coordinate Product Hunt launch for next major AI feature",
             "why_or_why_not": "Tech press loves AI stories and Linear has genuine innovation",
             "killer_insight": "Time announcements with broader AI news cycles",
             "deep_dive": {
                 "research_type": "platforms",
                 "actions": [
                     {"title": "Product Hunt Feature Launch", "description": "Launch next major AI feature as standalone PH product. Recruit 200+ upvoters from community in advance. Post at 12:01 AM PT on Tuesday (highest engagement day). Prepare maker comment with video demo.", "expected_result": "#1 Product of the Day, 5,000+ visits, 500+ signups"},
                     {"title": "Pitch TechCrunch 'AI Development' Story", "description": "Pitch Frederic Lardinois at TechCrunch with exclusive data: '25,000 teams using AI-powered project management — here's what they've learned.' Offer exclusive access to internal AI metrics.", "expected_result": "TechCrunch feature article, 50K+ views, enterprise credibility boost"},
                     {"title": "Submit to Developer Tool Awards", "description": "Submit to Golden Kitty Awards (Product Hunt), StackShare Top Tools, DevOps Dozen, and InfoWorld Technology of the Year. Create dedicated awards landing page.", "expected_result": "2-3 award nominations/wins, permanent credibility badges for marketing"}
                 ],
                 "research": [
                     {"name": "Product Hunt", "type": "Launch Platform", "audience": "Tech early adopters, founders, PMs", "strategy": "Tuesday launch, 200+ pre-committed upvoters, video demo"},
                     {"name": "Hacker News (Show HN)", "type": "Launch Platform", "audience": "Senior developers, CTOs", "strategy": "Technical post focusing on architecture, not marketing"},
                     {"name": "TechCrunch", "type": "Tech Publication", "audience": "Industry, investors, enterprise buyers", "strategy": "Pitch with data, offer exclusive access"}
                 ]
             }},
            {"channel": "Conferences & Events", "score": 8, "effort": "high", "timeline": "months", "budget": "$15K-30K",
             "specific_ideas": ["Sponsor DevOps conferences", "Host 'AI in Product' meetups", "Booth at GitHub Universe"],
             "first_move": "Sponsor and speak at next major DevOps conference",
             "why_or_why_not": "High-impact for enterprise prospects",
             "killer_insight": "Create hands-on AI workflow experiences, don't just sponsor",
             "deep_dive": {
                 "research_type": "conferences",
                 "actions": [
                     {"title": "Sponsor & Speak at GitHub Universe 2026", "description": "Book speaking slot on 'AI-powered development workflows.' Set up interactive demo booth where attendees can try AI agent integrations live. Host after-party for 100 enterprise prospects.", "expected_result": "200+ qualified enterprise leads, 15 pilot signups, press coverage"},
                     {"title": "Host 'AI Development Summit' Side Event", "description": "Instead of sponsoring a big conference, host your own 1-day event the day before a major conference (piggyback on the audience). 200 attendees, 8 speakers, hands-on workshops.", "expected_result": "Positions Linear as the AI dev tools leader, 200 warm leads, content for 3 months"},
                     {"title": "Launch Local Meetup Series in 5 Cities", "description": "Monthly meetups in SF, NYC, London, Berlin, and Tokyo. 30-50 attendees each. Lightning talks + demos + networking. Partner with local dev communities to co-host.", "expected_result": "150+ monthly touchpoints, local community building, word-of-mouth engine"}
                 ],
                 "research": [
                     {"name": "GitHub Universe 2026", "date": "Oct 2026", "location": "San Francisco, CA", "cost": "$8K-25K booth", "audience": "10,000+ developers", "fit": "Perfect audience overlap — GitHub users are Linear's core market"},
                     {"name": "KubeCon NA 2026", "date": "Nov 2026", "location": "Salt Lake City, UT", "cost": "$5K-15K booth", "audience": "12,000+ DevOps engineers", "fit": "Platform/infra teams who influence tooling decisions"},
                     {"name": "React Summit 2026", "date": "Jun 2026", "location": "Amsterdam", "cost": "$3K-10K sponsor", "audience": "3,000+ frontend devs", "fit": "Product-minded engineers who care about DX"},
                     {"name": "AI Engineer World's Fair", "date": "Jun 2026", "location": "San Francisco, CA", "cost": "$5K-20K booth", "audience": "5,000+ AI engineers", "fit": "Exact audience for AI workflow positioning"},
                     {"name": "DevOpsDays (Multiple Cities)", "date": "Year-round", "location": "Global", "cost": "$1K-5K per city", "audience": "200-500 per event", "fit": "Affordable, intimate, high-quality networking with decision makers"}
                 ]
             }},
            {"channel": "Sales Prospecting", "score": 8, "effort": "high", "timeline": "weeks", "budget": "$15K-30K",
             "specific_ideas": ["Cold outreach to CTOs at fast-growing companies", "LinkedIn prospecting", "Account-based marketing for top 100 targets"],
             "first_move": "Create targeted LinkedIn campaign reaching CTOs at Series B+ companies",
             "why_or_why_not": "Essential for enterprise growth",
             "killer_insight": "Lead with AI transformation consulting, not tool sales",
             "deep_dive": {
                 "research_type": "outreach",
                 "actions": [
                     {"title": "Build Top 100 Target Account List", "description": "Use Apollo + LinkedIn Sales Nav to identify 100 companies: Series B+, 50-500 engineers, using Jira/Asana, recent funding. Enrich with tech stack data from BuiltWith. Assign to SDR for multi-touch cadence.", "expected_result": "100 qualified accounts, 15-20% meeting rate from multi-touch outreach"},
                     {"title": "Launch LinkedIn ABM Campaign", "description": "Create LinkedIn ads targeting engineering leaders at top 100 accounts. Serve content sequence: awareness (AI dev blog) > consideration (case study) > conversion (free pilot offer). $50/day budget.", "expected_result": "5-8% account penetration rate, warm inbound from target accounts"},
                     {"title": "Cold Email Sequence with AI Personalization", "description": "3-email sequence personalized with company-specific AI insights. Email 1: share relevant case study. Email 2: offer AI maturity assessment. Email 3: pilot invitation with specific ROI projection.", "expected_result": "25% open rate, 5% reply rate, 10+ demos/month from cold outreach"}
                 ],
                 "research": [
                     {"name": "Email Template 1: The Insight Lead", "subject": "How [CompanyName] could ship 30% faster with AI workflows", "preview": "I noticed your team is using [Jira/Asana]. Companies like [Similar Company] switched to AI-native PM and saw..."},
                     {"name": "Email Template 2: The Case Study", "subject": "[Similar Company] cut sprint planning time by 60%", "preview": "Quick case study I thought you'd find interesting. [Company] migrated from Jira and within 90 days..."},
                     {"name": "Email Template 3: The Pilot Offer", "subject": "Free 90-day pilot for [CompanyName]'s engineering team", "preview": "I'll be direct: I think Linear could save your team 5+ hours/week. I'd like to prove it with a free pilot..."}
                 ]
             }},
            {"channel": "Search Engine Marketing", "score": 7, "effort": "medium", "timeline": "weeks", "budget": "$8K-15K",
             "specific_ideas": ["Target 'Jira alternatives for AI teams'", "Retargeting campaigns"],
             "first_move": "Launch Google Ads targeting 'Jira alternative' with AI landing page",
             "why_or_why_not": "Expensive but necessary for high-intent searches",
             "killer_insight": "Don't compete on generic PM keywords — own 'AI-powered project management'",
             "deep_dive": {
                 "research_type": "keywords",
                 "actions": [
                     {"title": "Launch 'Jira Alternative' Ad Campaign", "description": "Create Google Ads campaign targeting 'Jira alternative' long-tail keywords. Build dedicated landing page comparing Linear vs Jira with AI features highlighted. A/B test 3 ad copy variants.", "expected_result": "200+ clicks/month at $8-12 CPC, 15% landing page conversion rate"},
                     {"title": "Build Retargeting Funnel", "description": "Install Google/Meta pixels. Retarget website visitors who viewed pricing but didn't sign up. Serve case study ads showing productivity gains. Budget: $20/day.", "expected_result": "Recover 5-10% of lost visitors, 3x ROI on retargeting spend"},
                     {"title": "Own 'AI Project Management' Category", "description": "Bid on emerging AI+PM keywords before competition heats up. Create dedicated landing pages for each keyword cluster. First-mover advantage on new category terms.", "expected_result": "Category ownership before competitors enter, $2-4 CPC (vs $15+ for 'project management')"}
                 ],
                 "research": [
                     {"keyword": "jira alternative", "volume": "18,100/mo", "cpc": "$12.40", "competition": "High", "strategy": "Exact match, dedicated landing page"},
                     {"keyword": "ai project management tool", "volume": "2,400/mo", "cpc": "$4.20", "competition": "Medium", "strategy": "Category ownership — bid aggressively"},
                     {"keyword": "linear vs jira", "volume": "1,900/mo", "cpc": "$8.50", "competition": "Low", "strategy": "Comparison page, target switchers"},
                     {"keyword": "best pm tool for developers", "volume": "3,600/mo", "cpc": "$6.80", "competition": "Medium", "strategy": "Developer-focused landing page"},
                     {"keyword": "ai sprint planning", "volume": "720/mo", "cpc": "$2.10", "competition": "Low", "strategy": "Cheap emerging keyword — get in early"}
                 ]
             }},
            {"channel": "Email Marketing", "score": 7, "effort": "medium", "timeline": "weeks", "budget": "$3K-8K",
             "specific_ideas": ["Onboarding sequence for AI features", "Segmented campaigns by role"],
             "first_move": "Rebuild onboarding to feature AI agent setup in week 1",
             "why_or_why_not": "Essential for activation and retention",
             "killer_insight": "Most customers aren't using Linear's full AI capabilities",
             "deep_dive": {
                 "research_type": "email_sequences",
                 "actions": [
                     {"title": "Rebuild AI Onboarding Sequence", "description": "Replace current onboarding with a 7-email sequence that guides new users through AI agent setup. Day 1: Welcome + connect first integration. Day 3: Set up your first AI workflow. Day 5: Advanced automations. Day 7: Share your setup with team.", "expected_result": "40% increase in AI feature adoption within first 14 days, 25% reduction in churn at day 30"},
                     {"title": "Launch Role-Based Nurture Campaigns", "description": "Segment users by role (engineer, EM, PM, CTO) and send tailored content. Engineers get workflow tips. EMs get team productivity data. CTOs get ROI case studies. PMs get roadmap templates.", "expected_result": "3x click-through rate vs generic emails, 15% increase in team expansion"},
                     {"title": "Win-Back Campaign for Churned Teams", "description": "30/60/90 day re-engagement sequence for teams that cancelled. Lead with new AI features they missed. Include specific data on productivity gains from similar teams. Offer 30-day free restart.", "expected_result": "8-12% reactivation rate on churned teams, $50K+ recovered ARR in 90 days"}
                 ],
                 "research": [
                     {"name": "Welcome Email", "subject": "Your AI development co-pilot is ready", "timing": "Day 0 (immediate)", "goal": "First login + connect GitHub/GitLab integration"},
                     {"name": "Quick Win Email", "subject": "Your first AI-powered sprint in 5 minutes", "timing": "Day 1", "goal": "Create first AI-assisted sprint plan"},
                     {"name": "Power Feature Email", "subject": "The AI trick that saved Vercel 6 hours/week", "timing": "Day 3", "goal": "Set up automated bug triage with AI"},
                     {"name": "Team Invite Email", "subject": "Linear gets 3x better with your team", "timing": "Day 5", "goal": "Invite 3+ team members to workspace"},
                     {"name": "Case Study Email", "subject": "How Ramp's eng team ships 40% faster", "timing": "Day 7", "goal": "Conversion to paid plan or team expansion"}
                 ]
             }},
            {"channel": "Traditional PR", "score": 7, "effort": "medium", "timeline": "months", "budget": "$8K-20K",
             "specific_ideas": ["Pitch AI transforming software development", "Position founders as thought leaders"],
             "first_move": "Hire tech-focused PR agency, pitch '25,000 teams using AI' story",
             "why_or_why_not": "Important for credibility and enterprise sales",
             "killer_insight": "Pitch the broader AI development story with Linear as the example",
             "deep_dive": {
                 "research_type": "journalists",
                 "actions": [
                     {"title": "Pitch 'AI Development' Trend Story to TechCrunch", "description": "Pitch Frederic Lardinois with exclusive data: '25,000 teams now using AI-powered project management.' Offer internal metrics on how AI agents change sprint velocity. Tie to broader AI workplace narrative.", "expected_result": "TechCrunch feature article, 50K+ views, syndication to 5+ outlets"},
                     {"title": "Launch Founder Thought Leadership on LinkedIn", "description": "CEO publishes 2 LinkedIn articles/month on 'The Future of Human-AI Development Teams.' Share real data from Linear's usage. Tag relevant CTOs and VPs in comments. Goal: become THE voice on AI development workflows.", "expected_result": "10K+ LinkedIn followers in 6 months, 3-5 inbound press requests/month"},
                     {"title": "Create 'State of AI Development' Annual Report", "description": "Survey 500+ engineering leaders. Publish findings as definitive industry report. Distribute to press before public release. Every journalist covering AI gets an exclusive data point.", "expected_result": "50+ press mentions, 10K downloads, annual tradition that builds authority"}
                 ],
                 "research": [
                     {"name": "Frederic Lardinois", "outlet": "TechCrunch", "beat": "Developer tools, enterprise software", "recent_article": "How AI is reshaping the software development lifecycle", "twitter": "@fredericl", "relevance": "Covers exactly this space, has written about Linear before"},
                     {"name": "Tom Dotan", "outlet": "The Information", "beat": "Enterprise AI, SaaS", "recent_article": "The next wave of AI-native enterprise tools", "twitter": "@tomdotan", "relevance": "Deep enterprise AI coverage, influential with investors"},
                     {"name": "Kali Hays", "outlet": "Business Insider", "beat": "Tech industry, AI tools", "recent_article": "Companies racing to add AI to every workflow", "twitter": "@kalihays", "relevance": "Covers AI tools for broad business audience"},
                     {"name": "Anna Googin", "outlet": "The Verge", "beat": "Developer tools, productivity", "recent_article": "The developer tools transforming how teams ship code", "twitter": "@annagoogin", "relevance": "Developer-focused tech coverage with mainstream reach"},
                     {"name": "Connie Loizos", "outlet": "StrictlyVC / TechCrunch", "beat": "Startups, venture capital", "recent_article": "The hottest enterprise AI startups of 2026", "twitter": "@cookie", "relevance": "Key for fundraising narratives and investor attention"}
                 ]
             }},
            {"channel": "Business Development", "score": 7, "effort": "high", "timeline": "months", "budget": "$10K-25K",
             "specific_ideas": ["Partner with Cursor/GitHub Copilot", "Joint go-to-market with Figma"],
             "first_move": "Negotiate partnership with Cursor for bundled AI workflow",
             "why_or_why_not": "High potential but requires relationship building",
             "killer_insight": "Focus on partnerships that expand into non-technical roles",
             "deep_dive": {
                 "research_type": "partners",
                 "actions": [
                     {"title": "Launch Cursor + Linear Integration Bundle", "description": "Build deep integration where Cursor can create/update Linear issues directly from the IDE. Co-market as 'The AI Development Stack.' Joint blog post, shared landing page, cross-promotion to both user bases.", "expected_result": "Access to Cursor's 500K+ user base, 5K new signups from co-marketing"},
                     {"title": "Figma Design-to-Issue Pipeline", "description": "Build a Figma plugin that converts design specs directly into Linear issues with AI-generated acceptance criteria. Co-announce with Figma. Target design teams who influence PM tool choice.", "expected_result": "10K plugin installs, opens door to design-led organizations"},
                     {"title": "Y Combinator Portfolio Deal", "description": "Negotiate a portfolio-wide deal with YC: all current batch companies get Linear free for 12 months. In exchange, Linear is featured in the YC recommended stack. Target the 400+ companies per batch.", "expected_result": "200+ YC company adoptions per batch, long-term enterprise pipeline as these startups scale"}
                 ],
                 "research": [
                     {"name": "Cursor", "type": "Integration", "audience": "500K+ developers", "fit": "AI-native IDE + AI-native PM = the default AI dev stack. Deepest strategic fit."},
                     {"name": "Figma", "type": "Integration", "audience": "3M+ designers", "fit": "Design-dev handoff is broken everywhere. Linear can own this workflow."},
                     {"name": "Vercel", "type": "Co-marketing", "audience": "1M+ developers", "fit": "Same audience, complementary products. Joint webinars and case studies."},
                     {"name": "Y Combinator", "type": "Distribution", "audience": "400+ startups/batch", "fit": "Seed the next generation of fast-growing companies on Linear from day 1."},
                     {"name": "Anthropic/Claude", "type": "AI Partnership", "audience": "Growing rapidly", "fit": "Power Linear's AI agents with Claude. Co-develop AI workflow features."}
                 ]
             }},
            {"channel": "Webinars & Online Events", "score": 7, "effort": "medium", "timeline": "weeks", "budget": "$3K-8K",
             "specific_ideas": ["Monthly 'AI Development Workshop'", "Executive briefings", "Joint webinars with Figma/GitHub"],
             "first_move": "Launch monthly 'AI Development Masterclass' webinar series",
             "why_or_why_not": "Good for lead generation and explaining AI value",
             "killer_insight": "Focus on education rather than pitching",
             "deep_dive": {
                 "research_type": "conferences",
                 "actions": [
                     {"title": "Launch Monthly 'AI Dev Masterclass' Webinar", "description": "60-min webinar: 30 min teaching, 15 min live demo, 15 min Q&A. Topics rotate monthly: AI sprint planning, automated bug triage, AI code review workflows. Promote via LinkedIn + email. Record for YouTube.", "expected_result": "200+ live attendees/month, 1K+ YouTube views per recording, 50 qualified leads/month"},
                     {"title": "Executive Briefing Series for CTOs", "description": "Invite-only 30-min sessions for engineering leaders at target accounts. Share industry benchmarks on AI adoption. Position as peer-to-peer, not a sales pitch. 10 CTOs per session, monthly.", "expected_result": "Build relationships with 30+ enterprise decision makers in 90 days"},
                     {"title": "Co-Hosted Workshop with Figma on Design-Dev Handoff", "description": "Joint 90-min workshop showing end-to-end flow: design in Figma -> auto-generate Linear issues -> AI-assigned sprint -> shipped code. Both companies promote to their audiences.", "expected_result": "500+ registrations, access to Figma's audience, 100+ new signups"}
                 ],
                 "research": [
                     {"name": "AI Dev Masterclass #1: Sprint Planning", "date": "Apr 2026", "location": "Virtual (Zoom)", "cost": "$500 (Zoom license + promotion)", "audience": "Engineering managers, tech leads", "fit": "Highest-intent topic — everyone wants to improve sprint planning"},
                     {"name": "CTO Roundtable: AI Adoption Benchmarks", "date": "May 2026", "location": "Virtual (invite-only)", "cost": "$200 (platform only)", "audience": "CTOs, VPs Eng at 200+ person companies", "fit": "Peer learning format builds trust faster than any sales call"},
                     {"name": "Figma x Linear: Design-to-Ship Workshop", "date": "Jun 2026", "location": "Virtual (co-hosted)", "cost": "$1K (shared with Figma)", "audience": "Design + engineering teams", "fit": "Cross-functional audience expands Linear beyond engineering"},
                     {"name": "AI Dev Masterclass #2: Automated Bug Triage", "date": "Jul 2026", "location": "Virtual (Zoom)", "cost": "$500", "audience": "Senior engineers, QA leads", "fit": "High pain point — bug triage is universally hated"}
                 ]
             }},
            {"channel": "Social Media Marketing", "score": 6, "effort": "medium", "timeline": "weeks", "budget": "$2K-5K",
             "specific_ideas": ["Twitter threads showing AI agents in action", "LinkedIn content for CTOs"],
             "first_move": "Start weekly Twitter threads showcasing customer AI workflows",
             "why_or_why_not": "Good for brand building, won't drive immediate enterprise sales",
             "killer_insight": "Twitter for developers, LinkedIn for executives — don't spread thin",
             "deep_dive": {
                 "research_type": "influencers",
                 "actions": [
                     {"title": "Weekly 'AI Workflow Showcase' Twitter Threads", "description": "Every Tuesday, post a thread showing a real customer's AI workflow: before/after, screenshots, metrics. Tag the customer. Use @LinearApp account. Aim for 3-5 threads before repurposing best ones as LinkedIn articles.", "expected_result": "2-3 threads go semi-viral (500+ likes), 1K new followers/month, steady inbound from developers"},
                     {"title": "LinkedIn Thought Leadership for CTOs", "description": "CEO posts 3x/week on LinkedIn: 1 data insight, 1 industry take, 1 customer story. Focus on AI transformation metrics that CTOs care about. Comment strategy on 10 relevant posts/day to build visibility.", "expected_result": "15K+ LinkedIn followers in 6 months, 5+ inbound enterprise leads/month from LinkedIn"},
                     {"title": "Launch 'Linear Ships' Changelog Content", "description": "Every product release gets a mini-launch on Twitter: 30-sec video demo, GIF, or screenshot. Make the changelog itself entertaining. Build anticipation for releases like a game studio.", "expected_result": "Each launch tweet gets 200+ retweets, builds FOMO among non-users"}
                 ],
                 "research": [
                     {"name": "Guillermo Rauch", "platform": "Twitter", "url": "https://twitter.com/raaboron", "audience": "250K+", "engagement": "High", "relevance": "Vercel CEO, massive dev influence, frequently discusses dev tools and AI workflows"},
                     {"name": "Theo Browne", "platform": "YouTube/Twitter", "url": "https://twitter.com/t3dotgg", "audience": "400K+", "engagement": "Very High", "relevance": "Most influential dev content creator. A Linear review from him would reach entire dev community"},
                     {"name": "Lenny Rachitsky", "platform": "Substack/LinkedIn", "url": "https://twitter.com/lennysan", "audience": "700K+", "engagement": "High", "relevance": "Product management authority. Feature in his newsletter reaches every PM decision maker"},
                     {"name": "Swyx (Shawn Wang)", "platform": "Twitter", "url": "https://twitter.com/swyx", "audience": "120K+", "engagement": "High", "relevance": "AI engineering thought leader. Perfect for AI-native PM positioning"},
                     {"name": "Kent C. Dodds", "platform": "Twitter/YouTube", "url": "https://twitter.com/kentcdodds", "audience": "300K+", "engagement": "High", "relevance": "Respected senior dev. His tool recommendations carry weight with engineering teams"}
                 ]
             }},
            {"channel": "Influencer Marketing", "score": 6, "effort": "medium", "timeline": "weeks", "budget": "$5K-15K",
             "specific_ideas": ["Partner with developer YouTubers", "Sponsor dev newsletters"],
             "first_move": "Reach out to top 10 developer YouTube channels",
             "why_or_why_not": "Effective for awareness, hard to measure direct impact",
             "killer_insight": "Focus on productivity/AI influencers, not generic tech reviewers",
             "deep_dive": {
                 "research_type": "influencers",
                 "actions": [
                     {"title": "Sponsor Top 10 Developer YouTube Channels", "description": "Identify 10 dev YouTubers (50K-500K subs) who cover productivity and AI tools. Offer $2K-5K per sponsored video where they use Linear for a real project. Provide custom demo environment with pre-loaded AI features.", "expected_result": "500K+ combined views, 2-5K signups with tracked referral codes, lasting content assets"},
                     {"title": "Newsletter Sponsorship Blitz", "description": "Sponsor 5 developer newsletters simultaneously for 1 month. Coordinate messaging: same week, same campaign, different angles per audience. Track with unique landing pages per newsletter.", "expected_result": "200K+ email impressions, 1-3K clicks, 500+ signups. A/B test which newsletter converts best"},
                     {"title": "Micro-Influencer Seeding Program", "description": "Send Linear Pro to 100 developers with 1K-10K Twitter followers. No ask. Just give them the product. 20-30% will naturally tweet about it. The organic mentions are more valuable than paid ones.", "expected_result": "30+ organic mentions from respected developers, authentic word-of-mouth"}
                 ],
                 "research": [
                     {"name": "Theo Browne (t3.gg)", "platform": "YouTube", "url": "https://youtube.com/@t3dotgg", "audience": "420K subs", "engagement": "8-12%", "relevance": "Most influential dev YouTuber. Single video could drive 5K+ signups. Covers AI tools regularly."},
                     {"name": "Fireship", "platform": "YouTube", "url": "https://youtube.com/@fireship", "audience": "2.5M subs", "engagement": "5-7%", "relevance": "Massive reach with 100-word-a-minute dev content. Perfect for snappy Linear AI demo."},
                     {"name": "Traversy Media", "platform": "YouTube", "url": "https://youtube.com/@traversymedia", "audience": "2.2M subs", "engagement": "3-5%", "relevance": "Covers full-stack dev tools. Great for project management workflow tutorials."},
                     {"name": "James Q Quick", "platform": "YouTube", "url": "https://youtube.com/@jamesqquick", "audience": "250K subs", "engagement": "6-8%", "relevance": "Productivity-focused dev content. Perfect fit for Linear's workflow angle."},
                     {"name": "TLDR Newsletter", "platform": "Newsletter", "url": "https://tldr.tech", "audience": "1.2M subscribers", "engagement": "40% open rate", "relevance": "Largest dev newsletter. One placement reaches more devs than any other single channel."},
                     {"name": "Bytes.dev", "platform": "Newsletter", "url": "https://bytes.dev", "audience": "220K subscribers", "engagement": "45% open rate", "relevance": "JavaScript-focused newsletter. High engagement, dev-tool friendly audience."},
                     {"name": "Pointer.io", "platform": "Newsletter", "url": "https://pointer.io", "audience": "35K subscribers", "engagement": "50% open rate", "relevance": "Curated for senior engineers. Small but extremely high-quality audience."}
                 ]
             }},
            {"channel": "Unconventional Marketing", "score": 6, "effort": "medium", "timeline": "weeks", "budget": "$3K-10K",
             "specific_ideas": ["'Productivity Olympics' comparing human vs AI+human teams", "Public real-time AI metrics dashboard"],
             "first_move": "Launch public leaderboard of AI collaboration metrics",
             "why_or_why_not": "Could create buzz if executed well",
             "killer_insight": "Make AI capabilities tangible and visible",
             "deep_dive": {
                 "research_type": "stunts",
                 "actions": [
                     {"title": "Launch 'AI vs Human Sprint Challenge'", "description": "Live-stream a sprint planning challenge: one team uses traditional tools, one uses Linear AI. Same project, same timeline, public scoreboard. Let Twitter vote on predictions. Document everything.", "expected_result": "50K+ live viewers, trending on dev Twitter, 20+ press pickups from the spectacle"},
                     {"title": "Public Real-Time AI Metrics Dashboard", "description": "Launch a public page showing aggregate Linear AI metrics in real-time: issues auto-triaged, sprints auto-planned, bugs auto-categorized. Updated live. Make it a spectacle of scale.", "expected_result": "Becomes a reference point journalists cite. 'Linear's AI processes 50K issues/day.' Ongoing PR asset."},
                     {"title": "Billboard in SOMA: 'Your Jira Board is Crying'", "description": "Put a single billboard near SOMA/FiDi in San Francisco showing a sad Jira board with the tagline 'There's a better way.' QR code to Linear. Photo the billboard, post on Twitter. The tweet goes further than the billboard.", "expected_result": "Tweet of the billboard gets 100K+ impressions. Cost: $500 for a week. ROI: priceless meme potential."}
                 ],
                 "research": [
                     {"name": "AI vs Human Sprint Challenge", "budget": "$3K (streaming setup + prizes)", "virality": "9/10", "risk": "Medium", "description": "Live competition format. Risk: AI team could lose, but that's actually fine — the narrative becomes 'AI is a tool, not a replacement.' Either outcome is good press."},
                     {"name": "Public Metrics Dashboard", "budget": "$1K (hosting + design)", "virality": "6/10", "risk": "Low", "description": "Always-on PR asset. Journalists can reference it anytime. Compounds in value over time. Low effort to maintain."},
                     {"name": "Guerrilla Billboard in SOMA", "budget": "$500-2K", "virality": "8/10", "risk": "Low", "description": "The photo of the billboard > the billboard itself. Target SF tech neighborhoods. Jira-bashing is universally popular among devs."},
                     {"name": "Open-Source Linear's Design System", "budget": "$2K (documentation time)", "virality": "7/10", "risk": "Low", "description": "Linear's design is universally admired. Open-sourcing the design system generates massive goodwill + GitHub stars + press coverage."}
                 ]
             }},
            {"channel": "Viral Marketing", "score": 5, "effort": "low", "timeline": "weeks", "budget": "$1K-3K",
             "specific_ideas": ["Shareable demos of AI agents fixing bugs", "AI Development Challenge with leaderboards"],
             "first_move": "Create shareable widget showing team's AI development stats",
             "why_or_why_not": "Linear isn't naturally viral, but AI demos could be",
             "killer_insight": "Make AI workflows so impressive developers want to show them off",
             "deep_dive": {
                 "research_type": "free_tools",
                 "actions": [
                     {"title": "Shareable 'AI Dev Stats' Widget", "description": "Each team gets a public stats page: issues AI-triaged, time saved, sprint accuracy. Embed widget for README.md or team pages. Like GitHub's contribution graph but for AI-powered development.", "expected_result": "Teams share their stats on Twitter/LinkedIn. Each share = organic exposure. 5K embeds in 90 days."},
                     {"title": "AI Bug Triage Demo Generator", "description": "Public tool: paste any GitHub issue URL, watch Linear's AI triage it in real-time (classify, assign priority, suggest fix, estimate effort). Shareable output. No signup required for first 3 uses.", "expected_result": "Goes viral in dev communities. 10K+ uses in first week. 15% convert to signup."},
                     {"title": "'Dev Team Wrapped' Annual Summary", "description": "Like Spotify Wrapped but for development teams. Year-end summary: total issues shipped, AI time saved, most productive sprint, team MVP. Beautiful, shareable cards. Released every December.", "expected_result": "Every team shares their Wrapped on social media. Massive annual viral moment. 50K+ shares."}
                 ],
                 "research": [
                     {"name": "AI Dev Stats Widget", "effort": "2 weeks", "viral_potential": "8/10", "conversion": "Users embed widget -> visitors click -> discover Linear -> signup. Passive viral loop."},
                     {"name": "AI Bug Triage Demo", "effort": "1 week", "viral_potential": "9/10", "conversion": "Paste GitHub URL -> see AI in action -> want it for your team -> signup. Direct product demo as marketing."},
                     {"name": "Dev Team Wrapped", "effort": "3 weeks (once/year)", "viral_potential": "10/10", "conversion": "Annual event creates urgency. Teams need to be on Linear all year to get their Wrapped. Retention + viral."}
                 ]
             }},
            {"channel": "Trade Shows", "score": 5, "effort": "high", "timeline": "months", "budget": "$20K-40K",
             "specific_ideas": ["Exhibit at GitHub Universe, AWS re:Invent", "Interactive AI demos for booth visitors"],
             "first_move": "Book booth space at next GitHub Universe",
             "why_or_why_not": "Expensive but good for enterprise relationships",
             "killer_insight": "Focus on developer-heavy conferences, not general business shows",
             "deep_dive": {
                 "research_type": "conferences",
                 "actions": [
                     {"title": "Sponsor GitHub Universe 2026", "description": "Book a premium booth with interactive AI demo stations. Attendees try Linear's AI agent on their own repos. Collect emails for follow-up. Host VIP dinner night before for top 50 enterprise prospects.", "expected_result": "300+ qualified leads, 15 enterprise pilot signups, press coverage from live demos"},
                     {"title": "Developer Lounge at AWS re:Invent", "description": "Skip the expensive booth. Instead, rent a lounge space near the venue. Free coffee + charging stations + live AI workflow demos. Lower cost, higher quality conversations.", "expected_result": "150+ deep conversations with engineering leaders, 50% cheaper than a booth"},
                     {"title": "Speaking Circuit Strategy", "description": "Submit CFPs to 15 conferences. Target 'AI in engineering' track. Use talk as lead gen: every attendee gets free trial link. Record for YouTube content.", "expected_result": "5-8 accepted talks, 2,000+ total attendees, evergreen video content"}
                 ],
                 "research": [
                     {"name": "GitHub Universe 2026", "date": "Oct 29-30, 2026", "location": "San Francisco, CA", "cost": "$8K-25K booth", "audience": "10,000+ developers & engineering leaders", "fit": "Core audience overlap — GitHub users are Linear's primary market"},
                     {"name": "AWS re:Invent 2026", "date": "Dec 2-6, 2026", "location": "Las Vegas, NV", "cost": "$15K-40K booth", "audience": "60,000+ cloud & DevOps engineers", "fit": "Massive scale, enterprise buyers, AI/ML track growing fast"},
                     {"name": "KubeCon NA 2026", "date": "Nov 2026", "location": "Salt Lake City, UT", "cost": "$5K-15K sponsor", "audience": "12,000+ platform engineers", "fit": "Infrastructure teams that influence tooling decisions across orgs"},
                     {"name": "AI Engineer World's Fair", "date": "Jun 2026", "location": "San Francisco, CA", "cost": "$5K-20K booth", "audience": "5,000+ AI engineers", "fit": "Exact audience for AI-native workflow positioning"},
                     {"name": "DevOpsDays (Multiple Cities)", "date": "Year-round (Global)", "location": "50+ cities worldwide", "cost": "$1K-5K per city", "audience": "200-500 per event", "fit": "Affordable, intimate, high-quality networking with decision makers"},
                     {"name": "QCon London 2026", "date": "Apr 2026", "location": "London, UK", "cost": "$3K-10K sponsor", "audience": "1,500+ senior engineers", "fit": "European enterprise market, senior decision-makers"},
                     {"name": "PlatformCon 2026", "date": "Jun 2026", "location": "Virtual", "cost": "$2K-5K sponsor", "audience": "20,000+ platform engineers", "fit": "Virtual = low cost, massive reach, platform engineering audience"}
                 ]
             }},
            {"channel": "Affiliate Marketing", "score": 4, "effort": "medium", "timeline": "months", "budget": "$2K-5K",
             "specific_ideas": ["Partner with dev consultants", "Productivity review sites"],
             "first_move": "Pilot affiliate program with 5 development consultants",
             "why_or_why_not": "Not natural for B2B — most evaluate tools themselves",
             "killer_insight": "Focus on consultants/agencies, not traditional affiliates",
             "deep_dive": {
                 "research_type": "affiliates",
                 "actions": [
                     {"title": "Launch Dev Consultant Partner Program", "description": "Recruit 20 development consultants and agencies who help startups set up their tech stack. Offer 25% recurring commission for 12 months on every team they refer. Provide co-branded onboarding materials and priority support for their clients.", "expected_result": "20 active partners, 50+ referred teams in 6 months, $30K+ attributed revenue"},
                     {"title": "Newsletter Sponsorship Affiliate Program", "description": "Offer newsletter writers a unique referral link instead of a flat sponsorship fee. Pay $10 per signup + 15% of first year revenue. More aligned incentives than flat CPM sponsorships.", "expected_result": "10 newsletter partners, performance-based spending, 3x better ROI than flat sponsorships"},
                     {"title": "User Referral Program", "description": "Give every paid user a referral link. Refer a team, both get one month free. Simple, viral, built into the product. Show referral stats in settings dashboard.", "expected_result": "15% of new signups from referrals within 6 months, near-zero CAC on referred users"}
                 ],
                 "research": [
                     {"name": "Theo Browne (t3.gg)", "platform": "YouTube", "url": "https://youtube.com/@t3dotgg", "audience": "420K subs", "type": "Creator", "commission": "Per-video sponsorship ($3-5K) + affiliate link for ongoing attribution"},
                     {"name": "TLDR Newsletter", "platform": "Newsletter", "url": "https://tldr.tech", "audience": "1.2M subscribers", "type": "Newsletter", "commission": "CPA model: $10/signup + 15% rev share on conversions"},
                     {"name": "Bytes.dev", "platform": "Newsletter", "url": "https://bytes.dev", "audience": "220K subscribers", "type": "Newsletter", "commission": "CPA model: $8/signup, JavaScript-focused dev audience"},
                     {"name": "ThoughtBot", "platform": "Agency", "url": "https://thoughtbot.com", "audience": "500+ clients/year", "type": "Consultancy", "commission": "25% recurring for 12 months on referred teams"},
                     {"name": "Pointer.io", "platform": "Newsletter", "url": "https://pointer.io", "audience": "35K subscribers", "type": "Newsletter", "commission": "CPA model: $15/signup, senior engineer audience = high LTV"},
                     {"name": "DevOps Institute", "platform": "Community", "url": "https://devopsinstitute.com", "audience": "50K+ members", "type": "Education", "commission": "Revenue share on certified professional referrals"}
                 ]
             }}
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


# ═══════════════════════════════════════════════
# TESTSTREAM — Simulated streaming dashboard demo
# ═══════════════════════════════════════════════

# Track when each teststream session started (for time-based data release)
_teststream_starts: dict[str, float] = {}

@app.get("/teststream", response_class=HTMLResponse)
async def test_stream_page(request: Request, tier: str = "free"):
    """Streaming demo — shows how the dashboard fills in progressively.
    Uses mock data released on a timer to simulate real LLM analysis."""
    import time
    session_id = f"teststream-{int(time.time()*1000)}"
    _teststream_starts[session_id] = time.time()
    # Render dashboard with skeleton data + streaming enabled
    skeleton = {
        "company_profile": {
            "name": "Linear",
            "one_liner": "AI-powered project management for modern product teams",
            "stage": "scaling",
            "estimated_size": "medium (6-20)",
            "market": "Product development teams at tech companies",
        },
        "top_3_channels": [
            {"channel": "Developer Communities", "score": 10},
            {"channel": "Content Marketing", "score": 9},
            {"channel": "Partnerships & Integrations", "score": 9},
        ],
        "hot_take": "Linear is the best PM tool nobody outside of tech has heard of. Fix that.",
        "executive_summary": "",
        "channel_analysis": [],
        "bullseye_ranking": {},
        "ninety_day_plan": {},
        "budget_allocation": {},
        "risk_matrix": [],
        "competitive_moat": "",
        "leads_research": {},
        "investor_research": {},
        "_phase": "skeleton",
    }
    html = render_dashboard_v5(
        analysis=skeleton,
        startup_name="Linear",
        report_id=session_id,
        tier=tier,
        checkout_url="#pricing",
        upgrade_url="#pricing",
        logged_in=True,
        login_url="#",
        streaming=True,
        sse_base_url="",
    )
    return HTMLResponse(content=html)


@app.get("/report/{report_id}/progress")
async def poll_deep_progress_handler(request: Request, report_id: str):
    """Handles both real report progress AND teststream mock progress."""
    import time as _time

    # ---- TESTSTREAM MOCK MODE ----
    if report_id.startswith("teststream-"):
        start = _teststream_starts.get(report_id)
        if not start:
            start = _time.time()
            _teststream_starts[report_id] = start
        elapsed = _time.time() - start
        mock = _mock_analysis()

        all_channels = sorted(
            mock.get("channel_analysis", []),
            key=lambda c: c.get("score", 0), reverse=True
        )
        all_personas = mock.get("leads_research", {}).get("personas", [])
        all_leads = mock.get("leads_research", {}).get("leads", [])
        all_competitors = mock.get("investor_research", {}).get("competitors", [])
        all_investors = (
            mock.get("investor_research", {}).get("competitor_investors", [])
            + mock.get("investor_research", {}).get("market_investors", [])
        )

        # Timeline:
        #   0-1s:   "Connecting..."
        #   1-20s:  channels drip in (1 per second)
        #   20-22s: channels_meta (bullseye, summary, hot_take)
        #   22-25s: personas (1 per second)
        #   25-35s: leads drip in (1 per second)
        #   35-40s: competitors drip in (1 per second)
        #   40-50s: investors drip in (1 per second)
        #   50-52s: strategy section
        #   52s+:   complete

        result: dict = {
            "status": "starting",
            "channels": [],
            "personas": [],
            "leads": [],
            "competitors": [],
            "investors": [],
            "sections": {},
        }

        if elapsed < 1:
            result["status"] = "Connecting to analysis engine..."
            return JSONResponse(result)

        # Channels: 1 per second starting at t=1
        ch_count = min(len(all_channels), max(0, int(elapsed - 1)))
        result["channels"] = all_channels[:ch_count]
        if ch_count < len(all_channels):
            result["status"] = f"Analyzing growth channels... ({ch_count}/{len(all_channels)})"
        else:
            result["status"] = "Channels complete. Searching for leads..."

        # Channels meta at t=20
        if elapsed >= 20:
            result["sections"]["channels_meta"] = {
                "bullseye_ranking": mock.get("bullseye_ranking", {}),
                "executive_summary": mock.get("executive_summary", ""),
                "hot_take": mock.get("hot_take", ""),
                "company_profile": mock.get("company_profile", {}),
            }

        # Personas: 1 per second starting at t=22
        if elapsed >= 22:
            p_count = min(len(all_personas), max(0, int(elapsed - 22)))
            result["personas"] = all_personas[:p_count]

        # Leads: 1 per second starting at t=25
        if elapsed >= 25:
            l_count = min(len(all_leads), max(0, int(elapsed - 25)))
            result["leads"] = all_leads[:l_count]
            if l_count < len(all_leads):
                result["status"] = f"Finding potential leads... ({l_count}/{len(all_leads)})"
            else:
                result["sections"]["leads_complete"] = {"count": len(all_leads)}

        # Competitors: 1 per second starting at t=35
        if elapsed >= 35:
            c_count = min(len(all_competitors), max(0, int(elapsed - 35)))
            result["competitors"] = all_competitors[:c_count]
            if c_count > 0:
                result["status"] = f"Analyzing competitors... ({c_count}/{len(all_competitors)})"

        # Investors: 1 per second starting at t=40
        if elapsed >= 40:
            i_count = min(len(all_investors), max(0, int(elapsed - 40)))
            result["investors"] = all_investors[:i_count]
            if i_count < len(all_investors):
                result["status"] = f"Discovering investors... ({i_count}/{len(all_investors)})"
            else:
                result["sections"]["investors_complete"] = {"count": len(all_investors)}

        # Strategy at t=50
        if elapsed >= 50:
            result["sections"]["strategy"] = {
                "ninety_day_plan": mock.get("ninety_day_plan", {}),
                "budget_allocation": mock.get("budget_allocation", {}),
                "risk_matrix": mock.get("risk_matrix", []),
                "competitive_moat": mock.get("competitive_moat", ""),
            }
            result["status"] = "Finalizing strategy..."

        # Complete at t=52
        if elapsed >= 52:
            result["status"] = "complete"

        return JSONResponse(result)

    # ---- REAL REPORT PROGRESS (original handler below) ----
    return await _real_poll_deep_progress(request, report_id)


@app.get("/testreport", response_class=HTMLResponse)
async def test_report(request: Request, tier: str = "free", gate: str = ""):
    """Test report with mock data. ?tier=free|starter|growth  ?gate=login to preview login overlay"""
    # Check real session cookie — behave like a real report page
    session_cookie = request.cookies.get("mckoutie_session")
    user = auth.get_session_user(session_cookie)
    is_logged_in = user is not None
    # Override with ?gate param for testing
    if gate == "login":
        is_logged_in = False
    elif gate == "skip":
        is_logged_in = True
    mock = _mock_analysis()
    html = render_dashboard_v5(
        analysis=mock,
        startup_name="Linear",
        report_id="test-mock-001",
        tier=tier,
        checkout_url="#pricing",
        upgrade_url="#pricing",
        logged_in=is_logged_in,
        login_url="/auth/twitter?redirect=/testreport",
    )
    return HTMLResponse(content=html)


@app.get("/test2", response_class=HTMLResponse)
async def test_report_v5(request: Request, tier: str = "free", gate: str = ""):
    """V5 dashboard — formal BI style. ?tier=free|starter|growth  ?gate=login to preview login overlay"""
    # Check real session cookie — behave like a real report page
    session_cookie = request.cookies.get("mckoutie_session")
    user = auth.get_session_user(session_cookie)
    is_logged_in = user is not None
    # Override with ?gate param for testing
    if gate == "login":
        is_logged_in = False
    elif gate == "skip":
        is_logged_in = True
    mock = _mock_analysis()
    html = render_dashboard_v5(
        analysis=mock,
        startup_name="Linear",
        report_id="test-mock-001",
        tier=tier,
        checkout_url="#pricing",
        upgrade_url="#pricing",
        logged_in=is_logged_in,
        login_url="/auth/twitter?redirect=/test2",
    )
    return HTMLResponse(content=html)


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def view_report(request: Request, report_id: str, paid: str | None = None):
    """View a report — dashboard with tier-based content gating.

    If the report is in 'skeleton' status and the user is logged in,
    the dashboard will connect to the SSE stream to receive live deep analysis.
    """
    cookie_keys = list(request.cookies.keys())
    raw_cookie_header = request.headers.get("cookie", "")
    logger.info(f"[REPORT VIEW] report_id={report_id}, cookies={cookie_keys}, raw_cookie_len={len(raw_cookie_header)}, has_session={'mckoutie_session' in raw_cookie_header}")
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

    # Check login status — try cookie first, then URL token param (OAuth redirect)
    session_cookie = request.cookies.get("mckoutie_session")
    user = auth.get_session_user(session_cookie)
    token_from_url = request.query_params.get("_token")
    set_cookie_token = None
    if user is None and token_from_url:
        # OAuth just redirected back with token in URL — verify it server-side
        user = auth.get_session_user(token_from_url)
        if user:
            set_cookie_token = token_from_url  # We'll set the cookie on the response
            logger.info(f"[REPORT VIEW] Authenticated via URL _token for @{user.get('username')}")
    logged_in = user is not None
    login_url = f"/auth/twitter?redirect={quote(f'/report/{report_id}')}"
    logger.info(f"[REPORT VIEW] report={report_id} logged_in={logged_in} cookie={'yes' if session_cookie else 'no'} token_url={'yes' if token_from_url else 'no'} user={user.get('username') if user else 'none'} phase={analysis.get('_phase', 'n/a')} record_status={record.status}")

    # Determine tier based on subscription status + ownership
    tier = "free"
    checkout_url = record.checkout_url or "#"
    upgrade_url = "#"

    if logged_in:
        user_twitter_id = user.get("twitter_id", "")
        is_owner = (
            user_twitter_id == record.author_id
            or user_twitter_id == record.subscriber_twitter_id
        )

        if is_owner and record.status in ("active", "paid"):
            tier = record.tier or "starter"
        elif is_owner:
            try:
                sub = db.get_subscription_for_report(report_id, user_twitter_id)
                if sub and sub.get("status") == "active":
                    tier = sub.get("tier", "starter")
            except Exception:
                pass

        if is_owner and tier == "starter" and settings.has_payments:
            upgrade_url = payments.create_upgrade_session(
                report_id=report_id,
                startup_name=record.startup_name,
                customer_id=record.customer_id,
            ) or "#"

    # If the report was created via /analyze (author_id="web"), claim it for this user
    if logged_in and record.author_id == "web":
        user_twitter_id = user.get("twitter_id", "")
        record.author_id = user_twitter_id
        record.author_username = user.get("username", "web")
        report_store.save_record(record)
        try:
            db.update_report(report_id, author_twitter_id=user_twitter_id, author_username=user.get("username", ""))
        except Exception:
            pass
        logger.info(f"[REPORT VIEW] Claimed web report {report_id} for @{user.get('username')}")

    # Determine if this is a skeleton report that needs deep analysis
    is_skeleton = analysis.get("_phase") == "skeleton" or record.status == "skeleton"

    # Detect "complete but empty" — deep analysis ran but channels/leads were empty.
    # This happens when the LLM returned a malformed response or enrichment failed.
    channels_count = len(analysis.get("channel_analysis", []))
    leads_count = len(analysis.get("leads_research", {}).get("leads", []))
    investors_count = len(analysis.get("investor_research", {}).get("competitors", []))
    is_complete_but_empty = (
        analysis.get("_phase") == "complete"
        and (channels_count == 0 or (leads_count == 0 and investors_count == 0))
    )
    if is_complete_but_empty:
        logger.warning(f"[REPORT VIEW] Report {report_id} is 'complete' but incomplete data (ch={channels_count} leads={leads_count} inv={investors_count}) — resetting to skeleton for re-analysis")
        analysis["_phase"] = "skeleton"
        is_skeleton = True
        # Save the reset phase so the SSE endpoint also sees it
        analysis_path = REPORTS_DIR / report_id / "analysis.json"
        try:
            analysis_path.write_text(json.dumps(analysis))
        except Exception as e:
            logger.error(f"Failed to reset analysis phase: {e}")

    # Show streaming UI for skeleton reports (analysis starts on first JS poll, not here).
    # This prevents Twitter card unfurlers / bots from triggering expensive analysis.
    should_stream = is_skeleton or is_deep_analysis_running(report_id)

    if is_skeleton:
        logger.info(f"[REPORT VIEW] Skeleton report {report_id} — streaming={should_stream} logged_in={logged_in} deep_running={is_deep_analysis_running(report_id)}. Analysis deferred to first poll.")

    # Render the dashboard — with streaming flag for skeleton reports
    # SSE connects DIRECTLY to Railway (bypasses Vercel proxy which kills long-lived connections)
    html = render_dashboard_v5(
        analysis=analysis,
        startup_name=record.startup_name,
        report_id=report_id,
        tier=tier,
        checkout_url=checkout_url,
        upgrade_url=upgrade_url,
        logged_in=logged_in,
        login_url=login_url,
        streaming=should_stream,
        sse_base_url=settings.railway_public_url if should_stream else "",
    )
    response = HTMLResponse(content=html)
    # If we authenticated via URL token, set the cookie so future requests don't need the token
    if set_cookie_token:
        response.set_cookie(
            "mckoutie_session",
            set_cookie_token,
            max_age=30 * 24 * 3600,
            httponly=False,
            secure=True,
            samesite="lax",
            path="/",
        )
    return response


@app.get("/report/{report_id}/debug")
async def debug_report(request: Request, report_id: str):
    """Debug endpoint to inspect report state."""
    record = report_store.load_record(report_id)
    analysis_path = REPORTS_DIR / report_id / "analysis.json"
    analysis = {}
    if analysis_path.exists():
        try:
            analysis = json.loads(analysis_path.read_text())
        except Exception:
            pass

    session_cookie = request.cookies.get("mckoutie_session")
    user = auth.get_session_user(session_cookie)

    return JSONResponse({
        "report_id": report_id,
        "record_exists": record is not None,
        "record_status": record.status if record else None,
        "record_author_id": record.author_id if record else None,
        "analysis_exists": analysis_path.exists(),
        "analysis_phase": analysis.get("_phase"),
        "analysis_has_startup_data": bool(analysis.get("_startup_data")),
        "has_cookie": bool(session_cookie),
        "cookie_valid": user is not None,
        "user": user.get("username") if user else None,
        "is_skeleton": analysis.get("_phase") == "skeleton" or (record.status == "skeleton" if record else False),
        "deep_running": is_deep_analysis_running(report_id),
    })


@app.get("/report/{report_id}/stream")
async def stream_deep_analysis(request: Request, report_id: str):
    """True SSE endpoint — streams analysis events in real-time.

    If analysis isn't running yet, starts it and streams events directly.
    If analysis is already running (e.g. reconnect), starts a background task
    and polls _deep_progress so client still gets updates.
    """
    logger.info(f"[SSE] Stream request for {report_id}")
    record = report_store.load_record(report_id)
    if not record:
        return JSONResponse({"error": "Report not found"}, status_code=404)

    # Check if report is already complete
    analysis_path = REPORTS_DIR / report_id / "analysis.json"
    if analysis_path.exists():
        try:
            analysis = json.loads(analysis_path.read_text())
            if analysis.get("_phase") == "complete":
                async def done_gen():
                    yield {"event": "already_complete", "data": json.dumps({})}
                return EventSourceResponse(done_gen())
        except Exception:
            pass

    # ALWAYS use background task to drive the analysis.
    # SSE streams progress FROM the background task via _deep_progress.
    # This way even if SSE drops (Vercel proxy buffering), polling still works.
    if not is_deep_analysis_running(report_id):
        logger.info(f"[SSE] Starting background analysis for {report_id}")
        asyncio.create_task(run_deep_analysis_background(report_id))
        # Wait for the progress dict to be initialized before streaming
        for _ in range(20):  # up to 2s
            await asyncio.sleep(0.1)
            if get_deep_progress(report_id):
                break
    else:
        logger.info(f"[SSE] Analysis already running for {report_id}, streaming progress")

    # Stream progress from _deep_progress dict (populated by background task)
    async def progress_stream():
        emitted_channels = 0
        emitted_personas = 0
        emitted_leads = 0
        emitted_competitors = 0
        emitted_investors = 0
        last_status = ""
        emitted_sections = set()
        heartbeat_count = 0

        yield {"event": "thinking", "data": json.dumps({"message": "Deep analysis starting...", "detail": ""})}

        while True:
            if await request.is_disconnected():
                logger.info(f"[SSE] Client disconnected for {report_id} (analysis continues in background)")
                break

            progress = get_deep_progress(report_id)
            if not progress:
                heartbeat_count += 1
                # Send keepalive comment every 5 seconds to prevent proxy/browser timeout
                if heartbeat_count % 5 == 0:
                    yield {"comment": "keepalive"}
                await asyncio.sleep(1)
                continue

            status = progress.get("status", "")

            # Send periodic heartbeat thinking events to keep connection alive
            heartbeat_count += 1
            if heartbeat_count % 10 == 0 and not status.startswith("complete") and not status.startswith("error"):
                elapsed_min = heartbeat_count // 60
                elapsed_sec = heartbeat_count % 60
                yield {"event": "thinking", "data": json.dumps({"message": f"Analyzing... ({elapsed_min}m {elapsed_sec}s elapsed)", "detail": "Deep research in progress — this takes 2-4 minutes for thorough analysis"})}

            # Stream status/thinking updates
            if status and status != last_status:
                yield {"event": "thinking", "data": json.dumps({"message": status, "detail": ""})}
                last_status = status

            # Stream channels one by one
            p_channels = progress.get("channels", [])
            while emitted_channels < len(p_channels):
                ch = p_channels[emitted_channels]
                yield {"event": "channel", "data": json.dumps({"index": emitted_channels, "channel": ch})}
                emitted_channels += 1
                await asyncio.sleep(0.05)

            # Stream channels_meta section when available
            sections = progress.get("sections", {})
            if "channels_meta" in sections and "channels_meta" not in emitted_sections:
                yield {"event": "section", "data": json.dumps({"section": "channels_meta", "payload": sections["channels_meta"]})}
                emitted_sections.add("channels_meta")

            # Stream personas one by one
            p_personas = progress.get("personas", [])
            while emitted_personas < len(p_personas):
                p = p_personas[emitted_personas]
                yield {"event": "persona", "data": json.dumps({"index": emitted_personas, "persona": p})}
                emitted_personas += 1
                await asyncio.sleep(0.05)

            # Stream leads one by one
            p_leads = progress.get("leads", [])
            while emitted_leads < len(p_leads):
                l = p_leads[emitted_leads]
                yield {"event": "lead", "data": json.dumps({"index": emitted_leads, "lead": l})}
                emitted_leads += 1
                await asyncio.sleep(0.05)

            # Stream competitors one by one
            p_competitors = progress.get("competitors", [])
            while emitted_competitors < len(p_competitors):
                c = p_competitors[emitted_competitors]
                yield {"event": "competitor", "data": json.dumps({"index": emitted_competitors, "competitor": c})}
                emitted_competitors += 1
                await asyncio.sleep(0.05)

            # Stream investors one by one
            p_investors = progress.get("investors", [])
            while emitted_investors < len(p_investors):
                inv = p_investors[emitted_investors]
                yield {"event": "investor", "data": json.dumps({"index": emitted_investors, "investor": inv})}
                emitted_investors += 1
                await asyncio.sleep(0.05)

            # Stream leads_complete / investors_complete sections
            for sec_name in ("leads_complete", "investors_complete"):
                if sec_name in sections and sec_name not in emitted_sections:
                    yield {"event": "section", "data": json.dumps({"section": sec_name, "payload": sections[sec_name]})}
                    emitted_sections.add(sec_name)

            # Stream strategy section
            if "strategy" in sections and "strategy" not in emitted_sections:
                yield {"event": "section", "data": json.dumps({"section": "strategy", "payload": sections["strategy"]})}
                emitted_sections.add("strategy")

            # Check for completion
            if status == "complete":
                yield {"event": "done", "data": json.dumps({})}
                break
            if status == "error":
                yield {"event": "error", "data": json.dumps({"message": progress.get("error", "Unknown")})}
                break

            await asyncio.sleep(1)

    return EventSourceResponse(progress_stream())


async def _real_poll_deep_progress(request: Request, report_id: str):
    """Real poll endpoint for deep analysis progress.

    Returns current progress including completed sections.
    Client polls every 3 seconds until status is 'complete' or 'error'.
    """
    logger.debug(f"[PROGRESS] Polling {report_id}")
    # Check if analysis is complete (full report exists)
    analysis_path = REPORTS_DIR / report_id / "analysis.json"
    if analysis_path.exists():
        try:
            analysis = json.loads(analysis_path.read_text())
            if analysis.get("_phase") == "complete":
                # Build flat arrays matching what the client JS expects
                # (channels, leads, investors, competitors, personas at top level)
                leads_research = analysis.get("leads_research", {})
                investor_research = analysis.get("investor_research", {})
                channel_list = sorted(
                    analysis.get("channel_analysis", []),
                    key=lambda c: c.get("score", 0),
                    reverse=True,
                )
                return JSONResponse({
                    "status": "complete",
                    "channels": channel_list,
                    "personas": leads_research.get("personas", []),
                    "leads": leads_research.get("leads", []),
                    "competitors": investor_research.get("competitors", []),
                    "investors": investor_research.get("competitor_investors", []) + investor_research.get("market_investors", []),
                    "sections": {
                        "channels_meta": {
                            "bullseye_ranking": analysis.get("bullseye_ranking", {}),
                            "executive_summary": analysis.get("executive_summary", ""),
                            "hot_take": analysis.get("hot_take", ""),
                            "company_profile": analysis.get("company_profile", {}),
                        },
                        "leads_complete": {"count": len(leads_research.get("leads", []))},
                        "investors_complete": {"count": len(investor_research.get("competitor_investors", []) + investor_research.get("market_investors", []))},
                        "strategy": {
                            "ninety_day_plan": analysis.get("ninety_day_plan", {}),
                            "budget_allocation": analysis.get("budget_allocation", {}),
                            "risk_matrix": analysis.get("risk_matrix", []),
                            "competitive_moat": analysis.get("competitive_moat", ""),
                        },
                    },
                })
        except Exception:
            pass

    # Check in-memory progress (includes granular channels/leads/investors)
    progress = get_deep_progress(report_id)
    if progress:
        # Normalize: ensure flat top-level arrays exist (client JS expects d.channels, d.leads, etc.)
        # If flat arrays are empty but sections have data, extract from sections.
        normalized = dict(progress)
        sections = normalized.get("sections", {})

        if not normalized.get("channels") and "channels" in sections:
            ch_sec = sections["channels"]
            if isinstance(ch_sec, dict):
                normalized["channels"] = sorted(
                    ch_sec.get("channel_analysis", []),
                    key=lambda c: c.get("score", 0),
                    reverse=True,
                )
                # Also extract channels_meta from section data
                if "channels_meta" not in sections:
                    sections["channels_meta"] = {
                        "bullseye_ranking": ch_sec.get("bullseye_ranking", {}),
                        "executive_summary": ch_sec.get("executive_summary", ""),
                        "hot_take": ch_sec.get("hot_take", ""),
                        "company_profile": ch_sec.get("company_profile", {}),
                    }

        if not normalized.get("personas") and "leads" in sections:
            leads_sec = sections["leads"]
            if isinstance(leads_sec, dict):
                normalized["personas"] = leads_sec.get("personas", [])
                if not normalized.get("leads"):
                    normalized["leads"] = leads_sec.get("leads", [])

        if not normalized.get("leads") and "leads" in sections:
            leads_sec = sections["leads"]
            if isinstance(leads_sec, dict):
                normalized["leads"] = leads_sec.get("leads", [])

        if not normalized.get("competitors") and "investors" in sections:
            inv_sec = sections["investors"]
            if isinstance(inv_sec, dict):
                normalized["competitors"] = inv_sec.get("competitors", [])

        if not normalized.get("investors") and "investors" in sections:
            inv_sec = sections["investors"]
            if isinstance(inv_sec, dict):
                normalized["investors"] = inv_sec.get("competitor_investors", []) + inv_sec.get("market_investors", [])

        return JSONResponse(normalized)

    # Analysis is running but _deep_progress didn't have data yet (race condition on first poll)
    if is_deep_analysis_running(report_id):
        return JSONResponse({"status": "Analysis starting...", "sections": {}, "channels": [], "leads": [], "investors": [], "competitors": [], "personas": []})

    # If analysis hasn't started and report is still a skeleton, start it.
    # No auth check — the page view already started it, this is a safety net
    # for cases where the background task didn't launch (race condition, restart, etc.)
    if not is_deep_analysis_running(report_id):
        analysis_path_check = REPORTS_DIR / report_id / "analysis.json"
        if analysis_path_check.exists():
            try:
                analysis_check = json.loads(analysis_path_check.read_text())
                if analysis_check.get("_phase") != "complete":
                    logger.info(f"[PROGRESS] Starting deep analysis for {report_id} via polling safety net")
                    asyncio.create_task(run_deep_analysis_background(report_id))
                    return JSONResponse({"status": "starting", "sections": {}, "channels": [], "leads": [], "investors": [], "competitors": [], "personas": []})
            except Exception:
                pass

    return JSONResponse({"status": "not_started", "sections": {}, "channels": [], "leads": [], "investors": [], "competitors": [], "personas": []})


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
            now_iso = datetime.now(tz=timezone.utc).isoformat()
            report_store.update_status(
                report_id,
                "active",
                paid_at=now_iso,
                subscription_id=subscription_id,
                customer_id=customer_id,
                subscriber_twitter_id=twitter_id,
                tier=tier,
            )
            # Sync to Supabase
            try:
                db.update_report(report_id, status="active", tier=tier, paid_at=now_iso)
                if twitter_id:
                    db.update_user_stripe(twitter_id, customer_id)
                    db.create_subscription(
                        twitter_id=twitter_id,
                        report_id=report_id,
                        stripe_subscription_id=subscription_id,
                        stripe_customer_id=customer_id,
                        tier=tier,
                    )
            except Exception as e:
                logger.warning(f"Supabase sync failed (non-fatal): {e}")
            logger.info(f"Subscription started for report {report_id} (tier={tier})")

    elif event_type == "customer.subscription.deleted":
        # Subscription canceled
        metadata = obj.get("metadata", {})
        report_id = metadata.get("report_id")
        if report_id:
            report_store.update_status(report_id, "canceled")
            try:
                db.update_report(report_id, status="canceled")
                sub_id = obj.get("id", "")
                if sub_id:
                    db.cancel_subscription_by_stripe_id(sub_id)
            except Exception as e:
                logger.warning(f"Supabase sync failed (non-fatal): {e}")
            logger.info(f"Subscription canceled for report {report_id}")

    elif event_type == "invoice.payment_failed":
        # Payment failed on renewal
        sub_id = obj.get("subscription", "")
        if sub_id:
            # Find report by subscription ID and mark as past_due
            for record in report_store.list_reports(status="active"):
                if record.subscription_id == sub_id:
                    report_store.update_status(record.report_id, "ready")
                    try:
                        db.update_report(record.report_id, status="ready")
                    except Exception:
                        pass
                    logger.warning(f"Payment failed for report {record.report_id}")
                    break

    return JSONResponse({"status": "ok"})


# --- Advisor Chat API (proxies to VPS advisor service) ---

@app.post("/advisor/chat")
async def advisor_chat(request: Request):
    """Proxy chat messages to the VPS advisor service."""
    import httpx

    session_cookie = request.cookies.get("mckoutie_session")
    user = auth.get_session_user(session_cookie)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    body = await request.json()
    agent_id = body.get("agent_id", "")
    message = body.get("message", "")
    deep = body.get("deep", False)

    if not agent_id or not message:
        return JSONResponse({"error": "Missing agent_id or message"}, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.advisor_url}/chat",
                json={"agent_id": agent_id, "message": message, "deep": deep},
                headers={"X-Advisor-Key": settings.advisor_api_key},
            )
            resp.raise_for_status()
            return JSONResponse(resp.json())
    except httpx.TimeoutException:
        return JSONResponse({"error": "Advisor took too long to respond"}, status_code=504)
    except Exception as e:
        logger.error(f"Advisor chat error: {e}")
        return JSONResponse({"error": "Advisor unavailable"}, status_code=502)


@app.get("/advisor/history/{agent_id}")
async def advisor_history(request: Request, agent_id: str):
    """Get conversation history for an agent."""
    import httpx

    session_cookie = request.cookies.get("mckoutie_session")
    user = auth.get_session_user(session_cookie)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{settings.advisor_url}/agent/{agent_id}",
                headers={"X-Advisor-Key": settings.advisor_api_key},
            )
            if resp.status_code == 404:
                return JSONResponse({"exists": False, "message_count": 0})
            resp.raise_for_status()
            data = resp.json()
            data["exists"] = True
            return JSONResponse(data)
    except Exception as e:
        logger.error(f"Advisor history error: {e}")
        return JSONResponse({"exists": False, "error": str(e)}, status_code=502)


async def _handle_analyze(request: Request):
    """Accept a website URL from the landing page form."""
    logger.info(f"[ANALYZE] Received {request.method} request")
    try:
        from src.analysis.report_generator import generate_report_id, save_report
        from src.analysis.traction_engine import run_quick_analysis
        from src.modules.report_store import ReportRecord, save_record
        import re as _re

        if request.method == "POST":
            form = await request.form()
            raw_url = str(form.get("url", "")).strip()
        else:
            raw_url = request.query_params.get("url", "").strip()
        logger.info(f"[ANALYZE] URL: {raw_url}")

        if not raw_url:
            return RedirectResponse("/", status_code=303)

        # Normalize URL
        if not raw_url.startswith(("http://", "https://")):
            raw_url = "https://" + raw_url

        # Basic validation
        if not _re.match(r"https?://[a-zA-Z0-9]", raw_url):
            return RedirectResponse("/", status_code=303)

        report_id = generate_report_id(raw_url)

        # Check if we already have a report for this URL (within 24h)
        existing = report_store.load_record(report_id)
        if existing:
            login_url = f"/auth/twitter?redirect={quote(f'/report/{report_id}')}"
            return RedirectResponse(login_url, status_code=303)

        # Create a minimal skeleton — deep analysis runs on page visit after login
        record = ReportRecord(
            report_id=report_id,
            startup_name=raw_url,
            target=raw_url,
            tweet_id="",
            author_username="web",
            author_id="web",
            status="skeleton",
        )
        save_record(record)

        # Sync to Supabase
        try:
            db.create_report(
                report_id=report_id,
                startup_name=raw_url,
                target=raw_url,
                tweet_id="",
                author_twitter_id="web",
                author_username="web",
            )
        except Exception as e:
            logger.warning(f"Supabase report create failed (non-fatal): {e}")

        # Save a bare skeleton immediately so the report page works
        # Deep analysis will happen later when user visits the report
        skeleton_data = {
            "company_profile": {"name": raw_url},
            "top_3_channels": [],
            "hot_take": "",
            "channel_analysis": [],
            "bullseye_ranking": {},
            "ninety_day_plan": {},
            "budget_allocation": {},
            "risk_matrix": [],
            "competitive_moat": "",
            "executive_summary": "",
            "leads_research": {},
            "investor_research": {},
            "_startup_data": f"## WEBSITE DATA\nURL: {raw_url}",
            "_phase": "skeleton",
        }
        save_report(report_id, skeleton_data, "")

        # Try a fast quick-analysis prefill BEFORE redirect, so dashboard has
        # immediate top channels to render while deep analysis streams.
        try:
            quick_prefill = await asyncio.wait_for(
                run_quick_analysis(f"## WEBSITE DATA\nURL: {raw_url}"),
                timeout=10.0,
            )
            top3 = quick_prefill.get("top_3_channels", []) if isinstance(quick_prefill, dict) else []
            if top3:
                skeleton_data["top_3_channels"] = top3
                skeleton_data["hot_take"] = quick_prefill.get("hot_take", "") if isinstance(quick_prefill, dict) else ""
                profile = quick_prefill.get("company_profile", {}) if isinstance(quick_prefill, dict) else {}
                if profile:
                    skeleton_data["company_profile"] = profile
                save_report(report_id, skeleton_data, "")
                logger.info(f"[ANALYZE] Quick prefill ready for {report_id} with {len(top3)} channels")
        except Exception as e:
            logger.info(f"[ANALYZE] Quick prefill skipped for {report_id}: {e}")

        # Kick off scrape + quick analysis in background (non-blocking)
        async def _bg_quick_analyze(rid: str, url: str):
            try:
                from src.modules.scraper import scrape_website
                from src.modules.report_store import update_status

                site_data = await scrape_website(url)
                if site_data.get("content") and len(site_data["content"]) > 50:
                    parts = [f"## WEBSITE DATA\nURL: {site_data['url']}"]
                    if site_data.get("title"):
                        parts.append(f"Title: {site_data['title']}")
                    if site_data.get("description"):
                        parts.append(f"Description: {site_data['description']}")
                    parts.append(f"\nContent:\n{site_data['content'][:8000]}")
                    startup_data = "\n".join(parts)

                    quick = await run_quick_analysis(startup_data)
                    profile = quick.get("company_profile", {})
                    startup_name = profile.get("name", url)

                    enriched = {
                        "company_profile": profile,
                        "top_3_channels": quick.get("top_3_channels", []),
                        "hot_take": quick.get("hot_take", ""),
                        "channel_analysis": [],
                        "bullseye_ranking": {},
                        "ninety_day_plan": {},
                        "budget_allocation": {},
                        "risk_matrix": [],
                        "competitive_moat": "",
                        "executive_summary": "",
                        "leads_research": {},
                        "investor_research": {},
                        "_startup_data": startup_data,
                        "_phase": "skeleton",
                    }
                    save_report(rid, enriched, "")
                    update_status(rid, "skeleton", startup_name=startup_name)
                    logger.info(f"[ANALYZE] Background quick analysis done for {rid}")
            except Exception as e:
                logger.warning(f"[ANALYZE] Background quick analysis failed (non-fatal): {e}")

        import asyncio
        asyncio.create_task(_bg_quick_analyze(report_id, raw_url))

        # Redirect to Twitter login immediately (don't wait for analysis)
        login_url = f"/auth/twitter?redirect={quote(f'/report/{report_id}')}"
        logger.info(f"[ANALYZE] Redirecting to {login_url}")
        return RedirectResponse(login_url, status_code=303)

    except Exception as exc:
        logger.error(f"[ANALYZE] Unhandled error: {exc}", exc_info=True)
        return HTMLResponse(f"<h1>Error processing request</h1><pre>{exc}</pre>", status_code=500)


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_post(request: Request):
    return await _handle_analyze(request)


@app.get("/analyze", response_class=HTMLResponse)
async def analyze_get(request: Request):
    return await _handle_analyze(request)


@app.post("/api/hermes/analyze")
async def hermes_analyze(request: Request):
    """Server-to-server report creation for Hermes/Telegram bot."""
    ok, reason = _check_hermes_access(request)
    if not ok:
        return JSONResponse({"error": reason}, status_code=403)

    try:
        from src.analysis.report_generator import generate_report_id, save_report
        from src.modules.report_store import ReportRecord, save_record
        import re as _re

        body = await request.json()
        raw_url = str(body.get("url", "")).strip()
        if not raw_url:
            return JSONResponse({"error": "Missing url"}, status_code=400)

        if not raw_url.startswith(("http://", "https://")):
            raw_url = "https://" + raw_url
        if not _re.match(r"https?://[a-zA-Z0-9]", raw_url):
            return JSONResponse({"error": "Invalid url"}, status_code=400)

        report_id = generate_report_id(raw_url)
        existing = report_store.load_record(report_id)
        if existing:
            if not is_deep_analysis_running(report_id):
                asyncio.create_task(run_deep_analysis_background(report_id))
            return JSONResponse({
                "report_id": report_id,
                "status": "existing",
                "report_url": f"/report/{report_id}",
                "progress_url": f"/report/{report_id}/progress",
            })

        record = ReportRecord(
            report_id=report_id,
            startup_name=raw_url,
            target=raw_url,
            tweet_id="",
            author_username="hermes",
            author_id="hermes",
            status="skeleton",
        )
        save_record(record)

        try:
            db.create_report(
                report_id=report_id,
                startup_name=raw_url,
                target=raw_url,
                tweet_id="",
                author_twitter_id="hermes",
                author_username="hermes",
            )
        except Exception as e:
            logger.warning(f"Hermes Supabase report create failed (non-fatal): {e}")

        skeleton_data = {
            "company_profile": {"name": raw_url},
            "top_3_channels": [],
            "hot_take": "",
            "channel_analysis": [],
            "bullseye_ranking": {},
            "ninety_day_plan": {},
            "budget_allocation": {},
            "risk_matrix": [],
            "competitive_moat": "",
            "executive_summary": "",
            "leads_research": {},
            "investor_research": {},
            "_startup_data": f"## WEBSITE DATA\nURL: {raw_url}",
            "_phase": "skeleton",
        }
        save_report(report_id, skeleton_data, "")

        # Start deep analysis immediately for bot-driven flow.
        asyncio.create_task(run_deep_analysis_background(report_id))

        return JSONResponse({
            "report_id": report_id,
            "status": "started",
            "report_url": f"/report/{report_id}",
            "progress_url": f"/report/{report_id}/progress",
        })
    except Exception as e:
        logger.error(f"Hermes analyze failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/hermes/report/{report_id}")
async def hermes_report_progress(request: Request, report_id: str):
    """Auth-gated progress endpoint for Hermes bot."""
    ok, reason = _check_hermes_access(request)
    if not ok:
        return JSONResponse({"error": reason}, status_code=403)
    return await _real_poll_deep_progress(request, report_id)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mckoutie", "version": "0.1.0"}


@app.get("/debug/report/{report_id}")
async def debug_report(report_id: str):
    """Debug: show report file metadata (no sensitive data)."""
    analysis_path = REPORTS_DIR / report_id / "analysis.json"
    record_path = REPORTS_DIR / report_id / "record.json"
    result = {
        "report_id": report_id,
        "reports_dir": str(REPORTS_DIR),
        "analysis_exists": analysis_path.exists(),
        "record_exists": record_path.exists(),
    }
    if analysis_path.exists():
        try:
            data = json.loads(analysis_path.read_text())
            sd = data.get("_startup_data", "")
            result["_phase"] = data.get("_phase", "unknown")
            result["_startup_data_len"] = len(sd) if sd else 0
            result["_startup_data_preview"] = sd[:200] if sd else "(empty)"
            result["has_channels"] = len(data.get("channel_analysis", [])) > 0
            result["company_name"] = data.get("company_profile", {}).get("name", "")
        except Exception as e:
            result["analysis_error"] = str(e)
    if record_path.exists():
        try:
            rec = json.loads(record_path.read_text())
            result["target"] = rec.get("target", "")
            result["status"] = rec.get("status", "")
        except Exception as e:
            result["record_error"] = str(e)
    return result


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
