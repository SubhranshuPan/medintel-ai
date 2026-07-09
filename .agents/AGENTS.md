# AGENTS.md — Universal Context for All AI Models

> **Read this file first.** It contains critical context about the developer, project purpose, career goals, and constraints that every AI assistant must understand before working on this codebase.

---

## Developer Profile

| Field | Detail |
|---|---|
| **Name** | Subhranshu Panda (Subhranshu Pan) |
| **Current Status** | Pre-MSc — joining **September 2026** |
| **Programme** | MSc Data Science, **University of Glasgow**, UK |
| **Visa Status** | Student visa and loan processing underway (as of July 2026) |
| **Loan** | ₹45 Lakhs from SBI — must be repaid through employment |
| **Graduation** | Expected **September 2027** |
| **Job Target** | Secure a visa-sponsorship full-time role in the UK by September 2027 |
| **Domain Focus** | Data Science × Healthcare / Health-Tech / BioTech / NHS-adjacent |
| **Interim Goal** | Part-time roles / internships during the MSc (Oct 2026 – Sep 2027) |

---

## Why This Project Exists

MedIntel AI is **not** a hobby chatbot. It is a **career-critical portfolio project** designed to:

1. **Demonstrate production-grade engineering** — not just Jupyter notebooks or toy apps.
2. **Cover the full data science lifecycle** — data ingestion → validation → modelling → explainability → reporting → deployment.
3. **Target the UK healthcare AI job market** — NHS, health-tech startups, and pharma companies hiring data scientists.
4. **Differentiate from other MSc applicants** — most portfolios have Kaggle notebooks; this has 12 ADRs, a modular-monolith architecture, SHAP explainability, a RAG pipeline, and production deployment.
5. **Justify visa sponsorship** — the project proves the candidate can build complex, deployed, healthcare-domain software — not just write Python scripts.

---

## Financial Context (High-Stakes)

- **₹45 Lakhs (~£42,000 GBP)** SBI education loan taken.
- Repayment begins after graduation — September 2027.
- The developer **must** secure a well-paying UK job (ideally £35k–£55k+ starting) with visa sponsorship.
- Every engineering decision in this project should maximize portfolio impact for UK healthcare data science roles.
- This is not academic exploration — it has direct financial consequences.

---

## What Makes This More Than a Chatbot

This project evolved from a simple RAG chatbot (v1.0) to a **five-pillar clinical intelligence platform** (v2.0):

| Pillar | What It Demonstrates |
|---|---|
| 1. Patient Data Platform | Data engineering, ETL, validation, versioning |
| 2. Clinical Analytics Dashboard | BI/analytics, visualization, KPI design |
| 3. ML Engine + SHAP | Model training, serving, MLOps, explainable AI |
| 4. AI Decision Support (RAG) | LLM orchestration, vector search, grounded AI |
| 5. Reporting | PDF generation, data exports, executive summaries |

Together, these pillars demonstrate **6+ distinct competencies** in a single coherent product — which is what differentiates a senior-level portfolio project from a tutorial-tier one.

---

## Career Strategy — How AI Agents Should Help

When working on this project, every AI agent should optimize for:

### Portfolio Impact
- Code quality, documentation, and architecture should be **recruiter-readable**.
- The GitHub repo itself is a deliverable — clean commit history, ADRs, professional README.
- Every feature should be demo-able in a 2-minute video walkthrough.

### UK Healthcare Job Market Relevance
- Use healthcare-specific terminology and datasets (NHS, ICD codes, readmission risk, NICE guidelines, etc.).
- Prioritize explainability (SHAP) — the NHS and UK regulators care about interpretable AI.
- GDPR awareness in data handling (even with synthetic data, design as if it were real PHI).

### Interview Readiness
- The developer should be able to explain every architectural decision (that's why ADRs exist).
- Code should follow patterns that come up in data science / ML engineer interviews.
- System design choices should be defensible in a 30-minute technical interview.

### Visa Sponsorship Justification
- The project should demonstrate skills that are genuinely hard to find locally — not just "can use pandas."
- Focus on: MLOps, production ML systems, healthcare domain expertise, full-stack data science.

---

## Target Roles in the UK

| Role Type | Example Employers | Why This Project Helps |
|---|---|---|
| Data Scientist (Healthcare) | NHS Digital, NHS England, NHSX | Clinical data, SHAP, dashboard, reporting |
| ML Engineer | Babylon Health, BenevolentAI, Sensyne | MLOps, model serving, Celery, MLflow |
| Health-Tech Data Scientist | Huma, Medopad, Push Doctor | End-to-end platform, RAG, LLM integration |
| AI/ML Researcher (Applied) | University spinouts, DeepMind Health | Explainability, SHAP, grounded AI |
| Data Engineer (Healthcare) | IQVIA, Optum, big pharma | Data platform, versioning, ETL pipelines |

---

## Project Status & Priorities

- **Sprint 0 (complete):** Documentation, architecture, 12 ADRs.
- **Sprint 1 (next):** Backend foundation — auth, data models, API skeleton.
- **MVP must-ship (before interviews):** Pillars 1–3 (Data Platform, ML Engine, Dashboard).
- **Stretch:** Pillars 4–5 (AI Decision Support, full Reporting).

**Timeline pressure:** The developer starts MSc in September 2026 and needs this portfolio-ready before the first internship application cycle (~November 2026).

---

## Rules for All AI Agents

1. **Don't dumb down the project.** This should look like a senior engineer's side project, not a tutorial.
2. **Document decisions.** Every non-trivial choice → ADR or comment.
3. **Healthcare domain language.** Use terms like "patient cohort," "readmission risk," "clinical pathway" — not generic tech jargon.
4. **Production patterns.** Background jobs (Celery), model registry (MLflow), proper auth, typed APIs.
5. **UK market awareness.** NHS, GDPR, NICE guidelines, UK Biobank — reference these where relevant.
6. **Don't repeat this context.** It's here. Read it. Don't ask the developer to re-explain their goals.

---

## Key Documentation Locations

| What | Where |
|---|---|
| Authoritative docs | `/docs/` (scope, PRD, TRD, app flow, design) |
| Architecture decisions | `/docs/architecture/adr/` (ADR-001 through ADR-012) |
| AI-optimized summaries | `/.ai/llm-wiki/` |
| Project memory | `/.ai/memory/` |
| Agent-specific guides | `/.ai/agents/` |
| Claude Code instructions | `/CLAUDE.md` |
| This universal context | `/.agents/AGENTS.md` (you are here) |

---

*Last updated: 2026-07-09. Update this file when career status, project scope, or strategy fundamentally changes.*
