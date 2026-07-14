# 07_ML_OPS.md — MLOps Infrastructure

**Project:** MedIntel AI
**Version:** v1.0
**Status:** Active
**Related:** `06_ML_MODELS.md`, `00_VISION_ML_PLATFORM.md`, ADR-010, ADR-015, ADR-016, ADR-019

---

# 1. Purpose & Scope

This document specifies the shared MLOps machinery all three models
(`06_ML_MODELS.md`) run on: experiment tracking, model registry lifecycle,
continuous training and hyperparameter optimization, monitoring/alerting,
A/B rollout governance, and cost tracking. Model-specific detail
(hyperparameter search spaces, evaluation targets) lives in
`06_ML_MODELS.md`; this document owns the *mechanism*, not the per-model
numbers.

---

# 2. Experiment Tracking (MLflow, ADR-010)

## 2.1 Tracking Server

Self-hosted MLflow tracking server (Docker service, `02_TRD.md` §18),
backed by PostgreSQL for run metadata and the existing object storage
(ADR-009's pattern) for artifacts — no new storage technology introduced,
consistent with the project's "don't add infrastructure without a clear
need" discipline (same reasoning as ADR-009's rejection of DVC/LakeFS).

## 2.2 Run Hierarchy

- **Parent run** = one Optuna study (one model, one training invocation —
  manual, scheduled, or drift-triggered).
- **Nested runs** = individual Optuna trials, each logging its
  hyperparameters and validation metric.
- **Tags** applied to every run: `dataset_version_id`, `trigger_source`
  (`manual`/`scheduled`/`drift`/`degradation`), `model_name`, `git_commit`
  (so a run is traceable to the exact code that produced it, not just the
  data).

## 2.3 What Gets Logged

| Category | Examples |
|---|---|
| Parameters | All Optuna-searched hyperparameters (`06_ML_MODELS.md` per-model tables) |
| Metrics | Primary metric (ROC-AUC / precision-recall / NDCG per model), secondary metrics (calibration error, fairness gap per group), training time, trial count |
| Artifacts | Serialized model, a fixed evaluation report (confusion matrix / calibration plot / retrieval metric breakdown), the SHAP background sample used for global summaries (Models 1–2) |
| Cost | Wall-clock training time and, where applicable, LLM/embedding API calls consumed (Model 3's cross-encoder fine-tuning may call an embedding API) — feeds §6 |

## 2.4 Registry Lifecycle

Stages: `Staging` → `Production` → `Archived`. No version is ever deleted —
only archived — so rollback is always available as a stage change
(ADR-010/019). Promotion `Staging` → `Production` is **never** direct; it
only happens through the A/B rollout gate (§5). Demotion `Production` →
`Archived` happens automatically when a new version is promoted in its
place, or manually if a live model is pulled for cause (e.g. an
unanticipated fairness regression caught outside the normal monitoring
window).

---

# 3. Continuous Training Pipeline (ADR-015)

## 3.1 Trigger Types

| Trigger | Mechanism | Notes |
|---|---|---|
| Scheduled | Celery beat, weekly | Runs against whatever `dataset_version_id` is current for `Production` |
| Data drift | KS-test result from a monitoring sweep (§4) exceeding threshold | Same job type as scheduled — no special-cased "drift retraining" code path |
| Performance degradation | Rolling evaluation (§5) showing primary metric down >3% from registered baseline | Same job type |
| Manual | API call / admin action | Same job type — manual runs are not a different code path either |

**All four enter the same Celery job.** This is a deliberate architectural
choice (ADR-015): one training pipeline, tested once, behaves identically
regardless of what triggered it.

## 3.2 Job Steps

1. Resolve the target `dataset_version_id` (current `Production` data
   version, or an explicitly specified one for manual runs).
2. Load and validate data (pandera, ADR-014) — a retraining run is not
   exempt from the same validation a fresh upload gets.
3. Feature engineering (per model, `06_ML_MODELS.md`), versioned against
   the resolved dataset version.
4. Optuna study (parent MLflow run) launches N trials (nested runs); each
   trial trains, evaluates on a held-out validation split, logs metrics.
5. Best trial's model registers to MLflow `Staging`.
6. Admin notified (Slack/email, §4.4) that a new `Staging` candidate exists
   — this is where §5 (A/B rollout) picks up; §3 stops here.

## 3.3 Failure Handling

A failed trial does not fail the whole study (Optuna handles this
natively — a trial that errors is recorded as failed and excluded from the
best-trial selection). A failed *study* (e.g. the underlying data load
step fails) surfaces as a Celery task failure, logged and alertable (§4)
— it does not fail silently, and it does not leave a half-registered model
in `Staging`.

## 3.4 Operational Risk

Celery beat is a new always-on scheduling component (ADR-015's own
Negative consequence) — if it stops, retraining stops with it, silently,
unless monitored. §4.3 covers this explicitly: a missing expected
training run is itself an alertable condition, not just model-quality
metrics.

---

# 4. Monitoring & Alerting Architecture (ADR-016)

## 4.1 Metrics Collection

- **System metrics**: FastAPI via `prometheus-fastapi-instrumentator`
  (request latency/count/error-rate per route). Celery worker/beat metrics
  (job duration, failure count, queue depth) via a Celery-Prometheus
  exporter.
- **Model metrics** (pushed from inference and monitoring-job code, not
  scraped): prediction distribution (histogram per model), feature
  distribution (per input feature, for drift comparison), fairness gap per
  protected attribute (gauge, labelled by group).

## 4.2 Drift Detection Jobs

Celery beat scheduled job (same scheduling mechanism as §3), per
`Production` model:

1. Pull a recent window of inference inputs/outputs from `PredictionLog`.
2. **Data drift**: Kolmogorov–Smirnov test per input feature against the
   training-time feature distribution (stored as a reference snapshot at
   training time, not recomputed from scratch each sweep).
3. **Model drift**: Wasserstein distance between the recent prediction
   distribution and the training-time prediction distribution.
4. **Fairness**: equalized odds / demographic parity / predictive parity
   per protected attribute, computed over the same recent window.
5. Write results to Prometheus (for alerting/dashboards, §4.4/§4.5) **and**
   to `ModelMonitoringSnapshot` (`05_BACKEND_DESIGN.md` §5) for historical,
   queryable audit trail — consistent with the project's
   audit-everything stance (ADR-009/#31).

## 4.3 What Counts as "Missing," Not Just "Bad"

Alertable conditions include the *absence* of an expected signal, not only
a bad value: no monitoring snapshot in the expected window (drift job
didn't run), no training run in the expected weekly window (beat schedule
silently stopped), a `Staging` candidate sitting unreviewed past a
reasonable window (rollout stalled). This is what closes the "Celery beat
silently stops and nobody notices" risk from §3.4 and ADR-015.

## 4.4 Alerting

Prometheus Alertmanager rules, routed to Slack/email — **explicitly not a
paging service**; there is no real on-call rotation on a portfolio
project, and this document (and any demo of it) says so rather than
implying a production pager exists.

| Condition | Threshold |
|---|---|
| API latency (p95) | >300ms warning, >5s critical |
| Error rate | >5% |
| Model primary metric drop | >5% from registered baseline |
| Fairness gap | >5% between any two groups |
| Data/model drift | KS-test / Wasserstein statistic over configured threshold (per-model, set during that model's first monitoring baseline) |
| Missing expected signal | No training run / monitoring snapshot in the expected window (§4.3) |

## 4.5 Dashboards (Grafana)

Provisioned as code, checked into `infrastructure/grafana/`:

- **System health**: latency, error rate, throughput, per route.
- **Model performance trends**: primary metric over time, per model, per
  registry stage.
- **Fairness trends**: fairness gap over time, per model, per protected
  attribute group.
- **Cost tracking** (§6): LLM tokens, API calls, compute time per
  prediction, aggregated daily.
- **Data quality**: pandera validation pass/fail rate, drift statistic
  trend.

## 4.6 The Caveat That Travels With Every Dashboard

Drift and fairness numbers computed against synthetic or MIMIC-III
research-only data demonstrate the **methodology**, not a validated
real-world safety or fairness claim about any live clinical deployment.
This is stated once here in full and referenced (not silently dropped)
everywhere these dashboards are shown, demoed, or exported (§4.5,
`08_EVALUATION_FRAMEWORK.md`, `11_PRIVACY_COMPLIANCE.md`).

---

# 5. A/B Testing & Progressive Rollout (ADR-019)

## 5.1 Routing

In-process router; each inference request hashes to `candidate` or
`incumbent` deterministically by patient/session id, so a given patient
sees a consistent model version across repeated calls within one rollout
window. `rollout_percentage` lives on the `ModelVersion` row (§2.4) and
starts small (default 5%), widened manually by an Admin reviewing early
results — auto-widening is explicitly not implemented; only the
**promotion** decision is automatic (per the gate below), widening
mid-rollout is a human call.

## 5.2 Cohort Metrics

Aggregated from `PredictionLog` (tagged with `rollout_cohort` and
`model_version_id`, `05_BACKEND_DESIGN.md` §5): primary metric and
fairness metrics (§4.2) computed **per cohort**, not just overall — a
candidate that wins in aggregate but widens the fairness gap fails the
gate regardless of the aggregate win.

## 5.3 Statistical Test

Two-proportion z-test (classification primary metrics) or bootstrap
confidence interval (continuous metrics, e.g. Model 2's recovery-time
regression) comparing candidate vs. incumbent, run by the same Celery beat
scheduling pattern as §3/§4.

## 5.4 Auto-Promotion Gate

Promote `Staging` (candidate) → `Production`, demote current `Production`
→ `Archived`, only if **all** hold over a minimum 7-day window:

1. Primary metric better by > 2%.
2. Statistically significant (p < 0.05).
3. No fairness metric regressed past the §4.4 alert threshold.

Any single failing condition **blocks** promotion — this is surfaced to
Admin as an explicit decision point (report-only autonomy, consistent with
the project's workflow rules), not silently retried or force-promoted.

## 5.5 What Admin Sees on a Blocked Promotion

A blocked promotion isn't a dead end presented as one — the surfaced
decision includes: which condition(s) failed, current cohort metrics
side-by-side, and options (extend the rollout window if underpowered,
adjust `rollout_percentage`, or archive the candidate and return to §3).

## 5.6 Simulated vs. Real Traffic

On a portfolio project with no real users, "live traffic" for a rollout is
necessarily simulated or replayed (historical requests, synthetic request
generation — the concrete mechanism is an open question, `01_PRD.md` §12).
The rollout **mechanism** (routing, statistical test, gate) is real and
demonstrable regardless; the **result** of any given rollout should be
described as validating the mechanism, not as a real-world outcome claim
— same caveat as §4.6.

---

# 6. Cost Tracking

- **LLM/API cost**: tokens consumed per RAG query (Model 3, all 7 stages
  where an LLM or embedding API is called), tracked per request and
  aggregated to a daily Grafana panel (§4.5).
- **Compute cost**: training job wall-clock time (per Optuna study),
  monitoring sweep wall-clock time — informative for a student-budget
  project where "how much does a retrain cost" is a real, not rhetorical,
  question (`00_PROJECT_SCOPE.md` §Constraints).
- **No paid cost-tracking SaaS** — this is computed from data already
  logged (MLflow run duration, Prometheus request counters), not a new
  integration, consistent with the project's self-hosted-over-managed
  stance elsewhere (ADR-016 §Alternatives).

---

# 7. Open Implementation Questions

- Exact Optuna trial budget per model per retraining run — a real
  time/cost tradeoff to tune once real training wall-clock time on actual
  hardware is known, not a number to fix speculatively now.
- Whether `rollout_percentage` widening should ever be semi-automated
  (e.g. auto-widen from 5% to 20% after an early positive signal, before
  the full 7-day gate) — deliberately left manual for the first
  implementation (§5.1); revisit only with real operating experience.
- Concrete mechanism for simulated rollout traffic (§5.6) — tracked as the
  same open question in `01_PRD.md` §12, not duplicated here as a separate
  decision.

---

## Document Information

**Version History:**
- v1.0 — Initial MLOps infrastructure specification (current)

## End of Document
