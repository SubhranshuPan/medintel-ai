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
- **GitHub label taxonomy** normalized 2026-07-11 to: Area (`backend`/`frontend`/
  `ml`/`infra`/`database`/`auth`), Type (`feature`/`docs`/`bug`/`chore`/`epic`),
  Priority (`P0-Critical`..`P3-Low`), Meta (`security`/`sprint-1`). Don't reintroduce
  junk labels (`ai`, `high priority`, `needs Review`). Note: GitHub labels are
  case-insensitive — creating `security` collides with an existing `Security`.

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

- **CI workflow timing:** `.github/workflows/` is intentionally still empty as
  of 2026-07-08 — `backend/` and `frontend/` are `.gitkeep`-only scaffolds with
  no code/tests yet. Add CI (lint + test, Python backend / Node frontend) once
  Sprint 1 produces real code, not before.

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
