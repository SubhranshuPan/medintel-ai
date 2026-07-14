# Product Requirements Document (PRD)

**Project:** MedIntel AI
**Version:** v3.0
**Author:** Subhranshu Panda
**Status:** Active
**Last Updated:** July 2026

**Related:** `00_PROJECT_SCOPE.md`, `00_VISION_ML_PLATFORM.md`, `docs/architecture/adr/`

---

## Table of Contents

1. Executive Summary
2. Vision & Mission
3. Problem Statement
4. Product Goals
5. Target Users & Personas
6. Scope
7. Functional Requirements (by Pillar)
8. Non-Functional Requirements
9. Success Metrics
10. Risks & Assumptions
11. Release Plan (Phased Build Order)
12. Open Questions
13. Glossary
14. Approval

---

# 1. Executive Summary

MedIntel AI is a **production-grade healthcare ML platform** spanning five
pillars: a **Patient Data Platform** for ingesting, versioning, and managing
clinical datasets and patient/medical records; a **Clinical Analytics
Dashboard** for exploring cohorts and disease patterns; an **ML Engine**
running three models (risk stratification, treatment outcome prediction,
literature relevance ranking) with SHAP explainability, continuous training,
monitoring, and governed A/B rollout; an **AI Decision Support** layer with a
7-stage advanced RAG retrieval pipeline for grounded natural-language
interaction; and a **Reporting** layer for PDF/CSV/executive output plus
model-monitoring summaries.

The platform demonstrates the full lifecycle of an applied data science
product end to end: data ingestion → validation → modeling → continuous
training and monitoring → governed rollout → explanation → reporting. This
is a deliberately larger scope than "an ML model behind an API" — see
`00_VISION_ML_PLATFORM.md` for the full rationale and `CLAUDE.md`'s binding
scope mandate for why this is not to be quietly descoped under schedule
pressure.

---

# 2. Vision & Mission

**Vision:** Build an end-to-end clinical data intelligence platform that
takes raw patient data through validation, prediction, continuous
monitoring, and reporting — with every output either citation-backed (AI
text), model-traceable (predictions), or statistically/fairness-gated
(model rollout) — matching how production healthcare ML systems are
actually expected to behave, not just how a prototype behaves.

**Mission:** Enable users to upload clinical datasets and, without leaving
the platform: explore them visually and by cohort, generate explainable
risk and treatment-outcome predictions, retrieve grounded, cited medical
literature, ask natural-language questions about the data or a prediction,
watch model quality and fairness over time on a monitoring dashboard, and
export the results as shareable reports.

---

# 3. Problem Statement

Clinical data work today is fragmented across separate tools: spreadsheets
for cleaning, a BI tool for dashboards, a notebook for modeling, no
explainability layer, no systematic fairness testing, no monitoring once a
model ships, and manual report writing. Separately, general-purpose AI
models produce answers without reliable citations or grounding in the
actual uploaded data, making them unsuitable for decision support. And even
where ML models exist, they are rarely evaluated for fairness across
demographic groups or monitored for drift after deployment — a real gap in
how "portfolio" ML projects differ from production healthcare ML systems.

MedIntel AI consolidates ingestion, analytics, explainable and fairness-
tested prediction, grounded AI Q&A, continuous training and monitoring, and
reporting into a single modular platform.

---

# 4. Product Goals

**Primary:** Reliable dataset ingestion with versioning and patient/medical
record management; accurate, explainable, and fairness-tested risk and
treatment-outcome predictions; a literature retrieval pipeline good enough
to cite real evidence accurately; a usable analytics dashboard including
cohort analysis; continuous training and monitoring so model quality is a
tracked fact, not an assumption; a governed rollout process so no model
change reaches users without passing a statistical and fairness gate;
exportable reports.

**Secondary:** Modular architecture allowing pillars and MLOps capabilities
to be developed and demoed independently; easy free-tier deployment;
production-grade engineering practices throughout, including the MLOps and
compliance layers that portfolio-tier projects usually skip.

---

# 5. Target Users & Personas

**Primary users:** Healthcare Data Scientists, Clinical Researchers,
Hospital Administrators, ML/MLOps Engineers. **Secondary:**
Recruiters/hiring managers evaluating engineering capability.

**Persona 1 — Data Scientist:** Wants to upload a dataset, train and
compare models, inspect SHAP explanations, and tune hyperparameters
systematically (Optuna) without leaving the platform.

**Persona 2 — Clinical Researcher:** Wants to explore prevalence/demographic
trends, run cohort analyses, and ask natural-language questions about the
dataset ("what's the readmission rate for patients over 65 with diabetes?").

**Persona 3 — Hospital Administrator:** Wants a KPI dashboard and an
executive PDF summary, not raw model internals.

**Persona 4 — ML/MLOps Engineer (new):** Wants to see the model registry,
training run history, drift/fairness monitoring dashboards, and the A/B
rollout decision log — the "how do you know this model is still good"
story, not just the prediction endpoint.

---

# 6. Scope

**In Scope:** All five pillars listed in `00_PROJECT_SCOPE.md`; the full
MLOps layer (experiment tracking, continuous training, monitoring, A/B
rollout — ADR-010, ADR-015, ADR-016, ADR-019); the advanced RAG retrieval
pipeline (ADR-017); real clinical training data via credentialed MIMIC-III
access (ADR-018) with synthetic data as interim/CI fallback; JWT auth;
Docker deployment; free-tier hosting (Railway/Render initially).

**Out of Scope (for now, not "cut" — see §11):** Multi-hospital tenancy,
EMR integrations, mobile-first UI, a genuine on-call/paging rotation (the
monitoring stack alerts to Slack/email, not a pager — see ADR-016), and
full clinical/regulatory certification (HIPAA/GDPR *architecture* is
in scope per `11_PRIVACY_COMPLIANCE.md`; formal certification/audit is not
a v1 deliverable for a portfolio project with no real patients).

---

# 7. Functional Requirements (by Pillar)

## Pillar 1 — Patient Data Platform
| ID | Requirement |
|---|---|
| FR-101 | Users can upload CSV datasets through the UI. |
| FR-102 | Uploaded data is schema-validated and cleaned before use (pandera — ADR-014). |
| FR-103 | Users can list, inspect, and delete datasets. |
| FR-104 | Every dataset upload/transformation creates a new immutable version (ADR-009). |
| FR-105 | Patient and medical-record management: demographics, history, uploaded documents, OCR'd/structured extraction, patient timeline view. |
| FR-106 | Model training can draw on credentialed MIMIC-III data where available, falling back to synthetic data otherwise (ADR-018). |
| FR-107 | Engineered features are versioned and traceable to the `dataset_version_id` they were derived from (lightweight feature store, `02_TRD.md` §12). |

## Pillar 2 — Clinical Analytics Dashboard
| ID | Requirement |
|---|---|
| FR-201 | Disease prevalence visualizations across the active dataset. |
| FR-202 | Risk distribution visualizations. |
| FR-203 | Demographic breakdowns (age, sex, region where available). |
| FR-204 | Time-series trend charts. |
| FR-205 | Configurable KPI dashboard. |
| FR-206 | Cohort analysis: filter and compare patient groups by condition, treatment, demographics, and outcome. |
| FR-207 | Disease pattern mining: clustering and association discovery over the active dataset. |

## Pillar 3 — Machine Learning Engine
| ID | Requirement |
|---|---|
| FR-301 | Train the **Patient Risk Stratification** model (XGBoost) against a chosen dataset version, producing a 0–100 risk score for cardiac disease, diabetes, stroke, and cancer (ADR-010). |
| FR-302 | Train the **Treatment Outcome Predictor** (Random Forest + Gradient Boosting ensemble), producing success probability, expected recovery time, confidence interval, and ranked alternative treatments. |
| FR-303 | Evaluate the **Literature Relevance Ranker** (the Pillar 4 retrieval pipeline) against retrieval-quality metrics (NDCG, Precision@k) as a first-class model, not just a feature of chat. |
| FR-304 | Compare models by logged metrics (ROC-AUC, precision, recall, calibration) via MLflow. |
| FR-305 | Serve predictions through a REST endpoint. |
| FR-306 | Every prediction includes a SHAP-based explanation (ADR-011). |
| FR-307 | Prediction history is queryable per patient/dataset. |
| FR-308 | Hyperparameters are tuned systematically via Optuna, logged as nested MLflow runs (ADR-015). |
| FR-309 | Retraining is triggered on a weekly schedule or automatically on data drift / performance degradation, not only manually (ADR-015). |
| FR-310 | Every model is monitored in production for data drift, model drift, calibration drift, and fairness gap across demographic groups (ADR-016). |
| FR-311 | A candidate model version can only be promoted to `Production` after passing a statistical significance test and a fairness non-regression check over a live (or simulated) rollout (ADR-019). |

## Pillar 4 — AI Decision Support
| ID | Requirement |
|---|---|
| FR-401 | Conversational natural-language Q&A over the active dataset. |
| FR-402 | Natural-language explanation of a given model prediction, grounded in its stored SHAP values (not freely generated). |
| FR-403 | Automated patient summary generation. |
| FR-404 | RAG-backed retrieval of supporting medical literature with citations, via the 7-stage pipeline: dense (ColBERT) + sparse (BM25) retrieval → metadata filtering → Reciprocal Rank Fusion → cross-encoder re-ranking → citation graph traversal → temporal decay (ADR-017). |
| FR-405 | All LLM calls go through the existing multi-provider abstraction (OpenAI/Anthropic/Gemini) — no hardcoded provider. |

## Pillar 5 — Reporting
| ID | Requirement |
|---|---|
| FR-501 | Generate PDF reports from dashboard/prediction data (ADR-012). |
| FR-502 | Export data/results as CSV or XLSX. |
| FR-503 | Executive dashboard export (summary-level, non-technical). |
| FR-504 | Clinical summary export per patient. |
| FR-505 | Export a model monitoring / fairness summary report, suitable for a non-technical stakeholder audience. |

## Cross-Cutting — MLOps & Governance (new)
| ID | Requirement |
|---|---|
| FR-601 | Every training run (manual, scheduled, or drift-triggered) is logged to the MLflow registry with parameters, metrics, and artifact. |
| FR-602 | Model registry lifecycle stages (`Staging`/`Production`/`Archived`) are enforced; no version is ever deleted, only archived, so rollback is a stage change. |
| FR-603 | Drift, performance, and fairness alerts route to Slack/email (not a paging service — no real on-call rotation exists for a portfolio project). |
| FR-604 | Model monitoring and A/B rollout dashboards are available (Grafana), separate from the product-facing frontend. |

## Cross-Cutting — Auth & Compliance
| ID | Requirement |
|---|---|
| FR-701 | Registration, login, JWT auth, role-based authorization. |
| FR-702 | Audit logging of data uploads, patient-record access, predictions, and report generation (patient-data handling flagged for compliance review — see Assumptions). |
| FR-703 | MIMIC-III-derived data is stored only in private infrastructure and never enters the public repository, a public artifact store, or a public-facing demo environment (ADR-018). |

---

# 8. Non-Functional Requirements

See `00_PROJECT_SCOPE.md` §Non-Functional Requirements — Performance,
Scalability, Security, Reliability, Maintainability, Observability, and
**Fairness** (new section covering the equalized-odds/demographic-parity/
predictive-parity targets and the 5% fairness-gap alert threshold). This
PRD does not duplicate those targets; refer to the Scope doc as the single
source for NFR targets.

---

# 9. Success Metrics

See `00_PROJECT_SCOPE.md` §Project Success Metrics (Engineering / ML /
Product / Portfolio metrics) — shared across PRD and Scope to avoid drift
between the two documents. Notable additions in this version: per-model ML
targets for all three models (not just the risk model), retrieval-quality
targets (NDCG, citation accuracy, hallucination rate), and a fairness-gap
target that applies across all models.

---

# 10. Risks & Assumptions

See `00_PROJECT_SCOPE.md` §Risk Register and §Assumptions — notably the
MIMIC-III credentialing dependency, the overall scope-vs-timeline risk, and
the RAG-latency risk, all flagged explicitly rather than silently absorbed,
per `CLAUDE.md`'s binding scope mandate. Also: no data outside an approved
research-use license is stored (synthetic or credentialed MIMIC-III only),
and predictions are for educational/research purposes, not clinical use,
regardless of which model or data source produced them.

---

# 11. Release Plan (Phased Build Order)

**This is a build sequence, not a scope cut.** Per `CLAUDE.md`'s binding
scope mandate, nothing below is "stretch, ship if time allows" in the sense
of being droppable — every component ships eventually. What follows is the
order in which it gets built, so that later phases have working
infrastructure to build on rather than everything landing at once.

**Phase 1 — Foundation (in progress, Sprint 1–2):**
- Patient Data Platform (upload, validate, version) — Sprint 1–2, largely complete
- Core ML Engine: Model 1 (Risk Stratification) with SHAP, MLflow tracking, basic model comparison
- Clinical Analytics Dashboard (core charts + KPIs)

**Phase 2 — MLOps Depth:**
- Continuous training + Optuna HPO (ADR-015)
- Monitoring & alerting stack (ADR-016)
- A/B testing & governed rollout (ADR-019)
- Model 2 (Treatment Outcome Predictor)

**Phase 3 — AI Decision Support Depth:**
- Advanced 7-stage RAG retrieval pipeline (ADR-017)
- Model 3 (Literature Relevance Ranker) evaluated against retrieval metrics
- Prediction explanation and patient summary generation, grounded in SHAP

**Phase 4 — Governance & Reporting:**
- Full Reporting pillar (PDF/executive/clinical/monitoring summary exports)
- Privacy & compliance documentation and controls (`11_PRIVACY_COMPLIANCE.md`)
- Patient/medical-record management depth (`10_PATIENT_MANAGEMENT.md`)
- Cohort analysis & disease pattern mining

This sequencing exists because each pillar and each MLOps capability
depends on earlier infrastructure existing first (e.g. monitoring needs a
model in `Production` to monitor; A/B rollout needs monitoring to gate on).
If real velocity data through Phase 1–2 shows the full four-phase scope
isn't achievable by November 2026, that is a decision point to bring back
to Som explicitly — informed by actual progress, not pre-empted here.

---

# 12. Open Questions

- Which public/synthetic clinical dataset(s) will be used for demo data
  and CI, alongside MIMIC-III for real model validation?
- Should dataset versioning support rollback in the UI, or is version
  history read-only for v1?
- Does the AI Decision Support chat need to reference multiple datasets
  simultaneously, or only the currently active one?
- What protected attributes are available (even in synthetic form) to
  compute fairness metrics against, and how are they represented without
  themselves becoming a re-identification risk?
- How is the "live traffic" for A/B rollout simulated in the absence of
  real users — replayed historical requests, synthetic request generation,
  or something else? (ADR-019 defines the mechanism; the concrete traffic
  source for a no-user portfolio deployment is still open.)

---

# 13. Glossary

See `00_PROJECT_SCOPE.md` §Glossary (now includes MLOps/retrieval terms:
Optuna, drift, fairness gap, NDCG, ColBERT, BM25, RRF, A/B testing,
MIMIC-III, feature store).

---

# 14. Approval

| Role | Name | Status |
|---|---|---|
| Product Owner | Subhranshu Panda | Approved |

---

## Document Information

**Version History:**
- v1.0 — RAG-chatbot-framed PRD (superseded)
- v2.0 — Five-pillar platform PRD (superseded)
- v3.0 — Full production ML platform PRD: 3 models, MLOps depth
  (continuous training, monitoring, governed rollout), advanced RAG,
  MIMIC-III data source, phased (not cut) release plan (current)

## End of Document
