"""Embedding model — metadata for a document chunk vector.

The vector itself lives in Qdrant (ADR-004); this row stores the chunk text and
a reference to the Qdrant point so relational and vector stores stay in sync.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.document import Document


class Embedding(UUIDMixin, TimestampMixin, Base):
    """A single chunk of a document, embedded and indexed in Qdrant."""

    __tablename__ = "embeddings"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text_chunk: Mapped[str] = mapped_column(Text)
    # Qdrant point id for the stored vector.
    vector_id: Mapped[str] = mapped_column(String(255), index=True)

    document: Mapped["Document"] = relationship(back_populates="embeddings")
