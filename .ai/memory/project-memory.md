# Project Memory

> Accumulated decisions, conventions, and known gotchas that aren't in `/docs` yet
> (or that supplement it). Append new entries under the relevant section — don't
> rewrite history. If a decision here contradicts `/docs`, `/docs` wins; update
> this file to match and note the correction.

---

## Conventions Adopted

- RAG/LLM code must go through the existing multi-provider abstraction layer —
  never hardcode a single provider (OpenAI/Anthropic/Gemini) directly into a service.
- Backend follows a repository/service pattern. A new ORM access pattern is a
  deviation and should be flagged explicitly before merging, not introduced silently.
- Architectural decisions get written up as ADRs (not just described in a PR
  description or chat) — see `docs/` for the ADR template/location once established.
- Any code path touching patient data must be flagged for privacy/compliance
  review. Never assume amount of de-identification already applied upstream —
  verify or ask.

---

## Known Gotchas

*(none recorded yet — add here as they're discovered, e.g. migration quirks,
Qdrant collection config traps, provider-specific rate limits, etc.)*

---

## Open Questions / Decisions Pending

*(track anything flagged during a session that needs a human decision before
work can continue — move to "Conventions Adopted" once resolved)*

---

## Cross-Agent Notes

This file is shared across AI agents (Claude, ChatGPT, Gemini, OpenCode, etc. —
see `.ai/agents/`). Keep entries tool-agnostic: describe the convention or
constraint, not "Claude did X." Agent-specific working style belongs in
`.ai/agents/<agent>.md`, not here.
