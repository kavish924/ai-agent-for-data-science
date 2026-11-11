"""Review reconciliation (Spec 04 FR-RV-09/10)."""

from __future__ import annotations

import pytest

from app.schemas.plan import PlanIn
from app.services.plan_review import ReviewError, assign_ids, reconcile, unreviewed

GENERATED = assign_ids(
    PlanIn.model_validate(
        {
            "steps": [
                {"op": "drop_duplicates", "rationale": "dupes", "status": "approved"},
                {"op": "impute", "column": "age", "params": {"strategy": "median"}, "rationale": "nulls"},
                {"op": "clip_outliers", "column": "fare", "params": {}, "rationale": "outliers"},
            ]
        }
    )
)


def _submit(steps: list[dict]) -> PlanIn:
    return reconcile(GENERATED, PlanIn.model_validate({"steps": steps}))


def _gen(i: int, **overrides) -> dict:
    step = GENERATED.steps[i].model_dump()
    step.update(overrides)
    return step


def test_rv_fr09_assign_ids_forces_proposed_and_sequential_ids():
    assert [s.step_id for s in GENERATED.steps] == ["s1", "s2", "s3"]
    assert {s.status for s in GENERATED.steps} == {"proposed"}


def test_rv_fr09_unchanged_approved_stays_approved():
    plan = _submit([_gen(0, status="approved"), _gen(1, status="approved"), _gen(2, status="approved")])
    assert [s.status for s in plan.steps] == ["approved"] * 3


def test_rv_fr09_param_change_becomes_edited():
    plan = _submit([
        _gen(0, status="approved"),
        _gen(1, status="approved", params={"strategy": "mean"}),
        _gen(2, status="approved"),
    ])
    assert plan.steps[1].status == "edited"


def test_rv_fr09_default_param_spelled_out_is_not_an_edit():
    plan = _submit([
        _gen(0, status="approved"),
        _gen(1, status="approved"),
        _gen(2, status="approved", params={"method": "iqr", "factor": 1.5}),
    ])
    assert plan.steps[2].status == "approved"


def test_rv_fr09_toggle_off_becomes_disabled():
    plan = _submit([_gen(0, status="disabled"), _gen(1, status="approved"), _gen(2, status="approved")])
    assert plan.steps[0].status == "disabled"


def test_rv_fr09_unknown_step_is_user_added():
    plan = _submit([
        _gen(0, status="approved"),
        _gen(1, status="approved"),
        _gen(2, status="approved"),
        {"op": "drop_column", "params": {"columns": ["cabin"]}, "status": "approved"},
    ])
    assert plan.steps[3].status == "user_added"
    assert plan.steps[3].step_id == "u1"
    assert plan.steps[3].rationale


def test_rv_fr09_client_cannot_rewrite_rationale():
    plan = _submit([
        _gen(0, status="approved", rationale="hacked"),
        _gen(1, status="approved"),
        _gen(2, status="approved"),
    ])
    assert plan.steps[0].rationale == "dupes"


def test_rv_fr09_omitting_a_step_is_rejected():
    with pytest.raises(ReviewError) as exc:
        _submit([_gen(0, status="approved"), _gen(1, status="approved")])
    assert exc.value.code == "missing_steps"


def test_rv_fr09_changing_op_of_a_step_is_rejected():
    with pytest.raises(ReviewError) as exc:
        _submit([
            _gen(0, status="approved"),
            {**_gen(1), "op": "impute", "params": {"strategy": "mode"}, "status": "approved"},
            {**_gen(2), "op": "drop_column", "column": None, "params": {"columns": ["fare"]}},
        ])
    assert exc.value.code == "op_changed"


def test_rv_fr10_unreviewed_lists_proposed_steps():
    plan = _submit([_gen(0, status="approved"), _gen(1), _gen(2, status="disabled")])
    assert unreviewed(plan) == ["s2"]
