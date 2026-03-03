from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Twitter
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    twitter_bearer_token: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # Scraping
    exa_api_key: str = ""
    firecrawl_api_key: str = ""
    serper_api_key: str = ""

    # App
    port: int = 8000
    app_url: str = "http://localhost:8000"
    bot_username: str = "mckoutie"
    report_price_usd: int = 100
    poll_interval_seconds: int = 60
    analysis_model: str = "claude-sonnet-4-6-20250514"
    analysis_max_tokens: int = 12000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
