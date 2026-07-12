"""Typed application configuration loaded from environment / .env.

All settings use the ``MEDINTEL_`` env prefix (e.g. ``MEDINTEL_ENVIRONMENT``).
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dev-only placeholder; the settings validator refuses it outside dev/test.
PLACEHOLDER_JWT_SECRET = "dev-insecure-change-me"


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

    # JWT signing. The default is a dev-only placeholder; any non-dev/test
    # environment MUST override MEDINTEL_JWT_SECRET with a strong value
    # (enforced below). Generate one with: openssl rand -hex 32
    jwt_secret: str = PLACEHOLDER_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        """Reject the placeholder or a weak secret outside development/test.

        NOTE: ``environment`` defaults to ``development``, so a deployment that
        forgets to set ``MEDINTEL_ENVIRONMENT`` will not trip this guard —
        deployments MUST set both ``MEDINTEL_ENVIRONMENT`` and a strong
        ``MEDINTEL_JWT_SECRET`` (see .env.example).
        """
        if self.environment in {"development", "test"}:
            return self
        if self.jwt_secret == PLACEHOLDER_JWT_SECRET or len(self.jwt_secret) < 32:
            raise ValueError(
                "MEDINTEL_JWT_SECRET must be a strong secret (>=32 chars) "
                "outside development/test"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (one load per process)."""
    return Settings()
