"""Typed application configuration loaded from environment / .env.

All settings use the ``MEDINTEL_`` env prefix (e.g. ``MEDINTEL_ENVIRONMENT``).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables (prefixed ``MEDINTEL_``) or a
    local ``.env`` file. Unknown keys are ignored so infra-level env vars don't
    break startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MEDINTEL_",
        extra="ignore",
    )

    app_name: str = "MedIntel AI"
    environment: str = "development"
    version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Async SQLAlchemy URL (asyncpg driver). Override per environment.
    database_url: str = "postgresql+asyncpg://medintel:medintel@localhost:5432/medintel"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (one load per process)."""
    return Settings()
