# ADR-001 — FastAPI as Backend Framework

## Status

Accepted

## Context

The project requires a high-performance Python backend that integrates well with AI libraries and automatically generates API documentation.

## Decision

FastAPI was selected as the backend framework.

## Alternatives Considered

- Django
- Flask

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