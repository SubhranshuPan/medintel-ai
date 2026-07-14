# 06_ML_MODELS.md — Predictive & Retrieval Model Architecture

**Project:** MedIntel AI
**Version:** v1.0
**Status:** Active
**Related:** `00_VISION_ML_PLATFORM.md`, `02_TRD.md` §8–9, `05_BACKEND_DESIGN.md` §5,
ADR-010, ADR-011, ADR-015, ADR-017, ADR-018

---

# 1. Purpose & Scope

This document specifies the three models that make up the ML Engine and AI
Decision Support pillars: architecture, training data and pipeline,
hyperparameter search space, evaluation targets, explainability approach,
serving strategy, and monitoring hooks — for each model individually. The
*shared machinery* all three models sit on top of (MLflow registry, Optuna
infrastructure, Celery scheduling, Prometheus/Grafana, A/B rollout
mechanics) is specified once in `07_ML_OPS.md` and referenced here, not
duplicated per model.

**A note on what "three models" means here.** Models 1 and 2 are
conventional supervised learning problems over tabular clinical data.
Model 3 is not a classifier — it is the retrieval pipeline from ADR-017,
evaluated and monitored with the rigor of a model (versioned, benchmarked,
regression-tested) even though "training" for it means tuning a pipeline
and fine-tuning a re-ranker rather than fitting a single estimator. Listing
it alongside Models 1–2 is a deliberate statement: retrieval quality is not
"just RAG," it's a measured system component.

---

# 2. Model 1 — Patient Risk Stratification

## 2.1 Problem Framing

Given a patient's demographics, comorbidities, lab values, vital signs, and
medications, produce a 0–100 risk score for each of four conditions:
cardiac disease, diabetes, stroke, and cancer. This is framed as **four
related binary classification problems sharing a feature pipeline**, not
one multi-class problem — a patient can be high-risk for more than one
condition simultaneously, which a single multi-class model cannot express.

## 2.2 Inputs & Outputs

| | Detail |
|---|---|
| Input | Demographics (age, sex, BMI), comorbidities (structured list, e.g. from ICD-coded history), lab values (most recent + trend where available), vital signs, current medications |
| Output | Four risk scores (0–100), each with a SHAP-based explanation (§2.6) |
| Label source | MIMIC-III derived outcome labels (ADR-018) where credentialed access has landed; synthetic-data-derived labels as interim/CI fallback |
| Granularity | Per-patient, per-prediction-request — not a batch-only score |

## 2.3 Algorithm

**XGBoost**, one binary classifier per condition (four models sharing
feature engineering, registered as four related `ModelVersion` rows with a
shared `model_name` prefix, e.g. `risk_stratification.cardiac`). XGBoost
was chosen (over, say, logistic regression or a deep tabular model)
because: it handles the mixed categorical/continuous, missing-value-heavy
nature of clinical tabular data well without heavy preprocessing; it pairs
directly with SHAP's exact, fast `TreeExplainer` (ADR-011); and it's the
standard baseline in published clinical risk-prediction literature, which
matters for interview credibility (a reviewer can sanity-check the
approach against known work, e.g. comparisons to Framingham/CHADS2 per
`00_VISION_ML_PLATFORM.md`).

## 2.4 Feature Engineering

- **Comorbidity encoding**: multi-hot encoding over a fixed ICD-code-derived
  vocabulary, not raw free text.
- **Lab values**: most recent value plus a short trend feature (delta over
  the last N recorded values) where longitudinal data exists; missing labs
  are imputed with a clinically-reasonable default *and* flagged with a
  companion "was-missing" indicator column, so the model can learn that
  missingness itself may be informative (common in clinical ML — a lab not
  ordered is not the same as a lab that came back normal).
- **Vital signs**: latest reading; extreme-value flags (e.g. tachycardia
  threshold) as engineered binary features alongside the raw value, since
  tree models benefit from explicit threshold features even though they
  can in principle learn splits themselves.
- All engineered features are versioned against the source
  `dataset_version_id` per the lightweight feature store design
  (`02_TRD.md` §12) — a retrain against a new data version re-derives
  features rather than reusing a stale feature table.

## 2.5 Hyperparameter Search (Optuna, ADR-015)

| Parameter | Search space |
|---|---|
| `max_depth` | 3–10 |
| `learning_rate` | 0.01–0.3 (log scale) |
| `n_estimators` | 100–1000 |
| `subsample` | 0.5–1.0 |
| `colsample_bytree` | 0.5–1.0 |
| `min_child_weight` | 1–10 |
| `scale_pos_weight` | tuned per condition to address class imbalance (high-risk cases are the minority class for most conditions) |

Objective: validation ROC-AUC (primary), with precision/recall/calibration
logged as secondary metrics per trial for later gate evaluation (§2.7). 50
trials per condition per study is the default budget — enough for a
meaningful search without making a single retraining run prohibitively
slow on a single developer's hardware.

## 2.6 Explainability (SHAP, ADR-011)

- `TreeExplainer` (exact, fast for XGBoost) computes local SHAP values at
  prediction time; persisted in `PredictionLog.shap_values` and summarized
  in `RiskScore.top_risk_factors` (`05_BACKEND_DESIGN.md` §5).
- Global feature-importance summaries computed as a background job over a
  sampled background set (not per-request) for the dashboard's "what
  drives risk generally" view.
- The AI Decision Support module narrates these stored values in natural
  language (ADR-011) — it is never asked to explain a risk score from
  scratch.

## 2.7 Evaluation & Promotion Targets

Per `00_PROJECT_SCOPE.md`: ROC-AUC ≥ 0.85, Precision ≥ 0.80, Recall ≥ 0.80,
calibration assessed via a reliability diagram (not just Brier score in
isolation — a single scalar can hide a poorly calibrated model). Fairness:
equalized odds gap < 5% across available demographic groups (age band,
sex; race/ethnicity only if present and appropriately handled — see
`11_PRIVACY_COMPLIANCE.md`). These are the gate conditions referenced by
the A/B promotion process in `07_ML_OPS.md`/ADR-019, not a separate
standard.

## 2.8 Deployment & Serving

Synchronous FastAPI inference against whichever `ModelVersion` is
`production` for each condition (ADR-010); four conditions means four
independent registry entries and four independent A/B rollout tracks — a
new cardiac model can roll out without touching the diabetes model's
`production` stage.

## 2.9 Known Limitations

- Four independent per-condition models share feature engineering but not
  parameters — no multi-task learning is attempted; revisit only if
  per-condition sample sizes turn out too small individually (a real risk
  if MIMIC-III's cohort for a specific rare condition is small).
- Calibration across very different prevalence rates per condition (e.g.
  cancer risk in an ICU cohort vs. general population) needs explicit
  attention — MIMIC-III is an ICU population, which is not representative
  of the general population these risk scores would apply to in a real
  deployment; this is a real external-validity limitation to state plainly
  in any interview discussion of this model, not to gloss over.

---

# 3. Model 2 — Treatment Outcome Predictor

## 3.1 Problem Framing

Given a diagnosis, a proposed treatment, and a patient profile, predict:
success probability, expected recovery time, a confidence interval, likely
side effects, and a ranked list of alternative treatments. Framed as a
regression problem for recovery time and a calibrated binary/probabilistic
classification for success, sharing the same feature pipeline and served
together as one response.

## 3.2 Inputs & Outputs

| | Detail |
|---|---|
| Input | Diagnosis (coded), proposed treatment (coded), patient profile (as Model 1's feature set), similar historical cases (nearest-neighbor lookup over the training set, used both as a feature and as the source for "ranked alternatives") |
| Output | Success probability, expected recovery time (+ CI), possible side effects, ranked alternative treatments |
| Label source | Clinical trial outcome data + EHR outcome data (MIMIC-III procedure/outcome tables where applicable, ADR-018); synthetic fallback |

## 3.3 Algorithm

**Ensemble: Random Forest + Gradient Boosting**, combined via a simple
weighted average of calibrated probabilities (not a stacked meta-learner —
added complexity there isn't justified at this project's scale and would
complicate the SHAP story). Both base learners are tree-based, so
`TreeExplainer` applies to each and their SHAP contributions are combined
proportionally to the ensemble weights, keeping explainability consistent
with Model 1's approach rather than introducing a second explainability
method.

## 3.4 Feature Engineering

Shares Model 1's patient-profile features, plus: treatment encoding
(coded, not free text), a similarity feature derived from nearest-neighbor
distance to historical cases (informs both the confidence interval width
and the "ranked alternatives" output), and treatment-diagnosis interaction
features (a given treatment's typical response varies materially by
diagnosis, so these are modeled as explicit interaction terms rather than
left for the trees to discover from raw concatenation alone).

## 3.5 Hyperparameter Search (Optuna, ADR-015)

| Parameter | Search space |
|---|---|
| Random Forest `n_estimators` | 100–500 |
| Random Forest `max_depth` | 5–20 |
| Gradient Boosting `learning_rate` | 0.01–0.2 |
| Gradient Boosting `n_estimators` | 100–500 |
| Ensemble weight (RF vs. GB) | 0.3–0.7 (searched jointly with the above, not fixed a priori) |

Objective: a composite of validation precision/recall (primary) and
calibration error (secondary) — a model that's accurate on average but
badly calibrated at the individual-patient level fails this model's actual
purpose (helping a clinician weigh a specific patient's odds).

## 3.6 Explainability

Same `TreeExplainer`-based approach as Model 1 (§2.6), applied to each base
learner and combined; persisted the same way in `PredictionLog`/
`TreatmentOutcome` (`05_BACKEND_DESIGN.md` §5).

## 3.7 Evaluation & Promotion Targets

Precision > 0.80, Recall > 0.80 (per `00_PROJECT_SCOPE.md`), calibration
curve reviewed per release (not just a scalar target), fairness testing
identical in method to Model 1 (§2.7) — **ensuring similar success-rate
predictions across demographics is itself a named requirement** here, not
an afterthought, since a biased treatment-outcome model has more direct
potential for harm than a biased general risk score.

## 3.8 Deployment & Serving

Same synchronous FastAPI pattern as Model 1; the "ranked alternatives"
output additionally requires a fast nearest-neighbor lookup at inference
time (approximate nearest neighbor over the training feature space,
re-indexed whenever the model retrains) — this is new serving-path
complexity beyond Model 1's, and should be load-tested against the <2s
inference target, not assumed free.

## 3.9 Known Limitations

- "Similar historical cases" quality depends entirely on training-set
  coverage of the specific diagnosis-treatment pair being queried; sparse
  combinations produce wide, honestly-uncertain outputs rather than
  confident wrong ones (§3.2's edge case in `03_APP_FLOW.md` §10).
- Ensemble weighting is fixed per registered `ModelVersion`, not adaptive
  per-query — a future iteration could weight per-patient-segment if
  evaluation data shows one base learner outperforms the other on
  specific subpopulations.

---

# 4. Model 3 — Literature Relevance Ranker

## 4.1 Problem Framing

Not a classifier — the 7-stage retrieval pipeline from ADR-017, evaluated
and versioned as a ranking model. "Training" here means: fitting/
fine-tuning the cross-encoder re-ranker (stage 5) on relevance judgments,
and tuning fusion weights (stage 4) and temporal-decay parameters (stage
7) — the earlier stages (ColBERT, BM25) use pretrained/off-the-shelf
components rather than being trained from scratch on this project's data,
which does not have the scale to train a retrieval encoder from zero.

## 4.2 Inputs & Outputs

| | Detail |
|---|---|
| Input | A natural-language clinical question |
| Output | A ranked list of supporting literature passages with citations, each passage's contribution visible in the final ranking (not a black-box single relevance number) |
| Training/tuning data | Annotated queries with expert relevance judgments (target: 500+ queries, `00_VISION_ML_PLATFORM.md`), stored as `AnnotatedData` rows (`annotation_source = expert_panel`, `05_BACKEND_DESIGN.md` §5) |

## 4.3 "Training" Pipeline

1. Cross-encoder re-ranker (stage 5) fine-tuned on the annotated
   query-passage relevance pairs — a standard pairwise/listwise
   fine-tuning objective (e.g. margin ranking loss), logged to MLflow the
   same way Models 1–2's training runs are, so the registry has one
   consistent mental model across all three models.
2. Fusion weights (stage 4, Reciprocal Rank Fusion's `k` constant and any
   per-source weighting) and temporal-decay half-life (stage 7) are tuned
   via Optuna against the same annotated set (ADR-015's infrastructure
   reused, not a bespoke tuning loop).
3. ColBERT and BM25 (stages 1–2) are not retrained from scratch — ColBERT
   uses a pretrained checkpoint (fine-tuning is a stretch/future item, not
   assumed for the first version); BM25 has no learned parameters beyond
   standard term-frequency statistics computed directly over the document
   corpus.

## 4.4 Evaluation Metrics & Targets

NDCG@5 > 0.75, Precision@5 > 0.85, citation accuracy > 95% (per
`00_PROJECT_SCOPE.md`) — evaluated per-stage where possible (ADR-017), so
a regression is attributable: did fusion get worse, or did the re-ranker
regress, or did an upstream retrieval stage start missing candidates
entirely. Full metric definitions and the benchmark test set:
`08_EVALUATION_FRAMEWORK.md`.

## 4.5 "Explainability" for a Ranking Model

SHAP does not apply here — there is no single tabular prediction to
attribute. Instead, "explainability" for Model 3 means **citation
transparency**: every passage in a response is traceable to its retrieval
stage contributions (which stage(s) surfaced it, its fusion rank, its
re-ranked position, whether citation-graph traversal added it) — surfaced
in the UI as a lightweight provenance trail, not hidden behind a single
opaque relevance score. This is the RAG-appropriate analogue of Model
1–2's SHAP requirement, not an exemption from the project's
"explainability is mandatory" principle.

## 4.6 Deployment & Serving

Latency-critical: the full 7-stage path must fit the <500ms (p95) target
from `00_VISION_ML_PLATFORM.md` — genuinely difficult with this many
sequential stages (flagged as an open risk in `02_TRD.md` §19). Stages 1–2
run in parallel; a degraded-mode path (skip citation graph traversal under
load) is part of the serving design, not an afterthought bolted on after a
latency incident.

## 4.7 Known Limitations

- Fine-tuning the cross-encoder requires enough annotated data to avoid
  overfitting to 500 queries' idiosyncrasies; cross-validation across
  query subsets should be part of the evaluation, not just a held-out
  split.
- Citation graph traversal quality depends on the completeness of the
  citation metadata attached to ingested documents — a document ingested
  without citation metadata simply doesn't participate in that stage,
  which should degrade gracefully (documents ranked by the other 6 stages
  still surface), not error.

---

# 5. Cross-Model Requirements

- **Traceability**: every trained `ModelVersion` (all three models)
  references the `dataset_version_id` (or `AnnotatedData` set, for Model
  3) it was trained/tuned against — no model exists without a traceable
  data lineage, per ADR-009's principle extended to the ML layer.
- **Fairness**: Models 1–2 are evaluated for demographic fairness
  identically (§2.7/§3.7); Model 3 does not have an equivalent demographic
  fairness axis in the same sense (a literature query has no patient
  demographic), but does need bias-of-a-different-kind evaluation —
  whether retrieval favours certain journals/publication venues
  disproportionately — tracked in `08_EVALUATION_FRAMEWORK.md`, not
  ignored just because it doesn't fit the demographic-parity framework.
- **Registry consistency**: all three log to the same MLflow registry and
  `ModelVersion` table (`05_BACKEND_DESIGN.md` §5); all three go through
  the same A/B rollout gate (ADR-019) before reaching `production`,
  including Model 3 (a retrieval-pipeline "rollout" compares NDCG/citation
  accuracy between candidate and incumbent pipeline configurations, not
  just a classifier's accuracy).
- **PredictionLog conformance**: every inference from any of the three
  models writes a `PredictionLog` row (with model-specific detail in
  `RiskScore`/`TreatmentOutcome` for Models 1–2; Model 3's "predictions"
  are logged as query/ranking pairs for the same active-learning feedback
  loop, `03_APP_FLOW.md` §13).

---

# 6. Open Implementation Questions

- Exact ICD-code vocabulary and multi-hot encoding scheme for comorbidity
  features (§2.4) — needs a concrete decision once real MIMIC-III access
  (or a finalized synthetic schema) is in hand, not before.
- Whether Model 2's "similar historical cases" nearest-neighbor index is
  precomputed and refreshed on a schedule, or computed on-demand at
  inference time — a genuine latency-vs-freshness tradeoff to resolve
  against the <2s inference target once real data volume is known.
- Cross-encoder fine-tuning budget (epochs, learning rate) for Model 3 —
  deferred until the 500+ query annotated set actually exists; premature
  to fix now.

---

## Document Information

**Version History:**
- v1.0 — Initial full architecture for Models 1–3 (current)

## End of Document
