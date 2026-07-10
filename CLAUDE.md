# MedIntel AI — Claude Code Instructions

## Project Overview
MedIntel AI — Medical intelligence platform.

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

Skills relevant to this project (Claude Code / Cowork `engineering` plugin, plus general document skills):

| Skill | Use for |
|---|---|
| `engineering:architecture` | ADRs — evaluate/document design decisions (this repo already has 12) |
| `engineering:system-design` | API design, data modeling, service boundaries for Sprint 1+ |
| `engineering:code-review` | Reviewing diffs/PRs for security, performance, correctness |
| `engineering:debug` | Structured reproduce → isolate → diagnose → fix sessions |
| `engineering:testing-strategy` | Test plans once backend/frontend code lands |
| `engineering:deploy-checklist` | Pre-deployment verification (Railway/Render, later AWS) |
| `engineering:incident-response` | Triage/postmortem if something breaks post-deploy |
| `engineering:tech-debt` | Refactor/code-health audits as the codebase grows |
| `engineering:documentation` | READMEs, runbooks, API docs |
| `engineering:standup` | Turning commit/PR activity into a standup-style update |
| `docx` / `pdf` / `xlsx` | Generating reports, resumes, or data exports as deliverables |

Connectors:

| Connector | Status | Use for |
|---|---|---|
| GitHub (`plugin:engineering:github`) | Not yet authorized | PR/issue status, repo hygiene checks — authorize via Cowork Settings → Connectors → GitHub, or `claude mcp` in an interactive Claude Code session |

Update this table when new skills are installed or connectors are authorized.
