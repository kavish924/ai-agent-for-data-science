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


def test_nfr_ac12_precision_recall_f1_forbidden_rate():
    steps = [step("impute", "Age"), step("drop_column", "Sex"), step("clip_outliers", "Fare")]
    s = metrics.score_plan(steps, GOLDEN)
    assert s["precision"] == pytest.approx(1 / 3, abs=1e-4)        # only impute(Age) approved
    assert s["recall"] == pytest.approx(0.5)               # Cabin missing
    assert s["f1"] == pytest.approx(2 * (1 / 3) * 0.5 / (1 / 3 + 0.5), abs=1e-4)
    assert s["forbidden_rate"] == pytest.approx(1 / 3, abs=1e-4)


def test_nfr_ac12_empty_plan_and_zero_cases():
    empty = metrics.score_plan([], GOLDEN)
    assert (empty["precision"], empty["recall"], empty["f1"], empty["forbidden_rate"]) == (1.0, 0.0, 0.0, 0.0)
    bad = metrics.score_plan([step("drop_column", "Sex")], GOLDEN)
    assert (bad["precision"], bad["recall"], bad["f1"], bad["forbidden_rate"]) == (0.0, 0.0, 0.0, 1.0)
    perfect = metrics.score_plan([], {"expected": [], "acceptable": [], "forbidden": []})
    assert perfect["f1"] == 1.0


def test_nfr_ac12_summary_mean_f1_and_pooled_forbidden_rate():
    datasets = [
        {"planner_calls": [{"valid": 1}], "timings_ms": {"total": 1},
         "score": {"sensible": True, "approved": 1, "proposed": 2, "f1": 0.5, "forbidden_hits": [{}]}},
        {"planner_calls": [{"valid": 1}], "timings_ms": {"total": 1},
         "score": {"sensible": True, "approved": 2, "proposed": 2, "f1": 1.0, "forbidden_hits": []}},
    ]
    summary = metrics.summarize(datasets)
    assert summary["mean_f1"] == pytest.approx(0.75)
    assert summary["forbidden_rate"] == pytest.approx(0.25)


def test_nfr_ac13_bootstrap_ci_is_seeded_and_contains_mean():
    values = [0.2, 0.4, 0.5, 0.9, 1.0, 0.7]
    a = metrics.bootstrap_ci(values, seed=1)
    b = metrics.bootstrap_ci(values, seed=1)
    assert a == b
    m, lo, hi = a
    assert m == pytest.approx(sum(values) / len(values))
    assert lo <= m <= hi
    assert metrics.bootstrap_ci([0.5, 0.5]) == (0.5, 0.5, 0.5)
    with pytest.raises(ValueError):
        metrics.bootstrap_ci([])


def test_nfr_ac13_cohen_kappa():
    assert metrics.cohen_kappa([True, False, True], [True, False, True]) == 1.0
    assert metrics.cohen_kappa([True, True], [True, True]) == 1.0
    assert metrics.cohen_kappa([True, True, False, False], [True, False, True, False]) == pytest.approx(0.0)
    # po = 3/5 agree; pe from the marginals (3/5 True each)
    a = [True, True, True, False, False]
    b = [True, True, False, False, True]
    po, pe = 3 / 5, (3 / 5) * (3 / 5) + (2 / 5) * (2 / 5)
    assert metrics.cohen_kappa(a, b) == pytest.approx((po - pe) / (1 - pe))
    with pytest.raises(ValueError):
        metrics.cohen_kappa([True], [True, False])
