"""Spec 10 NFR-10: eval metrics (golden matching, scripted review, summary)."""

from __future__ import annotations

import pytest

from eval import metrics

GOLDEN = {
    "target": "Survived",
    "expected": [{"op": "impute", "column": "Age"}, {"op": "drop_column", "column": "Cabin"}],
    "acceptable": [{"op": "drop_duplicates", "column": "*"}, {"op": "drop_column", "column": "Name"}],
    "forbidden": [{"op": "drop_column", "column": "Sex"}],
}


def step(op, column=None, **params):
    return {"step_id": f"s-{op}-{column}", "op": op, "column": column, "params": params}


def test_nfr_ac8_matching_by_column_drop_list_and_wildcard():
    assert metrics.step_matches({"op": "impute", "column": "Age"}, step("impute", "Age"))
    assert not metrics.step_matches({"op": "impute", "column": "Age"}, step("impute", "Fare"))
    assert not metrics.step_matches({"op": "impute", "column": "Age"}, step("clip_outliers", "Age"))
    assert metrics.step_matches({"op": "drop_column", "column": "Cabin"},
                                step("drop_column", None, columns=["Name", "Cabin"]))
    assert metrics.step_matches({"op": "drop_duplicates", "column": "*"}, step("drop_duplicates"))


def test_nfr_ac8_sensible_plan_and_scripted_review():
    plan = [step("impute", "Age"), step("drop_column", None, columns=["Cabin"]),
            step("drop_duplicates"), step("impute", "Fare")]
    score = metrics.score_plan(plan, GOLDEN)
    assert score["expected_recall"] == 1.0
    assert score["missing"] == [] and score["forbidden_hits"] == []
    assert score["sensible"] is True
    decisions = {r["step_id"]: r["decision"] for r in score["review"]}
    assert decisions["s-impute-Fare"] == "skip"  # not in expected/acceptable
    assert list(decisions.values()).count("approve") == 3
    assert score["approved"] == 3 and score["proposed"] == 4
    assert score["approval_rate"] == pytest.approx(0.75)


def test_nfr_ac8_missing_or_forbidden_steps_are_not_sensible():
    missing = metrics.score_plan([step("impute", "Age")], GOLDEN)
    assert missing["expected_recall"] == 0.5 and missing["sensible"] is False
    assert missing["missing"] == [{"op": "drop_column", "column": "Cabin"}]

    # A drop list that hits a forbidden column is skipped even though Cabin is expected.
    bad = metrics.score_plan([step("impute", "Age"), step("drop_column", None, columns=["Cabin", "Sex"])],
                             GOLDEN)
    assert bad["forbidden_hits"] and bad["sensible"] is False
    assert [r["decision"] for r in bad["review"]] == ["approve", "skip"]


def test_nfr_ac8_empty_expectations_and_empty_plan():
    score = metrics.score_plan([], {"expected": [], "acceptable": [], "forbidden": []})
    assert score["expected_recall"] == 1.0 and score["sensible"] is True
    assert score["approval_rate"] is None  # nothing proposed


def test_nfr_ac9_summary_metrics():
    datasets = [
        {"name": "a", "planner_calls": [{"attempt": 1, "valid": 1}],
         "score": {"sensible": True, "approved": 3, "proposed": 4}, "timings_ms": {"total": 1000}},
        {"name": "b", "planner_calls": [{"attempt": 1, "valid": 0, "error": "transport:503"},
                                           {"attempt": 2, "valid": 1, "error": None}],
         "score": {"sensible": False, "approved": 1, "proposed": 1}, "timings_ms": {"total": 3000}},
    ]
    summary = metrics.summarize(datasets)
    assert summary["schema_validity"] == pytest.approx(0.5)
    assert summary["mean_planner_attempts"] == pytest.approx(1.5)
    assert summary["plan_quality"] == pytest.approx(0.5)
    assert summary["approval_rate"] == pytest.approx(0.8)
    assert summary["mean_time_to_report_ms"] == 2000
    assert summary["datasets"] == 2
    assert summary["transport_errors"] == 1
