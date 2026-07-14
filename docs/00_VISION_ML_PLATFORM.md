# 00_VISION_ML_PLATFORM.md — Full-Scope ML/MLOps/Compliance Vision

> **Status:** Adopted 2026-07-14 as binding project scope (see `CLAUDE.md` §Binding Scope Mandate).
> **Source:** Drafted from a research/planning session with GitHub Copilot, reviewed and
> adopted in full by Som on 2026-07-14 (Cowork session). Preserved close to its original
> form so intent isn't lost in summarization; execution detail lives in the ADRs and docs
> it points to.

## Why this document exists

MedIntel AI is not a simple RAG chatbot. It is a **production-grade, industry-level
healthcare intelligence platform** combining:

- Retrieval-Augmented Generation (RAG) for medical literature search
- Multiple predictive ML models for healthcare decision support
- MLOps infrastructure with experiment tracking and model monitoring
- Comprehensive evaluation frameworks and fairness testing
- Privacy-compliant data architecture (HIPAA/GDPR ready)

The project demonstrates full-stack data science engineering: data pipeline → model
deployment → production monitoring. Every component in this document is in scope, not
aspirational filler — see `CLAUDE.md`'s binding scope mandate.

---

## Predictive ML Models

### Model 1: Patient Risk Stratification
- **Input:** demographics (age, gender, BMI) + comorbidities + lab values + vital signs + medications
- **Output:** risk score (0–100) for cardiac disease, diabetes, stroke, cancer
- **Algorithm:** XGBoost classifier
- **Training data:** MIMIC-III clinical database (real, credentialed — see ADR-018 and the
  tracked risk in `.ai/memory/project-memory.md`)
- **Success metrics:** ROC-AUC ≥ 0.85, Precision ≥ 0.80, Recall ≥ 0.80
- **Real-world use:** help doctors identify high-risk patients for early intervention
- **Explainability:** SHAP values showing top risk factors per patient (ADR-011)
- **Deployment:** online inference API + batch prediction pipeline (ADR-010)
- **Monitoring:** prediction drift, fairness by demographics, calibration (ADR-016)

### Model 2: Treatment Outcome Predictor
- **Input:** diagnosis + proposed treatment + patient profile + similar historical cases
- **Output:** success probability (%), expected recovery time, confidence interval,
  possible side effects, ranked alternative treatments
- **Algorithm:** ensemble (Random Forest + Gradient Boosting)
- **Training data:** clinical trial results + EHR outcome data
- **Success metrics:** Precision > 0.80, Recall > 0.80, calibration curve
- **Real-world use:** help doctors choose the optimal treatment for an individual patient
- **Fairness testing:** ensure similar success rates across demographics
- **Deployment:** real-time inference with uncertainty quantification

### Model 3: Literature Relevance Ranker (Advanced RAG)
Current baseline is basic vector similarity search. Target is a multi-stage retrieval
pipeline (ADR-017):

1. Dense passage retrieval (ColBERT)
2. Sparse BM25 keyword matching
3. Metadata filtering (publication year, journal quality)
4. Fusion/aggregation (Reciprocal Rank Fusion)
5. Cross-encoder re-ranking
6. Citation graph traversal (related papers)
7. Temporal decay (recent papers weighted higher)

- **Training data:** annotated queries with relevance judgments from medical experts
- **Success metrics:** NDCG@5 > 0.75, Precision@5 > 0.85, citation accuracy > 95%
- **Real-world use:** retrieve the most relevant medical evidence for clinical questions

---

## MLOps Infrastructure

**Experiment tracking (MLflow, ADR-010):** log hyperparameters, training/test metrics,
artifacts, training time, cost; compare experiments; promote best models to staging.

**Model versioning & registry (ADR-010):** central repository for all models (risk,
outcome, ranker); version naming `v1.0`, `v1.1`, `v2.0`; deployment stages
development → staging → production; rollback to a previous version on degradation.

**Monitoring & alerting (ADR-016):**
- Data drift detection (Kolmogorov–Smirnov test)
- Model drift detection (Wasserstein distance)
- Performance degradation alert if ROC-AUC drops > 5%
- Fairness monitoring: alert if performance gap between demographic groups > 5%
- Cost tracking: LLM tokens, API calls, GPU time per prediction
- Automated alerting via Slack/email

**A/B testing framework (ADR-019):** route a percentage of users to new vs. baseline
model; track metrics per cohort; statistical significance testing; auto-promote if the
new model is better by > 2% over 7 days.

**Continuous training pipeline (ADR-015):** weekly retraining on latest data; automated
hyperparameter optimization (Optuna); cross-validation for robustness; automatic
evaluation on the test set; trigger retraining on data drift OR performance
degradation > 3%.

---

## Comprehensive Evaluation Framework
*(full detail: `08_EVALUATION_FRAMEWORK.md`, once written)*

- **Retrieval evaluation:** Precision@k, Recall@k, NDCG, MRR, citation accuracy against a
  500+ query expert-annotated test set; benchmark vs. PubMed/Google Scholar/ChatGPT.
- **Generation evaluation:** BLEU, ROUGE, hallucination rate, medical accuracy (expert
  review, inter-rater κ > 0.80), citation correctness, against a 100+ gold-standard Q&A set.
- **Prediction model evaluation:** ROC-AUC, PR curve, F1, calibration plots, fairness
  testing (equalized odds, demographic parity, predictive parity — alert if disparity
  > 5%), cost-effectiveness, ablation studies.
- **System-level benchmarking:** vs. Framingham/CHADS2 (risk), PubMed/UpToDate
  (retrieval), clinical guidelines (treatment recommendations), Optum/Epic/Cerner (cost).
- **Continuous evaluation pipeline:** weekly automated eval, regression detection
  (alert on any metric drop > 3%), bias drift detection, trend dashboard.

---

## Patient Data Management & Medical Records
*(full detail: `10_PATIENT_MANAGEMENT.md`, once written; schema: `05_BACKEND_DESIGN.md`)*

New entities: `Patient`, `MedicalRecord`, `RiskScore`, `TreatmentRecommendation`,
`PredictionLog`, `ModelVersion`, `AnnotatedData`.

Data pipeline: ETL for CSV/PDF/HL7 ingestion, OCR for medical documents, structured
extraction (medications, diagnoses, lab values), feature engineering (temporal
aggregations, domain transforms), dataset versioning (ADR-009), data quality checks.

Medical record features: upload reports (PDF/image), OCR extraction, structured
extraction, patient timeline view, version history.

---

## Privacy & Compliance
*(full detail: `11_PRIVACY_COMPLIANCE.md`, once written)*

**HIPAA:** de-identification of all PII, encryption at rest and in transit, RBAC +
admin audit trails, full audit logging (user, timestamp, action per access).

**GDPR:** right to deletion, right to portability, data processing agreements for any
third-party services, consent tracking.

**Data governance:** retention policy, de-identification before model training,
differential privacy for aggregates, audit dashboard.

---

## Advanced Analytics & Insights

Cohort analysis dashboard (filter/compare by condition, treatment, demographics,
outcomes), disease pattern mining (clustering, association discovery, treatment
effectiveness comparison, atypical presentation detection), outcome tracking (success
rates, recovery time trends, complication/readmission rates), clinical insights
(common conditions, literature trends, resource utilization, treatment recommendations).

---

## System Monitoring & Observability
*(full detail: `12_MONITORING_ALERTS.md`, once written)*

Metrics: API latency, retrieval latency, LLM inference time, model prediction latency,
DB query time, error rates by endpoint. Model-specific: prediction/feature
distribution, performance/fairness/calibration drift. Alerting: page on-call if API
latency > 5s, alert if error rate > 5%, model performance drop > 5%, data quality
issues, fairness worsening, prediction drift. Dashboards: system health, model
performance trends, user activity, cost tracking, data quality metrics.

---

## Key Principles

1. **Production-grade** — every component deployment-ready, not a prototype.
2. **Measurable impact** — every feature has clear success metrics.
3. **Explainability** — all AI outputs include explanations (SHAP, citations, confidence).
4. **Fairness** — all models tested for bias across demographics.
5. **Monitoring** — every model has continuous monitoring for drift/degradation.
6. **Scalability** — architecture supports 10x user growth without major refactoring.
7. **Security** — HIPAA/GDPR compliance from day one, not an afterthought.
8. **Data science rigor** — rigorous evaluation frameworks, not just user feedback.

## Success Criteria

**Technical:** API latency < 300ms (p95), RAG retrieval < 500ms, model inference < 2s,
uptime > 99.9%.

**ML:** Risk model ROC-AUC > 0.85, Treatment Outcome Precision/Recall > 0.80, Literature
Ranker NDCG > 0.75, Hallucination rate < 5%, Citation accuracy > 95%, Fairness gap < 5%
across demographics.

**Healthcare impact:** reduce clinical decision time by 50%, identify high-risk patients
earlier (sensitivity > 80%), reduce adverse outcomes (measured via pilot study), support
evidence-based medicine (all claims cited).

---

## Documentation Roadmap

**New documents to create:**

| Doc | Scope |
|---|---|
| `06_ML_MODELS.md` | Full architecture for all 3 prediction models: training, hyperparameters, evaluation, SHAP, deployment, monitoring |
| `07_ML_OPS.md` | MLflow setup, registry design, continuous training, A/B testing, monitoring/alerting, cost tracking |
| `08_EVALUATION_FRAMEWORK.md` | Retrieval/generation/prediction evaluation, fairness testing, continuous eval, benchmarking |
| `09_DATA_PIPELINE.md` | ETL architecture, feature engineering, dataset versioning (DVC), data quality, de-identification |
| `10_PATIENT_MANAGEMENT.md` | Patient data model, medical record processing, timeline, concept extraction |
| `11_PRIVACY_COMPLIANCE.md` | HIPAA/GDPR requirements, data governance, audit logging, de-identification procedures |
| `12_MONITORING_ALERTS.md` | Prometheus metrics, Grafana dashboards, alert thresholds, on-call escalation |

**Existing documents to significantly modify:**

| Doc | Additions |
|---|---|
| `01_PRD.md` | New ML features, cohort analysis, disease pattern mining, ML monitoring/fairness requirements, per-model success metrics, use cases |
| `02_TRD.md` | ML infra stack, data pipeline architecture, feature store design, ML monitoring architecture, training pipeline orchestration, deployment strategy |
| `03_APP_FLOW.md` | Risk assessment flow, treatment outcome flow, cohort analysis flow, retraining flow, A/B testing flow, active learning flow |
| `05_BACKEND_DESIGN.md` | `Patient`, `MedicalRecord`, `RiskScore`, `TreatmentOutcome`, `ModelVersion`, `PredictionLog`, `AnnotatedData`, enhanced `AuditLog` |

**New ADRs required before the docs above can be written consistently** (a stack/process
decision this size doesn't get silently folded into a PRD — it gets an ADR first, per
this project's own conventions):

| ADR | Decision |
|---|---|
| ADR-015 | Continuous training pipeline + Optuna hyperparameter optimization (extends ADR-010) |
| ADR-016 | ML monitoring & alerting stack — Prometheus + Grafana, drift/fairness detection |
| ADR-017 | Advanced multi-stage RAG retrieval pipeline (extends ADR-004, ADR-005) |
| ADR-018 | MIMIC-III as clinical training data source (credentialing risk tracked separately) |
| ADR-019 | A/B testing & progressive model rollout framework |

Tracking: `.ai/memory/session-history.md` (2026-07-14 entry) and the Cowork task list for
this session enumerate the same work as trackable items.
