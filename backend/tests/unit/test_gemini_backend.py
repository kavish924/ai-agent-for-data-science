"""Gemini backend selection: AI Studio key or Vertex AI (Spec 03 FR-PL-19) - SDK mocked."""

from __future__ import annotations

from typing import Any

import pytest

import app.llm.gemini as gemini
from app.config import settings
from app.routers.plans import get_llm


@pytest.fixture()
def sdk_calls(monkeypatch):
    """Record how `genai.Client` is built; no network, no credentials."""
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(gemini.genai, "Client", FakeClient)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    return calls


def test_pl_ac14_vertex_backend_uses_project_and_no_key(sdk_calls, monkeypatch):
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "google_cloud_project", "p")
    monkeypatch.setattr(settings, "google_cloud_location", "global")
    monkeypatch.setattr(settings, "gemini_api_key", None)

    llm = get_llm()

    assert isinstance(llm, gemini.GeminiClient)
    assert llm.model == settings.gemini_model
    (kwargs,) = sdk_calls
    assert kwargs["vertexai"] is True
    assert kwargs["project"] == "p"
    assert kwargs["location"] == "global"
    assert kwargs.get("api_key") is None


def test_pl_ac14_vertex_backend_honours_location(sdk_calls, monkeypatch):
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "google_cloud_project", "p")
    monkeypatch.setattr(settings, "google_cloud_location", "us-central1")

    get_llm()

    assert sdk_calls[0]["location"] == "us-central1"


def test_pl_ac14_default_backend_uses_api_key_not_vertex(sdk_calls, monkeypatch):
    monkeypatch.setattr(settings, "gemini_backend", "aistudio")
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "google_cloud_project", "p")  # ignored by this backend

    assert isinstance(get_llm(), gemini.GeminiClient)
    (kwargs,) = sdk_calls
    assert kwargs["api_key"] == "k"
    assert not kwargs.get("vertexai")
    assert "project" not in kwargs


def test_pl_ac15_vertex_without_project_is_not_configured(sdk_calls, monkeypatch):
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "google_cloud_project", None)
    monkeypatch.setattr(settings, "gemini_api_key", "k")  # a key does not stand in for a project

    assert settings.gemini_configured is False
    assert get_llm() is None
    assert sdk_calls == []
