# AI Workspace

> This directory contains AI-optimized documentation, workflows, and memory used by coding agents working on the MedIntel AI project.

The `.ai/` workspace is designed to provide concise, structured context for AI coding assistants without duplicating the full project documentation.

The authoritative project documentation remains in the `/docs` directory.

---

# Purpose

The AI workspace enables coding agents to:

- Understand the project quickly
- Follow a consistent development workflow
- Access summarized architectural knowledge
- Preserve project context across development sessions
- Produce consistent, maintainable code

---

# Directory Structure

```text
.ai/
├── BOOTSTRAP.md          # Entry point for every AI agent
├── README.md             # Overview of the AI workspace
│
├── llm-wiki/             # AI-optimized project knowledge
│
├── memory/               # Persistent project memory
│
├── agents/               # Agent-specific instructions
│
├── playbooks/            # Standard implementation workflows
│
├── rules/                # Repository engineering rules
│
├── templates/            # Reusable document templates
│
└── checklists/           # Quality and review checklists
```

---

# Workspace Components

## llm-wiki

Summarized technical knowledge derived from the project documentation.

Purpose:

- Fast onboarding
- Architecture summaries
- Technology summaries
- Repository overview

---

## memory

Stores long-term project context.

Includes:

- Project context
- Project memory
- Session history

---

## agents

Instructions tailored for different AI coding assistants.

Examples:

- Claude Code
- OpenCode
- Gemini CLI
- ChatGPT

---

## playbooks

Standard workflows for common engineering tasks.

Examples:

- Implement a feature
- Fix a bug
- Refactor code
- Update documentation

---

## rules

Repository-wide engineering standards.

Examples:

- Architecture rules
- Git workflow
- Documentation standards
- Security practices

---

## templates

Reusable templates for documentation and development.

Examples:

- ADR template
- Feature template
- Issue template

---

## checklists

Quality assurance checklists used before completing work.

Examples:

- Feature completion
- Pull request review
- Documentation review

---

# Documentation Hierarchy

Project information should always be interpreted in the following order:

1. `/docs`
2. `.ai/llm-wiki`
3. Source Code

If conflicts exist, the `/docs` directory is the source of truth.

---

# Maintenance

The AI workspace should evolve alongside the project.

Whenever major architectural or workflow changes occur:

- Update the relevant document in `/docs`
- Reflect the change in the appropriate `.ai` summary
- Update project memory if necessary