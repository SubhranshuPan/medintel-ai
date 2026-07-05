# Daily Development Workflow

> Playbook for working on MedIntel AI like a junior ML engineer at a software company.
> Cadence: **Mon–Fri, 1–2 hours/day.** Weekends off (optional light review).
> Goal: a portfolio that proves professional engineering habits to UK recruiters (target: part-time/full-time/internship roles in Glasgow alongside MSc Data Science, from Sept 2026).

---

## The Golden Rule

**One small, finished, visible deliverable per day.** A merged PR beats three half-done branches. Recruiters read your commit history and PR descriptions — make every day look like a professional shipped something.

---

## Daily Session (90–120 min)

### 1. Standup — 10 min
- Read Claude's 9 AM repo briefing (git activity, docs drift, memory vault status).
- Open the GitHub project board / issue list.
- Answer the three standup questions in `.ai/memory/session-history.md`:
  - What did I ship yesterday?
  - What will I ship today? (ONE issue)
  - What's blocking me?

### 2. Pick & scope — 5 min
- Choose ONE issue from the board. If it can't be finished in ~1 hour of work, split it into smaller issues first — that's the deliverable for today instead.
- Assign it to yourself, move it to "In Progress".

### 3. Branch — 2 min
- Follow `.ai/rules/git.md`. Branch from `main`:
  - `feat/<issue-number>-short-name`, `fix/...`, `docs/...`, `ml/...`

### 4. Build — 50–70 min
- Focused work on the one issue. No scope creep — new ideas become new issues, not new code today.
- Follow `.ai/playbooks/implement-feature.md` for feature work.
- For ML work: log experiments in `experiments/` with config + results, never just in your head.

### 5. Verify — 10 min
- Run tests; add at least one test for new logic.
- Run linter/formatter.
- If behaviour or architecture changed: update the relevant `docs/` page or ADR **in the same PR** (documentation-first rule).

### 6. Ship — 10 min
- Conventional commit(s): `feat(rag): add reranker to retrieval pipeline (#42)`.
- Open a PR with the template filled in: what/why/how tested/screenshots if UI.
- Self-review the diff like a colleague would. Merge when green (or leave for tomorrow's review if unsure).

### 7. Close the loop — 5 min
- Append today's entry to `.ai/memory/session-history.md` (date, issue, outcome, decisions).
- If a significant decision was made, record it in `.ai/memory/project-memory.md` and/or a new ADR.
- Move the issue to "Done". Note tomorrow's candidate issue.

---

## Weekly Rhythm

| Day | Focus |
|-----|-------|
| **Mon** | Sprint planning (15 min): pick 4–5 issues for the week, order them. Then normal session. |
| **Tue–Thu** | Build days — pure daily sessions. |
| **Fri** | Ship + retro: finish/merge the week's PRs, write a 5-line retro in `session-history.md` (went well / didn't / change next week). Update `.ai/llm-wiki/` if the repo drifted. |
| **Sat–Sun** | Off. Optional: read one ML/engineering article relevant to next week's issues. |

---

## Sprint Rhythm (every 2 weeks)

- **Sprint goal:** one user-visible capability (e.g. "RAG answers cite sources", "auth works end-to-end").
- End of sprint: demo it — record a 1–2 min screen capture, add it to the README or `reports/`.
- Milestone tags: `v0.x` releases with changelogs. Releases look great on a repo.

---

## Portfolio Amplifiers (weekly, pick one — 15 min)

These convert engineering work into job-search assets:

1. **README polish** — badges (CI, coverage), architecture diagram, demo GIF, quickstart that works.
2. **Write-up** — short LinkedIn post or blog entry on something you built ("How I added hybrid search to my RAG pipeline"). UK recruiters check LinkedIn activity.
3. **CV bullet** — translate the sprint into a quantified CV line while it's fresh.
4. **ADR quality** — a clean decision record (like ADR-001-fastapi) is rare in junior portfolios; it signals maturity.

### Glasgow/UK targeting notes
- Local market: financial services tech (JP Morgan and Barclays have large Glasgow engineering hubs), NHS/health data (fits MedIntel's domain directly), plus university research groups hiring MSc students part-time.
- Healthcare AI + evidence of production practices (CI, tests, docs, ADRs) is a strong differentiator for NHS-adjacent and health-tech roles.
- Keep the repo public, pinned on your GitHub profile, with a clear "what this demonstrates" section in the README.

---

## Definition of Done (every issue)

- [ ] Code works and is tested
- [ ] Linter passes, CI green
- [ ] Docs/ADR updated if behaviour or architecture changed
- [ ] Conventional commit + PR with filled template
- [ ] `.ai/memory/session-history.md` entry appended
- [ ] Issue closed on the board

---

## Anti-patterns (things that ruin portfolio repos)

- Committing straight to `main` with messages like "update" or "fix stuff".
- 500-line PRs nobody could review.
- Docs and `.ai/llm-wiki/` describing a repo that no longer exists.
- Long gaps then huge dumps — steady weekday commits read as discipline.
- Building for weeks with nothing runnable — keep `main` always demoable.
