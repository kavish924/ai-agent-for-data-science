"""Spec 11 (deployment) and Spec 09 FR-AP-23..25: meta endpoints, internal token, CORS, logs, secrets."""

from __future__ import annotations

import io
import logging
import time
from contextlib import redirect_stdout

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import session_store
from app.main import create_app
from tests.conftest import upload_csv

SECRET_KEY = "gk-very-secret-key-123"
SECRET_TOKEN = "tok-very-secret-456"


@pytest.fixture()
def make_client(tmp_path, monkeypatch):
    """Build an app after the test has set its settings (CORS, token and logs are read at creation)."""
    storage = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_root", storage)
    monkeypatch.setattr(settings, "db_path", storage / "app.db")
    monkeypatch.setattr(settings, "llm_provider", "offline")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "app_env", None)
    monkeypatch.setattr(settings, "internal_api_token", None)
    monkeypatch.setattr(settings, "log_to_file", False)
    clients: list[TestClient] = []

    def build(**overrides) -> TestClient:
        for key, value in overrides.items():
            monkeypatch.setattr(settings, key, value)
        session_store.init_db(settings.db_path)
        client = TestClient(create_app())
        client.__enter__()
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)
    for handler in logging.getLogger().handlers:  # release the rotating file on Windows
        handler.close()


def test_dp_ac3_health_reports_version_and_ready_checks_db_and_storage(make_client, monkeypatch, tmp_path):
    client = make_client(app_version="abc123")
    assert client.get("/api/v1/health").json() == {"status": "ok", "version": "abc123"}
    ready = client.get("/api/v1/ready")
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}

    not_a_dir = tmp_path / "plain_file"
    not_a_dir.write_text("x", encoding="utf-8")
    monkeypatch.setattr(settings, "storage_root", not_a_dir)
    broken = client.get("/api/v1/ready")
    assert broken.status_code == 503
    assert broken.json()["error"]["code"] == "not_ready"
    assert "storage" in broken.json()["error"]["details"]["failed"]

    monkeypatch.setattr(settings, "db_path", tmp_path / "missing_dir" / "app.db")
    broken = client.get("/api/v1/ready")
    assert broken.status_code == 503 and "database" in broken.json()["error"]["details"]["failed"]


def test_dp_ac3_ready_never_calls_the_llm(make_client, monkeypatch):
    import app.routers.plans as plans

    def boom():
        raise AssertionError("/ready must not touch the LLM")

    monkeypatch.setattr(plans, "get_llm", boom)
    assert make_client().get("/api/v1/ready").status_code == 200


def test_dp_ac8_app_refuses_to_start_when_production_is_misconfigured(make_client):
    with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
        make_client(app_env="production")


def test_dp_ac11_internal_token_closes_the_backend(make_client):
    client = make_client(internal_api_token=SECRET_TOKEN)
    for headers in ({}, {"X-Internal-Token": "wrong"}):
        response = client.get("/api/v1/config", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert SECRET_TOKEN not in response.text
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ready").status_code == 200
    assert client.get("/api/v1/config", headers={"X-Internal-Token": SECRET_TOKEN}).status_code == 200
    missing = client.get("/api/v1/sessions/nope", headers={"X-Internal-Token": SECRET_TOKEN})
    assert missing.status_code == 404  # past the gate, normal routing


def test_dp_ac12_cors_preflight_follows_the_setting(make_client):
    def allowed(client, origin):
        response = client.options("/api/v1/health", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET"})
        return response.headers.get("access-control-allow-origin") == origin

    custom = make_client(cors_origins="https://example.org")
    assert allowed(custom, "https://example.org")
    assert not allowed(custom, "http://localhost:3000")
    assert allowed(make_client(cors_origins=None), "http://localhost:3000")
    assert not allowed(make_client(cors_origins=""), "http://localhost:3000")


def test_dp_ac13_log_file_only_when_enabled(make_client):
    make_client(log_to_file=False)
    assert not (settings.storage_root / "logs" / "app.log").exists()
    make_client(log_to_file=True)
    assert (settings.storage_root / "logs" / "app.log").exists()


def test_dp_ac19_config_returns_exactly_the_public_settings(make_client):
    client = make_client(max_file_size_mb=5.0, max_rows=20_000, retention_days=7, storage_persistent=False,
                         app_env="production", internal_api_token=SECRET_TOKEN)
    body = client.get("/api/v1/config", headers={"X-Internal-Token": SECRET_TOKEN}).json()
    assert body == {"max_file_size_mb": 5.0, "max_rows": 20_000, "retention_days": 7,
                    "storage_persistent": False, "hosted": True}
    local = make_client(app_env=None, internal_api_token=None)
    assert local.get("/api/v1/config").json()["hosted"] is False


def test_dp_ac7_hosted_size_limit_returns_the_apps_413(make_client):
    client = make_client(max_file_size_mb=5.0)
    too_big = "a,b\n" + "1,2\n" * (6 * 1024 * 1024 // 4)
    response = upload_csv(client, too_big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_ap_ac14_meta_endpoints_and_token(make_client):
    client = make_client(app_version="v1", internal_api_token=SECRET_TOKEN)
    assert client.get("/api/v1/health").json()["version"] == "v1"
    assert client.get("/api/v1/ready").status_code == 200
    assert set(client.get("/api/v1/config", headers={"X-Internal-Token": SECRET_TOKEN}).json()) == {
        "max_file_size_mb", "max_rows", "retention_days", "storage_persistent", "hosted"}
    assert client.get("/api/v1/config").status_code == 401


def test_dp_ac9_secrets_never_in_logs_or_responses(make_client, caplog):
    stdout = io.StringIO()
    with caplog.at_level(logging.DEBUG), redirect_stdout(stdout):
        client = make_client(gemini_api_key=SECRET_KEY, internal_api_token=SECRET_TOKEN, app_version="v")
        client.headers.update({"X-Internal-Token": SECRET_TOKEN})
        bodies = [client.get(p).text for p in ("/api/v1/health", "/api/v1/ready", "/api/v1/config")]
        bodies.append(client.get("/api/v1/sessions/nope").text)  # an error response
        sid = upload_csv(client, "a,b\n1,\n2,x\n3,y\n4,y\n").json()["id"]
        for _ in range(50):
            if client.get(f"/api/v1/sessions/{sid}").json()["state"] == "profiled":
                break
            time.sleep(0.05)
        plan = client.post(f"/api/v1/sessions/{sid}/plan")
        bodies.append(plan.text)
        steps = [dict(s, status="approved") for s in plan.json()["steps"]]
        bodies.append(client.post(f"/api/v1/sessions/{sid}/plan/approve", json={"steps": steps}).text)
        bodies.append(client.post(f"/api/v1/sessions/{sid}/execute").text)
    logged = stdout.getvalue() + "\n".join(r.getMessage() + str(r.__dict__) for r in caplog.records)
    for secret in (SECRET_KEY, SECRET_TOKEN):
        assert secret not in logged
        assert all(secret not in body for body in bodies)
