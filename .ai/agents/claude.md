# Claude Code Agent Guide

## Purpose

This document provides repository-specific guidance for Claude Code.

Project knowledge is maintained in `.ai/llm-wiki/`.

---

# Read Order

Before making any changes, read:

1. .ai/BOOTSTRAP.md
2. .ai/README.md
3. .ai/llm-wiki/index.md
4. Relevant wiki pages
5. Relevant documents in `/docs`

---

# Responsibilities

Claude Code is primarily responsible for:

- Architecture implementation
- Backend development
- AI/RAG implementation
- Refactoring
- Documentation updates
- Code reviews

---

# Working Principles

- Follow the documentation before writing code.
- Respect the Modular Monolith architecture.
- Keep modules loosely coupled.
- Write clean, maintainable code.
- Prefer simple solutions over unnecessary complexity.
- Preserve existing architecture unless explicitly instructed otherwise.

---

# Coding Standards

- Follow repository coding standards.
- Keep functions focused.
- Avoid duplicate logic.
- Use meaningful names.
- Add comments only when necessary.

---

# Before Finishing

Ensure that:

- Code compiles.
- Existing functionality is preserved.
- Documentation is updated if required.
- Changes remain consistent with the project architecture.

---

# Do Not

- Rewrite unrelated files.
- Introduce unnecessary dependencies.
- Change architecture without approval.
- Ignore project documentation.