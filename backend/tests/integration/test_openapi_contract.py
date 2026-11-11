"""Spec 09 AC-5: the served OpenAPI matches the endpoints the spec declares."""

from __future__ import annotations

import re
from pathlib import Path

SPEC = Path(__file__).resolve().parents[3] / "docs" / "specs" / "09-api-contracts.md"
# Endpoints scheduled for later milestones are not served yet
NOT_YET_BUILT = {("POST", "/sessions/{id}/model"), ("GET", "/sessions/{id}/report")}


def _spec_endpoints() -> set[tuple[str, str]]:
    text = SPEC.read_text(encoding="utf-8")
    found = re.findall(r"`(GET|POST|PUT|DELETE) (/sessions[^`]*)`", text)
    return {(method, path) for method, path in found}


def test_ap_ac5_openapi_matches_spec(client):
    served = set()
    for path, ops in client.get("/openapi.json").json()["paths"].items():
        normalized = path.removeprefix("/api/v1").replace("{session_id}", "{id}")
        served |= {(method.upper(), normalized) for method in ops}

    declared = _spec_endpoints() - NOT_YET_BUILT
    assert declared, "no endpoints parsed from Spec 09"
    assert declared <= served, f"declared in spec but not served: {declared - served}"
    undeclared = {e for e in served if e[1].startswith("/sessions")} - _spec_endpoints()
    assert not undeclared, f"served but missing from spec: {undeclared}"
