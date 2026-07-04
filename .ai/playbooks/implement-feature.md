# Playbook: Implement Feature

## Purpose

This playbook defines the standard workflow for implementing any new feature in the MedIntel AI repository.

All AI coding agents should follow this process to ensure consistency, maintainability, and alignment with the project's architecture and documentation.

---

# Phase 1 — Understand

Before writing code:

- Read `.ai/BOOTSTRAP.md`
- Read `.ai/README.md`
- Read `.ai/llm-wiki/index.md`
- Read the relevant LLM Wiki pages
- Review the related documents in `/docs`
- Review the GitHub Issue or feature request

Do not begin implementation until the requirements are understood.

---

# Phase 2 — Plan

Before coding:

- Identify the affected modules.
- Review existing implementations.
- Reuse existing components where possible.
- Confirm the implementation aligns with the project architecture.
- Break the work into small, logical tasks.

---

# Phase 3 — Implement

During implementation:

- Follow repository coding standards.
- Keep changes focused on the feature.
- Maintain module boundaries.
- Write readable and maintainable code.
- Avoid unnecessary dependencies.

---

# Phase 4 — Validate

Before considering the feature complete:

- Verify functionality.
- Check for regressions.
- Confirm API consistency.
- Validate error handling.
- Ensure type safety.

---

# Phase 5 — Documentation

If applicable:

- Update documentation in `/docs`.
- Update the relevant LLM Wiki summary.
- Record any significant architectural decisions.

---

# Phase 6 — Final Review

Before submitting:

- Remove unused code.
- Improve readability where appropriate.
- Ensure naming consistency.
- Verify project structure remains consistent.

---

# Deliverables

Every completed feature should include:

- Working implementation
- Updated documentation (if required)
- Tests (when applicable)
- Suggested Conventional Commit message
- Summary of changes

---

# Definition of Done

A feature is complete when:

- Requirements are satisfied.
- Code follows project architecture.
- Documentation is synchronized.
- No known regressions are introduced.
- The implementation is ready for review.