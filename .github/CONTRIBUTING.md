# Contributing to MedIntel AI

Thank you for contributing to MedIntel AI.

This project follows a documentation-first and architecture-first development approach. Every contribution should align with the project's engineering principles and documentation.

---

# Development Workflow

Every task should follow this workflow:

1. Review the relevant documentation in `/docs`.
2. Read the AI workspace (`/.ai`) if using an AI coding assistant.
3. Create a new branch from `develop`.
4. Implement the change.
5. Update documentation if necessary.
6. Submit a Pull Request.

---

# Branch Strategy

- `main` → Stable releases
- `develop` → Active development
- `feature/*` → New features
- `fix/*` → Bug fixes
- `docs/*` → Documentation
- `refactor/*` → Refactoring

---

# Commit Messages

This repository follows the Conventional Commits specification.

Examples:

```text
feat(auth): implement JWT authentication

fix(api): handle invalid token

docs(prd): update functional requirements

refactor(chat): simplify service layer
```

---

# Coding Principles

- Follow the documented architecture.
- Keep modules focused and maintainable.
- Reuse existing code where appropriate.
- Avoid unnecessary dependencies.
- Write readable, self-documenting code.

---

# Documentation

Documentation is a core part of the project.

Whenever architecture, APIs, or workflows change, update the relevant documentation.

Documentation hierarchy:

1. `/docs`
2. `/.ai`
3. Source Code

---

# Pull Requests

Every Pull Request should:

- Address a single concern.
- Reference the related issue.
- Keep commits focused.
- Update documentation when applicable.
- Be ready for review before merging.

---

Thank you for helping maintain a clean, professional, and production-quality repository.