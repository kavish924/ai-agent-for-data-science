"""Integration tests for the plan/execute flow (Spec 05, Spec 09 FR-AP-03/04) - no LLM."""

from __future__ import annotations

import json

from app.config import settings
from app.storage.artifacts import cleaned_csv_path, execution_log_path
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


def _plan(client, sid: str, body=PLAN):
    return client.post(f"/api/v1/sessions/{sid}/plan", json=body)


def _execute(client, sid: str, body=PLAN):
    return client.post(f"/api/v1/sessions/{sid}/execute", json=body)


def test_full_flow_upload_plan_execute(client):
    sid = upload_csv(client, CSV).json()["id"]

    # plan: 201 -> awaiting_approval
    response = _plan(client, sid)
    assert response.status_code == 201
    assert response.json()["schema_version"] == "v1"
    assert client.get(f"/api/v1/sessions/{sid}").json()["state"] == "awaiting_approval"

    # stored plan is fetchable
    fetched = client.get(f"/api/v1/sessions/{sid}/plan")
    assert fetched.status_code == 200
    assert fetched.json()["steps"][1]["column"] == "a"

    # execute: 202 -> executed (TestClient runs background tasks synchronously)
    response = _execute(client, sid)
    assert response.status_code == 202
    assert client.get(f"/api/v1/sessions/{sid}").json()["state"] == "executed"

    # deliverable: cleaned_<name>.csv with dup removed and null filled (FR-EX-07)
    cleaned = cleaned_csv_path(settings.storage_root, sid, "test.csv").read_text()
    lines = cleaned.strip().splitlines()
    assert lines[0] == "a,b"  # original header preserved
    # Column 'a' is float64: the null at ingestion forces pandas' float dtype,
    # so the filled value renders as 0.0 (dtype preservation is not required by
    # the PRD - names and order are; a cast_type step can int-cast explicitly).
    assert sorted(lines[1:]) == ["0.0,y", "1.0,x"]

    # audit log: per-step before/after (FR-EX-03)
    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    assert log["status"] == "completed"
    assert [entry["status"] for entry in log["steps"]] == ["executed", "executed"]
    assert log["steps"][0]["before"]["rows"] == 3
    assert log["steps"][0]["after"]["rows"] == 2
    assert log["steps"][0]["notes"]["rows_removed"] == 1
    assert log["steps"][1]["notes"]["filled"] == 1
    assert log["steps"][1]["after"]["null_cells"] == 0

    # original upload untouched (FR-EX-06)
    from app.storage.artifacts import upload_path

    assert upload_path(settings.storage_root, sid).read_bytes() == CSV.encode("utf-8")

    # no re-planning after execution (Spec 09 state guards)
    assert _plan(client, sid).status_code == 409


def test_execute_requires_awaiting_approval(client):
    sid = upload_csv(client, CSV).json()["id"]  # state: profiled
    response = _execute(client, sid)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_approvable"


def test_get_plan_before_created_409(client):
    sid = upload_csv(client, CSV).json()["id"]
    response = client.get(f"/api/v1/sessions/{sid}/plan")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_pending"


def test_plan_can_be_regenerated_from_awaiting_approval(client):
    sid = upload_csv(client, CSV).json()["id"]
    assert _plan(client, sid).status_code == 201
    assert _plan(client, sid).status_code == 201  # regenerate
    assert client.get(f"/api/v1/sessions/{sid}").json()["state"] == "awaiting_approval"


def test_plan_unknown_column_422(client):
    sid = upload_csv(client, CSV).json()["id"]
    body = {"steps": [{"op": "impute", "column": "zzz", "params": {"strategy": "mode"}}]}
    response = _plan(client, sid, body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_plan"
    assert error["details"]["issues"]


def test_plan_type_incompatible_422(client):
    sid = upload_csv(client, CSV).json()["id"]  # b is categorical
    body = {"steps": [{"op": "impute", "column": "b", "params": {"strategy": "mean"}}]}
    response = _plan(client, sid, body)
    assert response.status_code == 422
    assert "numeric" in response.json()["error"]["details"]["issues"][0]["issue"]


def test_plan_unknown_op_422_validation_error(client):
    sid = upload_csv(client, CSV).json()["id"]
    body = {"steps": [{"op": "drop_outliers", "column": "a"}]}
    response = _plan(client, sid, body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_execute_revalidates_submitted_steps(client):
    """AC-3: the client is never trusted - the Gate runs again at execute time."""
    sid = upload_csv(client, CSV).json()["id"]
    assert _plan(client, sid).status_code == 201
    tampered = {"steps": [{"op": "impute", "column": "zzz", "params": {"strategy": "mode"}}]}
    response = _execute(client, sid, tampered)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_plan"


def test_failing_step_aborts_and_keeps_log(client):
    csv = "a,b\n1,x\n,y\n2,z\n"  # a: [1, null, 2] -> cast to int fails on the null
    sid = upload_csv(client, csv).json()["id"]
    body = {"steps": [{"op": "cast_type", "column": "a", "params": {"to": "int"}}]}
    assert _plan(client, sid, body).status_code == 201
    assert _execute(client, sid, body).status_code == 202

    status = client.get(f"/api/v1/sessions/{sid}").json()
    assert status["state"] == "awaiting_approval"  # last good state (FR-EX-05)
    assert "step 0" in status["error"]

    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    assert log["status"] == "failed"
    assert log["failed_step"] == 0
    assert log["steps"][0]["status"] == "failed"

    # no deliverable exported on failure (FR-EX-05)
    assert not cleaned_csv_path(settings.storage_root, sid, "test.csv").exists()


def test_disabled_step_skipped_and_logged(client):
    sid = upload_csv(client, CSV).json()["id"]
    body = {
        "steps": [
            {"op": "drop_duplicates", "params": {}, "status": "approved"},
            {
                "op": "impute",
                "column": "a",
                "params": {"strategy": "constant", "value": 99},
                "status": "disabled",
            },
        ]
    }
    assert _plan(client, sid, body).status_code == 201
    assert _execute(client, sid, body).status_code == 202
    assert client.get(f"/api/v1/sessions/{sid}").json()["state"] == "executed"

    cleaned = cleaned_csv_path(settings.storage_root, sid, "test.csv").read_text()
    assert len(cleaned.strip().splitlines()) == 3  # dup removed...
    assert ",y" in cleaned  # ...but null NOT filled (step disabled)

    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    assert [entry["status"] for entry in log["steps"]] == ["executed", "disabled"]


def test_deterministic_outputs_across_sessions(client):
    csv = "x,y\n1.5,1\n2.5,2\n100.0,3\n"
    body = {"steps": [{"op": "clip_outliers", "column": "x", "params": {"factor": 3}}]}
    outputs = []
    for _ in range(2):
        sid = upload_csv(client, csv).json()["id"]
        assert _plan(client, sid, body).status_code == 201
        assert _execute(client, sid, body).status_code == 202
        outputs.append(cleaned_csv_path(settings.storage_root, sid, "test.csv").read_bytes())
    assert outputs[0] == outputs[1]  # FR-EX-08 / PRD §9 Reproducibility
