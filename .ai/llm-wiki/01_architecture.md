# Architecture Summary

## Architecture Style

MedIntel AI follows a Modular Monolith architecture.

Each module has a single responsibility while remaining independently maintainable.

---

## Core Modules

- Authentication
- Chat
- RAG
- Documents
- Analytics
- Administration

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

- FastAPI
- React
- PostgreSQL
- Qdrant
- LangChain
- Docker
- GitHub Actions

See ADRs for details.

---

Reference:

docs/02_TRD.md