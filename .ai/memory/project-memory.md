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

---

## Open Questions / Decisions Pending

- **CI workflow timing:** RESOLVED for backend — `.github/workflows/ci.yml`
  landed in #8 (2026-07-12): ruff + pytest on push/PR to `develop`,
  `working-directory: backend`. **Frontend CI still pending** — add a Node
  lint/build job when the frontend gains real code beyond the #10 scaffold.

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
