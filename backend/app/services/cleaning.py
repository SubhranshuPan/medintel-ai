"""Deterministic dataset cleaning (ADR-009, #34).

Uploaded CSVs are arbitrary clinical extracts (validation.py, #33, is
generic for the same reason) — so cleaning fixes the same generic issues
validation flags: empty rows, stray whitespace, exact duplicate rows. No
column-specific normalisation (e.g. a fixed ``sex``/``age`` schema) and no
imputation — inventing patient values is a clinical-safety line this step
does not cross. Same input bytes always produce the same output bytes, so a
cleaned version is reproducible from its parent plus this report alone.
"""

import pandas as pd


def _cells_changed(before: pd.Series, after: pd.Series) -> int:
    changed = ~((before == after) | (before.isna() & after.isna()))
    return int(changed.sum())


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return the cleaned frame and a report of what was changed."""
    rows_before = len(df)
    steps: list[str] = []
    cells_changed: dict[str, int] = {}

    df = df.dropna(how="all").reset_index(drop=True)
    if len(df) != rows_before:
        steps.append("drop_empty_rows")

    for col in df.select_dtypes(include=["object", "str"]).columns:
        stripped = df[col].str.strip()
        changed = _cells_changed(df[col], stripped)
        if changed:
            cells_changed[col] = changed
            df[col] = stripped
    if cells_changed:
        steps.append("strip_whitespace")

    dup_mask = df.duplicated()
    if dup_mask.any():
        steps.append("drop_duplicate_rows")
        df = df[~dup_mask].reset_index(drop=True)

    return df, {
        "steps": steps,
        "rows_before": rows_before,
        "rows_after": len(df),
        "cells_changed": cells_changed,
    }
