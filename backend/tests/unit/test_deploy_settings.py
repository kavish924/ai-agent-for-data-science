"""Spec 11 (deployment): settings resolved from the environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings, check_production, production_problems

ROOT = Path(__file__).resolve().parents[3]


def _settings(**overrides) -> Settings:
    base: dict = {"_env_file": None, "app_env": None, "web_concurrency": None, "internal_api_token": None,
                  "llm_provider": "offline", "gemini_api_key": None, "gemini_backend": "aistudio",
                  "google_cloud_project": None, "app_version": None, "render_git_commit": None}
    base.update(overrides)
    return Settings(**base)


def test_dp_ac4_production_refuses_more_than_one_worker():
    bad = _settings(app_env="production", internal_api_token="t", web_concurrency=2)
    assert any("FR-DP-06" in p for p in production_problems(bad))
    with pytest.raises(RuntimeError, match="FR-DP-06"):
        check_production(bad)
    check_production(_settings(app_env="production", internal_api_token="t", web_concurrency=1))
    check_production(_settings(web_concurrency=2))  # development: not checked


def test_dp_ac8_production_requires_token_and_llm_credentials():
    with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
        check_production(_settings(app_env="production"))
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        check_production(_settings(app_env="production", internal_api_token="t", llm_provider="gemini"))
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        check_production(_settings(app_env="production", internal_api_token="t", llm_provider="gemini",
                                   gemini_backend="vertex"))
    check_production(_settings(app_env="production", internal_api_token="t", llm_provider="gemini",
                               gemini_api_key="k"))
    check_production(_settings(app_env="production", internal_api_token="t"))  # offline needs no key
    check_production(_settings())  # development: nothing required


def test_dp_ac9_gemini_key_is_read_from_a_file(tmp_path):
    key_file = tmp_path / "gemini_key"
    key_file.write_text("  secret-from-file\n", encoding="utf-8")
    assert _settings(gemini_api_key_file=key_file).gemini_api_key == "secret-from-file"
    assert _settings(gemini_api_key="direct", gemini_api_key_file=key_file).gemini_api_key == "direct"


def test_dp_ac12_cors_origins_from_the_environment():
    assert _settings(cors_origins="https://example.org").cors_origin_list == ["https://example.org"]
    assert _settings(cors_origins="https://a.org, https://b.org").cors_origin_list == ["https://a.org", "https://b.org"]
    assert _settings(cors_origins=None).cors_origin_list == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert _settings(cors_origins="").cors_origin_list == []


def test_dp_ac18_version_resolution():
    assert _settings(render_git_commit="def456").version == "def456"
    assert _settings(app_version="abc123", render_git_commit="def456").version == "abc123"
    assert _settings().version == "dev"


def test_dp_ac16_render_blueprint_matches_the_spec():
    yaml = pytest.importorskip("yaml")
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {s["name"]: s for s in blueprint["services"]}
    frontend, backend = services["ai-ds-agent-frontend"], services["ai-ds-agent-backend"]
    for service in (frontend, backend):
        assert service["type"] == "web" and service["runtime"] == "docker"
        assert service["plan"] == "free" and service["region"] == "singapore"
    assert frontend["healthCheckPath"] == "/healthz"
    assert backend["healthCheckPath"] == "/api/v1/ready"
    assert backend.get("numInstances", 1) == 1 and "scaling" not in backend

    def env(service):
        return {e["key"]: e for e in service.get("envVars", []) if "key" in e}

    benv = env(backend)
    expected = {"APP_ENV": "production", "LLM_PROVIDER": "gemini", "GEMINI_BACKEND": "aistudio",
                "STORAGE_PERSISTENT": "false", "LOG_TO_FILE": "false", "CORS_ORIGINS": "",
                "DB_PATH": "/data/app.db", "STORAGE_ROOT": "/data", "MAX_FILE_SIZE_MB": "5",
                "MAX_ROWS": "20000", "MODEL_MAX_ROWS": "10000"}
    for key, value in expected.items():
        assert str(benv[key]["value"]) == value, key
    assert benv["GEMINI_API_KEY"] == {"key": "GEMINI_API_KEY", "sync": False}
    fenv = env(frontend)
    for key in ("ACCESS_PASSWORD", "BACKEND_URL"):
        assert fenv[key] == {"key": key, "sync": False}
    assert fenv["APP_ENV"]["value"] == "production"

    groups = {g["name"]: g for g in blueprint["envVarGroups"]}
    (group_name,) = groups
    token = {e["key"]: e for e in groups[group_name]["envVars"]}["INTERNAL_API_TOKEN"]
    assert token == {"key": "INTERNAL_API_TOKEN", "generateValue": True}
    for service in (frontend, backend):
        assert {"fromGroup": group_name} in service["envVars"]
    secrets = {"GEMINI_API_KEY", "ACCESS_PASSWORD", "INTERNAL_API_TOKEN", "BACKEND_URL"}
    for service in (frontend, backend):
        for key, entry in env(service).items():
            if key in secrets:
                assert "value" not in entry, f"{key} must not hold a value in render.yaml"
