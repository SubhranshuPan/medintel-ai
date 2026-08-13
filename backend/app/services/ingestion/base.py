"""Connector output types — what a source looks like before it is persisted.

A connector's job ends at a list of :class:`SourceDocument`. It does not touch
the session, so a connector can be exercised against a committed fixture with
no database and no network, and the persistence rules (idempotency, edge
resolution) live in exactly one place (:mod:`app.services.ingestion.runner`)
rather than being reimplemented per source.

Every field that decides retrievability later — ``status``, ``effective_date``,
``update_cadence``, ``authority_tier`` — is captured *here*, at ingestion. That
is the whole point of ADR-021: "which version is current" has to be a stored
fact, because it cannot be recovered at query time from text that was ingested
without it.
"""

from dataclasses import dataclass, field
from datetime import date

from app.models.knowledge import (
    KnowledgeNodeType,
    KnowledgeSourceType,
    KnowledgeStatus,
    UpdateCadence,
)


@dataclass(frozen=True, slots=True)
class Section:
    """A labelled span within a source document.

    PubMed structured abstracts (``BACKGROUND``/``METHODS``/``RESULTS``) and
    guideline sections both arrive as these. Carried through ingestion unsplit:
    the structure-aware chunker (#62) consumes them, so the boundaries the
    publisher authored are the boundaries chunking respects rather than ones a
    token counter invents.
    """

    heading: str | None
    text: str


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """One fetched structural unit, mapping 1:1 to a ``KnowledgeNode``.

    Identity is ``(source_type, source_id, heading_path)``. A PubMed article is
    one document with no ``heading_path``; a guideline is one document for the
    guideline itself plus one per recommendation, all sharing the guideline's
    ``source_id`` and distinguished by their heading path. Re-ingestion
    reconciles on that triple, which is why re-running is an update rather than
    a duplicate.
    """

    source_id: str
    source_type: KnowledgeSourceType
    node_type: KnowledgeNodeType
    title: str
    text: str
    status: KnowledgeStatus
    update_cadence: UpdateCadence
    external_ref: str | None = None
    # Journal title for an article, issuing body for a guideline.
    source_venue: str | None = None
    effective_date: date | None = None
    authority_tier: int | None = None
    category: list[str] = field(default_factory=list)
    heading_path: str | None = None
    sections: tuple[Section, ...] = ()

    # --- relationship metadata, asserted by the source rather than inferred ---
    # ``source_id`` values this document cites (PMIDs from a reference list) and
    # the one it replaces. Both become edges with NULL ``confidence`` and
    # ``extracted_by``, because no model was involved in reading them — that
    # distinction is what lets #63's extracted edges be re-validated later
    # without disturbing the ones the publisher stated outright.
    references: tuple[str, ...] = ()
    supersedes: str | None = None
