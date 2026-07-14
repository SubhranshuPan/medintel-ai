# 08_EVALUATION_FRAMEWORK.md — Comprehensive Evaluation Framework

**Project:** MedIntel AI
**Version:** v1.0
**Status:** Active
**Related:** `06_ML_MODELS.md`, `07_ML_OPS.md`, `00_VISION_ML_PLATFORM.md`, ADR-016, ADR-017, ADR-019

---

# 1. Purpose & Scope

`07_ML_OPS.md` §4 covers **production monitoring** — is a live model still
behaving, is it drifting, is it still fair. This document covers
**evaluation** — the pre-deployment and continuous-regression discipline
that decides whether a model or retrieval configuration is good enough to
become a candidate in the first place, and stays good enough over time.
The two are related (monitoring feeds evaluation triggers, evaluation
results feed the A/B gate in ADR-019) but are distinct concerns: monitoring
asks "is production still okay," evaluation asks "how good is this,
exactly, and compared to what."

---

# 2. Retrieval Evaluation (Model 3 / RAG Quality)

## 2.1 Metrics

| Metric | Definition | Target |
|---|---|---|
| Precision@k | Fraction of top-k retrieved passages judged relevant | Precision@5 > 0.85 |
| Recall@k | Fraction of all relevant passages captured in top-k | Tracked, no hard target (recall/precision tradeoff is tuned via fusion weights, `07_ML_OPS.md`) |
| NDCG@k | Rank-aware relevance quality (rewards relevant results appearing higher) | NDCG@5 > 0.75 |
| MRR | Mean Reciprocal Rank of the first relevant result | Tracked as a secondary diagnostic |
| Citation Accuracy | % of retrieved documents that actually support the claim the AI response attributes to them | > 95% |

## 2.2 Test Dataset

500+ medical queries with expert relevance annotations, stored as
`AnnotatedData` rows (`annotation_source = expert_panel`,
`05_BACKEND_DESIGN.md` §5). Query set construction: sampled across the
platform's actual use cases (literature Q&A, prediction-explanation
grounding, patient summary source-checking — `03_APP_FLOW.md` §14), not
just generic medical trivia, so the benchmark reflects what the system is
actually asked to do.

## 2.3 Per-Stage Attribution

Because retrieval is a 7-stage pipeline (ADR-017), evaluation runs the
same query set through the pipeline with each downstream stage disabled in
turn (dense-only, dense+sparse without fusion, without re-ranking, without
citation graph, without temporal decay) to attribute a metric change to a
specific stage — this is what makes a regression debuggable rather than
"the number went down, somewhere."

## 2.4 Benchmark Comparison

Retrieval quality is compared against PubMed search, Google Scholar, and a
plain ChatGPT-style answer (no retrieval) on the same query set, reported
side by side — not to claim MedIntel AI outperforms specialized literature
search tools in general, but to give an honest, specific answer to "how
does this compare" for interview conversations.

## 2.5 Reporting

Dashboard (Grafana, `07_ML_OPS.md` §4.5, or a dedicated evaluation report
exported via the Reporting pillar) showing metric trends over time as
the retrieval pipeline changes, not just a point-in-time number.

---

# 3. Generation Evaluation (LLM Output Quality)

## 3.1 Metrics

| Metric | Definition | Target |
|---|---|---|
| BLEU | N-gram overlap similarity to a reference answer | Tracked, secondary (BLEU is a weak proxy for medical correctness on its own) |
| ROUGE | N-gram recall-oriented overlap | Tracked, secondary |
| Hallucination Rate | % of claims in a generated response not supported by retrieved documents | < 5% |
| Medical Accuracy | Expert physician review of generated answers against gold-standard references | Inter-rater agreement κ > 0.80 required for the review process itself to be trusted |
| Citation Correctness | % of citations that validly support the specific claim they're attached to (distinct from §2.1's citation accuracy, which is about the *retrieved documents*; this is about whether the *generated text's* citation placement is correct) | > 95% |

## 3.2 Test Dataset

100+ gold-standard Q&A pairs from medical domain experts, distinct from
the retrieval test set (§2.2) — retrieval can succeed while generation
still hallucinates or mis-attributes a citation, so these need independent
measurement, not one conflated score.

## 3.3 Methodology

- Automated metrics (BLEU/ROUGE/hallucination rate via retrieval-groundedness
  checking) computed on every evaluation run.
- Medical accuracy requires human expert review — this cannot be fully
  automated and is run less frequently (e.g. per major generation-pipeline
  change, not per commit) given the cost of expert time; the inter-rater
  κ check exists precisely because a single reviewer's medical-accuracy
  judgment is not by itself a reliable ground truth.
- Hallucination rate is computed by checking each generated claim against
  the actual retrieved passages passed to the LLM (a claim not traceable
  to any passage in context counts as a hallucination) — not by a
  separate LLM "fact-checking" pass, which would just move the reliability
  problem rather than solve it.

---

# 4. Prediction Model Evaluation (Models 1–2)

## 4.1 Classification & Calibration Metrics

ROC-AUC, Precision-Recall curve, F1-score (per `06_ML_MODELS.md` §2.7/§3.7
targets), plus a **calibration plot** reviewed at every promotion decision
— a model can hit its ROC-AUC target while being badly calibrated (e.g.
systematically overconfident), which a single scalar metric would hide and
which matters directly for how a clinician should weigh a reported
probability.

## 4.2 Fairness Testing

| Metric | Definition |
|---|---|
| Equalized Odds | Same true positive rate (and false positive rate) across demographic groups |
| Demographic Parity | Same positive-prediction rate across groups |
| Predictive Parity | Same precision across groups |

Alert/gate threshold: > 5% disparity on any metric, any group pair
(`00_PROJECT_SCOPE.md`, ADR-016, ADR-019). Fairness testing runs on the
same held-out evaluation split as the primary metrics, per protected
attribute available in the (synthetic or MIMIC-III) data — see
`11_PRIVACY_COMPLIANCE.md` for which attributes are available and how
they're handled without becoming a re-identification risk themselves.

## 4.3 Cost-Effectiveness

Cost per correct prediction (compute + any API cost, `07_ML_OPS.md` §6)
compared against a naive clinical baseline (e.g. always-predict-majority-
class, or an existing simple clinical risk score like Framingham/CHADS2 —
§4.4) — a model that's marginally more accurate at materially higher cost
is a real trade-off to surface, not to ignore because "more accurate" is
the reflexive answer.

## 4.4 Ablation Studies

Feature-group ablations (remove lab values, remove comorbidities, remove
vital signs, one group at a time) to report which feature categories
actually drive performance — both a model-quality diagnostic and a
concrete, specific thing to say in an interview beyond "SHAP shows X is
important" (ablation validates SHAP's importance ranking against actual
held-out performance, rather than trusting the explanation method alone).

---

# 5. System-Level Benchmarking

| Comparison | Against |
|---|---|
| Risk model (Model 1) | Framingham Risk Score, CHADS2 (established clinical risk scores) |
| Retrieval (Model 3) | PubMed, UpToDate |
| Treatment recommendations (Model 2) | Published clinical guidelines for the same diagnosis-treatment pairs |
| Cost | Commercial tools (Optum, Epic, Cerner) — qualitative cost/capability comparison, not a claim of head-to-head superiority |

These comparisons exist to answer "so what, compared to what already
exists" honestly — a required question in health-tech interviews — not to
overstate the platform's real-world readiness relative to
regulator-cleared clinical tools.

---

# 6. Continuous Evaluation Pipeline

## 6.1 Schedule

Weekly automated evaluation (Celery beat, same scheduling mechanism as
`07_ML_OPS.md` §3/§4) against the fixed test sets (§2.2, §3.2, §4's
held-out split) for every model currently in `Staging` or `Production`.

## 6.2 Regression Detection

Alert if any metric drops > 3% versus the previous evaluation run — a
tighter threshold than the 5% production-monitoring alert threshold
(`07_ML_OPS.md` §4.4), deliberately: evaluation is meant to catch a
regression *before* it reaches the looser production-monitoring gate, not
duplicate it.

## 6.3 Bias Drift Detection

Fairness metrics (§4.2) are part of the same weekly evaluation run, not
only the production-monitoring sweep — this gives two independent checks
(evaluation-time and monitoring-time) on the same fairness question, which
is deliberate redundancy given how much the project's principles weigh
fairness, not an accidental duplication to consolidate away.

## 6.4 Dashboard

All metrics (retrieval, generation, prediction, fairness) trended over
time in one place (Grafana, `07_ML_OPS.md` §4.5, or a dedicated evaluation
view) — a reviewer or interviewer should be able to see "is this system
getting better or worse over time" at a glance, not have to reconstruct it
from individual run logs.

---

# 7. Relationship to the A/B Rollout Gate (ADR-019)

The A/B rollout gate (`07_ML_OPS.md` §5) uses this framework's metrics as
its inputs — the gate does not define its own separate notion of "better."
A candidate passes evaluation (this document) before it is even considered
for a rollout, and the rollout's own statistical test (§5.3 of
`07_ML_OPS.md`) is evaluated using the same metric definitions specified
here (§2–§4), not a parallel metric scheme.

---

# 8. The Caveat That Travels With Every Evaluation Result

Every number in this framework, when computed against synthetic or
MIMIC-III research-only data, demonstrates **methodology** — that the
evaluation pipeline works and produces sensible, attributable results —
not a validated real-world clinical-safety or fairness claim. This is the
same caveat stated in `07_ML_OPS.md` §4.6 and ADR-016/ADR-019; it applies
here with equal force and should accompany any external presentation of
these results (demo, portfolio write-up, interview discussion).

---

# 9. Open Implementation Questions

- Exact composition of the 500-query retrieval test set and the 100-pair
  generation test set (§2.2, §3.2) — depends on which medical literature
  corpus is actually ingested first; premature to enumerate specific
  queries before that corpus exists.
- Cadence and format for the human expert medical-accuracy review (§3.3) —
  a real cost/rigor tradeoff (frequent review is expensive; infrequent
  review lets errors persist longer) to resolve once a reviewer/process is
  identified, not assumed here.
- Whether ablation studies (§4.4) run on every evaluation cycle or only at
  major model-version milestones — leaning toward the latter given their
  compute cost, but not fixed.

---

## Document Information

**Version History:**
- v1.0 — Initial evaluation framework covering retrieval, generation, prediction, and system-level benchmarking (current)

## End of Document
