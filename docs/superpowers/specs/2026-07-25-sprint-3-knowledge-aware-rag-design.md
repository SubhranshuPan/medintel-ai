# Sprint 3 Design — AI Decision Support: Knowledge-Aware Semantic RAG (Pillar 4)

**Date:** 2026-07-25
**Status:** Approved by Som, 2026-07-25
**Scope anchors:** `docs/00_VISION_ML_PLATFORM.md` (Model 3 — Literature Relevance Ranker),
`docs/02_TRD.md`, `docs/08_EVALUATION_FRAMEWORK.md`,
ADR-004 (Qdrant), ADR-005 (LangChain/LangGraph), ADR-017 (multi-stage retrieval).

---

## 1. Problem

Sprint 2 delivered the Patient Data Platform. Sprint 3 delivers Pillar 4 — RAG-based
AI decision support. The naive form of that pillar (embed the corpus, cosine-search it,
stuff the top-k into a prompt) fails on clinical content for structural reasons, not
tuning reasons:

- **Similarity is not relevance.** A superseded 2019 recommendation and its 2026
  replacement use near-identical language and sit at near-identical embedding distance.
- **Chunking destroys structure.** A comorbidity exception clause several paragraphs
  after the rule it exempts becomes an independent chunk with no link back to the rule.
- **Flat retrieval cannot compose multi-hop answers.** "What is the current first-line
  recommendation for condition X given comorbidity Y" needs the general recommendation,
  its `EXCEPTION_TO` child, and confirmation that no newer guideline supersedes it —
  facts that never co-occur in one chunk.
- **No notion of authority, recency, or exception.** Withdrawn guidance is exactly as
  retrievable as current guidance.

For a platform whose stated success criteria include citation accuracy > 95% and
hallucination rate < 5%, retrieving *text* rather than *knowledge* is not sufficient.

## 2. Decision

Sprint 3 builds the **knowledge layer**: typed entities, explicit relationships,
provenance and supersession, a query planner, and typed retrieval tools.
ADR-017's **ranking layer** (ColBERT dense, BM25 sparse, RRF fusion, cross-encoder
re-ranking, temporal decay) moves to Sprint 4.

Rationale: ranking upgrades applied to an unstructured corpus improve the ordering of
results that are already the wrong results. Supersession, exception-handling and
multi-hop composition are properties of the data model, not the ranker. Building the
knowledge layer first means Sprint 4's ranking work drops into an existing LangGraph
pipeline as additional nodes, with an evaluation baseline already in place to prove
the ranking actually helped.

This is a sequencing decision, not a descoping one. ADR-017 remains in force and
unamended; Sprint 4 implements it.

## 3. Architecture

```
ingestion ──▶ structure-aware chunking ──▶ LLM entity/edge extraction
                                                    │
                                                    ▼
                          knowledge store: PostgreSQL graph + Qdrant vectors
                                       (joined on shared node_id)
                                                    │
   user query ──▶ query planner ──▶ typed retrieval tools ──▶ grounded generation
                                                    │
                                                    ▼
                     evaluation harness — retrieval and generation scored separately
```

Qdrant (ADR-004) remains, but stops being the source of truth: it becomes one tool the
planner may call. LangGraph (ADR-005) hosts the planner and tool nodes, which is the
same host ADR-017 assumes for its ranking stages — so Sprint 4 adds nodes rather than
redesigning the pipeline.

### 3.1 Layer responsibilities

| Layer | Responsibility | Replaces |
|---|---|---|
| Ingestion | Fetch source documents with stable IDs, versions, effective dates; classify update cadence | Ad-hoc file loading |
| Structure-aware chunking | Split on document structure (headings, sections, recommendation boundaries) first; token-split only *within* an oversized structural unit | Fixed-size recursive chunking |
| Extraction | One constrained LLM call per structural unit emitting typed entities and edges from a closed set | Nothing — this layer does not exist in naive RAG |
| Knowledge store | Persist typed nodes and edges; keep vector payload joined by `node_id` | Flat vector index as sole store |
| Query planner | Classify intent, extract entities, decide whether traversal is needed, emit filters | Raw query string as the entire search input |
| Retrieval tools | Four typed tools the planner composes | A single `similarity_search` call |
| Generation | Provenance-carrying context, per-claim citation, instructed abstention | Context stuffing |
| Evaluation | Separate retrieval and generation harnesses over a gold set | Vibes |

## 4. Data model

### 4.1 `knowledge_nodes`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `UUIDMixin`, matching existing models |
| `node_type` | enum | `guideline` \| `article` \| `recommendation` \| `term` |
| `title` | varchar(512) | |
| `text` | text | The structural unit's text |
| `source_id` | varchar(255) | Stable per-source identifier |
| `source_type` | enum | `pubmed` \| `nice` |
| `external_ref` | varchar(255) | PMID / NICE guideline id |
| `effective_date` | date, nullable | Publication or effective-from date |
| `status` | enum | `active` \| `superseded` \| `withdrawn` \| `draft` |
| `authority_tier` | smallint, nullable | Source quality tier for later ranking |
| `category` | JSONB | Clinical categories/specialties |
| `update_cadence` | enum | `static` \| `periodic` \| `live` |
| `heading_path` | text, nullable | Structural breadcrumb from chunking |
| timestamps | | `TimestampMixin` |

Indexed on `(status, source_type)`, `effective_date`, and `external_ref`.

### 4.2 `knowledge_edges`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `from_node_id` | UUID FK → `knowledge_nodes` | `ON DELETE CASCADE` |
| `to_node_id` | UUID FK → `knowledge_nodes` | `ON DELETE CASCADE` |
| `edge_type` | PG enum | `SUPERSEDES` \| `DEFINED_BY` \| `EXCEPTION_TO` \| `CITES` \| `RELATED_TO` |
| `confidence` | float, nullable | Extractor confidence |
| `extracted_by` | varchar(128) | Model id + prompt version, for re-validation |
| timestamps | | |

Unique constraint on `(from_node_id, to_node_id, edge_type)`. The closed edge set is
enforced by the PostgreSQL enum plus foreign keys — a bad extraction is rejected by the
database, not by a code convention. `extracted_by` exists so edges can be re-validated
when the extractor changes, addressing the "treating the knowledge graph as static"
failure mode.

### 4.3 Relationship to existing tables

`documents` and `embeddings` (Sprint 1 migration) stay as the raw source layer.
`embeddings` gains a nullable `node_id` FK → `knowledge_nodes`. The chunk remains a
retrieval handle; the node is the unit of truth.

### 4.4 Qdrant payload

Every point carries `node_id`, `status`, `effective_date`, `category`, `source_type`,
`authority_tier`. This is what makes structural filtering run *before* vector search
rather than as a post-hoc pass, and what lets a vector hit be joined back to typed
metadata instead of returned as bare text.

### 4.5 Traversal

Recursive CTE over `knowledge_edges`, depth-capped (default 3). No Neo4j: at this corpus
size a recursive CTE is adequate, and a second datastore would mean a third source of
truth to keep consistent with PostgreSQL and Qdrant. Traversal sits behind a
`graph_traverse` interface, so swapping the backing store later does not touch callers.

## 5. Retrieval tools

| Tool | Called when | Returns |
|---|---|---|
| `vector_search(query, filters)` | Topical matching within a pre-filtered candidate set | Ranked chunks + node ids |
| `structured_filter(node_type, attributes)` | Narrowing by status, category, date range before search | Node id set |
| `graph_traverse(node_id, edge_type, hops)` | Following an explicit relationship — what supersedes this, what is an exception to this | Connected nodes + path |
| `fact_lookup(node_id, attribute)` | The query is a field read, not a search | Single typed value |

Each is independently unit-tested against a fixture graph, so a retrieval regression is
attributable to one tool rather than hidden in an end-to-end score.

`contradiction_check` from the source guide is deliberately **out of scope**: with
`SUPERSEDES` edges and a `status` field, the common conflict case is already resolved
structurally at ingestion. Revisit if evaluation shows conflicts surviving that.

## 6. Query planning

One structured-output LLM call converts the raw query into a plan before any retriever
runs:

```json
{
  "entities": ["heart failure", "chronic kidney disease"],
  "intent": "recommendation_lookup",
  "requires_graph_traversal": true,
  "traversal": {"edge_type": "EXCEPTION_TO", "hops": 1},
  "filters": {"status": "active", "category": ["cardiology"]}
}
```

The planner is a LangGraph node. Orchestration: plan → `structured_filter` →
`vector_search` within the filtered set → optional `graph_traverse` from the resolved
entity → candidate assembly. Filtering precedes vector search, never follows it.

## 7. Grounded generation

Context blocks carry provenance, not just chunk text:

```
[NICE NG106, effective 2026-03-01, status: active, supersedes NG106 v2]
"..."
```

The system prompt instructs: cite the bracketed source for every clinical claim; state
explicitly when no active source answers the question. Abstention is an instructed,
**tested** behaviour with its own metric — not a hoped-for emergent one.

Every response carries the clinical disclaimer that it supports, and does not replace,
clinical judgement. Responses persist as `Message` rows with `Citation` rows attached,
reusing the Sprint 1 models unchanged. Chat endpoints are audit-logged like every other
endpoint touching clinical content.

## 8. Evaluation

Retrieval and generation are scored separately — the failure mode this guards against is
shipping on the strength of fluent answers while retrieval is silently wrong underneath.

**Retrieval:** Recall@k against a hand-labelled gold set of (query, correct node) pairs;
supersession accuracy (does it return the current node, not the stale one); multi-hop
success rate (does the plan trigger traversal and land on the right connected node).

**Generation:** faithfulness (every claim traceable to a cited retrieved source);
abstention correctness (does it decline when no active source answers); citation
precision (cited sources are the ones the claim depends on, not merely topical).

The gold set deliberately includes supersession and multi-hop adversarial cases. A corpus
without a single superseded guideline cannot demonstrate the architecture's main claim.

## 9. Corpus

**PubMed abstracts** via NCBI E-utilities — free, real medical literature, carries
publication dates, journal, and citation relationships, so `CITES` edges, authority
tiers and (in Sprint 4) temporal decay have real signal.

**NICE clinical guidelines** — the source that exercises supersession and
`EXCEPTION_TO` most directly, and the strongest UK-healthcare signal for the portfolio's
stated audience.

## 10. Privacy and compliance

No PHI reaches the LLM provider in Sprint 3: the corpus is public medical literature and
guidelines, and the query is a clinical question, not a patient record.

Grounding answers on patient context (Sprint 4+) requires a de-identification gate before
any provider call. Recorded here so it is not assumed already handled.

## 11. Child issues (build order)

1. ADR-021 (knowledge-aware RAG architecture + PostgreSQL graph store) and ADR-022
   (Anthropic Claude as LLM provider)
2. `knowledge_nodes` / `knowledge_edges` models, Alembic migration, repository layer
3. Corpus ingestion connectors — PubMed E-utilities + NICE subset
4. Structure-aware chunking, embedding, Qdrant collection with filterable payload
5. LLM entity/relationship extraction with constrained schema and supersession detection
6. Retrieval tool layer — the four typed tools
7. Query planner + LangGraph orchestration
8. Grounded generation + conversation/chat endpoints
9. Evaluation harness — gold set, retrieval and generation metrics
10. Frontend clinical chat UI — citations, provenance, abstention state

## 12. Risks

**NICE licensing.** NICE content is licensed and bulk scraping likely breaches their
terms. Plan: a small manually-curated subset with attribution, or syndication API access
if obtainable. Must be resolved at issue 3, not discovered at issue 9.

**Extraction cost.** One LLM call per structural unit at ingestion. Haiku 4.5 keeps unit
cost low, but a corpus-size cap and a cost estimate are required before issue 5 starts.

**Latency.** The planner adds an LLM round trip ahead of retrieval. ADR-017's
< 500 ms p95 target covers retrieval only and is already demanding; a per-stage latency
budget is part of issue 7, not an afterthought.

**Extraction quality drift.** Edges carry `extracted_by` precisely so they can be
re-validated when the extractor changes. Periodic re-validation is scheduled work, not a
one-off ingestion concern.

## 13. Out of scope

ADR-017 ranking stages (Sprint 4). Predictive ML models 1 and 2. Patient-context
grounding. Auth hardening backlog (#24, #25, #26) remains unscheduled.
