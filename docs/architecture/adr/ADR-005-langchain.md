# ADR-005 — LangChain + LangGraph as Orchestration Framework

## Status

Accepted

## Context

The RAG-based AI decision support pillar needs to orchestrate retrieval
(Qdrant, ADR-004), prompt construction, LLM calls, and multi-step reasoning
— e.g. retrieve a relevant clinical guideline, combine it with a patient's
ML-predicted risk score, and generate a grounded explanation. Given the
project's GDPR-aware handling requirement, this orchestration also needs to
be auditable: it must be possible to reconstruct exactly what was retrieved
and what was sent to the LLM for any given output, not just get a final
answer back.

## Decision

LangChain + LangGraph was selected as the orchestration framework.

## Alternatives Considered

- LlamaIndex — stronger for pure retrieval/indexing workflows, but weaker
  for the explicit multi-step, stateful reasoning this pillar needs.
- A custom orchestration layer built directly against an LLM SDK — offers
  the most control, but means re-implementing retrieval chaining, memory,
  and tracing that LangChain already provides; not a good use of a single
  developer's time across a five-pillar project with a fixed timeline.

## Consequences

### Positive

- LangGraph's explicit state-graph model produces auditable, inspectable
  multi-step reasoning chains, which supports demonstrating explainable,
  non-black-box AI decision support rather than an opaque prompt-in,
  answer-out chatbot.
- Large integration ecosystem (Qdrant, LLM providers, output parsers) means
  less custom glue code to write and maintain.
- Widely recognized in the ML engineering job market, making it a directly
  discussable, transferable skill for target roles.

### Negative

- Fast-moving library with real breaking changes between versions, which
  requires version pinning and periodic maintenance work that a smaller,
  stabler dependency wouldn't impose.
- Its abstractions can obscure exactly what prompt/context was sent to the
  LLM unless explicitly logged — the project must instrument LangChain
  calls with its own audit logging to preserve GDPR-aware traceability
  rather than relying on the library's defaults.
- Adds a real learning-curve and debugging cost compared to calling an LLM
  API directly for the simpler request paths.

## References

- ADR-004 — Qdrant as vector database
- ADR-017 — Advanced RAG retrieval
- `docs/00_VISION_ML_PLATFORM.md`
