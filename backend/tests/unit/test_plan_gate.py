"""Unit tests for plan schemas (Pydantic Gate) + semantic gate (Spec 03 §4, Spec 05)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.plan import PlanIn
from app.services.gate import validate_plan

PROFILE = {
    "columns": [
        {"name": "age", "type": "numeric"},
        {"name": "city", "type": "categorical"},
        {"name": "joined", "type": "text"},
        {"name": "uid", "type": "id_like"},
    ]
}


def _step(**overrides) -> dict:
    step = {"op": "impute", "column": "age", "params": {"strategy": "median"}}
    step.update(overrides)
    return step


def _issues(steps: list[dict]) -> list[dict]:
    return validate_plan(PlanIn.model_validate({"steps": steps}), PROFILE)


# --- schema-level (Pydantic) -------------------------------------------------

def test_unknown_op_rejected():
    with pytest.raises(ValidationError):
        PlanIn.model_validate({"steps": [{"op": "drop_outliers", "column": "age"}]})


def test_impute_constant_requires_value():
    with pytest.raises(ValidationError):
        PlanIn.model_validate({"steps": [_step(params={"strategy": "constant"})]})


def test_impute_value_only_allowed_for_constant():
    with pytest.raises(ValidationError):
        PlanIn.model_validate({"steps": [_step(params={"strategy": "median", "value": 5})]})


def test_drop_duplicates_is_frame_level():
    with pytest.raises(ValidationError):
        PlanIn.model_validate({"steps": [{"op": "drop_duplicates", "column": "age"}]})


def test_unknown_params_rejected():
    with pytest.raises(ValidationError):
        PlanIn.model_validate({"steps": [_step(params={"strategy": "mode", "evil": 1})]})


def test_column_required_for_single_column_ops():
    with pytest.raises(ValidationError):
        PlanIn.model_validate({"steps": [{"op": "clip_outliers", "params": {}}]})


def test_schema_alias_accepted():
    plan = PlanIn.model_validate({"schema": "v1", "steps": []})
    assert plan.schema_version == "v1"


def test_default_status_is_approved():
    plan = PlanIn.model_validate({"steps": [_step()]})
    assert plan.steps[0].status == "approved"


def test_rationale_optional_at_schema_level():
    plan = PlanIn.model_validate({"steps": [_step()]})
    assert plan.steps[0].rationale is None


# --- semantic gate (profile-aware) --------------------------------------------

def test_valid_plan_has_no_issues():
    assert _issues([_step(), {"op": "drop_duplicates", "params": {}}]) == []


def test_unknown_column_flagged():
    issues = _issues([_step(column="zzz")])
    assert len(issues) == 1
    assert "zzz" in issues[0]["issue"]


def test_drop_column_unknown_flagged():
    issues = _issues([{"op": "drop_column", "params": {"columns": ["city", "nope"]}}])
    assert len(issues) == 1


def test_impute_mean_requires_numeric():
    issues = _issues([_step(column="city", params={"strategy": "mean"})])
    assert len(issues) == 1


def test_clip_outliers_requires_numeric():
    issues = _issues([{"op": "clip_outliers", "column": "joined", "params": {}}])
    assert len(issues) == 1


def test_standardize_text_requires_text_like():
    issues = _issues([
        {"op": "standardize_text", "column": "age", "params": {"ops": ["trim"]}},
    ])
    assert len(issues) == 1


def test_parse_datetime_allows_text():
    assert _issues([
        {"op": "parse_datetime", "column": "joined", "params": {}},
    ]) == []


def test_disabled_steps_not_checked():
    steps = [_step(column="zzz", status="disabled")]
    assert _issues(steps) == []


def test_issue_includes_step_index():
    issues = _issues([_step(), _step(column="nope")])
    assert issues[0]["step"] == 1
