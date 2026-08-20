"""The four retrieval tools (#64), each isolated.

Isolation is the point of the layer and therefore of these tests. Every tool is
exercised on its own against a fixture graph, so a retrieval regression is
attributable to one tool rather than absorbed into an end-to-end score where any
of four things could be responsible.

Three properties get the most attention, because each is a place where a
plausible implementation is silently wrong:

* **Filtering precedes search.** Post-filtering returns the survivors of a
  similarity ranking; pre-filtering searches inside the matching set. The
  difference only shows up when the best matches are all excluded — the
  superseded-guidance case, which is exactly the clinical one.
* **An empty candidate set is not an unfiltered search.** The worst available
  failure is a narrowed query quietly becoming a corpus-wide one.
* **Traversal reports its route.** Generation cites *why* a node was reached, so
  a path that is computed and then dropped is a citation that cannot be made.

The embedder is :class:`DeterministicEmbedder` — hash-based and deliberately
without semantic meaning, so a filtering test cannot pass by accident because
two similar sentences happened to rank together.
"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import date

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.knowledge import (
    KnowledgeEdge,
    KnowledgeEdgeType,
    KnowledgeNode,
    KnowledgeNodeType,
    KnowledgeSourceType,
    KnowledgeStatus,
    UpdateCadence,
)
from app.repositories.knowledge import TraversalDirection
from app.services.embedding import DeterministicEmbedder
from app.services.retrieval import (
    MAX_SEARCH_LIMIT,
    MAX_TRAVERSE_LIMIT,
    FactAttribute,
    NodeFilter,
    fact_lookup,
    graph_traverse,
    structured_filter,
    vector_search,
)
from app.services.vector_store import ChunkPayload, KnowledgeVectorStore, SearchFilters

DIMENSION = 32


@pytest.fixture
def session_factory(_engine: AsyncEngine) -> Callable[[], AsyncSession]:
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def embedder() -> DeterministicEmbedder:
    return DeterministicEmbedder(DIMENSION)


def _node(title: str, **overrides) -> KnowledgeNode:
    defaults = {
        "node_type": KnowledgeNodeType.recommendation,
        "title": title,
        "text": f"Clinical guidance: {title}",
        "source_id": "MSGC-CHF-2026",
        "source_type": KnowledgeSourceType.synthetic_guideline,
        "status": KnowledgeStatus.active,
        "update_cadence": UpdateCadence.periodic,
        "effective_date": date(2026, 3, 1),
        "authority_tier": 1,
        "category": ["cardiology"],
    }
    return KnowledgeNode(**{**defaults, **overrides})


async def _seed(session: AsyncSession, nodes: list[KnowledgeNode]) -> None:
    session.add_all(nodes)
    await session.commit()


# --------------------------------------------------------------------------
# structured_filter
# --------------------------------------------------------------------------


def test_structured_filter_narrows_by_status(session_factory) -> None:
    """The narrowing that has to happen *before* search, not after it."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("Current", heading_path="a"),
                    _node("Old", heading_path="b", status=KnowledgeStatus.superseded),
                    _node("Gone", heading_path="c", status=KnowledgeStatus.withdrawn),
                ],
            )
            active = await structured_filter(
                session, NodeFilter(status=[KnowledgeStatus.active])
            )
            everything = await structured_filter(session, NodeFilter())
            return len(active), len(everything)

    active, everything = asyncio.run(_run())
    assert active == 1
    # No implicit status default: a caller that asks for everything gets
    # everything, including retired guidance the supersession cases need.
    assert everything == 3


def test_structured_filter_combines_constraints(session_factory) -> None:
    """Constraints intersect rather than accumulating into a union."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("Match", heading_path="a"),
                    _node("Wrong category", heading_path="b", category=["endocrine"]),
                    _node("Too old", heading_path="c", effective_date=date(2019, 1, 1)),
                    _node("Wrong type", heading_path="d",
                          node_type=KnowledgeNodeType.article),
                ],
            )
            result = await structured_filter(
                session,
                NodeFilter(
                    node_type=[KnowledgeNodeType.recommendation],
                    status=[KnowledgeStatus.active],
                    category=["cardiology"],
                    effective_from=date(2024, 1, 1),
                ),
            )
            titles = [
                (await session.get(KnowledgeNode, node_id)).title
                for node_id in result.node_ids
            ]
            return titles

    assert asyncio.run(_run()) == ["Match"]


def test_structured_filter_matches_any_supplied_category(session_factory) -> None:
    """A multi-value category filter is "or", matching the Qdrant side."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("Cardio", heading_path="a"),
                    _node("Endo", heading_path="b", category=["endocrine"]),
                    _node("Both", heading_path="c",
                          category=["cardiology", "endocrine"]),
                    _node("Neither", heading_path="d", category=["renal"]),
                ],
            )
            result = await structured_filter(
                session, NodeFilter(category=["cardiology", "endocrine"])
            )
            return len(result)

    assert asyncio.run(_run()) == 3


def test_structured_filter_reports_truncation(session_factory) -> None:
    """A silently cut candidate set makes a later search look like it found
    nothing, so truncation is reported rather than inferred from a count."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session, [_node(f"Rec {i}", heading_path=f"p{i}") for i in range(5)]
            )
            capped = await structured_filter(session, NodeFilter(), limit=3)
            whole = await structured_filter(session, NodeFilter(), limit=50)
            return capped, whole

    capped, whole = asyncio.run(_run())
    assert len(capped) == 3 and capped.truncated is True
    assert len(whole) == 5 and whole.truncated is False


def test_structured_filter_truncation_keeps_the_most_authoritative(
    session_factory,
) -> None:
    """A cut candidate set must not be an arbitrary slice.

    Ordering by authority then recency means the material a cap discards is the
    weakest and oldest, never the guideline the question was about.
    """

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("Weak", heading_path="a", authority_tier=5),
                    _node("Authoritative", heading_path="b", authority_tier=1),
                    _node("Unrated", heading_path="c", authority_tier=None),
                    _node("Middling", heading_path="d", authority_tier=3),
                ],
            )
            result = await structured_filter(session, NodeFilter(), limit=2)
            return [
                (await session.get(KnowledgeNode, node_id)).title
                for node_id in result.node_ids
            ]

    assert asyncio.run(_run()) == ["Authoritative", "Middling"]


def test_structured_filter_excludes_unrated_sources_under_a_tier_ceiling(
    session_factory,
) -> None:
    """An unrated source is not evidence of authority.

    A tier ceiling is asked for precisely when weak sources should be excluded,
    so treating NULL as "unbounded, therefore passing" would invert the request.
    """

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("Rated", heading_path="a", authority_tier=1),
                    _node("Unrated", heading_path="b", authority_tier=None),
                ],
            )
            result = await structured_filter(
                session, NodeFilter(max_authority_tier=2)
            )
            return [
                (await session.get(KnowledgeNode, node_id)).title
                for node_id in result.node_ids
            ]

    assert asyncio.run(_run()) == ["Rated"]


def test_structured_filter_returns_empty_rather_than_everything(
    session_factory,
) -> None:
    """A filter that matches nothing returns nothing.

    Worth asserting explicitly: the failure mode is a narrowing that collapses
    into an unfiltered query, which returns a full corpus and looks healthy.
    """

    async def _run():
        async with session_factory() as session:
            await _seed(session, [_node("Only", heading_path="a")])
            result = await structured_filter(
                session, NodeFilter(source_id="does-not-exist")
            )
            return result.node_ids

    assert asyncio.run(_run()) == ()


# --------------------------------------------------------------------------
# vector_search
# --------------------------------------------------------------------------


async def _store(embedder: DeterministicEmbedder) -> KnowledgeVectorStore:
    client = AsyncQdrantClient(":memory:")
    store = KnowledgeVectorStore(
        client, collection=f"test_{uuid.uuid4().hex}", dimension=embedder.dimension
    )
    await store.ensure_collection()
    return store


def _payload(node_id: uuid.UUID, text: str, **overrides) -> ChunkPayload:
    defaults = {
        "node_id": node_id,
        "status": KnowledgeStatus.active,
        "source_type": KnowledgeSourceType.synthetic_guideline,
        "category": ["cardiology"],
        "authority_tier": 1,
        "effective_date": date(2026, 3, 1),
        "heading_path": None,
        "chunk_index": 0,
        "text": text,
    }
    return ChunkPayload(**{**defaults, **overrides})


class _Chunk:
    """Minimal stand-in for the chunker's output — only ``chunk_index`` is read."""

    def __init__(self, chunk_index: int) -> None:
        self.chunk_index = chunk_index


async def _index(store, embedder, payloads: list[ChunkPayload]) -> None:
    vectors = await embedder.embed([p.text for p in payloads])
    chunks = [_Chunk(p.chunk_index) for p in payloads]
    await store.upsert_chunks(chunks, vectors, payloads)


def test_vector_search_applies_the_candidate_set_inside_qdrant(embedder) -> None:
    """The candidate set is part of the query, not a pass over the results.

    Intersecting afterwards would reintroduce the post-filtering failure the
    whole design exists to prevent: the best matches get discarded and what
    survives is whatever happened to rank below them.
    """

    async def _run():
        store = await _store(embedder)
        wanted, other = uuid.uuid4(), uuid.uuid4()
        await _index(
            store,
            embedder,
            [
                _payload(wanted, "ACE inhibitor and beta-blocker for HFrEF"),
                _payload(other, "Anticoagulation for atrial fibrillation"),
            ],
        )
        result = await vector_search(
            "heart failure therapy",
            store=store,
            embedder=embedder,
            node_ids=[wanted],
        )
        return result

    result = asyncio.run(_run())
    assert result.node_ids == (result.hits[0].node_id,)
    assert len(result.hits) == 1
    assert result.empty_candidate_set is False


def test_an_empty_candidate_set_never_becomes_an_unfiltered_search(
    embedder,
) -> None:
    """The most dangerous available failure, asserted directly.

    "Match any of nothing" is not a filter Qdrant can express, so passing an
    empty set through would search the whole corpus — the caller asked for a
    narrowed search and would receive an unnarrowed one that looks fine.
    """

    async def _run():
        store = await _store(embedder)
        await _index(
            store, embedder, [_payload(uuid.uuid4(), "Some clinical guidance")]
        )
        return await vector_search(
            "anything", store=store, embedder=embedder, node_ids=[]
        )

    result = asyncio.run(_run())
    assert result.hits == ()
    assert result.empty_candidate_set is True


def test_disjoint_candidate_sets_intersect_to_nothing(embedder) -> None:
    """Two filters that share no node search nothing, not everything."""

    async def _run():
        store = await _store(embedder)
        first, second = uuid.uuid4(), uuid.uuid4()
        await _index(
            store,
            embedder,
            [_payload(first, "First guidance"), _payload(second, "Second guidance")],
        )
        return await vector_search(
            "guidance",
            store=store,
            embedder=embedder,
            filters=SearchFilters(node_ids=[first]),
            node_ids=[second],
        )

    result = asyncio.run(_run())
    assert result.empty_candidate_set is True
    assert result.hits == ()


def test_vector_search_keeps_structural_filters_when_narrowing(embedder) -> None:
    """A candidate set must not replace the filters it arrives alongside.

    Superseded guidance inside the candidate set still has to be excluded by the
    status filter — dropping it while merging would make the narrowing step
    *widen* what is retrievable.
    """

    async def _run():
        store = await _store(embedder)
        current, retired = uuid.uuid4(), uuid.uuid4()
        await _index(
            store,
            embedder,
            [
                _payload(current, "Current first-line therapy"),
                _payload(
                    retired,
                    "Superseded first-line therapy",
                    status=KnowledgeStatus.superseded,
                ),
            ],
        )
        return await vector_search(
            "first-line therapy",
            store=store,
            embedder=embedder,
            filters=SearchFilters(status=[KnowledgeStatus.active]),
            node_ids=[current, retired],
        )

    result = asyncio.run(_run())
    assert len(result.hits) == 1
    assert result.hits[0].payload["status"] == str(KnowledgeStatus.active)


def test_searching_with_no_candidate_set_is_a_normal_empty_result(
    embedder,
) -> None:
    """"Filtered to nothing" and "searched and found nothing" differ.

    Generation must abstain differently for each — one is a filter that was too
    narrow, the other is a corpus with no answer — so the flag distinguishes
    them rather than both arriving as an empty list.
    """

    async def _run():
        store = await _store(embedder)
        return await vector_search("anything", store=store, embedder=embedder)

    result = asyncio.run(_run())
    assert result.hits == ()
    assert result.empty_candidate_set is False


def test_an_empty_candidate_set_folded_into_filters_also_short_circuits(
    embedder,
) -> None:
    """The same failure by the other route, which is the one that bites.

    ``SearchFilters`` is a value object a caller can build directly, and an
    empty ``node_ids`` there would emit no Qdrant condition at all — so the
    parameter-form guard alone would leave the corpus-wide search reachable.
    """

    async def _run():
        store = await _store(embedder)
        await _index(
            store,
            embedder,
            [_payload(uuid.uuid4(), f"Guidance {i}") for i in range(5)],
        )
        return await vector_search(
            "anything",
            store=store,
            embedder=embedder,
            filters=SearchFilters(node_ids=[]),
        )

    result = asyncio.run(_run())
    assert result.hits == ()
    assert result.empty_candidate_set is True


def test_an_empty_status_filter_matches_nothing_rather_than_everything(
    embedder,
) -> None:
    """An explicitly empty sequence is a constraint, not the absence of one.

    Read as "no filter", it would turn a query narrowed to active guidance into
    one that returns withdrawn guidance — the narrowing would *widen*.
    """

    async def _run():
        store = await _store(embedder)
        await _index(store, embedder, [_payload(uuid.uuid4(), "Current guidance")])
        return (
            await vector_search(
                "guidance",
                store=store,
                embedder=embedder,
                filters=SearchFilters(status=[]),
            ),
            await vector_search("guidance", store=store, embedder=embedder),
        )

    constrained, unconstrained = asyncio.run(_run())
    assert constrained.hits == ()
    assert len(unconstrained.hits) == 1


def test_an_empty_status_filter_matches_nothing_on_the_relational_side(
    session_factory,
) -> None:
    """The same rule, applied consistently across both stores."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("Active", heading_path="a"),
                    _node("Gone", heading_path="b", status=KnowledgeStatus.withdrawn),
                ],
            )
            return (
                len(await structured_filter(session, NodeFilter(status=[]))),
                len(await structured_filter(session, NodeFilter())),
            )

    empty, unset = asyncio.run(_run())
    assert empty == 0
    assert unset == 2


@pytest.mark.parametrize("limit", [-1, 0])
def test_a_nonsense_limit_is_clamped_rather_than_obeyed(
    session_factory, limit: int
) -> None:
    """Limits may originate as planner output, so they are clamped.

    ``limit=-1`` is an error on PostgreSQL and *unbounded* on SQLite, which
    would invert the guard exactly where it is needed.
    """

    async def _run():
        async with session_factory() as session:
            await _seed(
                session, [_node(f"Rec {i}", heading_path=f"p{i}") for i in range(4)]
            )
            filtered = await structured_filter(session, NodeFilter(), limit=limit)
            traversed = await graph_traverse(
                session, uuid.uuid4(), edge_type=None, limit=limit
            )
            return len(filtered), traversed

    filtered, traversed = asyncio.run(_run())
    assert filtered == 1  # clamped up to the floor of 1, not down to nothing
    assert traversed == []


def test_a_huge_limit_is_capped_at_the_ceiling(session_factory) -> None:
    """The other end of the clamp."""

    async def _run():
        async with session_factory() as session:
            await _seed(session, [_node("Only", heading_path="a")])
            return await structured_filter(session, NodeFilter(), limit=10**9)

    # Not an error, and not a corpus dump: the ceiling applies silently.
    assert len(asyncio.run(_run())) == 1
    assert MAX_SEARCH_LIMIT < MAX_TRAVERSE_LIMIT


def test_node_filter_converts_to_qdrant_filters(embedder) -> None:
    """One narrowing serves both stores, so a filter cannot drift between them."""
    node_id = uuid.uuid4()
    converted = NodeFilter(
        status=[KnowledgeStatus.active],
        category=["cardiology"],
        max_authority_tier=2,
        effective_from=date(2024, 1, 1),
    ).to_search_filters([node_id])

    assert converted.status == [KnowledgeStatus.active]
    assert converted.node_ids == [node_id]
    assert converted.to_qdrant() is not None


# --------------------------------------------------------------------------
# graph_traverse
# --------------------------------------------------------------------------


def _link(
    from_node: KnowledgeNode, to_node: KnowledgeNode, edge_type: KnowledgeEdgeType
) -> KnowledgeEdge:
    return KnowledgeEdge(
        from_node_id=from_node.id, to_node_id=to_node.id, edge_type=edge_type
    )


def test_graph_traverse_returns_the_path_not_just_the_endpoint(
    session_factory,
) -> None:
    """The property that makes a traversal citable.

    Generation has to say *why* a node was reached — "superseded by the 2026
    edition, which replaced the edition you asked about" — and a node arriving
    with no stated route cannot be presented that way.
    """

    async def _run():
        async with session_factory() as session:
            first = _node("2019 edition", heading_path="a")
            second = _node("2022 edition", heading_path="b")
            third = _node("2026 edition", heading_path="c")
            await _seed(session, [first, second, third])
            session.add_all(
                [
                    _link(second, first, KnowledgeEdgeType.SUPERSEDES),
                    _link(third, second, KnowledgeEdgeType.SUPERSEDES),
                ]
            )
            await session.commit()

            hits = await graph_traverse(
                session,
                first.id,
                edge_type=KnowledgeEdgeType.SUPERSEDES,
                direction=TraversalDirection.incoming,
                hops=3,
            )
            return first.id, second.id, third.id, hits

    first_id, second_id, third_id, hits = asyncio.run(_run())

    assert [hit.node.title for hit in hits] == ["2022 edition", "2026 edition"]
    # Every path starts at the node asked about and ends at the node reached.
    assert hits[0].path == (first_id, second_id)
    assert hits[1].path == (first_id, second_id, third_id)
    assert [hit.depth for hit in hits] == [1, 2]
    assert all(hit.path[0] == first_id for hit in hits)
    assert all(hit.path[-1] == hit.node.id for hit in hits)


def test_traversal_steps_expose_the_route_for_citation(session_factory) -> None:
    """The path rendered as hops, which is the shape a citation needs."""

    async def _run():
        async with session_factory() as session:
            rule = _node("Rule", heading_path="a")
            exception = _node("Exception", heading_path="b")
            await _seed(session, [rule, exception])
            session.add(_link(exception, rule, KnowledgeEdgeType.EXCEPTION_TO))
            await session.commit()
            hits = await graph_traverse(
                session,
                rule.id,
                edge_type=KnowledgeEdgeType.EXCEPTION_TO,
                direction=TraversalDirection.incoming,
            )
            return hits[0].steps

    steps = asyncio.run(_run())
    assert len(steps) == 2
    # The start node was not reached by any edge.
    assert steps[0].edge_type is None
    assert steps[-1].edge_type is KnowledgeEdgeType.EXCEPTION_TO


def test_graph_traverse_respects_the_depth_limit(session_factory) -> None:
    """A hop budget is a hop budget, including when it comes from a planner."""

    async def _run():
        async with session_factory() as session:
            chain = [_node(f"Node {i}", heading_path=f"p{i}") for i in range(5)]
            await _seed(session, chain)
            session.add_all(
                [
                    _link(chain[i], chain[i + 1], KnowledgeEdgeType.CITES)
                    for i in range(4)
                ]
            )
            await session.commit()
            shallow = await graph_traverse(
                session, chain[0].id, edge_type=KnowledgeEdgeType.CITES, hops=2
            )
            deep = await graph_traverse(
                session, chain[0].id, edge_type=KnowledgeEdgeType.CITES, hops=4
            )
            return len(shallow), len(deep), max(h.depth for h in shallow)

    shallow, deep, max_depth = asyncio.run(_run())
    assert shallow == 2
    assert deep == 4
    assert max_depth == 2


def test_graph_traverse_on_an_isolated_node_returns_nothing(
    session_factory,
) -> None:
    """An empty result is a legitimate answer, not an error to raise on."""

    async def _run():
        async with session_factory() as session:
            lonely = _node("Unconnected", heading_path="a")
            await _seed(session, [lonely])
            return await graph_traverse(
                session, lonely.id, edge_type=KnowledgeEdgeType.SUPERSEDES
            )

    assert asyncio.run(_run()) == []


def test_graph_traverse_on_an_unknown_node_returns_nothing(
    session_factory,
) -> None:
    """A planner-supplied id that does not exist must not raise."""

    async def _run():
        async with session_factory() as session:
            return await graph_traverse(session, uuid.uuid4(), edge_type=None)

    assert asyncio.run(_run()) == []


def test_graph_traverse_filters_by_edge_type(session_factory) -> None:
    """"What supersedes this" must not also return what merely cites it."""

    async def _run():
        async with session_factory() as session:
            subject = _node("Subject", heading_path="a")
            replacement = _node("Replacement", heading_path="b")
            citation = _node("Citation", heading_path="c")
            await _seed(session, [subject, replacement, citation])
            session.add_all(
                [
                    _link(replacement, subject, KnowledgeEdgeType.SUPERSEDES),
                    _link(citation, subject, KnowledgeEdgeType.CITES),
                ]
            )
            await session.commit()
            typed = await graph_traverse(
                session,
                subject.id,
                edge_type=KnowledgeEdgeType.SUPERSEDES,
                direction=TraversalDirection.incoming,
            )
            untyped = await graph_traverse(
                session,
                subject.id,
                edge_type=None,
                direction=TraversalDirection.incoming,
            )
            return [h.node.title for h in typed], sorted(
                h.node.title for h in untyped
            )

    typed, untyped = asyncio.run(_run())
    assert typed == ["Replacement"]
    assert untyped == ["Citation", "Replacement"]


def test_graph_traverse_terminates_on_a_cycle(session_factory) -> None:
    """A looping chain terminates rather than hanging.

    The path is now returned as well as used for the visited check, so this
    also confirms surfacing it did not disturb the guard.
    """

    async def _run():
        async with session_factory() as session:
            first = _node("A", heading_path="a")
            second = _node("B", heading_path="b")
            await _seed(session, [first, second])
            session.add_all(
                [
                    _link(first, second, KnowledgeEdgeType.SUPERSEDES),
                    _link(second, first, KnowledgeEdgeType.SUPERSEDES),
                ]
            )
            await session.commit()
            hits = await graph_traverse(
                session, first.id, edge_type=KnowledgeEdgeType.SUPERSEDES, hops=10
            )
            return [h.node.title for h in hits]

    # B is reached; A is not returned as a result of walking back to itself.
    assert asyncio.run(_run()) == ["B"]


# --------------------------------------------------------------------------
# fact_lookup
# --------------------------------------------------------------------------


def test_fact_lookup_returns_a_typed_value(session_factory) -> None:
    """A field read, answered exactly.

    Separate from search because "when did this take effect" has a right answer,
    and approximating a date in clinical decision support is worse than not
    answering at all.
    """

    async def _run():
        async with session_factory() as session:
            node = _node("Rec", heading_path="a", effective_date=date(2026, 3, 1))
            await _seed(session, [node])
            return (
                await fact_lookup(session, node.id, FactAttribute.effective_date),
                await fact_lookup(session, node.id, FactAttribute.status),
                await fact_lookup(session, node.id, FactAttribute.category),
            )

    effective, status, category = asyncio.run(_run())
    assert effective.found and effective.value == date(2026, 3, 1)
    assert status.value is KnowledgeStatus.active
    assert category.value == ["cardiology"]
    assert effective.attribute is FactAttribute.effective_date


def test_fact_lookup_distinguishes_a_missing_node_from_a_missing_value(
    session_factory,
) -> None:
    """``None`` alone cannot carry this distinction, and generation needs it.

    "The planner named a node that does not exist" is a broken plan. "This
    guideline records no effective date" is a real, citable fact about the
    source. Collapsing both into a bare ``None`` would make the generation
    layer abstain identically for a bug and for the truth.
    """

    async def _run():
        async with session_factory() as session:
            undated = _node("No date", heading_path="a", effective_date=None)
            await _seed(session, [undated])
            return (
                await fact_lookup(
                    session, uuid.uuid4(), FactAttribute.effective_date
                ),
                await fact_lookup(
                    session, undated.id, FactAttribute.effective_date
                ),
            )

    missing_node, null_field = asyncio.run(_run())
    assert missing_node.found is False and missing_node.value is None
    assert null_field.found is True and null_field.value is None
    assert null_field.is_null is True
    assert missing_node.is_null is False


@pytest.mark.parametrize(
    "attribute",
    ["__class__", "outgoing_edges", "metadata", "text", "id"],
)
def test_fact_lookup_refuses_attributes_outside_the_closed_set(
    session_factory, attribute: str
) -> None:
    """The argument arrives from an LLM, so the readable surface is closed.

    An open ``getattr`` would reach relationships, dunders and lazy loads,
    turning a field read into an arbitrary introspection primitive — and a lazy
    relationship load would additionally blow up outside async context.
    """

    async def _run():
        async with session_factory() as session:
            node = _node("Rec", heading_path="a")
            await _seed(session, [node])
            with pytest.raises(ValueError):
                await fact_lookup(session, node.id, attribute)  # type: ignore[arg-type]

    asyncio.run(_run())


def test_every_fact_attribute_names_a_real_column() -> None:
    """The closed set cannot drift away from the model it reads."""
    for attribute in FactAttribute:
        assert hasattr(KnowledgeNode, attribute.value), attribute


# --------------------------------------------------------------------------
# composition — the shape the planner (#65) will use
# --------------------------------------------------------------------------


def test_filter_then_search_finds_current_guidance_the_ranking_would_bury(
    session_factory, embedder
) -> None:
    """The case the whole design exists for.

    Ten superseded chunks and one current one, with a non-semantic embedder so
    similarity cannot rescue the answer. Post-filtering a top-3 would return
    nothing useful; pre-filtering searches within the active set and finds the
    current recommendation regardless of where it would have ranked.
    """

    async def _run():
        async with session_factory() as session:
            current = _node("Current first-line therapy", heading_path="current")
            retired = [
                _node(
                    f"Superseded therapy {i}",
                    heading_path=f"old-{i}",
                    status=KnowledgeStatus.superseded,
                )
                for i in range(10)
            ]
            await _seed(session, [current, *retired])

            store = await _store(embedder)
            await _index(
                store,
                embedder,
                [_payload(current.id, current.text)]
                + [
                    _payload(node.id, node.text, status=KnowledgeStatus.superseded)
                    for node in retired
                ],
            )

            active = await structured_filter(
                session,
                NodeFilter(
                    status=[KnowledgeStatus.active],
                    node_type=[KnowledgeNodeType.recommendation],
                ),
            )
            result = await vector_search(
                "first-line therapy for heart failure",
                store=store,
                embedder=embedder,
                filters=NodeFilter(status=[KnowledgeStatus.active]).to_search_filters(),
                node_ids=active.node_ids,
                limit=3,
            )
            return current.id, result

    current_id, result = asyncio.run(_run())
    assert result.node_ids == (current_id,)
