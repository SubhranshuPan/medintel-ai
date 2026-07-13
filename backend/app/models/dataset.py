"""Dataset and DatasetVersion models — Patient Data Platform (ADR-009).

A ``Dataset`` is a logical, named clinical dataset. Each ``DatasetVersion`` is an
immutable snapshot: one stored object (never overwritten) plus one metadata row.
Validation and cleaning never mutate a version — they create a new one whose
``parent_version_id`` points at what it was derived from, so any model trained
downstream (ADR-010) can be traced back to exact data provenance.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonB, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class ValidationStatus(enum.StrEnum):
    """Outcome of schema/data validation for a version (ADR-014, #33)."""

    pending = "pending"      # uploaded, not yet validated
    passed = "passed"
    failed = "failed"


class VersionOrigin(enum.StrEnum):
    """How a version came to exist — the provenance of the row."""

    upload = "upload"        # raw user upload (v1, no parent)
    cleaned = "cleaned"      # derived by the cleaning pipeline (#34)


class Dataset(UUIDMixin, TimestampMixin, Base):
    """A logical clinical dataset owned by a user."""

    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    # Soft delete: an audited clinical artifact is never silently destroyed
    # (see #35 for the erasure discussion). NULL = live.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped["User"] = relationship()
    versions: Mapped[list["DatasetVersion"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetVersion.version_number",
    )


class DatasetVersion(UUIDMixin, TimestampMixin, Base):
    """An immutable snapshot of a dataset (ADR-009).

    Rows here are append-only by convention AND by construction: nothing in the
    service layer updates a persisted version except the one-shot validation
    stamp written immediately after creation. Cleaning produces a *new* row.
    """

    __tablename__ = "dataset_versions"
    __table_args__ = (
        # Version numbers are dense and unique per dataset. This constraint is
        # what makes the "read max, write max+1" race safe — a loser gets an
        # IntegrityError rather than a duplicate version.
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT")
    )
    origin: Mapped[VersionOrigin] = mapped_column(
        Enum(VersionOrigin, name="version_origin"), default=VersionOrigin.upload
    )

    # --- stored object (immutable) ---
    storage_uri: Mapped[str] = mapped_column(String(1024))
    checksum: Mapped[str] = mapped_column(String(64), index=True)  # sha256 hex
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    original_filename: Mapped[str | None] = mapped_column(String(512))

    # --- shape / schema (ADR-009: schema hash, row count, column list) ---
    row_count: Mapped[int | None] = mapped_column(Integer)
    column_names: Mapped[list[str] | None] = mapped_column(JsonB)
    schema_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    # --- validation (#33) ---
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"),
        default=ValidationStatus.pending,
    )
    validation_report: Mapped[dict | None] = mapped_column(JsonB)

    # --- provenance of a derived version (#34) ---
    transformation: Mapped[dict | None] = mapped_column(JsonB)

    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    dataset: Mapped["Dataset"] = relationship(back_populates="versions")
    parent_version: Mapped["DatasetVersion | None"] = relationship(remote_side="DatasetVersion.id")
