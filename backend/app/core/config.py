"""Typed application configuration loaded from environment / .env.

All settings use the ``MEDINTEL_`` env prefix (e.g. ``MEDINTEL_ENVIRONMENT``).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dev-only placeholder; the settings validator refuses it outside dev/test.
PLACEHOLDER_JWT_SECRET = "dev-insecure-change-me"

# The only environments allowed to run on the placeholder secret. Anything else
# — including an unset or misspelled MEDINTEL_ENVIRONMENT — must supply a real one.
_LOCAL_ENVIRONMENTS = frozenset({"development", "test"})


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
    # Not defaulted to a local environment: an unset MEDINTEL_ENVIRONMENT must
    # not be what decides whether the placeholder JWT secret is acceptable.
    environment: str = "production"
    version: str = "0.1.0"
    # Vite's dev server (frontend/vite.config.ts) — not CRA's port 3000.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Async SQLAlchemy URL (asyncpg driver). Override per environment.
    database_url: str = "postgresql+asyncpg://medintel:medintel@localhost:5432/medintel"

    # JWT signing. The default is a dev-only placeholder; any non-dev/test
    # environment MUST override MEDINTEL_JWT_SECRET with a strong value
    # (enforced below). Generate one with: openssl rand -hex 32
    jwt_secret: str = PLACEHOLDER_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Object storage (ADR-009). Local disk in dev; an S3/MinIO backend swaps in
    # behind the same ObjectStore protocol without touching callers.
    storage_dir: Path = Path("./storage/datasets")
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB — reject bigger CSVs outright

    # --- corpus ingestion (#61) ---
    # NCBI requires a tool name and contact address on every E-utilities call
    # and contacts the address before blocking a client that misbehaves. No
    # default email: a shared or invented address would mean someone else gets
    # the warning, so ingestion refuses to run until this is set deliberately.
    pubmed_tool: str = "medintel-ai"
    pubmed_email: str = ""
    # Optional. Raises NCBI's rate limit from 3 to 10 requests/second.
    pubmed_api_key: str | None = None
    # The clinical query set the corpus is built from. Narrow on purpose —
    # extraction (#63) costs one LLM call per structural unit, so corpus breadth
    # is a cost decision as much as a coverage one.
    pubmed_queries: list[str] = [
        "heart failure reduced ejection fraction guideline directed therapy",
        "atrial fibrillation anticoagulation stroke prevention",
        "type 2 diabetes glycaemic target adults",
    ]
    pubmed_results_per_query: int = 25

    # --- vector store (#62, ADR-004) ---
    # Service name `qdrant` resolves on the compose network; localhost in a
    # bare-metal dev run.
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "knowledge_chunks"
    # Must match the embedding provider's output width. Qdrant fixes vector size
    # at collection creation, so changing this means recreating the collection
    # and re-embedding the corpus — it is not a runtime knob.
    embedding_dimension: int = 768
    # Chunk budget. Structural units under it are embedded whole; only a unit
    # over it is token-split (see app/services/chunking.py).
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 64

    # --- knowledge extraction (#63, ADR-022) ---
    # No default key: extraction is the only pipeline here that spends money,
    # and it should refuse to start rather than pick up an ambient credential.
    anthropic_api_key: str | None = None
    # Pinned as config so a tier change is a config change and shows up in the
    # audit log, per ADR-022 — never hard-coded at the call site.
    extraction_model: str = "claude-haiku-4-5"
    # Two independent ceilings on a single run, both enforced in code. The unit
    # cap bounds how much corpus is touched; the spend cap bounds the bill even
    # if the per-call cost turns out higher than estimated. Measured against the
    # real corpus at ~2,770 input / 250 output tokens per structural unit, which
    # is $0.0040 on Haiku 4.5 — so 500 units is about $2.01, and the $5 ceiling
    # is the backstop rather than the expected spend. The current corpus (85
    # units) costs roughly $0.34 to extract in full.
    extraction_max_units: int = 500
    extraction_budget_usd: float = 5.0
    # Candidate passages offered per call — the dominant input-token cost after
    # the passage itself, and the set outside which a target is rejected.
    extraction_max_candidates: int = 20

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        """Reject the placeholder or a weak secret outside development/test.

        Fails closed: an unrecognised ``environment`` is treated as non-dev, so
        a typo (``prod`` for ``production``) still demands a strong secret. Only
        the two named local environments are exempt.
        """
        if self.environment in _LOCAL_ENVIRONMENTS:
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
