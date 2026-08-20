"""Knowledge extraction entry point (#63).

    python -m scripts.extract_knowledge --estimate
    python -m scripts.extract_knowledge --max-units 50 --budget 0.25
    python -m scripts.extract_knowledge --supersede-only

Run **after** ``scripts.ingest_corpus``: extraction reads persisted
``knowledge_nodes`` and writes typed edges between them.

This is the only command in the repo that spends money, so it is deliberately
awkward to run carelessly. ``--estimate`` prices the run without calling the
provider and is the intended first step; both the unit cap and the spend ceiling
are enforced in code and neither can be disabled from the command line.

``MEDINTEL_ANTHROPIC_API_KEY`` must be set. Extraction refuses to start without
it rather than picking up an ambient credential.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow `python scripts/extract_knowledge.py` from the backend root, not only
# `python -m scripts.extract_knowledge`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.db import AsyncSessionLocal  # noqa: E402
from app.services.extraction import (  # noqa: E402
    SYSTEM_PROMPT,
    apply_supersession,
    build_extractor,
    build_prompt,
    estimate_cost_usd,
    extract_knowledge,
    extractor_stamp,
    select_candidates,
    select_units,
)
from app.services.extraction.provider import MAX_OUTPUT_TOKENS  # noqa: E402

logger = logging.getLogger("extract_knowledge")

#: Characters per token for clinical English. Used only for the pre-flight
#: estimate; actual spend is metered from the provider's own usage figures, so a
#: drift here changes the forecast and never the ceiling.
CHARS_PER_TOKEN = 3.6

#: Output tokens assumed per unit when estimating. Well under
#: ``MAX_OUTPUT_TOKENS`` because the schema's own caps bound a well-formed
#: response long before the token limit does.
ESTIMATED_OUTPUT_TOKENS = 250


async def _estimate(max_units: int, max_candidates: int) -> int:
    """Price the run from real prompts, without calling the provider.

    Built by rendering the prompts that would actually be sent, rather than by
    assuming an average passage length: the candidate list dominates the input
    cost and its size depends on the corpus, so an assumed number would be a
    guess dressed as a measurement.
    """
    settings = get_settings()
    stamp = extractor_stamp(settings.extraction_model)

    async with AsyncSessionLocal() as session:
        units = await select_units(session, stamp=stamp, limit=max_units)
        if not units:
            print("nothing to extract — every unit already carries this stamp")
            return 0

        total_input = 0
        # Sampled rather than rendered for every unit: each sample costs a
        # candidate query, and the spread across a corpus of near-identical
        # structural units is small.
        sample = units[:10]
        for node in sample:
            candidates = await select_candidates(session, node, limit=max_candidates)
            prompt = build_prompt(node, candidates)
            total_input += len(SYSTEM_PROMPT) + len(prompt)

        per_unit_input = round(total_input / len(sample) / CHARS_PER_TOKEN)

    per_unit = estimate_cost_usd(
        settings.extraction_model, per_unit_input, ESTIMATED_OUTPUT_TOKENS
    )
    print(f"model            : {settings.extraction_model}")
    print(f"units pending    : {len(units)}")
    print(
        f"per unit         : ~{per_unit_input} in / {ESTIMATED_OUTPUT_TOKENS} out "
        f"= ${per_unit:.5f}"
    )
    print(f"estimated total  : ${per_unit * len(units):.2f}")
    print(f"budget ceiling   : ${settings.extraction_budget_usd:.2f}")
    if per_unit * len(units) > settings.extraction_budget_usd:
        print(
            "NOTE: the estimate exceeds the ceiling, so the run will stop part "
            "way through and report budget_exhausted. Raise "
            "MEDINTEL_EXTRACTION_BUDGET_USD or lower --max-units deliberately."
        )
    return 0


async def _run(
    max_units: int | None,
    budget: float | None,
    max_candidates: int | None,
    estimate: bool,
    supersede_only: bool,
) -> int:
    settings = get_settings()
    units = max_units or settings.extraction_max_units
    candidates = max_candidates or settings.extraction_max_candidates

    if estimate:
        return await _estimate(units, candidates)

    if supersede_only:
        async with AsyncSessionLocal() as session:
            report = await apply_supersession(session)
        print(
            f"documents_superseded={report.documents_superseded} "
            f"nodes_updated={report.nodes_updated} "
            f"conflicts_skipped={report.conflicts_skipped}"
        )
        return 0

    extractor = build_extractor(
        settings.anthropic_api_key, model_id=settings.extraction_model
    )
    async with AsyncSessionLocal() as session:
        report = await extract_knowledge(
            session,
            extractor,
            max_units=units,
            budget_usd=budget if budget is not None else settings.extraction_budget_usd,
            max_candidates=candidates,
        )
        # Supersession runs after extraction, not before: extraction skips
        # non-active nodes, so retiring first would silently shrink the corpus
        # this run was priced against.
        supersession = await apply_supersession(session)

    print(
        f"units_extracted={report.units_extracted} "
        f"units_skipped={report.units_skipped} "
        f"terms={report.terms_created} edges={report.edges_created}"
    )
    print(
        f"tokens in={report.input_tokens} out={report.output_tokens} "
        f"spend=${report.estimated_cost_usd:.4f} "
        f"(max output/call {MAX_OUTPUT_TOKENS})"
    )
    if report.rejections:
        print(f"rejected {len(report.rejections)}:")
        for reason, count in sorted(report.rejection_reasons.items()):
            print(f"  {count:>4}  {reason}")
    for error in report.errors:
        print(f"  ERROR {error}")
    if report.budget_exhausted:
        print(
            "WARNING: budget exhausted — the graph is PARTIAL. Re-run to "
            "continue; already-extracted units are skipped and not re-billed."
        )
    print(
        f"supersession: documents={supersession.documents_superseded} "
        f"nodes={supersession.nodes_updated} "
        f"conflicts={supersession.conflicts_skipped}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="Price the run from real prompts and exit without calling the provider",
    )
    parser.add_argument(
        "--max-units",
        type=int,
        default=None,
        help="Structural units to extract (default: MEDINTEL_EXTRACTION_MAX_UNITS)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Spend ceiling in USD (default: MEDINTEL_EXTRACTION_BUDGET_USD)",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Candidate passages offered per call — the dominant input cost",
    )
    parser.add_argument(
        "--supersede-only",
        action="store_true",
        help="Apply publisher-stated supersession only; no provider calls",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(
        _run(
            args.max_units,
            args.budget,
            args.max_candidates,
            args.estimate,
            args.supersede_only,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
