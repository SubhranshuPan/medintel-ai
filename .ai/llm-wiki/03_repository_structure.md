# Repository Structure

## Root Directories

docs/
: Project documentation

.ai/
: AI workspace

backend/
: FastAPI application

frontend/
: React application

ml/
: AI and ML components

data/
: Datasets and data artifacts

experiments/
: ML experiments and notebooks

configs/
: Configuration files

scripts/
: Automation scripts

infrastructure/
: Deployment and DevOps

reports/
: Generated reports

.github/
: Issue/PR templates, CODEOWNERS, CONTRIBUTING (CI workflows deferred until Sprint 1 code lands)

.agents/
: Universal AI-agent context (AGENTS.md — career/financial context, UK target roles, visa justification, agent rules); read first per BOOTSTRAP.md

.claude/
: Claude Code slash commands (`/plan`, `/execute`, `/status`) and settings

---

## Root Files

CLAUDE.md
: Claude Code instructions (model routing: Opus for planning, Sonnet for execution; code style)

README.md
: Project overview (five pillars, tech stack, repo structure, status)

LICENSE
: MIT (2026 Subhranshu Pan)

---

## Documentation Hierarchy

1. docs/
2. .ai/llm-wiki/
3. Source Code

---

## Development Order

Documentation

↓

Architecture

↓

Implementation

↓

Testing

↓

Deployment

---

## AI Workspace

BOOTSTRAP.md

↓

README.md

↓

LLM Wiki

↓

Task

↓

Code

---

Reference:

docs/
