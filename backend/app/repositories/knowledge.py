"""Knowledge graph persistence — nodes, edges, and bounded traversal.

Traversal is a recursive CTE over ``knowledge_edges`` rather than a second
datastore (ADR-021): at this corpus size Neo4j would buy traversal performance
PostgreSQL already delivers, in exchange for a third source of truth to keep
consistent with PostgreSQL and Qdrant.

Recursive CTEs have no natural termination, and an imperfect extractor can
easily emit a ``SUPERSEDES`` chain that loops. Traversal here is therefore
guarded twice: a hard depth cap, and a visited-set check carried as a path
string. Neither guard alone is sufficient — the depth cap stops a cycle from
hanging but still walks it exponentially, and the visited set alone would still
let a long acyclic chain run away.
"""

import enum
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import String, cast, func, literal, or_, select
from sqlalchemy.sql import ColumnElement

from app.models.knowledge import KnowledgeEdge, KnowledgeEdgeType, KnowledgeNode
from app.repositories.base import BaseRepository

#: Hops to follow when the caller does not say (ADR-021 / design spec §4.5).
DEFAULT_TRAVERSAL_DEPTH = 3
#: Ceiling applied to any caller-supplied depth. A planner-generated depth is
#: LLM output, so it is clamped rather than trusted.
MAX_TRAVERSAL_DEPTH = 10

#: Nodes returned by one traversal unless the caller says otherwise. Results are
#: depth-ordered, so truncation drops the most distant nodes first.
DEFAULT_TRAVERSAL_LIMIT = 200

#: Separator around every id in the visited-path string, so a substring test
#: cannot match a partial id.
_PATH_SEP = "/"


class TraversalDirection(enum.StrEnum):
    """Which way edges are followed from the start node."""

    outgoing = "outgoing"  # from_node -> to_node
    incoming = "incoming"  # to_node -> from_node ("what supersedes this?")
    both = "both"


class TraversalHit(NamedTuple):
    """A node reached by traversal, with its shortest hop distance."""

    node: KnowledgeNode
    depth: int


def _far_endpoint(
    arrived_at: ColumnElement[UUID], direction: TraversalDirection
) -> ColumnElement[UUID]:
    """The endpoint of an edge opposite the one we arrived at."""
    if direction is TraversalDirection.outgoing:
        return KnowledgeEdge.to_node_id
    if direction is TraversalDirection.incoming:
        return KnowledgeEdge.from_node_id
    return func.coalesce(
        # ``both``: whichever endpoint is not the one we came from.
        func.nullif(KnowledgeEdge.to_node_id, arrived_at),
        KnowledgeEdge.from_node_id,
    )


def _incident(
    node: ColumnElement[UUID] | UUID, direction: TraversalDirection
) -> ColumnElement[bool]:
    """Edges touching ``node`` in the requested direction."""
    if direction is TraversalDirection.outgoing:
        return KnowledgeEdge.from_node_id == node
    if direction is TraversalDirection.incoming:
        return KnowledgeEdge.to_node_id == node
    return or_(
        KnowledgeEdge.from_node_id == node,
        KnowledgeEdge.to_node_id == node,
    )


def _delimited(node: ColumnElement[UUID]) -> ColumnElement[str]:
    """``node``'s id wrapped in separators, as it appears in a visited path.

    Cast rather than formatted from the Python UUID: SQLite stores UUIDs as
    undashed hex and PostgreSQL as dashed text, so an f-string built from the
    Python value would only match on one of the two dialects.
    """
    return literal(_PATH_SEP) + cast(node, String) + literal(_PATH_SEP)


class KnowledgeNodeRepository(BaseRepository[KnowledgeNode]):
    """CRUD for :class:`KnowledgeNode`, plus bounded graph traversal."""

    model = KnowledgeNode

    async def traverse(
        self,
        node_id: UUID,
        *,
        edge_type: KnowledgeEdgeType | None = None,
        hops: int = DEFAULT_TRAVERSAL_DEPTH,
        direction: TraversalDirection = TraversalDirection.outgoing,
        limit: int = DEFAULT_TRAVERSAL_LIMIT,
    ) -> list[TraversalHit]:
        """Nodes reachable from ``node_id``, nearest first.

        ``edge_type=None`` follows every edge type. ``hops`` is clamped to
        ``[1, MAX_TRAVERSAL_DEPTH]``. The start node is never returned, and a
        node reachable by several paths is returned once, at its shortest depth.

        Bounded on both axes, because the depth cap alone does not bound the
        result *size* — a heavily cited guideline can fan out to thousands of
        nodes within three hops. Truncation is depth-ordered, so what falls off
        the end is the most distant, least relevant material.

        Cycle-safe by construction: a node already on the current path is not
        re-entered, so a looping ``SUPERSEDES`` chain terminates rather than
        hanging.
        """
        hops = max(1, min(hops, MAX_TRAVERSAL_DEPTH))

        def _typed(clause: ColumnElement[bool]) -> ColumnElement[bool]:
            if edge_type is None:
                return clause
            return clause & (KnowledgeEdge.edge_type == edge_type)

        start_col = literal(node_id)
        first_hop = _far_endpoint(start_col, direction)
        base = select(
            first_hop.label("node_id"),
            literal(1).label("depth"),
            (
                _delimited(start_col) + cast(first_hop, String) + literal(_PATH_SEP)
            ).label("path"),
        ).where(_typed(_incident(start_col, direction)))

        walk = base.cte("knowledge_traverse", recursive=True)
        next_id = _far_endpoint(walk.c.node_id, direction)
        walk = walk.union_all(
            select(
                next_id.label("node_id"),
                (walk.c.depth + 1).label("depth"),
                (walk.c.path + cast(next_id, String) + literal(_PATH_SEP)).label("path"),
            ).where(
                _typed(_incident(walk.c.node_id, direction)),
                walk.c.depth < hops,
                # Visited-set guard. The path carries every id seen so far, each
                # delimited on both sides, so this rejects a revisit — including
                # a return to the start node — without needing an array type
                # (SQLite runs the test suite) or PostgreSQL's CYCLE clause.
                ~walk.c.path.contains(_delimited(next_id)),
            )
        )

        # Several paths can reach the same node; report it once, nearest.
        shortest = (
            select(walk.c.node_id, func.min(walk.c.depth).label("depth"))
            .group_by(walk.c.node_id)
            .subquery()
        )
        result = await self.session.execute(
            select(KnowledgeNode, shortest.c.depth)
            .join(shortest, KnowledgeNode.id == shortest.c.node_id)
            .order_by(shortest.c.depth, KnowledgeNode.id)
            .limit(limit)
        )
        return [TraversalHit(node=node, depth=depth) for node, depth in result.all()]


class KnowledgeEdgeRepository(BaseRepository[KnowledgeEdge]):
    """CRUD for :class:`KnowledgeEdge`.

    Edge validity is a database concern, not a repository one: the closed type
    set is a PostgreSQL enum and both endpoints are foreign keys, so a malformed
    edge fails on flush rather than passing a Python check.
    """

    model = KnowledgeEdge

    async def list_for_node(
        self,
        node_id: UUID,
        *,
        direction: TraversalDirection = TraversalDirection.outgoing,
        edge_type: KnowledgeEdgeType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeEdge]:
        """Edges incident on ``node_id`` (one hop, unlike ``traverse``).

        Paged like every other repository read (``BaseRepository.list``): a
        heavily cited node has an unbounded number of incident edges.
        """
        stmt = select(KnowledgeEdge).where(_incident(node_id, direction))
        if edge_type is not None:
            stmt = stmt.where(KnowledgeEdge.edge_type == edge_type)
        result = await self.session.execute(
            stmt.order_by(KnowledgeEdge.created_at).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
