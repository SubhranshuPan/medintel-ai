# 00_PROJECT_SCOPE.md (v1.0)

---

# Stakeholder Matrix

| Stakeholder                | Primary Goal                                                 | How MedIntel AI Helps                                                                                       |
| -------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| Healthcare Data Scientist  | Develop accurate and explainable ML models                   | Provides model training, experiment tracking, evaluation metrics, and explainability tools.                 |
| Clinical Researcher        | Analyse patient trends and validate research hypotheses      | Enables interpretable predictions, feature analysis, and historical experiment comparison.                  |
| Hospital Administrator     | Monitor operational performance and reduce readmission rates | Provides dashboards, KPIs, analytics, and risk summaries.                                                   |
| System Administrator       | Maintain application reliability and security                | Provides authentication, monitoring, logging, backups, and deployment tooling.                              |
| Recruiter / Hiring Manager | Evaluate engineering capability                              | Demonstrates full-stack engineering, MLOps, software architecture, documentation, and deployment practices. |

---

# Functional Requirements

The system shall provide the following capabilities:

### Authentication

* User Registration
* Secure Login
* Password Reset
* JWT Authentication
* Role-Based Authorization

### Machine Learning

* Data Upload
* Data Validation
* Data Preprocessing
* Feature Engineering
* Model Training
* Model Evaluation
* Prediction API
* Explainable Predictions using SHAP
* Prediction History

### Dashboard

* Patient Statistics
* Risk Distribution
* Model Performance
* Historical Predictions
* Feature Importance Visualizations

### Administration

* User Management
* Model Version Management
* System Logs
* Audit Trail

---

# Non-Functional Requirements

## Performance

* API response time below 300 milliseconds for inference requests.
* Dashboard initial load under 2 seconds on broadband connections.
* Support concurrent prediction requests without blocking.

---

## Scalability

The architecture should support:

* Multiple prediction models
* Multiple hospitals (future)
* Horizontal backend scaling
* Independent ML model deployment

---

## Security

The platform shall implement:

* JWT Authentication
* Password Hashing (bcrypt)
* HTTPS in production
* Environment Variable Management
* Input Validation
* SQL Injection Prevention
* XSS Protection
* Rate Limiting

---

## Reliability

* Graceful API error handling
* Structured logging
* Health Check Endpoints
* Automatic restart through Docker
* Database migration support

---

## Maintainability

* Modular architecture
* Clear folder structure
* Layered backend architecture
* Comprehensive documentation
* Type-safe frontend
* Consistent coding standards

---

## Observability

The system should expose:

* Application Logs
* API Metrics
* Health Status
* Error Rates
* Performance Metrics

---

# Assumptions

The following assumptions are made for Version 1:

* Only publicly available datasets will be used.
* No Protected Health Information (PHI) will be stored.
* Predictions are for educational and research purposes only.
* Users possess basic technical knowledge.
* Internet connectivity is available.
* Desktop usage is prioritized over mobile for Version 1.
* English is the primary application language.

---

# Constraints

Technical Constraints

* Student-friendly budget.
* Open-source technologies whenever possible.
* Free cloud tiers during development.
* PostgreSQL as the primary database.
* FastAPI as the backend framework.
* React with TypeScript for the frontend.
* Dockerized deployment.

Development Constraints

* Single primary developer.
* Limited development timeline before MSc.
* Documentation-first workflow.
* AI-assisted development with human review.

---

# Project Success Metrics

## Engineering Metrics

| Metric                    | Target     |
| ------------------------- | ---------- |
| API Response Time         | <300 ms    |
| Frontend Lighthouse Score | >90        |
| Docker Deployment         | Successful |
| CI/CD Pipeline            | Passing    |
| Test Coverage             | >80%       |
| Backend Type Coverage     | 100%       |

---

## Machine Learning Metrics

| Metric              | Target      |
| ------------------- | ----------- |
| ROC-AUC             | ≥0.85       |
| Precision           | ≥0.80       |
| Recall              | ≥0.80       |
| SHAP Explainability | Implemented |
| Model Versioning    | Implemented |

---

## Product Metrics

* Secure authentication operational.
* End-to-end prediction workflow functional.
* Explainability dashboard operational.
* Live deployment completed.
* Architecture documentation complete.

---

## Portfolio Metrics

By project completion:

* Production deployment available.
* Professional GitHub repository.
* Comprehensive documentation.
* Architecture diagrams.
* Demo video.
* Resume-ready project.
* Technical blog/article (optional).

---

# Risk Register

| Risk                      | Probability | Impact | Mitigation                           |
| ------------------------- | ----------- | ------ | ------------------------------------ |
| Scope Creep               | High        | High   | Strict implementation plan           |
| Cloud Cost Increase       | Low         | Medium | Use free tiers until production      |
| Dataset Quality           | Medium      | High   | Evaluate multiple datasets           |
| Technology Learning Curve | Medium      | Medium | Documentation-first approach         |
| Deployment Failures       | Medium      | Medium | Containerized deployment and staging |

---

# Glossary

| Term       | Meaning                                              |
| ---------- | ---------------------------------------------------- |
| API        | Application Programming Interface                    |
| CI/CD      | Continuous Integration / Continuous Deployment       |
| Docker     | Containerization platform                            |
| FastAPI    | Python web framework for APIs                        |
| JWT        | JSON Web Token                                       |
| MLOps      | Machine Learning Operations                          |
| PHI        | Protected Health Information                         |
| PostgreSQL | Relational Database Management System                |
| SHAP       | SHapley Additive exPlanations                        |
| ROC-AUC    | Receiver Operating Characteristic - Area Under Curve |

---

# Versioning Policy

Documentation Version: Semantic Versioning

* v0.x → Draft
* v1.0 → Stable Documentation
* v1.x → Minor Improvements
* v2.0 → Major Product Expansion

Every major architectural decision shall be documented through an Architecture Decision Record (ADR).

---

# Repository Standards

This repository follows the following principles:

* Documentation before implementation.
* Architecture before coding.
* Testing before deployment.
* Explainability before optimization.
* Production quality over prototype speed.
* Code reviews (AI + Human).
* Conventional Git commits.
* Issue-driven development.
* Milestone-based releases.

---

# Final Statement

MedIntel AI is not intended to be a classroom assignment or a simple machine learning demonstration.

It is a production-oriented software engineering project whose primary objective is to demonstrate professional competence in Data Science, Machine Learning Engineering, Full-Stack Development, MLOps, Cloud Deployment, and Technical Documentation while solving a meaningful healthcare analytics problem using explainable artificial intelligence.
