# ADR-001 — FastAPI as Backend Framework

## Status

Accepted

## Context

MedIntel AI's backend must serve a REST API across all five pillars: patient
data ingestion/management, clinical analytics queries, ML risk-prediction
(including SHAP explainability output), and RAG-based AI decision support,
where LLM and vector-store calls (LangChain, Qdrant — ADR-004, ADR-005) are
I/O-bound and benefit from native async handling. The API also needs
request/response schema validation strict enough to catch malformed clinical
data early (ICD codes, patient cohort fields) given the project's
GDPR-aware, PHI-style data-handling stance, and needs to produce a
recruiter-readable, interview-defensible codebase built by a single
developer against a fixed timeline (interview-ready by November 2026).

## Decision

FastAPI was selected as the backend framework.

## Alternatives Considered

- Django — batteries-included (ORM, admin panel, auth), but sync-first by
  design; its async support is newer and less central to the framework than
  FastAPI's, which matters for LLM/vector-DB-heavy request paths.
- Flask — minimal and flexible, but has no async support or request
  validation built in; both would need to be bolted on via extensions,
  effectively rebuilding what FastAPI provides natively.

## Consequences

### Positive

- Native `async`/`await` support suits the I/O-bound calls this project
  makes constantly — LangChain LLM calls, Qdrant similarity search,
  PostgreSQL queries — without blocking the event loop.
- Pydantic-based request/response models give free schema validation at the
  API boundary, which matters for clinical data integrity (malformed ICD
  codes or cohort fields are rejected before they reach the database).
- Automatic OpenAPI/Swagger documentation keeps the API contract
  recruiter-readable and interview-demoable without hand-written API docs.
- Dependency-injection system (`Depends`) is a clean fit for cross-cutting
  concerns this project requires everywhere — auth, and the audit-logging
  middleware GDPR-aware handling depends on.
- Strong typing (Pydantic + type hints) catches integration errors early,
  which matters more on a single-developer project with no second reviewer.

### Negative

- Smaller batteries-included ecosystem than Django — no built-in ORM or
  admin panel, so the project pairs FastAPI with SQLAlchemy and Alembic
  separately (ADR-013) rather than getting them for free.
- Async-everywhere discipline is required: a blocking call inside an async
  route (e.g. a sync ML/SHAP library invoked without offloading to a thread
  pool) silently degrades throughput instead of failing loudly — a real risk
  given SHAP and some ML tooling are not async-native.
- Fewer opinionated conventions than Django means more upfront architectural
  decisions fall to the developer (addressed via the modular monolith
  structure in ADR-008 rather than left ad hoc).

## References

- ADR-008 — Modular monolith architecture
- ADR-013 — SQLAlchemy ORM and Alembic migrations
- `docs/00_VISION_ML_PLATFORM.md`
