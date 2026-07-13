"""Audit log — GDPR-aware trail for patient-data access (TRD §9, §13).

Append-only by construction: nothing in the codebase updates or deletes rows
here. Records both successful and rejected (401/403) access attempts, because a
denied attempt on patient data is exactly the event a compliance review cares
about. Synthetic data is treated as real PHI per project policy.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonB, TimestampMixin, UUIDMixin


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """One request against an audited (patient-data) endpoint."""

    __tablename__ = "audit_logs"

    # Nullable: an unauthenticated/invalid-token request is still audited, and
    # has no user to attribute it to. ondelete RESTRICT — deleting a user must
    # not erase the trail.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(32))

    action: Mapped[str] = mapped_column(String(16))          # HTTP method
    resource_type: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "dataset"
    resource_id: Mapped[str | None] = mapped_column(String(64), index=True)
    path: Mapped[str] = mapped_column(String(512))
    status_code: Mapped[int] = mapped_column(Integer, index=True)

    client_ip: Mapped[str | None] = mapped_column(String(45))   # IPv6-safe length
    user_agent: Mapped[str | None] = mapped_column(String(512))
    detail: Mapped[dict | None] = mapped_column(JsonB)          # endpoint-enriched
