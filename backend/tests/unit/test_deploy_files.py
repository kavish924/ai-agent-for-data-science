"""Spec 11: static checks of the deployment files. The Docker build itself runs in CI (deploy-smoke)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _ignored(rel: str) -> set[str]:
    return {line.strip() for line in _read(rel).splitlines() if line.strip() and not line.startswith("#")}


def test_dp_ac1_images_run_as_non_root_and_ship_nothing_sensitive():
    backend, frontend = _read("backend/Dockerfile"), _read("frontend/Dockerfile")
    assert re.search(r"^USER appuser$", backend, re.M), "backend must drop root"
    assert re.search(r"^USER node$", frontend, re.M), "frontend must drop root"
    assert "COPY app ./app" in backend and "COPY . " not in backend  # only the source tree
    assert "[project]" not in backend and "optional-dependencies" not in backend  # no dev extras installed
    assert {"tests/", ".env", ".venv/", "storage/", "eval/", "scripts/"} <= _ignored("backend/.dockerignore")
    assert {".env", "backend/", "storage/", ".git/", "**/node_modules/"} <= _ignored(".dockerignore")
    assert re.search(r"^FROM python:3\.11\.\d+-slim", backend, re.M)  # pinned base
    assert re.search(r"^FROM node:22\.\d+\.\d+-", frontend, re.M)
    assert "--workers 1" in backend  # FR-DP-06


def test_dp_ac17_images_listen_on_render_port():
    assert "${PORT:-8000}" in _read("backend/Dockerfile")
    assert "${PORT:-3000}" in _read("frontend/Dockerfile")


def test_dp_ac5_compose_keeps_sessions_on_a_volume():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load(_read("deploy/compose.yaml"))
    backend = compose["services"]["backend"]
    assert "data:/data" in backend["volumes"] and "data" in compose["volumes"]
    assert backend["environment"]["STORAGE_PERSISTENT"] == "true"
    assert "ports" not in backend, "only the frontend is published"
    assert backend["mem_limit"] == "512m"  # FR-DP-20: Render free-tier memory
    assert compose["services"]["frontend"]["environment"]["BACKEND_URL"] == "http://backend:8000"


def test_dp_ac15_ci_runs_the_deployment_smoke():
    yaml = pytest.importorskip("yaml")
    job = yaml.safe_load(_read(".github/workflows/ci.yml"))["jobs"]["deploy-smoke"]
    script = "\n".join(step.get("run", "") for step in job["steps"])
    assert "deploy/ci.env" in job["env"]["COMPOSE"] and "--build --wait" in script
    assert "smoke_deploy.py" in script and "--check-session" in script  # AC-5 after a restart
    assert "restart backend" in script and "401" in script  # token closes the backend
    lines = [line for line in _read("deploy/ci.env").splitlines() if "=" in line and not line.startswith("#")]
    ci = dict(line.split("=", 1) for line in lines)
    assert ci["APP_ENV"] == "production" and ci["LLM_PROVIDER"] == "offline"
    assert ci["MAX_FILE_SIZE_MB"] == "5" and ci["MAX_ROWS"] == "20000"
