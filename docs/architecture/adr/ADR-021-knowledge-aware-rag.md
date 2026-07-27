# ADR-021 — Knowledge-Aware RAG Architecture and PostgreSQL Graph Store

## Status

Accepted

## Context

ADR-004 (Qdrant) and ADR-005 (LangChain + LangGraph) established a vector
store and an orchestration framework for the RAG-based AI decision support
pillar. ADR-017 then specified a seven-stage *ranking* pipeline on top of
that store. Sprint 3 implements this pillar, and scoping it surfaced a
problem that neither a better vector store nor a better ranker can solve:
the corpus is stored as unstructured text, and clinical questions are
questions about structured knowledge.

Four failure modes make this concrete:

- **Similarity is not relevance.** A superseded 2019 recommendation and its
  2026 replacement use near-identical clinical language and therefore sit at
  near-identical embedding distance. Nothing in a vector index expresses
  "this one replaced that one."
- **Chunking destroys structure.** A comorbidity exception clause several
  paragraphs after the rule it exempts becomes an independent chunk with no
  link back to the rule it modifies. Retrieving the rule without its
  exception is a clinically unsafe answer, not merely an incomplete one.
- **Flat retrieval cannot compose multi-hop answers.** "What is the current
  first-line recommendation for condition X given comorbidity Y" requires the
  general recommendation, its exception child, and confirmation that no newer
  guideline supersedes it — facts that never co-occur in a single chunk.
- **No notion of authority, recency, or withdrawal.** Withdrawn guidance is
  exactly as retrievable as current guidance.

Supersession, exception-handling, and multi-hop composition are properties of
the **data model**, not of the ranker. Applying ADR-017's ranking stages to an
unstructured corpus improves the ordering of results that are already the
wrong results. Given the platform's stated targets — citation accuracy > 95%,
hallucination rate < 5% (`docs/00_VISION_ML_PLATFORM.md`) — retrieving *text*
rather than *knowledge* is not sufficient.

## Decision

Sprint 3 builds a **knowledge layer** underneath retrieval: typed entities,
explicit typed relationships, provenance and supersession, a query planner,
and typed retrieval tools. The graph is stored in the **existing PostgreSQL
database** (ADR-003) and traversed with a depth-capped recursive CTE, joined
to Qdrant vectors on a shared `node_id`.

### Storage

Two new tables alongside the existing `documents` / `embeddings` tables:

- **`knowledge_nodes`** — the unit of truth. `node_type`
  (`guideline | article | recommendation | term`), `title`, `text`,
  `source_id`, `source_type` (`pubmed | nice`), `external_ref`,
  `effective_date`, `status` (`active | superseded | withdrawn | draft`),
  `authority_tier`, `category` (JSONB), `update_cadence`
  (`static | periodic | live`), `heading_path`.
- **`knowledge_edges`** — typed relationships over a closed set:
  `SUPERSEDES | DEFINED_BY | EXCEPTION_TO | CITES | RELATED_TO`, with
  `confidence` and `extracted_by` (model id + prompt version). Unique on
  `(from_node_id, to_node_id, edge_type)`; both endpoints are foreign keys
  with `ON DELETE CASCADE`.

The closed edge set is enforced by a **PostgreSQL enum plus foreign keys**,
not by a code convention: a malformed extraction is rejected by the database,
not caught in review. `extracted_by` exists so edges can be re-validated when
the extractor model or prompt changes — extraction quality drifts as source
documents and models change, and an unversioned graph silently rots.

`embeddings` gains a nullable `node_id` foreign key. The chunk remains a
retrieval *handle*; the node becomes the unit of truth.

### Retrieval

Qdrant (ADR-004) stays, but stops being the sole source of truth: it becomes
one of four typed tools a LangGraph query planner composes —
`vector_search`, `structured_filter`, `graph_traverse`, `fact_lookup`.
Structural filtering runs *before* vector search, as a Qdrant payload filter,
never as a post-hoc pass. Every Qdrant point carries `node_id`, `status`,
`effective_date`, `category`, `source_type`, and `authority_tier` in its
payload, which is what makes that pre-filtering possible and what lets a
vector hit be joined back to typed metadata instead of returned as bare text.

Traversal sits behind a `graph_traverse` interface, so replacing the backing
store later does not touch callers.

### Relationship to ADR-017

ADR-017 remains **in force and unamended**. It specifies the *ranking* layer
(ColBERT dense retrieval, BM25 sparse matching, RRF fusion, cross-encoder
re-ranking, temporal decay); this ADR specifies the *knowledge* layer beneath
it. ADR-017's implementation moves to Sprint 4, where its stages drop into
the LangGraph pipeline this ADR establishes as additional nodes, against an
evaluation baseline already in place to prove the ranking actually helped.

This is a **sequencing decision, not a descoping one**, and is recorded as
such per the binding scope mandate in `CLAUDE.md`.

## Alternatives Considered

- **Neo4j as the graph store** — the purpose-built option: native traversal,
  Cypher, and the reference stack for most published GraphRAG work. Rejected
  for this corpus size (thousands of nodes, not millions): it adds a *third*
  source of truth that must be kept consistent with PostgreSQL and Qdrant,
  a third stateful service in the Docker Compose stack (ADR-006), and a
  second query language, in exchange for traversal performance a depth-capped
  recursive CTE already delivers at this scale. Revisit if traversal latency
  becomes the measured bottleneck rather than an assumed one — the
  `graph_traverse` interface exists so that swap does not touch callers.
- **Inferring relationships at query time with the LLM** — no schema, no
  migration, no extraction pipeline: ask the model at query time whether one
  retrieved passage supersedes another. Rejected because it reintroduces
  exactly the non-determinism this architecture exists to remove (the same
  question can yield a different supersession verdict on two runs), it
  multiplies per-query cost and latency by the number of candidate pairs, and
  it makes supersession unauditable — there is no row to point at when asked
  why an answer cited the 2019 guideline.
- **A property graph in JSONB on the existing `documents` table** — cheaper
  than new tables, but edges stored inside a JSON blob cannot carry foreign
  keys, cannot be constrained to a closed type set, and cannot be traversed
  by a recursive CTE without unnesting on every hop. It moves the integrity
  guarantee from the database back into application code, which is the thing
  the decision above is specifically trying to avoid.
- **No graph at all — improve chunking and ranking only** — the cheapest
  path, and the one most naive RAG implementations take. Rejected: see
  Context. Larger chunks reduce, but do not remove, the rule/exception split,
  and no ranking function can express supersession, because supersession is
  not a similarity signal.

## Consequences

### Positive

- Supersession, exceptions, and multi-hop composition become **queryable
  facts** rather than emergent behaviours hoped for from a ranker. "Which
  guideline is current" has a row that answers it, and an audit trail.
- Zero new infrastructure: the graph lives in the PostgreSQL instance already
  running (ADR-003), under the same Alembic migrations (ADR-013), the same
  backup and the same connection pool. Two sources of truth, not three.
- The database rejects malformed knowledge. A closed enum plus foreign keys
  means an extractor regression fails loudly at ingestion instead of quietly
  degrading retrieval months later.
- Sprint 4's ADR-017 work becomes additive — new LangGraph nodes against an
  existing pipeline and an existing evaluation baseline, rather than a
  redesign.
- Retrieval failures become attributable: four independently unit-testable
  typed tools instead of one opaque `similarity_search` call.

### Negative

- An extraction layer that naive RAG simply does not have: one constrained
  LLM call per structural unit at ingestion, with its own cost, its own
  failure modes, and its own quality-drift problem. Cost estimate and a
  corpus-size cap are a prerequisite for the extraction issue, not an
  afterthought.
- Two stores must be kept consistent on `node_id`. A node deleted in
  PostgreSQL leaves an orphaned Qdrant point unless deletion is handled
  explicitly; this is a real operational burden Neo4j-plus-Qdrant would have
  had in triplicate, but it is not zero.
- The query planner adds an LLM round trip *ahead* of retrieval. ADR-017's
  p95 < 500 ms target covers retrieval only and is already demanding; a
  per-stage latency budget is required in the planner issue.
- Recursive CTEs need explicit cycle protection. A `SUPERSEDES` chain that
  loops — entirely possible from an imperfect extractor — must be
  depth-capped and visited-set guarded, or traversal hangs.
- The graph is only as good as the extractor. `extracted_by` makes
  re-validation *possible*; performing it is scheduled work the project now
  owns.

## References

- ADR-003 — PostgreSQL as Relational Database
- ADR-004 — Qdrant as Vector Database (payload filtering, joined on `node_id`)
- ADR-005 — LangChain + LangGraph as Orchestration Framework (planner host)
- ADR-006 — Docker for Containerization (service count in the local stack)
- ADR-013 — SQLAlchemy 2.0 (async) + Alembic for ORM and Migrations
- ADR-017 — Advanced Multi-Stage RAG Retrieval Pipeline (the ranking layer;
  unamended, implemented in Sprint 4)
- ADR-022 — Anthropic Claude as LLM Provider (extraction and generation)
- `docs/superpowers/specs/2026-07-25-sprint-3-knowledge-aware-rag-design.md`
- `docs/00_VISION_ML_PLATFORM.md` — Model 3, Literature Relevance Ranker
- `docs/08_EVALUATION_FRAMEWORK.md` — retrieval evaluation metrics
- Epic #58 — Sprint 3: AI & RAG, knowledge-aware semantic RAG
