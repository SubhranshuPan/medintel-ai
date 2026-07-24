# ADR-002 — React as Frontend Framework

## Status

Accepted

## Context

The clinical analytics dashboard, patient cohort views, dataset-management
UI, and SHAP explainability visualizations (force plots, dependency plots)
need a frontend that data scientists and clinical stakeholders can use to
review cohorts and understand model output. The frontend is a consumer of
the FastAPI backend's typed API (ADR-001) and needs a component model
suited to a dashboard made of many independent visual modules — cohort
tables, risk-score cards, SHAP panels, report export — rather than a
single content-driven page.

## Decision

React + TypeScript was selected as the frontend framework.

## Alternatives Considered

- Vue — comparable developer experience, but a smaller ecosystem of
  data-visualization libraries and a smaller footprint in UK health-tech
  hiring, which matters for a portfolio project.
- Angular — more opinionated and heavier than this project's single
  dashboard-style frontend needs; its DI/module system is overkill here.
- Next.js — server-side rendering and routing conventions built for public,
  SEO-sensitive sites; irrelevant for an authenticated internal clinical
  dashboard, and its deployment model adds complexity the project doesn't
  need.

## Consequences

### Positive

- Largest ecosystem of data-visualization libraries (Recharts, Visx, D3
  bindings) for the SHAP force/dependency plots and clinical dashboard
  charts this project specifically needs.
- TypeScript pairs with FastAPI's Pydantic schemas to give end-to-end type
  safety when combined with an OpenAPI-generated client, catching
  integration mismatches at compile time rather than in the browser.
- React is the most in-demand frontend skill among the target UK
  data-science/ML-engineering roles, making the portfolio directly
  recruiter-legible.
- Component model maps cleanly onto the dashboard's structure: cohort
  table, risk-score cards, and SHAP panels are naturally independent,
  composable components.

### Negative

- No built-in routing or state management — the project takes on
  additional library choices (React Router, a data-fetching layer such as
  TanStack Query) that a more opinionated framework would decide for it.
- Client-side rendering means no meaningful first-paint or SEO benefit;
  irrelevant for an internal authenticated tool, but worth naming as a
  trade-off rather than ignoring it.
- JSX/hooks has a real learning curve relative to Vue's template syntax —
  acceptable for a single-developer project but a genuine onboarding cost
  if the team ever grows.

## References

- ADR-001 — FastAPI as backend framework
- ADR-011 — SHAP explainability
- `docs/00_VISION_ML_PLATFORM.md`
