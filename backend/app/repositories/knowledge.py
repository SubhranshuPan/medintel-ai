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

from sqlalchemy import String, case, cast, func, literal, or_, select
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
    """A node reached by traversal.

    ``edge_type`` is the type of the edge on the *shortest* path in, so a
    caller can tell a supersession notice apart from an incidental citation
    without issuing a second query per hit — a distinction that matters when
    the result feeds clinical decision support.
    """

    node: KnowledgeNode
    depth: int
    edge_type: KnowledgeEdgeType


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


def _edge_priority(edge_type: ColumnElement[KnowledgeEdgeType]) -> ColumnElement[int]:
    """Sort key placing safety-critical edge types ahead of incidental ones.

    Ordering on the enum column directly is not an option: PostgreSQL orders an
    enum by declaration order while SQLite stores it as text and orders it
    alphabetically, so the two dialects would disagree about which edge wins.
    An explicit ranking makes the order the same everywhere *and* makes it the
    clinically right one — a hit reached by ``SUPERSEDES`` or ``EXCEPTION_TO``
    outranks one reached by a citation, so it is never the row truncation drops.
    """
    return case(
        (edge_type == KnowledgeEdgeType.SUPERSEDES, 0),
        (edge_type == KnowledgeEdgeType.EXCEPTION_TO, 1),
        (edge_type == KnowledgeEdgeType.DEFINED_BY, 2),
        else_=3,  # CITES, RELATED_TO — context, not safety signal
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
        edge_type: KnowledgeEdgeType | None,
        hops: int = DEFAULT_TRAVERSAL_DEPTH,
        direction: TraversalDirection = TraversalDirection.outgoing,
        limit: int = DEFAULT_TRAVERSAL_LIMIT,
    ) -> list[TraversalHit]:
        """Nodes reachable from ``node_id``, nearest and most critical first.

        ``edge_type`` is required rather than defaulted: following every edge
        type is a legitimate exploratory query, but it should be an explicit
        choice at the call site, not what you get by forgetting the argument.
        Pass ``None`` to follow all of them.

        ``hops`` is clamped to ``[1, MAX_TRAVERSAL_DEPTH]``. The start node is
        never returned, and a node reachable by several paths is returned once,
        by its shortest path.

        Bounded on both axes, because the depth cap alone does not bound the
        result *size* — a heavily cited guideline can fan out to thousands of
        nodes within three hops. Ordering is ``(depth, edge priority, id)``, so
        truncation drops the most distant, least safety-relevant material:
        within a depth a ``SUPERSEDES`` or ``EXCEPTION_TO`` hit always outranks
        a citation and cannot be cut in favour of one. The same ordering
        decides which edge represents a node reachable by more than one.

        Cycle-safe by construction: a node already on the current path is not
        re-entered, so a looping ``SUPERSEDES`` chain terminates rather than
        hanging.

        Note the ceiling: the visited guard is per *path*, not per node, so a
        densely connected graph expands every distinct path to a node rather
        than only the first. Bounded in practice by the corpus size (thousands
        of nodes, ADR-021) and by ``hops``; if traversal ever becomes the
        measured bottleneck, per-node pruning during expansion is the upgrade,
        and a native graph store is the one after that.
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
            KnowledgeEdge.edge_type.label("edge_type"),
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
                KnowledgeEdge.edge_type.label("edge_type"),
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

        # Several paths can reach the same node; report it once, by the
        # shortest. A window function rather than GROUP BY / MIN, because the
        # edge type has to survive the dedup alongside the depth.
        priority = _edge_priority(walk.c.edge_type)
        ranked = select(
            walk.c.node_id,
            walk.c.depth,
            walk.c.edge_type,
            priority.label("priority"),
            func.row_number()
            .over(partition_by=walk.c.node_id, order_by=(walk.c.depth, priority))
            .label("rank"),
        ).subquery()
        shortest = select(ranked).where(ranked.c.rank == 1).subquery()

        result = await self.session.execute(
            select(KnowledgeNode, shortest.c.depth, shortest.c.edge_type)
            .join(shortest, KnowledgeNode.id == shortest.c.node_id)
            # Priority before id: within a depth the cut must not be arbitrary,
            # or a supersession notice can be truncated away by citation noise.
            .order_by(shortest.c.depth, shortest.c.priority, KnowledgeNode.id)
            .limit(limit)
        )
        return [
            TraversalHit(node=node, depth=depth, edge_type=KnowledgeEdgeType(edge_type))
            for node, depth, edge_type in result.all()
        ]


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
