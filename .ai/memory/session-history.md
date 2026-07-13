# Session History

> Append-only log, most recent session on top. One entry per working session.
> Keep entries brief — link to the PR/issue/ADR for detail rather than duplicating it.

---

## Template

```
## YYYY-MM-DD — <short title>

**Agent:** Claude / ChatGPT / Gemini / OpenCode / human
**Branch:** <branch name>
**Did:**
- ...

**Decisions made:**
- ...

**Next up:**
- ...

**Refs:** PR #, Issue #, ADR #
```

---

## 2026-07-13 — Sprint 2 kickoff: GitHub board + Opus planning pass

**Agent:** Claude (Opus 4.8, Claude Code)
**Branch:** `develop` (planning only — no feature branch yet)
**Did:**
- Followed `.ai/playbooks/sprint-2-kickoff.md` steps 1–2
- **Step 1 (GitHub):** renamed milestone #5 `Sprint 2 - Authentication` →
  `Sprint 2 - Patient Data Platform` (title was stale — auth shipped as #7 in
  Sprint 1); created epic **#29** + children **#30–#36**, all linked as GitHub
  sub-issues, milestoned, labelled per the existing taxonomy
- Confirmed #24/#25/#26 already existed (auth hardening) — not recreated, left
  unmilestoned as backlog
- **Step 2 (Opus `/plan`):** wrote `.claude/current_plan.md` — per-issue steps,
  file paths, code snippets, risks, verification, for Sonnet `/execute`

**Decisions made:**
- **ADR-014 → pandera** (to be written up in #33): schema-as-code, native pandas,
  structured failure report → `validation_report` JSONB, no extra infra.
  great-expectations rejected — Data Context / expectation suites / Data Docs are
  a second config surface beside the ORM; same reasoning ADR-009 used against
  DVC/LakeFS
- **Audit logging = ASGI middleware, not per-endpoint calls.** A handler-level
  `audit(...)` can be forgotten on a new endpoint and can never record 401/403
  (the handler never runs). Middleware over the `/api/v1/datasets` prefix audits
  every request incl. denials; endpoints enrich via `request.state.audit_detail`
- **`audit_logs` (#31) sequenced before the upload endpoint (#32)** — deviates
  from the playbook's issue order so the first patient-data endpoint never ships
  unaudited
- **`DELETE /datasets/{id}` = soft delete.** Hard delete would destroy artifacts
  referenced by audit rows and future training runs, breaking the traceability
  ADR-009 exists to provide. GDPR erasure = a separate, itself-audited purge
  (out of Sprint 2 scope)
- Two landmines documented in the plan: bare `JSONB` won't compile against the
  SQLite test DB (needs `.with_variant(JSON, "sqlite")`); the audit middleware
  binds `AsyncSessionLocal` at import, so `dependency_overrides` can't redirect
  it — `conftest.py` must monkeypatch or tests write to the real Postgres

**Next up:**
- Execute #30 (Dataset/DatasetVersion models + migration) in a **fresh Sonnet
  session**: branch `feat/30-dataset-models`, `/execute`, `/code-review`, PR.
  One issue = one session (playbook §Context/token efficiency)
- Then #31 → #32 → (#33 → #34) + #35 → #36. Frontend CI lint/build job lands
  with #36 (carried-forward backlog)

**Refs:** Epic #29, issues #30–#36, ADR-009, ADR-014 (pending, #33),
`.ai/playbooks/sprint-2-kickoff.md`, `.claude/current_plan.md`

---

## 2026-07-12 — Sprint 1: Frontend initialization (#10)

**Agent:** Claude (Opus 4.8, Claude Code)
**Branch:** `feat/10-frontend-init` (off `develop`)
**Did:**
- Scaffolded `frontend/` by hand (no Vite CLI cruft): React 19 + TypeScript +
  Vite 6, Tailwind CSS v4 via `@tailwindcss/vite`, React Router 7
- App shell `AppLayout` (sidebar + header, `<Outlet/>`), routes: Clinical
  Dashboard + Patient Cohorts placeholders, 404; index redirects to `/dashboard`
- Typed fetch client `src/lib/api.ts` (`ApiError`, `getHealth`) hitting
  `VITE_API_BASE_URL` + `/api/v1`; `HealthStatus` mirrors backend `HealthResponse`
- Dashboard renders the live backend health probe (Connected/Unreachable badge)
  as end-to-end proof the client reaches the API
- `npm run build` green (tsc `--noEmit` typecheck + vite build, 46 modules)

**Decisions made:**
- Followed the TRD-pinned stack (02_TRD.md §Frontend); no new ADR needed
- Ponytail-scoped to init only: deferred Zustand / React Hook Form+Zod / Recharts
  / shadcn/ui components / TanStack Query until feature screens need them
- Single `tsconfig.json` with `noEmit` + `tsc --noEmit` in build (skips project
  references); ESLint deferred (tsc covers type errors for a scaffold)

**Merged:** PR #28 rebased to `develop` (commit 5239839); #10 closed manually
(`Closes #10` only auto-fires on merge to the default branch, not `develop`);
milestone **Sprint 1 - Backend Foundation** closed (11/11 issues). **Sprint 1
complete.**

**Next up:**
- Sprint 2 (Authentication milestone) or first frontend analytics screen + auth wiring
- Add frontend CI job (lint/build); backlog hardening #24 (rate-limit) / #25 / #26

**Refs:** Issue #10, PR #28, ADR-002, 02_TRD.md

## 2026-07-11 — Tooling: obsidian-second-brain skill install + `.ai/` vault init

**Agent:** Claude (Opus 4.8 / Fable 5, Claude Code)
**Branch:** `develop` (working tree only, nothing committed)
**Did:**
- Installed `obsidian-second-brain` skill (eugeniughelbur/obsidian-second-brain)
  to `~/.claude/skills/`; wired `OBSIDIAN_VAULT_PATH=D:/AI-Portfolio/medintel-ai/.ai`,
  SessionStart hook (vault-context inject), inert PostCompact bg-agent hook, and
  44 `/obsidian-*` slash commands into global Claude Code config (`~/.claude/`)
- Windows fixes: bypassed missing `jq` (manual settings.json edits), used `python`
  not broken `python3` Store alias, copied commands instead of symlinks
- Ran `/obsidian-init` on the `.ai/` vault: created `_CLAUDE.md` (vault operating
  manual encoding existing conventions — append-only memory, /docs > llm-wiki > code,
  report-only autonomy), root `index.md` (catalog of all 22 notes), `log.md` pointer
  + `Logs/2026-07-11.md` (per-day op log)
- Fixed `Home.md` `[[index]]` wikilink shadowed by new root `index.md`
  (now explicit `[[llm-wiki/index]]`)

**Decisions made:**
- `.ai/` doubles as the Obsidian vault — no separate copy, git-tracked with repo
- Skipped skill's `Bases/` kanban files (no Daily/People/Projects/Tasks folders
  here; vault is a project workspace, not a life OS — rule written into `_CLAUDE.md`)
- Legacy vault files keep plain-markdown style; only new skill-generated notes
  get AI-first frontmatter

**Next up:**
- Restart session so `_CLAUDE.md` + SessionStart hook take effect
- Sprint 1 continues: issues #7 (auth) / #8 remaining under epic #5

**Refs:** github.com/eugeniughelbur/obsidian-second-brain

## 2026-07-12 — Sprint 1: Docker environment + CI (#8)

**Agent:** Claude (Opus 4.8, Claude Code)
**Branch:** `feat/8-docker` (off `develop`)
**Did:**
- `backend/Dockerfile` — multi-stage `uv` build, non-root runtime user, venv on PATH
- `docker-compose.yml` (repo root) — api + `postgres:16-alpine` + `qdrant:v1.12.4`;
  Postgres healthcheck + named volume `pgdata`; api waits for healthy DB, runs
  `alembic upgrade head` then serves; api healthcheck via urllib on `/health`
- `backend/.dockerignore`; `GET /api/v1/health/ready` readiness probe (DB `SELECT 1`
  → 200/503) in `api/v1/health.py`
- `.github/workflows/ci.yml` — CI on push/PR to develop: `uv sync` + `ruff` + `pytest`
  (suite uses SQLite, so CI needs no Postgres service)
- README: documented the compose workflow + probes; refreshed layout/planned sections
- 14 tests pass (added readiness test), ruff clean, `docker compose config` valid

**Decisions made:**
- Qdrant runs as a container now but the app has **no** qdrant client dependency yet
  (YAGNI — wired when the RAG pillar lands); readiness checks DB only
- CI added now that real code/tests exist (previously deferred per project-memory)

**Next up:**
- **Manual verification pending:** live `docker compose up --build` (not run in-session)
- #10 Frontend (React/Vite) — last Sprint 1 child

**Refs:** PR (feat/8-docker → develop); Issue #8 (parent #5)

---

## 2026-07-12 — Sprint 1: Authentication module (#7)

**Agent:** Claude (Opus 4.8, Claude Code)
**Branch:** `feat/7-auth` (off `develop`)
**Did:**
- Built #7 auth: bcrypt password hashing + JWT (python-jose, HS256) issue/verify
  in `core/security.py`; `POST /api/v1/auth/register` + `/login`
  (OAuth2PasswordRequestForm); `get_current_user` + `require_role` RBAC factory
  in `api/deps.py`; `/users/me` (any auth) + admin-only `GET /users` (403 demo)
- Added `schemas/auth.py` (Pydantic contracts), `repositories/user.py`
  (`get_by_email`), `services/auth.py` (AuthService: register/authenticate);
  JWT settings + prod-secret guard in `config.py`
- **No new migration** — `users.role`/`hashed_password` already shipped in #6
- Tests: 13 pass (8→13 auth incl. register, login, token expiry→401, RBAC
  403/200, case-insensitive email). File-backed SQLite fixture (NullPool) so the
  suite needs no Postgres
- Ran `ecc:security-reviewer` on the diff: no rookie mistakes; fixed 2 HIGH
  (JWT-secret fail-open guard hardened; constant-time login to stop timing-based
  user enumeration) + email normalization + unused-claim guard comment

**Decisions made:**
- **Deviation from #7 spec:** dropped `passlib` for direct `bcrypt` — passlib
  1.7.4 is unmaintained and hard-breaks against bcrypt 5.x. Kept `python-jose`
  for JWT (sound on HS256). 72-byte secret truncation handled explicitly
- Registration cannot self-assign `role` (no `role` field on `UserCreate`) —
  privileged roles provisioned out-of-band; anti-privilege-escalation
- Authorization always re-reads role from DB, never trusts the JWT `role` claim

**Next up:**
- Deferred security follow-ups (pre-deploy, not #7): rate-limiting on
  `/login`+`/register`; consider swapping `python-jose`→`PyJWT`
- #8 Docker, #10 Frontend

**Refs:** PR (feat/7-auth → develop); Issue #7 (parent #5); depends on #6

---

## 2026-07-11 — Sprint 1: GitHub hygiene + FastAPI skeleton (#9) + DB schema (#6)

**Agent:** Claude (Opus 4.8, Claude Code)
**Branch:** `feat/9-fastapi-setup`, `feat/6-db-schema` (both merged to `develop`)
**Did:**
- GitHub hygiene: normalized label taxonomy (created `epic`/`sprint-1`/`auth`/
  `security`/`infra`, deleted junk `ai`/`high priority`/`needs Review`/dupes),
  relabeled + prioritized issues #5–#10, wrote acceptance-criteria bodies into
  #5–#9, linked #6/#7/#8/#9 as native sub-issues of epic #5 (milestone already set)
- Built #9 FastAPI skeleton in `backend/`: `create_app()` factory, pydantic-settings
  config (`MEDINTEL_` prefix), logging, versioned `GET /api/v1/health`, pytest +
  TestClient, ruff config, README. `uv`-managed (`uv.lock` committed)
- Verified: ruff clean, pytest green, live uvicorn serves `/api/v1/health` 200
- Ran `/code-review` (high): approved, no blockers; one CORS advisory deferred to #7
- Built #6 Database Schema: 6 async SQLAlchemy 2.0 models (User/Conversation/
  Message/Document/Embedding/Citation) with UUID PKs + audit-timestamp mixins,
  `get_db()` async session, generic `BaseRepository`, async Alembic + initial
  migration, **ADR-013** (ORM/migrations) + wiki synced
- Verified #6 vs live Postgres 16 (ephemeral docker): upgrade→downgrade→upgrade
  idempotent, `alembic check` no drift. Caught + fixed a real bug — autogenerate
  left PG enum types orphaned on downgrade, breaking re-upgrade; downgrade now
  drops them explicitly
- Merged PR #21 (#9) and PR #22 (#6) to `develop` (rebase, linear); closed #9/#6;
  epic #5 at 2/4 sub-issues
- Wired `ECC_DISABLED_HOOKS=pre:edit-write:gateguard-fact-force` into gitignored
  `.claude/settings.local.json` (GateGuard fact-force gate; effect next session)

**Decisions made:**
- Python tooling: **uv + pyproject.toml** (over Poetry/pip)
- Execution: **one PR per issue** off `develop`, report-only (Som approves merges)
- ORM/migrations: **SQLAlchemy 2.0 async + Alembic** — ADR-013 (Accepted). UUID PKs,
  audit timestamps, repository pattern; Alembic URL from settings (no creds in repo)
- StrEnum + PEP 695 generics (target py3.12); deferred `services/` until #7 (YAGNI)

**Next up (holding per Som):**
- #7 Auth (JWT/bcrypt/RBAC) off updated `develop`, then #8 Docker, #10 Frontend
- GitHub Projects link pending — token needs `read:project` scope
  (`gh auth refresh -s read:project,project`)

**Refs:** PR #21, #22; Issues #5/#6/#7/#8/#9; ADR-013; commits ffc1c24, cb853c9

---

## 2026-07-09 — Universal agent context + NHS impact analysis

**Agent:** Claude (Cowork)
**Branch:** `develop`
**Did:**
- Added `.agents/AGENTS.md` (career/financial context, UK target roles, visa
  justification) as mandatory first-read for all agents
- Added `.ai/llm-wiki/05_real_world_impact.md` (NHS readmission ROI, market
  gap, competency map, resume bullets)
- Updated `04_domain_knowledge.md` (NHSX/GDPR/NICE/ICD, NHS programmes),
  `index.md` (registered new page + reading guide), `BOOTSTRAP.md`
  (AGENTS.md now required first read)
- Updated `project-context.md` / `project-memory.md` with career context
  cross-refs

**Refs:** commit d52e21f

---

## 2026-07-08 — GitHub hygiene pass (pre-Sprint 1)

**Agent:** Claude (Sonnet, VS Code extension)
**Branch:** `develop`
**Did:**
- Installed GitHub CLI (`gh` 2.96.0, was missing) via winget; authenticated via
  browser device flow (`gh auth login --web`) as `SubhranshuPan`
- Audited GitHub state: labels (30+, already good coverage), milestones
  (Sprint 0–5 + v1.0), issues (10 total — 4 closed docs issues, 6 open under
  Sprint 1: #5 Backend Foundation, #6 DB Schema, #7 Auth Module, #8 Docker Env,
  #9 FastAPI Setup, #10 Frontend Init)
- Published GitHub Release for existing `v0.1.0` tag (was tagged but never
  released): https://github.com/SubhranshuPan/medintel-ai/releases/tag/v0.1.0
- Closed Milestone #1 "Sprint 0 - Documentation" (8/8 issues closed, was
  still showing open)
- Deleted stale local branch `sprint-1/backend-foundation` — it predated the
  housekeeping commits on `develop` (README/LICENSE/CODEOWNERS rewrite, PR #19)
  and would have deleted those files if merged as-is; confirmed with human
  before deleting, never pushed to origin so no remote cleanup needed

**Decisions made:**
- `sprint-1/backend-foundation` is gone — start a fresh branch off current
  `develop` when Sprint 1 work actually begins, don't try to resurrect it
- No CI workflow added yet (`.github/workflows/` still empty) — deferred
  intentionally since `backend/` and `frontend/` are still empty scaffolds
  (`.gitkeep` only); add CI once there's real code/tests to run

**Next up:**
- Sprint 1 (Backend Foundation: FastAPI setup, DB schema, auth module, Docker)
  is real multi-file architecture work. Per this repo's `CLAUDE.md` model-routing
  table, that requires `/model` → Opus → `/plan` first, not direct Sonnet
  execution. Do the planning pass before writing backend code.
- Once Sprint 1 code lands, add `.github/workflows/` CI (lint + test, Python
  backend / Node frontend)
- Tag + release `v0.2.0` (or similar) when Sprint 1 closes, same pattern as
  this session's `v0.1.0` release

**Refs:** Milestone #1, Issues #5–#10, Release v0.1.0

---

## 2026-07-05 — AI workspace memory vault initialized

**Agent:** Claude
**Branch:** main (drafted locally, not yet committed)
**Did:**
- Reviewed full `.ai/` workspace (BOOTSTRAP.md, README.md, agents/, rules/, llm-wiki/)
- Drafted initial content for `project-context.md`, `project-memory.md`, and this file,
  sourced from existing `llm-wiki/` pages — no new decisions invented
- Confirmed branch strategy and conventional-commit convention from `rules/git.md`

**Decisions made:**
- Vault update process: agent drafts a session-history entry at end of session;
  human reviews and commits (no direct agent push)

**Next up:**
- Review and commit these three files
- Populate `04_domain_knowledge.md`-adjacent pages (05–15) in `llm-wiki/` as those
  areas of the project develop
- Start logging real session entries above this line going forward

**Refs:** —

---

## 2026-07-05 — Five-pillar scope rewrite (Sprint 0 close-out)

**Agent:** human + Claude
**Branch:** `docs/sprint0-scope-expansion`, `docs/scope-v2-five-pillars` (merged via PR #14, #16, #17)
**Did:**
- Rewrote PRD/TRD/APP_FLOW and PROJECT_SCOPE around the five-pillar platform
  (Patient Data Platform, Clinical Analytics, ML Engine, AI Decision Support, Reporting)
- Deleted `01A_Requirements_Matrix.md` (superseded by v2 scope docs)
- Added ADR-009 (dataset versioning), ADR-010 (ML model serving),
  ADR-011 (SHAP explainability), ADR-012 (reporting/export); all Accepted
- Added `.ai/playbooks/daily-workflow.md`; gitignored `.claude/`

**Decisions made:**
- AI Decision Support (original RAG/chat scope) is now one pillar among five,
  not the whole product

**Next up:**
- Sync `.ai/llm-wiki/` pages to the five-pillar scope
- Rebase `sprint-1/backend-foundation` onto fresh `develop` before Sprint 1

**Refs:** PR #14–#17, ADR-009–ADR-012

---

## 2026-07-06 — Repo housekeeping & wiki sync

**Agent:** Claude (Cowork)
**Branch:** `docs/wiki-sync-and-line-endings` (off `develop`)
**Did:**
- Pulled `develop` and `main` to match origin; deleted merged local branches
  (`docs/sprint0-scope-expansion`, `docs/init-memory-vault`, `docs/github-setup`)
- Added `.gitattributes` (`* text=auto eol=lf`) to stop recurring CRLF noise
- Synced `llm-wiki/` (overview, architecture, tech stack, domain knowledge, index)
  to the five-pillar scope and ADR-009–012
- Updated this vault (session history, project context)

**Decisions made:**
- LF enforced in repo and working tree via `.gitattributes`

**Next up:**
- Push branch and open PR to `develop`
- Write real `README.md`, add `LICENSE`, fix CODEOWNERS placeholder
- Rebase `sprint-1/backend-foundation` onto fresh `develop`

**Refs:** —

---

## 2026-07-07 — Repo housekeeping (README, LICENSE, CODEOWNERS)

**Agent:** Claude (Cowork)
**Branch:** `chore/repo-housekeeping` (off `develop`)
**Did:**
- Pulled `develop` to origin (PR #18 merge); deleted merged local branches
  (`docs/wiki-sync-and-line-endings`, `docs/scope-v2-five-pillars`)
- Wrote real `README.md` (five pillars, tech stack, repo structure, status)
- Added MIT `LICENSE` (2026 Subhranshu Pan)
- `CODEOWNERS`: replaced `@YOUR_GITHUB_USERNAME` placeholder with `@SubhranshuPan`;
  removed redundant `.github/.gitkeep`
- `llm-wiki/03_repository_structure.md`: added missing `data/` and `experiments/`
- `project-memory.md`: recorded CRLF/line-endings gotcha under Known Gotchas

**Decisions made:**
- MIT license adopted for the repo
- Deferred: rebase of `sprint-1/backend-foundation` (kept as-is per Som)

**Next up:**
- Rebase `sprint-1/backend-foundation` onto fresh `develop` before Sprint 1
- Delete stale remote branch `chore/repo-housekeeping` after merge cleanup
- Start Sprint 1 (backend foundation)

**Refs:** PR #19 (merged to `develop` 2026-07-08)
