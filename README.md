# MedIntel AI

**AI Clinical Intelligence Platform** — a production-grade portfolio project demonstrating data engineering, explainable ML, RAG, and full-stack engineering in the healthcare domain.

> ⚕️ Educational and research use only. Out of scope: medical diagnosis, prescription recommendations, and emergency medical advice.

## What It Is

MedIntel AI is a modular-monolith platform built around **five pillars**:

1. **Patient Data Platform** — ingestion, versioned datasets, and management of de-identified patient data
2. **Clinical Analytics Dashboard** — interactive cohort and trend analytics
3. **Machine Learning Engine** — risk prediction models with SHAP explainability
4. **AI Decision Support** — RAG-powered clinical chat over medical documents
5. **Reporting** — configurable report generation and export

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind, shadcn/ui, Zustand, React Router, RHF/Zod, Recharts |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2.0, Pydantic v2, Alembic, JWT/OAuth2 |
| AI/ML | LangChain + LangGraph, multi-provider LLMs (OpenAI/Anthropic/Gemini), Qdrant, RAG, scikit-learn, SHAP |
| Data | PostgreSQL, Qdrant |
| DevOps | Docker, GitHub Actions, Nginx — Railway/Render now, AWS later |

## Repository Structure

```
docs/            Authoritative project documentation (scope, PRD, TRD, design, ADRs)
.ai/             AI agent workspace (llm-wiki, memory vault, rules, playbooks)
backend/         FastAPI application
frontend/        React application
ml/              ML models, training, and explainability
data/            Datasets and data artifacts
experiments/     ML experiments and notebooks
configs/         Configuration files
scripts/         Automation scripts
infrastructure/  Deployment and DevOps
reports/         Generated reports
```

## Development Philosophy

**Documentation-first.** `docs/` is the source of truth; `.ai/llm-wiki/` is the AI-optimized summary layer; source code comes last. Architectural decisions are recorded as ADRs in `docs/architecture/adr/`.

**Workflow:** feature branches → PR into `develop` → release to `main`.

## Status

🚧 Sprint 0 (documentation and architecture) complete — ADR-001 through ADR-012 accepted. Sprint 1 (backend foundation) is next.

## License

[MIT](LICENSE) © 2026 Subhranshu Pan
