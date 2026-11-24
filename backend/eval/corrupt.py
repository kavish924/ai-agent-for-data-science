"""Seeded corruption generator with exact ground truth (Spec 10 NFR-16).

`corrupt(df, target, seed)` injects known data-quality issues into a copy of `df` and
returns the corrupted frame plus a golden entry (expected / acceptable / forbidden steps,
in the format of `eval/golden.json`) that records exactly what was injected. Pure: the
input frame is never modified and the result depends only on (df, target, seed).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

Entry = dict[str, Any]

INJECTION_ORDER = ("id_column", "constant", "leak", "missing", "heavy_missing", "outliers",
                   "text_noise", "duplicates")
ID_COLUMN = "record_id"
CONSTANT_COLUMN = "export_batch"
MISSING_RATE = 0.10
HEAVY_MISSING_RATE = 0.80
OUTLIER_RATE = 0.01
OUTLIER_FACTOR = 50
TEXT_NOISE_RATE = 0.20
DUPLICATE_RATE = 0.02
TEXT_MAX_UNIQUE = 50
OUTLIER_MIN_UNIQUE = 10  # no outliers in 0/1 or other low-cardinality numeric columns

ACCEPTABLE: list[Entry] = [
    {"op": "impute", "column": "*"},
    {"op": "clip_outliers", "column": "*"},
    {"op": "standardize_text", "column": "*"},
    {"op": "cast_type", "column": "*"},
]


def _is_numeric(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _is_text(s: pd.Series) -> bool:
    return (pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)) and \
        all(isinstance(v, str) for v in s)


def corrupt(df: pd.DataFrame, target: str, seed: int,
            protected: Iterable[str] = ()) -> tuple[pd.DataFrame, Entry]:
    """`protected`: columns that must not be made heavily missing (their drop is forbidden)."""
    if target not in df.columns:
        raise ValueError(f"target {target!r} is not a column")
    rng = np.random.default_rng(seed)
    out = df.copy().reset_index(drop=True)
    n = len(out)
    original = [c for c in out.columns if c != target]
    used: set[str] = set()
    keep = set(protected)
    injections: list[Entry] = []
    skipped: list[str] = []
    expected: list[Entry] = []
    forbidden: list[Entry] = [{"op": "drop_column", "column": target, "why": "the target"}]

    def complete(c: str) -> bool:
        return c not in used and bool(out[c].notna().all()) and out[c].nunique() > 1

    def pick(candidates: list[str]) -> str | None:
        return str(candidates[int(rng.integers(len(candidates)))]) if candidates else None

    def rows(rate: float, minimum: int = 0) -> np.ndarray:
        k = min(n, max(minimum, round(rate * n)))
        return np.sort(rng.choice(n, size=k, replace=False))

    def record(kind: str, column: str, affected: int, entry: Entry) -> None:
        injections.append({"type": kind, "column": column, "rows": int(affected)})
        expected.append(entry)

    for kind in INJECTION_ORDER:
        if kind == "id_column":
            if ID_COLUMN in out.columns or n == 0:
                skipped.append(kind)
                continue
            ids = [f"REC-{i:06d}" for i in rng.permutation(n) + 1]
            out.insert(0, ID_COLUMN, ids)
            record(kind, ID_COLUMN, n, {"op": "drop_column", "column": ID_COLUMN,
                                        "why": "injected: unique record identifier"})
        elif kind == "constant":
            if CONSTANT_COLUMN in out.columns:
                skipped.append(kind)
                continue
            out[CONSTANT_COLUMN] = "B1"
            record(kind, CONSTANT_COLUMN, n, {"op": "drop_column", "column": CONSTANT_COLUMN,
                                              "why": "injected: a single value"})
        elif kind == "leak":
            leak = f"{target}_copy"
            if leak in out.columns:
                skipped.append(kind)
                continue
            out[leak] = out[target]
            record(kind, leak, n, {"op": "drop_column", "column": leak,
                                   "why": "injected: a copy of the target (leakage)"})
        elif kind == "missing":
            col = pick([c for c in original if complete(c) and _is_numeric(out[c])])
            if col is None:
                skipped.append(kind)
                continue
            idx = rows(MISSING_RATE, 1)
            out[col] = out[col].astype("float64")
            out.loc[idx, col] = np.nan
            used.add(col)
            record(kind, col, len(idx), {"op": "impute", "column": col,
                                         "why": f"injected: {MISSING_RATE:.0%} missing"})
            forbidden.append({"op": "drop_column", "column": col,
                              "why": f"only {MISSING_RATE:.0%} missing: impute, don't drop"})
        elif kind == "heavy_missing":
            ok = [c for c in original if complete(c) and c not in keep]
            col = pick([c for c in ok if _is_numeric(out[c])] or ok)
            if col is None:
                skipped.append(kind)
                continue
            idx = rows(HEAVY_MISSING_RATE, 1)
            if _is_numeric(out[col]):
                out[col] = out[col].astype("float64")
            else:
                out[col] = out[col].astype(object)
            out.loc[idx, col] = np.nan
            used.add(col)
            record(kind, col, len(idx), {"op": "drop_column", "column": col,
                                         "why": f"injected: {HEAVY_MISSING_RATE:.0%} missing"})
        elif kind == "outliers":
            col = pick([c for c in original if complete(c) and _is_numeric(out[c])
                        and out[c].nunique() >= OUTLIER_MIN_UNIQUE and float(out[c].abs().max()) > 0])
            if col is None:
                skipped.append(kind)
                continue
            idx = rows(OUTLIER_RATE, 1)
            value = OUTLIER_FACTOR * out[col].abs().max()
            out.loc[idx, col] = value
            used.add(col)
            record(kind, col, len(idx), {"op": "clip_outliers", "column": col,
                                         "why": f"injected: values set to {OUTLIER_FACTOR}x the max"})
        elif kind == "text_noise":
            col = pick([c for c in original if complete(c) and _is_text(out[c])
                        and out[c].nunique() <= TEXT_MAX_UNIQUE])
            if col is None:
                skipped.append(kind)
                continue
            idx = rows(TEXT_NOISE_RATE, 1)
            variants = rng.integers(0, 2, size=len(idx))
            values = out[col].astype(object).copy()
            for i, v in zip(idx, variants, strict=True):
                s = str(values.iat[i])
                values.iat[i] = s.upper() if v == 0 and s.upper() != s else f" {s}  "
            out[col] = values
            used.add(col)
            record(kind, col, len(idx), {"op": "standardize_text", "column": col,
                                         "why": "injected: inconsistent case and spacing"})
        elif kind == "duplicates":
            if n == 0:
                skipped.append(kind)
                continue
            idx = rows(DUPLICATE_RATE, 1)
            out = pd.concat([out, out.iloc[idx]], ignore_index=True)
            record(kind, "*", len(idx), {"op": "drop_duplicates", "column": "*",
                                         "why": f"injected: {len(idx)} repeated rows"})

    entry: Entry = {"target": target, "expected": expected, "acceptable": list(ACCEPTABLE),
                    "forbidden": forbidden, "injections": injections, "skipped": skipped}
    return out, entry


def _key(e: Entry) -> tuple[str, str]:
    return e["op"], e.get("column", "*")


def merge_golden(base: Entry, generated: Entry) -> Entry:
    """Union the source's own golden entry into a generated one (base entries first)."""
    merged = dict(generated)
    for k in ("expected", "acceptable", "forbidden"):
        seen: set[tuple[str, str]] = set()
        items: list[Entry] = []
        for e in [*base.get(k, []), *generated.get(k, [])]:
            if _key(e) not in seen:
                seen.add(_key(e))
                items.append(e)
        merged[k] = items
    expected = {_key(e) for e in merged["expected"]}
    merged["forbidden"] = [e for e in merged["forbidden"] if _key(e) not in expected]  # safety net
    merged["target"] = base.get("target") or generated["target"]
    return merged


def protected_columns(golden: Entry) -> list[str]:
    """Columns a golden entry forbids dropping."""
    return [e["column"] for e in golden.get("forbidden", [])
            if e["op"] == "drop_column" and e.get("column", "*") != "*"]
