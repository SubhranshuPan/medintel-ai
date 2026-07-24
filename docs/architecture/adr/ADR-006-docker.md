# ADR-006 — Docker for Containerization

## Status

Accepted

## Context

The platform has multiple stateful services (PostgreSQL, Qdrant) plus the
FastAPI backend and React frontend, and needs to run identically on the
developer's machine, in CI (GitHub Actions, ADR-007), and in eventual
deployment. Reproducibility matters more here than in a typical CRUD app:
if the ML training/serving environment drifts between machines, SHAP
explanations and predictions produced in one environment are not
trustworthy evidence of behaviour in another.

## Decision

Docker was selected as the containerization technology, with Docker
Compose for local multi-service orchestration.

## Alternatives Considered

- Podman — daemonless and rootless, technically comparable, but smaller
  ecosystem and tooling support and less universal support across the CI
  and deployment platforms a UK health-tech employer is likely to use.
- Running services natively without containers — fastest to start locally,
  but breaks dev/CI/deployment parity and makes onboarding and CI setup
  brittle as the number of services grows.

## Consequences

### Positive

- Identical environments across dev, CI, and deployment remove "works on
  my machine" risk — important given that model-training environment
  drift can itself change SHAP output.
- Docker Compose gives one-command startup for the full multi-service stack
  (PostgreSQL, Qdrant, backend, frontend), lowering the barrier for anyone
  reviewing or running the project.
- Near-universal support across CI providers and cloud deployment targets
  keeps future deployment options open rather than locking into one
  platform's native tooling.

### Negative

- Adds real virtualization overhead on the developer's own machine during
  local development, especially running Postgres and Qdrant simultaneously.
- Multi-stage Dockerfiles and Compose networking are additional
  infrastructure to write and keep correct, not a one-time cost.
- Image size and build time become an ongoing CI cost to manage as ML
  dependencies (SHAP, LangChain, model libraries) grow.

## References

- ADR-007 — GitHub Actions CI/CD
- ADR-008 — Modular monolith architecture
