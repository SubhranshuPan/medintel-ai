# Session History

> Append-only log, most recent session on top. One entry per working session.
> Keep entries brief — link to the PR/issue/ADR for detail rather than duplicating it.

---

## 2026-07-24 — Sprint 2 #36 (frontend datasets UI): PR #53 merged — epic #29 scope complete

**Agent:** Claude Code (Sonnet 5)
**Branch:** `feat/36-frontend-datasets` → merged to `develop` via PR #53
**Did:**
- `DatasetsPage`: upload form (client-side `.csv`/50MB guard), dataset list,
  click-to-expand version history, validation failures rendered as readable
  sentences (raw-JSON `<details>` fallback for anything unmapped). Status
  badges are text+color, not color-only.
- `api.ts`: token in `localStorage` + `Authorization` header, `FormData`-safe
  `Content-Type` (was hardcoded to `application/json`, breaking multipart),
  `ApiError.detail` from FastAPI's error body, typed dataset client functions.
- Added `LoginPage` — not in the original plan. No login screen exists
  anywhere in the app (#10 scoped the scaffold to a health-check placeholder
  only); #36's own DoD ("auth token attached", "works end-to-end") is
  impossible without one. Flagged as the minimum enabler in the PR, not
  scope creep. Registration stays out of scope.
- Frontend CI job added (`setup-node` → `npm ci` → `npm run build`) — CI was
  backend-only until now, carried-forward backlog item from #10.
- Used `ui-ux-pro-max`'s UX checklist (forms/feedback + accessibility
  domains) as a review pass rather than generating a new design system —
  reused the existing teal/slate visual language from #10.
- Self-reviewed inline before commit (no agent swarm): caught and fixed two
  real bugs — `event.currentTarget` reads `null` after an `await` in the
  upload handler (native DOM behavior, not React pooling — fixed by
  capturing the form ref synchronously), and the datasets-list effect fired
  an unauthenticated fetch (wasted 401, discarded error) before the
  login-gate check ran (fixed by guarding the effect on `getToken()`).
- Docker Desktop came up mid-session; ran a real `docker compose up` + Chrome
  pass to verify E2E, which surfaced two **pre-existing** infra bugs (not
  from this PR) blocking upload/login entirely: `cors_origins` defaulted to
  `http://localhost:3000` (stale Sprint 1/CRA assumption — frontend has been
  Vite on 5173 since #10), and the api container's non-root user couldn't
  write to the `datasets` named volume (Docker creates a new named volume
  root-owned unless the mount path already has the right ownership in the
  image). Fixed both (`backend/app/core/config.py`, `backend/Dockerfile`) in
  a follow-up commit on the same PR, since #36's own DoD literally requires
  E2E to work. Confirmed after the fix: register → login → upload a CSV with
  a duplicate row → v1 shows `failed` with the readable reason "duplicate
  rows present" → version history expands correctly.
- Closed #36, synced epic #29 (all children ticked, all DoD items ticked,
  progress line) — **epic #29 scope is now fully complete**, flagged in the
  epic body as ready for Som to close (closing the epic itself is Som's
  call, not part of the routine child-sync).

**Decisions made:**
- `LoginPage` added as necessary infrastructure, explicitly flagged rather
  than silently expanding scope.
- The two infra bugs (CORS default port, storage volume ownership) were
  fixed rather than just reported, because they were the literal blocker for
  #36's own Definition of Done — but flagged clearly as pre-existing (#9/#32)
  in the PR, not silently folded in as if part of the planned frontend work.

**Next up:**
- Epic #29 (Sprint 2 — Patient Data Platform) is complete. Next epic/sprint
  scope not yet defined this session — awaiting Som's direction (Sprint 3 is
  the ML risk-prediction engine per the vision doc's pillar order).

**Refs:** PR #53, issue #36 (closed), epic #29

---

## 2026-07-24 — Sprint 2 #35 (dataset management endpoints): PR #51 merged

**Agent:** Claude Code (Sonnet 5)
**Branch:** `feat/35-dataset-endpoints` → merged to `develop` via PR #51
**Did:**
- Implemented `GET /datasets` (paginated, owner-scoped unless admin),
  `GET /datasets/{id}` (detail + version history), `GET /datasets/{id}/versions`,
  `DELETE /datasets/{id}` (soft delete, audited). Repo/service split respected
  — no ORM queries in the router.
- Factored the owner-or-admin check into one `_check_access` helper and
  reused it in `revalidate_latest`/`clean_latest` (#33/#34), removing
  duplicated inline checks.
- Updated `test_audit.py`: the pre-#35 tests asserted a 405 placeholder for
  `GET /api/v1/datasets` (no GET route existed yet) — now asserts the real
  401/200 behavior against the live endpoint.
- Self-reviewed inline (no agent swarm), same cost-conscious approach as #34.
- Closed #35, synced epic #29 (child checklist, progress line).

**Decisions made:**
- Non-admin list/detail/versions/delete are **owner-scoped**, not just
  auth-gated — same PHI-leak precedent as #33/#34 (`validation_report`/
  `column_names` can carry patient-level content, so a stranger must not
  browse another user's datasets by id or listing).
- Delete = soft delete only (`deleted_at`); documented in the docstring, not
  a new ADR (ADR-009 already covers immutability — this is its consequence).
- `list_for_owner`'s N+1 (one query per dataset for its latest version)
  logged as a `ponytail:` ceiling, not fixed — fine under the 200-row page cap.

**Next up:**
- #36 (frontend dataset upload + list UI, plus the missing frontend CI job)
  is the last child issue in epic #29. Not started — gated on Som's
  go-ahead per standing practice.

**Refs:** PR #51, issue #35 (closed), epic #29

---

## 2026-07-24 — Sprint 2 #34 (cleaning pipeline): PR #49 merged

**Agent:** Claude Code (Sonnet 5)
**Branch:** `feat/34-cleaning-pipeline` → merged to `develop` via PR #49
**Did:**
- Implemented `POST /datasets/{id}/clean` (ADR-009): derives a new
  `DatasetVersion` from the dataset's latest version via a deterministic
  cleaning pass (drop empty rows, strip whitespace, drop duplicate rows);
  parent version's bytes/row untouched. Child records `parent_version_id`,
  `origin=cleaned`, and a `transformation` report. Re-validates the cleaned
  frame and stamps the new version.
- `DatasetService.clean_latest` — owner-or-admin gated, same pattern as
  #33's `revalidate_latest`.
- Self-reviewed the diff inline (no agent swarm, cost-conscious) instead of
  the full 8-angle code-review skill; caught and fixed one test-coverage gap
  (failed→passed flip wasn't asserted) before opening the PR.
- Closed #34, synced epic #29 (child checklist, DoD, progress line).

**Decisions made:**
- Cleaning steps are generic (empty rows / whitespace / duplicate rows),
  not the plan's cohort-specific ones (`normalize_sex`, coerce `age`) —
  `validate()` from #33 is already generic with no fixed-column schema to
  clean against, so this follows that precedent instead of the plan. Flagged
  in the PR, not silently resolved (same pattern as #33).
- No imputation — inventing patient values is a clinical-safety line this
  step doesn't cross (explicit in the module docstring).

**Next up:**
- #35 (dataset management endpoints — list/view/versions/delete) is next in
  build order. Not started — gated on Som's go-ahead per standing practice.

**Refs:** PR #49, issue #34 (closed), epic #29

---

## 2026-07-24 — ADR-001-008 PR shipped + merged; session-history landing

**Agent:** OpenCode (deepseek-v4-flash-free)
**Branch:** `docs/adr-001-008-consequences-rewrite` → merged to `develop` via PR #47
**Did:**
- Ran `git fetch`, `git push`, and `gh pr create` for the
  `docs/adr-001-008-consequences-rewrite` branch — PR #47 opened, reviewed,
  merged by Som, branch deleted.
- Pulled merged `develop`, created this session-history entry.

**Decisions made:** None new — standard bookkeeping.

**Next up:**
- Sprint 2 #34 (cleaning pipeline) still next in build order.

**Refs:** PR #47, commit `179971e` on `docs/adr-001-008-consequences-rewrite`

---

## 2026-07-24 — ADR-001–008 rewritten (Consequences + Context, not just Consequences)

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `docs/adr-001-008-consequences-rewrite` (committed locally, not pushed)
**Did:**
- Ran the morning-briefing steps manually (scheduled task's 9:10 AM run was
  covered separately); found zero repo activity since the 2026-07-17
  entry, so no session-history write was needed at that point.
- Som approved proposed action #2 (rewrite ADR-001–008) and #4 (authorize
  GitHub connector) from that briefing.
- Read all 8 files and found the problem was worse than the 2026-07-17
  walkthrough flagged: not just "Consequences" but Context and Alternatives
  were verbatim copy-pasted across all eight ADRs (e.g. ADR-003's Context
  talked about "a high-performance Python backend," and ADR-002 listed
  "Automatic OpenAPI generation" as a React consequence). Rewrote all 8
  fully — Context, Alternatives Considered, and Consequences — to match the
  ADR-009+ quality bar, with project-specific reasoning for each stack
  choice (FastAPI, React, PostgreSQL, Qdrant, LangChain, Docker, GitHub
  Actions, modular monolith).
- Created branch `docs/adr-001-008-consequences-rewrite` off `develop` and
  committed the rewrite locally. Could not push or open a PR — this
  sandbox has no `gh` CLI and no GitHub push credentials (known limitation,
  see `medintel-mount-git-quirks` memory); gave Som the exact commands to
  push and open the PR from his own terminal.
- Hit the known mounted-repo git quirk again: a stale `.git/index.lock`
  blocked `git add`/`git commit` with "Operation not permitted" until
  cleared via `allow_cowork_file_delete`. Also had to set local (not
  global) `git config user.name`/`user.email` since the sandbox identity
  was unset — verified `.git/config` read back correctly before and after,
  per the standing rule not to write git config blind on this mount.

**Decisions made:**
- None new — this session executed a previously-flagged doc-quality fix,
  it didn't make a new architecture decision.

**Next up:**
- Som to review the diff, push `docs/adr-001-008-consequences-rewrite`,
  and open the PR himself (exact commands given in chat).
- Som to authorize the GitHub connector (`plugin:engineering:github`) via
  Cowork connector settings — sandbox can't run the OAuth flow.
- Sprint 2 #34 (cleaning pipeline) still next in build order, untouched.

**Refs:** local commit `179971e` on `docs/adr-001-008-consequences-rewrite`
(unpushed)

---

## 2026-07-17 — Interview-prep walkthrough (Sprint 0–2) written

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `develop` (working tree only, nothing committed)
**Did:**
- Ran the morning repo briefing (no activity since 2026-07-15, nothing to log
  at that point).
- Som asked for a full, accurate, step-by-step walkthrough of everything
  built so far (Sprint 0 docs/ADRs, Sprint 1 backend foundation, Sprint 2
  #30–#33) for interview prep — what was built, why, and the tech's role.
  Read all 19 ADRs, the full Sprint 1/2 backend source (auth, models, audit
  middleware, object storage, dataset service, pandera validation, CI/Docker),
  and `project-memory.md`/`session-history.md` for the real bug/decision
  narratives, then wrote `.ai/interview-prep/sprint-0-to-2-walkthrough.md`.
- **Flagged a real doc-quality gap while reading the ADRs**: ADR-001–008
  (the core stack ADRs) have generic, copy-pasted "Consequences" sections —
  e.g. ADR-002 (React) lists "Automatic OpenAPI generation" as a consequence,
  which is nonsensical for a frontend framework. ADR-009 onward are genuinely
  detailed. Surfaced this to Som in the walkthrough doc rather than silently
  ignoring it, since it conflicts with the project's "recruiter-readable"
  bar; offered to rewrite 001–008 on request.

**Decisions made:**
- None new — this session is research/writing, not architecture.

**Next up:**
- Rewrite ADR-001–008 "Consequences" sections with real trade-offs, if Som
  wants it prioritized.
- Sprint 2 #34 (cleaning pipeline) is next in the build order — not started.

**Refs:** `.ai/interview-prep/sprint-0-to-2-walkthrough.md` (new, uncommitted)

---

## 2026-07-15 — Sprint 2 #33 (dataset validation): PR #44 merged

**Agent:** Claude (Sonnet 5, Claude Code)
**Branch:** `feat/33-adr-014-validation` → merged to `develop`
**Did:**
- Resumed from a saved cross-day session file (`~/.claude/session-data/2026-07-13-sprint-2-session.tmp`,
  written via the `save-session` skill at the end of the 2026-07-13 session) —
  confirmed `develop` still matched the saved state before continuing.
- Discovered ADR-014 (`docs/architecture/adr/ADR-014-schema-validation.md`) and
  the TRD update were **already merged** from the 2026-07-14 vision-doc rewrite,
  ahead of this issue's implementation. The ADR's decision (generic frame-level
  checks: non-empty, no fully-null column, no duplicate rows/column names) is
  narrower than both `.claude/current_plan.md`'s original fixed cohort schema
  (`patient_id`/`age`/`sex`/`icd_code`) and issue #33's own DoD wording (named
  clinical schema, ICD-code shape, value ranges). Implemented against the ADR —
  the authoritative, already-merged decision — and flagged the discrepancy
  explicitly in the PR description rather than silently picking one.
- Added `app/services/validation.py` (pandera `DataFrameSchema`, `lazy=True`),
  wired it into `DatasetService.create_from_upload` (dispatched via
  `asyncio.to_thread` — CPU-bound sync work off the event loop), and added
  `DatasetService.revalidate_latest` + `POST /datasets/{id}/validate`.
- **Code review caught a real cross-tenant PHI leak before merge**: the new
  `/validate` endpoint had no ownership check, so any authenticated user could
  revalidate and read back another user's `validation_report` — which can
  carry raw row values via pandera's `failure_cases` — by guessing a dataset
  id. Fixed: owner-or-admin only, 403 otherwise (`DatasetForbiddenError`).
  Covered by `test_revalidate_non_owner_is_forbidden`.
- **`gh pr create` bug**: opened [PR #44](https://github.com/SubhranshuPan/medintel-ai/pull/44)
  without an explicit `--base`, which silently targeted the repo's *default*
  branch (`main`) instead of `develop` — violating the never-merge-to-main
  rule and silently skipping CI (the workflow only triggers on PRs against
  `develop`). Caught by checking `gh pr checks`/`gh run list` and noticing
  **zero** CI runs existed for the branch. Fixed with `gh pr edit 44 --base
  develop`, then `gh pr close`/`gh pr reopen` to force a fresh `pull_request`
  event (changing the base via the API alone doesn't trigger the workflow —
  only `opened`/`synchronize`/`reopened` do, and base-retarget is `edited`).
  CI went green afterward. **Always pass `--base develop` explicitly on every
  `gh pr create` in this repo** — logged as a gotcha in `project-memory.md`.
- Merged manually by Som; local `develop` synced, `feat/33-adr-014-validation`
  deleted locally and on GitHub.

**Decisions made:**
- **Docs win over a stale plan when they conflict** (project-memory's own
  existing rule, applied concretely here): `.claude/current_plan.md` was
  written 2026-07-13, before the 2026-07-14 vision-doc rewrite pre-wrote
  ADR-014 with a narrower scope. Implementation followed the merged ADR, not
  the plan text or the issue body.
- **Ownership checks belong in the service layer, not the router** — same
  layering already used elsewhere (`revalidate_latest` takes `requester: User`
  and raises `DatasetForbiddenError`), pre-empting the pattern issue #35 will
  need for its own owner-only delete check.

**Next up:** #34 (cleaning/preprocessing pipeline → new `DatasetVersion`), per
`.claude/current_plan.md`'s build order. Not started — proceeds only on
Som's explicit go-ahead, same as every issue this sprint.

---

## 2026-07-14 — Full-scope docs shipped: PR #41 merged, released as v0.2.0

**Agent:** Claude (Opus 4.8, Claude Code)
**Branch:** `docs/full-scope-ml-platform-vision` → merged to `develop`
**Did:**
- Committed the whole full-scope documentation rollout (accumulated over the
  previous two sessions, still uncommitted in the working tree) as four
  semantic commits on `docs/full-scope-ml-platform-vision`: (1) scope mandate
  + `00_VISION_ML_PLATFORM.md` + ADR-015–019, (2) the five updated core docs
  (Scope/PRD/TRD/App Flow/Backend Design), (3) the seven new specs (06–12),
  (4) the memory log.
- Opened [PR #41](https://github.com/SubhranshuPan/medintel-ai/pull/41)
  (`documentation` + `ml` labels), merged it into `develop` as a merge commit
  (`1a50ebe`) — 22 files, +3909/−287.
- Cut annotated tag **`v0.2.0`** on `develop` and published the
  [GitHub Release](https://github.com/SubhranshuPan/medintel-ai/releases/tag/v0.2.0).
  First tag since `v0.1.0` (67 commits back).
- Created milestone **#8 `Platform Vision & Architecture`** for cross-cutting
  scope/architecture work and assigned PR #41 to it (this work is not Sprint 2).
- Pushed the v0.2.0 bookkeeping commit (`b42c1fe`) **directly to `develop`**,
  which Som flagged. Tightened the policy in response: opened and merged
  [PR #42](https://github.com/SubhranshuPan/medintel-ai/pull/42) (`c5dd7e5`) —
  `CLAUDE.md` now forbids direct pushes to `develop` outright.

**Decisions made:**
- **Release tagging convention** (now in `project-memory.md`): annotated semver
  tags cut on `develop`, not `main`; a minor bump is warranted for a
  scope/architecture milestone even with no runtime change.
- **Milestone taxonomy**: Sprint milestones stay sprint-scoped; cross-cutting
  vision/architecture work goes to #8.
- **Every commit goes through a PR — no exceptions** (PR #42): including
  bookkeeping (`.ai/memory/*`, doc touch-ups). There is no "too small for a PR"
  category, and no direct pushes to `develop`. The old Session-End Checklist
  wording implied bookkeeping could be committed directly; that loophole is
  closed. *Writing* the memory entry stays exempt from report-only autonomy (do
  it unprompted); *landing* it does not (feature branch + PR, Som merges).
- **Git writes go through the `gh` CLI, reads through the GitHub MCP** — also
  now recorded in `CLAUDE.md`, not just project memory.

**Correction to prior session-history:** the earlier claim that this sandbox has
no push credentials was **wrong**. `git push` and the `gh` CLI both work
(authenticated as `SubhranshuPan`). Only the GitHub *MCP* token is read-only
(403 on writes). Use `gh` for writes, MCP for reads. Logged as a gotcha in
`project-memory.md`. Also note ADR-014 was already committed in `1f7fdce`, so it
is **not** part of the v0.2.0 diff despite earlier drafts saying "ADR-014–019".

**Next up:** Unchanged — Sprint 2 backend (#33/#34, dataset validation and
management endpoints) still comes first, then Phase 1 of the ML build
(Model 1 + SHAP + MLflow + core dashboard) per `01_PRD.md` §11. An Opus `/plan`
pass before Phase 1/2 remains the recommendation.

---

## 2026-07-14 — New docs 09–12 written; full documentation rollout complete

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `develop`
**Did:**
- Wrote `09_DATA_PIPELINE.md`: ETL paths (CSV/PDF/HL7-future/MIMIC-III as
  a structurally separate private path), feature engineering mechanics
  (versioned against `dataset_version_id`, computed at training time not
  precomputed), explicit recap that DVC/LakeFS were already rejected by
  ADR-009 (not reopened here), data quality check categories, and the
  MIMIC-III private ingestion path in full (never through the public
  upload endpoint or object store).
- Wrote `10_PATIENT_MANAGEMENT.md`: `Patient`/`MedicalRecord` schema
  rationale (deliberately minimal identity fields — year-only DOB, no
  names, opaque `external_ref`), OCR/extraction/review-queue pipeline,
  medical concept extraction and coding, patient timeline (a read-only
  assembly view, no new entity), and record correction via new-version
  rows (never overwritten) mirroring `DatasetVersion`'s pattern.
- Wrote `11_PRIVACY_COMPLIANCE.md`: opened with an explicit scope
  statement that this is HIPAA/GDPR-*aware* architecture, not
  certification or legal advice — no BAAs, not a covered entity. Covered
  de-identification, encryption, access control, audit logging coverage
  for the new entities (extends the existing middleware, no new
  mechanism needed), GDPR rights (soft-delete pattern reused, hard-delete
  explicitly flagged as not yet built), and named the real tension
  between fairness testing's need for protected attributes and
  re-identification-risk minimization, with a concrete resolution
  (group-level aggregation only, row-level linkage discarded after
  aggregation).
- Wrote `12_MONITORING_ALERTS.md`: concrete Prometheus metric names/types,
  five dashboard specs (system/model/fairness/cost/data-quality), a full
  alert rule table, and an explicit "no real on-call rotation" honesty
  statement (Slack/email, not paging) rather than overclaiming operational
  maturity.
- **This completes the full documentation rollout** from the scope
  adoption two sessions ago: all 4 modified docs + all 7 new docs are
  now written, alongside ADR-014–019 and `00_VISION_ML_PLATFORM.md`.
- Verified all files landed correctly on disk despite several showing
  stale `stat` mtimes (a mount quirk, not a real write failure — see
  `.ai/memory/session-history.md`'s companion note in project memory).

**Decisions made:** None new — this is documentation of mechanisms already
decided in ADR-015–019, worked through to full specification.

**Next up:** Implementation. Per `01_PRD.md` §11's phased build order,
Phase 1 (Model 1 + SHAP + MLflow + core dashboard) is the next actual
coding work — the current Sprint 2 backend work (#33/#34, dataset
validation/management) still comes first since Phase 1 of the ML build
depends on the data platform being usable. Recommend an Opus `/plan` pass
before starting Phase 1/2 implementation given the scope now specified in
`06_ML_MODELS.md`/`07_ML_OPS.md`, per the Model Routing guidance in
`CLAUDE.md`.

**Refs:** `09_DATA_PIPELINE.md`, `10_PATIENT_MANAGEMENT.md`,
`11_PRIVACY_COMPLIANCE.md`, `12_MONITORING_ALERTS.md`, ADR-009, ADR-014,
ADR-016, ADR-018, ADR-019

---

## 2026-07-14 — New docs 06–08 written (ML Models, ML Ops, Evaluation Framework)

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `develop`
**Did:**
- Wrote `06_ML_MODELS.md`: full architecture for all three models —
  problem framing, features, Optuna search space, evaluation targets,
  explainability approach, serving strategy, and known limitations, each
  per model. Explicit note that Model 3 (retrieval) has no SHAP equivalent
  and needs citation-provenance transparency instead — flagged as the
  RAG-appropriate analogue of the explainability requirement, not an
  exemption from it.
- Wrote `07_ML_OPS.md`: the shared machinery all three models sit on
  top of — MLflow run hierarchy, registry lifecycle, continuous training
  trigger types (all four enter the same Celery job, no separate
  "automated" path), monitoring/alerting mechanics (including "missing
  signal" as its own alert class, not just bad values), A/B rollout gate
  mechanics, and cost tracking.
- Wrote `08_EVALUATION_FRAMEWORK.md`: retrieval/generation/prediction
  evaluation metrics and test sets, fairness testing methodology, ablation
  studies, system-level benchmarking (vs. Framingham/CHADS2/PubMed/
  UpToDate), and the continuous weekly evaluation pipeline — explicitly
  distinguished from `07_ML_OPS.md`'s production *monitoring* (this doc is
  pre-deployment/regression evaluation; monitoring is "is production still
  okay"). Repeated the "methodology, not real-world validation" caveat
  once more since it applies to every evaluation number too.

**Decisions made:** None new — this is documentation of mechanisms
ADR-010/015/016/017/019 already decided, worked through to implementation-
level detail.

**Next up:** `09_DATA_PIPELINE.md`, `10_PATIENT_MANAGEMENT.md`,
`11_PRIVACY_COMPLIANCE.md`, `12_MONITORING_ALERTS.md` — the remaining four
of the seven new docs.

**Refs:** `06_ML_MODELS.md`, `07_ML_OPS.md`, `08_EVALUATION_FRAMEWORK.md`, ADR-010, ADR-011, ADR-015, ADR-016, ADR-017, ADR-019

---

## 2026-07-14 — 05_BACKEND_DESIGN.md brought current + extended (schema drift fixed)

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `develop`
**Did:**
- Found `05_BACKEND_DESIGN.md` marked "Frozen v1.0" but still describing
  only the original RAG-chatbot schema — it had never been updated across
  Sprint 1–2 (auth/RBAC, datasets, audit logging) or the five-pillar
  expansion, a bigger drift than the Sprint-status drift caught earlier
  today. Verified actual current schema against `backend/app/models/*.py`
  (User w/ RBAC roles, Conversation, Message, Document, Embedding,
  Citation, Dataset, DatasetVersion, AuditLog) and rewrote §4 to document
  what's real, not what v1.0 assumed.
- Added §5: new entities for the full platform scope — `Patient`,
  `MedicalRecord`, `ModelVersion`, `PredictionLog`, `RiskScore`,
  `TreatmentOutcome`, `ModelMonitoringSnapshot`, `AnnotatedData` — with
  purpose/key-fields per entity and an ER diagram, reconciling naming
  against `02_TRD.md`'s earlier generic sketch (`ModelVersion`/
  `PredictionLog` are now the authoritative names).
- Added ML data-flow diagram (train → Optuna → MLflow → staging → A/B gate
  → production → monitoring → retrain-on-drift, one pipeline not two) and
  updated the RAG data-flow diagram for the 7-stage retrieval pipeline.
  Added a Migration & Implementation Notes section sequencing the new
  tables against the phased build order in `01_PRD.md` §11.
- This completes all four "significantly modify" docs from the original
  scope-adoption plan (`02_TRD.md`, `00_PROJECT_SCOPE.md`/`01_PRD.md`,
  `03_APP_FLOW.md`, `05_BACKEND_DESIGN.md`).

**Decisions made:** `ModelVersion`/`PredictionLog` (this doc) supersede the
generic `models`/`training_runs`/`predictions` names sketched in
`02_TRD.md` §14 — noted explicitly in both docs so they don't silently
diverge.

**Next up:** the seven new docs, `06_ML_MODELS.md` through
`12_MONITORING_ALERTS.md` — starting with `06_ML_MODELS.md` since the
other new docs (`07_ML_OPS.md`, `08_EVALUATION_FRAMEWORK.md`) reference its
model definitions.

**Refs:** ADR-010, ADR-011, ADR-015, ADR-016, ADR-017, ADR-018, ADR-019, `05_BACKEND_DESIGN.md`

---

## 2026-07-14 — Doc rollout for full-scope platform: TRD, Scope, PRD, App Flow updated

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `develop`
**Did:** (continuation of the same-day scope-adoption session — see the
entry below for the ADR-015–019 background)
- Updated `02_TRD.md` (v2.0 → v3.0): added ML Infrastructure/Continuous
  Training, ML Monitoring & Alerting, and A/B Testing/Rollout as new
  sections; expanded AI Architecture with the 7-stage RAG pipeline;
  expanded Database Design, Security, Testing, Deployment, and Risks
  sections against ADR-015–019.
- Updated `00_PROJECT_SCOPE.md` (v2.0 → v3.0) — **not originally in the
  task list, but added** because `01_PRD.md` explicitly defers to it as
  the single source for NFRs/Success Metrics/Risk Register/Glossary;
  updating PRD without it would have created immediate drift. Notably
  corrected the Assumptions section: v2.0 said "no PHI stored / synthetic
  only," which directly conflicted with ADR-018's real MIMIC-III adoption
  — reworded to be precise about what MIMIC-III is (already de-identified
  under HIPAA Safe Harbor, handled under its DUA) rather than silently
  leaving the contradiction in place.
- Updated `01_PRD.md` (v2.0 → v3.0): added FRs for Model 2 (treatment
  outcome), Model 3 (literature ranker as an evaluated model, not just a
  chat feature), and a new MLOps & Governance cross-cutting FR block.
  Replaced the old "MVP / Stretch" release-plan framing with a 4-phase
  **build sequence** framing — the old wording implied stretch items could
  be dropped, which now contradicts `CLAUDE.md`'s binding scope mandate;
  the new framing is explicit that phasing is not scope-cutting.
- Updated `03_APP_FLOW.md` (v2.0 → v3.0): added flows for cohort
  analysis/disease pattern mining, Model 2 (treatment outcome), continuous
  training/Optuna, A/B rollout governance (including the "not promoted"
  path surfaced to Admin, not silently retried), active learning feedback
  capture, and updated the RAG chat flow for the 7-stage pipeline.

**Decisions made:** None new beyond what ADR-015–019 already decided —
this entry is documentation rollout, not new architecture. One framing
correction: release planning uses "phased build order," never
"MVP/stretch," going forward on this project, to stay consistent with the
binding scope mandate.

**Next up:**
- `05_BACKEND_DESIGN.md` (new entities: Patient, MedicalRecord, RiskScore,
  TreatmentOutcome, ModelVersion, PredictionLog, AnnotatedData, enhanced
  AuditLog).
- Then the seven new docs, `06_ML_MODELS.md` through `12_MONITORING_ALERTS.md`.

**Refs:** ADR-015–019, `docs/00_VISION_ML_PLATFORM.md`, `02_TRD.md`,
`00_PROJECT_SCOPE.md`, `01_PRD.md`, `03_APP_FLOW.md`

---

## 2026-07-14 — Full-scope platform vision adopted; ADR-015–019 written

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `develop`
**Did:**
- Som brought a Copilot-drafted plan to expand MedIntel AI from the 5-pillar
  MVP into a full production ML platform: 3 predictive models (risk
  stratification, treatment outcome, advanced RAG literature ranker), full
  MLOps (MLflow+Optuna continuous training, Prometheus/Grafana monitoring,
  A/B testing), a rigorous evaluation/fairness framework, patient data
  management, and HIPAA/GDPR compliance tooling. Flagged the tension with
  existing constraints (single dev, MSc starts Sept 2026, Nov 2026
  interview target, ADR-locked stack) before acting; Som explicitly chose
  full-scope adoption, a binding CLAUDE.md mandate, and real (credentialed)
  MIMIC-III access over the more conservative phased/synthetic-data options.
- Added a binding scope mandate to `CLAUDE.md` (never silently descope this
  platform) and created `docs/00_VISION_ML_PLATFORM.md` as the durable
  north-star reference, preserving the original plan's detail.
- Wrote 5 new ADRs to ground the new stack/process decisions before the
  PRD/TRD/design docs get rewritten against them: **ADR-015** (continuous
  training + Optuna HPO, extends ADR-010), **ADR-016** (Prometheus/Grafana
  ML monitoring + fairness alerting), **ADR-017** (7-stage advanced RAG
  retrieval pipeline: ColBERT dense + BM25 sparse + metadata filter + RRF
  fusion + cross-encoder rerank + citation graph + temporal decay, extends
  ADR-004/005), **ADR-018** (MIMIC-III as real training data source —
  credentialing process documented, explicitly flagged as a schedule risk
  rather than a formality), **ADR-019** (A/B testing + statistical
  promotion gate + fairness-aware auto-promotion criteria, closes the gap
  ADR-010/015 left open).
- Logged the MIMIC-III credentialing dependency and the overall
  scope/timeline tension as tracked risks in `project-memory.md`'s new
  Risk Register section, each with an explicit owner/next action rather
  than left implicit.
- Updated ADR-count references (14 → 19) in `CLAUDE.md` and `.ai/_CLAUDE.md`.
- **Not yet done** (tracked as open Cowork tasks, same session): updates to
  `01_PRD.md`, `02_TRD.md`, `03_APP_FLOW.md`, `05_BACKEND_DESIGN.md`, and
  new docs `06_ML_MODELS.md` through `12_MONITORING_ALERTS.md`. This is
  deliberately sequenced after the ADRs so those docs aren't written
  against undecided stack choices.

**Decisions made:**
- Full platform scope adopted as binding (not aspirational) — see
  `docs/00_VISION_ML_PLATFORM.md` and `CLAUDE.md`.
- pandera-style "decide via ADR before documenting" convention extended to
  this entire scope expansion — 5 ADRs written before any PRD/TRD edits.
- Real MIMIC-III access chosen over synthetic-only; interim synthetic-data
  fallback while credentialing is pending, so Sprint velocity doesn't stall.

**Next up:**
- Start MIMIC-III credentialing today (PhysioNet account + CITI course) —
  see Risk Register.
- Work through the remaining doc tasks in dependency order: TRD → PRD →
  APP_FLOW → BACKEND_DESIGN → the 7 new docs.

**Refs:** ADR-015, ADR-016, ADR-017, ADR-018, ADR-019, `docs/00_VISION_ML_PLATFORM.md`

---

## 2026-07-14 — Docs drift fix + ADR-014 (schema validation decision)

**Agent:** Claude (Sonnet 5, Cowork)
**Branch:** `develop`
**Did:**
- Morning briefing flagged root `CLAUDE.md` and `.ai/_CLAUDE.md` as stale
  (both still said Sprint 1 "has NOT started"). Corrected both to reflect
  reality: Sprint 1 complete (11/11 issues, closed 2026-07-12), Sprint 2
  (Patient Data Platform) in progress with #30–#32 shipped, #33/#34 next.
  ADR count references bumped 12/13 → 14.
- Wrote **ADR-014** (`docs/architecture/adr/ADR-014-schema-validation.md`),
  resolving the "pandera vs. great-expectations" open item flagged in
  `02_TRD.md` §3 and in the Sprint 2 kickoff playbook. Decision: **pandera**
  — runs in-process against the pandas `DataFrame` already parsed in
  `DatasetService.create_from_upload`, serialises failures straight into the
  existing `validation_report` JSONB column (`app/models/dataset.py`), and
  needs no separate store/checkpoint scaffolding the way great-expectations
  would. Updated `02_TRD.md`'s stack table to point at the decision instead
  of listing it as undecided.
- Did NOT delete the four stale merged branches (`feat/30-dataset-models`,
  `feat/31-audit-logs`, `feat/32-csv-upload`, `fix/object-store-path-traversal`)
  flagged in the same briefing — this sandbox has no GitHub push
  credentials, so branch deletion needs to happen from Som's own terminal.

**Decisions made:**
- ADR-014 accepted: pandera is the schema/data-validation library for the
  Patient Data Platform, unblocking #33. See `project-memory.md` and the ADR
  itself for full rationale.

**Next up:**
- Implement #33 (schema validation) against the two-tier design in ADR-014.
- Delete the four stale remote branches from a terminal with push access:
  `git push origin --delete feat/30-dataset-models feat/31-audit-logs feat/32-csv-upload fix/object-store-path-traversal`

**Refs:** ADR-014, #33, #34, `02_TRD.md` §3

---

## 2026-07-13 — #32 CI failure + path-traversal hardening (post-merge)

**Agent:** Claude (Sonnet 5, Claude Code)
**Branch:** `fix/object-store-path-traversal` (off `develop`, after #32/PR #39 merged)
**Did:**
- PR #39's CI failed on `Lint (ruff)` with an `I001 unsorted import` error in
  `tests/test_datasets.py` that did not reproduce locally. Investigated rather
  than blindly applying the pasted "run `ruff check --fix`" suggestion — local
  `ruff check .` was clean even against the exact failing commit's git blob,
  which meant the working tree didn't match what was actually committed.
- Root cause: `backend/.gitignore`'s bare `storage/` line (added in #32 to
  ignore the runtime upload directory) also matched `backend/app/storage/` —
  the `ObjectStore`/`LocalObjectStore` **source package** — so it was never
  committed since #32. Confirmed via a fresh clone + `uv sync --frozen`
  (ruff couldn't classify the import as first-party because the file
  genuinely didn't exist in the repo; pytest would have hit
  `ModuleNotFoundError` next had lint passed).
- Fixed by anchoring the pattern (`/storage/`) and committing the
  previously-excluded `app/storage/__init__.py` + `object_store.py`
  (commit `a4fe94a`). Verified green against a second fresh clone before
  trusting the real CI run.
- A background security review of the merged #32 commit then flagged a path-
  traversal gap in `LocalObjectStore.get()` (strips `file://`, joins the
  remainder straight into a path with no validation). Not exploitable today
  (only `put()`'s own sha256 output is ever stored/read back), but #33/#34
  will read `storage_uri` off a `DatasetVersion` row and call `get()` on it,
  so hardened now: `get()` rejects any URI whose digest isn't a bare 64-char
  hex string. New `tests/test_object_store.py` (round-trip, dedup, traversal
  rejection). Opened as PR #40 (not merged yet).

**Decisions made:** None new — both are bug fixes, not design changes. Both
new gotchas (BaseHTTPMiddleware deadlock, gitignore anchoring) recorded in
project-memory.md.

**Next up:** PR #40 awaiting merge, then #33 (ADR-014 + pandera validation).

**Verification:**
- Gitignore fix: fresh clone + `uv sync --frozen` + `ruff check .` + `pytest -q`
  — clean/26 passed, matching the real CI run (`29254794515`) that went green.
- Path-traversal fix: `uv run ruff check .` clean, `uv run pytest -q` — 29 passed.

**Refs:** Issue #32, PR #39 (merged), PR #40 (open)

---

## 2026-07-13 — #32: CSV upload endpoint + immutable object storage

**Agent:** Claude (Sonnet 5, Claude Code)
**Branch:** `feat/32-csv-upload` (off `develop`, after #31/PR #38 merged)
**Did:**
- Executed plan steps 13–21 (issue #32) only.
- Added `pandas` dependency + `uv lock`; `storage_dir`/`max_upload_bytes` settings.
- `app/storage/object_store.py`: content-addressed `LocalObjectStore` (sha256
  key, write-once) behind an `ObjectStore` Protocol; `get_object_store` dep.
- `app/schemas/dataset.py`, `app/repositories/dataset.py` (`DatasetRepository`,
  `DatasetVersionRepository`), `app/services/dataset.py` (`DatasetService` —
  size guard, pandas parse for metadata only, schema hash, v1 creation).
- `app/api/v1/datasets.py`: `POST /datasets` — content-type/extension guard
  (415), size cap (413), malformed-CSV (422), enriches the audit row via
  `request.state.audit_resource_id`/`audit_detail`. Registered in `router.py`.
- `docker-compose.yml`/`.env.example`/`.gitignore`: storage volume + config.

**Bugs found and fixed during verification (real bugs, not scope creep):**
- **Deadlock: `AuditLogMiddleware` vs the request's own DB session.** First
  upload test hung for exactly 30s and failed with `sqlite3.OperationalError:
  database is locked`. Root cause: `BaseHTTPMiddleware.call_next()` runs the
  downstream app in a spawned task and can return before that task's `get_db`
  session has actually closed — so the middleware's separate SQLite connection
  deadlocks against the still-open one. Not a test-only artifact: this is a
  documented `BaseHTTPMiddleware` correctness gap. Fixed by rewriting
  `app/core/audit.py`'s `AuditLogMiddleware` as a raw ASGI middleware
  (`__call__(scope, receive, send)`, awaiting the inner app directly in the
  same task) — the standard fix for this class of Starlette issue. No API
  change; `request.state.audit_*` enrichment still works (same `scope["state"]`
  dict backs every `Request` built from that scope).
  test_audit.py updated for a real POST route existing.
- Belt-and-suspenders: added `PRAGMA journal_mode=WAL` +
  `PRAGMA busy_timeout=30000` on the test SQLite engine in `conftest.py`
  (NullPool means every checkout is a fresh connection to the same file).
- `test_audit.py`: GET `/api/v1/datasets` now 405 (route exists, method
  doesn't), not 404 — updated both tests and the module docstring.

**Decisions made:** None new beyond what project-memory.md records.

**Next up:** #33 (ADR-014 + pandera validation) — not started, per scope.

**Verification:**
- `uv run ruff check .` — clean.
- `uv run pytest -q` — 26 passed.
- Skipped the plan's manual `docker compose up --build` + `curl` step — the
  TestClient upload tests already exercise the full endpoint path end-to-end;
  flagging the skip rather than silently omitting it.

**Refs:** Issue #32, epic #29

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

## 2026-07-13 — #31: audit_logs table + audit middleware

**Agent:** Claude (Sonnet 5, Claude Code)
**Branch:** `feat/31-audit-logs` (off `develop`, after #30/PR #37 merged)
**Did:**
- Executed plan steps 7–12 (issue #31) only.
- `app/models/audit.py`: `AuditLog` model (append-only, nullable `actor_id`
  with `ondelete RESTRICT`, `detail` JsonB for endpoint-enriched metadata).
- `app/repositories/audit.py`: `AuditLogRepository` — no `delete` exposed.
- `app/core/audit.py`: `AuditLogMiddleware` — intercepts by path prefix
  (`/api/v1/datasets`), records actor from bearer token (best-effort, never
  raises), status code, resource type/id. Runs its own DB session since it
  can't use FastAPI DI.
- `app/main.py`: registered the middleware *after* CORS (outermost — sees
  final status code).
- Generated `alembic/versions/30d783a96ae4_audit_logs_table.py` (no enums,
  no manual downgrade fix needed).
- `tests/conftest.py`: `client` fixture now monkeypatches
  `app.core.audit.AsyncSessionLocal` to the test session factory (module-level
  singleton, `dependency_overrides` can't reach it — same gotcha class as the
  JSONB one); added `audit_rows()` fixture.
- `tests/test_audit.py`: adapted from the plan's draft since the dataset
  router doesn't exist until #32 — asserts against the 404 an unmatched route
  produces (per the plan's own contingency note), proving prefix-based
  interception and actor capture work independent of the endpoint existing.
  Dropped the literal 403/"successful access" cases (no RBAC-gated route to
  produce them yet); revisit once #32/#35 land.
- `tests/test_models.py`: registry assertion gained `audit_logs` (anticipated
  in the plan's risk list).

**Decisions made:**
- None new beyond what project-memory.md already records (audit-as-middleware,
  module-singleton monkeypatch pattern).

**Next up:**
- #32 (CSV upload + object storage) — not started, per scope.

**Verification:**
- `uv run ruff check .` — clean.
- `uv run pytest -q` — 20 passed.
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` — clean round-trip.

**Refs:** Issue #31, epic #29

---

## 2026-07-13 — #30: Dataset/DatasetVersion models + migration

**Agent:** Claude (Sonnet 5, Claude Code)
**Branch:** `feat/30-dataset-models`
**Did:**
- Executed plan steps 1–6 (issue #30) only, per instruction to stop before #31.
- `app/models/base.py`: added `JsonB = JSONB().with_variant(JSON(), "sqlite")` alias.
- `app/models/dataset.py`: `Dataset` + `DatasetVersion` models, `ValidationStatus`/
  `VersionOrigin` enums, `uq_dataset_version` constraint, self-referential
  `parent_version_id` FK — per ADR-009.
- Re-exported new models in `app/models/__init__.py`.
- Generated `alembic/versions/7a5287c24302_dataset_versioning_tables.py`
  (started Docker Desktop + `postgres` compose service to autogenerate against
  real Postgres); hand-added the enum-drop lines to `downgrade()` (autogenerate
  never emits those, same gotcha as `03bb608557d6`).
- Updated `test_models.py` registry assertion; added `test_datasets.py`
  (uniqueness constraint, version defaults, enum values).
- Fixed a test bug hit during verification: capturing dataset IDs immediately
  after `flush()`, before any `rollback()` — post-rollback ORM attribute access
  triggers an implicit refresh that raises `MissingGreenlet` under asyncio.

**Decisions made:**
- None new — followed the two cross-cutting decisions already recorded in
  project-memory.md (JSONB-on-SQLite, audit-as-middleware for later issues).

**Next up:**
- #31 (audit_logs + middleware) — not started, per scope.

**Verification:**
- `uv run ruff check .` — clean.
- `uv run pytest -q` — 17 passed.
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` — clean round-trip against live Postgres.

**Refs:** Issue #30, epic #29

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
