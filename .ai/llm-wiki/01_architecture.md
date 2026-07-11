# Architecture Summary

## Architecture Style

MedIntel AI follows a Modular Monolith architecture.

Each module has a single responsibility while remaining independently maintainable.

---

## Core Modules

Aligned with the five product pillars plus cross-cutting concerns:

- Patient Data Platform (upload, validation, cleaning, dataset versioning)
- Clinical Analytics (dashboards, KPIs, trends)
- ML Engine (training, prediction, SHAP explainability, model comparison)
- AI Decision Support (chat, RAG, documents, prediction explanation)
- Reporting (PDF, CSV/XLSX export, executive dashboards)
- Authentication & Authorization
- Administration (users, model versions, logs, audit trail)

---

## High-Level Flow

React

↓

FastAPI

↓

Authentication

↓

Business Services

↓

RAG Engine

↓

PostgreSQL + Qdrant

↓

LLM Provider

↓

Response

---

## Design Principles

- API First
- Separation of Concerns
- Stateless Services
- Explainable AI
- Layered Backend
- Modular Components

---

## Architecture Decisions

- ADR-001 FastAPI
- ADR-002 React
- ADR-003 PostgreSQL
- ADR-004 Qdrant
- ADR-005 LangChain
- ADR-006 Docker
- ADR-007 GitHub Actions
- ADR-008 Modular Monolith
- ADR-009 Dataset Versioning
- ADR-010 ML Model Serving
- ADR-011 SHAP Explainability
- ADR-012 Reporting & Export
- ADR-013 ORM & Migrations (SQLAlchemy 2.0 + Alembic)

See docs/architecture/adr/ for details.

---

Reference:

docs/02_TRD.md
