"""Shared test fixtures: isolated storage/DB per test, TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import session_store
from app.main import create_app

SAMPLE_CSV = "a,b,c\n1,x,true\n2,y,false\n3,z,true\n"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_root", storage)
    monkeypatch.setattr(settings, "db_path", storage / "app.db")
    monkeypatch.setattr(settings, "gemini_api_key", None)  # tests never reach a real LLM
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    session_store.init_db(settings.db_path)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def upload_csv(client: TestClient, content: str, name: str = "test.csv"):
    return client.post(
        "/api/v1/sessions",
        files={"file": (name, content.encode("utf-8"), "text/csv")},
    )


@pytest.fixture(autouse=True)
def _no_llm_backoff(monkeypatch):
    """Spec 03 FR-PL-18: transport retries back off; tests never really sleep."""
    import app.llm.client as llm_client

    if hasattr(llm_client, "_sleep"):
        monkeypatch.setattr(llm_client, "_sleep", lambda seconds: None)
