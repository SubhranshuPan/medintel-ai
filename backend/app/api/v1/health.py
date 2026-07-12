"""Health endpoints: liveness and readiness.

- ``/health``       — liveness (process is up); no external dependencies.
- ``/health/ready`` — readiness (can serve traffic); checks DB connectivity.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db

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


@router.get("/health/ready")
async def readiness(db: Annotated[AsyncSession, Depends(get_db)]) -> JSONResponse:
    """Return 200 when the database is reachable, else 503."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503, content={"status": "not_ready", "database": "down"}
        )
    return JSONResponse(status_code=200, content={"status": "ready", "database": "ok"})
