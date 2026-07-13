"""Declarative base and shared mixins.

All tables carry a UUID primary key (non-enumerable — avoids leaking record
counts or guessable patient identifiers) and audit timestamps (GDPR-aware).
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class UUIDMixin:
    """UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Audit timestamps, set/maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Postgres is the deployment target (ADR-003), but the test suite runs SQLite
# (tests/conftest.py). JSONB degrades to plain JSON there so metadata.create_all
# works in both.
JsonB = JSONB().with_variant(JSON(), "sqlite")
