"""Shared numeric parsing (Spec 02 FR-PR-10, Spec 05 FR-EX-13).

The profiler and the executor must agree on what "numeric" means, otherwise a value
counted as numeric while profiling (e.g. "1,234") is silently lost while cleaning.
"""

from __future__ import annotations

import pandas as pd


def parse_numeric(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Parse a column as float64.

    Returns:
        (values, unparseable): `values` is float64 aligned with `s` (NaN for nulls and
        unparseable entries); `unparseable` is True where `s` had a non-null value that
        could not be parsed.
    """
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        values = s.astype("float64")
    else:
        text = s.astype("string").str.strip().str.replace(",", "", regex=False)
        values = pd.to_numeric(text, errors="coerce").astype("float64")
    unparseable = s.notna() & values.isna()
    return values, unparseable
