"""The four typed retrieval tools (#64) — what makes this querying, not searching.

Naive RAG has one verb: embed the question, take the top *k*. That collapses
four genuinely different requests into one, and three of them come out wrong.
"What replaced this guideline?" is a graph walk. "Active cardiology guidance
since 2024" is a filter. "What is this recommendation's effective date?" is a
field read. Only "what does the corpus say about X" is a similarity search, and
even that should run *inside* a filtered candidate set rather than over the
whole corpus (ADR-021 §4.4).

So there are four tools, each a plain function with a typed signature:

======================  =========================================  ==============
Tool                    Called when                                Returns
======================  =========================================  ==============
``vector_search``       Topical matching in a pre-filtered set      Ranked chunks
``structured_filter``   Narrowing by status, type, category, date  Node ids
``graph_traverse``      Following an explicit relationship         Nodes + path
``fact_lookup``         The query is a field read, not a search    One typed value
======================  =========================================  ==============

**Deliberately not LangGraph nodes.** No orchestration coupling at this layer,
so each tool is unit-testable in isolation and a retrieval regression is
attributable to one tool rather than buried inside an end-to-end score. The
planner (#65) composes them; it does not live here.

**No ranking here either.** ADR-017's stages — sparse retrieval, fusion,
cross-encoder re-ranking, temporal decay — are Sprint 4 and drop in as
additional steps around these tools. Sprint 3 is the knowledge layer: ranking
upgrades applied to an unstructured corpus only improve the ordering of results
that are already the wrong results.

``contradiction_check`` is out of scope by design (epic #58). With ``SUPERSEDES``
edges and a ``status`` field, the common conflict case is resolved structurally
at ingestion; revisit only if evaluation shows conflicts surviving that.
"""

import enum
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    KnowledgeEdgeType,
    KnowledgeNode,
    KnowledgeNodeType,
    KnowledgeSourceType,
    KnowledgeStatus,
)
from app.repositories.knowledge import (
    DEFAULT_TRAVERSAL_DEPTH,
    KnowledgeNodeRepository,
    TraversalDirection,
)
from app.services.embedding import EmbeddingProvider
from app.services.vector_store import KnowledgeVectorStore, SearchFilters, SearchHit

logger = logging.getLogger(__name__)

#: Nodes one ``structured_filter`` call will return. A filter with no bound is a
#: table scan wearing a function signature, and the planner's arguments are LLM
#: output — a missing filter should return a truncated set, never the corpus.
DEFAULT_FILTER_LIMIT = 200

#: Chunks one ``vector_search`` call will return before any Sprint 4 re-ranking.
DEFAULT_SEARCH_LIMIT = 10

#: Nodes one ``graph_traverse`` call will return.
DEFAULT_TRAVERSE_LIMIT = 50

#: Ceilings on caller-supplied limits. Every ``limit`` here may originate as
#: planner output, and an unclamped one is not a bound: ``limit=-1`` is an error
#: on PostgreSQL and *unbounded* on SQLite, so the guard would invert exactly
#: where it is needed.
MAX_FILTER_LIMIT = 1_000
MAX_SEARCH_LIMIT = 100
MAX_TRAVERSE_LIMIT = 500

#: Rows the category pre-pass will scan. ``category`` cannot be filtered in SQL
#: portably (see ``structured_filter``), so it is matched in Python over a
#: bounded, ordered scan rather than over the whole table. Ordered by authority
#: and recency like the main query, so the scan window holds the material worth
#: matching. If the corpus ever outgrows this, a JSONB containment index with a
#: PostgreSQL-only branch is the upgrade — worth doing once SQLite is no longer
#: the only other dialect in play.
CATEGORY_SCAN_LIMIT = 5_000


def _clamp(limit: int, ceiling: int) -> int:
    """Force a caller-supplied limit into ``[1, ceiling]``."""
    return max(1, min(limit, ceiling))


class FactAttribute(enum.StrEnum):
    """Fields ``fact_lookup`` will read.

    A closed set rather than ``getattr`` on a planner-supplied string. The
    argument arrives from an LLM, so an open attribute read is an arbitrary
    property read on an ORM object — which reaches relationships, dunders and
    lazy loads, and turns a "what is the effective date" tool into an
    unbounded introspection primitive. Adding a field here is deliberate.
    """

    title = "title"
    node_type = "node_type"
    status = "status"
    effective_date = "effective_date"
    source_id = "source_id"
    source_type = "source_type"
    source_venue = "source_venue"
    external_ref = "external_ref"
    authority_tier = "authority_tier"
    category = "category"
    heading_path = "heading_path"
    update_cadence = "update_cadence"


@dataclass(frozen=True, slots=True)
class NodeFilter:
    """Structural constraints for :func:`structured_filter`.

    ``status`` has no default, matching :class:`SearchFilters`. Defaulting it to
    ``active`` would look like the safe choice and is the wrong one: a caller
    that means "including superseded guidance" — which the supersession
    evaluation case does — would silently get filtered results and appear to
    pass. Every call site states what it wants.
    """

    node_type: Sequence[KnowledgeNodeType] | None = None
    status: Sequence[KnowledgeStatus] | None = None
    source_type: Sequence[KnowledgeSourceType] | None = None
    source_id: str | None = None
    category: Sequence[str] | None = None
    max_authority_tier: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None

    def to_search_filters(
        self, node_ids: Sequence[UUID] | None = None
    ) -> SearchFilters:
        """The Qdrant-side equivalent, so one narrowing serves both stores.

        ``node_type`` and ``source_id`` are absent from the vector payload and
        are dropped here — which is exactly why the planner runs
        ``structured_filter`` first and passes its ``node_ids`` through: the
        relational side resolves what the payload cannot express, and the
        vector side then searches only within that set.
        """
        return SearchFilters(
            status=self.status,
            source_type=self.source_type,
            category=self.category,
            node_ids=node_ids,
            max_authority_tier=self.max_authority_tier,
            effective_from=self.effective_from,
            effective_to=self.effective_to,
        )


@dataclass(frozen=True, slots=True)
class TraversalStep:
    """One hop of a traversal path, as the generation layer will cite it."""

    node_id: UUID
    edge_type: KnowledgeEdgeType | None


@dataclass(frozen=True, slots=True)
class GraphHit:
    """A node reached by traversal, with the route that reached it."""

    node: KnowledgeNode
    depth: int
    edge_type: KnowledgeEdgeType
    #: Start node first, reached node last. Carried because generation cites
    #: *why* a node was reached, not only that it was.
    path: tuple[UUID, ...]

    @property
    def steps(self) -> tuple[TraversalStep, ...]:
        """The path as steps, the first being the start node with no edge in."""
        return tuple(
            TraversalStep(
                node_id=node_id,
                # Only the final hop's edge type is known per hit — the shortest
                # path's last edge. Intermediate types would need the full edge
                # chain, which is a second query and which nothing yet consumes.
                edge_type=self.edge_type if index == len(self.path) - 1 else None,
            )
            for index, node_id in enumerate(self.path)
        )


@dataclass(frozen=True, slots=True)
class FactResult:
    """One field read, with whether the node existed at all.

    ``found`` is not ceremony. A bare ``None`` conflates "the planner named a
    node that does not exist" with "this guideline records no effective date",
    and those call for different behaviour from the generation layer: the first
    is a broken plan, the second is a fact worth stating.
    """

    found: bool
    value: object | None
    attribute: FactAttribute

    @property
    def is_null(self) -> bool:
        """The node exists but the field is unset."""
        return self.found and self.value is None


@dataclass(frozen=True, slots=True)
class FilterResult:
    """Node ids matching a structural filter, and whether the cap bit."""

    node_ids: tuple[UUID, ...]
    truncated: bool = False

    def __len__(self) -> int:
        return len(self.node_ids)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Ranked chunks plus the node ids they resolve to."""

    hits: tuple[SearchHit, ...] = ()
    #: True when a pre-filter matched nothing, so no vector query was issued.
    #: Distinct from "searched and found nothing": the first is a filter that
    #: was too narrow and the second is a corpus that has no answer, and the
    #: generation layer must abstain differently for each.
    empty_candidate_set: bool = False

    @property
    def node_ids(self) -> tuple[UUID, ...]:
        """Distinct node ids, in rank order."""
        seen: dict[UUID, None] = {}
        for hit in self.hits:
            seen.setdefault(hit.node_id, None)
        return tuple(seen)


async def structured_filter(
    session: AsyncSession,
    filters: NodeFilter,
    *,
    limit: int = DEFAULT_FILTER_LIMIT,
) -> FilterResult:
    """Node ids matching structural constraints. No text, no vectors.

    The tool that runs *before* search rather than after it. Post-filtering asks
    for the top *k* by similarity and discards what fails the filter, so a query
    whose best matches are all superseded returns almost nothing and the current
    recommendation ranked fortieth is never seen. Pre-filtering searches within
    the matching set.

    Ordered by authority then recency, so a truncated result keeps the most
    authoritative and most current guidance rather than an arbitrary slice.
    ``truncated`` is reported because a silently cut candidate set makes a
    downstream search look like it found nothing.
    """
    limit = _clamp(limit, MAX_FILTER_LIMIT)

    conditions = []
    if filters.node_type is not None:
        # ``is not None`` rather than truthiness: an explicitly empty
        # sequence means "nothing matches", and treating it as "no
        # filter" would widen the result to the whole corpus — on the
        # status field, that returns withdrawn guidance.
        conditions.append(KnowledgeNode.node_type.in_(list(filters.node_type)))
    if filters.status is not None:
        # ``is not None`` rather than truthiness: an explicitly empty
        # sequence means "nothing matches", and treating it as "no
        # filter" would widen the result to the whole corpus — on the
        # status field, that returns withdrawn guidance.
        conditions.append(KnowledgeNode.status.in_(list(filters.status)))
    if filters.source_type is not None:
        # ``is not None`` rather than truthiness: an explicitly empty
        # sequence means "nothing matches", and treating it as "no
        # filter" would widen the result to the whole corpus — on the
        # status field, that returns withdrawn guidance.
        conditions.append(KnowledgeNode.source_type.in_(list(filters.source_type)))
    if filters.source_id:
        conditions.append(KnowledgeNode.source_id == filters.source_id)
    if filters.max_authority_tier is not None:
        # Lower tier means more authoritative, so a ceiling is an upper bound.
        # NULL is excluded rather than treated as unbounded: an unrated source
        # is not evidence of authority, and a tier ceiling is asked for when the
        # caller wants to *exclude* weak sources.
        conditions.append(KnowledgeNode.authority_tier.is_not(None))
        conditions.append(KnowledgeNode.authority_tier <= filters.max_authority_tier)
    if filters.effective_from:
        conditions.append(KnowledgeNode.effective_date >= filters.effective_from)
    if filters.effective_to:
        conditions.append(KnowledgeNode.effective_date <= filters.effective_to)

    order = (
        # NULL tiers and dates last without relying on dialect NULL ordering,
        # so a truncated result keeps the most authoritative and most current
        # guidance rather than an arbitrary slice.
        KnowledgeNode.authority_tier.is_(None),
        KnowledgeNode.authority_tier,
        KnowledgeNode.effective_date.is_(None),
        KnowledgeNode.effective_date.desc(),
        KnowledgeNode.id,
    )

    if filters.category is not None:
        # ``category`` is JSONB on PostgreSQL and plain JSON on the SQLite the
        # suite runs on, and the containment operators differ between them. The
        # column holds a handful of tags per node, so it is matched in Python
        # rather than behind a dialect fork of which only one branch would ever
        # be exercised.
        #
        # Bounded and single-pass: the scan is ordered and capped, and the ids
        # are consumed directly instead of being re-issued as a literal ``IN``
        # list — which on a large corpus would both defeat this module's own
        # no-unbounded-query rule and run into PostgreSQL's bind-parameter
        # ceiling.
        wanted = set(filters.category)
        rows = await session.execute(
            select(KnowledgeNode.id, KnowledgeNode.category)
            .where(*conditions)
            .order_by(*order)
            .limit(CATEGORY_SCAN_LIMIT)
        )
        matched = [
            node_id
            for node_id, category in rows.all()
            if wanted.intersection(category or ())
        ]
        return FilterResult(
            node_ids=tuple(matched[:limit]), truncated=len(matched) > limit
        )

    stmt = select(KnowledgeNode.id).where(*conditions)

    result = await session.execute(
        stmt.order_by(*order).limit(limit + 1)
    )
    node_ids = list(result.scalars().all())
    truncated = len(node_ids) > limit
    return FilterResult(node_ids=tuple(node_ids[:limit]), truncated=truncated)


async def vector_search(
    query: str,
    *,
    store: KnowledgeVectorStore,
    embedder: EmbeddingProvider,
    filters: SearchFilters | None = None,
    node_ids: Sequence[UUID] | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> SearchResult:
    """Topical search with structural constraints applied **by Qdrant**.

    ``node_ids`` narrows to a candidate set produced by
    :func:`structured_filter`. It is merged into the Qdrant filter rather than
    applied to the results, keeping the guarantee that filtering precedes search
    all the way down: a candidate set intersected afterwards would reintroduce
    exactly the post-filtering failure ADR-021 §4.4 exists to prevent.

    An **empty** candidate set short-circuits. Passing it to Qdrant as "match
    any of nothing" would be an unfiltered search over the whole corpus — the
    single most dangerous way for this to fail, because the caller asked for a
    narrowed search and would receive an unnarrowed one that looks fine.
    """
    limit = _clamp(limit, MAX_SEARCH_LIMIT)

    # Both ways an empty candidate set can arrive: as the parameter, and folded
    # into ``filters``. The second is the one that bites — ``SearchFilters``
    # tests its sequences for truthiness, so an empty ``node_ids`` there emits
    # *no* Qdrant condition at all and the "narrowed" search silently becomes a
    # corpus-wide one. Checked here rather than relied upon downstream.
    if (node_ids is not None and not node_ids) or (
        filters is not None and filters.node_ids is not None and not filters.node_ids
    ):
        logger.debug("vector_search short-circuited: candidate set is empty")
        return SearchResult(empty_candidate_set=True)

    if node_ids is not None:
        base = filters or SearchFilters()
        existing = set(base.node_ids or ())
        merged = (
            [n for n in node_ids if n in existing]
            if existing
            else list(node_ids)
        )
        if not merged:
            # Two disjoint candidate sets. An intersection of nothing is not a
            # licence to search everything.
            return SearchResult(empty_candidate_set=True)
        filters = SearchFilters(
            status=base.status,
            source_type=base.source_type,
            category=base.category,
            node_ids=merged,
            max_authority_tier=base.max_authority_tier,
            effective_from=base.effective_from,
            effective_to=base.effective_to,
        )

    vectors = await embedder.embed([query])
    hits = await store.search(vectors[0], filters=filters, limit=limit)
    return SearchResult(hits=tuple(hits))


async def graph_traverse(
    session: AsyncSession,
    node_id: UUID,
    *,
    edge_type: KnowledgeEdgeType | None,
    hops: int = DEFAULT_TRAVERSAL_DEPTH,
    direction: TraversalDirection = TraversalDirection.outgoing,
    limit: int = DEFAULT_TRAVERSE_LIMIT,
) -> list[GraphHit]:
    """Follow an explicit relationship. Returns the nodes **and the path**.

    The tool a similarity search cannot stand in for. "What supersedes this?"
    is an incoming ``SUPERSEDES`` walk, and no amount of embedding quality turns
    it into one — the answer is a property of the data model, not of the text.

    The path is returned, not just the endpoint, because generation has to cite
    *why* a node was reached. "Superseded by the 2026 edition" is checkable;
    a node appearing in the context with no stated route is not.

    ``edge_type`` is required, not defaulted, so following every relationship is
    an explicit choice rather than what you get by forgetting the argument. Depth
    is clamped and the result size bounded by the repository, since both
    arguments may originate as planner output.
    """
    limit = _clamp(limit, MAX_TRAVERSE_LIMIT)
    repository = KnowledgeNodeRepository(session)
    hits = await repository.traverse(
        node_id, edge_type=edge_type, hops=hops, direction=direction, limit=limit
    )
    return [
        GraphHit(
            node=hit.node, depth=hit.depth, edge_type=hit.edge_type, path=hit.path
        )
        for hit in hits
    ]


async def fact_lookup(
    session: AsyncSession, node_id: UUID, attribute: FactAttribute
) -> FactResult:
    """Read one field off one node. Not a search.

    Separate from ``vector_search`` because "when did this guideline take
    effect?" has an exact answer that a similarity search can only approximate,
    and approximating a date in clinical decision support is worse than not
    answering.

    ``attribute`` is a :class:`FactAttribute`, so the readable surface is a
    closed set rather than whatever string the planner produced.

    Returns a :class:`FactResult` rather than a bare value, because ``None``
    alone cannot distinguish "no such node" from "this node has no recorded
    effective date" — and generation has to abstain differently for each. The
    first means the planner supplied an id that does not exist; the second is a
    real, citable fact about the source.
    """
    attribute = FactAttribute(attribute)
    node = await session.get(KnowledgeNode, node_id)
    if node is None:
        return FactResult(found=False, value=None, attribute=attribute)
    return FactResult(
        found=True, value=getattr(node, attribute.value), attribute=attribute
    )
