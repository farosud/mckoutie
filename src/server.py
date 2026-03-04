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
            min-height: 100vh; display: flex; flex-direction: column;
            justify-content: center; align-items: center; text-align: center;
            padding: 2rem; position: relative;
            background: url('https://i0.wp.com/www.sensesatlas.com/wp-content/uploads/2020/05/BiyC5vOFtGL6CGvyMJ14c3rXYZrrFy3i_VLnOUyvJ2Q.jpg?fit=2119%2C2078&ssl=1') center center / cover no-repeat;
        }
        .hero::before {
            content: ''; position: absolute; inset: 0;
            background: rgba(10,10,10,0.75);
            pointer-events: none;
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
    <div class="logo">mck<span>ou</span>tie</div>
    <p class="tagline-main">Consultoría de crecimiento para startups argentinas</p>
    <p class="tagline-sub">
        Análisis de tracción con IA. 19 canales de crecimiento rankeados para TU startup.
        Plan de 90 días. Sin chamuyo, sin PowerPoints de 200 slides. $39/mes.
    </p>
    <a class="cta-hero" href="https://x.com/intent/tweet?text=@mckoutie%20analyse%20my%20startup%20" target="_blank">
        Analizá tu startup ahora
    </a>
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
