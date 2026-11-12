"""Reporter: assembles report.html and bundle.zip from stored artifacts (Spec 08).

Deterministic. Every number in the report comes from an artifact (profile, execution
log, chart manifest, model runs); the only LLM text is the Narrator's, and its numbers
are placeholders filled from the same facts.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import platform
import time
import zipfile
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
import sklearn
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import settings
from ..llm.client import LLMClient
from ..schemas.plan import SCHEMA_VERSION
from ..storage import artifacts
from .narrator import Narration, facts_hash, format_value, narrate, render

logger = logging.getLogger("reporter")

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
MODEL_LABELS = {"dummy": "Dummy", "logistic_regression": "Logistic regression",
                "linear_regression": "Linear regression", "random_forest": "Random forest"}
METRIC_LABELS = {"f1_macro": "F1 (macro)", "accuracy": "Accuracy", "roc_auc": "ROC AUC",
                 "rmse": "RMSE", "mae": "MAE", "r2": "R²"}
TYPE_LABELS = {"numeric": "number", "categorical": "category", "datetime": "date",
               "boolean": "yes/no", "text": "text", "id_like": "identifier"}
SUMMARY_TITLES = {"overview": "Overview", "cleaning": "Cleaning", "modeling": "Modeling",
                  "next_steps": "Next steps"}
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)  # fixed entry time: identical inputs -> identical zip

_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["j2", "html"]),
                   trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_context(storage_root: Path, session_id: str, row: dict) -> dict:
    """Every artifact the report needs (missing optional ones are None)."""
    version = row["plan_version"]
    return {
        "row": row,
        "profile": _read_json(artifacts.profile_path(storage_root, session_id)),
        "after": _read_json(artifacts.after_profile_path(storage_root, session_id)),
        "plan": _read_json(artifacts.plan_version_path(storage_root, session_id, version, "approved"))
        if version else None,
        "log": _read_json(artifacts.execution_log_path(storage_root, session_id)),
        "charts": _read_json(artifacts.charts_manifest_path(storage_root, session_id)),
        "runs": _read_json(artifacts.model_runs_path(storage_root, session_id)),
    }


def _executed(ctx: dict) -> list[dict]:
    return [s for s in (ctx["log"] or {}).get("steps", []) if s.get("status") == "executed"]


def collect_facts(ctx: dict) -> dict[str, Any]:
    """The numbers (and labels) the summary may mention, all read from artifacts."""
    profile, row = ctx["profile"], ctx["row"]
    executed = _executed(ctx)
    log_steps = (ctx["log"] or {}).get("steps", [])
    first = executed[0]["before"] if executed else None
    last = executed[-1]["after"] if executed else None
    after = ctx["after"] or {}
    facts: dict[str, Any] = {
        "file_name": row["original_filename"],
        "rows_before": first["rows"] if first else profile["n_rows"],
        "cols_before": first["cols"] if first else profile["n_columns"],
        "null_cells_before": first["null_cells"] if first else profile["total_null_cells"],
        "rows_after": last["rows"] if last else after.get("n_rows", profile["n_rows"]),
        "cols_after": last["cols"] if last else after.get("n_columns", profile["n_columns"]),
        "null_cells_after": (last["null_cells"] if last
                             else after.get("total_null_cells", profile["total_null_cells"])),
        "duplicate_rows_before": profile["duplicate_rows"],
        "steps_executed": len(executed),
        "steps_skipped": sum(1 for s in log_steps if s.get("status") == "disabled"),
        "charts_count": len((ctx["charts"] or {}).get("charts", [])),
    }
    runs = ctx["runs"]
    if runs:
        best = next(m for m in runs["models"] if m["name"] == runs["best_model"])
        dummy = next(m for m in runs["models"] if m["name"] == "dummy")
        metric = runs["primary_metric"]
        facts.update({
            "target": runs["target"],
            "problem_type": runs["problem_type"],
            "best_model": MODEL_LABELS.get(runs["best_model"], runs["best_model"]),
            "primary_metric": METRIC_LABELS.get(metric, metric),
            "best_score": best["cv"][metric]["mean"],
            "dummy_score": dummy["cv"][metric]["mean"],
            "holdout_score": best["holdout"].get(metric),
            "rows_used": runs["rows"]["used"],
        })
    return facts


def known_names(ctx: dict) -> set[str]:
    """Names the Narrator may write verbatim even if they contain digits."""
    names = {c["name"] for c in ctx["profile"]["columns"]}
    names |= set(MODEL_LABELS.values()) | set(METRIC_LABELS.values())
    names.add(ctx["row"]["original_filename"])
    return names


def _issues(profile: dict) -> list[str]:
    found = []
    if profile["duplicate_rows"]:
        found.append(f"{profile['duplicate_rows']:,} duplicate rows.")
    for c in profile["columns"]:
        if "all_empty" in c.get("flags", []):
            found.append(f"{c['name']}: entirely empty.")
        elif c["nulls"]:
            found.append(f"{c['name']}: {c['nulls']:,} missing values ({c['null_pct']}%).")
        if c.get("outliers_iqr"):
            found.append(f"{c['name']}: {c['outliers_iqr']:,} outliers by the IQR rule.")
        if "single_value" in c.get("flags", []):
            found.append(f"{c['name']}: a single repeated value.")
    return found


def _steps(ctx: dict) -> list[dict]:
    logged = {s.get("step_id"): s for s in (ctx["log"] or {}).get("steps", [])}
    steps = []
    for index, step in enumerate((ctx["plan"] or {}).get("steps", [])):
        entry = logged.get(step.get("step_id"), {})
        result = {"executed": "executed", "disabled": "skipped", "failed": "failed"}.get(
            entry.get("status", ""), "not run")
        steps.append({
            "step_id": step.get("step_id") or f"n{index}",
            "op": step["op"],
            "column": step.get("column"),
            "params": json.dumps(step.get("params") or {}, sort_keys=True) if step.get("params") else "",
            "rationale": step.get("rationale"),
            "decision": {"disabled": "skipped"}.get(step.get("status", ""), step.get("status", "")),
            "result": result,
            "executed": entry.get("status") == "executed",
            "before": entry.get("before") if entry.get("status") == "executed" else None,
            "after": entry.get("after") if entry.get("status") == "executed" else None,
        })
    return steps


def _charts(storage_root: Path, session_id: str, manifest: dict | None) -> tuple[list[dict], str]:
    if not manifest or manifest.get("status") != "completed":
        return [], ""
    folder = artifacts.charts_dir(storage_root, session_id)
    charts = []
    for chart in manifest["charts"]:
        path = folder / chart["file"]
        if path.is_file():
            charts.append({"title": chart["title"],
                           "data": base64.b64encode(path.read_bytes()).decode("ascii")})
    skipped = ", ".join(sorted({s["column"] for s in manifest.get("skipped", []) if s.get("column")}))
    return charts, skipped


def render_report(storage_root: Path, session_id: str, ctx: dict, narration: Narration) -> str:
    profile, after, row = ctx["profile"], ctx["after"] or {}, ctx["row"]
    facts = collect_facts(ctx)
    after_types = {c["name"]: c["type"] for c in after.get("columns", [])}
    after_nulls = {c["name"]: c["nulls"] for c in after.get("columns", [])}
    charts, skipped = _charts(storage_root, session_id, ctx["charts"])
    runs = ctx["runs"]

    def total_outliers(p: dict) -> int:
        return sum(c.get("outliers_iqr") or 0 for c in p.get("columns", []))

    html = _env.get_template("report.html.j2").render(
        session_id=session_id,
        file_name=row["original_filename"],
        fmt=format_value,
        score=lambda v: "—" if v is None else f"{v:.3f}",
        metric_label=lambda m: METRIC_LABELS.get(m, m),
        model_label=lambda m: MODEL_LABELS.get(m, m),
        rows_before=facts["rows_before"], rows_after=facts["rows_after"],
        cols_before=facts["cols_before"], cols_after=facts["cols_after"],
        nulls_before=facts["null_cells_before"], nulls_after=facts["null_cells_after"],
        columns=[{"name": c["name"], "before": TYPE_LABELS.get(c["type"], c["type"]),
                  "after": TYPE_LABELS.get(after_types.get(c["name"], ""), after_types.get(c["name"]))}
                 for c in profile["columns"]],
        issues=_issues(profile),
        plan_version=row["plan_version"],
        steps=_steps(ctx),
        executed_steps=facts["steps_executed"],
        comparison=[
            {"label": "Rows", "before": profile["n_rows"], "after": after.get("n_rows", facts["rows_after"])},
            {"label": "Columns", "before": profile["n_columns"],
             "after": after.get("n_columns", facts["cols_after"])},
            {"label": "Missing cells", "before": profile["total_null_cells"],
             "after": after.get("total_null_cells", facts["null_cells_after"])},
            {"label": "Duplicate rows", "before": profile["duplicate_rows"],
             "after": after.get("duplicate_rows", profile["duplicate_rows"])},
            {"label": "Outliers (IQR)", "before": total_outliers(profile), "after": total_outliers(after)},
        ],
        column_changes=[{"name": c["name"], "before": c["nulls"], "after": after_nulls.get(c["name"])}
                        for c in profile["columns"] if c["nulls"]],
        charts=charts,
        skipped_charts=skipped,
        runs=runs,
        secondary="r2" if runs and runs["problem_type"] == "regression" else "accuracy",
        replayed=", ".join(runs["replayed_ops"]) if runs else "",
        in_pipeline=", ".join(f"{s['op']} ({s['column']})" for s in runs["in_pipeline"]) if runs else "",
        narration_source=narration.source,
        narration_model=narration.model,
        summary=[(SUMMARY_TITLES[k], render(v, facts)) for k, v in narration.sections.items()],
        schema_version=SCHEMA_VERSION,
        versions={"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                  "sklearn": sklearn.__version__, "matplotlib": matplotlib.__version__},
    )
    return html


def generate_report(db_path: Path, storage_root: Path, session_id: str, row: dict,
                    llm: LLMClient | None, *, renarrate: bool = False) -> Narration:
    """Build report.html; reuse the stored narration while its facts are unchanged (FR-RP-13)."""
    started = time.perf_counter()
    ctx = load_context(storage_root, session_id, row)
    facts = collect_facts(ctx)
    stored = _read_json(artifacts.narration_path(storage_root, session_id))
    if stored and not renarrate and stored.get("facts_hash") == facts_hash(facts):
        narration = Narration(stored["sections"], stored["source"], stored["facts_hash"], stored.get("model"))
    else:
        narration = narrate(llm, facts, known_names(ctx), max_retries=settings.narration_max_retries,
                            db_path=db_path, session_id=session_id)
        artifacts.narration_path(storage_root, session_id).write_text(
            json.dumps(narration.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        if narration.source == "template":
            logger.info("narration.fallback", extra={"session_id": session_id, "stage": "report"})
    html = render_report(storage_root, session_id, ctx, narration)
    artifacts.report_path(storage_root, session_id).write_text(html, encoding="utf-8")
    logger.info("report.generated", extra={
        "session_id": session_id, "stage": "report",
        "duration_ms": int((time.perf_counter() - started) * 1000),
    })
    return narration


def build_bundle(storage_root: Path, session_id: str, row: dict) -> bytes:
    """All deliverables in one zip with fixed timestamps (FR-RP-15)."""
    entries: list[tuple[str, Path]] = [
        ("report.html", artifacts.report_path(storage_root, session_id)),
        (artifacts.cleaned_filename(row["original_filename"]),
         artifacts.cleaned_csv_path(storage_root, session_id, row["original_filename"])),
        ("execution_log.json", artifacts.execution_log_path(storage_root, session_id)),
        ("model_runs.json", artifacts.model_runs_path(storage_root, session_id)),
        ("charts_manifest.json", artifacts.charts_manifest_path(storage_root, session_id)),
    ]
    if row["plan_version"]:
        entries.append(("plan.approved.json", artifacts.plan_version_path(
            storage_root, session_id, row["plan_version"], "approved")))
    manifest = _read_json(artifacts.charts_manifest_path(storage_root, session_id)) or {}
    folder = artifacts.charts_dir(storage_root, session_id)
    entries += [(f"charts/{c['file']}", folder / c["file"]) for c in manifest.get("charts", [])]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(entries):
            if path.is_file():
                info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    return buffer.getvalue()
