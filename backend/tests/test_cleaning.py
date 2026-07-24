"""Cleaning pipeline unit tests (ADR-009, #34)."""

import io

import pandas as pd

from app.services.cleaning import clean

_DIRTY_CSV = (
    "patient_id,age\n"
    " p1 , 40\n"
    "p1,40\n"  # exact duplicate of the stripped row above
    ",\n"  # fully-empty row
    "p2,55\n"
)


def _df(content: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(content))


def test_clean_is_deterministic() -> None:
    df = _df(_DIRTY_CSV)
    cleaned_a, _ = clean(df.copy())
    cleaned_b, _ = clean(df.copy())
    assert cleaned_a.to_csv(index=False) == cleaned_b.to_csv(index=False)


def test_drops_fully_empty_rows() -> None:
    cleaned, report = clean(_df(_DIRTY_CSV))
    assert not cleaned["patient_id"].isna().any() or len(cleaned) < 4
    assert "drop_empty_rows" in report["steps"]


def test_strips_whitespace_and_reports_cells_changed() -> None:
    cleaned, report = clean(_df(_DIRTY_CSV))
    assert "strip_whitespace" in report["steps"]
    assert report["cells_changed"]["patient_id"] >= 1
    assert (cleaned["patient_id"] == cleaned["patient_id"].str.strip()).all()


def test_drops_duplicate_rows() -> None:
    cleaned, report = clean(_df(_DIRTY_CSV))
    assert "drop_duplicate_rows" in report["steps"]
    assert cleaned["patient_id"].tolist().count("p1") == 1


def test_report_shape_and_row_counts() -> None:
    cleaned, report = clean(_df(_DIRTY_CSV))
    assert report["rows_before"] == 4
    assert report["rows_after"] == len(cleaned) == 2


def test_already_clean_input_has_no_steps() -> None:
    clean_csv = "patient_id,age\np1,40\np2,55\n"
    cleaned, report = clean(_df(clean_csv))
    assert report["steps"] == []
    assert report["rows_before"] == report["rows_after"] == 2
