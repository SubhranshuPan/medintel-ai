"""Knowledge graph models and repository (#60).

Covers what the database is supposed to guarantee rather than what Python does:
the unique constraint on an ordered typed pair, ON DELETE CASCADE, and that
traversal terminates on a cycle instead of hanging.
"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from app.repositories.knowledge import (
    MAX_TRAVERSAL_DEPTH,
    KnowledgeEdgeRepository,
    KnowledgeNodeRepository,
    TraversalDirection,
)


def _node(title: str, **overrides) -> KnowledgeNode:
    defaults = {
        "node_type": KnowledgeNodeType.recommendation,
        "title": title,
        "text": f"Clinical guidance: {title}",
        "source_id": title.lower().replace(" ", "-"),
        "source_type": KnowledgeSourceType.nice,
    }
    return KnowledgeNode(**{**defaults, **overrides})


@pytest.fixture
def session_factory(_engine: AsyncEngine) -> Callable[[], AsyncSession]:
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def test_node_defaults(session_factory) -> None:
    """Status and cadence default to the safe values, not to NULL."""

    async def _run() -> KnowledgeNode:
        async with session_factory() as session:
            node = _node(
                "Hypertension first-line",
                effective_date=date(2026, 1, 1),
                authority_tier=1,
                category=["cardiology", "primary-care"],
                heading_path="Management > Adults > First line",
            )
            session.add(node)
            await session.commit()
            await session.refresh(node)
            return node

    node = asyncio.run(_run())
    assert node.status is KnowledgeStatus.active
    assert node.update_cadence is UpdateCadence.static
    assert node.category == ["cardiology", "primary-care"]
    assert node.authority_tier == 1


def test_edge_unique_per_ordered_typed_pair(session_factory) -> None:
    """Re-running extraction must not multiply the graph."""

    async def _run() -> tuple[bool, bool]:
        async with session_factory() as session:
            new, old = _node("2026 guidance"), _node("2019 guidance")
            session.add_all([new, old])
            await session.flush()
            new_id, old_id = new.id, old.id

            session.add(
                KnowledgeEdge(
                    from_node_id=new_id,
                    to_node_id=old_id,
                    edge_type=KnowledgeEdgeType.SUPERSEDES,
                )
            )
            await session.commit()

            session.add(
                KnowledgeEdge(
                    from_node_id=new_id,
                    to_node_id=old_id,
                    edge_type=KnowledgeEdgeType.SUPERSEDES,
                )
            )
            duplicate_rejected = False
            try:
                await session.commit()
            except IntegrityError:
                duplicate_rejected = True
                await session.rollback()

            # Same pair, different type is a different fact and is allowed.
            session.add(
                KnowledgeEdge(
                    from_node_id=new_id,
                    to_node_id=old_id,
                    edge_type=KnowledgeEdgeType.CITES,
                )
            )
            await session.commit()
            return duplicate_rejected, True

    duplicate_rejected, other_type_allowed = asyncio.run(_run())
    assert duplicate_rejected
    assert other_type_allowed


def test_edge_requires_existing_endpoints(session_factory) -> None:
    """A dangling endpoint is rejected by the FK, not by application code."""

    async def _run() -> bool:
        async with session_factory() as session:
            node = _node("Orphan source")
            session.add(node)
            await session.flush()
            session.add(
                KnowledgeEdge(
                    from_node_id=node.id,
                    to_node_id=uuid.uuid4(),  # no such node
                    edge_type=KnowledgeEdgeType.CITES,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return True
            return False

    assert asyncio.run(_run())


def test_deleting_a_node_cascades_to_its_edges(session_factory) -> None:
    async def _run() -> int:
        async with session_factory() as session:
            a, b, c = _node("A"), _node("B"), _node("C")
            session.add_all([a, b, c])
            await session.flush()
            a_id = a.id
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=a_id,
                        to_node_id=b.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    ),
                    KnowledgeEdge(
                        from_node_id=c.id,
                        to_node_id=a_id,
                        edge_type=KnowledgeEdgeType.CITES,
                    ),
                ]
            )
            await session.commit()

            # Emit a bare DELETE so the database's ON DELETE CASCADE is what is
            # under test, not SQLAlchemy's ORM-side cascade.
            await session.execute(
                KnowledgeNode.__table__.delete().where(KnowledgeNode.id == a_id)
            )
            await session.commit()

            remaining = await session.execute(select(KnowledgeEdge))
            return len(list(remaining.scalars().all()))

    assert asyncio.run(_run()) == 0


def test_traverse_multi_hop_and_direction(session_factory) -> None:
    """A supersession chain: 2026 -> 2022 -> 2019, plus an off-type edge."""

    async def _run() -> dict[str, list[tuple[str, int]]]:
        async with session_factory() as session:
            g2026, g2022, g2019 = _node("2026"), _node("2022"), _node("2019")
            aside = _node("Aside")
            session.add_all([g2026, g2022, g2019, aside])
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=g2026.id,
                        to_node_id=g2022.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    ),
                    KnowledgeEdge(
                        from_node_id=g2022.id,
                        to_node_id=g2019.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    ),
                    KnowledgeEdge(
                        from_node_id=g2026.id,
                        to_node_id=aside.id,
                        edge_type=KnowledgeEdgeType.CITES,
                    ),
                ]
            )
            await session.commit()

            repo = KnowledgeNodeRepository(session)

            def _titles(hits):
                return sorted((h.node.title, h.depth) for h in hits)

            return {
                "all_out": _titles(await repo.traverse(g2026.id)),
                "typed": _titles(
                    await repo.traverse(
                        g2026.id, edge_type=KnowledgeEdgeType.SUPERSEDES
                    )
                ),
                "one_hop": _titles(await repo.traverse(g2026.id, hops=1)),
                "incoming": _titles(
                    await repo.traverse(
                        g2019.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                        direction=TraversalDirection.incoming,
                    )
                ),
                "both": _titles(
                    await repo.traverse(
                        g2022.id, direction=TraversalDirection.both, hops=1
                    )
                ),
            }

    out = asyncio.run(_run())
    assert out["all_out"] == [("2019", 2), ("2022", 1), ("Aside", 1)]
    # Type filter drops the CITES branch entirely.
    assert out["typed"] == [("2019", 2), ("2022", 1)]
    assert out["one_hop"] == [("2022", 1), ("Aside", 1)]
    # "What replaced the 2019 guidance?" walks the chain backwards.
    assert out["incoming"] == [("2022", 1), ("2026", 2)]
    assert out["both"] == [("2019", 1), ("2026", 1)]


def test_traverse_terminates_on_a_cycle(session_factory) -> None:
    """A looping SUPERSEDES chain must return, not hang.

    An extractor can emit A -> B -> C -> A. Without the visited-set guard the
    recursive CTE walks that loop until the depth cap, and each node reappears
    at every lap.
    """

    async def _run() -> list[tuple[str, int]]:
        async with session_factory() as session:
            a, b, c = _node("Loop A"), _node("Loop B"), _node("Loop C")
            session.add_all([a, b, c])
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=x.id,
                        to_node_id=y.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    )
                    for x, y in ((a, b), (b, c), (c, a))
                ]
            )
            await session.commit()

            repo = KnowledgeNodeRepository(session)
            hits = await repo.traverse(a.id, hops=MAX_TRAVERSAL_DEPTH)
            return sorted((h.node.title, h.depth) for h in hits)

    # The start node is not returned even though an edge points back at it,
    # and each other node appears exactly once at its shortest depth.
    assert asyncio.run(_run()) == [("Loop B", 1), ("Loop C", 2)]


def test_traverse_clamps_depth(session_factory) -> None:
    """Planner-supplied depth is LLM output, so it is clamped, not trusted."""

    async def _run() -> int:
        async with session_factory() as session:
            nodes = [_node(f"Chain {i}") for i in range(MAX_TRAVERSAL_DEPTH + 3)]
            session.add_all(nodes)
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=nodes[i].id,
                        to_node_id=nodes[i + 1].id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    )
                    for i in range(len(nodes) - 1)
                ]
            )
            await session.commit()

            repo = KnowledgeNodeRepository(session)
            hits = await repo.traverse(nodes[0].id, hops=10_000)
            return len(hits)

    assert asyncio.run(_run()) == MAX_TRAVERSAL_DEPTH


def test_traverse_bounds_result_size(session_factory) -> None:
    """Depth alone does not bound size — a hub fans out within one hop."""

    async def _run() -> list[tuple[str, int]]:
        async with session_factory() as session:
            hub = _node("Hub")
            spokes = [_node(f"Spoke {i}") for i in range(6)]
            session.add_all([hub, *spokes])
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=hub.id,
                        to_node_id=spoke.id,
                        edge_type=KnowledgeEdgeType.CITES,
                    )
                    for spoke in spokes
                ]
            )
            await session.commit()

            repo = KnowledgeNodeRepository(session)
            hits = await repo.traverse(hub.id, limit=2)
            return [(h.node.title, h.depth) for h in hits]

    hits = asyncio.run(_run())
    assert len(hits) == 2
    # Truncation is depth-ordered, so what survives is the nearest material.
    assert all(depth == 1 for _, depth in hits)


def test_traverse_reports_how_each_node_was_reached(session_factory) -> None:
    """A supersession notice must be distinguishable from a bare citation."""

    async def _run() -> dict[str, KnowledgeEdgeType]:
        async with session_factory() as session:
            current, old, cited = _node("Current"), _node("Old"), _node("Cited")
            session.add_all([current, old, cited])
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=current.id,
                        to_node_id=old.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    ),
                    KnowledgeEdge(
                        from_node_id=current.id,
                        to_node_id=cited.id,
                        edge_type=KnowledgeEdgeType.CITES,
                    ),
                ]
            )
            await session.commit()

            repo = KnowledgeNodeRepository(session)
            return {h.node.title: h.edge_type for h in await repo.traverse(current.id)}

    assert asyncio.run(_run()) == {
        "Old": KnowledgeEdgeType.SUPERSEDES,
        "Cited": KnowledgeEdgeType.CITES,
    }


def test_typed_traversal_survives_unrelated_fan_out(session_factory) -> None:
    """The safety contract in traverse()'s docstring, exercised.

    An untyped traversal truncated at `limit` can lose a SUPERSEDES hit among
    citation noise. Asking the database for the edge type instead of filtering
    afterwards is what makes a supersession check reliable.
    """

    async def _run() -> tuple[list[str], list[str]]:
        async with session_factory() as session:
            guideline = _node("Guideline")
            replacement = _node("Replacement")
            noise = [_node(f"Citing {i}") for i in range(8)]
            session.add_all([guideline, replacement, *noise])
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=guideline.id,
                        to_node_id=replacement.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    )
                ]
                + [
                    KnowledgeEdge(
                        from_node_id=guideline.id,
                        to_node_id=n.id,
                        edge_type=KnowledgeEdgeType.CITES,
                    )
                    for n in noise
                ]
            )
            await session.commit()

            repo = KnowledgeNodeRepository(session)
            untyped = await repo.traverse(guideline.id, limit=3)
            typed = await repo.traverse(
                guideline.id, edge_type=KnowledgeEdgeType.SUPERSEDES, limit=3
            )
            return (
                [h.node.title for h in untyped],
                [h.node.title for h in typed],
            )

    untyped, typed = asyncio.run(_run())
    # The untyped call is capped and gives no guarantee the replacement is in it.
    assert len(untyped) == 3
    # The typed call cannot be crowded out — the filter runs in the database.
    assert typed == ["Replacement"]


def test_confidence_outside_zero_to_one_is_rejected(session_factory) -> None:
    """A malfunctioning extractor fails at ingestion, not silently downstream."""

    async def _run() -> tuple[bool, bool]:
        async with session_factory() as session:
            a, b = _node("Conf A"), _node("Conf B")
            session.add_all([a, b])
            # Commit the nodes first: the rollback below would otherwise discard
            # them too, and capture the ids before it expires the attributes.
            await session.commit()
            a_id, b_id = a.id, b.id

            session.add(
                KnowledgeEdge(
                    from_node_id=a_id,
                    to_node_id=b_id,
                    edge_type=KnowledgeEdgeType.RELATED_TO,
                    confidence=1.4,
                )
            )
            rejected = False
            try:
                await session.commit()
            except IntegrityError:
                rejected = True
                await session.rollback()

            session.add(
                KnowledgeEdge(
                    from_node_id=a_id,
                    to_node_id=b_id,
                    edge_type=KnowledgeEdgeType.RELATED_TO,
                    confidence=0.9,
                )
            )
            await session.commit()
            return rejected, True

    rejected, in_range_ok = asyncio.run(_run())
    assert rejected
    assert in_range_ok


def test_edge_list_for_node_is_paged(session_factory) -> None:
    async def _run() -> tuple[int, int]:
        async with session_factory() as session:
            hub = _node("Paged hub")
            others = [_node(f"Other {i}") for i in range(5)]
            session.add_all([hub, *others])
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=hub.id,
                        to_node_id=other.id,
                        edge_type=KnowledgeEdgeType.CITES,
                    )
                    for other in others
                ]
            )
            await session.commit()

            repo = KnowledgeEdgeRepository(session)
            page = await repo.list_for_node(hub.id, limit=2)
            tail = await repo.list_for_node(hub.id, limit=10, offset=4)
            return len(page), len(tail)

    assert asyncio.run(_run()) == (2, 1)


def test_edge_repository_list_for_node(session_factory) -> None:
    async def _run() -> tuple[int, int, int]:
        async with session_factory() as session:
            a, b, c = _node("Hub"), _node("Down"), _node("Up")
            session.add_all([a, b, c])
            await session.flush()
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=a.id,
                        to_node_id=b.id,
                        edge_type=KnowledgeEdgeType.EXCEPTION_TO,
                        confidence=0.82,
                        extracted_by="claude-haiku-4-5/extract-v1",
                    ),
                    KnowledgeEdge(
                        from_node_id=c.id,
                        to_node_id=a.id,
                        edge_type=KnowledgeEdgeType.CITES,
                    ),
                ]
            )
            await session.commit()

            repo = KnowledgeEdgeRepository(session)
            return (
                len(await repo.list_for_node(a.id)),
                len(
                    await repo.list_for_node(
                        a.id, direction=TraversalDirection.incoming
                    )
                ),
                len(await repo.list_for_node(a.id, direction=TraversalDirection.both)),
            )

    assert asyncio.run(_run()) == (1, 1, 2)


def test_knowledge_enums_are_closed_sets() -> None:
    assert {t.value for t in KnowledgeEdgeType} == {
        "SUPERSEDES",
        "DEFINED_BY",
        "EXCEPTION_TO",
        "CITES",
        "RELATED_TO",
    }
    assert {t.value for t in KnowledgeNodeType} == {
        "guideline",
        "article",
        "recommendation",
        "term",
    }
    assert {s.value for s in KnowledgeStatus} == {
        "active",
        "superseded",
        "withdrawn",
        "draft",
    }
    assert {s.value for s in KnowledgeSourceType} == {"pubmed", "nice"}
    assert {c.value for c in UpdateCadence} == {"static", "periodic", "live"}
