"""Persistence for ingested source documents — idempotent by construction.

Re-running ingestion over an unchanged corpus must be a no-op, and re-running it
over a *changed* corpus must update in place rather than accumulate a second
copy alongside the first. Both matter more here than they would elsewhere: a
duplicated guideline is two retrievable answers to a question that has one, and
a corpus that grows on every run makes "is this the current recommendation?"
unanswerable by exactly the mechanism meant to answer it.

Identity is ``(source_type, source_id, heading_path)`` — the triple the
connectors emit and ``ix_knowledge_nodes_source`` supports. Nothing is keyed on
text, so an editorial fix upstream updates a node instead of forking one.

Edges written here are only ones the *source states outright*: a ``SUPERSEDES``
declared by a guideline, a ``CITES`` read from a reference list. Both are stored
with NULL ``confidence`` and ``extracted_by``, which is what distinguishes them
from the model-inferred edges of #63 — those can be re-validated when the
extractor changes, and these should not be, because no extractor was involved.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    KnowledgeEdge,
    KnowledgeEdgeType,
    KnowledgeNode,
    KnowledgeSourceType,
)
from app.services.ingestion.base import SourceDocument

logger = logging.getLogger(__name__)

#: Node fields ingestion owns and will overwrite on re-run. ``heading_path`` is
#: absent deliberately — it is part of the identity key, so a change to it is a
#: different node, not an update to this one.
_MUTABLE_FIELDS = (
    "node_type",
    "title",
    "text",
    "status",
    "update_cadence",
    "external_ref",
    "source_venue",
    "effective_date",
    "authority_tier",
    "category",
)

NodeKey = tuple[KnowledgeSourceType, str, str | None]


@dataclass(slots=True)
class IngestionReport:
    """What one ingestion run actually changed.

    Reported rather than logged-and-forgotten so a scheduled re-ingestion can be
    asserted on: a run that reports ``created`` against a corpus that should be
    steady is a duplication bug, and it should be visible as a number.
    """

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    edges_created: int = 0
    #: References naming a document outside this corpus. Expected and benign —
    #: most cited PMIDs are not ingested — but counted, because a run where
    #: *every* reference is unresolved usually means the id format changed.
    unresolved_references: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def nodes_written(self) -> int:
        return self.created + self.updated


def _key(document: SourceDocument) -> NodeKey:
    return (document.source_type, document.source_id, document.heading_path)


def _apply(node: KnowledgeNode, document: SourceDocument) -> bool:
    """Copy ingestion-owned fields onto ``node``; True if anything changed."""
    changed = False
    for name in _MUTABLE_FIELDS:
        incoming = getattr(document, name)
        if getattr(node, name) != incoming:
            setattr(node, name, incoming)
            changed = True
    return changed


def _to_node(document: SourceDocument) -> KnowledgeNode:
    node = KnowledgeNode(
        source_id=document.source_id,
        source_type=document.source_type,
        heading_path=document.heading_path,
        **{name: getattr(document, name) for name in _MUTABLE_FIELDS},
    )
    return node


async def _load_existing(
    session: AsyncSession, documents: list[SourceDocument]
) -> dict[NodeKey, KnowledgeNode]:
    """Nodes already held for the source documents in this batch.

    Filtered on ``source_id`` alone and matched on the full triple in Python.
    A composite ``IN`` over row values would be tighter, but row-value support
    differs between PostgreSQL and the SQLite the test suite runs on, and the
    over-fetch is bounded by the number of source documents in the batch.
    """
    source_ids = {document.source_id for document in documents}
    if not source_ids:
        return {}
    result = await session.execute(
        select(KnowledgeNode).where(KnowledgeNode.source_id.in_(source_ids))
    )
    return {
        (node.source_type, node.source_id, node.heading_path): node
        for node in result.scalars()
    }


async def _write_edges(
    session: AsyncSession,
    documents: list[SourceDocument],
    nodes: dict[NodeKey, KnowledgeNode],
    report: IngestionReport,
) -> None:
    """Create the edges the sources declare, skipping ones already present.

    Only edges whose *both* endpoints are in the corpus are written — both
    columns are foreign keys, so a citation of an article we never ingested has
    nowhere to point. That is a deliberate property, not a limitation worked
    around: an edge to a node that does not exist would be a citation the
    generation step could not resolve to anything a clinician can read.
    """
    # A document-level id resolves to the node with no heading path — the
    # guideline or article itself, not one of its recommendations.
    by_source: dict[tuple[KnowledgeSourceType, str], KnowledgeNode] = {
        (source_type, source_id): node
        for (source_type, source_id, heading_path), node in nodes.items()
        if heading_path is None
    }

    wanted: set[tuple[str, str, KnowledgeEdgeType]] = set()
    pending: list[KnowledgeEdge] = []

    def _stage(
        from_node: KnowledgeNode, to_node: KnowledgeNode, edge_type: KnowledgeEdgeType
    ) -> None:
        if from_node.id == to_node.id:
            # A self-citation in a reference list is a data error upstream, and
            # a self-SUPERSEDES would make the node its own replacement.
            return
        triple = (str(from_node.id), str(to_node.id), edge_type)
        if triple in wanted:
            return
        wanted.add(triple)
        pending.append(
            KnowledgeEdge(
                from_node_id=from_node.id,
                to_node_id=to_node.id,
                edge_type=edge_type,
                # NULL: stated by the source, not inferred by a model.
                confidence=None,
                extracted_by=None,
            )
        )

    for document in documents:
        node = nodes.get(_key(document))
        if node is None:
            continue
        if document.supersedes:
            target = by_source.get((document.source_type, document.supersedes))
            if target is None:
                report.unresolved_references += 1
            else:
                _stage(node, target, KnowledgeEdgeType.SUPERSEDES)
        for reference in document.references:
            target = by_source.get((document.source_type, reference))
            if target is None:
                report.unresolved_references += 1
            else:
                _stage(node, target, KnowledgeEdgeType.CITES)

    if not pending:
        return

    # One query for every edge that could collide, rather than relying on the
    # unique constraint to reject duplicates: a constraint violation aborts the
    # surrounding transaction, which would take the whole run down on a re-run.
    node_ids = {node.id for node in nodes.values()}
    existing_result = await session.execute(
        select(
            KnowledgeEdge.from_node_id,
            KnowledgeEdge.to_node_id,
            KnowledgeEdge.edge_type,
        ).where(KnowledgeEdge.from_node_id.in_(node_ids))
    )
    existing = {
        (str(from_id), str(to_id), edge_type)
        for from_id, to_id, edge_type in existing_result.all()
    }

    for edge in pending:
        triple = (str(edge.from_node_id), str(edge.to_node_id), edge.edge_type)
        if triple in existing:
            continue
        session.add(edge)
        report.edges_created += 1


async def ingest_documents(
    session: AsyncSession, documents: list[SourceDocument]
) -> IngestionReport:
    """Upsert ``documents`` and their declared edges. Safe to re-run.

    Commits once at the end: a partially-applied corpus is worse than a failed
    run, because the failure is visible and the partial corpus is not.
    """
    report = IngestionReport()
    if not documents:
        return report

    nodes = await _load_existing(session, documents)

    for document in documents:
        key = _key(document)
        existing = nodes.get(key)
        if existing is None:
            node = _to_node(document)
            session.add(node)
            nodes[key] = node
            report.created += 1
        elif _apply(existing, document):
            report.updated += 1
        else:
            report.unchanged += 1

    # Ids are needed to build edges, and a new node has none until it reaches
    # the database. Flush rather than commit: still one transaction.
    await session.flush()

    await _write_edges(session, documents, nodes, report)
    await session.commit()

    logger.info(
        "corpus ingestion: %d created, %d updated, %d unchanged, %d edges, "
        "%d unresolved references",
        report.created,
        report.updated,
        report.unchanged,
        report.edges_created,
        report.unresolved_references,
    )
    return report
