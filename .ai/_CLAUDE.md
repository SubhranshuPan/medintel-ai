# Claude Operating Manual — MedIntel AI Vault (`.ai/`)

> Read this file before doing anything in this vault.
> This vault IS the `.ai/` directory of the medintel-ai git repo — every write here is git-tracked and lands in PRs. Treat writes accordingly: recruiter-readable, senior-engineer quality.

---

## Section 0 — AI-First Vault Rule

This vault is designed for **future-Claude** (and other coding agents) to read and reason over. Notes must be:

1. **Self-contained** — each note explains itself; don't rely on backlinks alone.
2. **Preamble** — new skill-generated notes begin with a short "For future Claude" summary (2-3 sentences).
3. **Frontmatter** — new notes created by obsidian-second-brain commands get frontmatter (`type`, `date`, `tags`, `ai-first: true`). **Exception:** existing files (`memory/`, `llm-wiki/`, `rules/`, `playbooks/`, `agents/`, `BOOTSTRAP.md`, `Home.md`, `README.md`) predate this convention and use plain markdown — extend them in their own style, do NOT retrofit frontmatter.
4. **Recency markers** — external claims carry a date: "FastAPI 0.115 (as of 2026-07)".
5. **Sources verbatim** — external claims keep their URL inline.
6. **Wikilinks** — link `[[project-memory]]`, `[[session-history]]`, ADRs, issues wherever referenced.
7. **Confidence levels** — `stated | high | medium | speculation` where applicable.

---

## Section 0.5 — Verify Live State Before Acting

Before declaring a bug, drafting a fix, or writing architecture: read the actual code, schema, branch, or live data. Specific to this repo:
- `/docs` is the source of truth; `.ai/llm-wiki` summarizes it; source code third. Conflicts resolve in that order.
- Read the real ADR in `../docs/architecture/adr/` before citing a decision.
- Check `git log develop` before claiming what has/hasn't landed.

---

## Vault Identity

- **Owner:** Som (Subhranshu Pan)
- **Primary purpose:** AI workspace for the MedIntel AI portfolio project — agent context, project memory, LLM-optimized architecture summaries. NOT a personal life vault.
- **Last updated:** 2026-07-11

---

## Folder Map

| Folder | Purpose | Write policy |
|---|---|---|
| `memory/` | `session-history.md` (append-only, newest on top), `project-memory.md` (decisions), `project-context.md` (state snapshot) | Append per existing template; never rewrite history |
| `llm-wiki/` | AI-optimized summaries of `/docs` (architecture, stack, domain) | Update only when `/docs` changes; keep summary, not duplicate |
| `agents/` | Per-agent instructions (claude, gemini, opencode, chatgpt, antigravity) | Edit deliberately, they steer all agents |
| `playbooks/` | Standard workflows (implement-feature, daily-workflow) | Extend in existing style |
| `rules/` | Engineering rules (architecture, git, documentation) | Edit deliberately |
| `templates/` | Empty — reserved for doc templates | — |
| `checklists/` | Empty — reserved for QA checklists | — |
| `Logs/` | Per-day vault operation logs (`YYYY-MM-DD.md`), append-only | obsidian-second-brain writes here |

No `Daily/`, `People/`, `Projects/`, `Tasks/`, or `Boards/` folders — this is a project workspace, not a life OS. Do not create them unless Som asks.

---

## Key Files

- **Dashboard:** `[[Home]]`
- **Entry point for agents:** `[[BOOTSTRAP]]`
- **Wiki reading order:** `[[llm-wiki/index]]`
- **Vault catalog:** `[[index]]` (root — read FIRST when navigating)
- **Operation log:** `[[log]]` (pointer) → `Logs/YYYY-MM-DD.md`

---

## Active Context

**Project:** MedIntel AI — five-pillar clinical intelligence platform (FastAPI/React/PostgreSQL/Qdrant/LangChain, 19 ADRs). Full-scope production ML platform per `docs/00_VISION_ML_PLATFORM.md` (adopted 2026-07-14) — see `CLAUDE.md`'s binding scope mandate.
**Current phase:** Sprint 1 (backend foundation, issues #5–#10) complete — 11/11 issues, milestone closed 2026-07-12. Sprint 2 (Patient Data Platform, issues #30–#34) in progress: dataset models (#30), audit logging (#31), CSV upload/object storage (#32) shipped; schema validation (#33, see ADR-014) and dataset management endpoints (#34) next.
**Branch policy:** all work on `develop`; `main` waits for first-draft product.
**Autonomy:** report-only — propose, Som approves. Memory-file bookkeeping is exempt (see repo `CLAUDE.md`).

---

## Auto-Save Rules

Auto-save **without asking**:
- Session summaries → `memory/session-history.md` (dated entry, top, existing template)
- Significant decisions → `memory/project-memory.md`
- Vault operations → `Logs/YYYY-MM-DD.md`

**Ask before**:
- Creating new top-level folders or note types
- Touching `llm-wiki/`, `rules/`, `agents/`, `playbooks/` (steering files)
- Deleting or archiving anything
- Anything that would land noise in a PR diff

---

## Naming Conventions

- Log files: `Logs/YYYY-MM-DD.md`
- Existing files: lowercase-kebab (`session-history.md`, `project-memory.md`) — match this for new memory-type files
- Wiki pages: `NN_topic.md` ordering inside `llm-wiki/`
- No em-dash filenames in this vault (git-tracked, keep paths portable)

---

## Propagation Rules

| Event | Also update |
|---|---|
| Working session ends, files changed | `memory/session-history.md` entry |
| Architecture/scope/tooling decision | `memory/project-memory.md` |
| `/docs` or ADR change | matching `llm-wiki/` page |
| Any vault write by a skill command | `Logs/YYYY-MM-DD.md` + `index.md` if a note was created/deleted |

---

## Do Not Touch

- `.obsidian/` — Obsidian app config
- `memory/session-history.md` past entries — append-only, never rewrite
- Never `git add`/`commit`/`push` from vault operations — writes sit in working tree for normal PR flow

---

*Generated by the obsidian-second-brain skill (2026-07-11). Regenerate with: "update my _CLAUDE.md".*
