"""Deterministic data profiler (Spec 02). No LLM, no network (FR-PR context).

Column type inference follows Spec 02's priority order; thresholds are recorded
inside the profile's `inference` block for auditability.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import pandas as pd

from .numeric import parse_numeric

logger = logging.getLogger("profiler")

# Inference thresholds (recorded in every profile via INFERENCE_META)
NUMERIC_PARSE_RATIO = 0.90
DATETIME_PARSE_RATIO = 0.90
ID_LIKE_UNIQUE_RATIO = 0.95
CATEGORICAL_MAX_UNIQUE = 50
CATEGORICAL_MAX_RATIO = 0.05
TOP_K = 10
OUTLIER_FACTOR = 1.5
BOOL_LIKE = {"true", "false", "yes", "no", "y", "n", "0", "1"}
ID_MONOTONIC_MIN_ROWS = 20
_CAMEL_ID = re.compile(r"([a-z]Id|ID)$")
LLM_TOP_K = 10
LLM_VALUE_MAX_CHARS = 40

INFERENCE_META = {
    "numeric_parse_ratio": NUMERIC_PARSE_RATIO,
    "datetime_parse_ratio": DATETIME_PARSE_RATIO,
    "id_like_unique_ratio": ID_LIKE_UNIQUE_RATIO,
    "categorical_max_unique": CATEGORICAL_MAX_UNIQUE,
    "categorical_max_ratio": CATEGORICAL_MAX_RATIO,
    "top_k": TOP_K,
    "outlier_method": {"name": "iqr", "factor": OUTLIER_FACTOR},
    "boolean_like_values": sorted(BOOL_LIKE),
    "id_like_integer_rule": {"monotonic_min_rows": ID_MONOTONIC_MIN_ROWS, "name_hint": True},
}


def _has_id_name(name: object) -> bool:
    text = str(name)
    lowered = text.lower()
    if lowered == "id" or lowered.endswith(("_id", "-id", " id")):
        return True
    if lowered.startswith(("id_", "id-", "id ")):
        return True
    return bool(_CAMEL_ID.search(text))  # camelCase only: "PassengerId", "customerID" - not "paid"


def _is_integer_id(name: object, nn: pd.Series) -> bool:
    """FR-PR-11: unique integers that are monotonic (enough rows) or identifier-named."""
    if pd.api.types.is_bool_dtype(nn):
        return False
    values, unparseable = parse_numeric(nn)
    if unparseable.any() or values.isna().any() or len(values) < 2:
        return False
    if not (values == values.round()).all() or values.nunique() != len(values):
        return False
    if _has_id_name(name):
        return True
    monotonic = values.is_monotonic_increasing or values.is_monotonic_decreasing
    return len(values) >= ID_MONOTONIC_MIN_ROWS and monotonic


def infer_column_type(s: pd.Series) -> tuple[str, list[str]]:
    """Assign exactly one type per column (FR-PR-01), in Spec 02 priority order."""
    flags: list[str] = []
    nn = s.dropna()
    if nn.empty:
        return "text", ["all_empty"]

    values = nn.unique()
    lowered = {str(v).strip().lower() for v in values}

    # 1. boolean
    if len(values) <= 2 and lowered <= BOOL_LIKE:
        return "boolean", flags
    # flag before type rules that might also apply
    if len(values) == 1:
        flags.append("single_value")
    # 2. datetime (string-ish columns only; numeric epochs are not dates for v1)
    #    Note: pandas >= 3 stores CSV text as StringDtype, not object dtype.
    if s.dtype == object or pd.api.types.is_string_dtype(s):
        parsed = pd.to_datetime(nn, errors="coerce", format="mixed")
        if parsed.notna().any() and parsed.notna().mean() >= DATETIME_PARSE_RATIO:
            return "datetime", flags
    # 3. integer identifiers (FR-PR-11) - before numeric
    if _is_integer_id(s.name, nn):
        return "id_like", flags
    # 4. numeric (shared parser, FR-PR-10)
    if pd.api.types.is_numeric_dtype(s):
        return "numeric", flags
    _, unparseable = parse_numeric(nn)
    if 1.0 - unparseable.mean() >= NUMERIC_PARSE_RATIO:
        return "numeric", flags
    # 5. id_like (strings)
    if nn.nunique() / len(nn) >= ID_LIKE_UNIQUE_RATIO:
        return "id_like", flags
    # 6. categorical
    nunique = int(nn.nunique())
    if nunique <= CATEGORICAL_MAX_UNIQUE or (
        len(s) > 0 and nunique <= CATEGORICAL_MAX_RATIO * len(s)
    ):
        return "categorical", flags
    # 7. text
    return "text", flags


def _round4(x: float) -> float:
    return round(x, 4) if x == x else 0.0  # NaN-safe


def _profile_column(name: str, s: pd.Series) -> dict:
    col_type, flags = infer_column_type(s)
    nn = s.dropna()
    nulls = int(s.isna().sum())
    profile: dict = {
        "name": str(name),
        "type": col_type,
        "nulls": nulls,
        "null_pct": round(100.0 * nulls / len(s), 1) if len(s) else 0.0,
        "unique": int(nn.nunique()),
        "top_values": [],
        "flags": flags,
    }
    if col_type in ("categorical", "text", "id_like", "boolean"):
        value_counts = nn.astype(str).value_counts().head(TOP_K)
        profile["top_values"] = [
            {"value": value, "count": int(count)} for value, count in value_counts.items()
        ]
    if col_type == "numeric":
        as_num = parse_numeric(nn)[0].dropna()
        if not as_num.empty:
            q1, q3 = as_num.quantile(0.25), as_num.quantile(0.75)
            iqr = q3 - q1
            low, high = q1 - OUTLIER_FACTOR * iqr, q3 + OUTLIER_FACTOR * iqr
            profile["outliers_iqr"] = int(((as_num < low) | (as_num > high)).sum())
            profile["stats"] = {
                "min": _round4(float(as_num.min())),
                "max": _round4(float(as_num.max())),
                "mean": _round4(float(as_num.mean())),
                "std": _round4(float(as_num.std())),
            }
    return profile


def profile_dataframe(session_id: str, df: pd.DataFrame) -> dict:
    """Build the full profile dict (FR-PR-02..07, FR-PR-09)."""
    columns = [_profile_column(name, df[name]) for name in df.columns]
    issues = {
        "columns_with_nulls": [c["name"] for c in columns if c["nulls"] > 0],
        "columns_with_outliers": [
            c["name"] for c in columns if (c.get("outliers_iqr") or 0) > 0
        ],
        "all_empty_columns": [c["name"] for c in columns if "all_empty" in c["flags"]],
        "single_value_columns": [c["name"] for c in columns if "single_value" in c["flags"]],
    }
    return {
        "session_id": session_id,
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "duplicate_rows": int(df.duplicated().sum()),
        "total_null_cells": int(df.isna().sum().sum()),
        "inference": INFERENCE_META,
        "columns": columns,
        "issues": issues,
    }


def run_profiling(db_path: Path, storage_root: Path, session_id: str) -> None:
    """Background task: read the immutable upload, write profile.json, update state."""
    from ..db import session_store
    from ..storage.artifacts import profile_path, upload_path

    started = time.perf_counter()
    row = session_store.get_session(db_path, session_id)
    if row is None:
        return
    try:
        df = pd.read_csv(
            upload_path(storage_root, session_id),
            sep=row["delimiter"] or ",",
            encoding=row["encoding"] or "utf-8",
            engine="python",
        )
        profile = profile_dataframe(session_id, df)
        profile_path(storage_root, session_id).write_text(
            json.dumps(profile, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception as exc:  # session stays in last good state + error (Spec 01/02)
        duration_ms = int((time.perf_counter() - started) * 1000)
        session_store.update_session(
            db_path, session_id, error=f"profiling failed: {exc}", failed_stage="profile"
        )
        logger.error(
            "profile.failed",
            extra={
                "session_id": session_id,
                "stage": "profile",
                "duration_ms": duration_ms,
                "error": str(exc),
            },
        )
        return

    duration_ms = int((time.perf_counter() - started) * 1000)
    session_store.update_session(
        db_path, session_id, state="profiled", error=None, failed_stage=None
    )
    logger.info(
        "profile.completed",
        extra={"session_id": session_id, "stage": "profile", "duration_ms": duration_ms},
    )


_LLM_COLUMN_KEYS = ("name", "type", "nulls", "null_pct", "unique", "outliers_iqr", "stats", "flags")
_LLM_TOP_VALUE_TYPES = {"categorical", "boolean"}


def llm_profile(profile: dict, target: str | None = None) -> dict:
    """Privacy projection of a profile: the only profile shape allowed in a prompt (FR-PR-12).

    Keeps aggregates; keeps top values only for categorical/boolean columns (capped and
    truncated); never includes values of text or id_like columns, nor the session id.
    """
    columns = []
    for column in profile.get("columns", []):
        projected = {key: column[key] for key in _LLM_COLUMN_KEYS if column.get(key) is not None}
        if column.get("type") in _LLM_TOP_VALUE_TYPES and column.get("top_values"):
            projected["top_values"] = [
                {"value": str(item["value"])[:LLM_VALUE_MAX_CHARS], "count": item["count"]}
                for item in column["top_values"][:LLM_TOP_K]
            ]
        columns.append(projected)
    return {
        "n_rows": profile.get("n_rows"),
        "n_columns": profile.get("n_columns"),
        "duplicate_rows": profile.get("duplicate_rows"),
        "total_null_cells": profile.get("total_null_cells"),
        "outlier_method": profile.get("inference", {}).get("outlier_method"),
        "target": target,
        "columns": columns,
        "issues": profile.get("issues", {}),
    }
