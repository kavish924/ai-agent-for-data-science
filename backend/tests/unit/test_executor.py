"""Unit tests for executor step semantics (Spec 05)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.executor import StepError, _snapshot, apply_step


def test_drop_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    out, notes = apply_step(df, {"op": "drop_duplicates", "params": {}})
    assert len(out) == 2
    assert notes["rows_removed"] == 1
    assert len(df) == 3  # input frame never mutated


def test_drop_column():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    out, _ = apply_step(df, {"op": "drop_column", "params": {"columns": ["b", "c"]}})
    assert list(out.columns) == ["a"]


def test_drop_column_missing_fails():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(StepError, match="not found"):
        apply_step(df, {"op": "drop_column", "params": {"columns": ["zzz"]}})


def test_impute_median():
    df = pd.DataFrame({"a": [1.0, None, 3.0]})
    out, notes = apply_step(df, {"op": "impute", "column": "a", "params": {"strategy": "median"}})
    assert out["a"].tolist() == [1.0, 2.0, 3.0]  # median of [1, 3]
    assert notes["filled"] == 1


def test_impute_constant():
    df = pd.DataFrame({"a": [1.0, None]})
    step = {"op": "impute", "column": "a", "params": {"strategy": "constant", "value": 0}}
    out, notes = apply_step(df, step)
    assert out["a"].tolist() == [1.0, 0.0]
    assert notes["filled"] == 1


def test_impute_mode_on_strings():
    df = pd.DataFrame({"c": ["x", None, "x", "y"]})
    out, notes = apply_step(df, {"op": "impute", "column": "c", "params": {"strategy": "mode"}})
    assert out["c"].tolist() == ["x", "x", "x", "y"]
    assert notes["filled"] == 1


def test_impute_all_null_column_fails():
    df = pd.DataFrame({"a": [None, None]})
    with pytest.raises(StepError, match="no non-null values"):
        apply_step(df, {"op": "impute", "column": "a", "params": {"strategy": "median"}})


def test_clip_outliers_iqr():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]})
    out, notes = apply_step(df, {"op": "clip_outliers", "column": "a", "params": {}})
    assert out["a"].max() == 16.0  # Q3 + 1.5*IQR
    assert notes["clipped"] == 1


def test_cast_type_int_dry_run_failure_leaves_frame_untouched():
    df = pd.DataFrame({"a": [1.5, None]})
    with pytest.raises(StepError, match="would fail"):
        apply_step(df, {"op": "cast_type", "column": "a", "params": {"to": "int"}})
    assert df["a"].tolist()[0] == 1.5  # frame untouched (FR-EX-04)


def test_cast_type_str_to_int_fails_dry_run():
    df = pd.DataFrame({"a": ["10", "abc"]})
    with pytest.raises(StepError, match="would fail"):
        apply_step(df, {"op": "cast_type", "column": "a", "params": {"to": "int"}})


def test_cast_type_float_to_int_succeeds():
    df = pd.DataFrame({"a": [1.0, 2.0]})
    out, _ = apply_step(df, {"op": "cast_type", "column": "a", "params": {"to": "int"}})
    assert out["a"].tolist() == [1, 2]


def test_parse_datetime_coerces_junk():
    df = pd.DataFrame({"d": ["2024-01-01", "not a date"]})
    out, notes = apply_step(df, {"op": "parse_datetime", "column": "d", "params": {}})
    assert notes["unparseable_to_null"] == 1
    assert out["d"].isna().tolist() == [False, True]


def test_standardize_text_ops():
    df = pd.DataFrame({"t": ["  Hello   World  "]})
    out, _ = apply_step(df, {
        "op": "standardize_text",
        "column": "t",
        "params": {"ops": ["trim", "lowercase", "collapse_spaces"]},
    })
    assert out["t"].tolist() == ["hello world"]


def test_standardize_text_rejects_numeric():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(StepError, match="not a text column"):
        apply_step(df, {"op": "standardize_text", "column": "a", "params": {"ops": ["trim"]}})


def test_unsupported_op_fails():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(StepError, match="unsupported op"):
        apply_step(df, {"op": "drop_everything", "params": {}})


def test_snapshot_counts():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100], "b": [None, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    snap = _snapshot(df)
    assert snap["rows"] == 11
    assert snap["cols"] == 2
    assert snap["null_cells"] == 1
    assert snap["outliers"] == 1


# --- M0 (Spec 05 FR-EX-12/13) -------------------------------------------------

def _cast(values, to):
    df = pd.DataFrame({"a": values})
    return apply_step(df, {"op": "cast_type", "column": "a", "params": {"to": to}})


def test_ex_ac8_bool_cast_maps_values_not_truthiness():
    out, _ = _cast(["True", "False", "no"], "bool")
    assert out["a"].tolist() == [True, False, False]


def test_ex_ac8_bool_cast_rejects_unknown_values():
    with pytest.raises(StepError, match="would fail"):
        _cast(["yes", "maybe"], "bool")


def test_ex_ac9_int_cast_allows_nulls():
    out, _ = _cast([1.0, None], "int")
    assert out["a"].iloc[0] == 1
    assert pd.isna(out["a"].iloc[1])
    assert str(out["a"].dtype) == "Int64"


def test_ex_ac9_int_cast_rejects_fractions():
    with pytest.raises(StepError, match="would fail"):
        _cast([1.5], "int")


def test_ex_fr12_int_cast_from_numeric_strings():
    out, _ = _cast(["10", "20"], "int")
    assert out["a"].tolist() == [10, 20]


def test_ex_ac10_clip_keeps_unparseable_values():
    values = ["1,000"] + [str(i) for i in range(1, 11)] + ["n/a"]
    df = pd.DataFrame({"a": values})
    out, notes = apply_step(df, {"op": "clip_outliers", "column": "a", "params": {}})
    assert out["a"].iloc[-1] == "n/a"
    assert notes["unparseable_kept"] == 1
    assert notes["clipped"] == 1
    assert float(out["a"].iloc[0]) < 1000


def test_ex_fr13_impute_median_ignores_unparseable_and_keeps_them():
    df = pd.DataFrame({"a": ["1", "3", None, "oops"]})
    out, notes = apply_step(df, {"op": "impute", "column": "a", "params": {"strategy": "median"}})
    assert out["a"].iloc[3] == "oops"
    assert float(out["a"].iloc[2]) == 2.0
    assert notes["filled"] == 1
    assert notes["unparseable_kept"] == 1
