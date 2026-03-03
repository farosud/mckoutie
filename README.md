# mckoutie

McKinsey at home. AI startup consulting for $100.

Tweet `@mckoutie analyse my startup https://yoursite.com` and get a full 19-channel traction strategy brief.

## How it works

1. Someone tweets at @mckoutie with their startup URL or Twitter handle
2. Bot scrapes the website + analyzes their Twitter presence
3. Runs a full 19-channel traction analysis via Claude
4. Replies with a free teaser thread (top 3 channels + hot take)
5. Links to a $100 Stripe checkout for the full brief
6. On payment, unlocks the complete report (90-day plan, budget, risk matrix)

## Architecture

```
Twitter mention → Scraper (Firecrawl/Exa/Jina) → Claude analysis → Report generator
                                                                  ↓
                                                        Teaser thread (free)
                                                        Full brief ($100 via Stripe)
```

## Setup

### Requirements

- Python 3.12+
- Twitter API access (Basic tier, $100/mo)
- Anthropic API key
- Stripe account
- At least one of: Exa API key, Firecrawl API key

### Local development

```bash
cp .env.example .env
# Fill in your API keys

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the full bot (server + Twitter polling)
python main.py

# Or test a single analysis without Twitter
python main.py analyze https://example.com
python main.py analyze @somecompany
```

### Deploy to Railway

```bash
railway login
railway init --name mckoutie

# Set environment variables
railway variable set TWITTER_API_KEY=xxx
railway variable set TWITTER_API_SECRET=xxx
railway variable set TWITTER_ACCESS_TOKEN=xxx
railway variable set TWITTER_ACCESS_TOKEN_SECRET=xxx
railway variable set TWITTER_BEARER_TOKEN=xxx
railway variable set ANTHROPIC_API_KEY=xxx
railway variable set STRIPE_SECRET_KEY=xxx
railway variable set STRIPE_WEBHOOK_SECRET=xxx
railway variable set EXA_API_KEY=xxx
railway variable set APP_URL=https://mckoutie.up.railway.app
railway variable set PORT=8000

# Deploy
railway up --detach

# Check logs
railway logs --lines 200
```

## Endpoints

- `GET /` — Landing page
- `GET /report/{id}` — View report (teaser or full)
- `POST /webhook/stripe` — Stripe payment webhook
- `GET /health` — Health check
- `GET /stats` — Report counts

## Twitter

https://x.com/mckoutie
