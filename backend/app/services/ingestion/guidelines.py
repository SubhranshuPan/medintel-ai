"""Clinical guideline connector — the NICE substitute corpus (ADR-023).

**Licensing position.** NICE guidance is licensed, and the NICE UK Open Content
Licence does not permit the bulk extraction this pillar would need; syndication
API access requires an approval we do not hold. So no scraper is shipped against
nice.org.uk — not throttled, not "just for a portfolio", not at all. The
substitute is an authored guideline corpus with deliberately-written
supersessions and exception clauses, labelled ``synthetic_guideline`` so no row
ever claims a publisher that did not publish it. Full reasoning and the
conditions for revisiting: ADR-023.

The corpus is authored rather than scraped, but the *shape* is faithful: stable
guideline ids, numbered recommendations, effective dates, explicit "replaces"
declarations, and exception clauses that sit apart from the rule they qualify.
That shape is what the rest of Sprint 3 is tested against — a corpus with no
superseded guidance cannot demonstrate the architecture's central claim
(design spec §8), and a scraped one we are not licensed to hold would not be
usable regardless of how good the retrieval over it was.

Loading is local-file only. If syndication access is ever granted, a fetch layer
lands in front of :func:`parse_guideline_corpus` and nothing downstream changes.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.models.knowledge import (
    KnowledgeNodeType,
    KnowledgeSourceType,
    KnowledgeStatus,
    UpdateCadence,
)
from app.services.ingestion.base import Section, SourceDocument

#: The committed corpus. Small and hand-authored by design — every entry exists
#: to exercise a specific retrieval behaviour (supersession, exception,
#: multi-hop), which is not a property a larger auto-collected corpus would have.
DEFAULT_CORPUS_PATH = Path(__file__).parent / "fixtures" / "guideline_corpus.json"

#: National-guideline tier. Authored content standing in for a national guideline
#: takes that guideline's tier, or the ranking layer it exists to exercise would
#: be exercised against the wrong authority ordering.
GUIDELINE_AUTHORITY_TIER = 1

#: Issuing body, carried onto every node so the corpus announces what it is at
#: the point of citation rather than only in this module's docstring. A reader
#: who sees this string in a rendered citation knows not to treat it as NICE.
GUIDELINE_VENUE = "MedIntel Synthetic Guideline Corpus (authored, ADR-023)"


class GuidelineCorpusError(ValueError):
    """The corpus file is malformed. Never silently partially loaded."""


def _require(entry: dict[str, Any], key: str, where: str) -> Any:
    if key not in entry or entry[key] in (None, ""):
        raise GuidelineCorpusError(f"{where}: missing required field {key!r}")
    return entry[key]


def _parse_date(value: str | None, where: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise GuidelineCorpusError(f"{where}: bad ISO date {value!r}") from exc


def _parse_enum(enum_cls, value: str, where: str, field: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(sorted(m.value for m in enum_cls))
        raise GuidelineCorpusError(
            f"{where}: {field} {value!r} is not one of: {allowed}"
        ) from exc


def parse_guideline_corpus(payload: str) -> list[SourceDocument]:
    """Map the authored corpus JSON to source documents.

    Each guideline yields one ``guideline`` node (the document itself, no
    heading path) plus one ``recommendation`` node per numbered recommendation.
    The recommendations share the guideline's ``source_id`` and are keyed apart
    by ``heading_path``, which is what makes re-ingestion an update rather than a
    duplication, and what lets a retrieved recommendation be shown inside the
    structure it came from instead of as an orphaned paragraph.

    Status is required per guideline, never defaulted: the one thing this corpus
    exists to test is that withdrawn guidance is not as retrievable as current
    guidance, and a defaulted status is how that guarantee quietly stops holding.
    """
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise GuidelineCorpusError(f"corpus is not valid JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise GuidelineCorpusError("corpus must be a JSON array of guidelines")

    documents: list[SourceDocument] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise GuidelineCorpusError(f"guideline[{index}] is not an object")
        source_id = str(_require(entry, "source_id", f"guideline[{index}]"))
        where = f"guideline {source_id}"

        status = _parse_enum(
            KnowledgeStatus, _require(entry, "status", where), where, "status"
        )
        cadence = _parse_enum(
            UpdateCadence,
            entry.get("update_cadence") or UpdateCadence.periodic.value,
            where,
            "update_cadence",
        )
        effective_date = _parse_date(entry.get("effective_date"), where)
        category = list(entry.get("category") or [])
        title = str(_require(entry, "title", where))
        summary = str(entry.get("summary") or title)
        recommendations = entry.get("recommendations") or []

        documents.append(
            SourceDocument(
                source_id=source_id,
                source_type=KnowledgeSourceType.synthetic_guideline,
                node_type=KnowledgeNodeType.guideline,
                title=title[:512],
                text=summary,
                status=status,
                update_cadence=cadence,
                external_ref=source_id,
                source_venue=GUIDELINE_VENUE,
                effective_date=effective_date,
                authority_tier=GUIDELINE_AUTHORITY_TIER,
                category=category,
                sections=(Section(heading=None, text=summary),),
                supersedes=entry.get("supersedes"),
            )
        )

        for rec_index, rec in enumerate(recommendations):
            rec_where = f"{where} recommendation[{rec_index}]"
            if not isinstance(rec, dict):
                raise GuidelineCorpusError(f"{rec_where} is not an object")
            number = str(_require(rec, "number", rec_where))
            heading_path = str(rec.get("heading_path") or "Recommendations")
            text = str(_require(rec, "text", rec_where))
            documents.append(
                SourceDocument(
                    source_id=source_id,
                    source_type=KnowledgeSourceType.synthetic_guideline,
                    node_type=KnowledgeNodeType.recommendation,
                    title=f"{number} {rec.get('title') or title}"[:512],
                    text=text,
                    # A recommendation inherits its guideline's lifecycle: when a
                    # guideline is superseded, every recommendation inside it is
                    # too. Deriving that here rather than restating it per
                    # recommendation removes the failure mode where a withdrawn
                    # guideline keeps serving individually-active clauses.
                    status=status,
                    update_cadence=cadence,
                    external_ref=f"{source_id}#{number}",
                    source_venue=GUIDELINE_VENUE,
                    effective_date=effective_date,
                    authority_tier=GUIDELINE_AUTHORITY_TIER,
                    category=list(rec.get("category") or category),
                    heading_path=f"{heading_path} > {number}",
                    sections=(Section(heading=number, text=text),),
                )
            )
    return documents


def load_guideline_corpus(path: Path | None = None) -> list[SourceDocument]:
    """Read and parse the committed corpus (no network, by design)."""
    corpus_path = path or DEFAULT_CORPUS_PATH
    if not corpus_path.is_file():
        raise GuidelineCorpusError(f"guideline corpus not found at {corpus_path}")
    return parse_guideline_corpus(corpus_path.read_text(encoding="utf-8"))
