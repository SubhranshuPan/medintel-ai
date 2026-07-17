# MedIntel AI — Sprint 0–2 Walkthrough (Interview Prep)

**Purpose:** a complete, accurate record of everything built so far, in order, with the *why* behind each decision — so you can talk through this project in an interview without hesitating on "why did you choose X" or "walk me through your data model." Written from the actual repo state as of 2026-07-17 (commit `16079ff`, `develop`), not from memory.

**How to use this:** each section covers one piece of work — what it is, why it exists, the tech behind it, and a "how to explain this in an interview" note. The bug/incident write-ups at the end of Sprint 2 are some of your strongest interview material — real production-grade debugging, not tutorial code.

**Honesty check first:** Sprint 0 and Sprint 1 are complete. Sprint 2 is partway done (#30–#33 merged; #34–#36 not started). Nothing from the ML engine, RAG/AI decision support, or reporting pillars has been *built* yet — ADR-010, 011, 012, and 015–019 describe the *planned* architecture for those pillars, adopted as binding decisions, but there's no code behind them yet. Keep that distinction sharp in an interview: describe SHAP, MLflow, Optuna, Prometheus, the 7-stage RAG pipeline etc. as "the architecture I've committed to and can walk through in detail" — not as "what I built," until it actually exists.

---

## 1. Sprint 0 — Documentation & Architecture (complete)

Sprint 0 produced the project's requirements docs (`docs/00`–`04`) and the first 14 Architecture Decision Records (ADRs), later extended to 19. This is the foundation everything else was built against.

### 1.1 The five-pillar scope

MedIntel AI is defined around five pillars: Patient Data Platform, Clinical Analytics Dashboard, ML Risk-Prediction Engine (with SHAP explainability), RAG-based AI Decision Support, and Reporting/Export. This was a deliberate rewrite (2026-07-05) from an earlier, narrower "RAG chatbot" scope — the five-pillar framing is what makes this a *platform* rather than a single-feature demo, which matters for how you position it against NHS/health-tech job specs.

On 2026-07-14 this scope was deliberately expanded further into a full production ML platform (3 predictive models, full MLOps, a rigorous evaluation/fairness framework, patient data management, HIPAA/GDPR compliance tooling) — see §5 below. That expansion is a real, binding decision (written into `CLAUDE.md` as a scope mandate), not aspiration; but be clear in interviews that it's the *target architecture*, and implementation is still at Sprint 2 of the original five pillars.

### 1.2 ADRs 001–008: the core stack

| ADR | Decision | Why (interview framing) |
|---|---|---|
| 001 | FastAPI | Async-native, automatic OpenAPI docs, strong typing via Pydantic — fits a data/ML-heavy backend better than Django's sync-first ORM assumptions. |
| 002 | React + TypeScript | Standard, hireable frontend stack; typed props catch integration bugs with the FastAPI/Pydantic contract early. |
| 003 | PostgreSQL | Relational integrity for clinical/audit data (foreign keys, constraints) where NoSQL's eventual consistency would be the wrong trade-off. |
| 004 | Qdrant | Purpose-built vector DB for the RAG pillar — open-source, self-hostable (no vendor lock-in, no cost, and a self-built pipeline is more interview-demonstrable than a managed service). |
| 005 | LangChain + LangGraph | Orchestration framework for the RAG/decision-support pillar; LangGraph specifically for the multi-stage retrieval graph (§5.4). |
| 006 | Docker | Containerization for reproducible dev/deploy — see §2.4. |
| 007 | GitHub Actions | CI/CD, free for a public repo, integrates directly with the PR workflow already in use. |
| 008 | Modular monolith | One deployable service with clear internal module boundaries, rather than microservices — right-sized for a single-developer project; avoids the operational overhead (service discovery, distributed tracing, network failure modes) that microservices would add without a matching benefit at this scale. |

**Important gap to know about, and to flag as a fix before anyone reviews this repo closely:** ADRs 001–008 currently have generic, copy-pasted "Consequences" sections — e.g. ADR-002 (React) lists "Automatic OpenAPI generation" and "Smaller ecosystem than Django" as consequences, which makes no sense for a frontend framework. This looks like unedited template output. ADRs 009 onward (dataset versioning through the 2026-07-14 platform-vision ADRs) are genuinely detailed and well-reasoned — real trade-off analysis, specific to this project. **Recommend fixing 001–008 before Sprint 2 wraps** — an interviewer who opens one of these files will notice immediately, and it undercuts the "recruiter-readable, interview-defensible" bar the rest of the repo meets. I flagged this in the same investigation that produced this document; happy to draft real content for 001–008 (there's more than enough real reasoning already in `project-memory.md` and the TRD to do this properly) whenever you want to prioritize it.

### 1.3 ADR-009: Dataset Versioning Strategy

This is the ADR that everything in Sprint 2 is built against, so it's worth knowing cold.

**Problem it solves:** ML models are trained against specific datasets. Every trained model and every prediction must be traceable back to the *exact version* of the data used to produce it — for reproducibility, auditability, and honest reporting.

**Decision:** a lightweight, database-backed versioning scheme instead of a dedicated data-versioning tool (DVC, LakeFS, Git LFS, Delta Lake were all considered and rejected). Raw uploaded files are stored as **immutable objects** (local disk in dev, S3-compatible in prod). A `datasets` table and a `dataset_versions` table track metadata for every upload — id, version number, parent version id, schema hash, row count, column list, validation status, uploader/timestamp. Any transformation that materially changes the data produces a *new* version row and a *new* stored object — the original is never overwritten.

**Why not DVC/LakeFS:** they're built for scenarios this project doesn't have — large-scale, multi-team, branching/merging data pipelines. For a single developer working with portfolio-scale clinical CSVs, they add infrastructure and a second tool to operate without buying back a benefit. The trade-off costs you diffing/branching semantics, which is an honest, statable "con" — not a hidden one.

**Interview framing:** this is a strong "explain a build-vs-buy decision" answer. You can explain exactly what you get and give up, and why the trade-off made sense *at this scale* — that's the kind of judgment interviewers are actually probing for, more than the tool choice itself.

### 1.4 ADR-013: SQLAlchemy 2.0 (async) + Alembic

Decided retroactively (written up after Sprint 1 #6 shipped, since it's foundational and hard to reverse).

- **Async engine** via `asyncpg` — one engine + `async_sessionmaker` in `app/core/db.py`; `get_db()` yields a request-scoped session that commits on success, rolls back on error.
- **Typed models** using SQLAlchemy 2.0's `Mapped[...]`/`mapped_column(...)` style.
- Every table gets a **UUID primary key** (non-enumerable — doesn't leak record counts or let someone guess patient IDs by incrementing) and **DB-maintained timestamps**, via shared mixins (`UUIDMixin`, `TimestampMixin`).
- **Repository pattern**: a generic `BaseRepository[ModelT]` is the *only* place that touches the SQLAlchemy session directly — services and API handlers never do.
- **Alembic in async mode**, migration URL sourced from settings (not hardcoded), autogenerate with `compare_type=True`.

**A genuine gotcha worth knowing:** Alembic's autogenerate does not handle PostgreSQL `ENUM` type drops on downgrade — it leaves orphaned enum types that break a subsequent re-upgrade. This was caught by testing `upgrade → downgrade → upgrade` against a live Postgres, not assumed to work. Every migration touching an enum since has a manually-added `downgrade()` step to drop the type explicitly. **This is a great "tell me about a subtle bug" interview answer** — it's a real, documented SQLAlchemy/Alembic limitation, not a beginner mistake, and the fix (test the full migration cycle, not just `upgrade`) generalizes.

### 1.5 ADR-014: pandera for validation

Covered in detail in §3.4 below (it's Sprint 2 work, but decided here). Chosen over great-expectations because great-expectations' Data Context/Checkpoint/Data Docs machinery is a second configuration surface next to the ORM, for a benefit (polished HTML reports) that doesn't map onto the project's compact JSONB `validation_report` column. pandera is in-process, pandas-native, and typed — consistent with the SQLAlchemy typed-model philosophy already in place.

### 1.6 ADRs 015–019: the platform-vision extensions (decided, not yet built)

Adopted 2026-07-14 alongside the full-scope platform expansion. Know these well enough to discuss the *architecture*, but always caveat that none of this is implemented yet:

- **ADR-015 — Continuous training + Optuna:** hyperparameter search logged as nested MLflow runs under an Optuna study; retraining triggered by schedule, data drift (Kolmogorov–Smirnov test), or performance degradation (>3% metric drop) — all through the same Celery job, not a separate "auto" path.
- **ADR-016 — Prometheus + Grafana monitoring:** FastAPI `/metrics` via `prometheus-fastapi-instrumentator`, drift/fairness computed by scheduled jobs and exported as labelled gauges, Alertmanager rules with explicit thresholds (p95 latency, error rate, model metric drop, fairness gap). Explicitly documented as Slack/email alerting, not real on-call paging — an honesty note worth repeating if asked, since overclaiming operational maturity is exactly the kind of thing a good interviewer will probe.
- **ADR-017 — 7-stage RAG retrieval pipeline:** dense (ColBERT) + sparse (BM25) retrieval → metadata filtering → Reciprocal Rank Fusion → cross-encoder re-ranking → citation graph traversal → temporal decay. Built as a LangGraph graph, each stage independently swappable/evaluable. This is meant to demonstrate retrieval-architecture depth well beyond a single-stage embedding-similarity RAG demo.
- **ADR-018 — MIMIC-III as real training data:** synthetic data validates the *pipeline*; MIMIC-III (via credentialed PhysioNet access — CITI training + Data Use Agreement) is what would give the risk models real-world predictive signal. **This is flagged as a genuine schedule risk in `project-memory.md`, not started as of 2026-07-14** — worth checking on, since it's an external process outside the project's control and sits on the critical path for the ML pillar's credibility.
- **ADR-019 — A/B testing / progressive rollout:** deterministic per-patient traffic split between candidate/incumbent model versions, promotion gated on statistical significance (p<0.05, >2% metric improvement) **and** no fairness regression — a candidate that wins on accuracy but widens a fairness gap does not auto-promote.

---

## 2. Sprint 1 — Backend Foundation (complete, 11/11 issues, closed 2026-07-12)

### 2.1 FastAPI skeleton (#9)

`create_app()` factory pattern (not a bare module-level `app`) — keeps construction testable, each test builds an isolated instance. Pydantic-settings config with an `MEDINTEL_` env prefix (`app/core/config.py`), structured logging, a versioned `GET /api/v1/health` endpoint. Tooling: `uv` (not Poetry/pip) with a committed `uv.lock`, `ruff` for linting, `pytest` + `httpx` for tests.

### 2.2 Database schema (#6)

Six initial SQLAlchemy models: `User`, `Conversation`, `Message`, `Document`, `Embedding`, `Citation` — the original RAG-chatbot core entities, later joined by `Dataset`/`DatasetVersion` (Sprint 2) and `AuditLog`. See §1.4 for the ORM/migration decisions (ADR-013) and the enum-downgrade bug caught here.

### 2.3 Authentication module (#7)

This is one of your strongest "walk me through the security design" pieces — worth knowing in full detail.

- **Password hashing:** direct `bcrypt`, not `passlib`. This was a deliberate deviation from the original spec: `passlib` 1.7.4 is unmaintained and hard-breaks against bcrypt 5.x. `_secret_bytes()` explicitly truncates to bcrypt's 72-byte limit (bcrypt 5.x *raises* on longer input rather than silently truncating, so this has to be handled, not assumed).
- **JWT:** `python-jose`, HS256, `create_access_token(subject, role)`. The `role` claim is explicitly documented as **informational only** — `app/api/deps.py`'s `get_current_user` re-reads the role from the database on every request, so a role change or account deactivation takes effect immediately rather than waiting for token expiry. This is a real, common auth mistake (trusting a stale claim) that this code deliberately avoids.
- **RBAC:** `require_role(*allowed)` — a dependency factory, not a per-endpoint if-check, returning 403 for an insufficient role. Roles: `clinician`, `analyst`, `admin` (`UserRole` StrEnum).
- **No self-assigned roles:** `UserCreate` (the registration schema) has no `role` field at all — every registrant is a clinician by the model's default, full stop. Privileged roles have to be provisioned out-of-band. This closes off privilege self-escalation at the schema level, not by a runtime check that could be forgotten.
- **Constant-time login:** a precomputed dummy bcrypt hash (`_DUMMY_HASH`) is verified against on the "no such user" and "inactive account" paths, so a missing/inactive account takes the same wall-clock time as a wrong password — closing a timing side-channel that would otherwise let an attacker enumerate valid emails by measuring response latency.
- **JWT secret guard:** `Settings._validate_jwt_secret` refuses the dev placeholder or any secret under 32 characters *outside* development/test. Caught and hardened via a security-focused review pass on the diff before merge (2 HIGH findings fixed: the fail-open guard, and the timing side-channel above).

**Interview framing:** "role claim is informational only, always re-read from DB" and "constant-time login to prevent user enumeration" are both specific, correct security statements that show you understand *why*, not just *that* you hashed passwords and signed tokens.

### 2.4 Docker + CI (#8)

Multi-stage Dockerfile: stage 1 resolves the locked dependency set with `uv` into a self-contained virtualenv; stage 2 is a slim runtime that copies only that venv + app code and runs as a **non-root user**. `docker-compose.yml` at the repo root: `api` + `postgres:16-alpine` (pinned, healthchecked) + `qdrant:v1.12.4` (pinned — provisioned for the RAG pillar ahead of time, but the app has no Qdrant client dependency yet; a deliberate YAGNI call, wired only when the RAG pillar actually needs it). The `api` service waits for a healthy Postgres, runs `alembic upgrade head`, then serves. GitHub Actions CI (`.github/workflows/ci.yml`) runs `ruff check` + `pytest` on every push/PR to `develop` — no Postgres service needed in CI because the test suite runs against file-backed SQLite (see §3.6 for why that specific choice caused real bugs later).

### 2.5 Frontend scaffold (#10)

React 19 + TypeScript + Vite 6, Tailwind CSS v4 (via `@tailwindcss/vite`, no separate `tailwind.config` needed for base use), React Router 7. Deliberately scoped to *init only* — Zustand, React Hook Form + Zod, Recharts, shadcn/ui, TanStack Query are all deferred until an actual feature screen needs them, rather than pre-installed speculatively. A typed `fetch` client (`src/lib/api.ts`) hits the backend's health endpoint and renders a live Connected/Unreachable badge — proof the frontend and backend are actually wired together end-to-end, not just two services that happen to sit in the same repo.

---

## 3. Sprint 2 — Patient Data Platform (in progress: #30–#33 merged, #34–#36 next)

Everything here sits on top of ADR-009 (dataset versioning) and ADR-014 (pandera validation).

### 3.1 Dataset / DatasetVersion models (#30)

`Dataset` is a logical, named clinical dataset owned by a user (soft-delete via `deleted_at`, never hard-deleted — see §3.6). `DatasetVersion` is an **immutable snapshot**: one stored object + one metadata row, linked to its parent version via a self-referential `parent_version_id` FK, so lineage is queryable directly. A `UniqueConstraint` on `(dataset_id, version_number)` makes the "read max version, write max+1" pattern race-safe — a concurrent loser gets an `IntegrityError` instead of silently creating a duplicate version.

Two enums worth naming precisely: `ValidationStatus` (`pending`/`passed`/`failed`) and `VersionOrigin` (`upload`/`cleaned` — the latter reserved for #34's cleaning pipeline, not used yet).

### 3.2 Audit logging (#31)

**Why middleware, not a per-endpoint call:** a handler-level `audit(...)` call is one forgotten line away from an unaudited PHI endpoint, and — critically — it *can't* record 401/403 denials at all, because the handler never runs on a rejected request. `AuditLogMiddleware` intercepts by path prefix (`/api/v1/datasets` today) at the ASGI layer, so any new route under that prefix is audited automatically, with no per-route opt-in required. It records actor id/role (best-effort from the bearer token, never raises on a bad token), HTTP method, resource type/id, status code, client IP, user agent — and lets an endpoint enrich the record via `request.state.audit_detail`/`audit_resource_id`.

**A real correctness bug caught here (your best "tell me about a hard bug" story):** the first version used Starlette's `BaseHTTPMiddleware`, and the first upload test hung for exactly 30 seconds before failing with `database is locked`. Root cause: `BaseHTTPMiddleware.call_next()` runs the downstream app in a *spawned task*, and can return control to the middleware before that task's own DB session has actually finished closing. The audit middleware then opened a second SQLite connection while the first was still technically open, and the two connections deadlocked against each other on SQLite's busy-timeout. This isn't a test-only artifact — it's a documented class of Starlette correctness issue. Fixed by rewriting the middleware as a **raw ASGI middleware** (`__call__(scope, receive, send)`, awaiting the inner app directly in the same task, no spawned task involved) — which guarantees the request's own session is fully closed before the middleware opens its own. This is now the documented pattern for any future middleware in this codebase that needs its own DB session.

**Another gotcha:** the audit middleware imports `AsyncSessionLocal` directly (it can't use FastAPI's dependency injection, since middleware sits outside the DI system) — which means it binds to the *real* database at import time. `dependency_overrides` (the normal way tests redirect to a test database) can't reach a module-level singleton like this. `conftest.py` has to `monkeypatch` `app.core.audit.AsyncSessionLocal` directly instead. The exact same problem hit a bare `JSONB` column type against the SQLite test suite (Postgres-only type, fails `create_all` on SQLite) — fixed with `JSONB().with_variant(JSON(), "sqlite")`, aliased as `JsonB` in `app/models/base.py`. Both are the same underlying lesson: **testing against SQLite while targeting Postgres in production surfaces real compatibility gaps you have to design around, not just work around once.**

Append-only by construction: nothing in the codebase updates or deletes an `AuditLog` row (the FK to `users` even uses `ondelete="RESTRICT"`, so deleting a user can't silently erase their audit trail).

### 3.3 CSV upload + object storage (#32)

**Object storage** (`app/storage/object_store.py`): a content-addressed `ObjectStore` protocol — the storage key *is* the SHA-256 hash of the bytes, so uploading identical content twice is a no-op, and an existing object can never be silently overwritten with different content under the same key. `LocalObjectStore` is the dev implementation (filesystem, fanned out by hash prefix to avoid one giant flat directory); the same `Protocol` is designed to be implemented by an S3/MinIO backend in production without touching any calling code.

**Upload flow** (`DatasetService.create_from_upload`): size-capped (413 if over `max_upload_bytes`, default 50MB), parsed with `pd.read_csv` for metadata (row count, column list, a schema hash from column names+dtypes), stored via the object store, validated (§3.4), and written as the dataset's v1 `DatasetVersion` row — all inside one service method, called from `POST /datasets` which itself is content-type/extension-gated (415 for anything that isn't `.csv`).

**Two real bugs found post-merge, both worth knowing cold:**

1. **A `.gitignore` bug that silently broke CI.** `backend/.gitignore` had a bare `storage/` line, meant to ignore the *runtime* upload directory (`backend/storage/datasets`). Git's unanchored pattern matching applied it at *every* directory depth — so it also matched `backend/app/storage/`, which is the actual `ObjectStore`/`LocalObjectStore` **source package**. That package was silently excluded from every commit since #32 landed. Local dev and local tests kept passing, because the files still existed untracked on disk — the bug only surfaced on a genuinely fresh CI checkout, which had no `app/storage/` directory at all. The fix was two things: anchoring the pattern (`/storage/` — leading slash means "only at the repo root path this applies to," not every matching subdirectory), and recovering the previously-excluded files into the commit. **The methodology point here is the real interview answer:** when CI fails but your local repo passes, the correct move is to reproduce in an actual fresh clone before trusting any fix — don't assume your working tree matches what's actually committed.
2. **A path-traversal gap**, caught by a security-review pass on the merged diff (not by a test written in advance — worth being upfront about that). `LocalObjectStore.get()` stripped the `file://` prefix and joined the remainder straight into a filesystem path with no validation. Not exploitable *at the time* (only `put()`'s own SHA-256 output was ever stored and read back), but #33/#34 read `storage_uri` off a database row and pass it straight to `get()` — so a future code path could hand it attacker-influenced input. Hardened by rejecting any URI whose digest isn't a bare 64-character hex string via regex, before it ever touches the filesystem, with a dedicated test (`test_object_store.py`) covering round-trip, dedup, and traversal rejection.

### 3.4 Schema/data validation (#33, ADR-014)

Validation runs **synchronously inside the upload request**, against the pandas `DataFrame` already parsed for metadata — but dispatched via `asyncio.to_thread` since it's CPU-bound sync work and must not block the async event loop (consistent with the async-first stance from ADR-001/013).

`GENERIC_SCHEMA` (`app/services/validation.py`) is a `pandera.DataFrameSchema` with frame-level checks: non-empty, no duplicate column names, no fully-null column, no duplicate rows. This is deliberately generic — Sprint 2 accepts *arbitrary* clinical CSV uploads, not one fixed pathway schema, so named `DataFrameModel` classes for specific pathways (e.g. an ICD-coded readmission cohort) are additive, later work, not part of this check.

Run with `lazy=True`, which collects *every* violation in one pass rather than stopping at the first — the reasoning being that a clinician correcting a rejected upload needs the complete list, not a fix-one-resubmit-repeat loop. On failure, `pandera.errors.SchemaErrors.failure_cases` (already a small tabular structure) is truncated to 100 rows and written straight into `DatasetVersion.validation_report` (JSONB) — `validation_status` set to `passed`/`failed` accordingly. No new storage or reporting infrastructure needed; it slots directly into ADR-009's existing versioning scheme.

**A worked example of "docs win when they conflict with a plan"**, worth citing if asked about handling ambiguous requirements: the ADR (already merged from an earlier vision-doc rewrite) specified generic frame-level checks, but the original implementation plan and the issue's own acceptance criteria both described a *named* clinical schema (specific columns, ICD-code shape, value ranges) — narrower and more specific than what the ADR actually decided. Rather than silently picking one interpretation, the implementation followed the ADR (the authoritative, already-merged decision) and explicitly flagged the discrepancy in the PR description for review.

`DatasetService.revalidate_latest` + `POST /datasets/{id}/validate` let a dataset be re-validated on demand — this is also where the sharpest security finding of Sprint 2 so far happened:

**Cross-tenant PHI leak, caught in code review before merge.** The `/validate` endpoint required a valid bearer token (i.e., *some* authenticated user) but never checked that token's owner against the dataset's actual `owner_id`. Any authenticated user could call it against *any* dataset id and read back that dataset's `validation_report` — which, via pandera's `failure_cases`, can contain raw row values from someone else's uploaded clinical data. Simply guessing or enumerating a UUID would have been enough. Fixed at the service layer: `revalidate_latest(..., requester: User)` now checks owner-or-admin and raises a dedicated `DatasetForbiddenError` → 403 otherwise, covered by `test_revalidate_non_owner_is_forbidden`. **The general lesson, stated explicitly in project memory and worth repeating verbatim in an interview:** "requires auth" and "requires *this* user's authorization" are different checks, and every new patient-data endpoint needs both audited, not just the first.

### 3.5 What's next in Sprint 2 (not started)

- **#34** — cleaning/preprocessing pipeline, producing a new `DatasetVersion` with `origin = cleaned`.
- **#35** — dataset management endpoints (list, soft delete). Will reuse the owner-or-admin authorization pattern established in #33.
- **#36** — frontend dataset UI, and the still-open item of frontend CI (Node `npm ci` + `npm run build`, which already typechecks via `tsc --noEmit`).

### 3.6 Cross-cutting conventions worth naming as a set

These aren't one issue's work — they're conventions established across Sprint 2 that show a consistent engineering stance, which is exactly what "senior-engineer output" means in practice:

- **Everything is treated as PHI even though it's synthetic.** This is a project-wide rule, not a per-feature choice — it's why validation failures don't echo raw file bytes back to API clients (a generic 422 message is returned instead of the underlying parser exception, which can contain raw content snippets), why audit `detail` fields only ever carry metadata (filenames, row counts, ids) and never patient-level values, and why the #33 PHI leak above was treated as a real finding rather than a "well, it's synthetic data anyway" shrug.
- **Nothing is ever hard-deleted.** Datasets soft-delete via `deleted_at`. The reasoning: an audited clinical artifact can't be silently destroyed without breaking the exact traceability ADR-009 exists to provide, and a real GDPR erasure request needs to be its own separate, deliberately audited purge — not something that falls out of a generic delete endpoint by accident.
- **Every mutation gets a schema-level or DB-level guard, not just a runtime check.** Registration schemas with no `role` field, DB constraints for version uniqueness, ownership checks at the service layer rather than scattered in route handlers — the pattern throughout is "make the invalid state hard to construct," not "remember to check for it."

---

## 4. How this maps to interview questions you'll actually get

- **"Walk me through your data model."** → §3.1: `Dataset`/`DatasetVersion`, immutability, lineage via `parent_version_id`, the unique-constraint race-safety trick.
- **"How do you handle explainability / regulatory requirements?"** → ADR-011 (SHAP) — be honest this is decided architecture, not yet built. You can describe *why* `TreeExplainer` for tree models, why SHAP values get stored per-prediction rather than recomputed, and why the LLM explanation layer is grounded in real computed SHAP values rather than free-form generation.
- **"Tell me about a bug you fixed that wasn't obvious."** → the `BaseHTTPMiddleware` deadlock (§3.2) or the `.gitignore` anchoring bug (§3.3) — both are real, non-tutorial-tier debugging stories with a clear root cause and a generalizable lesson.
- **"Tell me about a security issue you caught."** → the cross-tenant PHI leak on `/validate` (§3.4), or the path-traversal hardening on the object store (§3.3). Both show you reviewing your own merged code critically, not just shipping and moving on.
- **"How do you make build-vs-buy decisions?"** → ADR-009 (lightweight versioning vs. DVC/LakeFS) or ADR-014 (pandera vs. great-expectations) — both have explicit, stated trade-offs you gave up, not just reasons you chose the winner.
- **"How do you handle PHI/GDPR in a system with only synthetic data?"** → §3.6's "treat everything as real PHI" stance, plus the specific consequence (generic error messages, audit `detail` scoping) it produces in the actual code.
- **"What would you build next / what's not done yet?"** → §3.5 and the top-of-document honesty check — you can speak precisely to what's ADR-decided vs. actually implemented, which reads as more credible than claiming the whole platform is live.

---

## 5. Recommended fix before your next interview pass

Rewrite ADRs 001–008's "Consequences" sections with real, tool-specific trade-offs (the material already exists — `project-memory.md`'s Conventions section and the TRD have enough real reasoning to draw from for each). Right now they're the one part of this repo that would read as unedited template output to a close reader, which stands out against how carefully everything else — ADR-009 onward, the code comments, the session history — is actually written. Say the word and I'll draft real content for all eight.
