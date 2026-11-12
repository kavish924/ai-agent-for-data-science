"""Baseline training through the API (Spec 07 FR-ML-08/10, Spec 09 FR-AP-05/20/21)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.db import session_store
from app.main import create_app

SAMPLES = Path(__file__).resolve().parents[3] / "samples"
PLAN = {"steps": [
    {"op": "drop_column", "column": None, "params": {"columns": ["Cabin"]}, "rationale": "77% missing."},
    {"op": "impute", "column": "Age", "params": {"strategy": "median"}, "rationale": "20% missing."},
]}


def _url(sid: str, path: str = "") -> str:
    return f"/api/v1/sessions/{sid}{path}"


def _upload(client) -> str:
    raw = (SAMPLES / "titanic.csv").read_bytes()
    return client.post("/api/v1/sessions", files={"file": ("titanic.csv", raw, "text/csv")}).json()["id"]


def _execute(client, sid: str) -> None:
    plan = client.post(_url(sid, "/plan"), json=PLAN).json()
    review = {"steps": [{**s, "status": "approved"} for s in plan["steps"]]}
    assert client.post(_url(sid, "/plan/approve"), json=review).status_code == 200
    assert client.post(_url(sid, "/execute")).status_code == 202
    assert client.get(_url(sid)).json()["state"] == "executed"


def test_ml_ac9_training_flow(client):
    sid = _upload(client)
    client.put(_url(sid, "/target"), json={"target": "Survived"})
    assert client.post(_url(sid, "/model")).status_code == 409  # not executed yet

    _execute(client, sid)
    response = client.post(_url(sid, "/model"))
    assert response.status_code == 202
    status = client.get(_url(sid)).json()
    assert status["state"] == "modeled"

    runs = client.get(_url(sid, "/model")).json()
    assert runs["target"] == "Survived"
    assert runs["problem_type"] == "classification"
    assert runs["best_model"] != "dummy"
    assert runs["replayed_ops"] == ["drop_column"]

    # retraining from `modeled` is allowed
    assert client.post(_url(sid, "/model")).status_code == 202


def test_ml_ac9_invalid_targets_rejected(client):
    sid = _upload(client)
    _execute(client, sid)
    response = client.post(_url(sid, "/model"), json={"target": "PassengerId"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_target"
    # Age was imputed by the executed plan: it can't become the target afterwards
    response = client.post(_url(sid, "/model"), json={"target": "Age"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "target_changed_by_plan"
    assert client.get(_url(sid)).json()["state"] == "executed"


def test_ml_ac9_training_failure_returns_to_executed(client, monkeypatch):
    from app.services import analyst

    def boom(*args, **kwargs):
        raise RuntimeError("solver diverged")

    monkeypatch.setattr(analyst, "train_baselines", boom)
    sid = _upload(client)
    _execute(client, sid)
    assert client.post(_url(sid, "/model"), json={"target": "Survived"}).status_code == 202
    status = client.get(_url(sid)).json()
    assert status["state"] == "executed"
    assert status["failed_stage"] == "model"
    assert "solver diverged" in status["error"]


def test_ap_ac12_model_and_targets_endpoints(client):
    sid = _upload(client)
    assert client.get(_url(sid, "/model")).status_code == 404
    targets = client.get(_url(sid, "/targets"))
    assert targets.status_code == 200
    assert targets.json()["suggestions"][0]["column"] == "Survived"


def test_nfr_fr07_interrupted_training_is_recovered(client):
    sid = _upload(client)
    _execute(client, sid)
    session_store.update_session(settings.db_path, sid, state="modeling")
    with TestClient(create_app()) as restarted:
        status = restarted.get(_url(sid)).json()
    assert status["state"] == "executed"
    assert status["failed_stage"] == "model"
