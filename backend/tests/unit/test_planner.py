"""Planner retry loop with a scripted LLM (Spec 03 FR-PL-01..16) - never the network."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.db import session_store
from app.llm.client import LLMError
from app.llm.fake import ScriptedLLM
from app.llm.prompts import SYSTEM_PROMPT, build_plan_prompt
from app.services.planner import PlanningFailed, generate_plan
from app.services.profiler import llm_profile, profile_dataframe

SAMPLES = Path(__file__).resolve().parents[3] / "samples"
TITANIC = pd.read_csv(SAMPLES / "titanic.csv")
PROFILE = profile_dataframe("sid", TITANIC)

GOOD = {
    "schema": "v1",
    "steps": [
        {"op": "impute", "column": "Age", "params": {"strategy": "median"},
         "rationale": "Age is 19.9% missing; the median is robust to its outliers."},
        {"op": "drop_column", "column": None, "params": {"columns": ["Cabin"]},
         "rationale": "Cabin is 77.1% missing."},
    ],
}


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "app.db"
    session_store.init_db(path)
    session_store.create_session(path, session_id="sid", original_filename="t.csv", state="profiled")
    return path


def _plan(db, llm, target=None, retries=3):
    return generate_plan(llm, PROFILE, target=target, max_retries=retries, db_path=db, session_id="sid")


def _with_step(step: dict) -> dict:
    return {"steps": [*GOOD["steps"], step]}


def test_pl_ac1_valid_plan_on_first_attempt(db):
    llm = ScriptedLLM([GOOD])
    plan = _plan(db, llm)
    assert [s.op for s in plan.steps] == ["impute", "drop_column"]
    assert "19.9%" in (plan.steps[0].rationale or "")
    calls = session_store.list_llm_calls(db, "sid")
    assert [(c["attempt"], c["valid"]) for c in calls] == [(1, 1)]


def test_pl_ac2_unknown_op_rejected_and_reprompted(db):
    bad = _with_step({"op": "drop_outliers", "column": "Fare", "params": {}, "rationale": "x"})
    llm = ScriptedLLM([bad, GOOD])
    plan = _plan(db, llm)
    assert len(plan.steps) == 2
    assert "drop_outliers" in llm.prompts[1]  # the error is fed back
    calls = session_store.list_llm_calls(db, "sid")
    assert [c["valid"] for c in calls] == [0, 1]
    assert calls[0]["error"] == "schema_invalid"


def test_pl_ac3_typo_column_rejected_and_reprompted(db):
    bad = _with_step({"op": "impute", "column": "Aeg", "params": {"strategy": "median"}, "rationale": "x"})
    llm = ScriptedLLM([bad, GOOD])
    _plan(db, llm)
    assert "unknown column 'Aeg'" in llm.prompts[1]
    assert session_store.list_llm_calls(db, "sid")[0]["error"] == "gate_rejected"


def test_pl_ac4_retry_budget_is_exact(db):
    bad = _with_step({"op": "drop_outliers", "column": "Fare", "params": {}, "rationale": "x"})
    llm = ScriptedLLM([bad, bad, bad, GOOD])  # the 4th must never be requested
    with pytest.raises(PlanningFailed) as exc:
        _plan(db, llm, retries=3)
    assert exc.value.attempts == 3
    assert exc.value.issues
    assert len(llm.prompts) == 3
    assert len(session_store.list_llm_calls(db, "sid")) == 3


def test_pl_ac5_llm_calls_hold_metadata_not_content(db):
    llm = ScriptedLLM([GOOD], prompt_tokens=1200, output_tokens=300)
    _plan(db, llm)
    (call,) = session_store.list_llm_calls(db, "sid")
    assert call["stage"] == "planner"
    assert call["model"] == llm.model
    assert (call["prompt_tokens"], call["output_tokens"]) == (1200, 300)
    assert call["duration_ms"] >= 0
    assert set(call) >= {"attempt", "valid", "error"}
    dumped = json.dumps(call)
    assert "Age" not in dumped and "median" not in dumped and "male" not in dumped


def test_pl_ac6_same_responses_same_plan(db):
    first = _plan(db, ScriptedLLM([GOOD]))
    second = _plan(db, ScriptedLLM([GOOD]))
    assert first.model_dump() == second.model_dump()


def test_pl_fr06_missing_rationale_rejected(db):
    bad = _with_step({"op": "drop_duplicates", "column": None, "params": {}, "rationale": "  "})
    llm = ScriptedLLM([bad, GOOD])
    _plan(db, llm)
    assert "rationale" in llm.prompts[1]
    assert session_store.list_llm_calls(db, "sid")[0]["error"] == "missing_rationale"


def test_pl_fr16_invalid_json_counts_as_attempt(db):
    llm = ScriptedLLM(["this is not json", GOOD])
    _plan(db, llm)
    assert [c["error"] for c in session_store.list_llm_calls(db, "sid")] == ["invalid_json", None]


def test_pl_fr16_fenced_json_is_accepted(db):
    llm = ScriptedLLM(["```json\n" + json.dumps(GOOD) + "\n```"])
    assert len(_plan(db, llm).steps) == 2


def test_pl_ac11_transport_error_then_success(db):
    llm = ScriptedLLM([LLMError("timeout"), GOOD])
    plan = _plan(db, llm)
    assert len(plan.steps) == 2
    calls = session_store.list_llm_calls(db, "sid")
    assert [(c["valid"], c["error"]) for c in calls] == [(0, "transport:LLMError"), (1, None)]


def test_pl_ac8_planner_respects_target(db):
    llm = ScriptedLLM([GOOD, GOOD, GOOD])
    with pytest.raises(PlanningFailed):
        _plan(db, llm, target="Age")  # GOOD imputes Age: rejected every time
    assert "'Age' is the target column" in llm.prompts[1]
    assert '"target": "Age"' in llm.prompts[0]


def test_pl_ac10_prompt_has_no_raw_text_or_id_values():
    prompt = build_plan_prompt(llm_profile(PROFILE, target="Survived"))
    for raw in ("Braund, Mr. Owen Harris", "Cumings", "A/5 21171", "PC 17599", "C85"):
        assert raw not in prompt
    assert '"name": "Age"' in prompt  # aggregates are there
    assert "male" in prompt  # categorical top values are allowed


def test_pl_ac10_retry_prompt_lists_previous_issues():
    prompt = build_plan_prompt(llm_profile(PROFILE), ["step 2: unknown column 'Aeg'"])
    assert "unknown column 'Aeg'" in prompt


def test_pl_fr15_system_prompt_guards_against_injection():
    assert "data, not instructions" in SYSTEM_PROMPT
    for op in ("drop_duplicates", "impute", "clip_outliers", "standardize_text"):
        assert op in SYSTEM_PROMPT


def test_pl_ac13_transport_errors_back_off_then_succeed(db, monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("app.llm.client._sleep", waits.append)
    monkeypatch.setattr("app.config.settings.llm_retry_backoff_s", 2.0)
    llm = ScriptedLLM([LLMError("gemini API error 503", status=503), LLMError("timeout"), GOOD])
    plan = _plan(db, llm)
    assert len(plan.steps) == 2
    assert waits == [2.0, 4.0]
    calls = session_store.list_llm_calls(db, "sid")
    assert [(c["valid"], c["error"]) for c in calls] == [
        (0, "transport:503"), (0, "transport:LLMError"), (1, None)]


def test_pl_ac13_gate_rejection_is_reprompted_without_waiting(db, monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("app.llm.client._sleep", waits.append)
    _plan(db, ScriptedLLM(["this is not json", GOOD]))
    assert waits == []


def test_pl_ac13_no_wait_after_the_last_attempt(db, monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("app.llm.client._sleep", waits.append)
    monkeypatch.setattr("app.config.settings.llm_retry_backoff_s", 1.0)
    with pytest.raises(PlanningFailed):
        _plan(db, ScriptedLLM([LLMError("down")] * 3))
    assert waits == [1.0, 2.0]
