"""Deterministic cleaning executor (Spec 05). No LLM, no network.

Applies Gate-validated steps in order with pandas, records a before/after audit
entry per step, and on full success exports cleaned_<original_name>.csv.
The original upload is never modified (FR-EX-06); on step failure the log of
completed steps is persisted and no deliverable is exported (FR-EX-05).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import pandas as pd

from ..schemas.plan import SCHEMA_VERSION
from ..storage.artifacts import cleaned_csv_path, execution_log_path, upload_path

logger = logging.getLogger("executor")

EXECUTABLE_STATUSES = {"approved", "edited"}  # FR-EX-01
_OUTLIER_FACTOR = 1.5  # same IQR method as the profiler (Spec 05 op semantics)

_CAST_TARGETS = {
    "int": "int64",
    "float": "float64",
    "str": "str",
    "bool": "bool",
    "category": "category",
}


class StepError(Exception):
    """A step cannot be applied; aborts execution (FR-EX-05)."""


def _snapshot(df: pd.DataFrame) -> dict:
    """Frame-level counts logged before/after every step (FR-EX-03)."""
    outliers = 0
    for column in df.columns:
        s = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(s):
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            low, high = q1 - _OUTLIER_FACTOR * iqr, q3 + _OUTLIER_FACTOR * iqr
            outliers += int(((s < low) | (s > high)).sum())
    return {
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
        "null_cells": int(df.isna().sum().sum()),
        "outliers": outliers,
    }


def apply_step(df: pd.DataFrame, step: dict) -> tuple[pd.DataFrame, dict]:
    """Apply one step to a copy of the frame; returns (new_df, notes).

    Raises StepError for any failure; the input df is never mutated.
    """
    op = step["op"]
    params = step.get("params", {})
    column = step.get("column")
    notes: dict = {}

    if op == "drop_duplicates":
        rows_before = len(df)
        df = df.drop_duplicates(keep="first")
        notes["rows_removed"] = rows_before - len(df)
        return df, notes

    if op == "drop_column":
        columns = list(params["columns"])
        missing = [name for name in columns if name not in df.columns]
        if missing:
            raise StepError(f"column(s) not found: {missing}")
        return df.drop(columns=columns), notes

    if op == "impute":
        s = df[column]
        nn = s.dropna()
        if nn.empty:
            raise StepError(f"column '{column}' has no non-null values to impute from")
        strategy = params["strategy"]
        if strategy == "mean":
            value = pd.to_numeric(nn, errors="coerce").mean()
        elif strategy == "median":
            value = pd.to_numeric(nn, errors="coerce").median()
        elif strategy == "mode":
            value = nn.mode().iloc[0]  # smallest mode on ties -> deterministic
        else:
            value = params["value"]
        nulls_before = int(s.isna().sum())
        df = df.copy()
        df[column] = s.fillna(value)
        notes["filled"] = nulls_before - int(df[column].isna().sum())
        return df, notes

    if op == "clip_outliers":
        s = pd.to_numeric(df[column], errors="coerce")
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if pd.isna(iqr):
            raise StepError(f"cannot compute IQR for column '{column}'")
        factor = float(params.get("factor", 1.5))
        low, high = q1 - factor * iqr, q3 + factor * iqr
        df = df.copy()
        df[column] = s.clip(low, high)
        notes["clipped"] = int(((s < low) | (s > high)).sum())
        return df, notes

    if op == "cast_type":
        target = _CAST_TARGETS[params["to"]]
        try:
            df[column].astype(target)  # dry-run before mutating (FR-EX-04)
        except (ValueError, TypeError) as exc:
            raise StepError(f"cast to '{params['to']}' would fail: {exc}") from exc
        df = df.copy()
        df[column] = df[column].astype(target)
        return df, notes

    if op == "parse_datetime":
        s = df[column]
        nulls_before = int(s.isna().sum())
        parsed = pd.to_datetime(s, errors="coerce", format=params.get("format") or "mixed")
        df = df.copy()
        df[column] = parsed
        notes["unparseable_to_null"] = int(parsed.isna().sum()) - nulls_before
        return df, notes

    if op == "standardize_text":
        s = df[column]
        if not (pd.api.types.is_string_dtype(s) or s.dtype == object):
            raise StepError(f"'{column}' is not a text column")
        out = s.astype("string")
        for text_op in params["ops"]:
            if text_op == "trim":
                out = out.str.strip()
            elif text_op == "lowercase":
                out = out.str.lower()
            elif text_op == "collapse_spaces":
                out = out.str.replace(r"\s+", " ", regex=True)
        df = df.copy()
        df[column] = out
        return df, notes

    raise StepError(f"unsupported op '{op}'")  # unreachable: the Gate rejects first


def run_execution(db_path: Path, storage_root: Path, session_id: str, steps: list[dict]) -> None:
    """Background task: apply the approved steps and export deliverables (FR-EX-01..10)."""
    from ..db import session_store

    row = session_store.get_session(db_path, session_id)
    if row is None:
        return

    started = time.perf_counter()
    upload = upload_path(storage_root, session_id)
    original_sha = hashlib.sha256(upload.read_bytes()).hexdigest()

    # A new run supersedes artifacts from any previous run
    cleaned = cleaned_csv_path(storage_root, session_id, row["original_filename"])
    log_file = execution_log_path(storage_root, session_id)
    cleaned.unlink(missing_ok=True)
    log_file.unlink(missing_ok=True)

    df = pd.read_csv(
        upload,
        sep=row["delimiter"] or ",",
        encoding=row["encoding"] or "utf-8",
        engine="python",
    )

    entries: list[dict] = []
    for index, step in enumerate(steps):
        requested_status = step.get("status", "approved")
        entry: dict = {
            "index": index,
            "op": step.get("op"),
            "column": step.get("column"),
            "params": step.get("params", {}),
            "requested_status": requested_status,
            "rationale": step.get("rationale"),
        }
        if requested_status not in EXECUTABLE_STATUSES:
            entry["status"] = requested_status  # skipped and logged as such (FR-EX-01)
            entries.append(entry)
            continue

        before = _snapshot(df)
        try:
            df, notes = apply_step(df, step)
        except StepError as exc:
            entry.update({"status": "failed", "before": before, "after": None, "error": str(exc)})
            entries.append(entry)
            _finish_failure(db_path, log_file, session_id, entries, index, step, str(exc), started)
            return
        entry.update({"status": "executed", "before": before, "after": _snapshot(df), "notes": notes})
        entries.append(entry)

    cleaned.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cleaned, index=False)  # FR-EX-07/08: names & order preserved, deterministic

    duration_ms = int((time.perf_counter() - started) * 1000)
    post_sha = hashlib.sha256(upload.read_bytes()).hexdigest()
    if post_sha != original_sha:  # FR-EX-06 guard; must be impossible
        logger.critical("original upload changed during execution", extra={"session_id": session_id})

    log = {
        "session_id": session_id,
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "duration_ms": duration_ms,
        "steps": entries,
    }
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    session_store.update_session(db_path, session_id, state="executed", error=None)
    logger.info(
        "execute.completed",
        extra={"session_id": session_id, "stage": "execute", "duration_ms": duration_ms},
    )


def _finish_failure(
    db_path: Path,
    log_file: Path,
    session_id: str,
    entries: list[dict],
    index: int,
    step: dict,
    reason: str,
    started: float,
) -> None:
    """Persist the completed-steps log; session returns to awaiting_approval with error."""
    from ..db import session_store

    duration_ms = int((time.perf_counter() - started) * 1000)
    log = {
        "session_id": session_id,
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "failed_step": index,
        "error": reason,
        "duration_ms": duration_ms,
        "steps": entries,
    }
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    message = f"step {index} ({step.get('op')}) failed: {reason}"
    # Last good state + recorded error: user can edit the plan and re-execute
    session_store.update_session(db_path, session_id, state="awaiting_approval", error=message)
    logger.error(
        "execute.failed",
        extra={"session_id": session_id, "stage": "execute", "duration_ms": duration_ms, "error": reason},
    )
