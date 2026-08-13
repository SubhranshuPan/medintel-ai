"""Structure-aware chunking (#62) — split on meaning before splitting on length.

Fixed-size recursive chunking is the default in most RAG stacks and is the wrong
default for clinical text. A comorbidity exception clause several paragraphs
after the rule it exempts becomes an independent chunk with no link back to the
rule, and the retrieval layer then has no way to compose the two (design spec
§1). The structure the publisher authored — sections, numbered recommendations,
abstract labels — is exactly the structure that carries clinical meaning, so it
is the structure chunking respects.

The rule is therefore: **split on structure first**; token-split only *within* a
structural unit that exceeds the budget, and only with overlap, so an oversized
section degrades to something usable rather than being truncated or dropped.

Every chunk keeps its ``node_id`` and its ``heading_path``. A chunk is a
retrieval handle; the node is the unit of truth. That is what lets a vector hit
be resolved to typed, provenanced knowledge instead of returned as bare text.

**On token counting.** There is no tokenizer dependency here. Anthropic's token
count is an API call (ADR-022), which is the wrong thing to do per chunk at
ingestion time, and vendoring a different vendor's tokenizer would measure the
wrong model anyway. :func:`estimate_tokens` is a documented heuristic with a
deliberate safety margin — it over-estimates rather than under-estimates, so the
failure direction is chunks slightly smaller than the budget rather than
requests that overflow a context window. Swap in a real tokenizer here if
measurement ever shows the margin costs retrieval quality.
"""

import re
from dataclasses import dataclass
from uuid import UUID

from app.services.ingestion.base import Section, SourceDocument

#: Target size for one chunk. Comfortably inside any embedding model's window,
#: and small enough that a retrieved chunk is a quotable passage rather than a
#: page a clinician has to scan.
DEFAULT_MAX_TOKENS = 512

#: Overlap applied only when an oversized unit is token-split. Carries the tail
#: of one window into the head of the next so a sentence spanning the boundary
#: is retrievable from either side.
DEFAULT_OVERLAP_TOKENS = 64

#: Structural units shorter than this are merged into the following unit rather
#: than embedded alone. A bare heading or a one-line stub embeds to near-noise
#: and competes for top-k slots against passages that actually answer something.
MIN_CHUNK_TOKENS = 16

#: Characters per token. English prose runs ~4; clinical text with drug names,
#: dosages and abbreviations tokenises worse, so 3.5 over-estimates the count
#: slightly and keeps chunks inside the budget rather than over it.
_CHARS_PER_TOKEN = 3.5

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _tokens_for_chars(char_count: int) -> int:
    """Token estimate for a string of ``char_count`` characters."""
    return max(1, int(char_count / _CHARS_PER_TOKEN) + 1)


def estimate_tokens(text: str) -> int:
    """Approximate token count. Deliberately errs high — see the module docstring."""
    return _tokens_for_chars(len(text))


@dataclass(frozen=True, slots=True)
class Chunk:
    """One embeddable passage, still attributable to its node.

    ``chunk_index`` is per node and contiguous from zero, so re-embedding a node
    can replace its chunks by index without a separate identity scheme.
    """

    node_id: UUID | None
    chunk_index: int
    text: str
    #: Full structural breadcrumb, e.g.
    #: "Pharmacological management > HFrEF > First-line > 1.1.1 > BACKGROUND".
    #: Retained so a retrieved passage can be shown inside the structure it came
    #: from rather than as an orphaned paragraph.
    heading_path: str | None
    #: True when this chunk came out of a token split of an oversized unit,
    #: rather than being a whole structural unit. Worth knowing at evaluation
    #: time: a retrieval miss on a split chunk and one on a whole section have
    #: different causes and different fixes.
    is_split: bool = False

    @property
    def token_estimate(self) -> int:
        return estimate_tokens(self.text)


def _join_path(*parts: str | None) -> str | None:
    """Breadcrumb from the non-empty parts, deduplicating a repeated tail.

    Parts are flattened to segments before comparison, because a node's
    ``heading_path`` is itself a breadcrumb: joining "Management > 1.1.1" with
    a section heading of "1.1.1" must not read "Management > 1.1.1 > 1.1.1".
    """
    segments: list[str] = []
    for part in parts:
        if not part:
            continue
        for segment in part.split(">"):
            segment = segment.strip()
            if segment and (not segments or segments[-1] != segment):
                segments.append(segment)
    return " > ".join(segments) if segments else None


def _split_oversized(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """Token-split one oversized unit, preferring sentence boundaries.

    Only ever called *within* a structural unit, so a split never merges two
    sections into one chunk. Sentence-aligned where possible: cutting mid-clause
    in a dosing instruction can produce a fragment that reads as complete
    guidance while omitting the qualifier that made it safe.
    """
    sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
    if not sentences:
        return []

    windows: list[str] = []
    current: list[str] = []
    # Exact character length of ``" ".join(current)``. Tracked rather than
    # accumulated from per-sentence token estimates: each estimate truncates,
    # so summing them drifts from the estimate of the joined window and lets a
    # window creep over the budget it was checked against.
    current_chars = 0

    def _chars_with(sentence: str) -> int:
        return current_chars + (1 if current else 0) + len(sentence)

    def _flush() -> None:
        nonlocal current, current_chars
        if current:
            windows.append(" ".join(current))
            current, current_chars = [], 0

    for sentence in sentences:
        # A single sentence over the budget (a long table row, an unpunctuated
        # paragraph) still has to be emitted; hard-wrap it on characters.
        if estimate_tokens(sentence) > max_tokens:
            _flush()
            width = int(max_tokens * _CHARS_PER_TOKEN)
            windows.extend(
                sentence[start : start + width]
                for start in range(0, len(sentence), width)
            )
            continue

        if current and _tokens_for_chars(_chars_with(sentence)) > max_tokens:
            windows.append(" ".join(current))
            # Carry back whole sentences from the tail until the overlap budget
            # is spent, so the overlap is readable rather than a severed clause.
            carried: list[str] = []
            carried_chars = 0
            for previous in reversed(current):
                extra = carried_chars + (1 if carried else 0) + len(previous)
                if _tokens_for_chars(extra) > overlap_tokens:
                    break
                carried.insert(0, previous)
                carried_chars = extra
            current, current_chars = carried, carried_chars

        current_chars = _chars_with(sentence)
        current.append(sentence)

    _flush()
    return [window.strip() for window in windows if window.strip()]


def _units(document: SourceDocument) -> list[Section]:
    """The document's structural units, falling back to its whole text."""
    units = [s for s in document.sections if s.text and s.text.strip()]
    if units:
        return units
    if document.text and document.text.strip():
        return [Section(heading=None, text=document.text)]
    return []


def chunk_document(
    document: SourceDocument,
    *,
    node_id: UUID | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    min_tokens: int = MIN_CHUNK_TOKENS,
) -> list[Chunk]:
    """Chunk one source document, structure first.

    A structural unit within the budget becomes exactly one chunk — it is not
    merged with its neighbours to fill the window, because filling the window is
    not the goal and merging is how an exception clause ends up welded to an
    unrelated rule.

    A unit under ``min_tokens`` is merged forward into the next unit instead of
    being embedded alone, and a trailing stub merges backward, so no chunk is
    both tiny and orphaned.
    """
    units = _units(document)
    if not units:
        return []

    # Merge stubs before splitting: a heading-only unit should join the section
    # it introduces, and doing it first keeps the budget check honest.
    merged: list[Section] = []
    pending: Section | None = None
    for unit in units:
        if pending is not None:
            unit = Section(
                heading=pending.heading or unit.heading,
                text=f"{pending.text.strip()}\n\n{unit.text.strip()}",
            )
            pending = None
        if estimate_tokens(unit.text) < min_tokens:
            pending = unit
            continue
        merged.append(unit)
    if pending is not None:
        if merged:
            last = merged[-1]
            merged[-1] = Section(
                heading=last.heading,
                text=f"{last.text.strip()}\n\n{pending.text.strip()}",
            )
        else:
            # The whole document is shorter than the stub threshold. Emit it —
            # a short guideline is still guidance.
            merged.append(pending)

    chunks: list[Chunk] = []
    for unit in merged:
        text = unit.text.strip()
        path = _join_path(document.heading_path, unit.heading)
        if estimate_tokens(text) <= max_tokens:
            chunks.append(
                Chunk(
                    node_id=node_id,
                    chunk_index=len(chunks),
                    text=text,
                    heading_path=path,
                    is_split=False,
                )
            )
            continue
        for window in _split_oversized(text, max_tokens, overlap_tokens):
            chunks.append(
                Chunk(
                    node_id=node_id,
                    chunk_index=len(chunks),
                    text=window,
                    heading_path=path,
                    is_split=True,
                )
            )
    return chunks
