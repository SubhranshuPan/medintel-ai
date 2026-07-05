# Product Requirements Document (PRD)

**Project:** MedIntel AI
**Version:** v2.0
**Author:** Subhranshu Panda
**Status:** Active
**Last Updated:** July 2026

**Related:** `00_PROJECT_SCOPE.md`, `docs/architecture/adr/`

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
11. MVP Scope & Release Plan
12. Open Questions
13. Glossary
14. Approval

---

# 1. Executive Summary

MedIntel AI is a clinical intelligence platform spanning five pillars: a **Patient Data Platform** for ingesting and versioning clinical datasets, a **Clinical Analytics Dashboard** for exploring them, an **ML Engine** for risk and readmission prediction with SHAP explainability, an **AI Decision Support** layer for natural-language interaction and RAG-backed literature retrieval, and a **Reporting** layer for PDF/CSV/executive output.

The platform demonstrates the full lifecycle of an applied data science product: data ingestion → validation → modeling → explanation → reporting, with an LLM layer on top rather than as the sole feature.

---

# 2. Vision & Mission

**Vision:** Build an end-to-end clinical data intelligence platform that takes raw patient data through validation, prediction, explanation, and reporting — with every output either citation-backed (for AI-generated text) or model-traceable (for predictions).

**Mission:** Enable users to upload clinical datasets and, without leaving the platform: explore them visually, generate explainable risk predictions, ask natural-language questions about the data or a prediction, and export the results as shareable reports.

---

# 3. Problem Statement

Clinical data work today is fragmented across separate tools: spreadsheets for cleaning, a BI tool for dashboards, a notebook for modeling, no explainability layer, and manual report writing. Separately, general-purpose AI models produce answers without reliable citations or grounding in the actual uploaded data, making them unsuitable for decision support.

MedIntel AI consolidates ingestion, analytics, explainable prediction, grounded AI Q&A, and reporting into a single modular platform.

---

# 4. Product Goals

**Primary:** Reliable dataset ingestion with versioning; accurate and explainable risk/readmission predictions; a usable analytics dashboard; citation-backed AI answers grounded in the user's own data and in retrieved literature; exportable reports.

**Secondary:** Modular architecture allowing pillars to be developed and demoed independently; easy free-tier deployment; production-grade engineering practices throughout.

---

# 5. Target Users & Personas

**Primary users:** Healthcare Data Scientists, Clinical Researchers, Hospital Administrators. **Secondary:** Recruiters/hiring managers evaluating engineering capability.

**Persona 1 — Data Scientist:** Wants to upload a dataset, train and compare models, and inspect SHAP explanations without leaving the platform.

**Persona 2 — Clinical Researcher:** Wants to explore prevalence/demographic trends and ask natural-language questions about the dataset ("what's the readmission rate for patients over 65 with diabetes?").

**Persona 3 — Hospital Administrator:** Wants a KPI dashboard and an executive PDF summary, not raw model internals.

---

# 6. Scope

**In Scope:** All five pillars listed in `00_PROJECT_SCOPE.md`; JWT auth; Docker deployment; free-tier hosting (Railway/Render initially).

**Out of Scope (v1):** Multi-hospital tenancy, EMR integrations, mobile-first UI, real PHI, HIPAA-grade compliance certification (architecture should not preclude it later, but it is not a v1 deliverable).

---

# 7. Functional Requirements (by Pillar)

## Pillar 1 — Patient Data Platform
| ID | Requirement |
|---|---|
| FR-101 | Users can upload CSV datasets through the UI. |
| FR-102 | Uploaded data is schema-validated and cleaned before use (see ADR-009). |
| FR-103 | Users can list, inspect, and delete datasets. |
| FR-104 | Every dataset upload/transformation creates a new immutable version (ADR-009). |

## Pillar 2 — Clinical Analytics Dashboard
| ID | Requirement |
|---|---|
| FR-201 | Disease prevalence visualizations across the active dataset. |
| FR-202 | Risk distribution visualizations. |
| FR-203 | Demographic breakdowns (age, sex, region where available). |
| FR-204 | Time-series trend charts. |
| FR-205 | Configurable KPI dashboard. |

## Pillar 3 — Machine Learning Engine
| ID | Requirement |
|---|---|
| FR-301 | Train disease-risk and readmission-prediction models against a chosen dataset version (ADR-010). |
| FR-302 | Compare models by logged metrics (ROC-AUC, precision, recall) via MLflow. |
| FR-303 | Serve predictions through a REST endpoint. |
| FR-304 | Every prediction includes a SHAP-based explanation (ADR-011). |
| FR-305 | Prediction history is queryable per patient/dataset. |

## Pillar 4 — AI Decision Support
| ID | Requirement |
|---|---|
| FR-401 | Conversational natural-language Q&A over the active dataset. |
| FR-402 | Natural-language explanation of a given model prediction, grounded in its stored SHAP values (not freely generated). |
| FR-403 | Automated patient summary generation. |
| FR-404 | RAG-backed retrieval of supporting medical literature with citations. |
| FR-405 | All LLM calls go through the existing multi-provider abstraction (OpenAI/Anthropic/Gemini) — no hardcoded provider. |

## Pillar 5 — Reporting
| ID | Requirement |
|---|---|
| FR-501 | Generate PDF reports from dashboard/prediction data (ADR-012). |
| FR-502 | Export data/results as CSV or XLSX. |
| FR-503 | Executive dashboard export (summary-level, non-technical). |
| FR-504 | Clinical summary export per patient. |

## Cross-Cutting
| ID | Requirement |
|---|---|
| FR-601 | Registration, login, JWT auth, role-based authorization. |
| FR-602 | Audit logging of data uploads, predictions, and report generation (patient-data handling flagged for compliance review — see Assumptions). |

---

# 8. Non-Functional Requirements

See `00_PROJECT_SCOPE.md` §Non-Functional Requirements — Performance, Scalability, Security, Reliability, Maintainability, Observability. This PRD does not duplicate those targets; refer to the Scope doc as the single source for NFR targets.

---

# 9. Success Metrics

See `00_PROJECT_SCOPE.md` §Project Success Metrics (Engineering / ML / Product / Portfolio metrics) — shared across PRD and Scope to avoid drift between the two documents.

---

# 10. Risks & Assumptions

See `00_PROJECT_SCOPE.md` §Risk Register and §Assumptions. Notably: no real PHI is stored in v1, and predictions are for educational/research purposes, not clinical use.

---

# 11. MVP Scope & Release Plan

**MVP (must-ship before any demo/interview use):**
- Patient Data Platform (upload, validate, version)
- ML Engine (train, predict, SHAP explanation, basic comparison)
- Clinical Analytics Dashboard (core charts + KPIs)

**Stretch (ship if time allows before September 2026):**
- AI Decision Support (RAG Q&A, prediction explanation in natural language, patient summaries)
- Full Reporting (PDF/executive/clinical summary exports)

This sequencing exists because each pillar depends on data existing first, and an unfinished 5-pillar platform interviews worse than a finished 3-pillar one.

---

# 12. Open Questions

- Which public/synthetic clinical dataset(s) will be used for demo data?
- Should dataset versioning support rollback in the UI, or is version history read-only for v1?
- Does the AI Decision Support chat need to reference multiple datasets simultaneously, or only the currently active one?

---

# 13. Glossary

See `00_PROJECT_SCOPE.md` §Glossary.

---

# 14. Approval

| Role | Name | Status |
|---|---|---|
| Product Owner | Subhranshu Panda | Approved |

---

## Document Information

**Version History:**
- v1.0 — RAG-chatbot-framed PRD (superseded)
- v2.0 — Five-pillar platform PRD (current)

## End of Document
