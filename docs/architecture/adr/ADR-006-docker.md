# ADR-006 — Docker 

## Status

Accepted

## Context

The project require to deploy the application in a containerized environment.

## Decision

Docker was selected as the containerization technology.

## Alternatives Considered

- Podman

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