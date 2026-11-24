"""Eval metrics (Spec 10 NFR-10): golden matching, scripted review, summary. Pure functions."""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from statistics import mean
from typing import Any

Entry = dict[str, Any]
Step = dict[str, Any]


def step_columns(step: Step) -> list[str]:
    """Columns a step touches: its column, or a drop_column's list."""
    if step.get("column"):
        return [step["column"]]
    return list((step.get("params") or {}).get("columns") or [])


def step_matches(entry: Entry, step: Step) -> bool:
    """NFR-10: same op, and the entry's column is the step's column, in its drop list, or '*'."""
    if entry["op"] != step["op"]:
        return False
    column = entry.get("column", "*")
    return column == "*" or column in step_columns(step)


def _any(entries: Iterable[Entry], step: Step) -> bool:
    return any(step_matches(e, step) for e in entries)


def _bare(entry: Entry) -> Entry:
    return {"op": entry["op"], "column": entry.get("column", "*")}


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def score_plan(steps: list[Step], golden: dict[str, Any]) -> dict[str, Any]:
    """Score proposed steps against a golden entry and decide the scripted review."""
    expected, acceptable, forbidden = (golden.get(k, []) for k in ("expected", "acceptable", "forbidden"))
    missing = [_bare(e) for e in expected if not any(step_matches(e, s) for s in steps)]
    forbidden_hits = [{"step_id": s.get("step_id"), "op": s["op"], "columns": step_columns(s)}
                      for s in steps if _any(forbidden, s)]
    review = []
    for s in steps:
        ok = (_any(expected, s) or _any(acceptable, s)) and not _any(forbidden, s)
        review.append({"step_id": s.get("step_id"), "op": s["op"], "columns": step_columns(s),
                       "decision": "approve" if ok else "skip"})
    approved = sum(r["decision"] == "approve" for r in review)
    recall = 1.0 if not expected else (len(expected) - len(missing)) / len(expected)
    precision = approved / len(steps) if steps else 1.0
    return {
        "expected_recall": round(recall, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(_f1(precision, recall), 4),
        "forbidden_rate": round(len(forbidden_hits) / len(steps), 4) if steps else 0.0,
        "missing": missing,
        "forbidden_hits": forbidden_hits,
        "sensible": not missing and not forbidden_hits,
        "review": review,
        "approved": approved,
        "proposed": len(steps),
        "approval_rate": round(approved / len(steps), 4) if steps else None,
    }


def summarize(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    """PRD §9 metrics over per-dataset results (NFR-10)."""
    planned = [d for d in datasets if d.get("planner_calls")]
    first_valid = [bool(d["planner_calls"][0]["valid"]) for d in planned]
    scored = [d["score"] for d in datasets if d.get("score")]
    proposed = sum(s["proposed"] for s in scored)
    times = [d["timings_ms"]["total"] for d in datasets if d.get("timings_ms", {}).get("total") is not None]
    return {
        "datasets": len(datasets),
        "schema_validity": round(sum(first_valid) / len(first_valid), 4) if first_valid else None,
        "mean_planner_attempts": (round(mean(len(d["planner_calls"]) for d in planned), 4)
                                  if planned else None),
        "plan_quality": round(sum(bool(s["sensible"]) for s in scored) / len(scored), 4) if scored else None,
        "approval_rate": round(sum(s["approved"] for s in scored) / proposed, 4) if proposed else None,
        "transport_errors": sum(str(c.get("error") or "").startswith("transport:")
                                for d in planned for c in d["planner_calls"]),
        "mean_time_to_report_ms": int(mean(times)) if times else None,
        "mean_f1": round(mean(s["f1"] for s in scored if "f1" in s), 4)
                   if any("f1" in s for s in scored) else None,
        "forbidden_rate": round(sum(len(s.get("forbidden_hits", [])) for s in scored) / proposed, 4)
                          if proposed else None,
    }


def bootstrap_ci(values: Sequence[float], *, n: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float, float]:
    """NFR-14: (mean, low, high) percentile bootstrap CI of the mean; deterministic per seed."""
    if not values:
        raise ValueError("bootstrap_ci needs at least one value")
    rng = random.Random(seed)
    k = len(values)
    means = sorted(sum(rng.choices(values, k=k)) / k for _ in range(n))
    lo = means[int(alpha / 2 * (n - 1))]
    hi = means[int(round((1 - alpha / 2) * (n - 1)))]
    m = sum(values) / k
    return m, min(lo, m), max(hi, m)


def cohen_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    """NFR-14: Cohen's kappa for two annotators' binary labels."""
    if len(a) != len(b) or not a:
        raise ValueError("cohen_kappa needs two non-empty label lists of equal length")
    k = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / k
    pa, pb = sum(a) / k, sum(b) / k
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)
