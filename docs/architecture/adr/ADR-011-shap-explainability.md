# ADR-011 — SHAP as the Explainability Tooling

## Status

Accepted

## Context

Explainability is a core project principle ("Explainability over black-box AI") and is explicitly required for the ML Engine module (disease risk and readmission predictions) as well as the AI Decision Support module's "explain model predictions" capability. Clinical predictions in particular need per-patient, human-interpretable reasons for a risk score, not just an aggregate accuracy metric.

## Decision

**SHAP (SHapley Additive exPlanations)** is adopted as the explainability library for all tabular ML models produced by the ML Engine:

- `TreeExplainer` is used for tree-based models (XGBoost, tree-based scikit-learn models per ADR-010), since it is exact and fast for this model family.
- Local (per-prediction) SHAP values are computed at prediction time and stored alongside the prediction record (`predictions.shap_values`, as JSONB) so the frontend can render a per-patient explanation without recomputing it.
- Global feature-importance summaries (for the "Feature Importance Visualizations" dashboard requirement) are computed as a background job over a sampled background dataset, not on every request.
- The AI Decision Support module's "explain model predictions" feature translates the stored SHAP values into a natural-language explanation via the existing LLM pipeline (ADR-005), rather than the LLM inventing an explanation independently.

## Alternatives Considered

- LIME
- ELI5
- Permutation importance only (no per-instance explanations)
- Captum (primarily built for deep learning models, not the tabular tree models used here)

## Consequences

### Positive

- SHAP is the industry-standard explainability library and is widely recognized by technical interviewers, directly supporting the project's goal of demonstrating applied ML competence.
- `TreeExplainer` is fast enough for on-demand, per-prediction explanations with tree-based models, keeping inference latency within the project's performance targets.
- Grounding LLM explanations in actual computed SHAP values (rather than free-form generation) keeps the AI Decision Support module consistent with the project's "citation-backed, non-hallucinated" principle.

### Negative

- Computing SHAP values for large datasets or non-tree models can be slow; global summaries must be restricted to a sampled background set and computed asynchronously rather than per-request.
- Storing SHAP value arrays adds a non-trivial serialization/storage concern (JSONB payloads per prediction) that needs to be accounted for in the database schema and query performance planning.
- Ties the explainability approach fairly tightly to tree-based models; if a future version adopts deep learning models, a second explainer (e.g., DeepExplainer or KernelExplainer) would need to be introduced.

## References

- `docs/00_PROJECT_SCOPE.md` — "Explainable Predictions using SHAP" requirement
- ADR-010 — ML model training, registry, and serving strategy
- ADR-005 — LangChain + LangGraph as orchestration framework
