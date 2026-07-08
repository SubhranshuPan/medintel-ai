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
