# Architecture Rules

## Purpose

These rules define the architectural principles that every contributor and AI coding agent must follow.

---

# Core Principles

- Follow the Modular Monolith architecture.
- Maintain clear separation of concerns.
- Keep modules loosely coupled and highly cohesive.
- Design for maintainability and scalability.
- Favor composition over duplication.

---

# Module Boundaries

Every module must have a single responsibility.

Examples:

- Authentication
- Chat
- RAG
- Documents
- Analytics
- Administration

Modules should communicate only through well-defined interfaces.

---

# API Design

- Follow REST principles.
- Keep APIs stateless.
- Validate all inputs.
- Return consistent response formats.
- Handle errors gracefully.

---

# AI Architecture

- Keep LLM providers interchangeable.
- Isolate AI orchestration from business logic.
- Never hardcode provider-specific logic.
- Preserve the RAG pipeline architecture.

---

# Data Layer

- PostgreSQL stores relational data.
- Qdrant stores vector embeddings.
- Do not mix responsibilities between databases.

---

# Before Architectural Changes

Any significant architectural change must:

- Be documented.
- Include trade-off analysis.
- Update relevant ADRs if required.