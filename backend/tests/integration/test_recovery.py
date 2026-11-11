"""Startup recovery + retention sweep (Spec 10 NFR-07/08)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.config import settings
from app.db import session_store
from app.main import create_app
from app.services import retention
from app.storage.artifacts import profile_path, session_dir
from tests.conftest import SAMPLE_CSV, upload_csv


def test_nfr_ac7_inflight_sessions_recovered_on_startup(client):
    executing = upload_csv(client, SAMPLE_CSV).json()["id"]
    session_store.update_session(settings.db_path, executing, state="executing")
    stuck = upload_csv(client, SAMPLE_CSV).json()["id"]
    profile_path(settings.storage_root, stuck).unlink()
    session_store.update_session(settings.db_path, stuck, state="uploaded")

    with TestClient(create_app()) as restarted:
        first = restarted.get(f"/api/v1/sessions/{executing}").json()
        second = restarted.get(f"/api/v1/sessions/{stuck}").json()

    assert first["state"] == "awaiting_approval"
    assert first["failed_stage"] == "execute"
    assert first["error"]
    assert second["state"] == "uploaded"
    assert second["failed_stage"] == "profile"
    assert second["error"]


def test_nfr_ac3_retention_sweep_deletes_expired_sessions(client):
    expired = upload_csv(client, SAMPLE_CSV).json()["id"]
    kept = upload_csv(client, SAMPLE_CSV).json()["id"]
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat(timespec="seconds")
    session_store.update_session(settings.db_path, expired, retention_expires_at=past)
    expired_dir = session_dir(settings.storage_root, expired)

    deleted, freed = retention.sweep(settings.db_path, settings.storage_root)

    assert deleted == 1
    assert freed > 0
    assert session_store.get_session(settings.db_path, expired) is None
    assert not expired_dir.exists()
    assert session_store.get_session(settings.db_path, kept) is not None
