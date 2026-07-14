# ADR-018 — MIMIC-III as Clinical Training Data Source

## Status

Accepted (data access itself is a tracked risk — see Consequences)

## Context

The risk-stratification and treatment-outcome models (`docs/00_VISION_ML_PLATFORM.md`,
Models 1–2) need real clinical training data to produce credible, defensible
metrics (ROC-AUC, calibration, fairness) — synthetic data alone can validate
the *pipeline* but not the *models' real-world signal*, which matters for a
portfolio aimed at UK healthcare/health-tech hiring. MIMIC-III (Medical
Information Mart for Intensive Care III) is the standard, widely-recognised
public clinical dataset for exactly this kind of work, and is well known to
technical interviewers in this space.

MIMIC-III is not an open-download dataset: access requires PhysioNet
credentialing, which in turn requires a completed human-subjects research
ethics training course (CITI Program, "Data or Specimens Only Research"
track) and a signed Data Use Agreement. This is a real process with a real
timeline, not a config flag — it is called out separately here rather than
folded silently into "the data pipeline."

## Decision

**MIMIC-III is adopted as the primary real-world training data source** for
Models 1 and 2, accessed via credentialed PhysioNet access.

- **Credentialing steps** (tracked as a project risk, not assumed complete):
  1. Create a PhysioNet account.
  2. Complete the CITI Program "Data or Specimens Only Research" training
     course and attach the completion report to the PhysioNet profile.
  3. Submit the MIMIC-III credentialed-access application, including a
     brief research use statement (portfolio/educational ML research).
  4. On approval, sign the PhysioNet Credentialed Health Data Use Agreement
     before any download.
  - Typical turnaround is days to a few weeks depending on CITI course pace
     and PhysioNet review queue — **this is the long pole on the ML model
     work and should be started immediately**, independent of and in
     parallel with all other Sprint work, since nothing else in Models 1–2
     blocks on it starting.
- **Interim/fallback**: until credentialed access is granted, model
  development proceeds against synthetic clinical data (already the
  project's default per its GDPR-aware "treat data as real PHI" stance) so
  Sprint velocity does not stall on the credentialing timeline. Models are
  re-trained/re-validated against MIMIC-III once access is granted; this is
  a re-run of an already-built pipeline, not new development.
- **Handling once access is granted**: MIMIC-III is already de-identified
  under HIPAA Safe Harbor by PhysioNet, but the Data Use Agreement still
  prohibits re-identification attempts, restricts redistribution, and
  requires the data to stay within the approved storage/compute
  environment. Per the DUA and the project's GDPR-aware stance (this is a
  UK-based project), MIMIC-III data is stored only in the project's
  private, non-public infrastructure — never committed to the repository,
  never uploaded to a public artifact store, and excluded from any public
  demo deployment. Public-facing demos and screenshots use the existing
  synthetic dataset; MIMIC-III-trained model *artifacts and metrics* (not
  the underlying data) may be referenced in portfolio materials, consistent
  with standard practice for MIMIC-III-based research publications.

## Alternatives Considered

- **Synthetic data only, no real dataset** — no credentialing delay, but
  caps the project's credibility: ROC-AUC/fairness numbers on synthetic
  data demonstrate methodology, not real predictive signal, which is a
  material gap for interviews at NHS/health-tech organisations that will
  ask "what did you validate this against."
- **eICU Collaborative Research Database** — same PhysioNet credentialing
  process and similar scope; MIMIC-III is preferred for being the more
  widely recognised dataset in published healthcare-ML literature, which
  matters for interview legibility.
- **Synthea (fully synthetic patient generator)** — no credentialing
  needed at all, and useful as a *supplement* for stress-testing pipeline
  robustness at volume, but does not provide the real-world outcome signal
  MIMIC-III does; not a substitute for it, may still be used alongside it.

## Consequences

### Positive

- Real-world clinical data gives Models 1–2 defensible, literature-comparable
  metrics rather than synthetic-only numbers, directly strengthening the
  portfolio's credibility with health-tech interviewers.
- MIMIC-III is a widely recognised dataset — using it correctly (proper
  credentialing, DUA compliance, no data leakage into public artifacts) is
  itself a demonstrable compliance/governance competency, not just a
  modeling one.

### Negative

- **This is a genuine schedule risk, not a formality.** Credentialing
  (CITI training + PhysioNet review) has a real external timeline outside
  the project's control and should be started today, tracked explicitly
  (see `.ai/memory/project-memory.md`), and escalated if it stalls, given
  the November 2026 interview-readiness target.
- Adds a compliance surface the synthetic-data-only path didn't have: DUA
  terms must be followed indefinitely (not just at download time), and any
  future public deployment or demo must be re-verified as MIMIC-III-free
  before going live.
- Two data regimes now exist (synthetic for public demos/CI, MIMIC-III for
  real model validation) rather than one — documentation and demo scripts
  must be explicit about which is in use where, to avoid ever implying
  MIMIC-III data appears in a public-facing artifact when it doesn't.

## References

- `docs/00_VISION_ML_PLATFORM.md` — Models 1–2 training data requirements
- ADR-009 — Dataset Versioning Strategy
- `.ai/memory/project-memory.md` — MIMIC-III credentialing tracked as an
  active risk with an immediate action item
- PhysioNet — MIMIC-III Clinical Database, credentialed access requirements
