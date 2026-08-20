"""The constrained extraction contract (#63) — schema in, validated edges out.

Naive RAG stores prose and hopes the retriever finds the right paragraph. This
module is the alternative: prose is turned into typed, provenanced relationships
**once, at ingestion**, against a schema the model is not free to deviate from.

Three constraints stack, and each catches what the one before it cannot:

1. **The API constrains the model.** ``EXTRACTION_TOOL_SCHEMA`` is passed as a
   strict tool definition (ADR-022), so a malformed shape is rejected before it
   reaches Python.
2. **This module constrains the meaning.** A schema can require that
   ``edge_type`` be a string; it cannot require that the string is one of ours,
   that the target is a node we actually hold, or that the model did not invent
   a supersession. :func:`parse_extraction` does that, and *rejects* — never
   coerces, never picks a nearest match.
3. **The database constrains the write.** The edge type is a PostgreSQL enum and
   both endpoints are foreign keys (ADR-021), so anything the first two miss
   fails on flush rather than landing in the graph.

Rejection is recorded, not silently dropped: :class:`Rejection` carries the
reason, and the runner counts them. An extractor whose rejection rate climbs is
a prompt regression, and it should be a number somebody can see rather than a
log line nobody reads.
"""

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.knowledge import KnowledgeEdgeType

logger = logging.getLogger(__name__)

#: Bumped whenever the prompt or this schema changes in a way that could change
#: what the model emits. Stamped into every edge's ``extracted_by`` alongside the
#: model id, so the graph can be re-validated per extractor version rather than
#: rebuilt wholesale when the extractor moves on.
PROMPT_VERSION = "extract-v1"

#: The edge types a *model* is allowed to assert. Deliberately a strict subset of
#: ``KnowledgeEdgeType``.
#:
#: ``SUPERSEDES`` and ``CITES`` are excluded on clinical-safety grounds, not for
#: convenience. Both are facts the publisher states outright — a guideline says
#: which edition it replaces, a paper lists its references — and both are already
#: written from that metadata at ingestion (#61). Letting a model *infer* them
#: would mean an inferred supersession could flip a live recommendation to
#: ``superseded`` and remove current guidance from retrieval, on nothing stronger
#: than a paraphrase. The failure would be silent and clinically material, so the
#: model is never given the option.
#:
#: The remaining three are safe to infer: they add reachable context, and a wrong
#: one degrades ranking rather than withdrawing guidance.
MODEL_EXTRACTABLE_EDGE_TYPES: frozenset[KnowledgeEdgeType] = frozenset(
    {
        KnowledgeEdgeType.DEFINED_BY,
        KnowledgeEdgeType.EXCEPTION_TO,
        KnowledgeEdgeType.RELATED_TO,
    }
)

#: Entities per structural unit. A cap rather than a guideline: entity count is
#: the one output the model can inflate without bound, and each one is a node.
MAX_ENTITIES_PER_UNIT = 8
#: Relationships per structural unit, capped for the same reason.
MAX_RELATIONSHIPS_PER_UNIT = 12

#: Longest accepted entity name. The schema cannot express a length limit under
#: ADR-022's strict-output rules, so it is enforced here instead.
MAX_ENTITY_NAME_CHARS = 120

#: Relationships the model is less than half sure of are not worth a graph edge.
#: The threshold lives here rather than in the prompt because a prompt-stated
#: threshold is a request and this is a rule.
MIN_CONFIDENCE = 0.5

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def term_slug(name: str) -> str:
    """Normalise an entity name into a stable, comparable key.

    Two mentions of ``"HFrEF "`` and ``"hfref"`` are the same term and must
    resolve to the same node, or the graph accumulates a near-duplicate per
    phrasing and ``DEFINED_BY`` stops being answerable.
    """
    return _SLUG_STRIP.sub("-", name.strip().lower()).strip("-")


#: Name of the tool the model is required to call. Tool use rather than free
#: text: the response either validates against the schema or there is no
#: response to parse.
EXTRACTION_TOOL_NAME = "record_clinical_knowledge"

# Written inside ADR-022's strict-output limits rather than around them: no
# recursion, no numeric or string length constraints, and
# ``additionalProperties: false`` on every object.
EXTRACTION_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entities", "relationships"],
    "properties": {
        "entities": {
            "type": "array",
            "description": (
                "Clinical terms this passage itself defines or characterises. "
                "Only terms the passage explains, not every term it mentions."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "definition"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The term as a clinician would name it.",
                    },
                    "definition": {
                        "type": "string",
                        "description": (
                            "How this passage defines the term, in its own "
                            "words. Do not supply outside knowledge."
                        ),
                    },
                },
            },
        },
        "relationships": {
            "type": "array",
            "description": (
                "Relationships from this passage to one of the numbered "
                "candidate passages. Emit none if none genuinely hold."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["target_ref", "edge_type", "confidence", "evidence"],
                "properties": {
                    "target_ref": {
                        "type": "integer",
                        "description": (
                            "The number of the candidate passage this relates "
                            "to. Must be one of the numbers listed."
                        ),
                    },
                    "edge_type": {
                        "type": "string",
                        "enum": sorted(str(e) for e in MODEL_EXTRACTABLE_EDGE_TYPES),
                        "description": (
                            "EXCEPTION_TO: this passage exempts or qualifies "
                            "the candidate. DEFINED_BY: the candidate defines a "
                            "term this passage depends on. RELATED_TO: a weaker "
                            "clinical association."
                        ),
                    },
                    "confidence": {
                        "type": "number",
                        "description": "0 to 1. Below 0.5 will be discarded.",
                    },
                    "evidence": {
                        "type": "string",
                        "description": (
                            "The span of this passage that supports the "
                            "relationship, quoted."
                        ),
                    },
                },
            },
        },
    },
}


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    """A clinical term the passage defines."""

    name: str
    definition: str

    @property
    def slug(self) -> str:
        return term_slug(self.name)


@dataclass(frozen=True, slots=True)
class ExtractedRelationship:
    """A typed relationship from the extracted node to a candidate node.

    ``evidence`` is required of the model but **not currently persisted** —
    ``KnowledgeEdge`` has no column for it. It is still worth the output tokens:
    requiring a quoted span is a grounding constraint on the model, and a model
    made to point at the text before asserting a relationship asserts fewer
    relationships the text does not support. It is carried here so the runner
    can log it when an extraction is being debugged.

    ponytail: storing it needs a column on ``knowledge_edges`` and a migration.
    Worth doing when the generation layer (#66) starts citing *why* a node was
    reached rather than only that it was — that is the consumer which makes the
    column pay for itself.
    """

    target_node_id: UUID
    edge_type: KnowledgeEdgeType
    confidence: float
    evidence: str


@dataclass(frozen=True, slots=True)
class Rejection:
    """One discarded item and why — counted, not swallowed."""

    kind: str
    reason: str
    detail: str


@dataclass(slots=True)
class ExtractionResult:
    """What survived validation from one call, plus what did not."""

    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)


def parse_extraction(
    raw: Mapping[str, Any],
    candidates: Sequence[UUID],
    *,
    source_node_id: UUID,
) -> ExtractionResult:
    """Validate one raw tool-call payload into terms and edges.

    Pure and side-effect free, so the whole rejection surface is testable
    without an API key: every branch below is reachable from a hand-written
    dict.

    ``candidates`` is the ordered list the prompt numbered from 1. A
    ``target_ref`` outside it is a hallucinated target and is rejected — the
    model may only relate the passage to nodes we actually put in front of it,
    which is what keeps every extracted edge resolvable to something citable.
    """
    result = ExtractionResult()

    def reject(kind: str, reason: str, detail: Any) -> None:
        rejection = Rejection(kind=kind, reason=reason, detail=str(detail)[:200])
        result.rejections.append(rejection)
        logger.warning(
            "extraction rejected %s (%s): %s", kind, reason, rejection.detail
        )

    entities = _as_objects(raw.get("entities"), "entity", reject)
    if len(entities) > MAX_ENTITIES_PER_UNIT:
        # Counted, not just sliced. Silent truncation would hide the single most
        # likely prompt regression — a model that starts listing every term it
        # recognises instead of the ones the passage defines — behind a
        # rejection rate that never moves.
        reject("entity", "over per-unit cap", len(entities))
    for item in entities[:MAX_ENTITIES_PER_UNIT]:
        name = str(item.get("name") or "").strip()
        definition = str(item.get("definition") or "").strip()
        if not name or not definition:
            reject("entity", "missing name or definition", item)
            continue
        if len(name) > MAX_ENTITY_NAME_CHARS:
            # A name this long is a sentence the model mislabelled as a term,
            # and it would become a permanent node title.
            reject("entity", "name too long", name)
            continue
        if not term_slug(name):
            reject("entity", "name has no alphanumeric content", name)
            continue
        result.entities.append(ExtractedEntity(name=name, definition=definition))

    relationships = _as_objects(raw.get("relationships"), "relationship", reject)
    if len(relationships) > MAX_RELATIONSHIPS_PER_UNIT:
        reject("relationship", "over per-unit cap", len(relationships))
    for item in relationships[:MAX_RELATIONSHIPS_PER_UNIT]:
        edge_type = _edge_type(item.get("edge_type"))
        if edge_type is None:
            # Covers both a type outside ``KnowledgeEdgeType`` entirely and one
            # inside it that a model may not assert (SUPERSEDES, CITES).
            # Rejected, never mapped onto a nearby type.
            reject(
                "relationship",
                "edge_type not model-extractable",
                item.get("edge_type"),
            )
            continue

        target = _target(item.get("target_ref"), candidates)
        if target is None:
            reject(
                "relationship",
                "target_ref outside candidate set",
                item.get("target_ref"),
            )
            continue
        if target == source_node_id:
            # A node cannot be its own exception, and a self-edge would make
            # traversal report the start node as one of its own results.
            reject("relationship", "self-referential edge", target)
            continue

        confidence = _confidence(item.get("confidence"))
        if confidence is None:
            reject(
                "relationship",
                "confidence not a number in [0, 1]",
                item.get("confidence"),
            )
            continue
        if confidence < MIN_CONFIDENCE:
            reject("relationship", "confidence below threshold", confidence)
            continue

        result.relationships.append(
            ExtractedRelationship(
                target_node_id=target,
                edge_type=edge_type,
                confidence=confidence,
                evidence=str(item.get("evidence") or "").strip()[:500],
            )
        )

    return result


def _as_objects(
    value: Any, kind: str, reject: Callable[[str, str, Any], None]
) -> list[Mapping[str, Any]]:
    """The object items of ``value``, rejecting anything that is not one."""
    if value is None:
        return []
    if not isinstance(value, list):
        reject(kind, "not a list", value)
        return []
    objects: list[Mapping[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            objects.append(item)
        else:
            reject(kind, "not an object", item)
    return objects


def _edge_type(value: Any) -> KnowledgeEdgeType | None:
    try:
        edge_type = KnowledgeEdgeType(str(value))
    except ValueError:
        return None
    return edge_type if edge_type in MODEL_EXTRACTABLE_EDGE_TYPES else None


def _target(value: Any, candidates: Sequence[UUID]) -> UUID | None:
    """Resolve a 1-based candidate number to the node id it referred to."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not 1 <= value <= len(candidates):
        return None
    return candidates[value - 1]


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    confidence = float(value)
    # The database CHECK constraint would reject an out-of-range value too, but
    # a constraint violation aborts the transaction and takes the whole run down
    # with it, so it is caught here instead.
    return confidence if 0.0 <= confidence <= 1.0 else None
