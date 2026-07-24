# ADR-003 — PostgreSQL as Relational Database

## Status

Accepted

## Context

The platform needs a system of record for patient cohort data (synthetic
but handled as if it were real PHI), append-only audit logs required by the
project's GDPR-aware stance, dataset version metadata (ADR-009), user/auth
records, and ML training-run metadata (ADR-010). These all require real
transactional integrity — an audit trail that can silently lose or
duplicate a row is not acceptable even for a portfolio project aiming to
demonstrate production-grade thinking.

## Decision

PostgreSQL was selected as the relational database.

## Alternatives Considered

- MySQL — weaker JSON/array column support and a thinner window-function
  ecosystem, both of which matter for cohort analytics queries and flexible
  clinical attributes.
- SQLite — no real concurrent-write support and no row-level security;
  fine for prototyping but unsuitable once the API, background jobs, and
  eventual multi-user access all write concurrently.

## Consequences

### Positive

- Native JSONB support allows flexible, semi-structured clinical attributes
  (e.g. ICD code lists) to sit alongside strictly-typed relational columns
  in the same schema, without a second database.
- Strong ACID guarantees and row-level security suit GDPR-aware, PHI-style
  handling — particularly the append-only audit log, which must not lose
  writes.
- Mature Python integration (SQLAlchemy, asyncpg) plugs directly into
  FastAPI (ADR-001) and Alembic migrations (ADR-013) with no adapter layer.
- Widely used in real NHS and UK health-tech backends, making it a directly
  transferable, recruiter-recognizable skill rather than a portfolio-only
  choice.

### Negative

- Requires running a separate database service in local dev and CI, unlike
  SQLite's zero-ops single-file simplicity — addressed by containerizing it
  via Docker Compose (ADR-006).
- Horizontal write-scaling is harder than some NoSQL alternatives; not a
  real constraint at portfolio scale, but worth naming honestly rather than
  glossing over for interview purposes.
- Every schema change goes through an Alembic migration (ADR-013), which is
  process overhead a schemaless store wouldn't impose — acceptable given
  the auditability that overhead buys.

## References

- ADR-006 — Docker containerization
- ADR-009 — Dataset versioning strategy
- ADR-013 — SQLAlchemy ORM and Alembic migrations
