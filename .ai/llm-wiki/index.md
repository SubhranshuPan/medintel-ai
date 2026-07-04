# LLM Wiki Index

> This index provides the recommended reading order for AI coding agents working on MedIntel AI.

The LLM Wiki contains concise, AI-optimized summaries of the project's architecture, technology, and engineering decisions. It complements the documentation in `/docs` but does not replace it.

---

# Reading Order

Every AI coding agent should follow this order before starting work:

1. `.ai/BOOTSTRAP.md`
2. `.ai/README.md`
3. `index.md`
4. Relevant LLM Wiki pages
5. Related documents in `/docs`
6. Current task or GitHub Issue

---

# Wiki Pages

| File | Purpose |
|------|---------|
| `00_project_overview.md` | Understand the project vision, goals, scope, and target users. |
| `01_architecture.md` | Learn the system architecture, major modules, and design principles. |
| `02_tech_stack.md` | Understand the selected technologies and why they were chosen. |
| `03_repository_structure.md` | Navigate the repository and locate project components. |

Future pages:

| File | Purpose |
|------|---------|
| `04_domain_knowledge.md` | Medical AI, RAG concepts, and domain-specific knowledge. |
| `05_ai_pipeline.md` | End-to-end Retrieval-Augmented Generation workflow. |
| `06_backend.md` | Backend architecture and service responsibilities. |
| `07_frontend.md` | Frontend architecture and application structure. |
| `08_database.md` | Database schema and persistence strategy. |
| `09_api.md` | API conventions and endpoint organization. |
| `10_coding_conventions.md` | Coding standards and engineering practices. |
| `11_decision_log.md` | Summary of Architecture Decision Records (ADRs). |
| `12_current_state.md` | Current implementation status. |
| `13_current_sprint.md` | Active sprint goals and priorities. |
| `14_next_tasks.md` | Upcoming implementation tasks. |
| `15_glossary.md` | Common project terminology. |

---

# Task-Based Reading Guide

## Understanding the Project

Read:

- `00_project_overview.md`
- `01_architecture.md`

---

## Backend Development

Read:

- `01_architecture.md`
- `02_tech_stack.md`
- `/docs/02_TRD.md`
- `/docs/05_BACKEND_DESIGN.md`

---

## Frontend Development

Read:

- `01_architecture.md`
- `02_tech_stack.md`
- `/docs/03_APP_FLOW.md`
- `/docs/04_PRODUCT_DESIGN.md`

---

## AI / RAG Development

Read:

- `01_architecture.md`
- `02_tech_stack.md`
- `/docs/02_TRD.md`
- `/docs/architecture/ai-pipeline.md`

---

## Repository Maintenance

Read:

- `03_repository_structure.md`

---

# Guiding Principles

When using this wiki:

- Read only the pages relevant to the current task.
- Prefer summaries from the LLM Wiki before consulting detailed documentation.
- Use `/docs` as the authoritative source when additional detail is required.
- Never duplicate or contradict information maintained in `/docs`.

---

# Maintenance

Whenever a major change is made to the project:

1. Update the relevant document in `/docs`.
2. Update the corresponding LLM Wiki summary.
3. Keep this index synchronized with the available wiki pages.