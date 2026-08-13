"""Corpus ingestion (#61) — fetch source documents with provenance intact.

The layer that decides whether "which version is current" is answerable at all.
Every downstream stage (chunking, extraction, retrieval, generation) can only
filter and cite the provenance captured here; none of them can reconstruct a
stable id, an effective date or a lifecycle status that ingestion did not record.

Connectors produce :class:`~app.services.ingestion.base.SourceDocument` and touch
no session; :func:`~app.services.ingestion.runner.ingest_documents` persists them
idempotently. Source licensing positions are recorded in ADR-023.
"""

from app.services.ingestion.base import Section, SourceDocument
from app.services.ingestion.guidelines import (
    GuidelineCorpusError,
    load_guideline_corpus,
    parse_guideline_corpus,
)
from app.services.ingestion.pubmed import (
    PubMedConnector,
    PubMedError,
    parse_pubmed_xml,
)
from app.services.ingestion.runner import IngestionReport, ingest_documents

__all__ = [
    "GuidelineCorpusError",
    "IngestionReport",
    "PubMedConnector",
    "PubMedError",
    "Section",
    "SourceDocument",
    "ingest_documents",
    "load_guideline_corpus",
    "parse_guideline_corpus",
    "parse_pubmed_xml",
]
