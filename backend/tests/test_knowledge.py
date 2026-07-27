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
