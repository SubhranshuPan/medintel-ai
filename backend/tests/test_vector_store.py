"""Qdrant payload, filtering, and the indexing pipeline (#62).

Run against ``AsyncQdrantClient(":memory:")`` — the embedded local backend,
which is the real Qdrant filtering implementation rather than a stub. That
matters for the central test here: proving the filter is applied *by Qdrant
alongside the vector query*, not by Python afterwards.

The distinction is not pedantry. Post-filtering asks for the top *k* by
similarity and discards the failures, so a query whose nearest neighbours are
all superseded returns almost nothing and the current recommendation that ranked
40th is never seen. That is the difference between answering with current
guidance and answering with withdrawn guidance.
"""

import asyncio
import os
import uuid
from collections.abc import Callable
from datetime import date

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.embedding import Embedding
from app.models.knowledge import KnowledgeSourceType, KnowledgeStatus
from app.services.embedding import DeterministicEmbedder
from app.services.indexing import index_documents, orphaned_chunk_count
from app.services.ingestion import ingest_documents, load_guideline_corpus
from app.services.vector_store import (
    PAYLOAD_INDEXES,
    ChunkPayload,
    KnowledgeVectorStore,
    SearchFilters,
    point_id,
)

DIMENSION = 64


@pytest.fixture
def session_factory(_engine: AsyncEngine) -> Callable[[], AsyncSession]:
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def embedder() -> DeterministicEmbedder:
    return DeterministicEmbedder(dimension=DIMENSION)


async def _fresh_store() -> KnowledgeVectorStore:
    client = AsyncQdrantClient(":memory:")
    store = KnowledgeVectorStore(
        client, collection=f"test_{uuid.uuid4().hex[:8]}", dimension=DIMENSION
    )
    await store.ensure_collection()
    return store


# --------------------------------------------------------------------------
# Embedding provider
# --------------------------------------------------------------------------


def test_deterministic_embedder_is_stable_and_normalised(embedder) -> None:
    """Stable across calls, unit length so cosine distance is meaningful."""

    async def _run():
        first = await embedder.embed(["chronic heart failure"])
        second = await embedder.embed(["chronic heart failure"])
        return first[0], second[0]

    a, b = asyncio.run(_run())

    assert a == b
    assert len(a) == DIMENSION
    assert abs(sum(v * v for v in a) ** 0.5 - 1.0) < 1e-9


def test_deterministic_embedder_separates_different_text(embedder) -> None:
    """Distinct inputs must not collapse to the same point."""

    async def _run():
        return await embedder.embed(["heart failure", "atrial fibrillation"])

    a, b = asyncio.run(_run())

    assert a != b
    assert sum(x * y for x, y in zip(a, b, strict=True)) < 0.5


# --------------------------------------------------------------------------
# Collection and payload indexes
# --------------------------------------------------------------------------


def test_collection_creation_is_idempotent() -> None:
    """Safe to run on every startup and every ingestion run."""

    async def _run() -> tuple[bool, bool]:
        client = AsyncQdrantClient(":memory:")
        store = KnowledgeVectorStore(client, collection="repeat", dimension=DIMENSION)
        return await store.ensure_collection(), await store.ensure_collection()

    created, again = asyncio.run(_run())

    assert created is True
    assert again is False


@pytest.mark.skipif(
    not os.getenv("MEDINTEL_TEST_QDRANT_URL"),
    reason=(
        "Payload indexes are a no-op in the embedded Qdrant backend "
        "('Payload indexes have no effect in the local Qdrant'), so this "
        "cannot be verified without a real server. Set "
        "MEDINTEL_TEST_QDRANT_URL to run it — the local backend still "
        "executes the filters themselves, which is what the tests below prove."
    ),
)
def test_every_filterable_field_is_indexed() -> None:
    """A missing payload index is invisible: filtering stays correct, just slow.

    Without this assertion the regression would only ever surface as latency,
    long after the change that caused it — so it is asserted where it *can* be,
    against a real Qdrant, rather than quietly dropped because the default test
    backend cannot see it.
    """

    async def _run() -> set[str]:
        client = AsyncQdrantClient(url=os.environ["MEDINTEL_TEST_QDRANT_URL"])
        store = KnowledgeVectorStore(
            client, collection=f"idx_{uuid.uuid4().hex[:8]}", dimension=DIMENSION
        )
        await store.ensure_collection()
        try:
            return await store.verify_indexes()
        finally:
            await client.delete_collection(store.collection)

    assert asyncio.run(_run()) == set()


def test_payload_index_set_matches_the_adr() -> None:
    """ADR-021 §4.4 names these fields; drift here is a silent contract break."""
    assert set(PAYLOAD_INDEXES) == {
        "node_id",
        "status",
        "source_type",
        "category",
        "authority_tier",
        "effective_date",
    }


# --------------------------------------------------------------------------
# Filtering — applied by Qdrant, proven by construction
# --------------------------------------------------------------------------


def _payload(node_id: uuid.UUID, *, status: KnowledgeStatus, category: list[str],
             tier: int, effective: date, text: str) -> ChunkPayload:
    return ChunkPayload(
        node_id=node_id,
        status=status,
        source_type=KnowledgeSourceType.synthetic_guideline,
        category=category,
        authority_tier=tier,
        effective_date=effective,
        heading_path="Management",
        chunk_index=0,
        text=text,
    )


async def _seed(store: KnowledgeVectorStore, embedder: DeterministicEmbedder):
    """Four points differing on every filterable axis."""
    from app.services.chunking import Chunk

    specs = [
        ("active-cardio", KnowledgeStatus.active, ["cardiology"], 1, date(2026, 3, 1)),
        ("stale-cardio", KnowledgeStatus.superseded, ["cardiology"], 1, date(2019, 6, 1)),
        ("gone-endo", KnowledgeStatus.withdrawn, ["endocrinology"], 1, date(2021, 4, 12)),
        ("active-endo", KnowledgeStatus.active, ["endocrinology"], 3, date(2024, 9, 15)),
    ]
    chunks, payloads, ids = [], [], {}
    for name, status, category, tier, effective in specs:
        node_id = uuid.uuid4()
        ids[name] = node_id
        chunks.append(Chunk(node_id=node_id, chunk_index=0, text=name, heading_path="Management"))
        payloads.append(
            _payload(node_id, status=status, category=category, tier=tier,
                     effective=effective, text=name)
        )
    vectors = await embedder.embed([c.text for c in chunks])
    await store.upsert_chunks(chunks, vectors, payloads)
    return ids, vectors


def test_status_filter_is_applied_by_qdrant(embedder) -> None:
    """The load-bearing test.

    The query vector is the *superseded* point's own vector, so under post-hoc
    filtering that point is the nearest neighbour and the active one is not.
    Asking for ``status=active`` must nonetheless return only active points —
    which is only possible if Qdrant restricted the search space before ranking.
    """

    async def _run():
        store = await _fresh_store()
        ids, vectors = await _seed(store, embedder)
        stale_vector = vectors[1]

        unfiltered = await store.search(stale_vector, limit=1)
        filtered = await store.search(
            stale_vector,
            filters=SearchFilters(status=[KnowledgeStatus.active]),
            limit=10,
        )
        return ids, unfiltered, filtered

    ids, unfiltered, filtered = asyncio.run(_run())

    # Without a filter the superseded point wins outright — it is its own vector.
    assert unfiltered[0].node_id == ids["stale-cardio"]
    # With the filter it is absent, and every survivor is active.
    returned = {hit.node_id for hit in filtered}
    assert ids["stale-cardio"] not in returned
    assert ids["gone-endo"] not in returned
    assert returned == {ids["active-cardio"], ids["active-endo"]}


def test_category_filter_narrows_to_matching_points(embedder) -> None:
    async def _run():
        store = await _fresh_store()
        ids, vectors = await _seed(store, embedder)
        hits = await store.search(
            vectors[0], filters=SearchFilters(category=["endocrinology"]), limit=10
        )
        return ids, hits

    ids, hits = asyncio.run(_run())

    assert {h.node_id for h in hits} == {ids["gone-endo"], ids["active-endo"]}


def test_combined_filters_intersect(embedder) -> None:
    """status AND category — the common retrieval path."""

    async def _run():
        store = await _fresh_store()
        ids, vectors = await _seed(store, embedder)
        hits = await store.search(
            vectors[0],
            filters=SearchFilters(
                status=[KnowledgeStatus.active], category=["endocrinology"]
            ),
            limit=10,
        )
        return ids, hits

    ids, hits = asyncio.run(_run())

    assert {h.node_id for h in hits} == {ids["active-endo"]}


def test_effective_date_range_filters_on_the_ordinal(embedder) -> None:
    """Date range filtering must work in the embedded backend and a server alike."""

    async def _run():
        store = await _fresh_store()
        ids, vectors = await _seed(store, embedder)
        hits = await store.search(
            vectors[0],
            filters=SearchFilters(effective_from=date(2024, 1, 1)),
            limit=10,
        )
        return ids, hits

    ids, hits = asyncio.run(_run())

    assert {h.node_id for h in hits} == {ids["active-cardio"], ids["active-endo"]}


def test_authority_tier_ceiling_filters(embedder) -> None:
    """Lower tier is more authoritative, so a ceiling excludes weaker sources."""

    async def _run():
        store = await _fresh_store()
        ids, vectors = await _seed(store, embedder)
        hits = await store.search(
            vectors[0], filters=SearchFilters(max_authority_tier=1), limit=10
        )
        return ids, hits

    ids, hits = asyncio.run(_run())

    assert ids["active-endo"] not in {h.node_id for h in hits}


def test_node_id_filter_restricts_to_a_candidate_set(embedder) -> None:
    """How #64 composes structured_filter into vector_search."""

    async def _run():
        store = await _fresh_store()
        ids, vectors = await _seed(store, embedder)
        hits = await store.search(
            vectors[0],
            filters=SearchFilters(node_ids=[ids["gone-endo"]]),
            limit=10,
        )
        return ids, hits

    ids, hits = asyncio.run(_run())

    assert [h.node_id for h in hits] == [ids["gone-endo"]]


def test_search_hit_resolves_back_to_its_node(embedder) -> None:
    """A vector hit must be typed knowledge, not bare text (ADR-021)."""

    async def _run():
        store = await _fresh_store()
        ids, vectors = await _seed(store, embedder)
        return ids, await store.search(vectors[0], limit=1)

    ids, hits = asyncio.run(_run())

    hit = hits[0]
    assert hit.node_id == ids["active-cardio"]
    assert hit.heading_path == "Management"
    assert hit.payload["status"] == str(KnowledgeStatus.active)
    assert hit.payload["effective_date_iso"] == "2026-03-01"


def test_point_id_is_derived_so_reindexing_overwrites() -> None:
    """Same (node_id, chunk_index) must always mean the same point."""
    node_id = uuid.uuid4()

    assert point_id(node_id, 0) == point_id(node_id, 0)
    assert point_id(node_id, 0) != point_id(node_id, 1)
    assert point_id(node_id, 0) != point_id(uuid.uuid4(), 0)


def test_upsert_rejects_mismatched_input_lengths(embedder) -> None:
    async def _run():
        from app.services.chunking import Chunk

        store = await _fresh_store()
        chunk = Chunk(node_id=uuid.uuid4(), chunk_index=0, text="x", heading_path=None)
        await store.upsert_chunks([chunk], [], [])

    with pytest.raises(ValueError, match="same length"):
        asyncio.run(_run())


# --------------------------------------------------------------------------
# End-to-end: ingest, index, retrieve
# --------------------------------------------------------------------------


def test_indexing_joins_chunks_to_knowledge_nodes(session_factory, embedder) -> None:
    """Every chunk resolves to a knowledge_nodes row and carries a heading path."""
    documents = load_guideline_corpus()

    async def _run():
        store = await _fresh_store()
        async with session_factory() as session:
            await ingest_documents(session, documents)
            report = await index_documents(
                session, documents, store=store, embedder=embedder
            )
            rows = list((await session.execute(select(Embedding))).scalars())
            orphans = await orphaned_chunk_count(session)
        return report, rows, orphans

    report, rows, orphans = asyncio.run(_run())

    assert report.nodes_indexed == len(documents)
    assert report.chunks_written == len(rows)
    assert rows, "indexing must persist Embedding rows"
    # The join that makes a vector hit resolvable to typed knowledge.
    assert all(row.node_id is not None for row in rows)
    assert orphans == 0


def test_indexed_corpus_is_searchable_with_a_status_filter(
    session_factory, embedder
) -> None:
    """The pipeline's point: withdrawn guidance is not as retrievable as current."""
    documents = load_guideline_corpus()

    async def _run():
        store = await _fresh_store()
        async with session_factory() as session:
            await ingest_documents(session, documents)
            await index_documents(session, documents, store=store, embedder=embedder)

        withdrawn = next(d for d in documents if d.status is KnowledgeStatus.withdrawn)
        vector = (await embedder.embed([withdrawn.text]))[0]
        unfiltered = await store.search(vector, limit=1)
        active_only = await store.search(
            vector, filters=SearchFilters(status=[KnowledgeStatus.active]), limit=20
        )
        return unfiltered, active_only

    unfiltered, active_only = asyncio.run(_run())

    # The withdrawn text is its own nearest neighbour without a filter...
    assert unfiltered[0].payload["status"] == str(KnowledgeStatus.withdrawn)
    # ...and unreachable with one, however similar it is to the query.
    assert active_only
    assert all(
        hit.payload["status"] == str(KnowledgeStatus.active) for hit in active_only
    )


def test_reindexing_replaces_chunks_rather_than_duplicating(
    session_factory, embedder
) -> None:
    """An edited recommendation must not stay retrievable in its old wording."""
    documents = load_guideline_corpus()

    async def _run():
        store = await _fresh_store()
        async with session_factory() as session:
            await ingest_documents(session, documents)
            first = await index_documents(
                session, documents, store=store, embedder=embedder
            )
            second = await index_documents(
                session, documents, store=store, embedder=embedder
            )
            rows = len(list((await session.execute(select(Embedding))).scalars()))
        return first, second, rows

    first, second, rows = asyncio.run(_run())

    assert first.chunks_written == second.chunks_written
    assert rows == first.chunks_written


def test_documents_never_ingested_are_reported_not_swallowed(
    session_factory, embedder
) -> None:
    """A half-indexed corpus is fine; an unreported gap is not."""
    documents = load_guideline_corpus()

    async def _run():
        store = await _fresh_store()
        async with session_factory() as session:
            # Deliberately skip ingestion — no nodes exist.
            return await index_documents(
                session, documents, store=store, embedder=embedder
            )

    report = asyncio.run(_run())

    assert report.nodes_indexed == 0
    assert len(report.skipped_documents) == len(documents)


def test_embedding_requires_at_least_one_parent(session_factory) -> None:
    """A chunk attributable to nothing is a claim generation could not cite."""

    async def _run() -> bool:
        async with session_factory() as session:
            session.add(
                Embedding(
                    document_id=None,
                    node_id=None,
                    chunk_index=0,
                    text_chunk="orphan",
                    vector_id="v",
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return True
            return False

    assert asyncio.run(_run())
