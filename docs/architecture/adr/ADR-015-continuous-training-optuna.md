# ADR-015 — Continuous Training Pipeline with Optuna Hyperparameter Optimization

## Status

Accepted

## Context

ADR-010 established MLflow (experiment tracking/registry) and Celery + Redis
(background training jobs) for the ML Engine, but scoped a single manual
training run per model iteration. The expanded platform vision
(`docs/00_VISION_ML_PLATFORM.md`, adopted 2026-07-14) requires the risk and
treatment-outcome models to stay current as data grows and to be tuned
systematically rather than by hand, with retraining triggered automatically
rather than only on developer initiative.

This needs two decisions ADR-010 left open: how hyperparameters get chosen,
and what triggers a new training run.

## Decision

- **Optuna** is adopted for hyperparameter optimization, run as part of the
  same Celery background job type ADR-010 already defines (training remains
  off the request path).
  - Each Optuna study is itself an MLflow parent run; each trial logs as a
    nested MLflow run (params + validation metric), so the existing registry
    UI shows the full search, not just the winning trial.
  - Search space and number of trials are defined per model in
    `07_ML_OPS.md`; the objective is the primary success metric from
    `00_PROJECT_SCOPE.md` (ROC-AUC for the risk model, calibrated
    precision/recall for the outcome model).
  - The best trial's model artifact is registered to MLflow's `Staging`
    stage automatically; promotion to `Production` still requires the
    evaluation gate from ADR-019/`08_EVALUATION_FRAMEWORK.md`, not an
    automatic Optuna decision.
- **Retraining triggers**, evaluated by a scheduled Celery beat task (not a
  human clicking "retrain"):
  1. **Schedule**: weekly, against the current `Production` dataset version.
  2. **Data drift**: Kolmogorov–Smirnov test on input feature distributions
     vs. the training snapshot (detail in ADR-016) exceeding a configured
     threshold.
  3. **Performance degradation**: rolling evaluation (ADR-019) showing the
     live model's primary metric down more than 3% from its
     registered baseline.
  - Any of the three enqueues the same training+Optuna job used for manual
    runs — there is one training pipeline, not a separate "auto" path, so
    behaviour under automation matches behaviour under a manual run.

## Alternatives Considered

- **Ray Tune** — capable HPO framework, but pulls in Ray's distributed
  runtime as a dependency; Optuna's single-process, library-only footprint
  fits the project's existing modular-monolith / single-developer scale
  (ADR-008) without adding a cluster to operate.
- **Manual grid search** — simplest to implement, but does not scale to two
  models' worth of tuning and produces no reusable record of what was tried;
  loses the "systematic, not vibes-based" tuning that's part of the
  production-grade mandate.
- **Fully event-driven retraining (retrain on every new upload)** — rejected
  as wasteful and noisy for a project at this data volume; the
  weekly-or-drift-triggered schedule matches how real clinical ML pipelines
  are actually operated (retraining on every row is not standard practice
  even in industry).

## Consequences

### Positive

- One coherent training pipeline (manual, scheduled, and drift-triggered
  runs all go through the same Celery job + Optuna study + MLflow logging),
  keeping ADR-010's architecture intact rather than bolting on a parallel system.
- Every model version is now backed by a real, loggable hyperparameter
  search — a concrete, interview-defensible MLOps artifact, not a
  hand-picked config.
- Automatic triggers demonstrate the "continuous" half of continuous
  training without requiring a human in the loop for routine retraining.

### Negative

- Adds Optuna as a new dependency and a nested-run logging convention that
  must be learned and kept consistent across both prediction models.
- Automatic promotion to `Staging` (not `Production`) still means a human or
  the evaluation gate (ADR-019) must sign off before a new model actually
  serves traffic — this ADR does not by itself prevent a bad model reaching
  users; that safety property lives in ADR-019.
- Celery beat becomes a new always-on scheduling component; if it silently
  stops, retraining silently stops with it — needs a monitoring check
  (ADR-016) rather than being assumed to "just work."

## References

- ADR-008 — Modular Monolith architecture
- ADR-010 — ML Model Training, Registry, and Serving Strategy
- ADR-016 — ML Monitoring & Alerting Stack
- ADR-019 — A/B Testing & Progressive Model Rollout Framework
- `docs/00_VISION_ML_PLATFORM.md` — MLOps Infrastructure §Continuous training pipeline
- `docs/00_PROJECT_SCOPE.md` — per-model success metrics
