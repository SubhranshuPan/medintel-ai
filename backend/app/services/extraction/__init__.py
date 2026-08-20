"""Knowledge extraction (#63) — prose to typed, provenanced graph structure.

The layer naive RAG does not have. Retrieval can only filter and cite the
structure something put there; nothing downstream can recover "this
recommendation has an exception for severe CKD" from a paragraph that was
indexed as undifferentiated text.

What is inferred by a model and what is stated by a publisher are kept strictly
apart, and the split runs through the whole module:

* :mod:`~app.services.extraction.schema` — the constrained contract. A model may
  assert ``DEFINED_BY``, ``EXCEPTION_TO`` and ``RELATED_TO`` and nothing else;
  ``SUPERSEDES`` and ``CITES`` are publisher facts and are never inferred.
* :mod:`~app.services.extraction.provider` — the model seam and the spend
  ceiling, since this is the only pipeline in the platform that costs money per
  row of corpus.
* :mod:`~app.services.extraction.runner` — the run itself, plus
  :func:`~app.services.extraction.runner.apply_supersession`, which is what
  actually retires superseded guidance from retrieval.

Model choice and pricing are ADR-022; the graph itself is ADR-021.
"""

from app.services.extraction.provider import (
    MODEL_RATES_USD_PER_MTOK,
    AnthropicExtractor,
    BudgetExceededError,
    CostMeter,
    ExtractionCall,
    ExtractionModel,
    ExtractionUnavailableError,
    build_extractor,
    estimate_cost_usd,
)
from app.services.extraction.runner import (
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MAX_UNITS,
    SYSTEM_PROMPT,
    ExtractionReport,
    SupersessionReport,
    apply_supersession,
    build_prompt,
    extract_knowledge,
    extractor_stamp,
    select_candidates,
    select_units,
)
from app.services.extraction.schema import (
    EXTRACTION_TOOL_NAME,
    EXTRACTION_TOOL_SCHEMA,
    MODEL_EXTRACTABLE_EDGE_TYPES,
    PROMPT_VERSION,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
    Rejection,
    parse_extraction,
    term_slug,
)

__all__ = [
    "DEFAULT_MAX_CANDIDATES",
    "DEFAULT_MAX_UNITS",
    "EXTRACTION_TOOL_NAME",
    "EXTRACTION_TOOL_SCHEMA",
    "MODEL_EXTRACTABLE_EDGE_TYPES",
    "MODEL_RATES_USD_PER_MTOK",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "AnthropicExtractor",
    "BudgetExceededError",
    "CostMeter",
    "ExtractedEntity",
    "ExtractedRelationship",
    "ExtractionCall",
    "ExtractionModel",
    "ExtractionReport",
    "ExtractionResult",
    "ExtractionUnavailableError",
    "Rejection",
    "SupersessionReport",
    "apply_supersession",
    "build_extractor",
    "build_prompt",
    "estimate_cost_usd",
    "extract_knowledge",
    "extractor_stamp",
    "parse_extraction",
    "select_candidates",
    "select_units",
    "term_slug",
]
