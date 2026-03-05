from urllib.parse import unquote

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Twitter
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    twitter_bearer_token: str = ""
    twitter_client_id: str = ""
    twitter_client_secret: str = ""

    def model_post_init(self, __context) -> None:
        # Keep bearer token as-is — the X API pay-per-use tier requires
        # the URL-encoded form (with %2B, %3D etc.) for read endpoints.
        pass

    # Anthropic
    anthropic_api_key: str = ""

    # VPS Proxy (Claude Code Max — primary LLM)
    vps_proxy_url: str = "http://165.227.18.32:3457/v1"
    vps_proxy_key: str = ""

    # OpenRouter (fallback LLM + Gemini image gen)
    openrouter_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""  # recurring price ID (created on first checkout if empty)

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""  # service_role key for server-side operations

    # Scraping
    exa_api_key: str = ""
    firecrawl_api_key: str = ""
    serper_api_key: str = ""

    # App
    port: int = 8000
    app_url: str = "https://www.mckoutie.com"
    railway_public_url: str = "https://mckoutie-bot-production.up.railway.app"  # Direct Railway URL for SSE (bypasses Vercel proxy)
    bot_username: str = "mckoutie"
    report_price_usd: int = 39  # starter tier monthly subscription price
    growth_price_usd: int = 200  # growth tier monthly subscription price
    enterprise_email: str = "emi@mckoutie.com"
    poll_interval_seconds: int = 60
    # Tiered model allocation — Sonnet for bulk analysis, Opus for synthesis, Haiku for updates
    analysis_model: str = "claude-sonnet-4"  # Sonnet on VPS — main 19-channel analysis (fast, reliable)
    analysis_model_fallback: str = "anthropic/claude-sonnet-4"  # Sonnet on OpenRouter fallback
    hot_take_model: str = "claude-opus-4"  # Opus on VPS — hot take synthesis only (short, high-value)
    hot_take_model_fallback: str = "anthropic/claude-opus-4"  # Opus on OpenRouter fallback
    persona_model: str = "claude-haiku-4-5-20251001"  # Haiku on VPS — fast persona/lead/investor generation
    persona_model_fallback: str = "anthropic/claude-3-5-haiku-20241022"  # Haiku on OpenRouter fallback
    persona_model_fallback2: str = "google/gemini-2.5-flash"  # Gemini Flash — cheap + reliable
    update_model: str = "claude-haiku-4-5-20251001"  # Haiku on VPS — market updates (delta analysis)
    update_model_fallback: str = "anthropic/claude-3-5-haiku-20241022"  # Haiku on OpenRouter fallback
    analysis_max_tokens: int = 32000
    hot_take_max_tokens: int = 2000  # Opus hot take is short — keep it fast

    # Advisor Service (VPS — per-user AI strategy agents)
    advisor_url: str = "http://165.227.18.32:3458"
    advisor_api_key: str = "mckoutie-advisor-2026"

    # Stripe price IDs (created on first checkout if empty)
    stripe_starter_price_id: str = ""
    stripe_growth_price_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def has_twitter_write(self) -> bool:
        """Can we post tweets (need all 4 OAuth keys)?"""
        return all([
            self.twitter_api_key,
            self.twitter_api_secret,
            self.twitter_access_token,
            self.twitter_access_token_secret,
        ])

    @property
    def has_twitter_read(self) -> bool:
        """Can we read mentions (need OAuth 1.0a keys)?"""
        return self.has_twitter_write

    @property
    def has_vps_proxy(self) -> bool:
        """Do we have the VPS Claude proxy configured?"""
        return bool(self.vps_proxy_key and self.vps_proxy_url)

    @property
    def has_llm(self) -> bool:
        """Do we have at least one LLM provider?"""
        return bool(self.vps_proxy_key or self.anthropic_api_key or self.openrouter_api_key)

    @property
    def has_payments(self) -> bool:
        return bool(self.stripe_secret_key)

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def has_scraping(self) -> bool:
        return bool(self.exa_api_key or self.firecrawl_api_key)


settings = Settings()
