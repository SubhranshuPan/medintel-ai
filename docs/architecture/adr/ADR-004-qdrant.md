# ADR-004 — Qdrant as Vector Database

## Status

Accepted

## Context

The project requires a high-performance vector database for semantic search and RAG.

## Decision

Qdrant was selected as the vector database.

## Alternatives Considered

- ChromaDB
- Pinecone

## Consequences

### Positive

- Excellent async support
- Automatic OpenAPI generation
- Strong typing
- High performance

### Negative

- Smaller ecosystem than Django
- Requires familiarity with async programming

## References

- TRD Section 10.2