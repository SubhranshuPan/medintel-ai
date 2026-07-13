"""Audit log persistence. Append-only: no update/delete surface is exposed."""

from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Write-side of the audit trail.

    Deliberately does NOT expose ``delete`` — inherited from BaseRepository but
    never called; the audit trail is append-only (TRD §13).
    """

    model = AuditLog
