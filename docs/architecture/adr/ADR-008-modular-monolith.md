# ADR-008 — Modular Monolith Architecture

## Status

Accepted

## Context

The platform's five pillars — patient data platform, clinical analytics
dashboard, ML risk-prediction engine, RAG-based AI decision support, and
reporting/export — need clear boundaries for maintainability and to
demonstrate deliberate architectural thinking in interviews. At the same
time, a single developer on a fixed budget and an interview-ready-by-
November-2026 timeline cannot absorb the operational complexity of real
microservices (independent deploys, service discovery, distributed
tracing, N sets of infrastructure) without materially risking that
timeline.

## Decision

A modular monolith was chosen: one deployable FastAPI application,
internally organized into bounded modules per pillar, each with its own
routers, services, and schemas, communicating in-process rather than over
the network.

## Alternatives Considered

- Microservices — proper independent service boundaries and scaling, but
  the operational overhead (service discovery, inter-service auth,
  distributed tracing/observability, separate deployment pipelines per
  service) is disproportionate for one developer and adds real risk to the
  timeline.
- Layered monolith — global layers (`api/`, `services/`, `models/`) cutting
  across all five pillars; faster to start, but blurs pillar boundaries,
  makes it harder to reason about or later extract a module, and reads as
  less deliberate under interview scrutiny.

## Consequences

### Positive

- Per-pillar module boundaries keep the codebase navigable and support a
  credible interview narrative — clear service boundaries exist even
  inside a monolith, so the system could be split into microservices later
  if load demanded it.
- A single deployable unit means one CI pipeline, one Docker image, and one
  set of environment/config concerns, which is realistic to build and
  operate on this timeline.
- In-process calls between modules avoid the network latency and failure
  modes (timeouts, retries, partial failure) that a microservices design
  would need to handle explicitly.

### Negative

- Without discipline, module boundaries erode over time into a de facto
  layered monolith — mitigated by enforcing import rules and per-module
  ownership as the codebase grows, not a one-time decision.
- Scaling is all-or-nothing: the ML inference module can't be scaled
  independently under load the way a dedicated microservice could.
- The "this could become microservices later" narrative is only credible if
  module boundaries are actually respected in the code, not merely asserted
  in this document — worth revisiting if boundaries start slipping.

## References

- ADR-001 — FastAPI as backend framework
- ADR-010 — ML model serving pattern
- `docs/00_VISION_ML_PLATFORM.md`
