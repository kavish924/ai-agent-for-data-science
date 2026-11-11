"""Integration tests: plan versions → review → approve → execute (Specs 04, 05, 09) - no LLM."""

from __future__ import annotations

import json

from app.config import settings
from app.db import session_store
from app.storage.artifacts import cleaned_csv_path, execution_log_path, upload_path
from tests.conftest import upload_csv

CSV = "a,b\n1,x\n1,x\n,y\n"  # a: numeric with 1 null; b: categorical; 1 duplicate row

PLAN = {
    "schema": "v1",
    "steps": [
        {"op": "drop_duplicates", "params": {}, "rationale": "1 duplicate row found"},
        {
            "op": "impute",
            "column": "a",
            "params": {"strategy": "constant", "value": 0},
            "rationale": "fill the single missing value with 0",
        },
    ],
}


def _url(sid: str, path: str = "") -> str:
    return f"/api/v1/sessions/{sid}{path}"


def _state(client, sid: str) -> dict:
    return client.get(_url(sid)).json()


def _approve_all(plan: dict) -> dict:
    return {"steps": [{**step, "status": "approved"} for step in plan["steps"]]}


def _plan_and_approve(client, sid: str, body: dict = PLAN) -> dict:
    created = client.post(_url(sid, "/plan"), json=body)
    assert created.status_code == 201, created.json()
    approved = client.post(_url(sid, "/plan/approve"), json=_approve_all(created.json()))
    assert approved.status_code == 200, approved.json()
    return approved.json()


def test_full_flow_plan_review_approve_execute(client):
    sid = upload_csv(client, CSV).json()["id"]

    created = client.post(_url(sid, "/plan"), json=PLAN)
    assert created.status_code == 201
    plan = created.json()
    assert plan["version"] == 1
    assert [s["step_id"] for s in plan["steps"]] == ["s1", "s2"]
    assert {s["status"] for s in plan["steps"]} == {"proposed"}
    assert _state(client, sid)["state"] == "awaiting_approval"

    approved = client.post(_url(sid, "/plan/approve"), json=_approve_all(plan))
    assert approved.status_code == 200
    assert _state(client, sid)["state"] == "approved"

    response = client.post(_url(sid, "/execute"))
    assert response.status_code == 202
    assert _state(client, sid)["state"] == "executed"

    cleaned = cleaned_csv_path(settings.storage_root, sid, "test.csv").read_text()
    lines = cleaned.strip().splitlines()
    assert lines[0] == "a,b"
    assert sorted(lines[1:]) == ["0.0,y", "1.0,x"]

    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    assert log["status"] == "completed"
    assert log["plan_version"] == 1
    assert [entry["status"] for entry in log["steps"]] == ["executed", "executed"]
    assert [entry["step_id"] for entry in log["steps"]] == ["s1", "s2"]
    assert log["steps"][0]["notes"]["rows_removed"] == 1
    assert log["steps"][1]["after"]["null_cells"] == 0

    assert upload_path(settings.storage_root, sid).read_bytes() == CSV.encode("utf-8")
    assert client.post(_url(sid, "/plan"), json=PLAN).status_code == 409


def test_ap_ac6_execute_before_approve_is_409(client):
    sid = upload_csv(client, CSV).json()["id"]
    assert client.post(_url(sid, "/plan"), json=PLAN).status_code == 201
    response = client.post(_url(sid, "/execute"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_approved"


def test_ap_ac6_approve_with_proposed_steps_is_422(client):
    sid = upload_csv(client, CSV).json()["id"]
    assert client.post(_url(sid, "/plan"), json=PLAN).status_code == 201
    response = client.post(_url(sid, "/plan/approve"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "unreviewed_steps"
    assert error["details"]["step_ids"] == ["s1", "s2"]


def test_ap_ac6_execute_runs_the_frozen_approved_plan(client):
    sid = upload_csv(client, CSV).json()["id"]
    plan = client.post(_url(sid, "/plan"), json=PLAN).json()
    review = _approve_all(plan)
    review["steps"][1]["status"] = "disabled"
    assert client.post(_url(sid, "/plan/approve"), json=review).status_code == 200
    assert client.post(_url(sid, "/execute")).status_code == 202

    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    assert [entry["status"] for entry in log["steps"]] == ["executed", "disabled"]
    cleaned = cleaned_csv_path(settings.storage_root, sid, "test.csv").read_text()
    assert ",y" in cleaned  # null NOT filled: step 2 was disabled


def test_ap_ac7_second_execute_is_rejected(client):
    sid = upload_csv(client, CSV).json()["id"]
    _plan_and_approve(client, sid)
    # the conditional transition lets exactly one caller through
    assert session_store.transition(settings.db_path, sid, ["approved"], state="executing")
    assert not session_store.transition(settings.db_path, sid, ["approved"], state="executing")
    response = client.post(_url(sid, "/execute"))
    assert response.status_code == 409


def test_ap_ac8_history_keeps_every_version(client):
    sid = upload_csv(client, CSV).json()["id"]
    assert client.post(_url(sid, "/plan"), json=PLAN).status_code == 201
    second = client.post(_url(sid, "/plan"), json=PLAN).json()
    assert second["version"] == 2
    client.post(_url(sid, "/plan/approve"), json=_approve_all(second))

    history = client.get(_url(sid, "/plan/history")).json()
    assert [(h["version"], h["kind"]) for h in history["versions"]] == [
        (1, "generated"),
        (2, "generated"),
        (2, "approved"),
    ]
    assert _state(client, sid)["plan_version"] == 2


def test_rv_fr09_put_plan_reconciles_and_records_edits(client):
    sid = upload_csv(client, CSV).json()["id"]
    plan = client.post(_url(sid, "/plan"), json=PLAN).json()
    review = _approve_all(plan)
    review["steps"][1]["params"] = {"strategy": "constant", "value": 7}
    saved = client.put(_url(sid, "/plan"), json=review)
    assert saved.status_code == 200
    assert [s["status"] for s in saved.json()["steps"]] == ["approved", "edited"]
    assert client.get(_url(sid, "/plan")).json()["steps"][1]["status"] == "edited"


def test_ap_ac3_review_edits_are_regated(client):
    sid = upload_csv(client, CSV).json()["id"]
    plan = client.post(_url(sid, "/plan"), json=PLAN).json()
    review = _approve_all(plan)
    review["steps"].append(
        {"op": "impute", "column": "zzz", "params": {"strategy": "mode"}, "status": "approved"}
    )
    response = client.put(_url(sid, "/plan"), json=review)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_plan"


def test_get_plan_before_created_409(client):
    sid = upload_csv(client, CSV).json()["id"]
    response = client.get(_url(sid, "/plan"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_pending"


def test_plan_unknown_column_422(client):
    sid = upload_csv(client, CSV).json()["id"]
    body = {"steps": [{"op": "impute", "column": "zzz", "params": {"strategy": "mode"}}]}
    response = client.post(_url(sid, "/plan"), json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_plan"


def test_plan_type_incompatible_422(client):
    sid = upload_csv(client, CSV).json()["id"]
    body = {"steps": [{"op": "impute", "column": "b", "params": {"strategy": "mean"}}]}
    response = client.post(_url(sid, "/plan"), json=body)
    assert response.status_code == 422
    assert "numeric" in response.json()["error"]["details"]["issues"][0]["issue"]


def test_plan_unknown_op_422_validation_error(client):
    sid = upload_csv(client, CSV).json()["id"]
    body = {"steps": [{"op": "drop_outliers", "column": "a"}]}
    response = client.post(_url(sid, "/plan"), json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_ex_fr05_failing_step_returns_to_review_and_keeps_log(client):
    csv = "a,b\n1,x\nabc,y\n2,z\n"  # 'a' is text-ish; cast to int fails on 'abc'
    sid = upload_csv(client, csv).json()["id"]
    body = {"steps": [{"op": "cast_type", "column": "a", "params": {"to": "int"}}]}
    _plan_and_approve(client, sid, body)
    assert client.post(_url(sid, "/execute")).status_code == 202

    status = _state(client, sid)
    assert status["state"] == "awaiting_approval"
    assert status["failed_stage"] == "execute"
    assert "step 0" in status["error"]

    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    assert log["status"] == "failed"
    assert log["steps"][0]["status"] == "failed"
    assert not cleaned_csv_path(settings.storage_root, sid, "test.csv").exists()


def test_ex_ac11_unexpected_exception_never_leaves_executing(client, monkeypatch):
    from app.services import executor

    def boom(df, step):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(executor, "apply_step", boom)
    sid = upload_csv(client, CSV).json()["id"]
    _plan_and_approve(client, sid)
    assert client.post(_url(sid, "/execute")).status_code == 202
    status = _state(client, sid)
    assert status["state"] == "awaiting_approval"
    assert status["failed_stage"] == "execute"
    assert "disk on fire" in status["error"]


def test_ap_ac9_cleaned_csv_download(client):
    sid = upload_csv(client, CSV, name="people.csv").json()["id"]
    assert client.get(_url(sid, "/cleaned.csv")).status_code == 404
    _plan_and_approve(client, sid)
    client.post(_url(sid, "/execute"))
    response = client.get(_url(sid, "/cleaned.csv"))
    assert response.status_code == 200
    assert "cleaned_people.csv" in response.headers["content-disposition"]
    assert response.text.splitlines()[0] == "a,b"


def test_deterministic_outputs_across_sessions(client):
    csv = "x,y\n1.5,1\n2.5,2\n100.0,3\n"
    body = {"steps": [{"op": "clip_outliers", "column": "x", "params": {"factor": 3}}]}
    outputs = []
    for _ in range(2):
        sid = upload_csv(client, csv).json()["id"]
        _plan_and_approve(client, sid, body)
        assert client.post(_url(sid, "/execute")).status_code == 202
        outputs.append(cleaned_csv_path(settings.storage_root, sid, "test.csv").read_bytes())
    assert outputs[0] == outputs[1]  # FR-EX-08 / PRD §9 Reproducibility


# --- target (Spec 07 FR-ML-10, Spec 03 FR-PL-13) ------------------------------

TARGET_CSV = "uid,age,label\n" + "".join(f"u{i},{i % 7 or ''},{i % 2}\n" for i in range(30))


def test_ml_fr10_set_and_clear_target(client):
    sid = upload_csv(client, TARGET_CSV).json()["id"]
    response = client.put(_url(sid, "/target"), json={"target": "label"})
    assert response.status_code == 200
    assert response.json()["target"] == "label"
    assert client.put(_url(sid, "/target"), json={"target": None}).json()["target"] is None


def test_ml_fr10_id_like_and_unknown_targets_rejected(client):
    sid = upload_csv(client, TARGET_CSV).json()["id"]
    assert client.put(_url(sid, "/target"), json={"target": "uid"}).status_code == 422
    assert client.put(_url(sid, "/target"), json={"target": "nope"}).status_code == 422


def test_pl_ac8_plan_cannot_touch_target(client):
    sid = upload_csv(client, TARGET_CSV).json()["id"]
    client.put(_url(sid, "/target"), json={"target": "age"})
    body = {"steps": [{"op": "impute", "column": "age", "params": {"strategy": "median"}}]}
    response = client.post(_url(sid, "/plan"), json=body)
    assert response.status_code == 422
    assert "target" in response.json()["error"]["details"]["issues"][0]["issue"]


def test_ml_fr10_target_conflicting_with_plan_rejected(client):
    sid = upload_csv(client, TARGET_CSV).json()["id"]
    body = {"steps": [{"op": "impute", "column": "age", "params": {"strategy": "median"}}]}
    assert client.post(_url(sid, "/plan"), json=body).status_code == 201
    response = client.put(_url(sid, "/target"), json={"target": "age"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "target_conflicts_plan"
