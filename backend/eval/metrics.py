"""Eval metrics (Spec 10 NFR-10): golden matching, scripted review, summary. Pure functions."""

from __future__ import annotations

from collections.abc import Iterable
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
    return {
        "expected_recall": 1.0 if not expected else round((len(expected) - len(missing)) / len(expected), 4),
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
    }
