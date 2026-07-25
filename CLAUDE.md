# MedIntel AI — Claude Code Instructions

## Project Overview
MedIntel AI — a five-pillar clinical intelligence platform: patient data platform, clinical analytics dashboard, ML risk-prediction engine with SHAP explainability, RAG-based AI decision support, and reporting/export. This is a career-critical portfolio project (not a hobby build) targeting UK healthcare/health-tech data science and ML engineering roles. Full context: `.agents/AGENTS.md` (read first) and `.ai/BOOTSTRAP.md`.

### Binding Scope Mandate (do not silently scope this down)
MedIntel AI is not a demo RAG chatbot. It must remain, end to end, a **production-grade, industry-valuable healthcare data science platform**: multiple predictive ML models (not just one), a real MLOps stack (experiment tracking, model registry, continuous training, monitoring, A/B testing), a rigorous evaluation/fairness framework, and privacy/compliance architecture (HIPAA/GDPR-ready). Full detail and roadmap: `docs/00_VISION_ML_PLATFORM.md`. Never quietly drop or water down these components to save time — if a timeline conflict shows up, surface it explicitly to Som (as a flagged risk/tradeoff) rather than silently descoping. This mandate was set 2026-07-14 and supersedes any earlier "keep it minimal" framing elsewhere in this file or in `.ai/`.

## Tech Stack (per ADRs in `docs/architecture/adr/`)
| Layer | Choice | ADR |
|---|---|---|
| Backend API | FastAPI | ADR-001 |
| Frontend | React | ADR-002 |
| Relational DB | PostgreSQL | ADR-003 |
| Vector DB | Qdrant | ADR-004 |
| LLM orchestration | LangChain | ADR-005 |
| Containerization | Docker | ADR-006 |
| CI/CD | GitHub Actions | ADR-007 |
| Architecture style | Modular monolith | ADR-008 |
| Data versioning | Dataset versioning scheme | ADR-009 |
| Model serving | ML model serving pattern | ADR-010 |
| Explainability | SHAP | ADR-011 |
| Reporting | PDF/export pipeline | ADR-012 |

Don't propose a different stack for core pillars without flagging it as an ADR-worthy deviation first.

## Domain & Portfolio Requirements
- Use healthcare-domain terminology (readmission risk, clinical pathway, patient cohort, ICD codes) — not generic tech jargon.
- Treat all data as if it were real PHI even though it's synthetic: GDPR-aware handling, no shortcuts that wouldn't fly with real patient data.
- Explainability is not optional — any predictive model needs SHAP output, since that's what NHS/UK regulators and interviewers care about.
- Code, docs, and commits should read as senior-engineer output — recruiter-readable, interview-defensible. Document non-trivial decisions as ADRs (19 exist already in `docs/architecture/adr/`).
- Don't dumb the project down or default to tutorial-tier patterns.

## Workflow & Branch Policy
- All work stays on `develop`. Do not propose or perform a `develop` → `main` merge — `main` updates only once a basic first-draft product exists. Don't flag "main is behind develop" as an action item.
- Report-only autonomy: propose changes, let Som approve; never auto-merge PRs.
- **Never push directly to `develop`** (set 2026-07-14, after `b42c1fe` went straight to `develop`). *Every* commit lands via a feature branch and a PR — including bookkeeping-only changes (`.ai/memory/*`, doc touch-ups, scope-status edits). There is no "too small for a PR" category. Branch naming follows the existing pattern (`docs/…`, `fix/…`, `feat/…`).
- Git writes go through the **`gh` CLI**, not the GitHub MCP server — the MCP token is read-only and 403s on writes (`create_pull_request`, labels, milestones, releases). Use the MCP for reads. `git push` and `gh` are both authenticated; don't assume credentials are missing without testing.
- **Sync the parent epic after every child-issue merge (set 2026-07-15) — do this unprompted, every time, no exception.** As soon as Som confirms a child issue's PR is merged (and the branch deleted): (1) close the child issue via `gh issue close <n> --comment "..."` referencing the merging PR, if it isn't already auto-closed; (2) `gh issue edit <epic>` to tick that child's checkbox in the epic body's child-issue list and update any Definition-of-Done checkboxes the merged work satisfies, plus the "Progress" line's date/next-up. Applies to every epic in this repo (#29 and any future one), not just the current sprint. This is bookkeeping, so it doesn't need Som to ask each time — same standing as the session-history entry in the checklist below. A subagent may run this if convenient (it's a self-contained `gh issue`-only task), but it's simple enough to do inline most of the time.
- Project status: Sprint 0 (docs/architecture, 20 ADRs) is complete. Sprint 1 (backend foundation — auth, data models, API skeleton, issues #5–#10) is complete — 11/11 issues, milestone closed 2026-07-12. Sprint 2 (Patient Data Platform, epic #29) is **complete and closed** — #30–#36 all merged to `develop`, including the frontend dataset upload/list UI (#36, PR #53) and a follow-up UI polish pass (shadcn/ui + Animate UI + Aceternity UI + Lenis, ADR-020, PR #56). Sprint 3 (AI & RAG — knowledge-aware semantic RAG, **epic #58**) is scoped as of 2026-07-25: children #59–#68, design spec at `docs/superpowers/specs/2026-07-25-sprint-3-knowledge-aware-rag-design.md`. Build order starts at #59 (ADR-021 knowledge graph + ADR-022 LLM provider). Sprint 3 is the **knowledge layer**; ADR-017's ranking layer moves to Sprint 4 — sequencing, not descoping.

## Session-End Checklist (mandatory — Cowork and Claude Code, do this without being asked)
- If any file changed this session (code, config, docs, ADRs): append a dated entry to `.ai/memory/session-history.md`, using the template already at the top of that file. Do this automatically at the end of the session, before signing off — don't wait for Som to request it.
- If a significant decision was made (architecture, scope, tooling, tradeoffs): also add/update `.ai/memory/project-memory.md`.
- If nothing in the working tree changed (pure discussion, planning, or research with no files touched): skip — don't create an empty log entry.
- Writing the memory entry is bookkeeping, not a git action — it's exempt from report-only autonomy, so do it unprompted. Landing it is *not* exempt: the edit sits in the working tree like any other doc change and goes through a feature branch + PR (see Branch Policy above — no direct pushes to `develop`, and no auto-merge). Don't `git add`/`commit`/`push` without Som asking.
- Safety net: the `medintel-morning-repo-briefing` scheduled task (9:10 AM weekdays) checks the next morning and appends a session-history.md entry itself if it finds repo activity that wasn't logged — so a missed entry gets caught within a day either way.

## Model Routing (Token Optimization)

This project uses a **two-model workflow** to minimize token costs:

| Phase     | Model  | Command     | Purpose                              |
|-----------|--------|-------------|--------------------------------------|
| Planning  | Opus   | `/plan`     | Deep research, architecture, design  |
| Execution | Sonnet | `/execute`  | Code changes, following the plan     |
| Status    | Any    | `/status`   | Check plan progress                  |

### When to Suggest Opus Planning
If you detect the task involves ANY of the following, suggest the user switch to Opus and use `/plan`:
- New feature development spanning multiple files
- Architectural changes or refactors
- Complex debugging requiring deep codebase analysis
- Database schema changes
- API design decisions
- Security-sensitive changes
- Infrastructure or deployment changes

Say: _"This looks like a complex task. Consider running `/model` to switch to Opus, then `/plan <task>` for a thorough plan. You can switch back to Sonnet for execution."_

### When to Proceed Directly (Sonnet)
Handle these tasks immediately without suggesting Opus:
- Simple bug fixes and typos
- Formatting and style changes
- Adding comments or documentation
- Small, isolated code changes
- Running commands or checking status

## Code Style
- Use clear, descriptive variable and function names
- Add docstrings to all public functions
- Keep functions focused and under 50 lines where possible
- Preserve existing comments unrelated to your changes

## Connectors and Skills

Plugins are referenced at the plugin level, not per individual skill — pull whichever skill/agent/command inside the plugin fits the moment.

| Plugin | Use for |
|---|---|
| `engineering` | Core SDLC skills: architecture/ADRs, system-design, code-review, debug, testing-strategy, deploy-checklist, incident-response, tech-debt, documentation, standup |
| Project reviewer agents (`.claude/agents/`) | **The `ecc` plugin was disabled 2026-07-25** (67 agents + 277 skills of context overhead for the eight agents we actually use). Those eight were vendored into `.claude/agents/` and are invoked by bare name via the Agent tool — no `ecc:` prefix: `code-reviewer`, `fastapi-reviewer`, `react-reviewer`, `python-reviewer`, `database-reviewer` (PostgreSQL/migrations), `healthcare-reviewer` (clinical safety/PHI), `security-reviewer`, `mle-reviewer` (MLOps). This directory is gitignored (`.claude/*`), so it is machine-local — re-copy from the `ecc` plugin cache if it goes missing on another machine. |
| `code-review` (top-level) | Quick `/code-review` on a PR/diff outside the `ecc` marketplace flow |
| `ui-ux-pro-max` | Frontend design system work — styles, color palettes, font pairings, component patterns for the dataset UI, clinical dashboard, and future patient-facing screens |
| `frontend-design` | General frontend implementation guidance, complements `ui-ux-pro-max` |
| `dataviz` | Chart/graph/dashboard design — directly relevant to the clinical analytics dashboard pillar and SHAP explainability visualizations |
| `frontend-animation-libs` (project skill, `.claude/skills/`) | Animate UI, Lenis, Aceternity UI — the approved third-party libraries for frontend component polish/scroll/motion. Check this before hand-rolling animation on any `frontend/` page. |
| `playwright-skill` | Browser-driven E2E testing for the React frontend |
| `ponytail` | Default lazy-but-correct coding discipline (YAGNI, reuse before build, shortest safe diff) — applies to all code changes in this repo |
| `caveman` | Terse chat/response style — does not apply to code, commits, or PR bodies, which stay normal prose |
| `superpowers` | Process skills — brainstorming before new features, systematic-debugging before bug fixes, TDD, writing/executing plans |
| `claude-code-setup` | `claude-automation-recommender` — surfaces hooks/automation opportunities for this repo's workflow |
| `claude-md-management` | Keeping this file itself current as the project evolves |
| `anthropic-skills` | `docx`/`pdf`/`xlsx` for reports, resumes, or data exports as deliverables |

Connectors:

| Connector | Status | Use for |
|---|---|---|
| GitHub (`plugin:engineering:github`) | Not yet authorized | PR/issue status, repo hygiene checks — authorize via Cowork Settings → Connectors → GitHub, or `claude mcp` in an interactive Claude Code session |

Update this table when new plugins are installed or connectors are authorized.
