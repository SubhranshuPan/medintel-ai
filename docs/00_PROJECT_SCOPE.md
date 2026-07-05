# 00_PROJECT_SCOPE.md (v2.0)

**Status:** Updated — reflects five-pillar platform scope (supersedes v1.0's RAG-only framing)
**Last Updated:** July 2026

---

# Product Shape

MedIntel AI is a clinical intelligence platform built around five functional pillars:

1. **Patient Data Platform** — upload, validate, clean, manage, and version patient datasets.
2. **Clinical Analytics Dashboard** — disease prevalence, risk distributions, demographic analysis, time-series trends, KPIs.
3. **Machine Learning Engine** — disease risk & readmission prediction, SHAP explainability, model comparison, prediction history.
4. **AI Decision Support** — natural-language Q&A over uploaded data, model-prediction explanations, patient summaries, RAG-backed medical literature retrieval.
5. **Reporting** — PDF reports, CSV exports, executive dashboards, clinical summaries.

The AI Decision Support pillar is the original RAG/chat scope from v1.0; it is now one module among five rather than the whole product.

---

# Stakeholder Matrix

| Stakeholder                | Primary Goal                                                 | How MedIntel AI Helps                                                                                       |
| --------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Healthcare Data Scientist  | Develop accurate and explainable ML models                   | Dataset management, model training, experiment tracking, SHAP explainability, model comparison.             |
| Clinical Researcher        | Analyse patient trends and validate research hypotheses      | Analytics dashboards, interpretable predictions, feature analysis, historical comparison.                   |
| Hospital Administrator     | Monitor operational performance and reduce readmission rates | KPI dashboards, readmission risk, executive PDF reports.                                                     |
| System Administrator       | Maintain application reliability and security                | Auth, monitoring, logging, backups, deployment tooling.                                                     |
| Recruiter / Hiring Manager | Evaluate engineering capability                               | Demonstrates data engineering, MLOps, explainable AI, full-stack development, and documentation discipline. |

---

# Functional Requirements

## Pillar 1 — Patient Data Platform
* CSV Upload
* Schema & Data Validation
* Cleaning / Preprocessing
* Dataset Management (list, view, delete)
* Dataset Versioning (see ADR-009)

## Pillar 2 — Clinical Analytics Dashboard
* Disease Prevalence Views
* Risk Distribution Views
* Demographic Analysis
* Time-Series Trends
* KPI Dashboards

## Pillar 3 — Machine Learning Engine
* Feature Engineering
* Model Training (disease risk, readmission) — see ADR-010
* Model Evaluation & Comparison
* Prediction API
* Explainable Predictions via SHAP — see ADR-011
* Prediction History

## Pillar 4 — AI Decision Support
* Natural-Language Q&A over uploaded data
* Model Prediction Explanation (natural language, grounded in SHAP output)
* Patient Summary Generation
* RAG-Backed Medical Literature Retrieval, Citation Generation

## Pillar 5 — Reporting
* PDF Report Generation — see ADR-012
* CSV / XLSX Exports
* Executive Dashboards
* Clinical Summaries

## Cross-Cutting
* User Registration, Secure Login, JWT Authentication, Role-Based Authorization
* User Management, Model Version Management, System Logs, Audit Trail

---

# Non-Functional Requirements

## Performance
* API response time below 300ms for inference requests.
* Dashboard initial load under 2 seconds on broadband connections.
* Background jobs (training, report generation) must not block the request thread — see ADR-010.

## Scalability
* Multiple prediction models running concurrently.
* Multiple hospitals (future).
* Horizontal backend scaling.
* Independent ML model deployment.

## Security
* JWT Authentication, bcrypt password hashing, HTTPS in production.
* Environment variable management, input validation, SQL injection / XSS prevention, rate limiting.
* No PHI stored — see Assumptions.

## Reliability
* Graceful API error handling, structured logging, health check endpoints, automatic restart via Docker, database migration support.

## Maintainability
* Modular architecture, layered backend, comprehensive documentation, type-safe frontend, consistent standards.

## Observability
* Application logs, API metrics, health status, error rates, performance metrics.

---

# Assumptions

* Only publicly available / synthetic datasets are used.
* No Protected Health Information (PHI) will be stored.
* Predictions are for educational and research purposes only, not clinical decision-making.
* Users possess basic technical knowledge.
* Desktop usage is prioritized over mobile for Version 1.
* English is the primary application language.

---

# Constraints

**Technical:** Student-friendly budget, open-source technologies where possible, free cloud tiers during development, PostgreSQL, FastAPI, React + TypeScript, Dockerized deployment.

**Development:** Single primary developer, limited timeline before MSc (September 2026), documentation-first workflow, AI-assisted development with human review.

---

# Project Success Metrics

## Engineering Metrics
| Metric | Target |
|---|---|
| API Response Time | <300 ms |
| Frontend Lighthouse Score | >90 |
| Docker Deployment | Successful |
| CI/CD Pipeline | Passing |
| Test Coverage | >80% |
| Backend Type Coverage | 100% |

## Machine Learning Metrics
| Metric | Target |
|---|---|
| ROC-AUC | ≥0.85 |
| Precision | ≥0.80 |
| Recall | ≥0.80 |
| SHAP Explainability | Implemented |
| Model Versioning | Implemented |

## Product Metrics
* Secure authentication operational.
* End-to-end data upload → prediction → explanation workflow functional.
* Analytics dashboard operational.
* Reporting (PDF/CSV) operational.
* Live deployment completed.

## Portfolio Metrics
* Production deployment available.
* Professional GitHub repository with ADR trail.
* Demo video covering all five pillars.
* Resume-ready project spanning data engineering, ML, and applied AI.

---

# Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Scope Creep (5 pillars is a lot solo) | High | High | MVP sequencing: Data Platform → ML Engine → Dashboard are must-ship; AI Decision Support + full Reporting are stretch. |
| Cloud Cost Increase | Low | Medium | Free tiers until production. |
| Dataset Quality | Medium | High | Evaluate multiple public/synthetic datasets. |
| Technology Learning Curve (MLflow, SHAP, Celery new to stack) | Medium | Medium | Documentation-first approach; ADRs before implementation. |
| Deployment Failures | Medium | Medium | Containerized deployment and staging. |

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

---

# Versioning Policy

* v1.0 → Initial (RAG-chatbot-framed) scope
* v2.0 → Five-pillar clinical intelligence platform scope (current)

Every major architectural decision is documented through an ADR (see `docs/architecture/adr/`).

---

# Final Statement

MedIntel AI is a production-oriented software engineering project demonstrating Data Science, Machine Learning Engineering, Full-Stack Development, MLOps, Cloud Deployment, and Technical Documentation practice — applied to a five-pillar clinical intelligence platform, not a single chatbot feature.
