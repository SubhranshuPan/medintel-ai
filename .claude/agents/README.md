# Reviewer agents

These eight subagent definitions are vendored from the [ECC plugin](https://github.com/affaan-m/ECC)
(v2.0.0, MIT licensed, Copyright (c) 2026 Affaan Mustafa) and tracked in this
repository rather than loaded from a plugin.

## Why they are vendored

The ECC plugin loads 67 agents and 277 skills into every session. An agent's
`description` frontmatter is prompt-resident whether or not the agent is ever
invoked, so keeping the whole plugin enabled meant paying the listing cost for
all 67 in order to use these eight. The plugin was disabled on 2026-07-25 and
these files copied here instead.

They are self-contained — no plugin-root references, no dependency on ECC being
installed.

## Usage

Invoke by **bare name** via the Agent tool. There is no `ecc:` prefix any more;
anything in the docs or git history written before 2026-07-25 that says
`ecc:<agent>` is stale.

| Agent | Model | Covers |
|---|---|---|
| `code-reviewer` | sonnet | General quality, security, maintainability |
| `fastapi-reviewer` | sonnet | Async correctness, DI, Pydantic schemas (ADR-001) |
| `react-reviewer` | sonnet | Hooks, render performance, a11y (ADR-002) |
| `python-reviewer` | sonnet | PEP 8, type hints, Pythonic idioms |
| `database-reviewer` | sonnet | PostgreSQL queries, schema design, migrations (ADR-003) |
| `healthcare-reviewer` | opus | Clinical safety, CDSS accuracy, PHI handling |
| `security-reviewer` | sonnet | OWASP Top 10, secrets, injection |
| `mle-reviewer` | sonnet | Data contracts, training reproducibility, serving, monitoring |

`healthcare-reviewer` and `mle-reviewer` are the two that matter most for this
project's differentiators — clinical safety and the MLOps stack in
`docs/00_VISION_ML_PLATFORM.md`.

## Updating

These are a point-in-time copy; they do not update with the plugin. To refresh
one, re-copy it from the ECC plugin cache
(`~/.claude/plugins/cache/ecc/ecc/<version>/agents/`) and note the version bump
here.

## Note on the rest of `.claude/`

`.gitignore` excludes `.claude/*` and re-includes only `.claude/skills/` and
this directory. Everything else under `.claude/` — `launch.json`,
`settings.local.json`, `commands/` — stays machine-local by design.
