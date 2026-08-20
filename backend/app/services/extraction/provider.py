"""The model seam and the spend guard (#63).

Two jobs, both about keeping bulk extraction from being the thing that goes
wrong quietly.

**The seam.** :class:`ExtractionModel` is the one interface the runner talks to,
mirroring :class:`~app.services.embedding.EmbeddingProvider`. ADR-022 records
that swapping providers should be cheap precisely because extraction quality on
clinical text is the open question that would justify swapping; a protocol makes
that a one-class change rather than a rewrite. It also means the test suite runs
offline, with no API key, against a scripted model.

**The guard.** Extraction is the only part of this platform that spends money
per row of corpus. A loop that costs a fraction of a cent per structural unit is
harmless until a retry storm or an oversized corpus makes it three thousand
calls, and the way that failure normally surfaces is a bill. :class:`CostMeter`
therefore counts tokens as they are consumed and refuses the *next* call once the
ceiling is reached — before it is made, not after.

Rates are declared here rather than fetched: a hard-coded price that drifts is a
wrong estimate, but a silently-changing one is an unbounded spend, and the
former is the safer direction to be wrong in.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.services.extraction.schema import (
    EXTRACTION_TOOL_NAME,
    EXTRACTION_TOOL_SCHEMA,
)

logger = logging.getLogger(__name__)

#: USD per million tokens, per ADR-022's model table. Input rate first.
MODEL_RATES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
}

#: Fallback rate for an unlisted model. Deliberately the most expensive tier we
#: know about: an unknown model should exhaust the budget early and prompt
#: someone to add its real rate, not run to completion on an optimistic guess.
FALLBACK_RATE_USD_PER_MTOK = MODEL_RATES_USD_PER_MTOK["claude-sonnet-5"]

#: Output tokens allowed per extraction call. The schema's own caps
#: (``MAX_ENTITIES_PER_UNIT``, ``MAX_RELATIONSHIPS_PER_UNIT``) bound the useful
#: response well below this; the limit is what stops a degenerate repetition
#: loop from billing for a full context window.
MAX_OUTPUT_TOKENS = 1024

DEFAULT_MAX_ATTEMPTS = 4
#: First backoff step, doubled per attempt and jittered.
BASE_BACKOFF_SECONDS = 1.0


class BudgetExceededError(RuntimeError):
    """Raised when a run has spent its ceiling. Stops the run, does not retry."""


class ExtractionUnavailableError(RuntimeError):
    """The provider could not be reached, or is not configured.

    Carries the tokens the failed attempts consumed. A provider that refuses
    every call still bills for every call, so the spend has to survive the
    exception — otherwise a systematic refusal is the one failure mode that
    burns money while the meter reads zero and the budget ceiling never trips.
    """

    def __init__(
        self, message: str, *, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


@dataclass(frozen=True, slots=True)
class ExtractionCall:
    """One completed model call: what it returned and what it cost."""

    payload: dict[str, Any]
    input_tokens: int
    output_tokens: int


@runtime_checkable
class ExtractionModel(Protocol):
    """Turns a passage into a raw tool-call payload. The only provider seam."""

    @property
    def model_id(self) -> str:
        """Pinned model id, stamped into ``extracted_by`` on every edge."""

    async def extract(self, system: str, user: str) -> ExtractionCall:
        """Run one constrained extraction. Raises on unrecoverable failure."""


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """USD for a token count at ``model_id``'s published rate."""
    rate_in, rate_out = MODEL_RATES_USD_PER_MTOK.get(
        model_id, FALLBACK_RATE_USD_PER_MTOK
    )
    return (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000


@dataclass(slots=True)
class CostMeter:
    """Running spend for one extraction run, with a hard ceiling.

    ``budget_usd`` of ``None`` means unmetered, which is only ever appropriate
    for a scripted model in tests. Every production call site passes a number.
    """

    model_id: str
    budget_usd: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def spent_usd(self) -> float:
        return estimate_cost_usd(self.model_id, self.input_tokens, self.output_tokens)

    def check(self) -> None:
        """Refuse the next call if the ceiling is already reached.

        Checked before spending rather than after, so the budget is a ceiling on
        what is actually billed rather than on what has been noticed.
        """
        if self.budget_usd is not None and self.spent_usd >= self.budget_usd:
            raise BudgetExceededError(
                f"extraction budget of ${self.budget_usd:.2f} reached after "
                f"{self.calls} calls (${self.spent_usd:.4f} spent)"
            )

    def record(self, call: ExtractionCall) -> None:
        self.input_tokens += call.input_tokens
        self.output_tokens += call.output_tokens
        self.calls += 1


class AnthropicExtractor:
    """Claude Haiku 4.5 behind strict tool use (ADR-022).

    Tool use rather than free-text-and-parse: the response either arrives as a
    ``tool_use`` block matching :data:`EXTRACTION_TOOL_SCHEMA` or it does not
    arrive at all. That is what makes ADR-021's closed edge set enforceable by
    the API rather than by the prompt being persuasive.

    Called through the provider SDK directly rather than through LangChain. The
    orchestration ADRs (ADR-005, ADR-022) put query-time work behind LangGraph
    and that still holds — but this is one schema-bound call per structural unit
    with no chain, no memory and no branching, so the framework would add a
    dependency tree and an abstraction over ``tools=[...]`` without adding
    anything callers can use. LangGraph enters at #65, where there is actually a
    graph to orchestrate.
    """

    def __init__(
        self,
        client: Any,
        *,
        model_id: str = "claude-haiku-4-5",
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._max_attempts = max(1, max_attempts)

    @property
    def model_id(self) -> str:
        return self._model_id

    async def extract(self, system: str, user: str) -> ExtractionCall:
        last_error: Exception | None = None
        # Tokens burned by attempts that did not produce a usable result are
        # still billed, so they are carried into the returned call. Reporting
        # only the successful attempt's usage would make a systematic refusal —
        # four charged calls per unit — read as $0.00 on the meter, and the
        # budget ceiling would never trip on precisely the failure it exists to
        # stop.
        spent_input = 0
        spent_output = 0
        for attempt in range(self._max_attempts):
            try:
                response = await self._client.messages.create(
                    model=self._model_id,
                    max_tokens=MAX_OUTPUT_TOKENS,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    tools=[
                        {
                            "name": EXTRACTION_TOOL_NAME,
                            "description": (
                                "Record the clinical terms this passage defines "
                                "and its relationships to the candidate passages."
                            ),
                            "input_schema": EXTRACTION_TOOL_SCHEMA,
                        }
                    ],
                    # Force the tool: a model that answers in prose has produced
                    # nothing this pipeline can validate, and retrying it is
                    # cheaper than teaching the parser to read prose.
                    tool_choice={"type": "tool", "name": EXTRACTION_TOOL_NAME},
                )
            except Exception as exc:  # noqa: BLE001 - provider-agnostic by design
                # The SDK's exception hierarchy is provider-specific and this
                # class is the only place that knows about it; distinguishing
                # retryable from terminal would couple the seam to it. Bounded
                # retries with backoff handle the common transient cases
                # (429, 529, connection reset) and a terminal error simply
                # exhausts the attempts and surfaces with its own message.
                last_error = exc
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise ExtractionUnavailableError(
                    f"extraction failed after {self._max_attempts} attempts: {exc}",
                    input_tokens=spent_input,
                    output_tokens=spent_output,
                ) from exc

            usage = getattr(response, "usage", None)
            spent_input += int(getattr(usage, "input_tokens", 0) or 0)
            spent_output += int(getattr(usage, "output_tokens", 0) or 0)

            payload = _tool_payload(response)
            if payload is not None:
                return ExtractionCall(
                    payload=payload,
                    input_tokens=spent_input,
                    output_tokens=spent_output,
                )

            # A response with no tool block is a refusal or a truncation. Retry
            # once or twice, then give up rather than guessing at its meaning.
            logger.warning(
                "extraction response carried no %s tool call (attempt %d)",
                EXTRACTION_TOOL_NAME,
                attempt + 1,
            )
            last_error = ExtractionUnavailableError("no tool_use block in response")
            if attempt + 1 < self._max_attempts:
                await asyncio.sleep(_backoff(attempt))

        raise ExtractionUnavailableError(
            str(last_error), input_tokens=spent_input, output_tokens=spent_output
        )


def build_extractor(
    api_key: str | None, *, model_id: str, max_attempts: int = DEFAULT_MAX_ATTEMPTS
) -> AnthropicExtractor:
    """Construct the live extractor, or refuse clearly if it cannot be built.

    The SDK is imported here rather than at module scope so that importing the
    extraction package — which the test suite and every non-extraction code path
    do — never depends on the provider client being installed or a key being
    present. Missing configuration surfaces as ``ExtractionUnavailableError`` at the
    point of construction, not as an ``ImportError`` at startup.
    """
    if not api_key:
        raise ExtractionUnavailableError(
            "MEDINTEL_ANTHROPIC_API_KEY is not set; extraction cannot run"
        )
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ExtractionUnavailableError(f"anthropic SDK not installed: {exc}") from exc
    return AnthropicExtractor(
        AsyncAnthropic(api_key=api_key), model_id=model_id, max_attempts=max_attempts
    )


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter.

    Jittered because bulk extraction issues its calls in a tight loop, so an
    un-jittered backoff would synchronise every retry into the same instant and
    reproduce the rate limit it is backing off from.
    """
    return BASE_BACKOFF_SECONDS * (2**attempt) * (0.5 + random.random())


def _tool_payload(response: Any) -> dict[str, Any] | None:
    """The input of the first matching ``tool_use`` block, if present."""
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and (
            getattr(block, "name", None) == EXTRACTION_TOOL_NAME
        ):
            payload = getattr(block, "input", None)
            if isinstance(payload, dict):
                return payload
    return None
