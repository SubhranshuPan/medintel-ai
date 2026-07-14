# ADR-017 — Advanced Multi-Stage RAG Retrieval Pipeline

## Status

Accepted

## Context

ADR-004 (Qdrant) and ADR-005 (LangChain + LangGraph) established the vector
store and orchestration framework for RAG-based AI decision support, but
only as single-stage dense vector similarity search. The platform vision
(`docs/00_VISION_ML_PLATFORM.md`, Model 3 — Literature Relevance Ranker)
requires retrieval quality good enough to report NDCG@5 > 0.75 and citation
accuracy > 95%, which single-stage dense retrieval alone does not reliably
achieve for medical literature: pure embedding similarity misses exact
terminology matches (drug names, ICD codes) that keyword search catches,
and doesn't account for source quality, recency, or citation relationships.

## Decision

**A seven-stage retrieval pipeline**, implemented as a LangGraph graph
(each stage a node, consistent with ADR-005) sitting in front of the
existing Qdrant-backed dense retrieval:

1. **Dense passage retrieval** — ColBERT late-interaction embeddings against
   Qdrant (upgrading from the current single-vector embedding scheme;
   ColBERT's multi-vector-per-passage representation is stored as Qdrant
   named vectors on the same collection).
2. **Sparse BM25 keyword matching** — run in parallel via a lexical index
   (`rank_bm25` or Postgres full-text search on the same document store)
   to catch exact terminology dense retrieval misses.
3. **Metadata filtering** — publication year, journal quality tier, source
   type, applied as a Qdrant payload filter alongside the vector search
   rather than as a post-hoc pass, so it doesn't discard high-relevance
   results before they're seen.
4. **Fusion (Reciprocal Rank Fusion)** — combines the dense and sparse
   result lists into one ranked list without needing to normalize
   incomparable similarity scores across the two methods.
5. **Cross-encoder re-ranking** — a smaller set of top-N fused candidates
   (N ≈ 20–50) re-scored with a cross-encoder model for precision at the
   top of the list, where it matters most for citation accuracy.
6. **Citation graph traversal** — surfaces directly-cited or citing papers
   for the top re-ranked results, catching foundational or follow-up work
   that similarity search alone wouldn't surface.
7. **Temporal decay** — a recency weighting applied to the final ranking so
   otherwise-similar results favour more recent literature, without fully
   excluding older foundational papers.

Each stage is independently evaluable against the retrieval test set
(`08_EVALUATION_FRAMEWORK.md`) so a regression in one stage (e.g. the
re-ranker) is attributable rather than hidden inside one end-to-end score.

## Alternatives Considered

- **Keep single-stage dense retrieval, tune embeddings only** — cheapest,
  but caps achievable NDCG/citation-accuracy well below the vision's
  targets; medical literature retrieval is a well-studied case where hybrid
  dense+sparse consistently outperforms either alone.
- **Managed hybrid search (e.g. a hosted search API)** — would remove the
  fusion/re-ranking engineering, but reintroduces the same objection ADR-004
  already raised against hosted vector DBs: cost and loss of an
  interview-demonstrable, self-built pipeline.
- **Skip cross-encoder re-ranking, rely on RRF fusion alone** — simpler and
  cheaper at query time, but RRF fusion alone does not reliably hit the
  Precision@5 > 0.85 target; re-ranking is the stage most directly
  responsible for top-of-list precision in published RAG evaluations.
- **Skip citation graph traversal** — the least essential stage relative to
  the achievable NDCG target; kept in scope because citation-following is
  specifically how clinicians and researchers navigate literature, and its
  absence would be a noticeable gap in interview conversations about the
  RAG system's design.

## Consequences

### Positive

- Matches the retrieval-quality bar the platform vision commits to
  (NDCG@5 > 0.75, Precision@5 > 0.85, citation accuracy > 95%), which
  single-stage dense retrieval could not credibly hit.
- Each stage is independently swappable and evaluable — a LangGraph node
  can be replaced (e.g. a different cross-encoder) without redesigning the
  pipeline, and the evaluation framework can attribute regressions to a
  specific stage.
- A multi-stage retrieval pipeline with fusion and re-ranking is precisely
  the kind of RAG-architecture depth that differentiates a portfolio
  project from a LangChain quick-start tutorial — directly supports the
  "don't dumb the project down" instruction in `CLAUDE.md`.

### Negative

- Query latency grows with every added stage; the platform vision's
  RAG retrieval < 500ms (p95) target is materially harder to hit with seven
  stages than with one, and will need real latency budgeting per stage
  (tracked in `07_ML_OPS.md`/`12_MONITORING_ALERTS.md`), including deciding
  which stages can run in parallel (dense + sparse already can; re-ranking
  and citation traversal cannot start until fusion completes).
- ColBERT's multi-vector representation increases Qdrant storage and index
  size per document versus the single-vector scheme currently in place —
  a migration of the existing collection is required, not just an addition.
- Six new moving parts (ColBERT encoder, BM25 index, RRF fusion logic,
  cross-encoder model, citation graph store, decay function) to build, test,
  and keep evaluated — significant scope relative to a single-developer
  timeline; this is explicitly one of the areas flagged as a schedule risk
  alongside MIMIC-III credentialing (ADR-018).

## References

- ADR-004 — Qdrant as Vector Database
- ADR-005 — LangChain + LangGraph as Orchestration Framework
- ADR-016 — ML Monitoring & Alerting Stack (query latency monitoring)
- `docs/00_VISION_ML_PLATFORM.md` — Model 3, Literature Relevance Ranker
- `docs/08_EVALUATION_FRAMEWORK.md` — retrieval evaluation metrics/test set (to be written)
