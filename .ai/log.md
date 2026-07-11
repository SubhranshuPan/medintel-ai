---
type: log-pointer
date: 2026-07-11
tags:
  - log
ai-first: true
---

# Operation Log (pointer)

> For future Claude: vault operations are logged per-day in `Logs/YYYY-MM-DD.md`, append-only. Never write entries in THIS file — it only documents the structure.

## Entry format (in `Logs/YYYY-MM-DD.md`)

```
**HH:MM** - action | description
```

Actions: `init` · `save` · `ingest` · `health` · `synthesize` · `update` · `create`

## Rules
- One file per day, append-only. Never delete or rewrite entries.
- Every skill-driven vault write gets an entry.
- This log is separate from [[session-history]] (project working sessions) — Logs/ tracks vault mechanics only.
