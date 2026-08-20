"""Qdrant collection and filtered search (#62).

The payload is the whole point of this module. ADR-021 §4.4 requires that
structural filtering run **before** vector search, as a Qdrant filter applied
alongside the query vector — not as a post-hoc pass over the results.

The difference is not stylistic. Post-filtering asks for the top *k* by
similarity and then discards the ones that fail the filter, so a query whose
best matches are all superseded returns almost nothing, and the current
recommendation that ranked 40th is never seen. Pre-filtering searches *within*
the matching set, so the top result is the best active match rather than
whatever survived. For clinical retrieval that is the difference between
answering with current guidance and answering with withdrawn guidance.

Every point carries ``node_id``, so a vector hit resolves back to a typed,
provenanced ``KnowledgeNode`` instead of being returned as bare text. Qdrant is
not the source of truth here (ADR-021): PostgreSQL is, and this is one tool the
planner may call.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from qdrant_client import AsyncQdrantClient, models

from app.models.knowledge import KnowledgeSourceType, KnowledgeStatus
from app.services.chunking import Chunk

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "knowledge_chunks"

#: Payload fields that must be indexed for a filter on them to be cheap. Exactly
#: the set ADR-021 §4.4 names. An unindexed payload filter still returns the
#: right answer in Qdrant, just by scanning — so a missing index here is a
#: latency bug that no correctness test would ever catch, which is why the set
#: is declared once and asserted on rather than left to call sites.
PAYLOAD_INDEXES: dict[str, models.PayloadSchemaType] = {
    "node_id": models.PayloadSchemaType.KEYWORD,
    "status": models.PayloadSchemaType.KEYWORD,
    "source_type": models.PayloadSchemaType.KEYWORD,
    "category": models.PayloadSchemaType.KEYWORD,
    "authority_tier": models.PayloadSchemaType.INTEGER,
    # Stored as a day ordinal rather than a date string. Range filtering on an
    # integer behaves identically in the embedded client the tests use and in a
    # server deployment, whereas datetime range support has varied by version —
    # and "guidance effective after X" must not be a query that works in one
    # environment and silently returns nothing in the other.
    "effective_date": models.PayloadSchemaType.INTEGER,
}

#: Human-readable copy of the effective date, alongside the ordinal. Never
#: filtered on; carried so a rendered citation does not need a second lookup.
EFFECTIVE_DATE_DISPLAY = "effective_date_iso"


@dataclass(frozen=True, slots=True)
class ChunkPayload:
    """Everything a chunk needs to be filtered on and cited from.

    Assembled from the ``KnowledgeNode`` at index time rather than joined at
    query time: a filter that needs a PostgreSQL round trip per candidate is not
    a pre-filter, and the whole point is that Qdrant can apply it itself.
    """

    node_id: UUID
    status: KnowledgeStatus
    source_type: KnowledgeSourceType
    category: list[str]
    authority_tier: int | None
    effective_date: date | None
    heading_path: str | None
    chunk_index: int
    text: str
    title: str | None = None
    external_ref: str | None = None
    source_venue: str | None = None

    def to_qdrant(self) -> dict[str, Any]:
        return {
            "node_id": str(self.node_id),
            "status": str(self.status),
            "source_type": str(self.source_type),
            "category": list(self.category or []),
            "authority_tier": self.authority_tier,
            "effective_date": (
                self.effective_date.toordinal() if self.effective_date else None
            ),
            EFFECTIVE_DATE_DISPLAY: (
                self.effective_date.isoformat() if self.effective_date else None
            ),
            "heading_path": self.heading_path,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "title": self.title,
            "external_ref": self.external_ref,
            "source_venue": self.source_venue,
        }


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Structural constraints applied by Qdrant alongside the vector query.

    ``status`` defaults to nothing rather than to ``active``. A default would be
    the safer-looking choice and is the wrong one: a caller that means "search
    everything, including superseded guidance" — the supersession evaluation
    case does — would silently get filtered results and appear to pass. The
    retrieval tool layer (#64) makes the choice explicit at each call site.
    """

    status: Sequence[KnowledgeStatus] | None = None
    source_type: Sequence[KnowledgeSourceType] | None = None
    category: Sequence[str] | None = None
    node_ids: Sequence[UUID] | None = None
    max_authority_tier: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None

    def to_qdrant(self) -> models.Filter | None:
        """The Qdrant filter, or None when nothing was constrained.

        Each sequence is tested with ``is not None`` rather than for
        truthiness. An explicitly empty sequence means "nothing matches", and
        treating it as "no constraint" would make a narrowing *widen* the
        result — on ``status``, that means a query filtered to active guidance
        silently returning withdrawn guidance. Qdrant renders an empty
        ``MatchAny`` as a condition nothing satisfies, which is the intended
        reading.
        """
        must: list[models.FieldCondition] = []

        if self.status is not None:
            must.append(
                models.FieldCondition(
                    key="status",
                    match=models.MatchAny(any=[str(s) for s in self.status]),
                )
            )
        if self.source_type is not None:
            must.append(
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchAny(any=[str(s) for s in self.source_type]),
                )
            )
        if self.category is not None:
            # MatchAny on a list-valued payload field matches when *any* element
            # matches — "cardiology or endocrinology", not "both".
            must.append(
                models.FieldCondition(
                    key="category", match=models.MatchAny(any=list(self.category))
                )
            )
        if self.node_ids is not None:
            must.append(
                models.FieldCondition(
                    key="node_id",
                    match=models.MatchAny(any=[str(n) for n in self.node_ids]),
                )
            )
        if self.max_authority_tier is not None:
            # Lower tier means more authoritative, so a ceiling is a range max.
            must.append(
                models.FieldCondition(
                    key="authority_tier",
                    range=models.Range(lte=self.max_authority_tier),
                )
            )
        if self.effective_from or self.effective_to:
            must.append(
                models.FieldCondition(
                    key="effective_date",
                    range=models.Range(
                        gte=(
                            self.effective_from.toordinal()
                            if self.effective_from
                            else None
                        ),
                        lte=(
                            self.effective_to.toordinal() if self.effective_to else None
                        ),
                    ),
                )
            )
        return models.Filter(must=must) if must else None


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A retrieved chunk, resolvable to the node it realises."""

    node_id: UUID
    score: float
    text: str
    heading_path: str | None
    chunk_index: int
    payload: dict[str, Any]


class KnowledgeVectorStore:
    """Qdrant-backed chunk index with a filterable payload."""

    def __init__(
        self,
        client: AsyncQdrantClient,
        *,
        collection: str = DEFAULT_COLLECTION,
        dimension: int,
    ) -> None:
        self._client = client
        self._collection = collection
        self._dimension = dimension

    @property
    def collection(self) -> str:
        return self._collection

    async def ensure_collection(self) -> bool:
        """Create the collection and its payload indexes. Idempotent.

        Returns True if the collection was created by this call. Safe to run on
        every startup and on every ingestion run — index creation is requested
        unconditionally because a collection created by an earlier version may
        predate one of the indexes, and a missing index degrades silently to a
        full scan rather than failing.
        """
        existing = await self._client.collection_exists(self._collection)
        if not existing:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(
                    size=self._dimension,
                    # Cosine: the chunk vectors are unit-normalised and only
                    # direction carries meaning. Changing this later invalidates
                    # every stored vector, so it is fixed at creation.
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info("created Qdrant collection %s", self._collection)

        for field_name, schema in PAYLOAD_INDEXES.items():
            try:
                await self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:  # noqa: BLE001 - index already present
                # Qdrant has no "create if not exists" for payload indexes and
                # signals a duplicate differently across client versions and
                # between the embedded and server backends. Re-requesting an
                # existing index is a no-op, so this is safe to swallow — and
                # `verify_indexes` is what actually asserts the end state.
                logger.debug("payload index %s already present", field_name)

        return not existing

    async def verify_indexes(self) -> set[str]:
        """Payload fields in :data:`PAYLOAD_INDEXES` that are *not* indexed.

        Exists because a missing payload index is invisible: filtering still
        returns correct results, just by scanning every point. Without an
        explicit check that regression would only ever show up as latency, long
        after the change that caused it.

        **Only meaningful against a real Qdrant server.** The embedded backend
        (``":memory:"`` / on-disk local mode) does not implement payload indexes
        at all — it warns "Payload indexes have no effect in the local Qdrant"
        and this method will report every field as missing there. It still
        applies the *filters* correctly, which is the behaviour the test suite
        proves; index presence is a production-deployment assertion. Call this
        at startup against the configured server, not in local development.
        """
        info = await self._client.get_collection(self._collection)
        present = set(getattr(info.config.params, "payload_schema", None) or {})
        if not present:
            present = set(getattr(info, "payload_schema", None) or {})
        return {field for field in PAYLOAD_INDEXES if field not in present}

    async def upsert_chunks(
        self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]],
        payloads: Sequence[ChunkPayload],
    ) -> int:
        """Index ``chunks``. Point ids are derived, so re-indexing overwrites.

        A chunk's identity is ``(node_id, chunk_index)``. Deriving the point id
        from that pair rather than generating a fresh UUID is what makes
        re-ingestion of an edited node replace its chunks instead of leaving the
        old text retrievable alongside the new — the vector-store equivalent of
        the idempotency the relational side already has (#61).
        """
        if not (len(chunks) == len(vectors) == len(payloads)):
            raise ValueError("chunks, vectors and payloads must be the same length")
        if not chunks:
            return 0

        points = [
            models.PointStruct(
                id=point_id(payload.node_id, chunk.chunk_index),
                vector=list(vector),
                payload=payload.to_qdrant(),
            )
            for chunk, vector, payload in zip(chunks, vectors, payloads, strict=True)
        ]
        await self._client.upsert(collection_name=self._collection, points=points)
        return len(points)

    async def search(
        self,
        vector: Sequence[float],
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """Vector search with structural constraints applied *by Qdrant*.

        The filter goes into the query, not over the results.
        """
        response = await self._client.query_points(
            collection_name=self._collection,
            query=list(vector),
            query_filter=filters.to_qdrant() if filters else None,
            limit=limit,
            with_payload=True,
        )
        hits: list[SearchHit] = []
        for point in response.points:
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    node_id=UUID(payload["node_id"]),
                    score=point.score,
                    text=payload.get("text", ""),
                    heading_path=payload.get("heading_path"),
                    chunk_index=payload.get("chunk_index", 0),
                    payload=payload,
                )
            )
        return hits

    async def delete_node(self, node_id: UUID) -> None:
        """Remove every chunk belonging to ``node_id``."""
        await self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="node_id", match=models.MatchValue(value=str(node_id))
                        )
                    ]
                )
            ),
        )


def point_id(node_id: UUID, chunk_index: int) -> str:
    """Stable point id for a chunk.

    A UUID5 over ``node_id:chunk_index`` — Qdrant point ids must be a UUID or an
    unsigned integer, and a derived UUID keeps the id reproducible without
    needing a lookup table to find a node's existing points.
    """
    return str(uuid5(NAMESPACE_URL, f"medintel:chunk:{node_id}:{chunk_index}"))
