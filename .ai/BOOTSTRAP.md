# MedIntel AI - AI Agent Bootstrap

> **Purpose:** This file is the mandatory entry point for every AI coding agent working on the MedIntel AI repository.

---

# Project Philosophy

MedIntel AI is a production-oriented AI platform built using a **documentation-first** development approach.

The objectives are to:

- Build maintainable software
- Follow clean architecture principles
- Prioritize code quality over implementation speed
- Maintain synchronization between documentation and code
- Produce a portfolio that reflects professional software engineering practices

---

# Documentation Hierarchy

Always treat documentation in the following order of authority:

1. `/docs/`
2. `/.ai/llm-wiki/`
3. Source Code

Never assume behavior that contradicts the documentation.

---

# Required Reading Order

Before making any code changes, read the following files in order:

1. `/.agents/AGENTS.md` — **Developer context, career goals, and project strategy**
2. `.ai/README.md`
3. `.ai/llm-wiki/index.md`
4. Relevant LLM Wiki pages
5. Relevant `/docs/` documents
6. Current task or GitHub Issue

Do not begin implementation until sufficient project context has been gathered.

---

# Development Workflow

For every task:

1. Understand the requirement
2. Review related documentation
3. Plan the implementation
4. Implement the feature
5. Write or update tests
6. Update documentation if required
7. Suggest a conventional commit message

---

# Engineering Principles

Always:

- Follow the existing architecture
- Prefer simple, maintainable solutions
- Keep modules loosely coupled
- Reuse existing code before creating new code
- Write readable, type-safe code
- Handle errors gracefully
- Maintain consistent naming conventions

Never:

- Rewrite large sections without justification
- Introduce unnecessary dependencies
- Ignore existing documentation
- Break public interfaces without updating documentation

---

# Definition of Done

A task is complete only if:

- Requirements are satisfied
- Code is clean and documented
- Tests pass
- Documentation is updated (if applicable)
- No known regressions are introduced

---

# AI Agent Responsibility

When uncertain:

- Ask for clarification rather than making assumptions.
- Prefer consistency over creativity.
- Preserve the long-term maintainability of the project.

---

**This file is the single entry point for all AI coding agents working on MedIntel AI.**