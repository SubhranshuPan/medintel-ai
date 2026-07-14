# ADR-016 — ML Monitoring & Alerting Stack (Prometheus + Grafana)

## Status

Accepted

## Context

Nothing in ADR-001–ADR-013 covers observability once a model is serving
traffic: ADR-010 defines training/serving but not what happens after a model
is `Production` — whether its inputs are drifting, whether its predictions
are still accurate, or whether it treats demographic groups unequally. The
platform vision (`docs/00_VISION_ML_PLATFORM.md`) requires this as a
first-class capability, not an afterthought, and ADR-015's automatic
retraining triggers (data drift, performance degradation) depend on this
monitoring layer existing and being queryable.

This also covers general system observability (API/DB/retrieval latency,
error rates) — not just ML-specific signals — since both are naturally
served by the same metrics stack.

## Decision

**Prometheus** for metrics collection and **Grafana** for dashboards,
alongside the existing stack (FastAPI, Celery, PostgreSQL, Qdrant).

- **Instrumentation**: FastAPI exposes a `/metrics` endpoint via
  `prometheus-fastapi-instrumentator` (request latency/count/error-rate per
  route, out of the box). Celery workers export job duration/failure counts
  via `celery-prometheus-exporter`-style instrumentation. Model-specific
  metrics (prediction distribution, feature distribution, drift statistics)
  are pushed from the inference and monitoring-job code as custom
  Prometheus gauges/histograms, not scraped indirectly.
- **Drift detection jobs** (Celery beat, same scheduling mechanism as
  ADR-015): Kolmogorov–Smirnov test per feature for data drift, Wasserstein
  distance on the prediction distribution for model drift. Results are
  written both to Prometheus (for alerting/dashboards) and to a
  `model_monitoring_snapshots` table in PostgreSQL (for historical audit,
  consistent with the project's audit-everything stance from ADR-009/#31).
- **Fairness monitoring**: the same scheduled job computes equalized odds /
  demographic parity / predictive parity (ADR-019/`08_EVALUATION_FRAMEWORK.md`
  define the metrics) per protected attribute available in the (synthetic)
  patient data, exported as labelled Prometheus gauges (`fairness_gap{group=...}`)
  so Grafana can chart the gap over time per group.
- **Alerting**: Prometheus Alertmanager rules for the explicit thresholds
  already set in the vision doc — API p95 latency > 300ms/5s (warning/page),
  error rate > 5%, model metric drop > 5%, fairness gap > 5%, data/model
  drift over threshold. Routes to Slack/email webhook (no paging service is
  provisioned for a portfolio project with no real on-call rotation —
  see Negative consequences).
- **Dashboards** (Grafana, provisioned as code — JSON dashboards checked
  into `infrastructure/grafana/`): system health, model performance trends,
  fairness trends, cost tracking (LLM tokens/API calls/GPU time), data
  quality. Detailed dashboard/panel spec lives in `12_MONITORING_ALERTS.md`.
- **Containerization**: Prometheus + Grafana + Alertmanager are added to
  `docker-compose.yml` as new services, consistent with how ADR-010 added
  MLflow/Celery/Redis.

## Alternatives Considered

- **Datadog / New Relic (hosted APM)** — far less setup effort, but a paid
  SaaS product; conflicts with the project's student budget constraint
  (same reasoning ADR-009 used against DVC/LakeFS) and produces a portfolio
  artifact tied to a vendor's dashboard rather than something the developer
  built and can explain end-to-end in an interview.
- **Evidently AI** (drift/fairness-specific library) — strong fit for the
  drift/fairness computation itself, and may still be used *inside* the
  monitoring jobs as the statistical engine; not a replacement for
  Prometheus/Grafana as the metrics/dashboard/alerting substrate, since it
  doesn't provide time-series storage or alerting on its own.
- **No dedicated monitoring stack, log-based checks only** — cheapest, but
  gives no dashboards, no alerting, no time-series drift/fairness history —
  directly contradicts the "monitoring is not optional" principle in the
  platform vision and leaves ADR-015's automatic triggers with nothing to
  query.

## Consequences

### Positive

- Gives ADR-015's drift/performance retraining triggers a concrete,
  queryable data source instead of an ad-hoc check.
- Fairness and drift become time-series, dashboarded facts rather than
  one-off reports — directly demonstrable to interviewers as production
  ML-monitoring experience, which is a differentiator for NHS/health-tech
  roles.
- Reuses the same metrics stack for both general system observability and
  ML-specific signals, avoiding two parallel monitoring systems.

### Negative

- Three more services in `docker-compose.yml` (Prometheus, Grafana,
  Alertmanager) beyond ADR-010's additions — real operational surface for a
  single developer to keep healthy locally and in CI.
- Without a genuine on-call rotation, "alerting" here means Slack/email
  notification, not paging — the vision doc's "page on-call" language is
  aspirational for a portfolio project and should be described as such in
  `12_MONITORING_ALERTS.md`, not oversold as a live on-call system.
- Fairness/drift computations run against synthetic data; results demonstrate
  the *methodology* correctly but are not evidence of real-world model
  fairness — this caveat belongs in every doc/demo that shows these
  dashboards, per the project's GDPR-aware "treat synthetic data as real
  PHI" stance (it cuts the other way here: don't overclaim what synthetic
  fairness numbers prove).

## References

- ADR-009 — Dataset Versioning Strategy (audit-everything precedent)
- ADR-010 — ML Model Training, Registry, and Serving Strategy
- ADR-015 — Continuous Training Pipeline with Optuna
- ADR-019 — A/B Testing & Progressive Model Rollout Framework
- `docs/00_VISION_ML_PLATFORM.md` — MLOps Infrastructure §Monitoring & alerting
- `docs/12_MONITORING_ALERTS.md` — detailed metrics/dashboard/alert spec (to be written)
