# ADR-009 — Dataset Versioning Strategy

## Status

Accepted

## Context

The Patient Data Platform module requires users to upload CSV datasets, validate and clean them, and manage multiple datasets over time. Because ML models are trained against specific datasets, every trained model and every prediction must be traceable back to the exact version of the data used to produce it. This traceability is required for reproducibility, auditability, and honest reporting of model performance.

The project also operates under a student-friendly budget and a single-developer timeline (ADR-relevant constraints from `00_PROJECT_SCOPE.md`), which rules out adopting a heavyweight data-versioning platform purely for its own sake.

## Decision

Dataset versioning will be implemented as a lightweight, database-backed scheme rather than adopting a dedicated data-versioning tool:

- Raw uploaded files are stored as immutable objects (local disk volume in development, S3-compatible object storage such as MinIO in production).
- A `datasets` table and a `dataset_versions` table in PostgreSQL track metadata for every upload: dataset id, version number, parent version id, schema hash, row count, column list, validation status, and uploader/timestamp.
- Every cleaning or transformation step that materially changes the data produces a new version row and a new stored object; the original upload is never overwritten.
- Model training records (from ADR-010) reference the exact `dataset_version_id` they were trained on.

## Alternatives Considered

- DVC (Data Version Control)
- LakeFS
- Git LFS
- Delta Lake

## Consequences

### Positive

- No new infrastructure beyond what the project already provisions (PostgreSQL + object storage), keeping the stack consistent with ADR-003 and the project's budget constraints.
- Version metadata is directly queryable through the existing FastAPI/PostgreSQL stack, so the frontend dataset-management UI and analytics dashboard can display version history without extra tooling.
- Simple mental model: every version is an immutable row plus an immutable file, which gives a clean audit trail for free.

### Negative

- No automatic diffing, branching, or merge semantics the way DVC or LakeFS provide.
- Not designed for very large datasets or high-frequency versioning; acceptable given the project operates on portfolio-scale clinical CSVs, not production-scale data lakes.
- Change detection (deciding whether two uploads are "the same" dataset) has to be implemented manually via schema/content hashing rather than relying on a tool's built-in diffing.

## References

- `docs/00_PROJECT_SCOPE.md` — Patient Data Platform requirements
- ADR-003 — PostgreSQL as relational database
- TRD Section 24 — Database Design (to be updated with `datasets` / `dataset_versions` schema)
