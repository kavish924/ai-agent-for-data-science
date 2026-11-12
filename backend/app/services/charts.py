"""Deterministic chart generation (Spec 06). No LLM, no network.

Pure function of its inputs: dataframes and profiles in, PNG files plus a manifest out.
Uses matplotlib's object API (no pyplot global state) with a fixed style and no version
metadata in the PNGs, so the same inputs always give byte-identical images (FR-CH-07).
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless; must precede any figure creation

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import rc_context  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .numeric import parse_numeric  # noqa: E402

INK = "#16181D"
MUTED = "#5B5F68"
GRID = "#E4E4DF"
ACCENT = "#0F766E"
BEFORE = "#33363D"  # dark outline: must read over the teal bars at thumbnail size
MISSING = "#B45309"
PRESENT = "#F0F0EC"

STYLE: Any = {  # Any: matplotlib types rc keys as a Literal union
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "axes.titlecolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "path.simplify": False,
}
DPI = 100
MAX_HEATMAP_COLUMNS = 15
MAX_MAP_ROWS = 400
TOP_CATEGORIES = 10
LABEL_CHARS = 24

_SKIP_BY_TYPE = {
    "id_like": "identifier column (no chart)",
    "text": "text column (no chart in v1)",
    "datetime": "date column (no chart in v1)",
}


@dataclass(frozen=True)
class _Candidate:
    kind: str  # missing_map | correlation | distribution | bar
    column: str | None


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")[:40] or "column"


def _short(label: object) -> str:
    text = str(label)
    return text if len(text) <= LABEL_CHARS else text[: LABEL_CHARS - 1] + "…"


def _save(fig: Figure, path: Path) -> None:
    # metadata={"Software": None} drops the matplotlib version stamp (FR-CH-07)
    fig.savefig(path, format="png", dpi=DPI, metadata={"Software": None})


def _numeric(series: pd.Series) -> np.ndarray:
    return parse_numeric(series)[0].dropna().to_numpy(dtype="float64")


def _missing_map(df: pd.DataFrame, path: Path) -> str:
    step = max(1, math.ceil(len(df) / MAX_MAP_ROWS))
    matrix = df.iloc[::step].isna().to_numpy(dtype="float64")
    fig = Figure(figsize=(8, 4.5))
    ax = fig.add_subplot()
    from matplotlib.colors import ListedColormap

    ax.imshow(matrix, aspect="auto", interpolation="nearest",
              cmap=ListedColormap([PRESENT, MISSING]), vmin=0, vmax=1)
    ax.set_xticks(range(df.shape[1]))
    ax.set_xticklabels([_short(c) for c in df.columns], rotation=45, ha="right")
    ax.set_yticks([])
    ax.set_ylabel(f"rows (every {step})" if step > 1 else "rows")
    ax.set_title("Missing values (orange = missing)")
    fig.tight_layout()
    _save(fig, path)
    return "Missing values"


def _correlation(df: pd.DataFrame, columns: list[str], path: Path) -> str:
    columns = columns[:MAX_HEATMAP_COLUMNS]
    data = pd.DataFrame({c: parse_numeric(df[c])[0] for c in columns})
    corr = data.corr(method="pearson").fillna(0.0).to_numpy()
    size = 3.2 + 0.42 * len(columns)
    fig = Figure(figsize=(size, size * 0.85))
    ax = fig.add_subplot()
    image = ax.imshow(corr, cmap="BrBG", vmin=-1, vmax=1)
    labels = [_short(c) for c in columns]
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(len(columns)))
    ax.set_yticklabels(labels)
    if len(columns) <= 10:
        for i in range(len(columns)):
            for j in range(len(columns)):
                value = corr[i, j]
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if abs(value) > 0.6 else INK)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Correlation (Pearson)")
    fig.tight_layout()
    _save(fig, path)
    return "Correlation"


def _distribution(values: np.ndarray, before: np.ndarray | None, column: str, path: Path) -> str:
    fig = Figure(figsize=(6.4, 4))
    grid = fig.add_gridspec(2, 1, height_ratios=(1, 5), hspace=0.08)
    ax_box = fig.add_subplot(grid[0])
    ax_hist = fig.add_subplot(grid[1], sharex=ax_box)
    combined = values if before is None or before.size == 0 else np.concatenate([values, before])
    edges = np.histogram_bin_edges(combined, bins="auto")
    if len(edges) > 41:
        edges = np.histogram_bin_edges(combined, bins=40)
    bins: list[float] = edges.tolist()
    ax_hist.hist(values, bins=bins, color=ACCENT, alpha=0.85, label="cleaned")
    if before is not None and before.size:
        ax_hist.hist(before, bins=bins, histtype="step", color=BEFORE, linewidth=1.8, label="before")
        ax_hist.legend(frameon=False, loc="upper right")
    ax_hist.set_ylabel("rows")
    ax_hist.grid(axis="y", color=GRID, linewidth=0.6)
    ax_box.boxplot(values, orientation="horizontal", widths=0.6, patch_artist=True,
                   boxprops={"facecolor": PRESENT, "edgecolor": ACCENT},
                   medianprops={"color": ACCENT}, whiskerprops={"color": MUTED},
                   capprops={"color": MUTED},
                   flierprops={"marker": "o", "markersize": 2.5, "markerfacecolor": MUTED,
                               "markeredgecolor": "none"})
    ax_box.axis("off")
    ax_box.set_title(f"{_short(column)} — distribution")
    _save(fig, path)
    return f"{column} — distribution"


def _bar(series: pd.Series, column: str, path: Path) -> str:
    counts = series.dropna().astype(str).value_counts()
    top = (
        pd.DataFrame({"value": counts.index, "count": counts.to_numpy()})
        .sort_values(["count", "value"], ascending=[False, True], kind="mergesort")
        .head(TOP_CATEGORIES)
    )
    fig = Figure(figsize=(6.4, 0.9 + 0.36 * len(top)))
    ax = fig.add_subplot()
    labels = [_short(v) for v in top["value"]][::-1]
    ax.barh(labels, top["count"].to_list()[::-1], color=ACCENT)
    ax.set_xlabel("rows")
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_title(f"{_short(column)} — top values")
    fig.tight_layout()
    _save(fig, path)
    return f"{column} — top values"


def _ordered_columns(columns: Iterable[str], original_profile: dict) -> list[str]:
    """FR-CH-06: columns with nulls, then with outliers (per the ORIGINAL profile), then rest."""
    original = {c["name"]: c for c in original_profile.get("columns", [])}
    names = list(columns)
    with_nulls = [n for n in names if original.get(n, {}).get("nulls")]
    with_outliers = [n for n in names if n not in with_nulls and original.get(n, {}).get("outliers_iqr")]
    rest = [n for n in names if n not in with_nulls and n not in with_outliers]
    return with_nulls + with_outliers + rest


def generate_charts(
    cleaned: pd.DataFrame,
    *,
    after_profile: dict,
    original_profile: dict,
    out_dir: Path,
    max_charts: int,
    before: pd.DataFrame | None = None,
    changed_columns: set[str] | frozenset[str] = frozenset(),
) -> dict:
    """Render the capped chart set for `cleaned`; return the manifest (FR-CH-01..12)."""
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.png"):  # a new run replaces the previous run's charts
        stale.unlink()

    types = {c["name"]: c["type"] for c in after_profile.get("columns", [])}
    numeric = [c for c in cleaned.columns if types.get(c) == "numeric"]
    candidates: list[_Candidate] = []
    skipped: list[dict] = []

    if cleaned.isna().to_numpy().any():
        candidates.append(_Candidate("missing_map", None))
    else:
        skipped.append({"kind": "missing_map", "column": None, "reason": "no missing values"})
    if len(numeric) >= 2:
        candidates.append(_Candidate("correlation", None))
    else:
        skipped.append({"kind": "correlation", "column": None, "reason": "fewer than two numeric columns"})

    for column in _ordered_columns(cleaned.columns, original_profile):
        kind = types.get(column)
        if kind == "numeric":
            candidates.append(_Candidate("distribution", column))
        elif kind in ("categorical", "boolean"):
            candidates.append(_Candidate("bar", column))
        else:
            reason = _SKIP_BY_TYPE.get(kind or "", "no chart for this column type")
            skipped.append({"kind": "column", "column": column, "reason": reason})

    charts: list[dict] = []
    for candidate in candidates:
        if len(charts) >= max_charts:
            skipped.append({"kind": candidate.kind, "column": candidate.column,
                            "reason": f"chart cap ({max_charts}) reached"})
            continue
        index = len(charts) + 1
        suffix = f"_{_safe(candidate.column)}" if candidate.column else ""
        name = f"{index:02d}_{candidate.kind}{suffix}.png"
        path = out_dir / name
        overlay = False
        with rc_context(STYLE):
            if candidate.kind == "missing_map":
                title = _missing_map(cleaned, path)
            elif candidate.kind == "correlation":
                title = _correlation(cleaned, numeric, path)
            elif candidate.kind == "distribution":
                assert candidate.column is not None
                values = _numeric(cleaned[candidate.column])
                if values.size == 0:
                    skipped.append({"kind": "distribution", "column": candidate.column,
                                    "reason": "no numeric values"})
                    continue
                prior = None
                if before is not None and candidate.column in changed_columns and candidate.column in before:
                    prior = _numeric(before[candidate.column])
                    overlay = prior.size > 0
                title = _distribution(values, prior, candidate.column, path)
            else:
                assert candidate.column is not None
                title = _bar(cleaned[candidate.column], candidate.column, path)
        charts.append({"file": name, "kind": candidate.kind, "column": candidate.column,
                       "title": title, "before_overlay": overlay})

    return {
        "status": "completed",
        "max_charts": max_charts,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "charts": charts,
        "skipped": skipped,
    }
