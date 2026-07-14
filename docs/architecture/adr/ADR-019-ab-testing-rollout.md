# ADR-019 — A/B Testing & Progressive Model Rollout Framework

## Status

Accepted

## Context

ADR-010 gives every model version a `Staging`/`Production`/`Archived` stage
in the MLflow registry, and ADR-015 can now produce new candidate versions
automatically (scheduled or drift-triggered retraining). Neither ADR defines
how a `Staging` model earns promotion to `Production` — today that would be
a manual, ungoverned decision. The platform vision requires a real
promotion gate: route a fraction of traffic to the candidate, compare it
against the incumbent statistically, and only promote if it's genuinely
better.

## Decision

- **Traffic routing**: a lightweight in-process router (no separate
  feature-flag service) reads a `rollout_percentage` field from the
  registry stage metadata and assigns each inference request to
  `candidate` or `incumbent` via a deterministic hash of the request's
  patient/session id, so a given patient consistently sees the same model
  version across repeated calls within one rollout.
- **Metrics per cohort**: every prediction is already logged to
  `PredictionLog` (per `00_VISION_ML_PLATFORM.md`/`05_BACKEND_DESIGN.md`)
  tagged with the serving model version; the rollout job aggregates the
  primary success metric (ROC-AUC / calibrated precision-recall) plus the
  fairness metrics from ADR-016 **per cohort**, not just overall — a
  candidate that wins on aggregate but widens the fairness gap does not pass.
- **Statistical significance**: a two-proportion z-test (or bootstrap CI for
  continuous metrics) comparing candidate vs. incumbent, run by the same
  scheduled Celery job pattern used in ADR-015/ADR-016, not ad hoc.
- **Auto-promotion criteria**: promote candidate → `Production` (demote
  current incumbent → `Archived`) only if, over a minimum 7-day rollout
  window: the candidate's primary metric is better by > 2%, the result is
  statistically significant (p < 0.05), and no fairness metric has
  regressed beyond the ADR-016 alert threshold. Any one failing condition
  blocks auto-promotion; a blocked promotion is surfaced (per the project's
  report-only autonomy stance) rather than silently retried or overridden.
- **Rollback**: since every version remains registered and archived rather
  than deleted (ADR-010), reverting to a previous `Production` version is a
  registry stage change, not a redeploy — the router picks up the change on
  its next metadata read.

## Alternatives Considered

- **A dedicated feature-flag/experimentation platform (e.g. a hosted
  A/B-testing SaaS)** — more capable UI and analysis tooling, but is
  overkill for two models on a portfolio project, adds a paid dependency,
  and produces a black-box "promotion decision" instead of a pipeline the
  developer built and can explain end-to-end — the same trade-off ADR-009
  and ADR-016 already made against heavier managed tooling.
- **No statistical gate, promote whichever model MLflow shows the higher
  offline metric on** — simplest, but ignores the whole point of online
  A/B testing (offline validation metrics don't always hold under live
  traffic); does not match the "measurable impact, not vibes" principle in
  the platform vision.
- **Shadow deployment only (no live traffic to candidate)** — safer in that
  the candidate never affects a real user/patient outcome, but produces
  comparison metrics that are once-removed from real routing behaviour;
  rejected in favour of the cohort-split approach as the more standard,
  more demonstrable MLOps pattern, while still bounding blast radius via
  the `rollout_percentage` field (a rollout can start small, e.g. 5%,
  before widening).

## Consequences

### Positive

- Gives ADR-015's auto-produced candidates a real, principled gate before
  they can reach `Production` — closes the gap ADR-010/ADR-015 left open.
- Fairness is a first-class promotion criterion, not just a monitoring
  afterthought — a model cannot auto-promote by improving overall accuracy
  at a fairness cost, directly supporting the project's stated fairness
  principle.
- Full rollback is "just" a registry stage change because no version is
  ever deleted, keeping recovery fast and low-risk.

### Negative

- On a portfolio project with synthetic (or, per ADR-018, credentialed but
  still non-production) data and no real user base, "live traffic" is
  necessarily simulated/replayed rather than genuine production traffic —
  the framework's mechanics are real and demonstrable, but the *result* of
  any given rollout should be described as a validated methodology, not
  evidence about real-world patient outcomes. This mirrors the same caveat
  ADR-016 makes about fairness monitoring on synthetic data.
- Requires request-level logging discipline (every prediction tagged with
  serving model version) to hold everywhere inference happens; a missed
  tag silently corrupts a rollout's metrics rather than erroring loudly —
  worth an explicit test in `08_EVALUATION_FRAMEWORK.md`/testing strategy.
- Adds another scheduled job type to operate and monitor (ADR-016 covers
  the "is this job still running" concern, but the rollout logic itself is
  new surface area to get right, particularly the deterministic hashing
  for consistent per-patient assignment).

## References

- ADR-009 — Dataset Versioning Strategy
- ADR-010 — ML Model Training, Registry, and Serving Strategy
- ADR-015 — Continuous Training Pipeline with Optuna
- ADR-016 — ML Monitoring & Alerting Stack
- `docs/00_VISION_ML_PLATFORM.md` — MLOps Infrastructure §A/B testing framework
- `docs/08_EVALUATION_FRAMEWORK.md` — fairness metric definitions (to be written)
