# Git Rules

## Purpose

These rules define the Git workflow used throughout the project.

---

# Branch Strategy

- `main` → Stable production branch.
- `develop` → Active development.
- `feature/*` → New features.
- `fix/*` → Bug fixes.
- `docs/*` → Documentation.
- `refactor/*` → Refactoring.

---

# Commit Messages

Follow Conventional Commits.

Examples:

- feat:
- fix:
- docs:
- refactor:
- test:
- chore:

Example:

feat(auth): implement JWT authentication

---

# Pull Requests

Every Pull Request should:

- Address a single concern.
- Reference the related issue.
- Pass all checks.
- Update documentation if required.

---

# Before Merging

Verify:

- Code builds successfully.
- Tests pass.
- Documentation is updated.
- No merge conflicts remain.

---

# General Rules

- Commit small, focused changes.
- Avoid committing generated files.
- Never commit secrets or credentials.
- Keep commit history clean and meaningful.