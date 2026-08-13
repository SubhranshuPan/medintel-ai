"""PubMed connector — NCBI E-utilities ``esearch`` + ``efetch``.

Real medical literature with real publication dates and real reference lists, so
``CITES`` edges, authority tiers and (Sprint 4) temporal decay have genuine
signal rather than synthetic structure (design spec §9).

Two rules NCBI states and this module honours rather than hopes about:

* **Identify yourself.** ``tool`` and ``email`` are sent on every request. NCBI
  contacts the address before blocking a misbehaving client; an anonymous client
  is simply blocked.
* **Stay under the rate limit.** Three requests per second without an API key,
  ten with one. Enforced here by a shared minimum interval rather than left to
  caller discipline, because the caller is a batch loop and batch loops do not
  self-throttle.

Parsing is a pure function over bytes (:func:`parse_pubmed_xml`), so the whole
mapping is testable against the committed fixture with no network at all.
"""

import asyncio
import time
from collections.abc import Iterable, Sequence
from datetime import date

import httpx
from defusedxml import ElementTree as DefusedET

from app.models.knowledge import (
    KnowledgeNodeType,
    KnowledgeSourceType,
    KnowledgeStatus,
    UpdateCadence,
)
from app.services.ingestion.base import Section, SourceDocument

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

#: NCBI's published ceilings. Without a key: 3 req/s. With one: 10 req/s.
_RATE_LIMIT_NO_KEY = 3.0
_RATE_LIMIT_WITH_KEY = 10.0

#: PMIDs per ``efetch`` call. NCBI asks that large id lists use POST, which this
#: does; the batch size keeps any single response small enough to hold in memory.
EFETCH_BATCH_SIZE = 100

#: Hard ceiling on records per run. The extraction step (#63) spends one LLM call
#: per structural unit, so an unbounded corpus is an unbounded bill — the cap
#: belongs at the point that decides corpus size, not at the point that pays.
MAX_RECORDS_PER_RUN = 500

#: Refuse a response larger than this. NCBI is trusted, but "trusted" is not a
#: reason to let a single response exhaust the process's memory.
MAX_RESPONSE_BYTES = 32 * 1024 * 1024

#: Peer-reviewed literature is tier 2 — below a national guideline (tier 1),
#: above uncurated material. Read by ADR-017's ranking layer in Sprint 4.
PUBMED_AUTHORITY_TIER = 2

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}


class PubMedError(RuntimeError):
    """E-utilities returned something the connector will not guess about."""


class _RateLimiter:
    """Serialises requests to a minimum interval.

    Deliberately not a token bucket: a bucket permits a burst, and a burst is
    exactly what trips NCBI's limiter at the start of a batch run.
    """

    def __init__(self, per_second: float) -> None:
        self._interval = 1.0 / per_second
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._next_at:
                await asyncio.sleep(self._next_at - now)
            self._next_at = max(now, self._next_at) + self._interval


def _text(element, path: str) -> str | None:
    """Full text under ``path``, including any inline markup's tails."""
    found = element.find(path)
    if found is None:
        return None
    joined = "".join(found.itertext()).strip()
    return joined or None


def _parse_pub_date(element) -> date | None:
    """Best-effort publication date.

    PubMed dates are irregular — ``<Year>/<Month>/<Day>``, a bare year, or a
    free-text ``<MedlineDate>`` like "2024 Mar-Apr". A missing day or month
    falls back to the first of the period rather than dropping the date: knowing
    a guideline is from 2019 is what supersession reasoning needs, and precision
    to the day is not.
    """
    if element is None:
        return None
    year_text = _text(element, "Year")
    month_text = _text(element, "Month") or ""
    day_text = _text(element, "Day") or ""

    if year_text is None:
        # "2024 Mar-Apr" / "2024-2025". The month is in there and is worth
        # recovering: falling back to January would date a spring publication
        # to the previous quarter, which is a recency signal the ranking layer
        # reads in Sprint 4.
        parts = (_text(element, "MedlineDate") or "").split()
        if parts and parts[0][:4].isdigit():
            year_text = parts[0][:4]
            if len(parts) > 1 and not month_text:
                month_text = parts[1]
    if year_text is None or not year_text.isdigit():
        return None

    # "Mar", "March", "Mar-Apr" all reduce to the same first three letters;
    # a numeric "03" falls through to the isdigit branch.
    month = _MONTHS.get(month_text[:3].lower(), 0)
    if not month and month_text.isdigit():
        month = int(month_text)
    day = int(day_text) if day_text.isdigit() else 1
    try:
        return date(int(year_text), month or 1, day)
    except ValueError:
        return None


def _abstract_sections(article) -> tuple[Section, ...]:
    """Structured abstract sections, in document order.

    A structured abstract already carries the author's own section labels. Those
    become the chunker's boundaries in #62, so an unstructured abstract yields
    one unlabelled section rather than being force-split.
    """
    abstract = article.find("Abstract")
    if abstract is None:
        return ()
    sections: list[Section] = []
    for node in abstract.findall("AbstractText"):
        text = "".join(node.itertext()).strip()
        if not text:
            continue
        label = node.get("Label") or node.get("NlmCategory")
        sections.append(Section(heading=label.strip() if label else None, text=text))
    return tuple(sections)


def _categories(citation) -> list[str]:
    """MeSH descriptors, the closest thing PubMed has to a clinical category."""
    return [
        name
        for heading in citation.findall("MeshHeadingList/MeshHeading")
        if (name := _text(heading, "DescriptorName"))
    ]


def _reference_pmids(pubmed_data) -> tuple[str, ...]:
    """Cited PMIDs from the reference list — raw material for ``CITES`` edges.

    Only PMIDs: a DOI or a free-text citation cannot be resolved to a node in
    this corpus, and an edge to something we did not ingest is an edge we cannot
    store (both endpoints are foreign keys).
    """
    if pubmed_data is None:
        return ()
    seen: dict[str, None] = {}
    for article_id in pubmed_data.findall(
        "ReferenceList/Reference/ArticleIdList/ArticleId"
    ):
        if article_id.get("IdType") == "pubmed" and article_id.text:
            seen.setdefault(article_id.text.strip(), None)
    return tuple(seen)


def parse_pubmed_xml(payload: bytes) -> list[SourceDocument]:
    """Map an ``efetch`` XML response to source documents.

    Articles with no abstract are skipped: the node's ``text`` is what gets
    embedded and cited, and a title-only node is a citation the generation step
    cannot ground a claim in.
    """
    root = DefusedET.fromstring(payload)
    documents: list[SourceDocument] = []

    for entry in root.iter("PubmedArticle"):
        citation = entry.find("MedlineCitation")
        if citation is None:
            continue
        article = citation.find("Article")
        pmid = _text(citation, "PMID")
        if article is None or pmid is None:
            continue

        sections = _abstract_sections(article)
        if not sections:
            continue
        title = _text(article, "ArticleTitle") or f"PMID {pmid}"
        body = "\n\n".join(
            f"{s.heading}: {s.text}" if s.heading else s.text for s in sections
        )
        journal = _text(article, "Journal/Title")

        documents.append(
            SourceDocument(
                source_id=pmid,
                source_type=KnowledgeSourceType.pubmed,
                node_type=KnowledgeNodeType.article,
                title=title[:512],
                text=body,
                # A published article is a fixed artefact. It is never
                # ``superseded`` by ingestion — a retraction or a replacing
                # study is a SUPERSEDES edge, not a status rewrite, so the
                # original stays citable as what it was.
                status=KnowledgeStatus.active,
                update_cadence=UpdateCadence.static,
                external_ref=f"PMID:{pmid}",
                effective_date=_parse_pub_date(
                    article.find("Journal/JournalIssue/PubDate")
                ),
                authority_tier=PUBMED_AUTHORITY_TIER,
                category=_categories(citation),
                sections=sections,
                references=_reference_pmids(entry.find("PubmedData")),
                source_venue=journal,
                # No heading path: an article node *is* the document, the same
                # way a guideline node is. That is what a CITES reference
                # resolves to — heading paths key the units *within* a document.
                heading_path=None,
            )
        )
    return documents


class PubMedConnector:
    """Fetches PubMed abstracts for a configured clinical query set."""

    def __init__(
        self,
        *,
        tool: str,
        email: str,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not tool or not email:
            # NCBI's terms require both. Failing here beats being rate-limited
            # into silence halfway through a run with no explanation.
            raise ValueError("PubMed requires a tool name and contact email")
        self._params = {"tool": tool, "email": email, "db": "pubmed"}
        if api_key:
            self._params["api_key"] = api_key
        self._limiter = _RateLimiter(
            _RATE_LIMIT_WITH_KEY if api_key else _RATE_LIMIT_NO_KEY
        )
        self._client = client
        self._timeout = timeout

    async def _request(self, method: str, path: str, data: dict[str, str]) -> bytes:
        await self._limiter.wait()
        params = {**self._params, **data}
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            if method == "POST":
                response = await client.post(f"{EUTILS_BASE}/{path}", data=params)
            else:
                response = await client.get(f"{EUTILS_BASE}/{path}", params=params)
            response.raise_for_status()
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise PubMedError(
                    f"{path} returned {len(response.content)} bytes, over the "
                    f"{MAX_RESPONSE_BYTES}-byte cap"
                )
            return response.content
        finally:
            if self._client is None:
                await client.aclose()

    async def search(self, query: str, *, retmax: int) -> list[str]:
        """PMIDs matching ``query``, most recent first."""
        retmax = max(0, min(retmax, MAX_RECORDS_PER_RUN))
        if retmax == 0:
            return []
        payload = await self._request(
            "GET",
            "esearch.fcgi",
            {"term": query, "retmax": str(retmax), "sort": "date", "retmode": "xml"},
        )
        root = DefusedET.fromstring(payload)
        return [node.text.strip() for node in root.iter("Id") if node.text]

    async def fetch(self, pmids: Sequence[str]) -> list[SourceDocument]:
        """Full records for ``pmids``, batched under NCBI's POST guidance."""
        documents: list[SourceDocument] = []
        for start in range(0, len(pmids), EFETCH_BATCH_SIZE):
            batch = pmids[start : start + EFETCH_BATCH_SIZE]
            payload = await self._request(
                "POST",
                "efetch.fcgi",
                {"id": ",".join(batch), "retmode": "xml", "rettype": "abstract"},
            )
            documents.extend(parse_pubmed_xml(payload))
        return documents

    async def collect(
        self, queries: Iterable[str], *, per_query: int = 25
    ) -> list[SourceDocument]:
        """Search each query and fetch the union of results.

        Deduplicated across queries by PMID, so overlapping clinical queries
        ("heart failure", "cardiac resynchronisation") cost one fetch per article
        rather than one per query that matched it.
        """
        pmids: dict[str, None] = {}
        for query in queries:
            if len(pmids) >= MAX_RECORDS_PER_RUN:
                break
            headroom = MAX_RECORDS_PER_RUN - len(pmids)
            for pmid in await self.search(query, retmax=min(per_query, headroom)):
                pmids.setdefault(pmid, None)
        return await self.fetch(list(pmids))
