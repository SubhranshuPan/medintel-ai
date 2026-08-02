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
  `passlib` — 1.7.4 is unmaintained and breaks against bcrypt 5.x), **`PyJWT`**
  HS256 for JWT (2026-08-02, #26 — replaced `python-jose`, whose only remaining
  role was dragging in `ecdsa`, carrying an unfixed Minerva timing CVE we never
  needed since signing is HMAC). Authorization re-reads role from DB every
  request (JWT `role` claim is informational only). Registration never sets role
  (no privilege self-escalation). JWT secret from `MEDINTEL_JWT_SECRET`; startup
  refuses the placeholder/weak secrets outside development/test, and
  `MEDINTEL_ENVIRONMENT` now defaults to `production` so an unset value fails
  closed rather than silently exempting a deployment from that check.
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
- **Data validation = `pandera`** (2026-07-13, Sprint 2 planning; written up as
  ADR-014 on 2026-07-14, ahead of #33): resolves the TRD's open
  `pandera`/`great-expectations` choice.
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
- **Release tagging = annotated semver tags on `develop`** (2026-07-14, v0.2.0):
  `git tag -a vX.Y.Z` + `gh release create`. Tags are cut on `develop`, not `main`
  — `main` stays untouched until a first-draft product exists (see the branch
  policy in `CLAUDE.md`). Minor bump for scope/architecture milestones, not just
  shipped code: `v0.2.0` marks the full-scope ML platform adoption (docs only, no
  runtime change). Releases link the `v(N-1)...vN` compare view for the changelog.
- **Every commit goes through a PR — including bookkeeping** (2026-07-14, PR #42):
  no direct pushes to `develop`, no "too small for a PR" category. `.ai/memory/*`
  updates, doc touch-ups, and scope-status edits all get a feature branch + PR like
  any other change. Supersedes the older reading of the Session-End Checklist, which
  implied bookkeeping could be committed straight to `develop` (that's how `b42c1fe`
  slipped through). Writing the memory entry is still unprompted; *landing* it isn't.
- **Milestone `Platform Vision & Architecture` (#8)** (2026-07-14): the home for
  cross-cutting scope/vision/architecture work (ADRs, core specs) that isn't tied
  to a single sprint. Don't file this kind of work under a Sprint milestone —
  Sprint milestones (#3–#7) track sprint-scoped delivery only.
- **Frontend UI component/animation stack landed** (2026-07-25, PR #56;
  written up as ADR-020): shadcn/ui, Animate UI, Aceternity UI, Motion, and
  Lenis — supersedes the 2026-07-12 entry above that deferred shadcn/ui
  "until a feature screen needs it." `inspira-ui`, originally requested
  alongside Animate UI/Lenis, was swapped for Aceternity UI — inspira-ui is
  Vue/Nuxt-only and cannot run in this React 19 stack (ADR-002). Approved
  libraries are documented as a project skill
  (`.claude/skills/frontend-animation-libs/SKILL.md`, tracked via a
  `.gitignore` exception since `.claude/` is otherwise fully ignored) so
  future frontend work defaults to these instead of hand-rolled animation.
  Components are copy-pasted into `frontend/src/components/` via the shadcn
  CLI, not opaque npm deps — full rationale/alternatives in ADR-020.
- **Documentation-sync passes for someone else's merged PR still go through
  a PR** (2026-07-25): PR #56 (frontend UI polish) shipped with "No
  documentation changes required" checked, leaving ADRs/TRD/`.ai/`
  unsynced. Catching that gap afterward doesn't get a `develop` exception —
  same branch + PR requirement as any other change (2026-07-14 entry
  above).
- **Sprint 3 sequencing — knowledge layer before ranking layer
  (2026-07-25):** Sprint 3 builds the knowledge-aware layer (typed
  `knowledge_nodes`/`knowledge_edges` in PostgreSQL, provenance and
  supersession, query planner, four typed retrieval tools, grounded
  generation with abstention, evaluation harness). ADR-017's ranking layer
  (ColBERT, BM25, RRF, cross-encoder, temporal decay) moves to Sprint 4.
  Reason: ranking upgrades over an unstructured corpus reorder results that
  are already wrong — supersession, exceptions and multi-hop composition are
  properties of the data model, not the ranker. **This is sequencing, not
  descoping** — ADR-017 stands unamended and Sprint 4 implements it in full.
  Spec: `docs/superpowers/specs/2026-07-25-sprint-3-knowledge-aware-rag-design.md`;
  epic #58, children #59–#68.
- **Anthropic as LLM provider does not override the multi-provider rule
  (2026-07-25):** ADR-022 (accepted 2026-07-27, #59) selects Claude — Haiku 4.5 for bulk
  ingestion extraction, Sonnet 5 for grounded generation. It still goes
  through the LangChain orchestration layer (ADR-005), never a hardcoded
  provider call inside a service. The "never hardcode a single provider"
  convention above is about the call site, not the choice.
- **Reviewer agents are vendored, not plugin-supplied (2026-07-25):** the `ecc`
  plugin loaded 67 agents and 277 skills into every session so that we could
  use eight reviewers. It is now disabled; those eight live in
  `.claude/agents/` and are invoked by **bare name** — `code-reviewer`,
  `fastapi-reviewer`, `react-reviewer`, `python-reviewer`, `database-reviewer`,
  `healthcare-reviewer`, `security-reviewer`, `mle-reviewer` — with no `ecc:`
  prefix. Anything written before this date that says `ecc:<agent>` is stale.
  `.gitignore` re-includes `.claude/agents/` (as it already did for
  `.claude/skills/`), so these eight are tracked and present in a fresh clone —
  they are a point-in-time copy of ECC v2.0.0 (MIT) and do not auto-update;
  provenance and refresh steps are in `.claude/agents/README.md`. The rest of
  `.claude/` (`launch.json`, `settings.local.json`, `commands/`) stays
  machine-local.

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
- **The GitHub *MCP* token is read-only; the `gh` CLI token is not (2026-07-14):**
  `mcp__github__create_pull_request` fails with `403 Resource not accessible by
  personal access token`, and a prior session wrongly generalized that into "no
  push credentials in this sandbox" and hand-wrote manual steps for Som. Wrong.
  `git push` and `gh` (authenticated as `SubhranshuPan` via keyring, `gho_*`) both
  work fine. **Use `gh` for all writes** (PR create/merge, labels, milestones,
  releases); use the GitHub MCP for reads only. Before claiming an operation is
  impossible, test it — don't infer a credential gap from one tool's 403.
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
- **`BaseHTTPMiddleware` deadlocks against a request's own DB session
  (2026-07-13, #32):** `call_next()` runs the downstream app in a spawned task
  and can return before that task's `get_db` session has actually closed. In
  the test suite, `AuditLogMiddleware` opening a *second* SQLite connection at
  that point deadlocked against the still-open one (consistent 30s hang on the
  busy timeout, not a transient flake). Fixed by rewriting the middleware as a
  raw ASGI middleware (`__call__(scope, receive, send)`, awaiting the inner app
  directly in the same task) — the standard fix for this class of Starlette
  issue, not a test-only workaround. Any future ASGI middleware that opens its
  own DB session per request should use this pattern, not `BaseHTTPMiddleware`.
- **Unanchored `.gitignore` patterns match at every directory depth
  (2026-07-13, #32):** `backend/.gitignore` had a bare `storage/` line meant to
  ignore the *runtime* upload directory (`backend/storage/datasets`, from
  `LocalObjectStore`'s `storage_dir` setting). Git matched it against
  `backend/app/storage/` too — the actual `ObjectStore`/`LocalObjectStore`
  *source package* — so it was silently excluded from every commit since #32.
  Local dev/tests kept passing because the files still existed untracked on
  disk; a fresh CI checkout had no `app/storage/` at all, which is what broke
  (ruff's import-sort couldn't even classify the import as first-party).
  Caught by cloning the branch fresh and running `uv sync --frozen` +
  `ruff check .` outside the working tree — **when CI fails but the local repo
  passes, reproduce in an actual fresh clone before trusting any suggested
  fix**, don't assume the working tree matches what's committed. Fix: anchor
  gitignore patterns meant for a specific path with a leading slash
  (`/storage/` matches only `backend/storage/`, not `backend/app/storage/`).
- **`gh pr create` without `--base` targets the repo's *default* branch, not
  `develop` (2026-07-15, PR #44):** this repo's default branch is `main`.
  Omitting `--base` on `gh pr create` silently opened a PR against `main` —
  breaking the never-merge-to-main rule and also silently skipping CI (the
  workflow's `pull_request` trigger only matches `branches: [develop]`, so
  zero runs were queued and nothing looked broken until `gh run list` came
  back empty). Fixed with `gh pr edit <n> --base develop`, but that alone
  doesn't trigger CI — retargeting the base fires an `edited` event, and the
  workflow only listens for the default `opened`/`synchronize`/`reopened`
  set. Had to `gh pr close` + `gh pr reopen` to force a fresh `pull_request`
  event. **Always pass `--base develop` explicitly on every `gh pr create` in
  this repo** — don't rely on the CLI's default.
- **Any endpoint returning patient-data-derived content needs an ownership
  check, not just authentication (2026-07-15, #33 code review):** `POST
  /datasets/{id}/validate` required a valid bearer token but never checked
  the token's owner against the dataset's `owner_id`, so any authenticated
  user could pull another user's `validation_report` — which can contain raw
  row values via pandera's `failure_cases` — by guessing/enumerating a
  dataset id. Caught in code review before merge, not by a test written in
  advance. Fixed at the service layer (`revalidate_latest(..., requester:
  User)` raises a dedicated `DatasetForbiddenError` → 403), establishing the
  pattern #35 will need for its own owner-only delete check. **"requires
  auth" and "requires *this* user's authorization" are different checks —
  audit for both on every new patient-data endpoint, not just the first.**
- **CORS default targeted the wrong dev port (2026-07-24, #36):**
  `cors_origins` defaulted to `http://localhost:3000` — a Sprint 1/CRA-era
  assumption that outlived it; the frontend has been Vite on port 5173 since
  #10. Every browser request was silently blocked, and the failure mode is
  misleading: a CORS-blocked `fetch()` rejects with a plain `TypeError`
  *before* the response body is readable, so the app's own `ApiError`
  handling never even sees it — it just looks like a generic, detail-less
  failure. If a frontend error is suspiciously generic (no `ApiError.detail`)
  and the backend logs show the request actually succeeded, check CORS
  first, not the error-handling code.
- **Non-root container + fresh named volume = root-owned mount
  (2026-07-24, #36):** the api image runs as a non-root `app` user, but the
  `datasets` docker-compose named volume mounted at `/app/storage` was
  created root-owned on first use, so the app user couldn't write to it
  (`PermissionError` on upload, surfaced as a 503). Docker seeds a *new*
  named volume's ownership from whatever already exists at that path in the
  image — nothing existed there, so it defaulted to root. Fix: pre-create the
  mount path with the right ownership in the Dockerfile *before* it's used as
  a mount point. An already-created volume won't retroactively reseed —
  `docker volume rm` it once after the Dockerfile fix.

---

## Risk Register

- **MIMIC-III credentialing (opened 2026-07-14, ADR-018):** Models 1–2 need
  real clinical training data; access requires a PhysioNet account + CITI
  Program "Data or Specimens Only Research" course completion + a
  credentialed-access application + signed Data Use Agreement. This is an
  external process (days to a few weeks) outside the project's control and
  sits on the critical path for validating Models 1–2 against real data.
  **Immediate action: start the PhysioNet account + CITI course today**,
  independent of and in parallel with all other Sprint work — nothing else
  in Model 1/2 development blocks on starting it. Until access is granted,
  model development proceeds against synthetic data (already the default
  per the project's GDPR-aware stance) so Sprint velocity doesn't stall.
  Re-validate models against MIMIC-III once access lands — re-running an
  already-built pipeline, not new development. Owner: Som. Status: not yet
  started as of 2026-07-14.
- **Full-scope platform timeline risk (opened 2026-07-14):** the platform
  vision (`docs/00_VISION_ML_PLATFORM.md`, adopted 2026-07-14) commits to 3
  ML models, full MLOps (continuous training, A/B testing, monitoring), a
  7-stage RAG pipeline, and HIPAA/GDPR compliance tooling — a materially
  larger scope than the original 5-pillar MVP, against an unchanged
  November 2026 interview-readiness target and an MSc starting September
  2026 that will reduce available hours. This is flagged, not resolved:
  per `CLAUDE.md`'s binding scope mandate, the response to a timeline
  conflict is to surface it explicitly (this entry) rather than silently
  descope. If velocity data through Sprint 3–4 shows the full scope isn't
  achievable by November, that's a decision for Som to make explicitly,
  informed by real progress data — not something to pre-empt now.
- **NICE guideline licensing (opened 2026-07-25, Sprint 3 #61):** NICE
  clinical guideline content is licensed, and bulk scraping nice.org.uk very
  likely breaches their terms of use. The Sprint 3 corpus depends on
  guideline content specifically because it's the only source that exercises
  supersession and comorbidity-conditional exceptions — the architecture's
  central claim. Resolve at the ingestion issue (#61), not at evaluation
  (#67): obtain syndication API access, hand-curate a small subset with
  attribution, or fall back to a synthetic guideline corpus with
  deliberately-authored supersessions. Owner: Som. Status: open.
- **Sprint 3 ingestion LLM cost (opened 2026-07-25, #63):** entity/edge
  extraction is one LLM call per structural unit across the whole corpus.
  Haiku 4.5 keeps unit cost low, but a corpus-size cap and a recorded cost
  estimate are a precondition for starting #63 — not something to discover
  from the bill afterwards.

---

## Open Questions / Decisions Pending

- **CI workflow timing:** RESOLVED for backend — `.github/workflows/ci.yml`
  landed in #8 (2026-07-12): ruff + pytest on push/PR to `develop`,
  `working-directory: backend`. **Frontend CI still pending** — scheduled into
  Sprint 2 **#36** (Node `npm ci` + `npm run build`, which already typechecks via
  `tsc --noEmit`), landing with the first real frontend screen.
- **Documentation rollout for the expanded platform vision — RESOLVED
  2026-07-14:** ADR-015–019 written; `02_TRD.md`, `00_PROJECT_SCOPE.md`,
  `01_PRD.md`, `03_APP_FLOW.md`, `05_BACKEND_DESIGN.md` all updated;
  `06_ML_MODELS.md` through `12_MONITORING_ALERTS.md` all written. Full
  detail across four `session-history.md` entries dated 2026-07-14. Next
  real milestone is implementation (Phase 1 of `01_PRD.md` §11), not more
  documentation — don't re-open this as a pending item.

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
