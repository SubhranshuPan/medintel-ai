# ADR-007 — GitHub Actions as CI/CD

## Status

Accepted

## Context

The project requires a CI/CD pipeline for automated testing, building, and deploying the application.

## Decision

GitHub Actions was selected as the CI/CD tool.

## Alternatives Considered

- GitLab CI
- Jenkins

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