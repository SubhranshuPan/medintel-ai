"""Health-check endpoint (liveness).

Readiness (DB/vector-store connectivity) is added with the Docker slice (#8).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service liveness and build metadata."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.version,
        environment=settings.environment,
    )
