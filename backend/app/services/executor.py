"""Deterministic cleaning executor (Spec 05). No LLM, no network.

Applies the frozen approved plan in order with pandas, records a before/after audit
entry per step, and on full success exports cleaned_<original_name>.csv.
The original upload is never modified (FR-EX-06). On any failure - a step error or
anything unexpected - the log of completed steps is persisted, no deliverable is
exported, and the session returns to review (FR-EX-05, FR-EX-11).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

from ..schemas.plan import EXECUTABLE_STATUSES, SCHEMA_VERSION
from ..storage.artifacts import cleaned_csv_path, execution_log_path, upload_path
from .numeric import parse_numeric

logger = logging.getLogger("executor")

_OUTLIER_FACTOR = 1.5  # same IQR method as the profiler (Spec 05 op semantics)
_TRUE_VALUES = {"true", "yes", "y", "1"}
_FALSE_VALUES = {"false", "no", "n", "0"}


class StepError(Exception):
    """A step cannot be applied; aborts execution (FR-EX-05)."""


def _snapshot(df: pd.DataFrame) -> dict:
    """Frame-level counts logged before/after every step (FR-EX-03)."""
    outliers = 0
    for column in df.columns:
        s = parse_numeric(df[column])[0].dropna()
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


def _merge_numeric(original: pd.Series, values: pd.Series, unparseable: pd.Series) -> pd.Series:
    """Numeric result where every value parsed; otherwise keep unparseable values as-is."""
    if not unparseable.any():
        return values
    merged = original.astype(object).copy()
    parsed = values.notna()
    merged[parsed] = values[parsed]
    return merged


def _cast(s: pd.Series, to: str) -> pd.Series:
    """Strict cast semantics (FR-EX-12). Raises StepError instead of guessing."""
    if to in ("int", "float"):
        values, unparseable = parse_numeric(s)
        if unparseable.any():
            raise StepError(
                f"cast to '{to}' would fail: {int(unparseable.sum())} value(s) are not numeric"
            )
        if to == "float":
            return values
        present = values.dropna()
        if not (present == present.round()).all():
            raise StepError("cast to 'int' would fail: column has non-integral values")
        return values.astype("Int64")
    if to == "bool":
        if pd.api.types.is_bool_dtype(s):
            return s.astype("boolean")
        keys = s.astype("string").str.strip().str.lower()
        if pd.api.types.is_numeric_dtype(s):
            numbers = parse_numeric(s)[0]
            keys = numbers.map(lambda v: None if pd.isna(v) else (str(int(v)) if v in (0, 1) else "?"))
        known = keys.isna() | keys.isin(_TRUE_VALUES | _FALSE_VALUES)
        if not known.all():
            raise StepError(
                f"cast to 'bool' would fail: {int((~known).sum())} value(s) are not boolean-like"
            )
        result = pd.Series(pd.NA, index=s.index, dtype="boolean")
        result[keys.isin(_TRUE_VALUES).fillna(False).astype(bool)] = True
        result[keys.isin(_FALSE_VALUES).fillna(False).astype(bool)] = False
        return result
    if to == "str":
        return s.astype("string")
    if to == "category":
        return s.astype("category")
    raise StepError(f"unsupported cast target '{to}'")


def apply_step(df: pd.DataFrame, step: dict) -> tuple[pd.DataFrame, dict]:
    """Apply one step to a copy of the frame; returns (new_df, notes).

    Raises StepError for any expected failure; the input df is never mutated.
    """
    op = step["op"]
    params = step.get("params") or {}
    column = step.get("column")
    notes: dict[str, Any] = {}

    if column is not None and column not in df.columns:
        raise StepError(f"column '{column}' not found")

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
        nulls_before = int(s.isna().sum())
        strategy = params["strategy"]
        if strategy in ("mean", "median"):
            values, unparseable = parse_numeric(s)
            present = values.dropna()
            if present.empty:
                raise StepError(f"column '{column}' has no non-null values to impute from")
            value: Any = present.mean() if strategy == "mean" else present.median()
            filled = _merge_numeric(s, values, unparseable)
            filled = filled.where(s.notna(), value)
            notes["unparseable_kept"] = int(unparseable.sum())
        else:
            present = s.dropna()
            if present.empty:
                raise StepError(f"column '{column}' has no non-null values to impute from")
            value = present.mode().iloc[0] if strategy == "mode" else params["value"]
            filled = s.fillna(value)  # mode: smallest on ties -> deterministic
        df = df.copy()
        df[column] = filled
        notes["filled"] = nulls_before - int(df[column].isna().sum())
        return df, notes

    if op == "clip_outliers":
        s = df[column]
        values, unparseable = parse_numeric(s)
        present = values.dropna()
        if present.empty:
            raise StepError(f"cannot compute IQR for column '{column}'")
        q1, q3 = present.quantile(0.25), present.quantile(0.75)
        factor = float(params.get("factor", 1.5))
        low = float(q1 - factor * (q3 - q1))
        high = float(q3 + factor * (q3 - q1))
        clipped = values.clip(low, high)
        df = df.copy()
        df[column] = _merge_numeric(s, clipped, unparseable)
        notes["clipped"] = int(((values < low) | (values > high)).sum())
        notes["unparseable_kept"] = int(unparseable.sum())
        return df, notes

    if op == "cast_type":
        converted = _cast(df[column], params["to"])  # computed on the side: dry run
        df = df.copy()
        df[column] = converted
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


def run_execution(
    db_path: Path,
    storage_root: Path,
    session_id: str,
    steps: list[dict],
    plan_version: int | None = None,
) -> None:
    """Background task: apply the approved steps and export deliverables (FR-EX-01..13)."""
    from ..db import session_store

    row = session_store.get_session(db_path, session_id)
    if row is None:
        return

    started = time.perf_counter()
    log_file = execution_log_path(storage_root, session_id)
    entries: list[dict] = []
    context: dict[str, Any] = {"index": None, "op": None}
    try:
        upload = upload_path(storage_root, session_id)
        original_sha = hashlib.sha256(upload.read_bytes()).hexdigest()

        # A new run supersedes artifacts from any previous run
        cleaned = cleaned_csv_path(storage_root, session_id, row["original_filename"])
        cleaned.unlink(missing_ok=True)
        log_file.unlink(missing_ok=True)

        df = pd.read_csv(
            upload, sep=row["delimiter"] or ",", encoding=row["encoding"] or "utf-8", engine="python"
        )

        for index, step in enumerate(steps):
            context = {"index": index, "op": step.get("op")}
            status = step.get("status", "proposed")
            entry: dict = {
                "index": index,
                "step_id": step.get("step_id"),
                "op": step.get("op"),
                "column": step.get("column"),
                "params": step.get("params", {}),
                "requested_status": status,
                "rationale": step.get("rationale"),
            }
            if status not in EXECUTABLE_STATUSES:
                entry["status"] = status  # skipped and logged as such (FR-EX-01)
                entries.append(entry)
                continue

            before = _snapshot(df)
            try:
                df, notes = apply_step(df, step)
            except Exception as exc:  # StepError or anything unexpected (FR-EX-11)
                entry.update({"status": "failed", "before": before, "after": None, "error": str(exc)})
                entries.append(entry)
                _finish_failure(db_path, log_file, session_id, entries, plan_version,
                                f"step {index} ({step.get('op')}) failed: {exc}", started)
                return
            after = _snapshot(df)
            entry.update({"status": "executed", "before": before, "after": after, "notes": notes})
            entries.append(entry)
            logger.info(
                "execute.step",
                extra={"session_id": session_id, "stage": "execute",
                       "step_id": step.get("step_id"), "op": step.get("op")},
            )

        context = {"index": None, "op": "export"}
        cleaned.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cleaned, index=False)  # FR-EX-07/08: names & order preserved, deterministic

        if hashlib.sha256(upload.read_bytes()).hexdigest() != original_sha:  # FR-EX-06 guard
            logger.critical("original upload changed during execution", extra={"session_id": session_id})
    except Exception as exc:  # FR-EX-11: never leave the session in `executing`
        where = f"step {context['index']}" if context["index"] is not None else "execution"
        _finish_failure(db_path, log_file, session_id, entries, plan_version,
                        f"{where} failed: {exc}", started)
        return

    duration_ms = int((time.perf_counter() - started) * 1000)
    log = {
        "session_id": session_id,
        "schema_version": SCHEMA_VERSION,
        "plan_version": plan_version,
        "status": "completed",
        "duration_ms": duration_ms,
        "steps": entries,
    }
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    session_store.update_session(db_path, session_id, state="executed", error=None, failed_stage=None)
    logger.info(
        "execute.completed",
        extra={"session_id": session_id, "stage": "execute", "duration_ms": duration_ms},
    )


def _finish_failure(
    db_path: Path,
    log_file: Path,
    session_id: str,
    entries: list[dict],
    plan_version: int | None,
    message: str,
    started: float,
) -> None:
    """Persist the completed-steps log; session returns to review with the error (FR-EX-05)."""
    from ..db import session_store

    duration_ms = int((time.perf_counter() - started) * 1000)
    failed = [entry["index"] for entry in entries if entry.get("status") == "failed"]
    log = {
        "session_id": session_id,
        "schema_version": SCHEMA_VERSION,
        "plan_version": plan_version,
        "status": "failed",
        "failed_step": failed[0] if failed else None,
        "error": message,
        "duration_ms": duration_ms,
        "steps": entries,
    }
    try:
        log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    finally:
        session_store.update_session(
            db_path, session_id, state="awaiting_approval", error=message, failed_stage="execute"
        )
    logger.error(
        "execute.failed",
        extra={"session_id": session_id, "stage": "execute", "duration_ms": duration_ms, "error": message},
    )
