"""Citation model — source attribution linking a message to a document."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.message import Message


class Citation(UUIDMixin, TimestampMixin, Base):
    """A grounded reference backing part of an AI response."""

    __tablename__ = "citations"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    snippet: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)

    message: Mapped["Message"] = relationship(back_populates="citations")
    document: Mapped["Document"] = relationship(back_populates="citations")
