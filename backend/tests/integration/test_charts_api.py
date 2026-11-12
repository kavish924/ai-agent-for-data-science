"""Charts + after-profile through the API (Spec 06 FR-CH-10/11, Spec 09 FR-AP-17..19)."""

from __future__ import annotations

import json

from app.config import settings
from app.storage.artifacts import charts_manifest_path, cleaned_csv_path
from tests.conftest import upload_csv

# a: repeating numbers with 8 blanks (not unique, so not an identifier); b: numeric; c: category
CSV = "a,b,c\n" + "".join(
    f"{(i * 7) % 11 if i % 5 else ''},{i % 3},{'xyz'[i % 3]}\n" for i in range(1, 41)
)
PLAN = {"steps": [{"op": "impute", "column": "a", "params": {"strategy": "median"},
                   "rationale": "a has missing values."}]}


def _url(sid: str, path: str = "") -> str:
    return f"/api/v1/sessions/{sid}{path}"


def _run(client) -> str:
    sid = upload_csv(client, CSV).json()["id"]
    plan = client.post(_url(sid, "/plan"), json=PLAN).json()
    review = {"steps": [{**s, "status": "approved"} for s in plan["steps"]]}
    assert client.post(_url(sid, "/plan/approve"), json=review).status_code == 200
    assert client.post(_url(sid, "/execute")).status_code == 202
    return sid


def test_ap_ac11_chart_endpoints(client):
    sid = upload_csv(client, CSV).json()["id"]
    for path in ("/charts", "/charts/01_x.png", "/profile/after"):
        assert client.get(_url(sid, path)).status_code == 404

    sid = _run(client)
    manifest = client.get(_url(sid, "/charts"))
    assert manifest.status_code == 200
    charts = manifest.json()["charts"]
    assert charts
    for chart in charts:
        png = client.get(_url(sid, f"/charts/{chart['file']}"))
        assert png.status_code == 200
        assert png.headers["content-type"] == "image/png"
        assert png.content[:4] == b"\x89PNG"


def test_ch_ac7_after_profile_reflects_cleaning(client):
    sid = _run(client)
    after = client.get(_url(sid, "/profile/after"))
    assert after.status_code == 200
    columns = {c["name"]: c for c in after.json()["columns"]}
    assert columns["a"]["nulls"] == 0
    before = client.get(_url(sid, "/profile")).json()
    assert {c["name"]: c for c in before["columns"]}["a"]["nulls"] == 8


def test_ch_ac8_imputed_column_has_before_overlay(client):
    sid = _run(client)
    charts = client.get(_url(sid, "/charts")).json()["charts"]
    overlay = {c["column"]: c["before_overlay"] for c in charts if c["kind"] == "distribution"}
    assert overlay["a"] is True
    assert overlay["b"] is False


def test_ch_ac9_chart_files_are_whitelisted(client):
    sid = _run(client)
    for name in ("nope.png", "..%2Fprofile.json", "..%5Cprofile.json", "charts_manifest.json"):
        response = client.get(_url(sid, f"/charts/{name}"))
        assert response.status_code == 404, name


def test_ch_ac6_chart_failure_never_fails_the_run(client, monkeypatch):
    from app.services import charts

    def boom(*args, **kwargs):
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(charts, "generate_charts", boom)
    sid = _run(client)
    status = client.get(_url(sid)).json()
    assert status["state"] == "executed"
    assert status["error"] is None
    assert cleaned_csv_path(settings.storage_root, sid, "test.csv").exists()
    manifest = json.loads(charts_manifest_path(settings.storage_root, sid).read_text())
    assert manifest["status"] == "failed"
    assert "renderer exploded" in manifest["error"]
    assert manifest["charts"] == []
