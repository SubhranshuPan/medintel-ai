# Project Memory

> Accumulated decisions, conventions, and known gotchas that aren't in `/docs` yet
> (or that supplement it). Append new entries under the relevant section — don't
> rewrite history. If a decision here contradicts `/docs`, `/docs` wins; update
> this file to match and note the correction.

---

## Conventions Adopted

- RAG/LLM code must go through the existing multi-provider abstraction layer —
  never hardcode a single provider (OpenAI/Anthropic/Gemini) directly into a service.
- Backend follows a repository/service pattern. A new ORM access pattern is a
  deviation and should be flagged explicitly before merging, not introduced silently.
- Architectural decisions get written up as ADRs (not just described in a PR
  description or chat) — see `docs/` for the ADR template/location once established.
- Any code path touching patient data must be flagged for privacy/compliance
  review. Never assume amount of de-identification already applied upstream —
  verify or ask.
- **Python backend uses `uv`** (2026-07-11, Sprint 1 #9): `backend/pyproject.toml`
  + committed `uv.lock`. Not Poetry/pip. Run via `uv run ...`. Settings use the
  `MEDINTEL_` env prefix (pydantic-settings). Lint = `ruff`, tests = `pytest`+`httpx`.
- **One PR per issue** off `develop` for Sprint 1 execution (report-only — Som
  approves merges). Started 2026-07-11.
- **Auth stack** (2026-07-12, #7): direct `bcrypt` for password hashing (NOT
  `passlib` — 1.7.4 is unmaintained and breaks against bcrypt 5.x), `python-jose`
  HS256 for JWT. Authorization re-reads role from DB every request (JWT `role`
  claim is informational only). Registration never sets role (no privilege
  self-escalation). JWT secret from `MEDINTEL_JWT_SECRET`; startup refuses the
  placeholder/weak secrets outside development/test.
- **GitHub label taxonomy** normalized 2026-07-11 to: Area (`backend`/`frontend`/
  `ml`/`infra`/`database`/`auth`), Type (`feature`/`docs`/`bug`/`chore`/`epic`),
  Priority (`P0-Critical`..`P3-Low`), Meta (`security`/`sprint-1`). Don't reintroduce
  junk labels (`ai`, `high priority`, `needs Review`). Note: GitHub labels are
  case-insensitive — creating `security` collides with an existing `Security`.
- **Frontend stack** (2026-07-12, #10): React 19 + TypeScript, **Vite** build,
  **Tailwind CSS v4** (`@tailwindcss/vite`, no `tailwind.config` for base use),
  **React Router 7** — per the TRD-pinned stack, no new ADR. Typed `fetch` client
  in `src/lib/api.ts` (`VITE_API_BASE_URL` + `/api/v1`). Scaffold (#10) is init
  only; Zustand, RHF/Zod, Recharts, shadcn/ui, TanStack Query deferred until a
  feature screen needs them. `tsconfig.json` uses `noEmit` + `tsc --noEmit` in the
  build script (no project references); ESLint deferred (tsc covers a scaffold).
- **Data validation = `pandera`** (2026-07-13, Sprint 2 planning; ADR-014 to be
  written in #33): resolves the TRD's open `pandera`/`great-expectations` choice.
  Schema-as-code in Python, native pandas, structured failure report persisted to
  the `validation_report` JSONB column, no extra infra. great-expectations rejected
  — its Data Context / expectation suites / Data Docs are a second config surface
  beside the ORM; same reasoning ADR-009 used against DVC/LakeFS. Validate with
  `lazy=True` so a clinician sees *all* violations, not just the first.
- **Audit logging is ASGI middleware, not per-endpoint calls** (2026-07-13,
  Sprint 2 #31): a handler-level `audit(...)` is one forgotten line away from an
  unaudited PHI endpoint, and cannot record 401/403 at all (the handler never
  runs). `AuditLogMiddleware` intercepts by path prefix (`/api/v1/datasets`), so a
  new route under an audited prefix is audited by default; endpoints enrich via
  `request.state.audit_detail`. Never put patient-level values in `detail` — only
  metadata (filename, row counts, ids), or the audit table becomes an unaudited
  copy of the data it protects.
- **Dataset deletion is a soft delete** (2026-07-13, Sprint 2 #35): `deleted_at`
  timestamp, never a hard delete. Hard-deleting destroys artifacts referenced by
  audit rows and (later) training runs, breaking the exact traceability ADR-009
  exists to provide. A GDPR erasure request is a separate, deliberate purge that
  must itself be audited — out of Sprint 2 scope.
- **`.ai/` is an Obsidian vault** (2026-07-11): operated by the obsidian-second-brain
  skill (`OBSIDIAN_VAULT_PATH` set globally). `_CLAUDE.md` at vault root is the
  operating manual — read it before vault writes. New skill-generated notes get
  AI-first frontmatter; legacy files (`memory/`, `llm-wiki/`, `rules/`, ...) keep
  plain markdown. Vault ops logged in `.ai/Logs/YYYY-MM-DD.md`. No Daily/People/
  Projects/Boards folders — project workspace, not a life OS.

---

## Known Gotchas

- **Line endings (2026-07-06):** Windows checkouts produced recurring CRLF noise in
  diffs. Fixed via `.gitattributes` (`* text=auto eol=lf`); on sandboxed/mounted
  clones also set `core.filemode false`. Don't trust mode-only or line-ending-only
  diffs — normalize before reviewing.
- **`gh` CLI not preinstalled (2026-07-08):** wasn't on PATH on the Windows dev
  machine. Installed via `winget install --id GitHub.cli -e`, then
  `gh auth login --web`. If a fresh session finds `gh` missing again, that's
  expected on a new machine/container — same two commands fix it.
- **`JSONB` breaks the test suite (2026-07-13):** Postgres is the target, but
  `tests/conftest.py` runs on SQLite, where a bare `JSONB` column fails
  `Base.metadata.create_all`. Declare JSON columns as
  `JSONB().with_variant(JSON(), "sqlite")` (the `JsonB` alias in
  `app/models/base.py`), never bare `JSONB`.
- **Module-level singletons defeat `dependency_overrides` (2026-07-13):** anything
  importing `AsyncSessionLocal` directly (e.g. the audit middleware — middleware
  can't use FastAPI DI) binds it at import time, so tests would hit the developer's
  real Postgres. Such modules must be `monkeypatch`ed in `conftest.py`.
- **GitHub MCP token can't link sub-issues (2026-07-13):**
  `mcp__github__sub_issue_write` returns `403 Resource not accessible by personal
  access token` on `POST /issues/{n}/sub_issues`. The `gh` CLI's own token works —
  use `gh api -X POST repos/<owner>/<repo>/issues/<parent>/sub_issues -F
  sub_issue_id=<id>` (note: the *database id*, not the issue number).

---

## Open Questions / Decisions Pending

- **CI workflow timing:** RESOLVED for backend — `.github/workflows/ci.yml`
  landed in #8 (2026-07-12): ruff + pytest on push/PR to `develop`,
  `working-directory: backend`. **Frontend CI still pending** — scheduled into
  Sprint 2 **#36** (Node `npm ci` + `npm run build`, which already typechecks via
  `tsc --noEmit`), landing with the first real frontend screen.

---

## Important Files for New Agents

- **`/.agents/AGENTS.md`** (added 2026-07-09): Universal developer context file
  containing career goals, financial constraints, UK job market strategy, and
  portfolio objectives. **All AI agents must read this file** before starting
  work. It eliminates the need for the developer to re-explain their situation.

---

## Cross-Agent Notes

This file is shared across AI agents (Claude, ChatGPT, Gemini, OpenCode, etc. —
see `.ai/agents/`). Keep entries tool-agnostic: describe the convention or
constraint, not "Claude did X." Agent-specific working style belongs in
`.ai/agents/<agent>.md`, not here.
