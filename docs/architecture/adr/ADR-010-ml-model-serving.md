# ADR-010 — ML Model Training, Registry, and Serving Strategy

## Status

Proposed

## Context

The Machine Learning Engine module requires training disease-risk and readmission-prediction models, comparing multiple models against each other, serving predictions through the API, and maintaining a history of past predictions. This needs a clear separation between the (slow, offline) training process and the (fast, online) serving process, plus a way to track which model version is currently live and how it compares to earlier versions.

## Decision

- Models are trained using **scikit-learn** and **XGBoost**.
- **MLflow** is adopted as the experiment tracking and model registry layer: every training run logs parameters, metrics (ROC-AUC, precision, recall, per the targets in `00_PROJECT_SCOPE.md`), and the resulting model artifact; the registry tracks model stage (`Staging` / `Production` / `Archived`).
- Training runs execute as **background jobs** (Celery + Redis) rather than inline within an API request, since training is long-running and must not block the FastAPI event loop.
- The prediction API loads whichever model is currently tagged `Production` in the MLflow registry and serves inference synchronously, since inference itself is fast.
- Prediction requests and their outputs are persisted to PostgreSQL (`predictions` table, referencing the `dataset_version_id` and the MLflow `run_id`) to support the "Prediction History" requirement.

## Alternatives Considered

- BentoML
- Seldon Core / KServe
- Ray Serve
- Manually versioned pickle files with no registry

## Consequences

### Positive

- Gives the "Model Comparison" feature real backing data (logged metrics per run) instead of a hand-rolled comparison table — a concrete, demonstrable MLOps artifact for interviews.
- Clean separation of training (offline, background job) from serving (online, API), keeping the FastAPI service responsive.
- Fits inside the existing Modular Monolith (ADR-008) without requiring a separate model-serving microservice at this stage.
- Full reproducibility: every prediction can be traced to a model run, and every model run to a dataset version (ADR-009).

### Negative

- Introduces two new infrastructure pieces to containerize: an MLflow tracking server (with a Postgres or SQLite backend and an artifact store) and a Celery + Redis worker/broker pair — additional services in `docker-compose.yml`.
- Adds operational surface area (queue monitoring, worker health) that a purely synchronous API would not have.
- Requires the team (in this case, a single developer) to learn MLflow's registry API and Celery's task lifecycle in addition to the existing stack.

## References

- `docs/00_PROJECT_SCOPE.md` — Machine Learning functional requirements and ML success metrics
- ADR-008 — Modular Monolith architecture
- ADR-009 — Dataset versioning strategy
- TRD Section 17 — AI Architecture (to be updated with training/serving pipeline)
