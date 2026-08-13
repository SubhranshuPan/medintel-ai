"""Indexing pipeline (#62) — nodes to chunks to vectors, joined on ``node_id``.

Runs after ingestion (#61) and over the same ``SourceDocument`` objects, not
over the persisted rows. That is deliberate: the structural sections a connector
extracted (a structured abstract's labels, a guideline's numbered clauses) are
what the chunker splits on, and they are not a column on ``knowledge_nodes``.
Re-deriving them by parsing the persisted text back apart would be guessing at
structure that is still in hand.

The join is ``node_id``, carried in three places at once — the ``Embedding`` row,
the Qdrant payload, and the ``knowledge_nodes`` primary key. A vector hit
therefore resolves to typed, provenanced knowledge rather than bare text, and a
structural filter can run inside Qdrant rather than as a second pass in Python
(ADR-021 §4.4).

Re-indexing a node replaces its chunks rather than adding to them: Qdrant point
ids are derived from ``(node_id, chunk_index)``, and the node's ``Embedding``
rows are deleted before the new ones are written. Without both, an edited
recommendation would stay retrievable in its old wording alongside its new one —
the same duplication failure #61 guards against on the relational side.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import Embedding
from app.models.knowledge import KnowledgeNode
from app.services.chunking import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    Chunk,
    chunk_document,
)
from app.services.embedding import EmbeddingProvider
from app.services.ingestion.base import SourceDocument
from app.services.ingestion.runner import load_nodes_for_documents
from app.services.vector_store import ChunkPayload, KnowledgeVectorStore, point_id

logger = logging.getLogger(__name__)

#: Chunks embedded per provider call. Keeps one request bounded without making
#: a small corpus pay a round trip per chunk.
DEFAULT_EMBED_BATCH = 64


@dataclass(slots=True)
class IndexReport:
    """What one indexing run produced."""

    nodes_indexed: int = 0
    chunks_written: int = 0
    #: Chunks that came from token-splitting an oversized structural unit.
    #: Worth surfacing: a corpus where most chunks are split is one whose
    #: structure the chunker is failing to use, which is a chunking bug rather
    #: than a property of the source.
    split_chunks: int = 0
    #: Documents whose node could not be found — they were never ingested.
    skipped_documents: list[str] = field(default_factory=list)

    @property
    def structural_chunks(self) -> int:
        return self.chunks_written - self.split_chunks


def _payloads(node: KnowledgeNode, chunks: Sequence[Chunk]) -> list[ChunkPayload]:
    """Denormalise the node's filterable metadata onto each of its chunks."""
    return [
        ChunkPayload(
            node_id=node.id,
            status=node.status,
            source_type=node.source_type,
            category=list(node.category or []),
            authority_tier=node.authority_tier,
            effective_date=node.effective_date,
            heading_path=chunk.heading_path or node.heading_path,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            title=node.title,
            external_ref=node.external_ref,
            source_venue=node.source_venue,
        )
        for chunk in chunks
    ]


async def _embed_all(
    embedder: EmbeddingProvider, texts: Sequence[str], batch_size: int
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(await embedder.embed(texts[start : start + batch_size]))
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"embedding provider returned {len(vectors)} vectors for "
            f"{len(texts)} chunks"
        )
    return vectors


async def index_documents(
    session: AsyncSession,
    documents: Sequence[SourceDocument],
    *,
    store: KnowledgeVectorStore,
    embedder: EmbeddingProvider,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    batch_size: int = DEFAULT_EMBED_BATCH,
) -> IndexReport:
    """Chunk, embed and index ``documents`` that have already been ingested.

    A document with no corresponding node is recorded in ``skipped_documents``
    rather than raising: ingestion and indexing are separate runs, and a
    half-indexed corpus is more useful than an aborted one *provided* the gap is
    reported rather than swallowed.
    """
    report = IndexReport()
    if not documents:
        return report

    await store.ensure_collection()
    nodes = await load_nodes_for_documents(session, list(documents))

    all_chunks: list[Chunk] = []
    all_payloads: list[ChunkPayload] = []
    touched_node_ids: list = []

    for document in documents:
        node = nodes.get(
            (document.source_type, document.source_id, document.heading_path)
        )
        if node is None:
            report.skipped_documents.append(
                f"{document.source_type}:{document.source_id}"
            )
            continue

        chunks = chunk_document(
            document,
            node_id=node.id,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        if not chunks:
            continue

        all_chunks.extend(chunks)
        all_payloads.extend(_payloads(node, chunks))
        touched_node_ids.append(node.id)
        report.nodes_indexed += 1
        report.split_chunks += sum(1 for chunk in chunks if chunk.is_split)

    if not all_chunks:
        return report

    vectors = await _embed_all(embedder, [c.text for c in all_chunks], batch_size)

    # Clear the previous generation for exactly the nodes being rewritten,
    # before inserting — otherwise an edit that produces fewer chunks leaves the
    # surplus rows behind, still pointing at text that no longer exists.
    await session.execute(
        delete(Embedding).where(Embedding.node_id.in_(touched_node_ids))
    )
    for chunk, payload in zip(all_chunks, all_payloads, strict=True):
        session.add(
            Embedding(
                # No Document row: the corpus's unit of truth is the knowledge
                # node, and inventing a Document to satisfy a foreign key would
                # duplicate the node's title and text for nothing.
                document_id=None,
                node_id=payload.node_id,
                chunk_index=chunk.chunk_index,
                text_chunk=chunk.text,
                # Same derivation the Qdrant point uses, so a relational
                # row and its vector are findable from each other.
                vector_id=point_id(payload.node_id, chunk.chunk_index),
            )
        )

    report.chunks_written = await store.upsert_chunks(
        all_chunks, vectors, all_payloads
    )
    await session.commit()

    logger.info(
        "indexed %d nodes into %d chunks (%d split) in collection %s",
        report.nodes_indexed,
        report.chunks_written,
        report.split_chunks,
        store.collection,
    )
    return report


async def orphaned_chunk_count(session: AsyncSession) -> int:
    """``Embedding`` rows attached to neither a document nor a knowledge node.

    Should always be zero. A chunk that cannot be resolved back to something
    citable is a chunk the generation step could retrieve and then be unable to
    attribute, which is the failure mode this pillar exists to prevent.
    """
    result = await session.execute(
        select(Embedding).where(
            Embedding.node_id.is_(None), Embedding.document_id.is_(None)
        )
    )
    return len(list(result.scalars().all()))
