# 11_PRIVACY_COMPLIANCE.md — Privacy & Compliance Architecture

**Project:** MedIntel AI
**Version:** v1.0
**Status:** Active
**Related:** ADR-009, ADR-018, `05_BACKEND_DESIGN.md` §4/§9, `10_PATIENT_MANAGEMENT.md`, `00_PROJECT_SCOPE.md`

---

# 0. Scope Statement — What This Document Is and Isn't

This document specifies a **HIPAA-aware and GDPR-aware architecture** for
a portfolio project handling synthetic and credentialed-research clinical
data. It is engineering documentation, not legal advice, and does not
constitute HIPAA certification or a GDPR compliance audit — MedIntel AI is
not a covered entity, has no Business Associate Agreements, and stores no
real-world patient PHI. The goal is architecture that **would not need to
be rebuilt** if the project ever handled real PHI under proper legal
agreements — building the right patterns now, honestly labeled as
portfolio-stage rather than certified, per the project's "don't dumb it
down, but don't overclaim it either" stance. Any real deployment handling
actual patient data would require independent legal/compliance review;
nothing here substitutes for that.

---

# 1. HIPAA-Aware Architecture

## 1.1 De-identification

- **Safe Harbor-style minimalism** (`10_PATIENT_MANAGEMENT.md` §2.1):
  `Patient` rows store `date_of_birth_year` (not full DOB), no name, no
  direct hospital/NHS identifiers — `external_ref` is a de-identified
  source id, never a real-world identifier.
- MIMIC-III data is already de-identified under HIPAA Safe Harbor by its
  custodian (PhysioNet) prior to reaching this project (ADR-018) — the
  project does not re-identify or attempt to re-identify it, per the Data
  Use Agreement.
- Synthetic data is treated as if it were real PHI throughout (project-wide
  policy, predates this document) — there is no "relaxed" code path for
  data assumed safe, specifically so the architecture doesn't develop
  hidden shortcuts that would break if real data were ever substituted in.

## 1.2 Encryption

- **At rest**: PostgreSQL encryption (managed-provider disk encryption in
  hosted deployment; local dev uses unencrypted volumes, which is an
  accepted portfolio-stage gap explicitly noted here rather than silently
  assumed equivalent to production). Object storage (ADR-009) similarly
  relies on the hosting provider's at-rest encryption.
- **In transit**: HTTPS only in any non-local environment; no unencrypted
  data transmission between services in a deployed environment.

## 1.3 Access Controls

Role-based access control (`clinician`/`analyst`/`admin`,
`05_BACKEND_DESIGN.md` §9) gates every endpoint; JWT role claims are
re-verified against the database on every request rather than trusted from
the token alone (`.ai/memory/project-memory.md`), so a revoked or changed
role takes effect immediately, not after token expiry.

## 1.4 Audit Logging

Covered fully in §5 — every access to patient-data-handling endpoints,
success or rejection, is logged.

---

# 2. GDPR Compliance

## 2.1 Right to Deletion

`Dataset.deleted_at` (soft delete, already implemented) is the existing
pattern; the same soft-delete approach extends to `Patient` and
`MedicalRecord` rows (`05_BACKEND_DESIGN.md` §5) — a deletion request
marks records as deleted (excluded from all product-facing views and
model training going forward) rather than hard-deleting, **because**
`audit_logs` and `PredictionLog` rows referencing that patient must
survive for audit/reproducibility integrity (ADR-009's traceability
principle) even after the patient's own record is "deleted" from the
user's perspective. A true hard-delete/purge process (for genuine legal
erasure obligations) is a distinct, separately-gated administrative action
— not the same button as a user-facing "delete my data" request — and is
explicitly out of scope for the current phased plan (`01_PRD.md` §11),
flagged here rather than silently assumed solved.

## 2.2 Right to Portability

Dataset/patient data exportable via the existing Reporting pillar
(`02_TRD.md` §13) in a standard format (CSV/JSON) — reusing the export
pipeline rather than building a separate portability-specific mechanism.

## 2.3 Data Processing Agreements (Third-Party LLM Providers)

The multi-provider LLM abstraction (ADR-005) means requests may go to
OpenAI/Anthropic/Gemini depending on configuration. **For a real deployment
handling actual patient data**, a Data Processing Agreement with whichever
provider is active would be a hard legal prerequisite, not an
implementation detail — flagged here explicitly so it isn't silently
assumed handled. For the current portfolio-stage project (synthetic data,
or MIMIC-III data which never reaches the LLM layer at all per ADR-018),
this is a documented future requirement rather than an active gap.

## 2.4 Consent Tracking

For the current phased plan, consent tracking is architecturally deferred
(no real end-user patients are consenting to anything yet) but the
`AuditLog`/versioning patterns already in place (append-only, timestamped,
actor-attributed) are the same patterns a consent-tracking table would
use — extending to real consent tracking is additive, not a redesign, if
and when the project reaches a phase with real user-facing patient
consent flows.

---

# 3. Data Governance Framework

## 3.1 Retention Policy

Portfolio-stage default: data retained for the life of the project/demo
environment; no automatic expiry is implemented in the current phased
plan. This is stated explicitly as a gap relative to a real production
system (which would need a defined retention schedule per data category)
rather than silently omitted.

## 3.2 De-identification Before Analytics/Training

Already covered by §1.1 — there is no separate "de-identify before
training" step distinct from the baseline handling, since the baseline
already treats all data (synthetic or MIMIC-III) as requiring careful
handling from the moment it enters the system.

## 3.3 Differential Privacy for Aggregates

Not implemented in the current phased plan. Flagged as a legitimate future
enhancement for the Analytics pillar's cohort/aggregate views
(`02_TRD.md` §12) if the project reaches a phase with real, larger patient
populations where aggregate-level re-identification risk becomes material
— premature to build against a synthetic/MIMIC-III-scale portfolio dataset
where the risk is already low given §1.1's minimalism.

## 3.4 Audit Dashboard

A Grafana or Reporting-pillar view over `audit_logs` (who accessed what,
when, and whether the access succeeded or was rejected) — reuses existing
infrastructure (`07_ML_OPS.md` §4.5's dashboard pattern) rather than a
new bespoke audit-viewer tool.

---

# 4. Audit Logging Specification

## 4.1 What's Already Implemented

`AuditLog` (`05_BACKEND_DESIGN.md` §4) is append-only by construction
(nothing in the codebase updates or deletes rows), records both successful
and rejected (401/403) requests, and is implemented as raw ASGI middleware
(not `BaseHTTPMiddleware`, to avoid the deadlock gotcha recorded in
`.ai/memory/project-memory.md`) intercepting by path prefix.

## 4.2 Coverage for New Entities

The existing middleware pattern extends to every new patient-data-handling
endpoint from this scope (`Patient`, `MedicalRecord`, `RiskScore`,
`TreatmentOutcome`) by adding their path prefixes to the same middleware
configuration — **no new audit mechanism is required**, which is itself a
validation that the original audit middleware design (Sprint 2, #31) was
built generally rather than narrowly for datasets alone.

## 4.3 What Gets Logged Per Access

`actor_id`, `actor_role`, HTTP method, `resource_type`, `resource_id`,
path, status code, client IP, user agent, and an endpoint-enriched
`detail` JSONB field (e.g. which fields of a `MedicalRecord` were viewed,
for a sufficiently granular trail on the more sensitive entities).

---

# 5. De-identification Procedures

## 5.1 Safe Harbor Method (Reference, Not Reimplementation)

MIMIC-III's de-identification is performed by PhysioNet before the data
reaches this project (ADR-018) — this project does not reimplement Safe
Harbor de-identification on MIMIC-III data itself. What this project *does*
implement is Safe-Harbor-*informed* minimalism for its own `Patient`
schema (§1.1): avoiding full dates, avoiding direct identifiers, treating
`external_ref` as opaque.

## 5.2 Quasi-Identifier Awareness

Even de-identified data can be re-identified via a combination of
quasi-identifiers (age + sex + rare condition + region, for example). The
`Patient` schema's minimalism (§1.1) and the explicit avoidance of
storing region/full-date fields unless a specific feature genuinely
requires them are the project's concrete mitigation — this is called out
explicitly rather than assuming "de-identified" is a binary, permanent
property of a dataset regardless of what's later joined to it.

## 5.3 Fairness Metrics vs. Re-identification Risk (Tension, Named)

Fairness testing (`08_EVALUATION_FRAMEWORK.md` §4.2) needs protected
attributes (age band, sex, etc.) to compute a fairness gap — this is in
direct tension with minimizing quasi-identifiers (§5.2). The resolution:
protected attributes used for fairness computation are aggregated at the
**group level** for reporting (a `fairness_gap{group=...}` metric,
`07_ML_OPS.md` §4.1) and never re-attached to an individual patient's
retrievable record — the monitoring pipeline computes group statistics and
discards the row-level linkage after aggregation, rather than persisting
a queryable "this patient's group" join that would reintroduce the
re-identification risk fairness testing is meant to be evaluated
independently of.

---

# 6. MIMIC-III-Specific Compliance (ADR-018 Recap)

Full detail: ADR-018. Compliance-relevant obligations restated here for
completeness of this document: PhysioNet Credentialed Health Data Use
Agreement governs access; no redistribution; no re-identification
attempts; private-infrastructure-only storage; never committed to the
repository, a public artifact store, or a public-facing demo environment;
only derived model artifacts (not row-level data) cross into the
general-purpose MLflow registry/serving path (`09_DATA_PIPELINE.md` §7).

---

# 7. Compliance Review Triggers

The following are named here as events that should trigger an explicit
compliance re-review (not proceed on the existing architecture's
assumption alone): pursuing a genuinely public deployment with real
signups, any future decision to accept real (non-MIMIC-III, non-synthetic)
patient data, a change to which LLM provider is default-active (§2.3), or
scaling the patient population large enough that §3.3's differential-
privacy deferral needs revisiting.

---

# 8. Open Implementation Questions

- Exact retention schedule (§3.1) if the project moves beyond a pure demo
  environment — deferred until that's a real decision, not a portfolio
  hypothetical.
- Whether a genuine hard-delete/purge admin action (§2.1) is built in the
  current phased plan or left as documented-but-unimplemented — leaning
  toward documented-but-unimplemented given it's not required for any
  current use case, but not decided definitively here.
- Concrete threshold/method for §5.3's group-level aggregation (minimum
  group size before a fairness statistic is reported at all, to avoid a
  "group of one" leaking back to an individual) — needs real data volume
  to calibrate sensibly.

---

## Document Information

**Version History:**
- v1.0 — Initial privacy & compliance architecture (current)

## End of Document
