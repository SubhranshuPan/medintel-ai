# ADR-023: Corpus Sources and Licensing — PubMed Live, NICE Substituted

**Status:** Accepted
**Date:** 2026-08-13
**Deciders:** Som (Subhranshu Panda)
**Supersedes:** none
**Related:** ADR-004 (Qdrant), ADR-021 (knowledge-aware RAG), ADR-022 (LLM provider)
**Implements:** Sprint 3 issue #61 (corpus ingestion), epic #58

---

## Context

Sprint 3's knowledge layer retrieves over a corpus of clinical literature and
guidance. The Sprint 3 design spec (§9) named two sources: **PubMed abstracts**
via NCBI E-utilities, and **NICE clinical guidelines**.

The design spec (§12) flagged NICE licensing as a risk to be resolved *at the
ingestion issue, not discovered at the evaluation issue*. This ADR resolves it.

Two things depend on the answer and cannot proceed without it:

1. **The evaluation harness (#67)** needs supersession and multi-hop adversarial
   cases. A corpus with no superseded guidance cannot demonstrate the
   architecture's central claim — that retrieving *knowledge* beats retrieving
   *text* precisely because it knows which version is current.
2. **Every citation the platform renders** carries a source attribution. If the
   attribution is wrong, the platform's most visible output is a falsehood, and
   the pillar's stated success criterion (citation accuracy > 95%) is
   meaningless.

### What was actually checked

**PubMed / NCBI E-utilities.** Public API, free, no licence blocking programmatic
retrieval of abstracts and metadata. NCBI imposes conditions rather than
restrictions: identify the client with a `tool` name and contact `email` on every
request, and stay within the rate limit (3 requests/second unregistered, 10 with
an API key). Bulk abuse gets a client blocked, and NCBI emails the registered
address before doing so.

**NICE.** NICE guidance is published under the NICE UK Open Content Licence.
That licence is narrower than it sounds: it is territory-limited, non-commercial,
and does not grant the bulk extraction and redistribution this corpus would
require. NICE does operate a syndication API for programmatic reuse, but access
is granted per-application through an approval process. **We hold no such
grant.**

## Decision

**PubMed: ingest live**, via E-utilities, identified and rate-limited, with a
hard cap on records per run.

**NICE: do not ingest, do not scrape.** No scraper is shipped against
nice.org.uk — not throttled, not "small enough to be fine", not "it's only a
portfolio project". A licence that does not permit the use is not made to permit
it by keeping the request volume low.

In its place, ship an **authored guideline corpus** — the fallback the issue
itself pre-authorised — under a distinct source type, `synthetic_guideline`.

### Why a separate source type rather than reusing `nice`

This is the part that matters most and is the cheapest to get wrong.

Reusing the `nice` value would have avoided a migration and kept the enum
smaller. It would also have meant that every row of authored text claimed a
publisher that did not publish it, and every rendered citation attributed
authored guidance to a real national body. For a platform whose entire
architectural argument is that **provenance is a first-class, queryable fact**,
falsifying the provenance column to save a migration is self-defeating: the
retrieval layer filters and cites on exactly that column.

So `knowledge_source_type` gains `synthetic_guideline`, and
`knowledge_nodes.source_venue` carries the issuing body — for this corpus, a
string that names it as authored. The label is visible at the point of citation,
not buried in a module docstring.

### What the authored corpus deliberately contains

The corpus is authored, but its *shape* is faithful to real guidance: stable
guideline ids, numbered recommendations, effective dates, explicit "this
replaces X" declarations, and exception clauses that sit structurally apart from
the rule they qualify.

It is written to exercise specific retrieval behaviours rather than to be large:

- **A supersession pair** — a 2019 heart-failure guideline and its 2026
  replacement, both answering the same clinical question at recommendation
  1.1.1, in near-identical language. This is the case that defeats naive vector
  search, since the two sit at near-identical embedding distance.
- **Exception clauses** — severe CKD and symptomatic hypotension as exceptions to
  a first-line recommendation, and mechanical valve / mitral stenosis as an
  exception to a DOAC recommendation. These are the multi-hop `EXCEPTION_TO`
  cases flat chunking cannot compose.
- **A withdrawn guideline** with no replacement, so "abstain when no active
  source answers" has something real to abstain over.

A larger auto-collected corpus would not have these properties, because nobody
would have written them in on purpose.

## Consequences

**Positive**

- No licence is breached, and there is nothing to unwind if this project is ever
  shown publicly or discussed in an interview.
- No row misattributes its source. Citation accuracy is measurable against a
  ground truth that is actually true.
- The evaluation harness (#67) has supersession, exception and abstention cases
  guaranteed to exist, rather than hoped for in a scraped corpus.
- PubMed supplies real publication dates and real reference lists, so `CITES`
  edges, authority tiers and Sprint 4's temporal decay have genuine signal. The
  synthetic half does not have to carry the realism burden alone.

**Negative — stated plainly**

- The guideline half of the corpus is **not real clinical guidance**. Retrieval
  quality over it is evidence about the *architecture*, not about performance on
  real NICE content. Any evaluation result must be reported with that caveat
  attached; presenting a metric from this corpus as a NICE benchmark would be a
  worse misrepresentation than the licensing breach this ADR avoids.
- The corpus is small, so recall metrics have wide confidence intervals and
  retrieval looks easier than it would at scale.
- Nothing generated the authored content but deliberate authorship, so it cannot
  surface the messy real-world structure (inconsistent numbering, mid-document
  errata) a production ingestion pipeline eventually has to survive.

**Neutral**

- `synthetic_guideline` is permanent once rows exist. The downgrade path refuses
  to run while any row uses it rather than relabelling those rows to `nice`,
  which would introduce the exact false attribution the value exists to prevent.

## Revisiting this

Applying for NICE syndication access is worthwhile and is **not** blocked by this
decision. If a grant is obtained:

1. A fetch layer lands in front of `parse_guideline_corpus`; the parsing,
   persistence and edge-resolution code is unchanged, because the connector
   boundary already assumes a local-or-remote source.
2. Real content ingests under the existing `nice` source type, alongside rather
   than on top of the authored corpus.
3. The authored corpus stays, as the evaluation harness's adversarial set. Its
   deliberately-constructed supersession and exception cases remain useful even
   once real guidance is present — arguably more so, since real guidance rarely
   packs that many edge cases into four documents.

## Alternatives considered

**Scrape NICE anyway, politely.** Rejected. The volume of a breach does not
change whether it is one. It would also have to be disclosed or hidden in an
interview setting, and both options are bad.

**Use a different real guideline source with a permissive licence** (e.g. certain
WHO or CDC materials). Viable and worth revisiting, but rejected for this sprint:
sourcing, licence-checking and writing a connector for an unfamiliar publisher is
its own body of work, and it would still not guarantee the supersession density
the evaluation harness needs. Better as a follow-up than as a blocker on #61.

**PubMed only, no guidelines at all.** Rejected. PubMed abstracts carry almost no
supersession structure and no exception clauses — they are the wrong shape for
the behaviours this pillar exists to demonstrate. A corpus of abstracts alone
would let the knowledge layer be built but not shown to work.

**Label the authored corpus `nice` and note the caveat in documentation.**
Rejected, as above. A caveat in a document does not travel with a rendered
citation, and the citation is what a clinician sees.
