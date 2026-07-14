# 10_PATIENT_MANAGEMENT.md — Patient Data Management & Medical Records

**Project:** MedIntel AI
**Version:** v1.0
**Status:** Active
**Related:** `05_BACKEND_DESIGN.md` §5, `09_DATA_PIPELINE.md`, `00_VISION_ML_PLATFORM.md`, `11_PRIVACY_COMPLIANCE.md`

---

# 1. Purpose & Scope

Specifies the `Patient` and `MedicalRecord` entities (`05_BACKEND_DESIGN.md`
§5) in full: what a patient record actually contains, how an uploaded
medical document becomes structured data, how a patient's timeline is
assembled, and the review workflow for low-confidence extractions. This is
new ground for the platform — Sprint 1–2 built the dataset/tabular side
(ADR-009) but nothing patient-record-specific yet.

---

# 2. Patient Data Model

## 2.1 Deliberately Minimal Identity Fields

`Patient` (`05_BACKEND_DESIGN.md` §5) stores `external_ref` (a de-identified
source id — e.g. a MIMIC-III `subject_id` where applicable, or a
synthetic-data generator's id — **never** a real-world identifier like a
name or NHS/hospital number), `date_of_birth_year` (year only, not full
date — full DOB combined with a handful of other fields is a well-known
re-identification vector), `sex`, and a structured `comorbidities`
summary. This is a deliberate minimalism: the platform needs enough to
drive risk/outcome models and a timeline view, not a full demographic
profile that would increase re-identification surface for no functional
benefit.

## 2.2 Comorbidity Summary vs. Full History

`Patient.comorbidities` is a **summary** (structured, ICD-derived list) —
the detailed, document-level history lives in `MedicalRecord` rows (§3),
not duplicated into `Patient` itself. This keeps `Patient` a stable,
small, frequently-read row and `MedicalRecord` an append-only, growing
history — matching how the two are actually used (models read the
summary; the timeline view reads the full record history).

---

# 3. Medical Record Processing

## 3.1 Upload → OCR → Extraction Pipeline

1. User uploads a medical document (PDF or image) attached to a patient.
2. Stored immutably (same object-store pattern as ADR-009's dataset
   uploads — a medical record is never overwritten, only superseded by a
   new record referencing what it corrects, §6).
3. OCR extracts raw text from the document.
4. Structured extraction pulls medications, diagnoses, and lab values from
   the OCR'd text into `MedicalRecord.extracted_data` (JSONB,
   `05_BACKEND_DESIGN.md` §5).
5. An `extraction_confidence` score is computed (per extracted field, not
   just one document-level score — a document can have a clear diagnosis
   line but a garbled lab-values table, and those shouldn't share one
   confidence number).
6. Low-confidence extractions are queued for human review
   (`MedicalRecord.reviewed_by_id` set once a reviewer confirms or
   corrects them) rather than silently accepted into the patient's
   structured record.

## 3.2 OCR & Extraction Approach

OCR: a standard document OCR engine (e.g. Tesseract, or a hosted OCR API
if quality requires it — the specific choice is an implementation detail
appropriately deferred to a small, focused ADR when this phase actually
starts, per the project's "ADR before implementation" convention, not
decided speculatively here). Structured extraction: a combination of
pattern-based extraction for well-structured fields (dosage/frequency
patterns for medications) and an LLM-assisted extraction pass (via the
existing multi-provider abstraction, ADR-005) for less structured
narrative text — with the same grounding discipline as the RAG pipeline:
extracted fields are checked against the source OCR text
(span-attributable), not freely generated, so a hallucinated medication
name is a detectable, not silent, failure.

## 3.3 Confidence Thresholds & Review Queue

A configurable per-field confidence threshold determines what's
auto-accepted vs. queued. The review queue is a first-class Admin/
clinician-facing view (not a hidden backend table) — per-project
principle, low-confidence machine extraction silently entering a
patient's structured record is exactly the kind of unreviewed
automation the project's "don't assume, verify" compliance stance argues
against (`02_TRD.md` §12, §16).

---

# 4. Medical Concept Extraction

## 4.1 Target Concepts

Medications (name, dosage, frequency where extractable), diagnoses
(mapped to ICD codes where possible, kept as free text with a
"needs-coding" flag otherwise — silently forcing an uncertain mapping to
the nearest ICD code would corrupt downstream analytics), lab values
(name, value, unit, date).

## 4.2 Coding & Normalization

Where a diagnosis or medication can be confidently mapped to a standard
code (ICD for diagnoses, a medication vocabulary for drugs), it is — this
is what makes `Patient.comorbidities` usable as a structured model input
(`06_ML_MODELS.md` §2.4's comorbidity encoding depends on this). Where it
can't be confidently mapped, it's retained as reviewed free text with an
explicit "uncoded" flag rather than a forced, potentially wrong, code.

## 4.3 Feeding the Feature Pipeline

Extracted, coded concepts feed the same feature engineering pipeline
(`09_DATA_PIPELINE.md` §3) Models 1–2 train against — a patient's
extracted comorbidities and medications are not a separate, parallel data
source from the tabular dataset pipeline; they're additional evidence
that lands in the same versioned feature scheme.

---

# 5. Patient Timeline

## 5.1 What It Shows

A chronological view combining: uploaded medical records (with their
extracted concepts), predictions made for the patient (`PredictionLog`,
`05_BACKEND_DESIGN.md` §5) with their SHAP explanations, and — where
available — recorded actual outcomes (feeding the active-learning loop,
`03_APP_FLOW.md` §13). This is a read-oriented view assembled from
existing tables (`MedicalRecord`, `PredictionLog`, `RiskScore`/
`TreatmentOutcome`) — it introduces no new persisted entity of its own,
only a query/assembly service.

## 5.2 Why This Matters Beyond "a nice UI feature"

The timeline is what makes a risk score or treatment-outcome prediction
interpretable *in context* — a risk score means something different next
to a timeline showing three prior cardiac events versus next to an empty
history. This is the product-level payoff of Models 1–2's explainability
work (`06_ML_MODELS.md` §2.6/§3.6), not a separate feature bolted on
afterward.

---

# 6. Record Updates & Version History

Consistent with ADR-009's immutability principle applied to this pillar: a
correction to a `MedicalRecord`'s extracted data does not overwrite the
row — it creates a new `MedicalRecord` entry referencing the one it
supersedes (mirroring `DatasetVersion.parent_version_id`'s pattern), so
the timeline (§5) can show "this diagnosis was corrected on [date]" rather
than silently losing the pre-correction state. This matters specifically
for audit defensibility: a reviewer should be able to reconstruct what the
system believed at any point in time, not just its current best guess.

---

# 7. Privacy Considerations

Full detail: `11_PRIVACY_COMPLIANCE.md`. Specific to this pillar: medical
document uploads are exactly the kind of "obviously contains PHI-shaped
content" data the project's GDPR-aware stance treats as real PHI even when
synthetic — every `MedicalRecord` create/read/update is logged to
`audit_logs` (already-implemented middleware, `05_BACKEND_DESIGN.md` §4/§9)
with no exception for "this is probably fine" cases.

---

# 8. Open Implementation Questions

- Specific OCR engine/API choice (§3.2) — deferred to a focused ADR at
  implementation time, not decided speculatively here.
- Exact per-field confidence thresholds (§3.3) — need real extraction
  output to calibrate against; premature to fix a number now.
- Whether ICD-code mapping (§4.2) uses a rules-based lookup, a fuzzy-match
  library, or an LLM-assisted mapping step with human confirmation — same
  "defer to implementation-time ADR" answer as the OCR choice.

---

## Document Information

**Version History:**
- v1.0 — Initial patient data management & medical records specification (current)

## End of Document
