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
    session_store.init_db(settings.db_path)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def upload_csv(client: TestClient, content: str, name: str = "test.csv"):
    return client.post(
        "/api/v1/sessions",
        files={"file": (name, content.encode("utf-8"), "text/csv")},
    )
