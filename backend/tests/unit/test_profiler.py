"""Unit tests for the deterministic profiler (Spec 02)."""

from __future__ import annotations

import json

import pandas as pd

from app.services.profiler import profile_dataframe, infer_column_type


def test_boolean_from_zero_one():
    assert infer_column_type(pd.Series([0, 1, 0, 1]))[0] == "boolean"


def test_boolean_from_bool_dtype():
    assert infer_column_type(pd.Series([True, False, True]))[0] == "boolean"


def test_datetime_from_iso_strings():
    s = pd.Series(["2024-01-01", "2024-02-01", "2024-03-01"])
    assert infer_column_type(s)[0] == "datetime"


def test_numeric_dtype():
    assert infer_column_type(pd.Series([1.5, 2.5, 3.0]))[0] == "numeric"


def test_numeric_from_numeric_strings():
    assert infer_column_type(pd.Series(["10", "20", "30"]))[0] == "numeric"


def test_id_like_near_unique_strings():
    s = pd.Series([f"id{i}" for i in range(20)])
    assert infer_column_type(s)[0] == "id_like"


def test_categorical_low_cardinality():
    s = pd.Series(["red", "blue", "red", "green", "blue", "red"])
    assert infer_column_type(s)[0] == "categorical"


def test_text_free_sentences():
    sentences = [f"sentence number {i} about topic {i % 7}" for i in range(100)]
    s = pd.Series(sentences * 2)  # 200 rows, 100 uniques -> not id_like, not categorical
    assert infer_column_type(s)[0] == "text"


def test_all_empty_column_flagged():
    col_type, flags = infer_column_type(pd.Series([None, None, None]))
    assert col_type == "text"
    assert "all_empty" in flags


def test_single_value_flagged():
    col_type, flags = infer_column_type(pd.Series(["same", "same", "same"]))
    assert col_type == "categorical"
    assert "single_value" in flags


def test_iqr_outlier_count():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100])
    profile = _column(s)
    assert profile["outliers_iqr"] == 1
    assert profile["stats"]["max"] == 100.0


def _column(s: pd.Series) -> dict:
    df = pd.DataFrame({"col": s})
    return profile_dataframe("sid", df)["columns"][0]


def test_duplicate_rows_counted():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    profile = profile_dataframe("sid", df)
    assert profile["duplicate_rows"] == 1


def test_top_values_truncated_to_top_k():
    df = pd.DataFrame({"cat": [f"v{i % 30}" for i in range(300)]})
    profile = profile_dataframe("sid", df)
    assert len(profile["columns"][0]["top_values"]) == 10


def test_profile_is_json_serializable():
    df = pd.DataFrame(
        {
            "num": [1.0, 2.0, 3.0],
            "cat": ["a", "b", "a"],
            "empty": [None, None, None],
        }
    )
    profile = profile_dataframe("sid", df)
    text = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
    assert "session_id" in text


def test_top_k_capping_not_full_column_dump():
    df = pd.DataFrame({"secret": [f"v{i}" for i in range(100)]})
    profile = profile_dataframe("sid", df)
    text = json.dumps(profile)
    # Top-K cap: only 10 of the 100 distinct values appear — no full raw dump
    # (FR-PR-04 top-K + FR-PR-07 compact profile; design D2).
    assert "v99" not in text
    assert text.count('"value"') == 10
