"""Running extraction over the corpus, and applying supersession (#63).

Two passes with different trust levels, kept apart on purpose.

**Model-inferred structure.** One constrained call per structural unit, emitting
terms the passage defines and typed relationships to a bounded candidate set.
Everything it writes carries ``confidence`` and ``extracted_by``, so it can be
re-validated — or deleted wholesale — when the extractor changes, without
touching anything else in the graph.

**Publisher-stated structure.** ``SUPERSEDES`` and ``CITES`` edges are written by
ingestion (#61) from source metadata, with NULL ``confidence`` and
``extracted_by``. :func:`apply_supersession` finishes that job: it reads those
stated edges and flips the superseded side's ``status``, which is the step that
makes withdrawn guidance actually stop being retrievable. No model is consulted,
because no model needs to be — the guideline says which edition it replaces.

The separation is the point. A pipeline where an LLM can retire live clinical
guidance is a pipeline with a silent, clinically material failure mode; here the
only thing that can retire guidance is the publisher saying so.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    KnowledgeEdge,
    KnowledgeEdgeType,
    KnowledgeNode,
    KnowledgeNodeType,
    KnowledgeStatus,
)
from app.services.extraction.provider import (
    BudgetExceededError,
    CostMeter,
    ExtractionCall,
    ExtractionModel,
    ExtractionUnavailableError,
)
from app.services.extraction.schema import (
    PROMPT_VERSION,
    ExtractedEntity,
    ExtractionResult,
    Rejection,
    parse_extraction,
)

logger = logging.getLogger(__name__)

#: Structural units one run will extract from, before any budget is consulted.
#: A belt-and-braces companion to the spend ceiling: the budget bounds cost, and
#: this bounds *corpus*, so a mistakenly broad node selection is caught even if
#: the per-call cost turns out lower than estimated.
DEFAULT_MAX_UNITS = 500

#: Candidate passages shown to the model per call. Directly proportional to
#: input tokens, so this is the main cost knob after corpus size.
DEFAULT_MAX_CANDIDATES = 20

#: Node types worth extracting from. A ``term`` node is itself an extraction
#: output, so re-extracting from one would compound the model's own paraphrase.
EXTRACTABLE_NODE_TYPES = (
    KnowledgeNodeType.recommendation,
    KnowledgeNodeType.article,
)

#: Marker in a term node's heading path. Also its identity within a document:
#: ``(source_type, source_id, "term:hfref")`` is the same triple ingestion keys
#: on, so re-extraction updates a term rather than forking one.
TERM_HEADING_PREFIX = "term:"

SYSTEM_PROMPT = (
    "You are a clinical knowledge engineer building a decision-support "
    "knowledge graph from published medical literature and clinical "
    "guidelines.\n\n"
    "Extract only what the passage states. Never add clinical knowledge from "
    "your own training, and never infer a relationship the text does not "
    "support — an empty result is correct and expected when the passage "
    "stands alone. A wrong edge in a clinical knowledge graph surfaces the "
    "wrong guidance to a clinician, so under-extraction is the safer error.\n\n"
    "Relate the passage only to the numbered candidate passages supplied. "
    "Never invent a candidate number."
)


@dataclass(slots=True)
class ExtractionReport:
    """What one extraction run produced, cost, and threw away.

    Rejections are reported as a list rather than a count because the *reasons*
    are the signal: a run rejecting fifty targets outside the candidate set is a
    prompt problem, and one rejecting fifty low-confidence edges is a corpus
    problem. Those need different fixes and a single counter cannot tell them
    apart.
    """

    units_extracted: int = 0
    units_skipped: int = 0
    terms_created: int = 0
    edges_created: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    budget_exhausted: bool = False
    rejections: list[Rejection] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def rejection_reasons(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for rejection in self.rejections:
            counts[rejection.reason] = counts.get(rejection.reason, 0) + 1
        return counts


def extractor_stamp(model_id: str) -> str:
    """The ``extracted_by`` value for a model at the current prompt version."""
    return f"{model_id}/{PROMPT_VERSION}"


def _render_candidates(candidates: Sequence[KnowledgeNode]) -> str:
    lines = []
    for number, node in enumerate(candidates, start=1):
        where = f" [{node.heading_path}]" if node.heading_path else ""
        # Truncated: the model needs enough to recognise the candidate, not to
        # re-read the corpus. Candidate text is the largest term in the input
        # token count and the one with the least marginal value per token.
        lines.append(f"{number}. {node.title}{where}\n   {node.text[:400]}")
    return "\n".join(lines) if lines else "(none)"


def build_prompt(node: KnowledgeNode, candidates: Sequence[KnowledgeNode]) -> str:
    """The user turn for one structural unit."""
    heading = f"\nSection: {node.heading_path}" if node.heading_path else ""
    return (
        f"PASSAGE ({node.node_type}, {node.source_type} {node.external_ref or ''})"
        f"{heading}\n"
        f"Title: {node.title}\n\n"
        f"{node.text}\n\n"
        f"CANDIDATE PASSAGES\n{_render_candidates(candidates)}\n"
    )


async def select_units(
    session: AsyncSession,
    *,
    stamp: str,
    limit: int,
    source_ids: Sequence[str] | None = None,
) -> list[KnowledgeNode]:
    """Nodes to extract from, newest guidance first, already-done ones skipped.

    "Already done" means the node has at least one edge carrying this exact
    ``extracted_by`` stamp, so bumping ``PROMPT_VERSION`` re-extracts the corpus
    and re-running an unchanged extractor does not.

    ponytail: a unit that legitimately yields no edges has nothing to stamp, so
    it is re-extracted on every run. Accepted for now — a zero-yield unit is
    cheap and the corpus is small. The fix is an ``extracted_at``/
    ``extracted_by`` watermark column on ``knowledge_nodes``, which is a
    migration, and it should land when the corpus is large enough for the waste
    to be measurable rather than theoretical.
    """
    # A unit's own extraction is what wrote these, and nothing else could have.
    # Two directions rather than one, because a unit's outputs do not all point
    # the same way: relationships point *out* of the unit, but the ``DEFINED_BY``
    # edge for a term this unit defined points from the term *into* it (the
    # direction ADR-021 gives that type). Watching only ``from_node_id`` would
    # re-extract — and re-pay for — every passage whose sole output was a term.
    #
    # The inbound half is narrowed to edges originating at a ``term`` node, and
    # that narrowing is load-bearing twice over. A model may also assert
    # ``DEFINED_BY`` from a passage to a candidate, and a passage that merely
    # *receives* such an edge has had nothing extracted from it — counting that
    # would skip it permanently and leave a hole no report would show. Only a
    # term node's outgoing ``DEFINED_BY`` is evidence that *this* unit ran, since
    # term nodes are created by nothing but the extraction of the unit they
    # attach to.
    term_defined = select(KnowledgeEdge.to_node_id).join(
        KnowledgeNode, KnowledgeNode.id == KnowledgeEdge.from_node_id
    ).where(
        KnowledgeEdge.extracted_by == stamp,
        KnowledgeEdge.edge_type == KnowledgeEdgeType.DEFINED_BY,
        KnowledgeNode.node_type == KnowledgeNodeType.term,
    )
    done = (
        select(KnowledgeEdge.from_node_id)
        .where(KnowledgeEdge.extracted_by == stamp)
        .union(term_defined)
        .scalar_subquery()
    )
    stmt = (
        select(KnowledgeNode)
        .where(
            KnowledgeNode.node_type.in_(EXTRACTABLE_NODE_TYPES),
            # Superseded and withdrawn guidance is not worth spending on: it is
            # filtered out of retrieval before vector search anyway (ADR-021).
            KnowledgeNode.status == KnowledgeStatus.active,
            KnowledgeNode.id.not_in(done),
        )
        # Deterministic and useful: if a cap truncates the run, it truncates the
        # oldest material rather than an arbitrary slice.
        .order_by(
            KnowledgeNode.effective_date.is_(None),
            KnowledgeNode.effective_date.desc(),
            KnowledgeNode.id,
        )
        .limit(limit)
    )
    if source_ids:
        stmt = stmt.where(KnowledgeNode.source_id.in_(list(source_ids)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def select_candidates(
    session: AsyncSession, node: KnowledgeNode, *, limit: int
) -> list[KnowledgeNode]:
    """Nodes the model is permitted to relate ``node`` to.

    Siblings from the same source document first. That ordering is not
    incidental: ``EXCEPTION_TO`` almost always lives inside one document — "this
    recommendation does not apply to patients with…" sits beside the
    recommendation it qualifies — so a truncated candidate list must not be the
    reason an exception goes unextracted.

    A bounded set rather than the whole corpus, because it is both the dominant
    input-token cost and the mechanism that makes hallucinated targets
    impossible: the model can only name a number we listed.
    """
    stmt = (
        select(KnowledgeNode)
        .where(
            KnowledgeNode.id != node.id,
            KnowledgeNode.status == KnowledgeStatus.active,
            KnowledgeNode.node_type.in_(
                (*EXTRACTABLE_NODE_TYPES, KnowledgeNodeType.guideline)
            ),
            or_(
                KnowledgeNode.source_id == node.source_id,
                KnowledgeNode.source_type == node.source_type,
            ),
        )
        .order_by(
            # Same-document first, then everything else by recency.
            (KnowledgeNode.source_id != node.source_id),
            KnowledgeNode.effective_date.is_(None),
            KnowledgeNode.effective_date.desc(),
            KnowledgeNode.id,
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _upsert_terms(
    session: AsyncSession,
    node: KnowledgeNode,
    entities: Sequence[ExtractedEntity],
) -> tuple[list[KnowledgeNode], int]:
    """Materialise extracted terms as ``term`` nodes within ``node``'s document.

    Scoped to the document rather than deduplicated corpus-wide, and that is the
    honest modelling: what is recorded is "*this guideline* defines HFrEF this
    way", which is a statement with provenance. A corpus-wide term node would
    have to claim a ``source_type`` it does not have, and reconciling two
    publishers' definitions of the same term is a normalisation problem, not an
    extraction one.
    """
    if not entities:
        return [], 0

    wanted = {entity.slug: entity for entity in entities if entity.slug}
    paths = [f"{TERM_HEADING_PREFIX}{slug}" for slug in wanted]
    result = await session.execute(
        select(KnowledgeNode).where(
            KnowledgeNode.source_type == node.source_type,
            KnowledgeNode.source_id == node.source_id,
            KnowledgeNode.heading_path.in_(paths),
        )
    )
    existing = {
        (n.heading_path or "").removeprefix(TERM_HEADING_PREFIX): n
        for n in result.scalars()
    }

    terms: list[KnowledgeNode] = []
    created = 0
    for slug, entity in wanted.items():
        term = existing.get(slug)
        if term is None:
            term = KnowledgeNode(
                node_type=KnowledgeNodeType.term,
                title=entity.name[:512],
                text=entity.definition,
                source_id=node.source_id,
                source_type=node.source_type,
                heading_path=f"{TERM_HEADING_PREFIX}{slug}",
                external_ref=node.external_ref,
                source_venue=node.source_venue,
                effective_date=node.effective_date,
                # A term inherits the lifecycle of the document that defines it,
                # for the same reason a recommendation does: a definition from a
                # withdrawn guideline is withdrawn guidance.
                status=node.status,
                authority_tier=node.authority_tier,
                category=list(node.category or []),
                update_cadence=node.update_cadence,
            )
            session.add(term)
            created += 1
        else:
            term.text = entity.definition
        terms.append(term)
    return terms, created


async def _existing_edges(
    session: AsyncSession, from_ids: Sequence[UUID]
) -> set[tuple[UUID, UUID, KnowledgeEdgeType]]:
    """Edges already written out of ``from_ids``.

    Queried rather than left to the unique constraint: a constraint violation
    aborts the surrounding transaction, which on a re-run would take down a run
    that had already paid for its calls.
    """
    if not from_ids:
        return set()
    result = await session.execute(
        select(
            KnowledgeEdge.from_node_id,
            KnowledgeEdge.to_node_id,
            KnowledgeEdge.edge_type,
        ).where(KnowledgeEdge.from_node_id.in_(list(from_ids)))
    )
    return {(f, t, KnowledgeEdgeType(e)) for f, t, e in result.all()}


async def _write_extraction(
    session: AsyncSession,
    node: KnowledgeNode,
    extraction: ExtractionResult,
    *,
    stamp: str,
    report: ExtractionReport,
) -> None:
    """Persist one unit's terms and edges. Flushes; does not commit."""
    terms, created = await _upsert_terms(session, node, extraction.entities)
    # Terms need ids before they can be an edge endpoint.
    await session.flush()
    report.terms_created += created

    from_ids = [node.id, *(term.id for term in terms)]
    seen = await _existing_edges(session, from_ids)

    def add(
        from_id: UUID,
        to_id: UUID,
        edge_type: KnowledgeEdgeType,
        confidence: float | None,
    ) -> None:
        key = (from_id, to_id, edge_type)
        if from_id == to_id or key in seen:
            return
        seen.add(key)
        session.add(
            KnowledgeEdge(
                from_node_id=from_id,
                to_node_id=to_id,
                edge_type=edge_type,
                confidence=confidence,
                extracted_by=stamp,
            )
        )
        report.edges_created += 1

    for term in terms:
        # "This term is defined by this passage" — the direction ADR-021 gives
        # DEFINED_BY, so traversing incoming DEFINED_BY from a passage lists
        # what it defines.
        add(term.id, node.id, KnowledgeEdgeType.DEFINED_BY, None)

    for relationship in extraction.relationships:
        add(
            node.id,
            relationship.target_node_id,
            relationship.edge_type,
            relationship.confidence,
        )


async def extract_knowledge(
    session: AsyncSession,
    model: ExtractionModel,
    *,
    max_units: int = DEFAULT_MAX_UNITS,
    budget_usd: float | None = None,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    source_ids: Sequence[str] | None = None,
) -> ExtractionReport:
    """Extract terms and relationships across the corpus, within a hard cap.

    Bounded on both axes before the first call is made: ``max_units`` caps how
    much corpus a run touches and ``budget_usd`` caps what it spends. Exhausting
    the budget ends the run cleanly with everything extracted so far committed
    and ``budget_exhausted`` set — a partial graph is fine and a partial graph
    that nobody knows is partial is not.

    A failure on one unit is recorded and the run continues. One malformed
    passage should not cost the corpus its extraction pass.
    """
    stamp = extractor_stamp(model.model_id)
    meter = CostMeter(model_id=model.model_id, budget_usd=budget_usd)
    report = ExtractionReport()

    units = await select_units(
        session, stamp=stamp, limit=max(0, max_units), source_ids=source_ids
    )
    if not units:
        return report

    # Ids, not instances, across the loop. A rollback expires every object in
    # the session, so a unit held from before it would raise on the next
    # attribute read — which means one failed unit would take down every unit
    # after it, the exact opposite of the per-unit isolation promised above.
    # Re-loading costs one indexed primary-key lookup against a call that takes
    # a second or more.
    unit_ids = [unit.id for unit in units]

    for unit_id in unit_ids:
        try:
            meter.check()
        except BudgetExceededError as exc:
            logger.warning("%s", exc)
            report.budget_exhausted = True
            # Everything not yet attempted. Subtracting the already-skipped as
            # well as the extracted, or the counts stop summing to the corpus
            # and a report nobody can add up is a report nobody trusts.
            report.units_skipped += (
                len(units) - report.units_extracted - report.units_skipped
            )
            break

        # The whole unit is inside the guard, not just the model call. A failure
        # in candidate selection or in persistence is as survivable as a provider
        # error, and leaving it outside would abort a run that had already paid
        # for every unit before it.
        try:
            node = await session.get(KnowledgeNode, unit_id)
            if node is None:
                # Deleted between selection and extraction. Nothing to do and
                # nothing wrong — a re-ingestion running alongside can do this.
                report.units_skipped += 1
                continue
            candidates = await select_candidates(session, node, limit=max_candidates)
            candidate_ids = [candidate.id for candidate in candidates]
            call = await model.extract(SYSTEM_PROMPT, build_prompt(node, candidates))
            meter.record(call)
            extraction = parse_extraction(
                call.payload, candidate_ids, source_node_id=node.id
            )
            report.rejections.extend(extraction.rejections)
            await _write_extraction(
                session, node, extraction, stamp=stamp, report=report
            )
            # Committed per unit rather than once at the end. A run that spends
            # real money on every iteration must not be able to lose the units it
            # has already paid for because a later one failed — and the rollback
            # below can only be safe if there is nothing uncommitted behind it.
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - one bad unit must not end the run
            await session.rollback()
            # A failed provider call is still a billed provider call. Metering
            # it here is what makes the budget bite on a systematic refusal,
            # which would otherwise be the one failure that spends the whole
            # allowance while every unit reports as skipped and free.
            if isinstance(exc, ExtractionUnavailableError):
                meter.record(
                    ExtractionCall(
                        payload={},
                        input_tokens=exc.input_tokens,
                        output_tokens=exc.output_tokens,
                    )
                )
            # Identified by id: the rollback has expired every loaded object, so
            # reading ``node.source_id`` for a friendlier message would raise a
            # second time inside the handler for the first.
            report.errors.append(f"node {unit_id}: {exc}")
            report.units_skipped += 1
            continue

        report.units_extracted += 1

    report.input_tokens = meter.input_tokens
    report.output_tokens = meter.output_tokens
    report.estimated_cost_usd = meter.spent_usd
    logger.info(
        "extraction: %d units, %d terms, %d edges, %d rejected, ~$%.4f (%s)",
        report.units_extracted,
        report.terms_created,
        report.edges_created,
        len(report.rejections),
        report.estimated_cost_usd,
        stamp,
    )
    return report


@dataclass(slots=True)
class SupersessionReport:
    """Nodes retired by applying publisher-stated supersession."""

    documents_superseded: int = 0
    nodes_updated: int = 0
    #: Nodes left active because the supersession claim was mutual. Reported
    #: rather than logged: it means two editions each claim to replace the
    #: other, which is a corpus defect somebody has to go and fix.
    conflicts_skipped: int = 0


async def apply_supersession(session: AsyncSession) -> SupersessionReport:
    """Retire every node a ``SUPERSEDES`` edge points at. Idempotent.

    Ingestion writes the edge from source metadata but leaves the predecessor's
    ``status`` alone, because a connector sees one document at a time and cannot
    know whether the thing it replaces is in the corpus yet. This closes that
    gap after the fact, which is still "captured at ingestion" in the sense
    ADR-021 requires: it is derived from stated metadata at load time, never
    inferred from text at query time.

    The flip cascades to every node sharing the superseded document's
    ``source_id``. A guideline's recommendations inherit its lifecycle — that is
    already how the connector assigns them (``guidelines.py``) — and a
    superseded guideline still serving individually-active clauses is exactly
    the failure the status column exists to prevent.
    """
    report = SupersessionReport()

    stated = await session.execute(
        select(KnowledgeEdge.from_node_id, KnowledgeEdge.to_node_id).where(
            KnowledgeEdge.edge_type == KnowledgeEdgeType.SUPERSEDES
        )
    )
    pairs = set(stated.all())

    # A mutual claim is not a supersession, it is a contradiction, and retiring
    # both sides of one would leave a clinical topic with no active guidance at
    # all — the worst available outcome, arrived at silently. Neither side is
    # retired; the pair is counted so somebody can go and fix the corpus.
    #
    # Longer cycles are handled by the same rule transitively: A→B→C→A retires
    # nothing extra that a mutual pair would not, because each edge is judged
    # against its own reverse and traversal itself is already cycle-guarded
    # (``app/repositories/knowledge.py``).
    superseded_ids = set()
    for from_id, to_id in pairs:
        if (to_id, from_id) in pairs:
            report.conflicts_skipped += 1
            logger.warning(
                "mutual SUPERSEDES between %s and %s — neither retired", from_id, to_id
            )
            continue
        superseded_ids.add(to_id)

    if not superseded_ids:
        return report

    result = await session.execute(
        select(KnowledgeNode.source_type, KnowledgeNode.source_id)
        .where(
            KnowledgeNode.id.in_(superseded_ids),
            # Only ``active`` is flipped. ``withdrawn`` is a stronger statement
            # than ``superseded`` and must not be softened by a later edge.
            KnowledgeNode.status == KnowledgeStatus.active,
        )
        .distinct()
    )
    documents = result.all()
    if not documents:
        return report

    for source_type, source_id in documents:
        updated = await session.execute(
            update(KnowledgeNode)
            .where(
                KnowledgeNode.source_type == source_type,
                KnowledgeNode.source_id == source_id,
                KnowledgeNode.status == KnowledgeStatus.active,
            )
            .values(status=KnowledgeStatus.superseded)
        )
        report.documents_superseded += 1
        report.nodes_updated += updated.rowcount or 0

    await session.commit()
    logger.info(
        "supersession applied: %d documents, %d nodes retired",
        report.documents_superseded,
        report.nodes_updated,
    )
    return report
