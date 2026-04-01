from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://meruem:meruem_dev_pass@localhost:5432/meruem"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Twitter / X API
    twitter_bearer_token: str = ""
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""

    # Object storage
    object_storage_local: bool = True
    local_raw_data_dir: str = "raw_data"
    object_storage_bucket: str = "meruem-raw"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    aws_endpoint_url: str = ""  # For DO Spaces / custom S3

    # Instagram Graph API
    instagram_access_token: str = ""
    instagram_graph_api_version: str = "v19.0"

    # Facebook Graph API
    facebook_access_token: str = ""
    facebook_graph_api_version: str = "v19.0"

    # Sentry error tracking (optional)
    sentry_dsn: str = ""
    sentry_environment: str = "development"

    # API rate limiting
    rate_limit_enabled: bool = True
    rate_limit_default: str = "200/minute"  # per IP / account

    # Email / SMTP (optional — notifications gracefully skip if not configured)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@meruem.app"
    smtp_tls: bool = True

    # LinkedIn API (optional — enables API path for company pages)
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_access_token: str = ""

    # Anthropic / profiling
    anthropic_api_key: str = ""
    anthropic_api_base: str = "https://api.anthropic.com/v1/messages"
    anthropic_api_version: str = "2023-06-01"
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_timeout_seconds: int = 30
    profiling_rate_limit_per_minute: int = 50
    profiling_max_profiles_per_run: int = 500

    # Bot scraper settings
    bot_use_proxy: bool = True
    bot_headless: bool = True
    proxy_max_failures: int = 5     # Deactivate proxy after this many consecutive failures

    # App
    app_name: str = "Meruem"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"


settings = Settings()
