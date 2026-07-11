---
type: index
date: 2026-07-11
tags:
  - index
ai-first: true
---

# Vault Catalog

> For future Claude: full catalog of this vault's pages. Read this FIRST when navigating — cheaper than searching. Update when a note is created or deleted.

## Root
- [[Home]] — dashboard and navigation hub
- [[BOOTSTRAP]] — mandatory entry point for any AI agent
- [[README]] — what the `.ai/` workspace is and how it's organized
- [[_CLAUDE]] — Claude operating manual for this vault
- [[log]] — operation log pointer (entries live in `Logs/`)

## memory/
- [[session-history]] — append-only session log, newest on top
- [[project-memory]] — accumulated decisions, conventions, gotchas
- [[project-context]] — current project state snapshot

## llm-wiki/
- [[llm-wiki/index]] — wiki reading order and task-based guide
- [[00_project_overview]] — what MedIntel AI is, five pillars
- [[01_architecture]] — modular monolith design summary
- [[02_tech_stack]] — FastAPI, React, PostgreSQL, Qdrant, LangChain
- [[03_repository_structure]] — repo layout guide
- [[04_domain_knowledge]] — healthcare domain concepts (readmission risk, ICD codes)
- [[05_real_world_impact]] — clinical/NHS relevance framing

## agents/
- [[agents/claude]] — Claude Code instructions
- [[agents/gemini]] — Gemini CLI instructions
- [[agents/opencode]] — OpenCode instructions
- [[agents/chatgpt]] — ChatGPT instructions
- [[agents/antigravity]] — Antigravity IDE instructions

## playbooks/
- [[implement-feature]] — standard feature workflow
- [[daily-workflow]] — Mon–Fri working session structure

## rules/
- [[rules/architecture]] — architecture rules
- [[rules/git]] — git workflow rules
- [[rules/documentation]] — documentation standards

## templates/ · checklists/
Empty — reserved.

---
*22 content notes + skill files. Stats refresh: `python scripts/vault_stats.py --vault <path>` from the skill repo.*
