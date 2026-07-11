"""Document model — a medical knowledge source for RAG retrieval."""

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.citation import Citation
    from app.models.embedding import Embedding


class Document(UUIDMixin, TimestampMixin, Base):
    """A source document (guideline, article) chunked into embeddings."""

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(512))
    source: Mapped[str | None] = mapped_column(String(1024))
    content: Mapped[str | None] = mapped_column(Text)

    embeddings: Mapped[list["Embedding"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    citations: Mapped[list["Citation"]] = relationship(back_populates="document")
