"""Application configuration from environment."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str
    webhook_secret: str = ""
    webhook_base_url: str = ""

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    log_level: str = "INFO"

    # Scheduler: how many minutes after target time we still dispatch notifications.
    # Increase this if celery_beat occasionally drifts or misses a tick.
    dispatch_window_minutes: int = 10

    @property
    def database_url_sync(self) -> str:
        """Synchronous URL for Alembic (replace asyncpg with psycopg2)."""
        if "+asyncpg" in self.database_url:
            return self.database_url.replace("+asyncpg", "").strip()
        return self.database_url
