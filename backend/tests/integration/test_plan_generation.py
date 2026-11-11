"""LLM plan generation through the API (Spec 03 FR-PL-14, Spec 10 AC-2/AC-5) - fake LLM."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest

from app.config import settings
from app.db import session_store
from app.llm.client import LLMError
from app.llm.fake import ScriptedLLM
from app.logging_setup import JsonFormatter
from app.routers.plans import get_llm
from app.storage.artifacts import upload_path
from tests.conftest import upload_csv

SAMPLES = Path(__file__).resolve().parents[3] / "samples"

TITANIC_PLAN = {
    "steps": [
        {"op": "impute", "column": "Age", "params": {"strategy": "median"},
         "rationale": "Age is 19.9% missing."},
        {"op": "impute", "column": "Embarked", "params": {"strategy": "mode"},
         "rationale": "Embarked has 2 missing values."},
    ]
}


@pytest.fixture()
def use_llm(client):
    def install(llm):
        client.app.dependency_overrides[get_llm] = lambda: llm
        return llm

    yield install
    client.app.dependency_overrides.clear()


def _upload_titanic(client) -> str:
    raw = (SAMPLES / "titanic.csv").read_bytes()
    return client.post("/api/v1/sessions", files={"file": ("titanic.csv", raw, "text/csv")}).json()["id"]


def test_pl_ac1_generate_titanic_plan(client, use_llm):
    llm = use_llm(ScriptedLLM([TITANIC_PLAN]))
    sid = _upload_titanic(client)
    response = client.post(f"/api/v1/sessions/{sid}/plan")
    assert response.status_code == 201, response.json()
    plan = response.json()
    assert plan["version"] == 1
    assert [s["step_id"] for s in plan["steps"]] == ["s1", "s2"]
    assert {s["status"] for s in plan["steps"]} == {"proposed"}
    assert plan["steps"][0]["rationale"].startswith("Age is 19.9%")
    assert client.get(f"/api/v1/sessions/{sid}").json()["state"] == "awaiting_approval"
    assert len(llm.prompts) == 1


def test_pl_ac9_no_api_key_is_503_and_changes_nothing(client, use_llm):
    use_llm(None)
    sid = upload_csv(client, "a,b\n1,x\n2,y\n").json()["id"]
    response = client.post(f"/api/v1/sessions/{sid}/plan")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_not_configured"
    status = client.get(f"/api/v1/sessions/{sid}").json()
    assert status["state"] == "profiled"
    assert status["plan_version"] is None


def test_pl_fr14_manual_plan_still_works_without_llm(client, use_llm):
    use_llm(None)
    sid = upload_csv(client, "a,b\n1,x\n,y\n").json()["id"]
    body = {"steps": [{"op": "impute", "column": "a", "params": {"strategy": "median"}}]}
    assert client.post(f"/api/v1/sessions/{sid}/plan", json=body).status_code == 201


def test_nfr_ac5_llm_failure_is_visible_and_recoverable(client, use_llm):
    use_llm(ScriptedLLM([LLMError("boom")] * 3))
    sid = _upload_titanic(client)
    before = hashlib.sha256(upload_path(settings.storage_root, sid).read_bytes()).hexdigest()

    response = client.post(f"/api/v1/sessions/{sid}/plan")
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "planner_failed"
    assert error["details"]["attempts"] == 3
    status = client.get(f"/api/v1/sessions/{sid}").json()
    assert status["state"] == "profiled"
    assert status["failed_stage"] == "plan"
    assert status["error"]
    after = hashlib.sha256(upload_path(settings.storage_root, sid).read_bytes()).hexdigest()
    assert before == after  # no data mutation

    use_llm(ScriptedLLM([TITANIC_PLAN]))  # retry succeeds
    assert client.post(f"/api/v1/sessions/{sid}/plan").status_code == 201
    status = client.get(f"/api/v1/sessions/{sid}").json()
    assert status["error"] is None and status["failed_stage"] is None


def test_pl_ac6_execution_never_calls_the_llm(client, use_llm):
    llm = use_llm(ScriptedLLM([TITANIC_PLAN]))  # exactly one response available
    sid = _upload_titanic(client)
    plan = client.post(f"/api/v1/sessions/{sid}/plan").json()
    review = {"steps": [{**s, "status": "approved"} for s in plan["steps"]]}
    assert client.post(f"/api/v1/sessions/{sid}/plan/approve", json=review).status_code == 200
    assert client.post(f"/api/v1/sessions/{sid}/execute").status_code == 202
    assert client.get(f"/api/v1/sessions/{sid}").json()["state"] == "executed"
    assert len(llm.prompts) == 1


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def test_nfr_ac2_no_data_or_prompt_in_logs(client, use_llm):
    secret = "Zebediah-Quux-PRIVATE"
    rows = "".join(f"{i},{secret}-{i},{i % 3}\n" for i in range(60))
    csv = "uid,note,grp\n" + rows
    plan = {"steps": [{"op": "drop_duplicates", "column": None, "params": {},
                       "rationale": "Remove exact duplicates."}]}
    llm = use_llm(ScriptedLLM([{"steps": [{"op": "drop_outliers"}]}, plan]))

    capture = _Capture()
    logging.getLogger().addHandler(capture)
    try:
        sid = upload_csv(client, csv).json()["id"]
        assert client.post(f"/api/v1/sessions/{sid}/plan").status_code == 201
    finally:
        logging.getLogger().removeHandler(capture)

    text = "\n".join(capture.lines)
    assert "llm.call" in text  # the call is logged...
    assert secret not in text  # ...but no raw values
    assert "You are" not in text and llm.prompts[0][:80] not in text  # ...and no prompt
    for call in session_store.list_llm_calls(settings.db_path, sid):
        assert secret not in json.dumps(call)
    assert all(secret not in prompt for prompt in llm.prompts)  # never sent to the LLM
