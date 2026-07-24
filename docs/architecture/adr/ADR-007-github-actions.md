# ADR-007 — GitHub Actions as CI/CD

## Status

Accepted

## Context

The project needs automated testing, linting, and build verification on
every PR to keep the "senior-engineer output, interview-defensible" bar
credible, and the branch-policy workflow — all work via feature branch and
PR, no direct pushes to `develop` — depends on CI gating before merge to be
meaningful rather than a formality.

## Decision

GitHub Actions was selected as the CI/CD tool.

## Alternatives Considered

- GitLab CI — would require moving the repository off GitHub, where the
  portfolio needs to live for recruiter and interviewer visibility.
- Jenkins — self-hosted, requiring the developer to operate a CI server;
  disproportionate operational overhead for a single-developer project.

## Consequences

### Positive

- Native to GitHub, so PR checks and branch protection live in the same
  place recruiters and interviewers will actually look when reviewing the
  repository.
- Large marketplace of prebuilt actions (Python setup, Docker build,
  coverage reporting) reduces custom CI scripting that would otherwise need
  to be written and maintained from scratch.
- Free tier is generous enough for a portfolio project's CI volume, keeping
  infrastructure cost at zero — consistent with the project's budget
  constraint.

### Negative

- Vendor lock-in to GitHub's workflow syntax — migrating CI to another
  provider later would mean rewriting the pipeline, not just re-pointing it.
- Less powerful than a self-hosted Jenkins setup for highly custom
  multi-stage pipelines, though the project's CI needs don't currently
  require that level of customization.
- Workflow debugging — caching behaviour, matrix builds — has a genuine
  trial-and-error cost compared to running the same steps locally first.

## References

- ADR-006 — Docker containerization
- `CLAUDE.md` — branch and PR policy
