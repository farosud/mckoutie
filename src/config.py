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

    # OpenRouter (fallback LLM)
    openrouter_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""  # recurring price ID (created on first checkout if empty)

    # Scraping
    exa_api_key: str = ""
    firecrawl_api_key: str = ""
    serper_api_key: str = ""

    # App
    port: int = 8000
    app_url: str = "https://www.mckoutie.com"
    bot_username: str = "mckoutie"
    report_price_usd: int = 39  # starter tier monthly subscription price
    growth_price_usd: int = 200  # growth tier monthly subscription price
    enterprise_email: str = "emi@mckoutie.com"
    poll_interval_seconds: int = 60
    analysis_model: str = "claude-sonnet-4-20250514"
    analysis_max_tokens: int = 12000

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
    def has_llm(self) -> bool:
        """Do we have at least one LLM provider?"""
        return bool(self.anthropic_api_key or self.openrouter_api_key)

    @property
    def has_payments(self) -> bool:
        return bool(self.stripe_secret_key)

    @property
    def has_scraping(self) -> bool:
        return bool(self.exa_api_key or self.firecrawl_api_key)


settings = Settings()
