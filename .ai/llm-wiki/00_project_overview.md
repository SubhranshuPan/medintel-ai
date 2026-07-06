# Project Overview

## Purpose

MedIntel AI is a production-grade clinical intelligence platform built around five functional pillars. It demonstrates data engineering, machine learning with explainability (SHAP), Retrieval-Augmented Generation (RAG), and full-stack software engineering using the healthcare domain.

The project is designed to showcase professional engineering practices rather than serve as a simple portfolio application.

---

## Objectives

- Build a production-quality AI application.
- Demonstrate data engineering, MLOps, and explainable ML.
- Demonstrate RAG and LLM integration.
- Follow documentation-first development.
- Apply clean architecture and engineering best practices.
- Maintain scalability and maintainability.

---

## Target Users

- Healthcare Data Scientists
- Clinical Researchers
- Hospital Administrators
- System Administrators
- Recruiters evaluating engineering capability

---

## Five Pillars

1. **Patient Data Platform** — upload, validate, clean, manage, and version patient datasets (ADR-009).
2. **Clinical Analytics Dashboard** — disease prevalence, risk distributions, demographic analysis, time-series trends, KPIs.
3. **Machine Learning Engine** — disease risk & readmission prediction, SHAP explainability, model comparison, prediction history (ADR-010, ADR-011).
4. **AI Decision Support** — natural-language Q&A over uploaded data, prediction explanations, patient summaries, RAG-backed literature retrieval with citations.
5. **Reporting** — PDF reports, CSV/XLSX exports, executive dashboards, clinical summaries (ADR-012).

Cross-cutting: authentication (JWT), role-based authorization, user management, model version management, audit trail.

---

## Architecture Summary

Frontend:
- React
- TypeScript

Backend:
- FastAPI

Data:
- PostgreSQL
- Qdrant

AI:
- LangChain
- LangGraph
- Multiple LLM Providers

ML:
- scikit-learn
- SHAP

---

## Project Principles

- Documentation First
- Architecture First
- Explainability
- Security by Default
- Modular Design
- Production Quality

---

For complete requirements refer to:

- docs/00_PROJECT_SCOPE.md
- docs/01_PRD.md
- docs/02_TRD.md
