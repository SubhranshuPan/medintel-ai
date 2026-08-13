"""Embedding providers (#62) — behind a protocol, deliberately.

**Open decision, flagged not buried.** No ADR has chosen an embedding model.
ADR-022 selected Anthropic Claude for extraction and generation, and Anthropic
publishes no embedding endpoint, so the embedding provider is a genuinely
separate choice with its own tradeoffs (a local biomedical model such as
PubMedBERT versus a hosted general-purpose one: domain fit and zero per-call
cost against operational weight and a heavy dependency). Making that call
silently inside an implementation file is precisely the kind of decision this
repo records as an ADR, so it is **not** made here.

What #62 needs is the chunk-to-Qdrant path proven end to end: structure-aware
chunks, a payload joined on ``node_id``, and filtering executed by Qdrant rather
than in Python afterwards. None of that depends on which model produces the
vectors, so this module defines the seam — :class:`EmbeddingProvider` — and
ships one deterministic implementation to develop and test against.

:class:`DeterministicEmbedder` is **not** a semantic model and must never be
used to produce a corpus anyone reasons over. It exists so the suite runs
offline, with no API key and no model download, and so a retrieval test asserts
on filtering and plumbing rather than on embedding quality it cannot control.
It is named to make substituting it for the real thing an obvious mistake.
"""

import hashlib
import math
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

#: Dimensionality of the placeholder embedder. Matches the common 768-dim
#: biomedical encoder family, so the Qdrant collection created in development
#: has the same shape it will have once a real provider lands.
DEFAULT_DIMENSION = 768


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turns text into vectors. The one seam a model swap has to pass through."""

    @property
    def dimension(self) -> int:
        """Vector length. Must match the Qdrant collection's configured size."""

    @property
    def model_id(self) -> str:
        """Stable identifier, recorded so a re-embed can be scoped to a model."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed ``texts``, returning one vector per input, in order."""


class DeterministicEmbedder:
    """Hash-based pseudo-embeddings for offline development and tests.

    Deterministic across processes and runs, unit-normalised so cosine distance
    is well-defined, and completely without semantic meaning: two paraphrases of
    the same recommendation are as far apart as two unrelated documents.

    That is a feature for the tests it serves. A filtering test that passed only
    because similar text happened to rank together would not be testing the
    filter, and this embedder makes such an accident impossible.
    """

    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_id(self) -> str:
        return f"deterministic-hash-v1/{self._dimension}"

    def _vector(self, text: str) -> list[float]:
        # Expand a digest to the required width by re-hashing with a counter,
        # rather than tiling one digest, which would make distant dimensions
        # perfectly correlated.
        raw = bytearray()
        counter = 0
        seed = text.encode("utf-8")
        while len(raw) < self._dimension * 2:
            raw.extend(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())
            counter += 1

        # Two bytes per dimension, centred on zero so vectors are not confined
        # to a single orthant (where every pair would look similar).
        values = [
            int.from_bytes(raw[i * 2 : i * 2 + 2], "big") / 32767.5 - 1.0
            for i in range(self._dimension)
        ]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]
