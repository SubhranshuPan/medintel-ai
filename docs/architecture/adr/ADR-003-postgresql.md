# ADR-003 — PostgreSQL as Database

## Status

Accepted

## Context

The project requires a high-performance Python backend that integrates well with AI libraries and automatically generates API documentation.

## Decision

PostgreSQL was selected as the database.

## Alternatives Considered

- MySQL
- SQLite

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