# Playbook: Sprint 2 Kickoff — Patient Data Platform

## Purpose

This playbook defines the plan and workflow for Sprint 2. It exists so a fresh
Claude Code session can pick up Sprint 2 with full context, without Som having
to re-explain scope, sequencing, or process from scratch.

Sprint 1 (Backend Foundation: auth, DB schema, FastAPI skeleton, Docker,
frontend scaffold) is complete — 11/11 issues, milestone closed
(`.ai/memory/session-history.md`, 2026-07-12 entries).

---

# Scope — Why Sprint 2 = Patient Data Platform

Per `docs/01_PRD.md` §11 (MVP Scope & Release Plan), the MVP pillar order is:

**Patient Data Platform → ML Engine → Clinical Analytics Dashboard**

"This sequencing exists because each pillar depends on data existing first."

An earlier session-history note floated "Authentication milestone" as a
Sprint 2 candidate — that's stale now that #7 (JWT auth + RBAC) shipped as
part of Sprint 1. Sprint 2 is **Pillar 1 — Patient Data Platform**
(`docs/00_PROJECT_SCOPE.md` §Pillar 1, `docs/architecture/adr/ADR-009-dataset-versioning.md`).

## Sub-issues (create fresh — do not guess issue numbers)

| Issue | Notes |
|---|---|
| epic: Patient Data Platform | mirrors epic #5 pattern from Sprint 1 |
| `Dataset` / `DatasetVersion` models + Alembic migration | UUID PK, audit-timestamp mixins, same pattern as #6 |
| CSV upload endpoint + immutable object storage | local disk in dev, MinIO-compatible in prod (ADR-009) |
| Schema/data validation | TRD (`02_TRD.md` line 79) names `pandera` **or** `great-expectations` as undecided — needs a real decision, write it up as **ADR-014**, don't pick silently |
| Cleaning/preprocessing → new version row | never mutate an existing version, per ADR-009 |
| Dataset management endpoints (list/view/delete) + repo/service layer | `GET/POST /datasets`, `GET /datasets/{id}/versions` |
| `audit_logs` table + logging on any endpoint touching patient-level data | mandatory — TRD §9: "flag for privacy/compliance review"; treat synthetic data as real PHI per project GDPR rule |
| Frontend: dataset upload + list UI wired to the real API | first real screen beyond the health-check placeholder from #10 |

## Carried-forward backlog

- Frontend CI lint/build job — still missing from `.github/workflows/ci.yml` (backend-only job exists today)
- Issues #24 / #25 / #26 — referenced in session-history as deferred hardening (rate-limiting on `/login` + `/register` is #24) but not yet detailed here; **check `gh issue list` before creating anything new** to avoid duplicates

---

# Where each step happens

## 1. GitHub setup — Claude Code (has `gh` auth; the Cowork sandbox does not)

Milestones "Sprint 0–5 + v1.0" were pre-created during the 2026-07-08 hygiene
pass — verify "Sprint 2" exists before creating it:

```
gh api repos/SubhranshuPan/medintel-ai/milestones --jq '.[].title'
gh issue list --milestone "Sprint 2 - Patient Data Platform"
```

Create the epic + sub-issues above if not already present. Use the existing
label taxonomy (Area: `backend`/`frontend`/`database`; Type: `feature`;
Priority: `P1-High` for the models/upload/validation chain, `P2-Medium` for
the frontend screen; Meta: `sprint-2`). Link sub-issues to the epic the same
way #6–#10 were linked under epic #5.

## 2. Planning — Claude Code, Opus, new session

DB schema changes + API design + a new architectural decision (validation
library) — per `CLAUDE.md`'s Model Routing table, this requires an Opus
`/plan` pass before any Sonnet execution.

First prompt in the new session:

> `/model` → Opus, then:
> `/plan Sprint 2 — Patient Data Platform pillar. Scope: Dataset/DatasetVersion
> SQLAlchemy models + Alembic migration per ADR-009; CSV upload to object
> storage; schema/data validation (decide pandera vs great-expectations — write
> ADR-014); cleaning pipeline producing new versions; list/view/delete
> endpoints; audit_logs table for GDPR compliance on any patient-data endpoint.
> Read docs/00_PROJECT_SCOPE.md §Pillar 1, docs/02_TRD.md §9 and §11, ADR-009,
> and the existing backend/app structure from #6/#7/#9 before proposing
> anything.`

Let it read the actual code rather than pasting file contents into the
prompt — shorter prompt, same context, no wasted tokens re-typing what
Claude Code can read itself.

## 3. Execution — Claude Code, Sonnet, one branch/PR per issue

Same pattern as #6–#10: branch off `develop`
(`feat/<issue-number>-short-name`), `/execute`, one concern per PR, rebase
onto `develop`, report-only (Som merges, never auto-merge). After the Opus
plan is approved: `/model` → Sonnet, then `/execute` per issue in separate
focused turns — don't execute all sub-issues in one context.

## 4. Skill layering per issue

- **`ponytail`** at the start of each issue — this is what kept #10 scoped to
  "init only" and deferred Zustand/RHF/Recharts in Sprint 1. Use it the same
  way: scope each Patient Data Platform issue narrowly, defer polish.
- **ADR-014** (validation library choice) — follow the existing ADR template
  in `docs/architecture/adr/`.
- **`code-review`** before opening each PR — this is what caught the CORS
  advisory on #9 and is already the Definition of Done gate.
- **`engineering:testing-strategy`** once validation/versioning logic exists —
  dataset versioning correctness deserves a real test plan, not ad hoc pytest.

## 5. Docs/memory — automatic

`CLAUDE.md`'s Session-End Checklist is loaded natively by Claude Code, so it
appends `.ai/memory/session-history.md` / `project-memory.md` entries itself
at end of session, same as every Sprint 1 entry. Review the entry before
committing; don't need to ask for it.

---

# Context/token efficiency

- Two-model routing: Opus only for the planning pass, Sonnet for all
  execution. Don't run the whole sprint in Opus.
- One issue = one session/context, not one epic = one context. A fresh
  session per issue avoids dragging stale context (e.g. the upload-endpoint
  discussion) into the validation-library issue.
- Point Claude Code at doc paths (`docs/02_TRD.md §9`, `ADR-009`) instead of
  pasting their content into prompts.
- `ponytail`'s scope discipline is itself a token-saver — Sprint 1's #10 entry
  shows it explicitly deferring unrelated frontend work rather than letting
  the session balloon.
- Session-end checklist writes are cheap (one templated file) — don't let a
  session run long trying to "wrap up thoroughly" beyond that.

---

# Definition of Done (per issue, unchanged from `.ai/rules/git.md` / `daily-workflow.md`)

- [ ] Code works and is tested
- [ ] Linter passes, CI green
- [ ] Docs/ADR updated if behaviour or architecture changed (ADR-014 for the
      validation library decision)
- [ ] Conventional commit + PR with filled template, referencing the issue
- [ ] `.ai/memory/session-history.md` entry appended
- [ ] Issue closed on the board, epic progress updated

---

# Refs

- `docs/01_PRD.md` §11 (MVP Scope & Release Plan)
- `docs/00_PROJECT_SCOPE.md` §Pillar 1
- `docs/02_TRD.md` §9 (Data Platform Architecture), §11 (Database Design)
- `docs/architecture/adr/ADR-009-dataset-versioning.md`
- `.ai/memory/session-history.md` (2026-07-11, 2026-07-12 entries — Sprint 1 pattern to mirror)
- `CLAUDE.md` (Model Routing table)
