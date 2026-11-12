"""Report generation through the API (Spec 08, Spec 09 FR-AP-06/22, Spec 10 AC-4)."""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from pathlib import Path

import pytest

from app.config import settings
from app.llm.client import LLMError
from app.llm.fake import ScriptedLLM
from app.logging_setup import JsonFormatter
from app.routers.plans import get_llm
from app.storage.artifacts import execution_log_path, model_runs_path

SAMPLES = Path(__file__).resolve().parents[3] / "samples"
SECTIONS = ["snapshot", "issues", "cleaning", "comparison", "charts", "ml", "summary"]
PLAN = {"steps": [
    {"op": "drop_column", "column": None, "params": {"columns": ["Cabin"]}, "rationale": "77% missing."},
    {"op": "impute", "column": "Age", "params": {"strategy": "median"}, "rationale": "Age is 19.9% missing."},
]}
NARRATION = {
    "overview": "The cleaned data keeps {{rows_after}} rows and {{cols_after}} columns.",
    "cleaning": "Missing cells fell from {{null_cells_before}} to {{null_cells_after}}.",
    "modeling": "{{best_model}} was best.",
    "next_steps": "Tune the best model.",
}


def _url(sid: str, path: str = "") -> str:
    return f"/api/v1/sessions/{sid}{path}"


@pytest.fixture()
def narrator(client):
    def install(llm):
        client.app.dependency_overrides[get_llm] = lambda: llm
        return llm

    yield install
    client.app.dependency_overrides.clear()


def _run(client, *, train: bool = True, disable_all: bool = False) -> str:
    raw = (SAMPLES / "titanic.csv").read_bytes()
    sid = client.post("/api/v1/sessions", files={"file": ("titanic.csv", raw, "text/csv")}).json()["id"]
    client.put(_url(sid, "/target"), json={"target": "Survived"})
    plan = client.post(_url(sid, "/plan"), json=PLAN).json()
    status = "disabled" if disable_all else "approved"
    review = {"steps": [{**s, "status": status} for s in plan["steps"]]}
    assert client.post(_url(sid, "/plan/approve"), json=review).status_code == 200
    assert client.post(_url(sid, "/execute")).status_code == 202
    if train:
        assert client.post(_url(sid, "/model")).status_code == 202
    return sid


def _report(client, sid: str, **body) -> str:
    created = client.post(_url(sid, "/report"), json=body or None)
    assert created.status_code == 201, created.json()
    response = client.get(_url(sid, "/report"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def _section(html: str, name: str) -> str:
    match = re.search(rf'<section id="sec-{name}".*?</section>', html, re.DOTALL)
    assert match, f"section {name} missing"
    return match.group(0)


def test_rp_ac1_seven_sections_in_order(client, narrator):
    narrator(ScriptedLLM([NARRATION]))
    html = _report(client, _run(client))
    positions = [html.index(f'id="sec-{name}"') for name in SECTIONS]
    assert positions == sorted(positions)


def test_rp_ac2_step_shows_rationale_status_and_logged_counts(client, narrator):
    narrator(ScriptedLLM([NARRATION]))
    sid = _run(client)
    html = _report(client, sid)
    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    age = next(s for s in log["steps"] if s["column"] == "Age")
    row = re.search(r'<tr id="step-s2".*?</tr>', html, re.DOTALL).group(0)
    assert "Age is 19.9% missing." in row
    assert "approved" in row
    assert f"{age['before']['null_cells']:,} → {age['after']['null_cells']:,}" in row


def test_rp_ac3_numbers_come_from_artifacts(client, narrator):
    narrator(ScriptedLLM([NARRATION]))
    sid = _run(client)
    html = _report(client, sid)
    log = json.loads(execution_log_path(settings.storage_root, sid).read_text())
    runs = json.loads(model_runs_path(settings.storage_root, sid).read_text())
    summary = _section(html, "summary")
    first, last = log["steps"][0]["before"], log["steps"][-1]["after"]
    assert f"Missing cells fell from {first['null_cells']:,} to {last['null_cells']:,}." in summary
    assert f"keeps {last['rows']:,} rows and {last['cols']:,} columns" in summary
    best = next(m for m in runs["models"] if m["name"] == runs["best_model"])
    assert f"{best['cv'][runs['primary_metric']]['mean']:.3f}" in _section(html, "ml")


def test_rp_ac4_narration_failure_uses_template(client, narrator):
    narrator(ScriptedLLM([LLMError("down")] * 2))
    sid = _run(client)
    created = client.post(_url(sid, "/report"))
    assert created.status_code == 201
    assert created.json()["narration_source"] == "template"
    assert "Template summary" in _section(client.get(_url(sid, "/report")).text, "summary")


def test_rp_ac5_report_404_until_created(client, narrator):
    narrator(ScriptedLLM([NARRATION]))
    sid = _run(client)  # modeled, no report yet
    response = client.get(_url(sid, "/report"))
    assert response.status_code == 404
    assert response.json()["error"]["details"]["state"] == "modeled"


def test_rp_ac6_bundle_holds_every_deliverable(client, narrator):
    narrator(ScriptedLLM([NARRATION]))
    sid = _run(client)
    _report(client, sid)
    response = client.get(_url(sid, "/bundle.zip"))
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert archive.testzip() is None
    names = set(archive.namelist())
    assert {"report.html", "cleaned_titanic.csv", "execution_log.json", "model_runs.json",
            "plan.approved.json"} <= names
    assert any(n.startswith("charts/") and n.endswith(".png") for n in names)
    again = client.get(_url(sid, "/bundle.zip")).content
    assert again == response.content  # fixed entry timestamps: reproducible


def test_rp_ac7_all_steps_disabled_renders_no_changes(client, narrator):
    narrator(None)
    html = _report(client, _run(client, train=False, disable_all=True))
    assert "No changes applied" in _section(html, "cleaning")


def test_rp_ac9_rerender_is_byte_identical_and_offline(client, narrator):
    llm = narrator(ScriptedLLM([NARRATION]))  # one answer only: a re-render must not ask again
    sid = _run(client)
    first = _report(client, sid)
    second = _report(client, sid)
    assert first == second
    assert len(llm.prompts) == 1
    assert not re.search(r'(src|href)="https?://', first)


def test_rp_ac10_no_model_run_says_training_skipped(client, narrator):
    narrator(None)
    html = _report(client, _run(client, train=False))
    assert "Model training was skipped" in _section(html, "ml")


def test_ap_ac13_report_and_bundle_endpoints(client, narrator):
    narrator(None)
    sid = _run(client, train=False)
    assert client.get(_url(sid, "/report")).status_code == 404
    assert client.get(_url(sid, "/bundle.zip")).status_code == 404
    _report(client, sid)
    assert client.get(_url(sid, "/bundle.zip")).headers["content-type"] == "application/zip"
    # retraining after a report moves the state on: the old report is not served
    assert client.post(_url(sid, "/model"), json={"target": "Survived"}).status_code == 202
    assert client.get(_url(sid, "/report")).status_code == 404


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.events: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.events.append(json.loads(self.format(record)))


def test_nfr_ac4_one_completion_line_per_stage(client, narrator):
    narrator(ScriptedLLM([NARRATION]))
    capture = _Capture()
    logging.getLogger().addHandler(capture)
    try:
        sid = _run(client)
        _report(client, sid)
    finally:
        logging.getLogger().removeHandler(capture)
    for event in ("profile.completed", "plan.validated", "execute.completed", "charts.generated",
                  "model.completed", "report.generated"):
        lines = [e for e in capture.events if e["message"] == event and e.get("session_id") == sid]
        assert len(lines) == 1, event
        assert isinstance(lines[0].get("duration_ms"), int), event
