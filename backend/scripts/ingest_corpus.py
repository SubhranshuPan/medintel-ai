"""Corpus ingestion entry point (#61).

    python -m scripts.ingest_corpus --source guidelines
    python -m scripts.ingest_corpus --source pubmed --per-query 25
    python -m scripts.ingest_corpus --source all --dry-run

Idempotent: re-running over an unchanged corpus reports only ``unchanged`` and
writes nothing. That is the property worth checking after any connector change,
and it is what the printed report exists to make checkable.

PubMed ingestion needs ``MEDINTEL_PUBMED_EMAIL`` set — NCBI requires a contact
address on every call, and the run refuses rather than sending an invented one.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow `python scripts/ingest_corpus.py` from the backend root, not only
# `python -m scripts.ingest_corpus`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.db import AsyncSessionLocal  # noqa: E402
from app.services.ingestion import (  # noqa: E402
    PubMedConnector,
    SourceDocument,
    ingest_documents,
    load_guideline_corpus,
)

logger = logging.getLogger("ingest_corpus")

SOURCES = ("pubmed", "guidelines", "all")


async def _collect(source: str, per_query: int | None) -> list[SourceDocument]:
    settings = get_settings()
    documents: list[SourceDocument] = []

    if source in ("guidelines", "all"):
        guidelines = load_guideline_corpus()
        logger.info("guideline corpus: %d documents", len(guidelines))
        documents.extend(guidelines)

    if source in ("pubmed", "all"):
        if not settings.pubmed_email:
            raise SystemExit(
                "MEDINTEL_PUBMED_EMAIL is required for PubMed ingestion. "
                "NCBI contacts this address before blocking a client; an "
                "unset or borrowed one means someone else gets the warning."
            )
        connector = PubMedConnector(
            tool=settings.pubmed_tool,
            email=settings.pubmed_email,
            api_key=settings.pubmed_api_key,
        )
        articles = await connector.collect(
            settings.pubmed_queries,
            per_query=per_query or settings.pubmed_results_per_query,
        )
        logger.info("pubmed: %d documents", len(articles))
        documents.extend(articles)

    return documents


async def _run(source: str, per_query: int | None, dry_run: bool) -> int:
    documents = await _collect(source, per_query)
    if not documents:
        logger.warning("no documents collected — nothing to ingest")
        return 1

    if dry_run:
        by_type: dict[str, int] = {}
        for document in documents:
            by_type[document.node_type] = by_type.get(document.node_type, 0) + 1
        print(f"dry run — {len(documents)} documents, nothing written")
        for node_type, count in sorted(by_type.items()):
            print(f"  {node_type:>16}: {count}")
        return 0

    async with AsyncSessionLocal() as session:
        report = await ingest_documents(session, documents)

    print(
        f"created={report.created} updated={report.updated} "
        f"unchanged={report.unchanged} edges={report.edges_created} "
        f"unresolved_refs={report.unresolved_references}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=SOURCES, default="all")
    parser.add_argument(
        "--per-query",
        type=int,
        default=None,
        help="PubMed results per query (default: MEDINTEL_PUBMED_RESULTS_PER_QUERY)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse, print what would be written, touch nothing",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(_run(args.source, args.per_query, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
