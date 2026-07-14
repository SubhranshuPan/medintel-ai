# 09_DATA_PIPELINE.md — Data Pipeline Architecture

**Project:** MedIntel AI
**Version:** v1.0
**Status:** Active
**Related:** `02_TRD.md` §12, `06_ML_MODELS.md`, ADR-009, ADR-014, ADR-018

---

# 1. Purpose & Scope

Specifies how clinical data moves from raw upload (or credentialed
research source) through validation, feature engineering, and versioning,
to the point where it's ready for a model to train against
(`06_ML_MODELS.md`) or a dashboard to render (`02_TRD.md` §12's Analytics
module). This document is the implementation-level detail behind ADR-009
(versioning) and ADR-014 (validation); it does not re-decide either, it
specifies how they're carried out end to end.

---

# 2. ETL Architecture

## 2.1 Ingestion Paths

| Source | Path | Notes |
|---|---|---|
| CSV upload | User-facing upload endpoint (`03_APP_FLOW.md` §6) | The primary, already-implemented path (`app/services/dataset.py`) |
| PDF (medical documents) | Patient Management upload → OCR → structured extraction | New for this scope, detailed in `10_PATIENT_MANAGEMENT.md` |
| HL7 (future) | Not implemented in the current phased plan (`01_PRD.md` §11) | Included here for architectural completeness — HL7 parsing is a distinct, nontrivial subsystem and is explicitly not assumed free; it's a future-phase item, not silently folded into "ingestion" as if already solved |
| MIMIC-III | Private, credentialed batch import (§7) | Never through the user-facing upload endpoint — a structurally separate path, not a variant of CSV upload |

## 2.2 Ingestion Steps (CSV path, current)

1. Upload received, size-capped (`Settings.max_upload_bytes`,
   already implemented).
2. Parsed via pandas (`pd.read_csv`); parse failures raise
   `InvalidCsvError` rather than silently producing a partial frame.
3. Stored immutably (object store, ADR-009) with a `sha256` checksum before
   any validation runs — the raw upload is never lost even if validation
   subsequently fails, since validation and cleaning produce new versions
   rather than mutating the original (§4).
4. `DatasetVersion` row created (`version_number = 1`,
   `origin = upload`, `validation_status = pending`).
5. Validation (§5) runs, updating `validation_status` and
   `validation_report` on that same row — this is the one documented
   exception to "never mutate a persisted version" (ADR-014/`05_BACKEND_DESIGN.md`
   §4's `DatasetVersion` note: "nothing in the service layer updates a
   persisted version except the one-shot validation stamp written
   immediately after creation").

## 2.3 Ingestion Steps (PDF/OCR path, new)

Detailed fully in `10_PATIENT_MANAGEMENT.md` §3; summarized here for
pipeline completeness: upload → OCR → structured extraction (medications,
diagnoses, lab values) → confidence scoring → (if below threshold) queued
for human review → attached to the patient's `MedicalRecord` row
(`05_BACKEND_DESIGN.md` §5), not to a `DatasetVersion` — medical records
and tabular datasets are deliberately different entities with different
lifecycles, not force-fit into one model.

---

# 3. Feature Engineering Pipeline

## 3.1 Principle: Features Are Versioned, Not Recomputed Silently

Per the lightweight feature store design (`02_TRD.md` §12), engineered
features are materialised as versioned columns/tables keyed by
`dataset_version_id` — a retrain against a new data version re-derives
features from that version, it does not reuse a stale feature table
computed against an earlier version. This is what keeps every trained
`ModelVersion` traceable to an exact, reproducible input (ADR-009's
principle extended to the ML layer, `06_ML_MODELS.md` §5).

## 3.2 Per-Model Feature Specs

Feature engineering detail (comorbidity encoding, lab-value trend
features, missingness indicators, treatment-diagnosis interaction terms)
is specified per model in `06_ML_MODELS.md` §2.4/§3.4 — not duplicated
here. This document owns the *pipeline mechanics* (when features are
computed, how they're versioned, how they're invalidated), not the
per-model feature list.

## 3.3 Computation Timing

Feature engineering runs as part of the same Celery training job that
consumes it (`07_ML_OPS.md` §3.2, step 3) — not as a separately-scheduled
precomputation step for the current scope. A precomputed, always-fresh
feature table is a reasonable future optimization if training frequency
increases, but isn't justified yet given the weekly-or-triggered retraining
cadence (`07_ML_OPS.md` §3.1) and would add staleness-tracking complexity
this project doesn't yet need.

## 3.4 Temporal Aggregations

For features requiring history (e.g. Model 1's lab-value trend feature,
`06_ML_MODELS.md` §2.4), aggregation windows are computed against the
patient's recorded history up to the `dataset_version_id`'s snapshot
time — never against data that would not have been available at that
point, since using future data as a training feature (temporal leakage) is
exactly the kind of subtle correctness bug that undermines a "we validated
against real data" claim.

---

# 4. Dataset Versioning (ADR-009 Recap)

Uploads/derived data are immutable objects; `datasets`/`dataset_versions`
tables track lineage; every cleaning/transformation step produces a new
version rather than mutating an existing one. **A dedicated data-versioning
tool (DVC, LakeFS, Git LFS, Delta Lake) was considered and explicitly
rejected in ADR-009** in favour of this lightweight, database-backed
scheme — this document does not reopen that decision; it specifies how
the chosen scheme is exercised in practice:

- A "new version" is triggered by: initial upload (v1), a cleaning/
  preprocessing step, or a schema-validation-driven correction — never by
  an in-place edit.
- `parent_version_id` forms a lineage chain; `schema_hash` (already
  implemented) enables detecting whether two uploads are "the same"
  dataset shape without a dedicated diffing tool, per ADR-009's accepted
  trade-off (manual hashing instead of a tool's built-in diff).

---

# 5. Data Quality Checks (ADR-014 Recap)

pandera validation (ADR-014) is the enforcement mechanism; this section
specifies the concrete check categories run against every version:

| Check | Example |
|---|---|
| Structural | Non-empty, unique/present column names, no fully-null columns |
| Type | Column dtypes match the expected schema (generic checks for arbitrary uploads today; named `DataFrameModel` schemas for specific clinical pathways as they're formalised, ADR-014) |
| Row-level | No duplicate rows, row count within a sane range for the dataset type |
| Domain-specific (named schemas only) | ICD-code columns contain valid codes; lab values within physiologically plausible ranges (not clinically validated ranges — a portfolio-scale plausibility check, not a clinical decision support claim) |

Failures serialise into `validation_report` (JSONB) with `lazy=True`
(ADR-014) so every violation surfaces in one pass.

---

# 6. Data Privacy & De-identification (Summary)

Full detail: `11_PRIVACY_COMPLIANCE.md`. Summary relevant to the pipeline
itself: synthetic data is treated as real PHI throughout (project-wide
GDPR-aware stance) — the pipeline does not have a "relaxed" code path for
data it assumes is safe. MIMIC-III data (already de-identified under HIPAA
Safe Harbor by PhysioNet, ADR-018) still flows through a structurally
separate, private ingestion path (§7) rather than the general pipeline,
specifically so its DUA-governed handling requirements can't be
accidentally bypassed by code written for the general case.

---

# 7. MIMIC-III Ingestion Path (ADR-018)

1. Credentialed download (manual, by Som, outside the application) into
   private infrastructure only — never through the application's upload
   endpoint or object store used for user-facing datasets.
2. A separate, explicitly-named ingestion script (not the general CSV
   upload service) loads MIMIC-III tables into a dedicated schema/database
   instance not shared with the public-facing application database.
3. Feature engineering (§3) and training (`07_ML_OPS.md` §3) read from
   this private instance for Model 1/2 training runs; the resulting
   trained `ModelVersion` artifact (weights, not data) is what moves into
   the normal MLflow registry and serving path.
4. No MIMIC-III row-level data ever appears in `PredictionLog`,
   `AnnotatedData`, a public demo, or a committed file — only derived,
   aggregate artifacts (a trained model, its logged metrics) cross that
   boundary, consistent with ADR-018's Data Use Agreement handling
   requirements.

---

# 8. Pipeline Orchestration & Scheduling

ETL and feature engineering run as Celery jobs (same worker pool as
training, `07_ML_OPS.md`), not a separate orchestration system (Airflow,
Dagster, Prefect) — consistent with the project's "don't add
infrastructure without a clear need" discipline (ADR-009's rejection of
DVC/LakeFS uses the same reasoning). Revisit only if pipeline complexity
or scheduling needs (e.g. genuine multi-step DAG dependencies beyond what
Celery beat's simple scheduling handles) outgrow this — not assumed
upfront.

---

# 9. Open Implementation Questions

- Concrete physiological plausibility ranges for lab-value domain checks
  (§5) — depends on which specific lab values the first named clinical
  pathway schema actually needs; premature to enumerate before that
  schema exists (tracked alongside ADR-014's "named schemas as pathways
  are formalised" note).
- Whether the MIMIC-III private database instance (§7) is a separate
  PostgreSQL instance entirely or a schema-isolated database within the
  same instance — a real infrastructure decision to make once credentialed
  access actually lands (ADR-018's risk register entry), not before.
- HL7 ingestion (§2.1) is explicitly out of the current phased plan — if
  it's pulled forward, it needs its own ADR before implementation, not a
  quiet addition to this pipeline.

---

## Document Information

**Version History:**
- v1.0 — Initial data pipeline architecture (current)

## End of Document
