# ADR-004 — Qdrant as Vector Database

## Status

Accepted

## Context

The RAG-based AI decision support pillar needs semantic retrieval over
embedded clinical guidelines and reference material to ground LLM responses
(orchestrated via LangChain, ADR-005), combined with structured metadata
filtering — e.g. restricting retrieval to a specific ICD-code category or
clinical pathway rather than pure nearest-neighbour search across
everything. The project also runs on a self-funded student budget (SBI
loan-financed), which rules out recurring per-query SaaS costs for
infrastructure that can be self-hosted at zero marginal cost.

## Decision

Qdrant was selected as the vector database.

## Alternatives Considered

- ChromaDB — simpler and embeddable, but a weaker production filtering and
  scaling story for combined vector + metadata queries.
- Pinecone — strong managed offering, but a recurring SaaS cost unsuitable
  for a loan-financed budget; self-hosting a vector database is also itself
  a demonstrable ML-infrastructure skill worth having in the portfolio,
  which a managed service would abstract away entirely.

## Consequences

### Positive

- Open-source and self-hostable via Docker (ADR-006) at zero recurring
  cost, which matters directly given the project's budget constraint.
- Rich payload filtering combines vector similarity with structured
  metadata filters in one query — needed for clinical-guideline retrieval
  that must respect category/pathway constraints, not just similarity.
- Written in Rust with strong production performance characteristics,
  giving a defensible technical answer in interviews beyond "it was the
  first result in a tutorial."
- Native Python client integrates directly with LangChain's vector-store
  interface (ADR-005) with no custom adapter code.

### Negative

- Self-hosting means the project owns backup, persistence, and upgrade
  operations that a managed service like Pinecone would otherwise handle.
- Smaller managed-hosting ecosystem and community than Pinecone if the
  project ever needed a hosted production tier beyond the portfolio scope.
- Another stateful service in the Docker Compose stack alongside
  PostgreSQL, adding local-development resource overhead.

## References

- ADR-005 — LangChain as orchestration framework
- ADR-006 — Docker containerization
- ADR-017 — Advanced RAG retrieval
