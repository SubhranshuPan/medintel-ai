# 00_PROJECT_SCOPE.md (v3.0)

**Status:** Updated — reflects full production ML platform scope
(`00_VISION_ML_PLATFORM.md`, adopted 2026-07-14), supersedes v2.0's
five-pillar-only framing (which itself superseded v1.0's RAG-only framing).
**Last Updated:** July 2026

---

# Product Shape

MedIntel AI is a production-grade healthcare ML platform built around five
functional pillars, now extended with a full MLOps, evaluation, and
compliance layer (`00_VISION_ML_PLATFORM.md`) rather than stopping at
"models exist and are explainable":

1. **Patient Data Platform** — upload, validate, clean, manage, and version
   patient datasets; patient/medical-record management; a lightweight
   versioned feature store (ADR-009, ADR-014, ADR-018).
2. **Clinical Analytics Dashboard** — disease prevalence, risk
   distributions, demographic analysis, time-series trends, KPIs, cohort
   analysis, and disease pattern mining.
3. **Machine Learning Engine** — **three** predictive/retrieval models
   (risk stratification, treatment outcome prediction, literature relevance
   ranking), SHAP explainability, model comparison, prediction history,
   continuous training with hyperparameter optimization, monitoring, and
   governed A/B rollout (ADR-010, ADR-011, ADR-015, ADR-016, ADR-019).
4. **AI Decision Support** — natural-language Q&A over uploaded data,
   model-prediction explanations, patient summaries, and a 7-stage
   advanced RAG retrieval pipeline over medical literature (ADR-004,
   ADR-005, ADR-017).
5. **Reporting** — PDF reports, CSV exports, executive dashboards, clinical
   summaries, and model-monitoring/fairness summary exports.

The AI Decision Support pillar is the original RAG/chat scope from v1.0; it
is now one module among five, and its retrieval quality is now held to
explicit, measured targets (NDCG, citation accuracy) rather than "it
returns something relevant."

---

# Stakeholder Matrix

| Stakeholder                | Primary Goal                                                 | How MedIntel AI Helps                                                                                       |
| --------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Healthcare Data Scientist  | Develop accurate and explainable ML models                   | Dataset management, model training, experiment tracking, SHAP explainability, model comparison, hyperparameter optimization, drift/fairness monitoring. |
| Clinical Researcher        | Analyse patient trends and validate research hypotheses      | Analytics dashboards, interpretable predictions, feature analysis, historical comparison, cohort analysis, disease pattern mining.           |
| Hospital Administrator     | Monitor operational performance and reduce readmission rates | KPI dashboards, readmission risk, executive PDF reports, outcome tracking.                                   |
| System Administrator       | Maintain application reliability and security                | Auth, monitoring (Prometheus/Grafana), logging, backups, deployment tooling, alerting.                       |
| Recruiter / Hiring Manager | Evaluate engineering capability                               | Demonstrates data engineering, full production MLOps (experiment tracking, continuous training, monitoring, A/B testing), explainable/fair AI, full-stack development, and documentation discipline. |

---

# Functional Requirements

## Pillar 1 — Patient Data Platform
* CSV Upload
* Schema & Data Validation (pandera — ADR-014)
* Cleaning / Preprocessing
* Dataset Management (list, view, delete)
* Dataset Versioning (see ADR-009)
* Patient & Medical Record management (demographics, history, uploaded
  documents, OCR'd/structured extraction, patient timeline)
* Lightweight versioned feature store, keyed to `dataset_version_id`
* Clinical training data sourcing via credentialed MIMIC-III access
  (ADR-018), synthetic data as interim/CI fallback

## Pillar 2 — Clinical Analytics Dashboard
* Disease Prevalence Views
* Risk Distribution Views
* Demographic Analysis
* Time-Series Trends
* KPI Dashboards
* Cohort Analysis (filter/compare by condition, treatment, demographics, outcomes)
* Disease Pattern Mining (clustering, association discovery, atypical-presentation detection)
* Outcome Tracking (treatment success rates, recovery time trends, readmission rates)

## Pillar 3 — Machine Learning Engine
* Feature Engineering
* **Model 1 — Patient Risk Stratification** (XGBoost; cardiac/diabetes/stroke/cancer risk score) — ADR-010
* **Model 2 — Treatment Outcome Predictor** (Random Forest + Gradient Boosting ensemble; success probability, recovery time, alternatives)
* **Model 3 — Literature Relevance Ranker** (multi-stage RAG retrieval quality as a ranking problem — ADR-017)
* Model Evaluation & Comparison (MLflow)
* Prediction API
* Explainable Predictions via SHAP — see ADR-011
* Prediction History
* Hyperparameter Optimization (Optuna) and Continuous/Triggered Retraining — ADR-015
* Drift, Performance, and Fairness Monitoring — ADR-016
* A/B Testing & Governed Rollout (statistical + fairness promotion gate) — ADR-019

## Pillar 4 — AI Decision Support
* Natural-Language Q&A over uploaded data
* Model Prediction Explanation (natural language, grounded in SHAP output)
* Patient Summary Generation
* Advanced Multi-Stage RAG Retrieval (dense + sparse + fusion + re-ranking
  + citation graph + temporal decay) with Citation Generation — ADR-017

## Pillar 5 — Reporting
* PDF Report Generation — see ADR-012
* CSV / XLSX Exports
* Executive Dashboards
* Clinical Summaries
* Model Monitoring / Fairness Summary Exports

## Cross-Cutting
* User Registration, Secure Login, JWT Authentication, Role-Based Authorization
* User Management, Model Version Management, System Logs, Audit Trail
* **MLOps & Governance** (new): experiment tracking, model registry
  lifecycle (`Staging`/`Production`/`Archived`), scheduled/triggered
  retraining, drift/fairness monitoring and alerting, statistical A/B
  rollout gate — ADR-010, ADR-015, ADR-016, ADR-019
* **Privacy & Compliance** (new): HIPAA-aware de-identification and access
  controls, GDPR rights (deletion, portability, consent tracking) — full
  detail in `11_PRIVACY_COMPLIANCE.md` (in progress)

---

# Non-Functional Requirements

## Performance
* API response time below 300ms (p95) for inference requests.
* Dashboard initial load under 2 seconds on broadband connections.
* Background jobs (training, report generation, monitoring sweeps) must not
  block the request thread — see ADR-010, ADR-015, ADR-016.
* RAG retrieval under 500ms (p95) — a materially harder target now that
  retrieval is a 7-stage pipeline (ADR-017); requires explicit per-stage
  latency budgeting, tracked as an open risk (see Risk Register below and
  `02_TRD.md` §19).
* Model inference under 2 seconds.

## Scalability
* Multiple prediction models running concurrently.
* Multiple hospitals (future).
* Horizontal backend scaling.
* Independent ML model deployment and independent rollout per model.
* Architecture supports 10x user growth without major refactoring.

## Security
* JWT Authentication, bcrypt password hashing, HTTPS in production.
* Environment variable management, input validation, SQL injection / XSS prevention, rate limiting.
* Real (credentialed, de-identified) clinical data (MIMIC-III) is handled
  under its Data Use Agreement — private infrastructure only, never
  committed to the repository or a public-facing environment — see
  ADR-018. Synthetic data continues to be treated as if it were real PHI
  throughout, per the project's GDPR-aware stance — see Assumptions.

## Reliability
* Graceful API error handling, structured logging, health check endpoints, automatic restart via Docker, database migration support.
* Scheduled jobs (retraining, monitoring sweeps, rollout evaluation) must
  be themselves monitored — a silently-stopped Celery beat schedule is a
  reliability failure, not just an ML concern (ADR-015, ADR-016).

## Maintainability
* Modular architecture, layered backend, comprehensive documentation, type-safe frontend, consistent standards.
* Every new architectural or tooling decision (this scope introduced five:
  ADR-015–019) is documented as an ADR before being adopted in code, per
  the project's existing convention.

## Observability
* Application logs, API metrics, health status, error rates, performance metrics.
* Model-specific observability (new): prediction/feature distribution,
  data/model drift (KS-test, Wasserstein distance), fairness gap by
  demographic group, calibration drift — Prometheus + Grafana (ADR-016).

## Fairness (new)
* Every predictive model is evaluated for bias across demographic groups
  using equalized odds, demographic parity, and predictive parity.
* A fairness gap exceeding 5% between groups is treated as a monitoring
  alert condition (ADR-016) and blocks A/B auto-promotion (ADR-019) — not
  just reported after the fact.

---

# Assumptions

* Publicly available research datasets and synthetic data are used.
  **Updated 2026-07-14 (ADR-018):** this now explicitly includes MIMIC-III
  via credentialed PhysioNet access for real-data model validation —
  MIMIC-III is already de-identified under HIPAA Safe Harbor by its
  custodian, but access and handling are still governed by its Data Use
  Agreement (no redistribution, no re-identification attempts, private
  infrastructure only). This is a narrower, more precise claim than v2.0's
  blanket "no PHI stored" — see ADR-018 for full handling requirements.
* Predictions are for educational and research purposes only, not clinical
  decision-making — this holds regardless of whether the underlying
  training data is synthetic or MIMIC-III-sourced.
* Users possess basic technical knowledge.
* Desktop usage is prioritized over mobile for Version 1.
* English is the primary application language.
* Fairness and drift metrics computed against synthetic or MIMIC-III
  research data demonstrate methodology, not a validated real-world safety
  or fairness claim about any live clinical deployment — this caveat
  travels with every dashboard, demo, or portfolio artifact that shows
  these numbers (ADR-016, ADR-019).

---

# Constraints

**Technical:** Student-friendly budget, open-source technologies where
possible, free cloud tiers during development, PostgreSQL, FastAPI, React +
TypeScript, Dockerized deployment. The MLOps/monitoring stack added in this
scope (MLflow, Optuna, Prometheus, Grafana, Alertmanager, Celery beat) is
self-hosted rather than a paid SaaS product for the same budget reasons.

**Development:** Single primary developer, limited timeline before MSc
(September 2026), documentation-first workflow, AI-assisted development
with human review. **This scope expansion (2026-07-14) materially
increases the amount of work against an unchanged November 2026
interview-readiness target** — see the Risk Register entry below and
`CLAUDE.md`'s binding scope mandate: the response to a timeline conflict is
to surface it explicitly, not silently descope.

**External dependency:** MIMIC-III credentialed access (PhysioNet account +
CITI training + Data Use Agreement) has its own timeline outside the
project's control — tracked as an active risk, not assumed instantaneous.

---

# Project Success Metrics

## Engineering Metrics
| Metric | Target |
|---|---|
| API Response Time | <300 ms (p95) |
| RAG Retrieval Latency | <500 ms (p95) |
| Model Inference Latency | <2 s |
| System Uptime | >99.9% |
| Frontend Lighthouse Score | >90 |
| Docker Deployment | Successful |
| CI/CD Pipeline | Passing |
| Test Coverage | >80% |
| Backend Type Coverage | 100% |

## Machine Learning Metrics
| Metric | Target |
|---|---|
| Risk Model (Model 1) ROC-AUC | ≥0.85 |
| Risk Model Precision / Recall | ≥0.80 / ≥0.80 |
| Treatment Outcome (Model 2) Precision / Recall | >0.80 / >0.80 |
| Literature Ranker (Model 3) NDCG@5 | >0.75 |
| Literature Ranker Precision@5 | >0.85 |
| Citation Accuracy | >95% |
| Hallucination Rate | <5% |
| Fairness Gap (all models, across demographic groups) | <5% |
| SHAP Explainability | Implemented, all predictive models |
| Model Versioning & Registry | Implemented (MLflow) |
| Continuous Training Pipeline | Implemented (ADR-015) |
| Monitoring & Alerting | Implemented (ADR-016) |
| A/B Rollout Governance | Implemented (ADR-019) |

## Product Metrics
* Secure authentication operational.
* End-to-end data upload → prediction → explanation workflow functional.
* Analytics dashboard, including cohort analysis, operational.
* Reporting (PDF/CSV) operational.
* Model monitoring dashboard operational and showing real (even if
  synthetic-data-derived) drift/fairness trends.
* Live deployment completed.

## Portfolio Metrics
* Production deployment available.
* Professional GitHub repository with full ADR trail (19 ADRs as of this
  scope, growing as remaining design decisions are made).
* Demo video covering all five pillars **and** the MLOps/monitoring layer
  (training run, drift alert, A/B rollout decision) — not just the
  user-facing product.
* Resume-ready project spanning data engineering, applied ML, MLOps, and
  applied AI — explicitly positioned as production-grade, not a tutorial
  project, per `CLAUDE.md`'s binding scope mandate.

---

# Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Scope Creep / Scope Size (now a full ML platform, not just 5 pillars, solo) | **High** | **High** | Sequenced build order: TRD/PRD/design docs first (this pass), then implementation pillar-by-pillar; risk tracked explicitly rather than silently absorbed — see `.ai/memory/project-memory.md` Risk Register and `CLAUDE.md`'s binding scope mandate. If Sprint 3–4 velocity shows the full scope isn't achievable by November 2026, that's an explicit decision point for Som, informed by real data. |
| MIMIC-III Credentialing Delay (ADR-018) | Medium | High | Start PhysioNet account + CITI training immediately, in parallel with all other work; synthetic data as interim fallback so Sprint velocity doesn't stall on this dependency. |
| RAG Pipeline Latency (7 stages vs. <500ms target, ADR-017) | Medium | Medium | Parallelise stages 1–2 (dense+sparse); per-stage latency budgeting and profiling before assuming the target is met; tracked in `02_TRD.md` §19. |
| Cloud Cost Increase (now more services: MLflow, Prometheus, Grafana, Alertmanager, Celery beat) | Low–Medium | Medium | Self-hosted/open-source stack, free tiers until production; containerized so cost scales with actual usage, not a SaaS subscription. |
| Dataset Quality | Medium | High | Evaluate multiple public/synthetic datasets; pandera validation (ADR-014) catches quality issues before they reach training. |
| Technology Learning Curve (MLflow, SHAP, Celery, **now also** Optuna, Prometheus/Grafana, ColBERT/cross-encoder re-ranking) | **Medium–High** | Medium | Documentation-first approach; ADRs before implementation (ADR-015–019 already written before any code); tackle one new tool per sprint rather than all at once. |
| Deployment Failures | Medium | Medium | Containerized deployment and staging. |
| Overclaiming Synthetic/MIMIC-III Results as Real-World Validation | Low | High (reputational, in interviews) | Every fairness/drift/A-B-rollout artifact carries the "methodology, not real-world validation" caveat (ADR-016, ADR-019) — checked in doc/demo review, not left implicit. |

---

# Glossary

| Term | Meaning |
|---|---|
| API | Application Programming Interface |
| CI/CD | Continuous Integration / Continuous Deployment |
| MLOps | Machine Learning Operations |
| PHI | Protected Health Information |
| SHAP | SHapley Additive exPlanations |
| ROC-AUC | Receiver Operating Characteristic — Area Under Curve |
| RAG | Retrieval-Augmented Generation |
| HPO | Hyperparameter Optimization |
| Optuna | Python library for automated hyperparameter search, used for Models 1–2 (ADR-015) |
| Data Drift | Statistical change in a model's input feature distribution over time, detected via the Kolmogorov–Smirnov test (ADR-016) |
| Model Drift | Statistical change in a model's prediction distribution over time, detected via Wasserstein distance (ADR-016) |
| Fairness Gap | Difference in a model's performance (e.g. true positive rate) between demographic groups; monitored via equalized odds, demographic parity, predictive parity (ADR-016, ADR-019) |
| NDCG | Normalized Discounted Cumulative Gain — a ranking-quality metric used to evaluate the Literature Relevance Ranker (ADR-017) |
| ColBERT | Dense passage retrieval model using late-interaction, multi-vector embeddings (ADR-017) |
| BM25 | Sparse, keyword-based ranking function used alongside dense retrieval (ADR-017) |
| RRF | Reciprocal Rank Fusion — a method for combining multiple ranked result lists (ADR-017) |
| A/B Testing | Routing a fraction of traffic to a candidate model vs. an incumbent and comparing outcomes statistically before promotion (ADR-019) |
| MIMIC-III | Medical Information Mart for Intensive Care III — a credentialed-access clinical research database used as real-world training data for Models 1–2 (ADR-018) |
| Feature Store | A system for storing and serving versioned, reusable model input features; implemented here as a lightweight, versioned-column extension of `dataset_versions` rather than a dedicated product (`02_TRD.md` §12) |

---

# Versioning Policy

* v1.0 → Initial (RAG-chatbot-framed) scope
* v2.0 → Five-pillar clinical intelligence platform scope
* v3.0 → Full production ML platform scope: 3 predictive/retrieval models,
  continuous training + HPO, monitoring/alerting, advanced RAG, real
  (MIMIC-III) clinical data, governed A/B rollout, privacy/compliance
  layer (current)

Every major architectural decision is documented through an ADR (see `docs/architecture/adr/`).

---

# Final Statement

MedIntel AI is a production-grade software engineering platform
demonstrating Data Science, Machine Learning Engineering, full production
MLOps (experiment tracking, continuous training, monitoring, governed
rollout), Full-Stack Development, Cloud Deployment, and rigorous technical
documentation — applied to a five-pillar clinical intelligence platform,
not a single chatbot feature and not a modeling-only prototype. Per
`CLAUDE.md`'s binding scope mandate, this is the target the project is held
to; timeline pressure is a reason to surface and sequence risk explicitly,
not a reason to quietly ship a smaller thing under the same description.
