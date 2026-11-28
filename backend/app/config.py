"""Application configuration (docs/tech-stack.md §4, Spec 01/03/06/10/11 defaults)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: backend/app/config.py -> parents[2]
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    api_v1_prefix: str = "/api/v1"  # Spec 09 (resolved open question)

    # PRD §6.1 upload limits (Spec 01)
    max_file_size_mb: float = 25.0
    max_rows: int = 100_000

    # PRD §6.6 chart cap (Spec 06, used from M4)
    max_charts: int = 12

    # Spec 07 FR-ML-13: larger datasets are down-sampled (seeded) before training
    model_max_rows: int = 50_000

    # PRD §6.3 bounded LLM retries (Spec 03, used from M3)
    plan_max_retries: int = 3
    narration_max_retries: int = 2  # Spec 08 FR-RP-11

    # PRD §7 privacy: upload retention window (Spec 10)
    retention_days: int = 7
    retention_sweep_minutes: int = 60  # Spec 10 NFR-08

    # Storage (design D5: SQLite + filesystem behind thin interfaces)
    db_path: Path = ROOT_DIR / "storage" / "app.db"
    storage_root: Path = ROOT_DIR / "storage"

    # Observability (Spec 10)
    log_level: str = "INFO"

    # Reproducibility (PRD §7)
    random_seed: int = 42

    # LLM: Google Gemini, used from M3 (Spec 03)
    llm_provider: Literal["gemini", "offline"] = "gemini"  # Spec 03 FR-PL-17
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"  # 2.5 retired for new keys (404, 2026-11)
    llm_timeout_s: float = 60.0  # per LLM call
    llm_retry_backoff_s: float = 2.0  # Spec 03 FR-PL-18: wait after a transport failure, doubling
    # Spec 03 FR-PL-19: AI Studio (API key) or Vertex AI (Google Cloud project + ADC)
    gemini_backend: Literal["aistudio", "vertex"] = "aistudio"
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"  # newest models are often served only from global

    # Deployment (Spec 11)
    app_env: str | None = None  # "production" turns on the checks of FR-DP-06/11
    web_concurrency: int | None = None  # FR-DP-06: must stay 1 in production
    internal_api_token: str | None = None  # FR-DP-14: required header when set
    cors_origins: str | None = None  # FR-DP-16: comma-separated; unset = localhost dev origins
    log_to_file: bool = True  # FR-DP-18: the images set it to false (stdout only)
    storage_persistent: bool = True  # FR-DP-07: false on Render's free tier (no disk)
    app_version: str | None = None  # FR-DP-04
    render_git_commit: str | None = None  # FR-DP-04: set by Render at runtime
    gemini_api_key_file: Path | None = None  # FR-DP-12: read-only secret file

    @model_validator(mode="after")
    def _read_key_file(self) -> Settings:
        if not self.gemini_api_key and self.gemini_api_key_file is not None:
            self.gemini_api_key = self.gemini_api_key_file.read_text(encoding="utf-8").strip() or None
        return self

    @property
    def gemini_configured(self) -> bool:
        """The chosen Gemini backend has what it needs (Spec 03 FR-PL-19)."""
        if self.gemini_backend == "vertex":
            return bool(self.google_cloud_project)
        return bool(self.gemini_api_key)

    @property
    def is_production(self) -> bool:
        return (self.app_env or "").strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        """FR-DP-16: unset keeps the local dev origins; an empty string allows none."""
        if self.cors_origins is None:
            return list(_DEV_ORIGINS)
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def version(self) -> str:
        """FR-DP-04: APP_VERSION, else Render's commit, else "dev"."""
        return self.app_version or self.render_git_commit or "dev"


_DEV_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def production_problems(s: Settings) -> list[str]:
    """Spec 11 FR-DP-06/11: what stops a production start. Empty outside production."""
    if not s.is_production:
        return []
    problems = []
    if (s.web_concurrency or 1) > 1:
        problems.append(
            f"WEB_CONCURRENCY={s.web_concurrency}: the backend must run one worker (Spec 11 FR-DP-06)"
        )
    if not s.internal_api_token:
        problems.append("INTERNAL_API_TOKEN is not set (Spec 11 FR-DP-11/14)")
    if s.llm_provider == "gemini" and not s.gemini_configured:
        missing = "GOOGLE_CLOUD_PROJECT" if s.gemini_backend == "vertex" else "GEMINI_API_KEY"
        problems.append(f"{missing} is not set for LLM_PROVIDER=gemini (Spec 11 FR-DP-11)")
    return problems


def check_production(s: Settings) -> None:
    """Raise with every problem named, so a misconfigured deploy never starts (FR-DP-11)."""
    problems = production_problems(s)
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))


settings = Settings()
