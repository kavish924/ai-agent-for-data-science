"""Integration tests for the sessions API (Specs 01, 02, 09) - no LLM needed."""

from __future__ import annotations

from tests.conftest import SAMPLE_CSV, upload_csv


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_and_profile_happy_path(client):
    response = upload_csv(client, SAMPLE_CSV)
    assert response.status_code == 201
    body = response.json()
    session_id = body["id"]
    assert body["state"] == "uploaded"
    assert body["n_rows"] == 3
    assert body["n_columns"] == 3
    assert body["retention_expires_at"]

    # TestClient runs background tasks before returning, so profiling is done.
    profile = client.get(f"/api/v1/sessions/{session_id}/profile")
    assert profile.status_code == 200
    data = profile.json()
    assert data["session_id"] == session_id
    assert data["n_rows"] == 3
    types = {c["name"]: c["type"] for c in data["columns"]}
    assert types["a"] == "numeric"  # 1,2,3
    assert types["b"] == "id_like"  # x,y,z near-unique
    assert types["c"] == "boolean"  # true/false

    status = client.get(f"/api/v1/sessions/{session_id}")
    assert status.status_code == 200
    assert status.json()["state"] == "profiled"


def test_upload_original_is_immutable(client, tmp_path):
    from app.config import settings
    from app.storage.artifacts import upload_path

    response = upload_csv(client, SAMPLE_CSV, name="orig.csv")
    session_id = response.json()["id"]
    stored = upload_path(settings.storage_root, session_id).read_bytes()
    assert stored == SAMPLE_CSV.encode("utf-8")


def test_unknown_session_404_with_envelope(client):
    response = client.get("/api/v1/sessions/doesnotexist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "session_not_found"
    assert "message" in error


def test_profile_pending_409(client):
    from app.config import settings
    from app.db import session_store

    session_id = upload_csv(client, SAMPLE_CSV).json()["id"]
    session_store.update_session(settings.db_path, session_id, state="uploaded")
    response = client.get(f"/api/v1/sessions/{session_id}/profile")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "profile_pending"


def test_file_too_large_413(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_file_size_mb", 0.00001)
    response = upload_csv(client, SAMPLE_CSV)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_too_many_rows_413(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_rows", 2)
    response = upload_csv(client, SAMPLE_CSV)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_many_rows"


def test_non_csv_rejected_415(client):
    response = client.post(
        "/api/v1/sessions",
        files={"file": ("junk.bin", b"\x00\x01\x02\x03binaryjunk", "application/octet-stream")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "not_a_csv"


def test_empty_file_422(client):
    response = client.post(
        "/api/v1/sessions", files={"file": ("empty.csv", b"", "text/csv")}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_file"


def test_missing_file_422(client):
    response = client.post("/api/v1/sessions")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- M0 (Spec 01 FR-UP-11/12) -------------------------------------------------

def test_up_ac7_oversized_upload_writes_nothing(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_file_size_mb", 0.00001)
    response = upload_csv(client, SAMPLE_CSV * 10)
    assert response.status_code == 413
    sessions_dir = settings.storage_root / "sessions"
    assert not sessions_dir.exists() or not any(sessions_dir.iterdir())


def test_up_ac8_profiling_retry(client, monkeypatch):
    from app.config import settings
    from app.db import session_store
    from app.storage.artifacts import profile_path

    session_id = upload_csv(client, SAMPLE_CSV).json()["id"]
    profile_path(settings.storage_root, session_id).unlink()
    session_store.update_session(
        settings.db_path, session_id, state="uploaded", error="boom", failed_stage="profile"
    )
    response = client.post(f"/api/v1/sessions/{session_id}/profile")
    assert response.status_code == 202
    status = client.get(f"/api/v1/sessions/{session_id}").json()
    assert status["state"] == "profiled"
    assert status["error"] is None and status["failed_stage"] is None
    # any other state -> 409
    assert client.post(f"/api/v1/sessions/{session_id}/profile").status_code == 409
