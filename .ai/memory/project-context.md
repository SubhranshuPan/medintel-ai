# Project Context

> Stable, slow-changing facts about MedIntel AI. This file should rarely need edits —
> update it only when the fundamentals below actually change. For day-to-day progress,
> see `session-history.md`. For accumulated decisions and conventions, see `project-memory.md`.

---

## What This Project Is

MedIntel AI is a production-grade AI Clinical Intelligence Platform built around
five pillars — Patient Data Platform, Clinical Analytics Dashboard, Machine Learning
Engine (with SHAP explainability), AI Decision Support (RAG/chat), and Reporting —
demonstrating data engineering, explainable ML, RAG, and full-stack engineering
in the healthcare domain. It is documentation-first: `/docs` is authoritative,
`.ai/llm-wiki` is the AI-optimized summary layer, source code is last.

Target users: healthcare data scientists, clinical researchers, hospital
administrators, system administrators, and recruiters evaluating engineering
capability.

Out of scope for v1: medical diagnosis, prescription recommendations, emergency
medical advice. Educational/research use only.

---

## Architecture

Modular Monolith. Core modules follow the five pillars: Patient Data Platform,
Clinical Analytics, ML Engine, AI Decision Support (chat/RAG/documents), Reporting —
plus Authentication and Administration. Key ADRs: 001–008 (core stack),
009 (dataset versioning), 010 (ML model serving), 011 (SHAP), 012 (reporting/export).

Flow: React → FastAPI → Auth → Business Services → RAG Engine → (PostgreSQL + Qdrant)
→ LLM Provider → Response.

Design principles: API-first, separation of concerns, stateless services,
explainable AI, layered backend, modular components.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, Zustand, React Router, RHF + Zod, Recharts |
| Backend | FastAPI, Python 3.12+, SQLAlchemy 2.0, Pydantic v2, Alembic, JWT/OAuth2 |
| AI / ML | LangChain, LangGraph, multi-provider LLM abstraction (OpenAI/Anthropic/Gemini), Qdrant, embeddings (BAAI BGE/OpenAI), SHAP, scikit-learn, pandas, NumPy |
| Data | PostgreSQL, Qdrant (vector DB) |
| DevOps | Docker, GitHub Actions, Nginx, Railway/Render (current), AWS (future) |
| PM / Docs | Markdown, Mermaid, GitHub Issues/Milestones/Projects, ADRs, Notion |

Selection criteria: mature ecosystem, performance, scalability, strong
documentation, industry adoption.

---

## Repository Structure

```
docs/            Project documentation (authoritative)
.ai/             AI workspace (this workspace)
backend/         FastAPI application
frontend/        React application
ml/              AI/ML components
configs/         Configuration files
scripts/         Automation scripts
infrastructure/  Deployment and DevOps
reports/         Generated reports
.github/         GitHub workflows
```

---

## Repo & Branching

Repo: `github.com/SubhranshuPan/medintel-ai`

Branch strategy (`.ai/rules/git.md`):
- `main` — stable production
- `develop` — active development
- `feature/*`, `fix/*`, `docs/*`, `refactor/*` — scoped work

Conventional Commits required (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

---

## Core Domain Concepts

- **RAG**: responses grounded in retrieved medical literature, not model memory alone — reduces hallucination, enables citations.
- **Semantic search**: vector embeddings, not keyword matching.
- **Explainability**: every AI response should carry supporting citations where possible; SHAP used for model explainability.
- **Knowledge base**: research papers, clinical guidelines, textbooks, biomedical literature — trusted, legally usable sources only.

---

---

## Developer Context & Career Goals

**Full details:** `/.agents/AGENTS.md` — read that file for the complete picture.

Summary: Developer is Subhranshu Panda, joining MSc Data Science at University of
Glasgow (UK) in September 2026, graduating September 2027. Has a ₹45 Lakh SBI loan
to repay via a visa-sponsorship full-time role in the UK healthcare/data science
domain. This project is the primary portfolio piece for landing part-time roles,
internships during the MSc, and a post-graduation full-time position. Every
engineering decision should maximize portfolio impact for UK healthcare data
science roles. The project must look like a senior engineer's production system,
not a tutorial chatbot.

---

## Real-World Impact & Market Positioning

**Full details:** `.ai/llm-wiki/05_real_world_impact.md`

**Problem solved:** Clinical data workflows are fragmented across 5+ tools
(Excel, Tableau, Jupyter, ChatGPT, Word). MedIntel AI consolidates data
ingestion, analytics, explainable ML, grounded AI Q&A, and reporting into
one platform.

**NHS revenue impact:** Each avoided hospital readmission saves ~£1,700. A
reduction from 18% to 15% readmission rate across 5,000 patients = £255,000
saved per year per trust. Across ~220 NHS trusts, savings scale to millions.

**Market gap:** No open-source tool combines dataset versioning + explainable ML
(SHAP) + grounded RAG + clinical dashboards + automated reporting for healthcare.

**Target employers:** NHS Digital, BenevolentAI, IQVIA, Huma, AstraZeneca,
DeepMind Health, Optum, Babylon Health.

**Visa sponsorship justification:** The project demonstrates 5 rare competencies
simultaneously (production ML, healthcare domain, MLOps, explainable AI,
full-stack engineering) — skills genuinely hard to find locally in the UK.

---

*Last reviewed: 2026-07-09. Update this file only when stack, architecture, or repo structure fundamentally change — not for routine feature work.*
