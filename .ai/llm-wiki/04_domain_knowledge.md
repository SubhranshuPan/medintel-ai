# Domain Knowledge

## Purpose

MedIntel AI is a production-grade clinical intelligence platform spanning five pillars: patient data management, clinical analytics, predictive ML with explainability, RAG-backed AI decision support, and reporting.

The healthcare domain is used to demonstrate modern AI engineering, data engineering, explainable ML, semantic search, and full-stack software engineering practices.

---

# Domain Overview

The platform enables users to query trusted medical knowledge using natural language.

Rather than relying solely on an LLM, responses are grounded in retrieved medical literature to improve transparency and reduce hallucinations.

---

# Target Users

- Medical Students
- Clinical Researchers
- Healthcare Professionals
- AI Engineers
- Recruiters evaluating AI engineering skills

---

# Core Concepts

## Retrieval-Augmented Generation (RAG)

Instead of generating responses from model memory alone, the system retrieves relevant medical documents and supplies them as context to the LLM.

Benefits:

- More accurate responses
- Citation-backed answers
- Reduced hallucinations
- Updatable knowledge base

---

## Semantic Search

Documents are retrieved using vector embeddings rather than keyword matching.

Workflow:

User Query
→ Embedding
→ Vector Search
→ Relevant Documents

---

## Predictive ML & Explainability

The ML Engine predicts disease risk and hospital readmission from uploaded patient datasets.

Every prediction is explainable via SHAP (ADR-011): feature attributions show which patient factors drove a given risk score, and the AI Decision Support pillar translates SHAP output into natural-language explanations.

---

## Explainable AI

Every AI response should include supporting citations whenever possible.

The platform prioritizes transparency over unsupported generation.

---

## Knowledge Base

The medical knowledge base consists of:

- Research Papers
- Clinical Guidelines
- Medical Textbooks
- Biomedical Literature

Only trusted and legally usable sources should be indexed.

---

## AI Principles

The system follows these principles:

- Evidence over speculation
- Transparency by default
- Explainability first
- Human-in-the-loop development
- Modular AI architecture

---

## Constraints

Version 1 does NOT provide:

- Medical diagnosis
- Prescription recommendations
- Emergency medical advice

The platform is intended for educational and research purposes.

---

## UK Healthcare Context (NHS)

The NHS is the world's largest single-payer healthcare system. Key facts agents
should know when writing code, documentation, or making design decisions:

- **1.7 million+ employees**, £168 billion annual budget
- Active digital transformation via **NHSX** and **NHS Digital**
- Strong push for **explainable AI** — the NHS will not deploy black-box models
- **GDPR** governs all patient data processing in the UK
- **NICE guidelines** (National Institute for Health and Care Excellence) define
  clinical best practices — the AI assistant should reference these
- **ICD codes** (International Classification of Diseases) are the standard for
  disease coding in NHS datasets

### Revenue / Cost-Saving Metrics

These numbers provide real-world context for the platform's impact:

| Metric | Value | Source |
|---|---|---|
| Cost per avoided readmission | ~£1,700 | NHS England |
| National 30-day readmission rate (heart failure) | ~15% | NHS Digital |
| Potential savings (18% → 15% across 5,000 patients) | £255,000/year per trust | Calculated |
| Number of NHS trusts in England | ~220 | NHS England |
| Potential scaled savings across trusts | Millions per year | Projected |

### Relevant NHS Programmes

- **GIRFT (Getting It Right First Time)** — reducing unwarranted clinical variation
- **NHS Long Term Plan** — digital-first approach to healthcare
- **NHS AI Lab** — testing and deploying AI in healthcare settings
- **Federated Data Platform** — secure data sharing across trusts

---

## Market Gap

No open-source tool currently combines all of these in one platform:

- ✅ Dataset versioning with audit trail
- ✅ Explainable ML predictions (SHAP)
- ✅ Grounded AI with citations (RAG)
- ✅ Interactive clinical dashboards
- ✅ Automated report generation
- ✅ Healthcare-domain-specific design

Existing tools cover subsets: Tableau (dashboards only), Epic/Cerner (expensive,
locked), ChatGPT (no grounding), Jupyter (not deployable).

---

## Related Documentation

- `/.agents/AGENTS.md` — Developer career context, portfolio strategy, agent rules
- `.ai/llm-wiki/05_real_world_impact.md` — Full real-world impact analysis
- docs/00_PROJECT_SCOPE.md
- docs/01_PRD.md
- docs/02_TRD.md
- docs/03_APP_FLOW.md
