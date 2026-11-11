"""Shared numeric parser (Spec 02 FR-PR-10, Spec 05 FR-EX-13)."""

from __future__ import annotations

import pandas as pd

from app.services.numeric import parse_numeric


def test_pr_fr10_strips_thousands_separators_and_spaces():
    values, unparseable = parse_numeric(pd.Series(["1,234", " 5 ", None, "n/a"]))
    assert values.tolist()[:2] == [1234.0, 5.0]
    assert pd.isna(values.iloc[2]) and pd.isna(values.iloc[3])
    assert unparseable.tolist() == [False, False, False, True]


def test_pr_fr10_numeric_dtype_passthrough():
    values, unparseable = parse_numeric(pd.Series([1, 2, None]))
    assert values.tolist()[:2] == [1.0, 2.0]
    assert not unparseable.any()
