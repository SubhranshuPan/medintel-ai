"""Generic dataset validation (#33, ADR-014)."""

import io

import pandas as pd

from app.services.validation import validate

_VALID_CSV = b"patient_id,age,sex\np1,40,M\np2,55,F\n"
_EMPTY_COLUMN_CSV = b"patient_id,age,notes\np1,40,\np2,55,\n"
_DUPLICATE_ROW_CSV = b"patient_id,age\np1,40\np1,40\n"


def _df(content: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(content))


def test_valid_dataset_passes() -> None:
    passed, report = validate(_df(_VALID_CSV))

    assert passed
    assert report == {"failure_count": 0, "failures": []}


def test_empty_dataframe_fails() -> None:
    passed, report = validate(pd.DataFrame())

    assert not passed
    assert report["failure_count"] > 0


def test_all_null_column_fails() -> None:
    passed, report = validate(_df(_EMPTY_COLUMN_CSV))

    assert not passed
    assert report["failure_count"] > 0


def test_duplicate_rows_fail() -> None:
    passed, report = validate(_df(_DUPLICATE_ROW_CSV))

    assert not passed
    assert report["failure_count"] > 0


def test_lazy_collects_multiple_violations() -> None:
    # Both an all-null column AND a duplicate row in one frame -> both surface.
    df = pd.DataFrame({"a": [1, 1], "b": [None, None]})

    passed, report = validate(df)

    assert not passed
    assert report["failure_count"] >= 2
