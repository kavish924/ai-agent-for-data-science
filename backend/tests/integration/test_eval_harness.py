"""Spec 10 NFR-09/11/12: the eval harness, offline (RuleBasedLLM), in-process."""

from __future__ import annotations

import json

import pytest

from app.llm.fake import RuleBasedLLM
from app.routers.plans import get_llm
from eval import harness


@pytest.fixture()
def offline(client):
    client.app.dependency_overrides[get_llm] = RuleBasedLLM
    yield client
    client.app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def golden():
    return harness.load_golden()


def test_nfr_ac10_offline_eval_runs_every_stage_and_writes_results(offline, golden, tmp_path):
    result = harness.run_dataset(offline, "titanic.csv", golden["titanic.csv"])
    assert result["status"] == "ok", result
    for stage in ("upload_profile", "plan", "execute", "model", "report", "total"):
        assert result["timings_ms"][stage] >= 0
    assert result["planner_calls"] and result["planner_calls"][0]["attempt"] == 1
    assert result["score"]["sensible"] is True  # the fake plans Age, Embarked, Cabin
    assert result["best_model"] != "dummy" and result["narration_source"] == "template"

    report = {"provider": "offline", "datasets": [result], "summary": harness.metrics.summarize([result])}
    json_path, md_path = harness.write_results(report, tmp_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["datasets"] == 1
    text = md_path.read_text(encoding="utf-8")
    assert "Schema validity" in text and "titanic.csv" in text


def test_nfr_ac1_replayed_plan_is_byte_identical(offline, golden):
    result = harness.run_dataset(offline, "titanic.csv", golden["titanic.csv"])
    repro = result["reproducibility"]
    assert repro["cleaned_csv"] is True
    assert repro["charts"] is True and repro["chart_count"] > 0
    assert repro["model_scores"] is True
    assert repro["report_rerender"] is True
    assert repro["report_cross_session"] is True  # both narrations are the template


def test_nfr_ac6_performance_baseline_is_recorded(offline):
    perf = harness.perf_baseline(offline, rows=3000)
    assert perf["rows"] == 3000 and perf["size_mb"] > 0
    assert perf["upload_profile_ms"] >= 0 and perf["execute_ms"] >= 0
    assert perf["budget_s"] == 60
    assert perf["within_budget"] is True
