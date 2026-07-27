# ADR-022 — Anthropic Claude as LLM Provider

## Status

Accepted

## Context

ADR-005 selected LangChain + LangGraph as the orchestration framework but
deliberately left the LLM provider unspecified — at Sprint 0 there was no
concrete workload to choose against. Sprint 3 (epic #58) creates two, and they
have materially different requirements:

1. **Bulk constrained extraction at ingestion.** One LLM call per structural
   unit of the corpus, each emitting typed entities and edges from the closed
   set defined in ADR-021 (`SUPERSEDES | DEFINED_BY | EXCEPTION_TO | CITES |
   RELATED_TO`). This is high-volume, low-creativity, and schema-bound: what
   matters is that the output *validates*, cheaply, thousands of times.
2. **Grounded generation at query time.** A small number of calls per user
   question, each assembling provenance-carrying context into an answer that
   cites its sources per clinical claim and abstains when no active source
   answers. This is low-volume and quality-critical.

Optimising both with one model tier wastes money on the first workload or
quality on the second. The provider decision therefore has to cover a model
*pair*, not a single model, and the provider has to support **constrained
output** as a first-class API feature — not as prompt-engineering hope — or the
"database rejects malformed knowledge" guarantee in ADR-021 degrades into an
expensive retry loop.

The project also carries a hard privacy constraint (CLAUDE.md: treat synthetic
data as if it were real PHI), so the provider choice has to be defensible on
data-handling grounds and not only on capability.

## Decision

**Anthropic Claude, called through the existing LangChain orchestration layer
(ADR-005)** via the `langchain-anthropic` integration, with a two-model split:

| Workload | Model | Model ID | Context | Price (in / out per 1M tokens) |
|---|---|---|---|---|
| Ingestion-time extraction | Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 / $5.00 |
| Query-time generation | Claude Sonnet 5 | `claude-sonnet-5` | 1M | $3.00 / $15.00 |

Model IDs are pinned as configuration (`settings`), not hard-coded at call
sites, so a tier change is a config change and shows up in the audit log.

### Constrained extraction

Extraction uses Claude's **structured outputs** (`output_config.format` with a
JSON Schema) and/or **strict tool use** (`strict: true` on the tool
definition), both of which Haiku 4.5 supports. This is what makes the closed
edge set enforceable end to end: the schema constrains the model, the
PostgreSQL enum and foreign keys constrain the writer (ADR-021), and neither
relies on the prompt being persuasive.

Note the schema limits that apply: no recursive schemas, no numeric or string
length constraints, `additionalProperties: false` required on every object.
The extraction schema is designed inside those limits rather than around them.

### Generation

Generation uses Sonnet 5 with prompt caching on the stable system prompt and
retrieval instructions. Its 1M-token context window means multi-hop retrieval
results — the recommendation, its `EXCEPTION_TO` children, and the supersession
chain — fit in one prompt without a second summarisation pass that would break
the citation chain.

### Privacy position

**No PHI reaches the provider in Sprint 3.** The corpus is public medical
literature and clinical guidelines; the query is a clinical question, not a
patient record. This is a property of what Sprint 3 builds, not a guarantee
that holds automatically afterwards: grounding answers on patient context
(Sprint 4+) **requires a de-identification gate in front of every provider
call**, and that gate is a prerequisite for that work, not a follow-up to it.
Recorded here so the boundary is explicit rather than assumed.

Every provider call is audit-logged with the model ID, prompt version, and
retrieved node IDs — the same instrumentation ADR-005 already flagged as
necessary, since LangChain's own defaults do not preserve that traceability.

## Alternatives Considered

- **OpenAI (GPT family)** — equivalent structured-output support and a
  comparable price ladder, and would work as well technically. Rejected on
  weaker grounds than usual: there is no existing OpenAI footprint in this
  repo to build on, and no capability gap that Claude leaves open for these two
  workloads. Choosing it would mean a second provider SDK, a second key to
  manage, and a second set of rate limits, for no measured benefit. This is a
  close call and is recorded as such — if extraction quality benchmarks in
  issue #63 show a real gap, revisiting is cheap because LangChain abstracts the
  call site.
- **A local open model via Ollama (e.g. Llama, Mistral)** — zero marginal API
  cost and by far the strongest PHI story, since nothing leaves the machine.
  Genuinely attractive for a self-funded project, and rejected for two specific
  reasons rather than on principle: constrained-extraction quality on clinical
  text is materially weaker at the parameter sizes that run on this hardware,
  and bulk ingestion over the whole corpus would be slow enough to make the
  extraction pass a multi-day job on local hardware. **This is the designated
  fallback**: if patient-context grounding later makes sending anything to a
  hosted provider unacceptable — or if a real deployment has to satisfy a
  data-residency requirement — a local model behind the same LangChain
  interface is the escape hatch, at a documented quality cost.
- **A managed RAG/LLM platform (e.g. a hosted assistants API)** — would remove
  the orchestration work, but reintroduces the objection ADR-004 already raised
  against hosted vector databases: recurring cost, and it abstracts away exactly
  the pipeline this project exists to demonstrate.
- **One model tier for both workloads** — simpler configuration, and rejected
  in both directions: Sonnet 5 for extraction triples the ingestion bill for a
  schema-bound task that does not need the capability, while Haiku 4.5 for
  generation risks the citation-accuracy and abstention targets
  (`docs/08_EVALUATION_FRAMEWORK.md`) that the pillar is measured against.

## Consequences

### Positive

- Constrained extraction is enforced by the API, not by prompt wording, which
  is what makes ADR-021's closed edge set a real guarantee rather than a
  convention.
- The two-model split puts cost where volume is (Haiku 4.5 at $1/$5 for
  thousands of ingestion calls) and capability where quality is measured
  (Sonnet 5 for the handful of generation calls per question).
- No new orchestration dependency: `langchain-anthropic` slots into the
  ADR-005 stack, and the provider sits behind LangChain's chat-model
  interface, so the Ollama fallback is an implementation swap rather than a
  rewrite.
- Sonnet 5's 1M-token context removes the need to compress multi-hop retrieval
  results before generation — compression is precisely where per-claim
  citations get lost.
- The privacy boundary is written down at the moment it is still trivially
  true, so a future sprint has to argue past it rather than drift through it.

### Negative

- A recurring per-token cost on a self-funded project. Ingestion cost is
  bounded by a corpus-size cap set before the extraction issue starts (a
  standing risk in the Sprint 3 design spec), but it is real spend and the
  first genuine one in this stack.
- An external API dependency in the ingestion path: rate limits, transient
  errors, and provider availability now affect a pipeline that was previously
  fully local. Retries with backoff and idempotent re-runs are required, not
  optional.
- Model behaviour drifts across versions. Pinned model IDs plus the
  `extracted_by` column on `knowledge_edges` (ADR-021) make re-validation
  possible; performing it is scheduled work the project now owns.
- Provider lock-in at the *prompt* level even though the call site is
  abstracted — prompts and extraction schemas tuned against Claude will need
  re-tuning against any replacement. LangChain hides the SDK, not the tuning.
- Anthropic's structured-output schema subset excludes recursive schemas and
  numeric/length constraints, so some validation that could have lived in the
  schema has to live in the Pydantic layer instead.

## References

- ADR-004 — Qdrant as Vector Database
- ADR-005 — LangChain + LangGraph as Orchestration Framework
- ADR-014 — pandera for Dataset Schema/Data Validation (validation-at-boundary
  precedent)
- ADR-017 — Advanced Multi-Stage RAG Retrieval Pipeline (Sprint 4)
- ADR-021 — Knowledge-Aware RAG Architecture and PostgreSQL Graph Store
- `docs/superpowers/specs/2026-07-25-sprint-3-knowledge-aware-rag-design.md`
  (§6 query planning, §7 grounded generation, §10 privacy, §12 risks)
- `docs/08_EVALUATION_FRAMEWORK.md` — citation accuracy and abstention metrics
- Epic #58 — Sprint 3: AI & RAG, knowledge-aware semantic RAG
