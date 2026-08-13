"""Embedding model — metadata for a document chunk vector.

The vector itself lives in Qdrant (ADR-004); this row stores the chunk text and
a reference to the Qdrant point so relational and vector stores stay in sync.

Since ADR-021 the row is also the join between a retrieval chunk and the
knowledge graph: ``node_id`` points at the ``KnowledgeNode`` the chunk realises,
so a vector hit can be resolved to typed, provenanced knowledge rather than
returned as bare text.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.document import Document


class Embedding(UUIDMixin, TimestampMixin, Base):
    """A single chunk of a document, embedded and indexed in Qdrant."""

    __tablename__ = "embeddings"
    __table_args__ = (
        # Both parents are nullable, but not at the same time. A chunk with
        # neither is text that retrieval can surface and generation cannot
        # attribute to anything — an uncitable claim, which is the exact failure
        # this pillar exists to prevent. Enforced by the database so it holds
        # regardless of which writer created the row.
        CheckConstraint(
            "document_id IS NOT NULL OR node_id IS NOT NULL",
            name="ck_embeddings_has_parent",
        ),
    )

    # Nullable since #62. A corpus chunk's unit of truth is its knowledge node
    # (ADR-021), and minting a Document row purely to satisfy this key would
    # duplicate the node's title and text to no end. Uploaded documents still
    # set it; the table-level check below is what stops a chunk from having
    # neither parent.
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text_chunk: Mapped[str] = mapped_column(Text)
    # Qdrant point id for the stored vector.
    vector_id: Mapped[str] = mapped_column(String(255), index=True)
    # The knowledge node this chunk realises (ADR-021). Nullable: chunks
    # embedded before the knowledge layer existed, and any chunk whose
    # extraction produced no node, have none. The chunk stays a retrieval
    # handle; the node is the unit of truth.
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "knowledge_nodes.id", ondelete="SET NULL", name="fk_embeddings_node_id"
        ),
        index=True,
    )

    document: Mapped["Document"] = relationship(back_populates="embeddings")
