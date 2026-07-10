# MedIntel AI — Vault Home

This vault *is* `.ai/` in the medintel-ai repo — no duplicate copy, no sync step. Anything written here is git-tracked with the project.

## Start here
- [[BOOTSTRAP]] — mandatory entry point for any AI agent (this file is `BOOTSTRAP.md`)
- [[AGENTS]] — developer/career context (lives in `/.agents/`, outside this vault root — open separately)

## Living memory
- [[session-history]] — append-only session log, most recent on top
- [[project-memory]] — significant decisions worth remembering across sessions
- [[project-context]] — current state snapshot

## LLM Wiki (architecture & domain summaries)
- [[index]] — wiki reading order and task-based guide
- [[00_project_overview]]
- [[01_architecture]]
- [[02_tech_stack]]
- [[03_repository_structure]]
- [[04_domain_knowledge]]
- [[05_real_world_impact]]

## Playbooks & rules
- [[daily-workflow]] — the Mon–Fri working session structure
- [[implement-feature]]
- [[architecture]] (rules)
- [[documentation]] (rules)
- [[git]] (rules)

## Outside this vault
`docs/` (PRD, TRD, ADRs) and the codebase (`backend/`, `frontend/`, `ml/`) live one level up in the repo root, outside this vault's boundary — Obsidian won't graph-link them. Reference by relative path, e.g. `../docs/architecture/adr/ADR-001-fastapi.md`.

## Scheduled upkeep
The `medintel-morning-repo-briefing` scheduled task runs daily at 9:10 AM and appends a dated entry to [[session-history]] automatically. Everything else it finds (docs drift, ADR gaps, stale wiki pages) stays a proposal in the chat report — Som applies those manually, consistent with report-only autonomy.
