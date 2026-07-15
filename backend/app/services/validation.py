"""Dataset validation (ADR-014, pandera).

Uploaded CSVs are arbitrary clinical extracts, not one fixed pathway — so this
is a generic, frame-level sanity check (non-empty, no fully-null columns, no
duplicate rows, column names present and unique), not a named schema tied to
specific clinical columns. Named ``DataFrameModel`` schemas for particular
pathways (e.g. an ICD-coded readmission cohort) are a later, additive step
(ADR-014), not part of this generic check.
"""

import pandas as pd
import pandera.pandas as pa
from pandera import Check, DataFrameSchema

GENERIC_SCHEMA = DataFrameSchema(
    columns={},
    checks=[
        Check(lambda df: len(df) > 0, error="dataset is empty"),
        Check(lambda df: not df.columns.duplicated().any(), error="duplicate column names"),
        Check(lambda df: not df.isna().all(axis=0).any(), error="a column is entirely null"),
        Check(lambda df: not df.duplicated().any(), error="duplicate rows present"),
    ],
    strict=False,
)


def validate(df: pd.DataFrame) -> tuple[bool, dict]:
    """Validate a dataset frame. Returns ``(passed, report)``.

    Never raises on invalid data — a failed validation is a recorded outcome
    on the version row, not an exception; the raw upload is kept regardless
    (ADR-009: nothing is discarded, everything is traceable). ``lazy=True``
    collects every violation in one pass so a clinician sees the full list.
    """
    try:
        GENERIC_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        failures = exc.failure_cases.head(100).to_dict(orient="records")
        return False, {
            "failure_count": int(len(exc.failure_cases)),
            "failures": failures,
            "truncated": bool(len(exc.failure_cases) > 100),
        }
    return True, {"failure_count": 0, "failures": []}
