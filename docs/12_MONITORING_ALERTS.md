# 12_MONITORING_ALERTS.md — Monitoring, Dashboards & Alerting Specification

**Project:** MedIntel AI
**Version:** v1.0
**Status:** Active
**Related:** `07_ML_OPS.md` §4, ADR-016, `02_TRD.md` §10, §18

---

# 1. Purpose & Scope

`07_ML_OPS.md` §4 and ADR-016 establish *that* Prometheus/Grafana/
Alertmanager are the monitoring stack and *why*. This document is the
concrete specification: metric names and types, dashboard panel layouts,
alert rule definitions, and an honest statement of what "on-call" means
for a portfolio project with no real rotation.

---

# 2. Prometheus Metrics Collection

## 2.1 System Metrics (via `prometheus-fastapi-instrumentator`)

| Metric | Type | Labels |
|---|---|---|
| `http_request_duration_seconds` | Histogram | `method`, `path`, `status_code` |
| `http_requests_total` | Counter | `method`, `path`, `status_code` |
| `http_requests_in_progress` | Gauge | `method`, `path` |

## 2.2 Celery/Job Metrics

| Metric | Type | Labels |
|---|---|---|
| `celery_task_duration_seconds` | Histogram | `task_name`, `status` |
| `celery_task_total` | Counter | `task_name`, `status` (`success`/`failure`) |
| `celery_queue_depth` | Gauge | `queue_name` |
| `celery_beat_last_run_timestamp` | Gauge | `task_name` — powers the "missing expected run" alert class (`07_ML_OPS.md` §4.3), since a stalled beat schedule shows up as this gauge going stale, not just as an absence of other signals |

## 2.3 Model-Specific Metrics (pushed from application code)

| Metric | Type | Labels |
|---|---|---|
| `model_prediction_total` | Counter | `model_name`, `model_version`, `rollout_cohort` |
| `model_prediction_value` | Histogram | `model_name`, `model_version` — prediction distribution, feeds model-drift comparison |
| `model_feature_value` | Histogram | `model_name`, `feature_name` — per-feature distribution, feeds data-drift comparison |
| `model_data_drift_statistic` | Gauge | `model_name`, `feature_name` — latest KS-test statistic |
| `model_drift_statistic` | Gauge | `model_name` — latest Wasserstein distance |
| `model_fairness_gap` | Gauge | `model_name`, `metric` (`equalized_odds`/`demographic_parity`/`predictive_parity`), `group_a`, `group_b` |
| `model_primary_metric` | Gauge | `model_name`, `model_version`, `stage` — latest evaluated primary metric (ROC-AUC / precision-recall / NDCG per `06_ML_MODELS.md`) |
| `rollout_significance_pvalue` | Gauge | `model_name`, `candidate_version` — latest A/B test result (ADR-019) |
| `llm_tokens_total` | Counter | `provider`, `purpose` (`rag_query`/`explanation`/`summary`) — feeds cost tracking (`07_ML_OPS.md` §6) |

## 2.4 Retention

Prometheus's own local retention is sufficient for dashboards/alerting
(recent-window queries); longer-term historical trend data relies on
`ModelMonitoringSnapshot` (`05_BACKEND_DESIGN.md` §5) in PostgreSQL, not on
extending Prometheus retention indefinitely — consistent with using
Prometheus for what it's good at (recent time-series + alerting) rather
than as a long-term audit store, which is what the database table is for.

---

# 3. Grafana Dashboards

## 3.1 System Health Dashboard

Panels: request latency (p50/p95/p99) by route, error rate by route,
throughput (requests/sec), Celery queue depth, Celery task failure rate.
Audience: whoever is actively developing/debugging the platform.

## 3.2 Model Performance Dashboard

Panels: primary metric over time per model per stage
(`Staging`/`Production`), calibration summary (latest evaluation run's
reliability diagram, rendered as an image panel refreshed by the
evaluation pipeline, `08_EVALUATION_FRAMEWORK.md` §6), rollout
significance p-value trend per active A/B test. Audience: whoever is
reviewing whether a candidate model should be promoted.

## 3.3 Fairness Dashboard

Panels: `model_fairness_gap` trend per model per protected-attribute
group pair, with the 5% alert threshold rendered as a reference line on
every panel so a viewer never has to remember the threshold separately —
the panel itself makes "is this okay" visually obvious. Audience:
anyone reviewing an A/B promotion decision (ADR-019) or preparing an
interview walkthrough of the platform's fairness story.

## 3.4 Cost Dashboard

Panels: `llm_tokens_total` by provider/purpose (daily), Celery job
wall-clock time by task type (training/monitoring/evaluation), a rough
daily-cost-estimate panel (tokens × provider's published per-token rate,
computed in Grafana via a transform, not a separate billing integration).

## 3.5 Data Quality Dashboard

Panels: pandera validation pass/fail rate over time (`09_DATA_PIPELINE.md`
§5), `model_data_drift_statistic` trend per model per feature, count of
`MedicalRecord` extractions below the confidence threshold awaiting review
(`10_PATIENT_MANAGEMENT.md` §3.3).

## 3.6 Provisioning

All dashboards defined as JSON, checked into `infrastructure/grafana/`,
loaded via Grafana's provisioning config at container startup — dashboards
are version-controlled artifacts, not manually clicked together and
therefore undocumented/unreproducible.

---

# 4. Alert Rules

Defined as Prometheus Alertmanager rules (checked into
`infrastructure/prometheus/alerts.yml`), routed to a Slack webhook and/or
email (§5) — not a paging service.

| Alert | Condition | Severity |
|---|---|---|
| `HighAPILatency` | `http_request_duration_seconds` p95 > 0.3s for 5m | Warning |
| `CriticalAPILatency` | p95 > 5s for 2m | Critical |
| `HighErrorRate` | error rate > 5% over 5m, any route | Critical |
| `ModelPerformanceDrop` | `model_primary_metric` down > 5% vs. registered baseline | Critical |
| `FairnessGapExceeded` | `model_fairness_gap` > 5% for any group pair | Critical |
| `DataDriftDetected` | `model_data_drift_statistic` over the model's calibrated threshold | Warning |
| `ModelDriftDetected` | `model_drift_statistic` over the model's calibrated threshold | Warning |
| `MissingScheduledTraining` | `celery_beat_last_run_timestamp{task_name="continuous_training"}` stale beyond 8 days (schedule is weekly, `07_ML_OPS.md` §3.1) | Warning |
| `MissingMonitoringSweep` | `celery_beat_last_run_timestamp{task_name="drift_monitoring"}` stale beyond expected sweep interval | Warning |
| `RolloutStalled` | A `Staging` candidate has an active rollout with no promotion decision after 14 days (7-day minimum window, `07_ML_OPS.md` §5.4, doubled as a "someone should look at this" threshold) | Warning |

Per-model drift thresholds (`DataDriftDetected`/`ModelDriftDetected`) are
calibrated individually at each model's first monitoring baseline
(`07_ML_OPS.md` §4.2) rather than a single global constant — a threshold
that's meaningful for Model 1's feature distributions isn't necessarily
meaningful for Model 2's.

---

# 5. On-Call Escalation — Honest Scope

**There is no real on-call rotation on this project.** "Alerting" means
Alertmanager routing to a Slack channel and/or email — a human (Som)
checks it when available, not a paged responder with an SLA. This is
stated plainly here (and should be stated plainly in any demo or interview
discussion of this monitoring stack) rather than described in
page-on-call language that would overclaim operational maturity the
project doesn't have. What a **real** on-call setup would add on top of
this architecture: a paging integration (PagerDuty/Opsgenie) subscribed to
the same Alertmanager rules, a documented escalation policy (who's paged,
after how long unacknowledged, escalate to whom), and defined incident
severity levels — all straightforward additions to this architecture, not
requiring it to be rebuilt, but not implemented now because there's no one
to page.

---

# 6. Runbook Pointers

Brief first-response guidance per alert class (a full runbook is future
work, not written here in full to avoid documenting response procedures
for a system that doesn't have real on-call staff to execute them yet):

| Alert | First check |
|---|---|
| `HighAPILatency`/`CriticalAPILatency` | Which route; check `07_ML_OPS.md` §4.1's per-route breakdown; if it's the RAG endpoint, check whether the full 7-stage retrieval path is running (ADR-017's latency risk) |
| `ModelPerformanceDrop`/Fairness/Drift alerts | Check the model's `ModelMonitoringSnapshot` history (`05_BACKEND_DESIGN.md` §5) for a trend vs. a step-change (a trend suggests real drift; a step-change suggests a recent deploy or data issue) |
| `MissingScheduledTraining`/`MissingMonitoringSweep` | Check Celery beat process health directly — this alert class exists precisely because the absence of downstream signals wouldn't otherwise be noticed (`07_ML_OPS.md` §3.4) |
| `RolloutStalled` | Check `07_ML_OPS.md` §5.5 — likely blocked on an unreviewed gate failure, not a system fault |

---

# 7. Open Implementation Questions

- Concrete per-model drift thresholds (§4) — require a real monitoring
  baseline from each model's first production period; not set
  speculatively here.
- Whether Slack or email is the primary alert channel (or both) — a
  configuration detail, not an architectural one; deferred to
  implementation.
- Whether `infrastructure/grafana/` dashboard JSON is hand-written or
  generated from a higher-level dashboard-as-code tool (e.g. Grafonnet) —
  hand-written is sufficient at this project's dashboard count; revisit
  only if the dashboard count grows enough to make hand-maintenance
  genuinely painful.

---

## Document Information

**Version History:**
- v1.0 — Initial monitoring, dashboards, and alerting specification (current)

## End of Document
