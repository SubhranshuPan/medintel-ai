# ADR-014 — pandera for Dataset Schema/Data Validation

## Status

Accepted

## Context

`02_TRD.md` §3 (Technology Stack) lists the Data Platform's schema-validation
library as undecided — "pandera/great-expectations" — pending a real
decision. Sprint 2's CSV upload endpoint (#32) already writes a
`DatasetVersion` row with `validation_status = pending` and an empty
`validation_report` JSONB column (`app/models/dataset.py`); #33 needs to fill
those in with an actual validation step, so this can no longer stay
undecided.

Constraints specific to this project:

- Uploads are treated as PHI (project-wide GDPR rule) even though the data is
  synthetic, so validation results must be captured as a structured,
  auditable record — not just a pass/fail flag — and stored inline on the
  version row for traceability (ADR-009).
- The upload path is a synchronous FastAPI request (`DatasetService.create_from_upload`)
  that must return promptly; validation runs in-process against a pandas
  `DataFrame` already parsed from the upload, not as a separate batch job.
- This is a single-developer, portfolio-timeline project (interview-ready by
  ~November 2026, per `.agents/AGENTS.md`). Tooling that requires its own
  config/store/checkpoint scaffolding to get a first result is a poor trade
  against a project of this size and deadline.
- The uploaded CSV's shape isn't fixed in advance — Sprint 2 supports
  arbitrary clinical dataset uploads, not one fixed pathway schema — so
  whatever tool is chosen has to support both a generic "sanity check" mode
  (nulls, dtypes, duplicate rows) today and stricter, named schemas
  (ICD-code columns, expected ranges) as specific clinical pathways are
  formalised later.

## Decision

**pandera is adopted for dataset schema and data validation.**

- Validation runs synchronously inside `DatasetService.create_from_upload`
  (or a follow-on step called from #33/#34), directly against the `pandas.DataFrame`
  already produced by `pd.read_csv`. Because pandera validation is CPU-bound
  sync code, it is dispatched via `asyncio.to_thread` rather than blocking
  the event loop, consistent with the async-first stance of ADR-001/ADR-013.
- Two validation tiers, matching the "arbitrary upload today, formal pathway
  later" reality:
  - A generic `pandera.DataFrameSchema` applied to every upload: non-empty,
    no fully-null columns, no duplicate rows, column names present and
    unique. This is what backs #33 for the general case.
  - Named `pandera.DataFrameModel` classes for specific, known clinical
    pathways (e.g. an ICD-coded readmission cohort schema) can be added
    incrementally and selected by dataset type; out of scope for #33 itself
    but the same library handles both without a second dependency.
- Validation runs with `lazy=True` so a single upload surfaces *every*
  violation in one pass, not just the first — a clinician correcting a
  rejected upload needs the full list, not a fix-one-resubmit-repeat loop.
- On failure, pandera's `SchemaErrors.failure_cases` (already a small,
  tabular structure) is converted to a plain dict/list and written directly
  into `DatasetVersion.validation_report` (JSONB); `validation_status` is set
  to `passed` or `failed` accordingly. No additional storage or reporting
  infrastructure is required beyond what ADR-009 already provisions.
- Schema definitions live in the service layer next to the models they
  validate (`app/services/` or a new `app/validation/` module), following
  the existing repository/service separation — they are not a separate
  standalone data-quality subsystem.

## Alternatives Considered

- **great-expectations** — the more feature-complete data-quality platform
  (Expectation Suites, Checkpoints, auto-generated HTML "Data Docs"). Rejected
  for this project: it expects its own context/store configuration and a
  Checkpoint-run model built around batch/pipeline validation, which is a
  heavier integration than a single synchronous upload endpoint needs. Its
  richer output (HTML Data Docs) doesn't map cleanly onto a compact JSONB
  `validation_report` column, and stitching it into a scoped FastAPI request
  adds real setup cost without a matching benefit at this project's data
  volume and team size (one developer, portfolio deadline). Revisit if a
  future pillar needs organisation-wide, multi-pipeline data-quality
  monitoring rather than per-upload validation.
- **Hand-rolled pandas checks (no library)** — fastest to write, but loses
  declarative, reusable schema definitions and produces ad-hoc error shapes
  that would need bespoke serialisation for every check; also weaker for
  recruiter-facing code review (project explicitly avoids tutorial-tier
  patterns).
- **Pydantic v2 row-by-row validation** — already in the stack (ADR-001), but
  validating a clinical CSV row-by-row through Pydantic models is far slower
  and more awkward for whole-DataFrame checks (column-level null ratios,
  cross-column constraints, duplicate detection) than a vectorised,
  DataFrame-native tool. Pydantic remains the right tool for the API request/
  response schemas; it is not a substitute for dataset-shape validation.

## Consequences

### Positive

- Lightweight, in-process, pandas-native — no new infrastructure beyond the
  library itself, matching the budget/single-developer constraint already
  established in ADR-009.
- `DataFrameModel` classes are declarative and statically typed, echoing the
  typed-model philosophy already adopted for SQLAlchemy in ADR-013 —
  consistent, recruiter-readable code style across the codebase.
- Failure cases serialise naturally into the existing `validation_report`
  JSONB column with no extra reporting layer, keeping the audit trail
  entirely inside the ADR-009 dataset-versioning scheme.
- Supports both today's generic sanity checks and future named clinical
  pathway schemas with the same dependency — no second migration needed
  when stricter schemas are introduced.

### Negative

- No built-in human-readable "Data Docs" the way great-expectations
  produces; if a polished, browsable data-quality report becomes a portfolio
  requirement (e.g. as part of the Reporting pillar, ADR-012), that view
  will need to be built on top of `validation_report` rather than generated
  for free.
- pandera is less mature than great-expectations for large-scale,
  multi-pipeline data-quality monitoring across many data sources; acceptable
  here since validation is scoped to one upload at a time, not a warehouse-wide
  pipeline.
- Generic vs. named-schema selection logic (which schema applies to which
  upload) still needs to be designed as pathway-specific schemas are added —
  tracked as follow-up work for whichever issue introduces the first named
  clinical pathway, not solved by this ADR.

## References

- ADR-009 — Dataset Versioning Strategy
- ADR-001 — FastAPI as the backend framework
- ADR-013 — SQLAlchemy 2.0 (async) + Alembic for ORM and Migrations
- `docs/02_TRD.md` §3 — Technology Stack (validation library previously
  listed as undecided)
- `backend/app/models/dataset.py` — `ValidationStatus`, `validation_report`
- `backend/app/services/dataset.py` — `DatasetService.create_from_upload`
- Issue #33 — Sprint 2: Schema/data validation
