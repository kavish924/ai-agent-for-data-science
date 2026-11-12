"""Application configuration (docs/tech-stack.md §4, Spec 01/03/06/10 defaults)."""

from pathlib import Path
from typing import Literal

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
    gemini_model: str = "gemini-2.5-flash"
    llm_timeout_s: float = 60.0  # per LLM call


settings = Settings()
