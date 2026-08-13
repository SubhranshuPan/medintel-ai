"""Knowledge graph models — typed clinical entities and their relationships.

The knowledge layer beneath retrieval (ADR-021). A ``KnowledgeNode`` is the unit
of truth for a structural unit of the corpus (a guideline recommendation, an
article abstract, a defined term); a ``KnowledgeEdge`` is a typed, provenanced
relationship between two of them.

Both the node value sets and the edge type set are closed and enforced by
PostgreSQL enums plus foreign keys, not by a code convention: a malformed
extraction is rejected by the database at ingestion rather than caught in review
months later. ``KnowledgeEdge.extracted_by`` records which model and prompt
version produced an edge so the graph can be re-validated when the extractor
changes — extraction quality drifts as source documents and models change, and
an unversioned graph rots silently.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonB, TimestampMixin, UUIDMixin


class KnowledgeNodeType(enum.StrEnum):
    """What kind of thing a node represents."""

    guideline = "guideline"            # a whole clinical guideline
    article = "article"                # a published paper
    recommendation = "recommendation"  # a single actionable recommendation
    term = "term"                      # a defined clinical term


class KnowledgeSourceType(enum.StrEnum):
    """Where a node was ingested from (#61)."""

    pubmed = "pubmed"
    nice = "nice"
    # An authored guideline corpus standing in for NICE content, which is
    # licensed and could not be redistributed here (ADR-023). A separate value
    # rather than reusing ``nice``: a platform whose central claim is
    # first-class provenance cannot label authored text with a publisher that
    # did not publish it. Retained as a distinct value so a later syndication
    # grant swaps the connector without silently reclassifying existing rows.
    synthetic_guideline = "synthetic_guideline"


class KnowledgeStatus(enum.StrEnum):
    """Lifecycle state — the reason supersession is queryable rather than inferred.

    Withdrawn guidance must never be as retrievable as current guidance, so
    status is a first-class column and a Qdrant payload field (ADR-021 §4.4),
    filtered *before* vector search rather than after.
    """

    active = "active"
    superseded = "superseded"
    withdrawn = "withdrawn"
    draft = "draft"


class UpdateCadence(enum.StrEnum):
    """How often the upstream source changes, classified at ingestion.

    Drives re-ingestion scheduling: a ``live`` source needs re-checking, a
    ``static`` published article does not.
    """

    static = "static"
    periodic = "periodic"
    live = "live"


class KnowledgeEdgeType(enum.StrEnum):
    """The closed relationship set (ADR-021).

    Deliberately small. Every new edge type is a schema migration and an
    extraction-prompt change, which is the point: an open-ended relation
    vocabulary is what makes most extracted graphs unusable.
    """

    SUPERSEDES = "SUPERSEDES"        # newer guidance replaces older
    DEFINED_BY = "DEFINED_BY"        # a term is defined by a node
    EXCEPTION_TO = "EXCEPTION_TO"    # a clause exempts a rule
    CITES = "CITES"                  # a source references another
    RELATED_TO = "RELATED_TO"        # weak, untyped association


class KnowledgeNode(UUIDMixin, TimestampMixin, Base):
    """One structural unit of the corpus, typed and provenanced."""

    __tablename__ = "knowledge_nodes"
    __table_args__ = (
        # Retrieval almost always filters "active guidance from source X"
        # together, so the composite serves the common path in one index.
        Index("ix_knowledge_nodes_status_source", "status", "source_type"),
        Index("ix_knowledge_nodes_effective_date", "effective_date"),
        Index("ix_knowledge_nodes_external_ref", "external_ref"),
        # Re-ingestion (#61) reads every node already held for a source
        # document before deciding what to update. Not unique: one guideline
        # yields many nodes, all sharing its source_id.
        Index("ix_knowledge_nodes_source", "source_type", "source_id"),
    )

    node_type: Mapped[KnowledgeNodeType] = mapped_column(
        Enum(KnowledgeNodeType, name="knowledge_node_type")
    )
    title: Mapped[str] = mapped_column(String(512))
    text: Mapped[str] = mapped_column(Text)

    # --- provenance ---
    # Stable identifier of the *source document* (a PMID, a NICE guideline id).
    # Shared by every node extracted from that document, so it identifies what
    # re-ingestion should reconcile against rather than uniquely keying a node —
    # ``heading_path`` is what distinguishes structural units within a document.
    source_id: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        Enum(KnowledgeSourceType, name="knowledge_source_type")
    )
    # Human-resolvable reference for citation display (PMID / guideline id).
    external_ref: Mapped[str | None] = mapped_column(String(255))
    # Who published it — journal title for an article, issuing body for a
    # guideline. Deliberately not folded into ``heading_path`` (a structural
    # breadcrumb) or ``external_ref`` (a single resolvable id): a rendered
    # citation needs the venue alongside the id, and a clinician reading
    # "supported by [J Cardiac Failure Res, 2026]" is being told something the
    # PMID alone does not tell them. For the authored corpus it is also what
    # makes the content's provenance visible at the point of citation.
    source_venue: Mapped[str | None] = mapped_column(String(512))
    effective_date: Mapped[date | None] = mapped_column(Date)

    # --- lifecycle and authority ---
    # Deliberately no default. Defaulting to ``active`` would mean any writer
    # that forgets the field silently publishes fully retrievable guidance;
    # required-and-NOT-NULL turns the same mistake into an insert error at
    # ingestion, which is the failure direction ADR-021 asks for.
    status: Mapped[KnowledgeStatus] = mapped_column(
        Enum(KnowledgeStatus, name="knowledge_status")
    )
    # Source quality tier, lower = more authoritative. Consumed by the ranking
    # layer in Sprint 4 (ADR-017); stored now so ingestion never has to be re-run
    # to backfill it.
    authority_tier: Mapped[int | None] = mapped_column(SmallInteger)
    category: Mapped[list[str] | None] = mapped_column(JsonB)
    update_cadence: Mapped[UpdateCadence] = mapped_column(
        Enum(UpdateCadence, name="knowledge_update_cadence"),
        default=UpdateCadence.static,
    )
    # Structural breadcrumb from chunking, e.g. "Management > Adults > Dosing".
    # Retained so a retrieved recommendation can be shown in context rather than
    # as an orphaned paragraph.
    heading_path: Mapped[str | None] = mapped_column(Text)

    outgoing_edges: Mapped[list["KnowledgeEdge"]] = relationship(
        back_populates="from_node",
        foreign_keys="KnowledgeEdge.from_node_id",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["KnowledgeEdge"]] = relationship(
        back_populates="to_node",
        foreign_keys="KnowledgeEdge.to_node_id",
        cascade="all, delete-orphan",
    )


class KnowledgeEdge(UUIDMixin, TimestampMixin, Base):
    """A typed, provenanced relationship between two knowledge nodes."""

    __tablename__ = "knowledge_edges"
    __table_args__ = (
        # One edge of a given type per ordered pair: re-running extraction over
        # an unchanged document must not multiply the graph.
        UniqueConstraint(
            "from_node_id", "to_node_id", "edge_type", name="uq_knowledge_edge"
        ),
        # An extractor that emits a confidence outside [0, 1] is malfunctioning,
        # and a malfunctioning extractor should fail at ingestion rather than
        # quietly poison every downstream ranking that reads the column.
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_knowledge_edge_confidence",
        ),
    )

    from_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True
    )
    to_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True
    )
    edge_type: Mapped[KnowledgeEdgeType] = mapped_column(
        Enum(KnowledgeEdgeType, name="knowledge_edge_type"), index=True
    )
    # Extractor confidence. NULL for edges asserted by ingestion metadata rather
    # than inferred by a model (e.g. a CITES edge read from a reference list).
    confidence: Mapped[float | None] = mapped_column(Float)
    # Model id + prompt version, e.g. "claude-haiku-4-5/extract-v1" (ADR-022).
    # NULL for the same non-inferred case as ``confidence``.
    extracted_by: Mapped[str | None] = mapped_column(String(128))

    from_node: Mapped["KnowledgeNode"] = relationship(
        back_populates="outgoing_edges", foreign_keys=[from_node_id]
    )
    to_node: Mapped["KnowledgeNode"] = relationship(
        back_populates="incoming_edges", foreign_keys=[to_node_id]
    )
