"""Knowledge extraction and supersession (#63).

Two things are worth testing here and they are not the happy path.

**What the extractor refuses.** Every guarantee in this layer is a rejection:
an edge type a model may not assert, a target it was never shown, a confidence
outside the range the database would reject anyway. ``parse_extraction`` is pure,
so the whole rejection surface is exercised from hand-written payloads with no
API key and no network — which is the point of keeping validation out of the
provider class.

**What it costs.** A pipeline that spends money per row of corpus needs its caps
tested like any other correctness property. A budget that is only checked after
the call, or a unit cap that is documented but not enforced, is not a cap.

The model is scripted throughout. A test that asserted on real extraction quality
would be asserting on the weather.
"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select
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
from app.services.extraction import (
    EXTRACTION_TOOL_SCHEMA,
    MODEL_EXTRACTABLE_EDGE_TYPES,
    PROMPT_VERSION,
    BudgetExceededError,
    CostMeter,
    ExtractionCall,
    ExtractionModel,
    ExtractionUnavailableError,
    apply_supersession,
    build_prompt,
    estimate_cost_usd,
    extract_knowledge,
    extractor_stamp,
    parse_extraction,
    select_candidates,
    select_units,
    term_slug,
)
from app.services.extraction.runner import TERM_HEADING_PREFIX

# --------------------------------------------------------------------------
# scripted model
# --------------------------------------------------------------------------


class ScriptedModel:
    """An :class:`ExtractionModel` that replays fixed payloads.

    Records every prompt it was given, so the tests can assert on what the
    corpus actually put in front of the model — the candidate set is a
    correctness property, not a presentation detail, because it is the set
    outside which a target is rejected.
    """

    def __init__(
        self,
        payloads: list[dict] | None = None,
        *,
        model_id: str = "claude-haiku-4-5",
        input_tokens: int = 1_000,
        output_tokens: int = 200,
        fail_on: int | None = None,
    ) -> None:
        self._payloads = payloads or []
        self._model_id = model_id
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._fail_on = fail_on
        self.prompts: list[str] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    async def extract(self, system: str, user: str) -> ExtractionCall:
        index = len(self.prompts)
        self.prompts.append(user)
        if self._fail_on is not None and index == self._fail_on:
            raise RuntimeError("provider blew up on this unit")
        payload = (
            self._payloads[index]
            if index < len(self._payloads)
            else {"entities": [], "relationships": []}
        )
        return ExtractionCall(
            payload=payload,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


def test_scripted_model_satisfies_the_protocol() -> None:
    """The seam is real, not a shape the tests invented for themselves."""
    assert isinstance(ScriptedModel(), ExtractionModel)


# --------------------------------------------------------------------------
# the constrained schema
# --------------------------------------------------------------------------


def test_schema_stays_within_the_strict_output_limits() -> None:
    """ADR-022's strict tool-use rules are a contract, not advice.

    ``additionalProperties: false`` on every object is what makes the API reject
    an extra field rather than passing it through to a parser that ignores it.
    """

    def walk(node: dict, path: str) -> None:
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False, path
            for name, child in node.get("properties", {}).items():
                walk(child, f"{path}.{name}")
        if node.get("type") == "array":
            walk(node["items"], f"{path}[]")
            # A length constraint here would be rejected by strict output; the
            # caps are enforced in parse_extraction instead.
            assert "maxItems" not in node and "minItems" not in node, path

    walk(EXTRACTION_TOOL_SCHEMA, "root")


def test_model_may_not_assert_supersedes_or_cites() -> None:
    """The clinical-safety line: a model cannot retire live guidance.

    ``SUPERSEDES`` is the one edge type that removes guidance from retrieval, and
    it is stated by publishers, so it is never in the model's vocabulary.
    """
    assert KnowledgeEdgeType.SUPERSEDES not in MODEL_EXTRACTABLE_EDGE_TYPES
    assert KnowledgeEdgeType.CITES not in MODEL_EXTRACTABLE_EDGE_TYPES

    enum_values = set(
        EXTRACTION_TOOL_SCHEMA["properties"]["relationships"]["items"]["properties"][
            "edge_type"
        ]["enum"]
    )
    assert enum_values == {str(e) for e in MODEL_EXTRACTABLE_EDGE_TYPES}


@pytest.mark.parametrize(
    ("edge_type", "reason"),
    [
        ("SUPERSEDES", "edge_type not model-extractable"),
        ("CITES", "edge_type not model-extractable"),
        ("CAUSES", "edge_type not model-extractable"),
        ("exception_to", "edge_type not model-extractable"),
    ],
)
def test_out_of_set_edge_types_are_rejected_not_coerced(
    edge_type: str, reason: str
) -> None:
    """Nothing is mapped onto a nearest neighbour.

    ``exception_to`` is in the list on purpose: it is one casing away from a
    valid type, which is exactly the case a forgiving parser would "helpfully"
    accept and thereby make the closed set meaningless.
    """
    target = uuid.uuid4()
    result = parse_extraction(
        {
            "entities": [],
            "relationships": [
                {
                    "target_ref": 1,
                    "edge_type": edge_type,
                    "confidence": 0.9,
                    "evidence": "...",
                }
            ],
        },
        [target],
        source_node_id=uuid.uuid4(),
    )
    assert result.relationships == []
    assert [r.reason for r in result.rejections] == [reason]


@pytest.mark.parametrize(
    ("target_ref", "reason"),
    [
        (0, "target_ref outside candidate set"),
        (3, "target_ref outside candidate set"),
        (-1, "target_ref outside candidate set"),
        ("2", "target_ref outside candidate set"),
        (None, "target_ref outside candidate set"),
    ],
)
def test_targets_outside_the_candidate_set_are_rejected(
    target_ref, reason: str
) -> None:
    """A hallucinated target has nowhere to point.

    The model is shown a numbered list and may only answer with one of those
    numbers. Anything else would produce an edge to a node that either does not
    exist or was never offered, and generation could not cite it.
    """
    result = parse_extraction(
        {
            "relationships": [
                {
                    "target_ref": target_ref,
                    "edge_type": "RELATED_TO",
                    "confidence": 0.9,
                    "evidence": "",
                }
            ]
        },
        [uuid.uuid4(), uuid.uuid4()],
        source_node_id=uuid.uuid4(),
    )
    assert result.relationships == []
    assert [r.reason for r in result.rejections] == [reason]


def test_self_referential_edges_are_rejected() -> None:
    """A node cannot be its own exception."""
    node_id = uuid.uuid4()
    result = parse_extraction(
        {
            "relationships": [
                {
                    "target_ref": 1,
                    "edge_type": "EXCEPTION_TO",
                    "confidence": 1.0,
                    "evidence": "",
                }
            ]
        },
        [node_id],
        source_node_id=node_id,
    )
    assert result.relationships == []
    assert result.rejections[0].reason == "self-referential edge"


@pytest.mark.parametrize(
    ("confidence", "reason"),
    [
        (1.4, "confidence not a number in [0, 1]"),
        (-0.1, "confidence not a number in [0, 1]"),
        ("high", "confidence not a number in [0, 1]"),
        (True, "confidence not a number in [0, 1]"),
        (0.2, "confidence below threshold"),
    ],
)
def test_confidence_is_validated_before_it_reaches_the_database(
    confidence, reason: str
) -> None:
    """Caught in Python, not by the CHECK constraint.

    The constraint would also reject an out-of-range value — but a constraint
    violation aborts the transaction, which on a bulk run would discard every
    unit already paid for.
    """
    result = parse_extraction(
        {
            "relationships": [
                {
                    "target_ref": 1,
                    "edge_type": "RELATED_TO",
                    "confidence": confidence,
                    "evidence": "",
                }
            ]
        },
        [uuid.uuid4()],
        source_node_id=uuid.uuid4(),
    )
    assert result.relationships == []
    assert [r.reason for r in result.rejections] == [reason]


def test_malformed_containers_are_rejected_without_raising() -> None:
    """One bad payload must not end a corpus-wide run."""
    result = parse_extraction(
        {"entities": "not a list", "relationships": [42, None]},
        [uuid.uuid4()],
        source_node_id=uuid.uuid4(),
    )
    assert result.entities == []
    assert result.relationships == []
    assert {r.reason for r in result.rejections} == {"not a list", "not an object"}


def test_entity_and_relationship_counts_are_capped() -> None:
    """The one output a model can inflate without bound.

    Every entity becomes a node, so an unbounded list is unbounded corpus growth
    from a single call.
    """
    from app.services.extraction.schema import (
        MAX_ENTITIES_PER_UNIT,
        MAX_RELATIONSHIPS_PER_UNIT,
    )

    target = uuid.uuid4()
    result = parse_extraction(
        {
            "entities": [
                {"name": f"term {i}", "definition": "d"}
                for i in range(MAX_ENTITIES_PER_UNIT + 5)
            ],
            "relationships": [
                {
                    "target_ref": 1,
                    "edge_type": "RELATED_TO",
                    "confidence": 0.9,
                    "evidence": "",
                }
                for _ in range(MAX_RELATIONSHIPS_PER_UNIT + 5)
            ],
        },
        [target],
        source_node_id=uuid.uuid4(),
    )
    assert len(result.entities) == MAX_ENTITIES_PER_UNIT
    # All but the first collapse into one edge downstream, but the parser's own
    # cap is what bounds the work before dedup ever runs.
    assert len(result.relationships) == MAX_RELATIONSHIPS_PER_UNIT


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HFrEF ", "hfref"),
        ("  heart   failure ", "heart-failure"),
        ("eGFR (ml/min/1.73m2)", "egfr-ml-min-1-73m2"),
    ],
)
def test_term_slug_normalises_phrasing(raw: str, expected: str) -> None:
    """Two spellings of one term must not become two nodes."""
    assert term_slug(raw) == expected


# --------------------------------------------------------------------------
# cost
# --------------------------------------------------------------------------


def test_cost_meter_refuses_the_call_that_would_exceed_the_budget() -> None:
    """Checked before spending, so the ceiling bounds the bill not the report."""
    meter = CostMeter(model_id="claude-haiku-4-5", budget_usd=0.01)
    meter.check()  # nothing spent yet
    for _ in range(5):
        meter.record(ExtractionCall(payload={}, input_tokens=1_000, output_tokens=500))
    # 5 x (1000 in @ $1/Mtok + 500 out @ $5/Mtok) = $0.0175
    assert meter.spent_usd == pytest.approx(0.0175)
    with pytest.raises(BudgetExceededError):
        meter.check()


def test_unknown_model_is_priced_at_the_most_expensive_known_tier() -> None:
    """An unpriced model must fail safe towards under-spending."""
    unknown = estimate_cost_usd("some-future-model", 1_000_000, 0)
    assert unknown == estimate_cost_usd("claude-sonnet-5", 1_000_000, 0)
    assert unknown > estimate_cost_usd("claude-haiku-4-5", 1_000_000, 0)


# --------------------------------------------------------------------------
# database-backed behaviour
# --------------------------------------------------------------------------


@pytest.fixture
def session_factory(_engine: AsyncEngine) -> Callable[[], AsyncSession]:
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


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
    }
    return KnowledgeNode(**{**defaults, **overrides})


async def _seed(session: AsyncSession, nodes: list[KnowledgeNode]) -> None:
    session.add_all(nodes)
    await session.commit()


def test_extraction_writes_terms_and_edges_stamped_with_the_extractor(
    session_factory,
) -> None:
    """The whole path: call, validate, persist, provenance.

    ``extracted_by`` on every model-written edge is what makes the graph
    re-validatable when the extractor changes — an unversioned graph rots
    silently, which is the failure ADR-021 calls out by name.
    """

    async def _run():
        async with session_factory() as session:
            rule = _node("1.1.1 First-line therapy for HFrEF")
            exception = _node(
                "1.1.2 Exception: severe chronic kidney disease",
                heading_path="Pharmacological management > 1.1.2",
            )
            await _seed(session, [rule, exception])

            model = ScriptedModel(
                [
                    # First unit gets a term; second relates back to the first.
                    {
                        "entities": [
                            {
                                "name": "HFrEF",
                                "definition": "Heart failure with an ejection "
                                "fraction at or below 40%.",
                            }
                        ],
                        "relationships": [],
                    },
                    {
                        "entities": [],
                        "relationships": [
                            {
                                "target_ref": 1,
                                "edge_type": "EXCEPTION_TO",
                                "confidence": 0.92,
                                "evidence": "does not apply unmodified",
                            }
                        ],
                    },
                ]
            )
            report = await extract_knowledge(
                session, model, max_units=10, budget_usd=1.0
            )

            edges = (await session.execute(select(KnowledgeEdge))).scalars().all()
            terms = (
                (
                    await session.execute(
                        select(KnowledgeNode).where(
                            KnowledgeNode.node_type == KnowledgeNodeType.term
                        )
                    )
                )
                .scalars()
                .all()
            )
            return report, list(edges), list(terms)

    report, edges, terms = asyncio.run(_run())

    assert report.units_extracted == 2
    assert report.terms_created == 1
    assert report.edges_created == 2

    stamp = extractor_stamp("claude-haiku-4-5")
    assert stamp == f"claude-haiku-4-5/{PROMPT_VERSION}"
    assert {edge.extracted_by for edge in edges} == {stamp}

    by_type = {edge.edge_type: edge for edge in edges}
    assert set(by_type) == {
        KnowledgeEdgeType.DEFINED_BY,
        KnowledgeEdgeType.EXCEPTION_TO,
    }
    # A term-definition edge is a structural fact about the passage, not a
    # judgement call, so it carries no confidence.
    assert by_type[KnowledgeEdgeType.DEFINED_BY].confidence is None
    assert by_type[KnowledgeEdgeType.EXCEPTION_TO].confidence == pytest.approx(0.92)

    assert len(terms) == 1
    assert terms[0].heading_path == f"{TERM_HEADING_PREFIX}hfref"
    # A term inherits the lifecycle of the document that defines it.
    assert terms[0].status is KnowledgeStatus.active
    assert terms[0].source_id == "MSGC-CHF-2026"


def test_rerunning_the_same_extractor_is_a_no_op(session_factory) -> None:
    """Re-running must not multiply the graph, or cost a second time.

    Idempotency here is a spend property as much as a data one: extraction is
    the only pipeline in the platform billed per row.
    """

    async def _run():
        async with session_factory() as session:
            await _seed(session, [_node("1.1.1 First-line therapy")])
            payload = {
                "entities": [{"name": "HFrEF", "definition": "EF <= 40%."}],
                "relationships": [],
            }
            first = await extract_knowledge(
                session, ScriptedModel([payload]), budget_usd=1.0
            )
            second_model = ScriptedModel([payload])
            second = await extract_knowledge(session, second_model, budget_usd=1.0)
            edges = (await session.execute(select(KnowledgeEdge))).scalars().all()
            return first, second, second_model.prompts, len(list(edges))

    first, second, prompts, edge_count = asyncio.run(_run())
    assert first.edges_created == 1
    assert second.units_extracted == 0
    assert prompts == []  # the model was never called a second time
    assert edge_count == 1


def test_receiving_an_edge_does_not_count_as_having_been_extracted(
    session_factory,
) -> None:
    """The watermark tracks what a unit *produced*, not what points at it.

    A passage that a sibling named as its ``EXCEPTION_TO`` target has had
    nothing extracted *from* it, and skipping it would silently leave a hole in
    the graph that no report would show — the run would look complete.
    """

    async def _run():
        async with session_factory() as session:
            subject = _node("1.1.1 Rule", heading_path="rule")
            other = _node("1.1.2 Exception", heading_path="exception")
            await _seed(session, [subject, other])
            session.add(
                KnowledgeEdge(
                    from_node_id=other.id,
                    to_node_id=subject.id,
                    edge_type=KnowledgeEdgeType.EXCEPTION_TO,
                    confidence=0.9,
                    extracted_by=extractor_stamp("claude-haiku-4-5"),
                )
            )
            await session.commit()
            units = await select_units(
                session, stamp=extractor_stamp("claude-haiku-4-5"), limit=10
            )
            return sorted(unit.title for unit in units)

    # ``other`` produced the edge and is done; ``subject`` only received it.
    assert asyncio.run(_run()) == ["1.1.1 Rule"]


def test_a_failing_unit_does_not_end_the_run(session_factory) -> None:
    """One malformed passage should not cost the corpus its extraction pass."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("1.1.1 First", heading_path="a"),
                    _node("1.1.2 Second", heading_path="b"),
                    _node("1.1.3 Third", heading_path="c"),
                ],
            )
            model = ScriptedModel(
                [
                    {"entities": [{"name": "T1", "definition": "d"}]},
                    {"entities": []},
                    {"entities": [{"name": "T3", "definition": "d"}]},
                ],
                fail_on=1,
            )
            return await extract_knowledge(session, model, budget_usd=1.0)

    report = asyncio.run(_run())
    assert report.units_extracted == 2
    assert report.units_skipped == 1
    assert len(report.errors) == 1


def test_a_model_asserted_defined_by_does_not_watermark_its_target(
    session_factory,
) -> None:
    """``DEFINED_BY`` is in the model's vocabulary as well as the term's.

    Only a *term node's* outgoing ``DEFINED_BY`` is evidence that a passage was
    extracted. A passage that a sibling pointed at with the same edge type has
    had nothing extracted from it, and treating that as done would leave it
    permanently unextracted while the run reported success.
    """

    async def _run():
        async with session_factory() as session:
            subject = _node("1.1.1 Rule", heading_path="rule")
            other = _node("1.1.2 Other", heading_path="other")
            await _seed(session, [subject, other])
            session.add(
                KnowledgeEdge(
                    from_node_id=other.id,
                    to_node_id=subject.id,
                    edge_type=KnowledgeEdgeType.DEFINED_BY,
                    confidence=0.8,
                    extracted_by=extractor_stamp("claude-haiku-4-5"),
                )
            )
            await session.commit()
            units = await select_units(
                session, stamp=extractor_stamp("claude-haiku-4-5"), limit=10
            )
            return sorted(unit.title for unit in units)

    assert asyncio.run(_run()) == ["1.1.1 Rule"]


def test_units_after_a_failure_are_still_extracted(session_factory) -> None:
    """The rollback must not poison the rest of the run.

    Rolling back expires every object in the session, so a run that held its
    units as ORM instances would fail on the *next* unit's first attribute read
    — turning one bad passage into a dead run that still reported per-unit
    isolation.
    """

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [_node(f"1.1.{i} Rec", heading_path=f"p{i}") for i in range(4)],
            )
            model = ScriptedModel(
                [{"entities": [{"name": f"T{i}", "definition": "d"}]} for i in range(4)],
                fail_on=0,
            )
            report = await extract_knowledge(session, model, budget_usd=1.0)
            edges = (await session.execute(select(KnowledgeEdge))).scalars().all()
            return report, len(list(edges))

    report, edges = asyncio.run(_run())
    assert report.units_skipped == 1
    assert report.units_extracted == 3
    assert edges == 3


def test_a_refused_call_is_still_metered(session_factory) -> None:
    """A provider that refuses every call still bills for every call.

    This is the one failure that would otherwise spend the whole allowance
    while every unit reported as skipped and free.
    """

    class RefusingModel:
        model_id = "claude-haiku-4-5"

        async def extract(self, system: str, user: str) -> ExtractionCall:
            raise ExtractionUnavailableError(
                "no tool_use block in response",
                input_tokens=1_000,
                output_tokens=100,
            )

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [_node(f"1.1.{i} Rec", heading_path=f"p{i}") for i in range(6)],
            )
            return await extract_knowledge(
                session, RefusingModel(), max_units=10, budget_usd=0.004
            )

    report = asyncio.run(_run())
    assert report.units_extracted == 0
    # $0.0015 per refused call, so the $0.004 ceiling trips on the fourth check.
    assert report.budget_exhausted is True
    assert report.estimated_cost_usd > 0
    # Every unit is accounted for exactly once, whether it errored or was cut.
    assert report.units_skipped == 6


def test_the_unit_cap_bounds_a_run(session_factory) -> None:
    """A corpus cap enforced in code, not only documented in the issue."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [_node(f"1.1.{i} Rec", heading_path=f"p{i}") for i in range(6)],
            )
            model = ScriptedModel()
            report = await extract_knowledge(
                session, model, max_units=2, budget_usd=1.0
            )
            return report, len(model.prompts)

    report, calls = asyncio.run(_run())
    assert calls == 2
    assert report.units_extracted == 2


def test_the_budget_stops_a_run_and_says_so(session_factory) -> None:
    """Exhausting the budget ends the run cleanly, and reports that it did.

    A partial graph is acceptable; a partial graph nobody knows is partial is
    not — the next stage would read it as a complete corpus.
    """

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [_node(f"1.1.{i} Rec", heading_path=f"p{i}") for i in range(6)],
            )
            # $0.002 buys exactly one call at 1000 in / 200 out on Haiku
            # ($0.001 + $0.001), after which the meter refuses.
            model = ScriptedModel()
            report = await extract_knowledge(
                session, model, max_units=10, budget_usd=0.002
            )
            return report, len(model.prompts)

    report, calls = asyncio.run(_run())
    assert calls == 1
    assert report.budget_exhausted is True
    assert report.units_extracted == 1
    assert report.units_skipped == 5
    assert report.estimated_cost_usd == pytest.approx(0.002)


def test_candidates_are_bounded_and_prefer_the_same_document(
    session_factory,
) -> None:
    """Same-document siblings first, because that is where exceptions live.

    "This recommendation does not apply to patients with…" sits beside the
    recommendation it qualifies, so a truncated candidate list must never be the
    reason an ``EXCEPTION_TO`` goes unextracted.
    """

    async def _run():
        async with session_factory() as session:
            subject = _node("1.1.1 Subject", heading_path="subject")
            sibling = _node("1.1.2 Sibling", heading_path="sibling")
            outsiders = [
                _node(
                    f"Other {i}",
                    source_id="MSGC-AF-2024",
                    heading_path=f"other-{i}",
                    effective_date=date(2024, 1, 1),
                )
                for i in range(5)
            ]
            await _seed(session, [subject, sibling, *outsiders])
            candidates = await select_candidates(session, subject, limit=3)
            return [c.title for c in candidates]

    titles = asyncio.run(_run())
    assert len(titles) == 3
    assert titles[0] == "1.1.2 Sibling"


def test_superseded_and_withdrawn_units_are_not_paid_for(session_factory) -> None:
    """Retired guidance is filtered out of retrieval anyway — do not extract it."""

    async def _run():
        async with session_factory() as session:
            await _seed(
                session,
                [
                    _node("Active", heading_path="a"),
                    _node(
                        "Old", heading_path="b", status=KnowledgeStatus.superseded
                    ),
                    _node(
                        "Gone", heading_path="c", status=KnowledgeStatus.withdrawn
                    ),
                ],
            )
            units = await select_units(session, stamp="x/y", limit=10)
            return [unit.title for unit in units]

    assert asyncio.run(_run()) == ["Active"]


def test_prompt_numbers_candidates_from_one() -> None:
    """The numbering is the contract the ``target_ref`` validation depends on."""
    subject = _node("Subject")
    candidates = [_node("First"), _node("Second")]
    prompt = build_prompt(subject, candidates)
    assert "1. First" in prompt
    assert "2. Second" in prompt
    assert "Subject" in prompt


def test_a_passage_with_no_candidates_still_produces_a_valid_prompt() -> None:
    """A single-document corpus must not emit an empty candidate section."""
    assert "(none)" in build_prompt(_node("Alone"), [])


# --------------------------------------------------------------------------
# supersession
# --------------------------------------------------------------------------


def test_supersession_retires_the_whole_predecessor_document(
    session_factory,
) -> None:
    """The flip cascades to every node of the superseded document.

    A guideline's recommendations inherit its lifecycle. A superseded guideline
    still serving individually-active clauses is precisely the failure the
    status column exists to prevent.
    """

    async def _run():
        async with session_factory() as session:
            old_doc = _node(
                "Chronic heart failure (2019)",
                node_type=KnowledgeNodeType.guideline,
                source_id="MSGC-CHF-2019",
                heading_path=None,
                effective_date=date(2019, 6, 1),
            )
            old_rec = _node(
                "1.1.1 First-line (2019)",
                source_id="MSGC-CHF-2019",
                heading_path="Pharmacological management > 1.1.1",
                effective_date=date(2019, 6, 1),
            )
            new_doc = _node(
                "Chronic heart failure (2026)",
                node_type=KnowledgeNodeType.guideline,
                heading_path=None,
            )
            unrelated = _node(
                "Atrial fibrillation", source_id="MSGC-AF-2024", heading_path=None
            )
            await _seed(session, [old_doc, old_rec, new_doc, unrelated])
            session.add(
                KnowledgeEdge(
                    from_node_id=new_doc.id,
                    to_node_id=old_doc.id,
                    edge_type=KnowledgeEdgeType.SUPERSEDES,
                    # Stated by the publisher, so no confidence and no extractor.
                    confidence=None,
                    extracted_by=None,
                )
            )
            await session.commit()

            report = await apply_supersession(session)
            rerun = await apply_supersession(session)

            rows = (await session.execute(select(KnowledgeNode))).scalars().all()
            return report, rerun, {node.title: node.status for node in rows}

    report, rerun, statuses = asyncio.run(_run())

    assert report.documents_superseded == 1
    assert report.nodes_updated == 2
    assert statuses["Chronic heart failure (2019)"] is KnowledgeStatus.superseded
    assert statuses["1.1.1 First-line (2019)"] is KnowledgeStatus.superseded
    # The replacement and an unrelated guideline are untouched.
    assert statuses["Chronic heart failure (2026)"] is KnowledgeStatus.active
    assert statuses["Atrial fibrillation"] is KnowledgeStatus.active
    # Idempotent: a second pass finds nothing left to retire.
    assert rerun.documents_superseded == 0


def test_supersession_never_softens_a_withdrawn_node(session_factory) -> None:
    """``withdrawn`` is a stronger statement than ``superseded``.

    Guidance pulled outright must not be quietly downgraded to "replaced" by a
    later edge — the two mean different things to a clinician.
    """

    async def _run():
        async with session_factory() as session:
            old = _node(
                "Withdrawn guidance",
                node_type=KnowledgeNodeType.guideline,
                source_id="MSGC-OLD",
                heading_path=None,
                status=KnowledgeStatus.withdrawn,
            )
            new = _node("Replacement", node_type=KnowledgeNodeType.guideline,
                        heading_path=None)
            await _seed(session, [old, new])
            session.add(
                KnowledgeEdge(
                    from_node_id=new.id,
                    to_node_id=old.id,
                    edge_type=KnowledgeEdgeType.SUPERSEDES,
                )
            )
            await session.commit()
            await apply_supersession(session)
            await session.refresh(old)
            return old.status

    assert asyncio.run(_run()) is KnowledgeStatus.withdrawn


def test_mutually_superseding_editions_are_both_left_active(
    session_factory,
) -> None:
    """A contradiction must not retire everything.

    If two editions each claim to replace the other, retiring both would leave
    the topic with no active guidance at all — a clinician's query would return
    nothing where it should return something, and nothing in the report would
    say why. Neither side is retired, and the conflict is counted so somebody
    can go and fix the corpus.
    """

    async def _run():
        async with session_factory() as session:
            first = _node(
                "Edition A",
                node_type=KnowledgeNodeType.guideline,
                source_id="MSGC-A",
                heading_path=None,
            )
            second = _node(
                "Edition B",
                node_type=KnowledgeNodeType.guideline,
                source_id="MSGC-B",
                heading_path=None,
            )
            await _seed(session, [first, second])
            session.add_all(
                [
                    KnowledgeEdge(
                        from_node_id=first.id,
                        to_node_id=second.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    ),
                    KnowledgeEdge(
                        from_node_id=second.id,
                        to_node_id=first.id,
                        edge_type=KnowledgeEdgeType.SUPERSEDES,
                    ),
                ]
            )
            await session.commit()
            report = await apply_supersession(session)
            rows = (await session.execute(select(KnowledgeNode))).scalars().all()
            return report, {node.title: node.status for node in rows}

    report, statuses = asyncio.run(_run())
    assert report.nodes_updated == 0
    assert report.conflicts_skipped == 2
    assert statuses["Edition A"] is KnowledgeStatus.active
    assert statuses["Edition B"] is KnowledgeStatus.active


def test_supersession_is_derived_from_stated_edges_only(session_factory) -> None:
    """No other edge type retires anything.

    ``RELATED_TO`` between two editions is a plausible model output; it must not
    be able to withdraw guidance.
    """

    async def _run():
        async with session_factory() as session:
            old = _node("Older", source_id="MSGC-OLD", heading_path=None)
            new = _node("Newer", heading_path=None)
            await _seed(session, [old, new])
            session.add(
                KnowledgeEdge(
                    from_node_id=new.id,
                    to_node_id=old.id,
                    edge_type=KnowledgeEdgeType.RELATED_TO,
                    confidence=0.99,
                    extracted_by=extractor_stamp("claude-haiku-4-5"),
                )
            )
            await session.commit()
            report = await apply_supersession(session)
            await session.refresh(old)
            return report, old.status

    report, status = asyncio.run(_run())
    assert report.nodes_updated == 0
    assert status is KnowledgeStatus.active
