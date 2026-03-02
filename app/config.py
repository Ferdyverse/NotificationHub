from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/app.db"
    base_url: str = "http://localhost:8080"

    ui_basic_auth_user: str | None = None
    ui_basic_auth_pass: str | None = None
    session_secret: str = "change-me"

    default_dedupe_seconds: int = 60
    default_rate_limit_per_min: int = 60
    max_events: int = 500
    max_raw_payload_chars: int = 50000

    outbound_timeout_seconds: int = 10
    outbound_retry_attempts: int = 3
    outbound_retry_backoff_seconds: float = 0.8


settings = Settings()
