"""Corpus ingestion (#61).

Two things are worth testing here and the rest is plumbing.

First, that provenance survives the parse: an effective date, a stable id and a
lifecycle status that arrive wrong or absent cannot be recovered by any later
stage, because there is nothing left to recover them from.

Second, that re-running ingestion is a no-op. A duplicated guideline is two
retrievable answers to a question that has one, and the failure is invisible
until a clinician is shown both.

Both connectors are exercised against committed fixtures, so the suite needs no
network and no NCBI quota.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path

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
from app.services.ingestion import (
    GuidelineCorpusError,
    PubMedConnector,
    ingest_documents,
    load_guideline_corpus,
    parse_guideline_corpus,
    parse_pubmed_xml,
)
from app.services.ingestion.pubmed import _RateLimiter

FIXTURES = Path(__file__).resolve().parent.parent / "app" / "services" / "ingestion" / "fixtures"
PUBMED_FIXTURE = FIXTURES / "pubmed_sample.xml"


@pytest.fixture
def session_factory(_engine: AsyncEngine) -> Callable[[], AsyncSession]:
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def pubmed_docs():
    return parse_pubmed_xml(PUBMED_FIXTURE.read_bytes())


@pytest.fixture
def guideline_docs():
    return load_guideline_corpus()


# --------------------------------------------------------------------------
# PubMed connector
# --------------------------------------------------------------------------


def test_pubmed_parses_provenance(pubmed_docs) -> None:
    """PMID, journal, date and category all survive the parse."""
    article = next(d for d in pubmed_docs if d.source_id == "40010001")

    assert article.source_type is KnowledgeSourceType.pubmed
    assert article.node_type is KnowledgeNodeType.article
    assert article.external_ref == "PMID:40010001"
    assert article.effective_date == date(2026, 2, 14)
    assert article.source_venue == "Journal of Cardiac Failure Research"
    # No heading path: an article node *is* its document, which is what a CITES
    # reference has to resolve to. Journal belongs in source_venue, not here.
    assert article.heading_path is None
    assert "Heart Failure" in article.category
    # A published article is a fixed artefact — never re-dated, never re-statused
    # by ingestion. A retraction is an edge, not a status rewrite.
    assert article.status is KnowledgeStatus.active
    assert article.update_cadence is UpdateCadence.static


def test_pubmed_keeps_structured_abstract_sections(pubmed_docs) -> None:
    """Author-written section labels are the chunker's boundaries in #62.

    If they were flattened here, #62 would have to re-derive structure from
    prose that no longer carries it.
    """
    article = next(d for d in pubmed_docs if d.source_id == "40010001")

    assert [s.heading for s in article.sections] == [
        "BACKGROUND",
        "METHODS",
        "RESULTS",
        "CONCLUSIONS",
    ]
    # Inline markup contributes its text rather than truncating the section at
    # the first child element.
    results = next(s for s in article.sections if s.heading == "RESULTS")
    assert "not significantly different" in results.text


def test_pubmed_handles_medline_date_and_unstructured_abstract(pubmed_docs) -> None:
    """A free-text MedlineDate still yields a usable year."""
    article = next(d for d in pubmed_docs if d.source_id == "40010002")

    # "2019 Mar-Apr" — precision to the day is not what supersession reasoning
    # needs; knowing the year is.
    assert article.effective_date == date(2019, 3, 1)
    assert [s.heading for s in article.sections] == [None]


def test_pubmed_skips_articles_without_an_abstract(pubmed_docs) -> None:
    """A title-only node is a citation nothing can be grounded in."""
    assert all(d.source_id != "40010003" for d in pubmed_docs)


def test_pubmed_collects_only_pmid_references(pubmed_docs) -> None:
    """DOIs are dropped: an edge endpoint has to be a node in this corpus."""
    article = next(d for d in pubmed_docs if d.source_id == "40010001")

    assert article.references == ("40010002", "39990000")


def test_pubmed_requires_tool_and_email() -> None:
    """NCBI's terms are not optional, and being silently blocked is worse."""
    with pytest.raises(ValueError, match="tool name and contact email"):
        PubMedConnector(tool="medintel-ai", email="")


def test_rate_limiter_spaces_requests() -> None:
    """Three calls at 50/s must take at least two intervals, not burst.

    A burst is precisely what trips NCBI's limiter at the start of a batch run,
    so the limiter must not permit one even when idle beforehand.
    """

    async def _run() -> float:
        limiter = _RateLimiter(50.0)
        loop = asyncio.get_running_loop()
        started = loop.time()
        for _ in range(3):
            await limiter.wait()
        return loop.time() - started

    assert asyncio.run(_run()) >= 2 / 50.0


# --------------------------------------------------------------------------
# Guideline corpus
# --------------------------------------------------------------------------


def test_guideline_corpus_is_never_labelled_nice(guideline_docs) -> None:
    """ADR-023: authored content must not claim a publisher that did not publish it.

    The single most damaging thing this pillar could do is attach a real
    authority's name to text that authority never wrote, since every downstream
    citation would then be a false attribution.
    """
    assert guideline_docs
    assert all(
        d.source_type is KnowledgeSourceType.synthetic_guideline for d in guideline_docs
    )


def test_guideline_yields_document_and_recommendation_nodes(guideline_docs) -> None:
    """One guideline node plus one node per numbered recommendation."""
    chf = [d for d in guideline_docs if d.source_id == "MSGC-CHF-2026"]
    document = next(d for d in chf if d.node_type is KnowledgeNodeType.guideline)
    recommendations = [d for d in chf if d.node_type is KnowledgeNodeType.recommendation]

    # The guideline itself is the node with no heading path — that is what a
    # SUPERSEDES declaration resolves to.
    assert document.heading_path is None
    assert document.supersedes == "MSGC-CHF-2019"
    assert len(recommendations) == 4
    first_line = next(r for r in recommendations if r.external_ref.endswith("#1.1.1"))
    assert first_line.heading_path.endswith("> 1.1.1")
    assert first_line.effective_date == date(2026, 3, 1)


def test_recommendations_inherit_guideline_lifecycle(guideline_docs) -> None:
    """A withdrawn guideline must not keep serving individually-active clauses."""
    withdrawn = [d for d in guideline_docs if d.source_id == "MSGC-T2D-2021"]

    assert withdrawn
    assert all(d.status is KnowledgeStatus.withdrawn for d in withdrawn)


def test_corpus_contains_supersession_and_exception_cases(guideline_docs) -> None:
    """The evaluation harness (#67) needs these to exist from somewhere.

    A corpus without a superseded guideline cannot demonstrate the
    architecture's central claim, so their presence is asserted rather than
    assumed.
    """
    statuses = {d.status for d in guideline_docs}
    assert KnowledgeStatus.superseded in statuses
    assert KnowledgeStatus.withdrawn in statuses
    assert KnowledgeStatus.active in statuses

    # Two guidelines answering the same clinical question, one current.
    chf_first_line = [
        d
        for d in guideline_docs
        if d.external_ref and d.external_ref.endswith("#1.1.1") and "CHF" in d.source_id
    ]
    assert len(chf_first_line) == 2
    assert {d.status for d in chf_first_line} == {
        KnowledgeStatus.active,
        KnowledgeStatus.superseded,
    }

    assert any("exception to recommendation" in d.text.lower() for d in guideline_docs)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ("{}", "must be a JSON array"),
        ("not json", "not valid JSON"),
        ('[{"title": "x", "status": "active"}]', "missing required field 'source_id'"),
        ('[{"source_id": "a", "title": "x", "status": "sideways"}]', "not one of"),
        (
            '[{"source_id": "a", "title": "x", "status": "active",'
            ' "effective_date": "not-a-date"}]',
            "bad ISO date",
        ),
    ],
)
def test_malformed_corpus_fails_loudly(payload: str, match: str) -> None:
    """A partially-loaded corpus is worse than a failed load: it looks complete."""
    with pytest.raises(GuidelineCorpusError, match=match):
        parse_guideline_corpus(payload)


def test_status_is_required_per_guideline() -> None:
    """No default. A defaulted status is how "withdrawn" quietly stops meaning it."""
    with pytest.raises(GuidelineCorpusError, match="missing required field 'status'"):
        parse_guideline_corpus(json.dumps([{"source_id": "a", "title": "x"}]))


# --------------------------------------------------------------------------
# Persistence — idempotency and declared edges
# --------------------------------------------------------------------------


def _ingest(session_factory, documents):
    async def _run():
        async with session_factory() as session:
            return await ingest_documents(session, documents)

    return asyncio.run(_run())


def _count(session_factory, model) -> int:
    async def _run() -> int:
        async with session_factory() as session:
            result = await session.execute(select(model))
            return len(list(result.scalars().all()))

    return asyncio.run(_run())


def test_ingestion_persists_every_document(session_factory, guideline_docs) -> None:
    report = _ingest(session_factory, guideline_docs)

    assert report.created == len(guideline_docs)
    assert report.updated == 0
    assert _count(session_factory, KnowledgeNode) == len(guideline_docs)


def test_reingesting_an_unchanged_corpus_writes_nothing(
    session_factory, guideline_docs
) -> None:
    """The property the whole module exists for.

    Re-running must not multiply the corpus, or "which recommendation is
    current" stops being answerable by the mechanism meant to answer it.
    """
    _ingest(session_factory, guideline_docs)
    before = _count(session_factory, KnowledgeNode)

    second = _ingest(session_factory, guideline_docs)

    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == len(guideline_docs)
    assert second.edges_created == 0
    assert _count(session_factory, KnowledgeNode) == before


def test_reingestion_updates_in_place_when_the_source_changes(
    session_factory, guideline_docs
) -> None:
    """An upstream editorial fix updates a node; it does not fork one."""
    _ingest(session_factory, guideline_docs)
    before = _count(session_factory, KnowledgeNode)

    edited = [
        replace(d, text=f"{d.text} Reviewed 2026.")
        if d.source_id == "MSGC-AF-2024"
        else d
        for d in guideline_docs
    ]
    report = _ingest(session_factory, edited)

    changed = sum(1 for d in guideline_docs if d.source_id == "MSGC-AF-2024")
    assert report.updated == changed
    assert report.created == 0
    assert _count(session_factory, KnowledgeNode) == before


def test_declared_supersession_becomes_an_edge(
    session_factory, guideline_docs
) -> None:
    """The 2026 guideline supersedes the 2019 one, and the graph says so."""
    _ingest(session_factory, guideline_docs)

    async def _run():
        async with session_factory() as session:
            nodes = {
                (n.source_id, n.heading_path): n
                for n in (await session.execute(select(KnowledgeNode))).scalars()
            }
            edges = list(
                (await session.execute(select(KnowledgeEdge))).scalars()
            )
            return nodes, edges

    nodes, edges = asyncio.run(_run())
    current = nodes[("MSGC-CHF-2026", None)]
    stale = nodes[("MSGC-CHF-2019", None)]

    supersedes = [e for e in edges if e.edge_type is KnowledgeEdgeType.SUPERSEDES]
    assert len(supersedes) == 1
    assert supersedes[0].from_node_id == current.id
    assert supersedes[0].to_node_id == stale.id
    # Stated by the source, not inferred by a model — that is what tells #63's
    # re-validation pass to leave this edge alone.
    assert supersedes[0].confidence is None
    assert supersedes[0].extracted_by is None


def test_citations_are_written_only_within_the_corpus(
    session_factory, pubmed_docs
) -> None:
    """A reference to an article we never ingested has nowhere to point.

    Both edge columns are foreign keys, so an out-of-corpus citation is counted
    and dropped rather than written as a dangling edge.
    """
    report = _ingest(session_factory, pubmed_docs)

    assert report.edges_created == 1  # 40010001 CITES 40010002
    assert report.unresolved_references == 1  # PMID 39990000 is outside the corpus

    async def _run():
        async with session_factory() as session:
            return list((await session.execute(select(KnowledgeEdge))).scalars())

    edges = asyncio.run(_run())
    assert [e.edge_type for e in edges] == [KnowledgeEdgeType.CITES]


def test_reingestion_does_not_duplicate_edges(session_factory, pubmed_docs) -> None:
    """Edge identity is checked before insert, not left to the unique constraint.

    A constraint violation would abort the surrounding transaction and take the
    whole re-run down with it.
    """
    _ingest(session_factory, pubmed_docs)
    second = _ingest(session_factory, pubmed_docs)

    assert second.edges_created == 0
    assert _count(session_factory, KnowledgeEdge) == 1


def test_mixed_sources_ingest_together(
    session_factory, guideline_docs, pubmed_docs
) -> None:
    """Both connectors write into one graph without colliding on source_id."""
    report = _ingest(session_factory, [*guideline_docs, *pubmed_docs])

    assert report.created == len(guideline_docs) + len(pubmed_docs)
    assert report.edges_created == 2  # one SUPERSEDES, one CITES


def test_empty_ingestion_is_a_no_op(session_factory) -> None:
    report = _ingest(session_factory, [])

    assert report.nodes_written == 0
    assert _count(session_factory, KnowledgeNode) == 0
