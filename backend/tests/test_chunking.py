"""Structure-aware chunking (#62).

The property under test is that structure wins over length. A chunker that
splits on token count first will pass any test about chunk sizes and still
destroy the thing that makes clinical text usable — an exception clause severed
from the rule it qualifies is retrievable, plausible and wrong.
"""

import pytest

from app.models.knowledge import (
    KnowledgeNodeType,
    KnowledgeSourceType,
    KnowledgeStatus,
    UpdateCadence,
)
from app.services.chunking import (
    MIN_CHUNK_TOKENS,
    Chunk,
    chunk_document,
    estimate_tokens,
)
from app.services.ingestion.base import Section, SourceDocument


def _document(sections: tuple[Section, ...], *, heading_path: str | None = None,
              text: str = "") -> SourceDocument:
    return SourceDocument(
        source_id="TEST-1",
        source_type=KnowledgeSourceType.synthetic_guideline,
        node_type=KnowledgeNodeType.recommendation,
        title="Test document",
        text=text or "\n\n".join(s.text for s in sections),
        status=KnowledgeStatus.active,
        update_cadence=UpdateCadence.periodic,
        heading_path=heading_path,
        sections=sections,
    )


def _sentences(count: int, word: str = "guidance") -> str:
    return " ".join(f"Sentence {i} about {word} for adults." for i in range(count))


def test_each_structural_unit_becomes_its_own_chunk() -> None:
    """Units within budget are not merged to fill the window.

    Filling the window is not the goal. Merging is how an exception clause ends
    up welded to an unrelated rule and retrieved as though it qualified it.
    """
    document = _document(
        (
            Section(heading="BACKGROUND", text=_sentences(6, "background")),
            Section(heading="METHODS", text=_sentences(6, "methods")),
            Section(heading="RESULTS", text=_sentences(6, "results")),
        )
    )

    chunks = chunk_document(document, max_tokens=512)

    assert len(chunks) == 3
    assert all(not c.is_split for c in chunks)
    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    # No chunk contains text from two sections.
    assert not any("background" in c.text and "methods" in c.text for c in chunks)


def test_oversized_unit_is_token_split_within_itself() -> None:
    """The DoD case: a section longer than the budget.

    It must be split, the split must stay inside the section, and every piece
    must still carry that section's heading path.
    """
    long_section = Section(heading="RESULTS", text=_sentences(400, "results"))
    short_section = Section(heading="CONCLUSIONS", text=_sentences(5, "conclusions"))
    document = _document((long_section, short_section), heading_path="Trial report")

    assert estimate_tokens(long_section.text) > 512
    chunks = chunk_document(document, max_tokens=512, overlap_tokens=64)

    split = [c for c in chunks if c.is_split]
    whole = [c for c in chunks if not c.is_split]

    assert len(split) > 1, "an oversized section must produce multiple chunks"
    assert len(whole) == 1, "the in-budget section must survive as one chunk"
    # The split never reached across the section boundary.
    assert all("conclusions" not in c.text for c in split)
    assert all(c.heading_path == "Trial report > RESULTS" for c in split)
    assert whole[0].heading_path == "Trial report > CONCLUSIONS"


def test_split_chunks_respect_the_token_budget() -> None:
    document = _document((Section(heading="LONG", text=_sentences(400)),))

    chunks = chunk_document(document, max_tokens=256, overlap_tokens=32)

    assert len(chunks) > 1
    # The estimator over-counts by design, so a chunk at the budget is fine and
    # a chunk far over it is a bug.
    assert all(c.token_estimate <= 256 for c in chunks)


def test_split_chunks_overlap_so_a_boundary_sentence_stays_findable() -> None:
    """A sentence spanning a split must be retrievable from either side."""
    document = _document((Section(heading="LONG", text=_sentences(200)),))

    chunks = chunk_document(document, max_tokens=256, overlap_tokens=64)

    assert len(chunks) > 1
    first_tail = chunks[0].text.split()[-6:]
    assert " ".join(first_tail) in chunks[1].text


def test_a_single_unpunctuated_sentence_over_budget_is_still_emitted() -> None:
    """A long table row or unbroken paragraph must not be dropped silently."""
    monster = Section(heading="TABLE", text="x" * 8000)
    document = _document((monster,))

    chunks = chunk_document(document, max_tokens=128)

    assert len(chunks) > 1
    assert "".join(c.text for c in chunks).startswith("xxx")
    assert all(c.is_split for c in chunks)


def test_tiny_units_merge_forward_rather_than_embedding_alone() -> None:
    """A bare heading embeds to near-noise and competes for top-k slots."""
    stub = Section(heading="NOTE", text="See below.")
    body = Section(heading="BODY", text=_sentences(10))
    document = _document((stub, body))

    assert estimate_tokens(stub.text) < MIN_CHUNK_TOKENS
    chunks = chunk_document(document, max_tokens=512)

    assert len(chunks) == 1
    assert "See below." in chunks[0].text
    assert "Sentence 0" in chunks[0].text


def test_trailing_stub_merges_backward() -> None:
    document = _document(
        (Section(heading="BODY", text=_sentences(10)), Section(heading=None, text="Ends."))
    )

    chunks = chunk_document(document, max_tokens=512)

    assert len(chunks) == 1
    assert chunks[0].text.endswith("Ends.")


def test_document_without_sections_falls_back_to_its_text() -> None:
    document = _document((), text=_sentences(8))

    chunks = chunk_document(document, max_tokens=512)

    assert len(chunks) == 1
    assert chunks[0].heading_path is None


def test_empty_document_produces_no_chunks() -> None:
    assert chunk_document(_document((), text="   ")) == []


def test_heading_path_does_not_repeat_a_shared_tail() -> None:
    """"1.1.1 > 1.1.1" is a breadcrumb bug, not a structure."""
    document = _document(
        (Section(heading="1.1.1", text=_sentences(8)),),
        heading_path="Management > 1.1.1",
    )

    chunks = chunk_document(document, max_tokens=512)

    assert chunks[0].heading_path == "Management > 1.1.1"


def test_node_id_is_carried_onto_every_chunk() -> None:
    """A chunk that cannot name its node is text no citation can resolve."""
    import uuid

    node_id = uuid.uuid4()
    document = _document(
        (Section(heading="A", text=_sentences(8)), Section(heading="B", text=_sentences(8)))
    )

    chunks = chunk_document(document, node_id=node_id, max_tokens=512)

    assert chunks
    assert all(c.node_id == node_id for c in chunks)


@pytest.mark.parametrize("text", ["", "a", "short text"])
def test_token_estimate_is_always_positive(text: str) -> None:
    assert estimate_tokens(text) >= 1


def test_chunk_indexes_are_contiguous_from_zero() -> None:
    """Re-embedding replaces chunks by index, so gaps would strand old rows."""
    document = _document(
        (
            Section(heading="A", text=_sentences(400)),
            Section(heading="B", text=_sentences(8)),
            Section(heading="C", text=_sentences(400)),
        )
    )

    chunks: list[Chunk] = chunk_document(document, max_tokens=256)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
