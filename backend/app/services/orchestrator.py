"""Post-execution pipeline steps (Spec 06 FR-CH-10/11).

Runs inside the execution job after the cleaned CSV is written and before the session
becomes `executed`. Every step is isolated: a failure here is recorded in its artifact
and logged, but never fails the run that already produced the deliverable.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pandas as pd

from ..config import settings
from ..storage.artifacts import (
    after_profile_path,
    charts_dir,
    charts_manifest_path,
    profile_path,
)
from . import charts
from .profiler import profile_dataframe

logger = logging.getLogger("orchestrator")

# Ops whose execution changes a column's values (they get a "before" overlay, FR-CH-09)
_VALUE_CHANGING_OPS = {"impute", "clip_outliers", "cast_type", "parse_datetime", "standardize_text"}


def changed_columns(log_entries: list[dict]) -> set[str]:
    return {
        entry["column"]
        for entry in log_entries
        if entry.get("status") == "executed"
        and entry.get("op") in _VALUE_CHANGING_OPS
        and entry.get("column")
    }


def after_execution(
    storage_root: Path,
    session_id: str,
    *,
    cleaned_csv: Path,
    original: pd.DataFrame,
    log_entries: list[dict],
) -> None:
    """Re-profile the deliverable, then render charts. Never raises."""
    after: dict | None = None
    try:
        cleaned = pd.read_csv(cleaned_csv)  # exactly what the user downloads
        after = profile_dataframe(session_id, cleaned)
        after_profile_path(storage_root, session_id).write_text(
            json.dumps(after, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    except Exception as exc:
        logger.error("profile.after.failed", extra={"session_id": session_id, "stage": "charts",
                                                    "error": str(exc)})
        _write_manifest(storage_root, session_id, _failed(f"re-profiling failed: {exc}"))
        return

    started = time.perf_counter()
    try:
        original_profile = json.loads(profile_path(storage_root, session_id).read_text(encoding="utf-8"))
        manifest = charts.generate_charts(
            cleaned,
            after_profile=after,
            original_profile=original_profile,
            out_dir=charts_dir(storage_root, session_id),
            max_charts=settings.max_charts,
            before=original,
            changed_columns=changed_columns(log_entries),
        )
    except Exception as exc:  # FR-CH-11: isolated
        manifest = _failed(f"chart rendering failed: {exc}")
        logger.error("charts.failed", extra={"session_id": session_id, "stage": "charts",
                                             "error": str(exc)})
    else:
        logger.info("charts.generated", extra={
            "session_id": session_id, "stage": "charts",
            "duration_ms": int((time.perf_counter() - started) * 1000),
        })
    _write_manifest(storage_root, session_id, manifest)


def _failed(reason: str) -> dict:
    return {"status": "failed", "max_charts": settings.max_charts, "duration_ms": 0,
            "charts": [], "skipped": [], "error": reason}


def _write_manifest(storage_root: Path, session_id: str, manifest: dict) -> None:
    charts_manifest_path(storage_root, session_id).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
