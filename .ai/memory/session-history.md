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
