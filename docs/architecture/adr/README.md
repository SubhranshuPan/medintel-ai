# Architecture Decision Records (ADRs)

Architecture Decision Records document significant engineering decisions made throughout the development of MedIntel AI.

Each ADR follows the template:

- Status
- Context
- Decision
- Alternatives Considered
- Consequences (Positive / Negative)
- References

ADRs provide historical context for future contributors and simplify architectural evolution.

## Index

| ADR | Decision | Status |
|---|---|---|
| [001](ADR-001-fastapi.md) | FastAPI as Backend Framework | Accepted |
| [002](ADR-002-react.md) | React as Frontend Framework | Accepted |
| [003](ADR-003-postgresql.md) | PostgreSQL as Relational Database | Accepted |
| [004](ADR-004-qdrant.md) | Qdrant as Vector Database | Accepted |
| [005](ADR-005-langchain.md) | LangChain + LangGraph as Orchestration Framework | Accepted |
| [006](ADR-006-docker.md) | Docker for Containerization | Accepted |
| [007](ADR-007-github-actions.md) | GitHub Actions as CI/CD | Accepted |
| [008](ADR-008-modular-monolith.md) | Modular Monolith Architecture | Accepted |
| [009](ADR-009-dataset-versioning.md) | Dataset Versioning Strategy | Accepted |
| [010](ADR-010-ml-model-serving.md) | ML Model Training, Registry, and Serving Strategy | Accepted |
| [011](ADR-011-shap-explainability.md) | SHAP as the Explainability Tooling | Accepted |
| [012](ADR-012-reporting-export.md) | Reporting and Export Tooling | Accepted |
| [013](ADR-013-orm-migrations.md) | SQLAlchemy 2.0 (async) + Alembic for ORM and Migrations | Accepted |
| [014](ADR-014-schema-validation.md) | pandera for Dataset Schema/Data Validation | Accepted |
| [015](ADR-015-continuous-training-optuna.md) | Continuous Training Pipeline with Optuna Hyperparameter Optimization | Accepted |
| [016](ADR-016-ml-monitoring-alerting.md) | ML Monitoring & Alerting Stack (Prometheus + Grafana) | Accepted |
| [017](ADR-017-advanced-rag-retrieval.md) | Advanced Multi-Stage RAG Retrieval Pipeline | Accepted |
| [018](ADR-018-mimic-iii-data-source.md) | MIMIC-III as Clinical Training Data Source | Accepted |
| [019](ADR-019-ab-testing-rollout.md) | A/B Testing & Progressive Model Rollout Framework | Accepted |
| [020](ADR-020-frontend-ui-component-libraries.md) | Frontend UI Component & Animation Library Stack | Accepted |
| [021](ADR-021-knowledge-aware-rag.md) | Knowledge-Aware RAG Architecture and PostgreSQL Graph Store | Accepted |
| [022](ADR-022-llm-provider.md) | Anthropic Claude as LLM Provider | Accepted |
