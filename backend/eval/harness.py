"""Eval harness (Spec 10 NFR-09, NFR-11, NFR-12).

Drives the real API in-process through a FastAPI `TestClient`, so the eval runs exactly
the code users hit: upload → target → LLM plan → scripted review → approve → execute
(re-profile + charts) → models → report. The caller decides the LLM (offline fake or
Gemini) through the app's `get_llm` dependency.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import settings
from app.db import session_store

from . import metrics

Response = Any  # TestClient responses (httpx); typed loosely across httpx versions

EVAL_DIR = Path(__file__).resolve().parent
SAMPLES = EVAL_DIR.parents[1] / "samples"
API = "/api/v1/sessions"
PERF_BUDGET_S = 60  # NFR-12, per stage
_STEP_FIELDS = ("op", "column", "params", "rationale")


class StageFailed(Exception):
    def __init__(self, stage: str, response: Response) -> None:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text[:300]
        super().__init__(f"{stage}: HTTP {response.status_code}")
        self.stage, self.status_code, self.detail = stage, response.status_code, detail


def load_golden(path: Path = EVAL_DIR / "golden.json") -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))["datasets"]


def _expect(stage: str, response: Response, *codes: int) -> Response:
    if response.status_code not in codes:
        raise StageFailed(stage, response)
    return response


class _Clock:
    def __init__(self) -> None:
        self.start = time.perf_counter()
        self.timings: dict[str, int] = {}

    def lap(self, stage: str, since: float) -> None:
        self.timings[stage] = int((time.perf_counter() - since) * 1000)


def _upload(client: TestClient, name: str, raw: bytes) -> str:
    created = _expect("upload", client.post(API, files={"file": (name, raw, "text/csv")}), 201)
    sid: str = created.json()["id"]
    state = client.get(f"{API}/{sid}").json()["state"]
    if state != "profiled":
        raise StageFailed("profile", client.get(f"{API}/{sid}"))
    return sid


def _approve(client: TestClient, sid: str, steps: list[dict], decisions: dict[str | None, str]) -> None:
    review = {"steps": [{**s, "status": "approved" if decisions.get(s["step_id"], "approve") == "approve"
                         else "disabled"} for s in steps]}
    _expect("approve", client.post(f"{API}/{sid}/plan/approve", json=review), 200)


def _execute_model_report(client: TestClient, sid: str, clock: _Clock | None = None) -> dict[str, Any]:
    base = f"{API}/{sid}"
    t = time.perf_counter()
    _expect("execute", client.post(f"{base}/execute"), 202)
    status = client.get(base).json()
    if status["state"] != "executed":
        raise StageFailed("execute", client.get(base))
    if clock:
        clock.lap("execute", t)
    t = time.perf_counter()
    _expect("model", client.post(f"{base}/model"), 202)
    runs = _expect("model", client.get(f"{base}/model"), 200).json()
    if clock:
        clock.lap("model", t)
    t = time.perf_counter()
    report = _expect("report", client.post(f"{base}/report"), 201).json()
    if clock:
        clock.lap("report", t)
    return {"runs": runs, "narration_source": report["narration_source"]}


def _artifacts(client: TestClient, sid: str) -> dict[str, Any]:
    base = f"{API}/{sid}"
    manifest = client.get(f"{base}/charts").json()
    charts = {c["file"]: client.get(f"{base}/charts/{c['file']}").content for c in manifest.get("charts", [])}
    runs = client.get(f"{base}/model").json()
    scores = [(m["name"], m["cv"], m["holdout"]) for m in runs["models"]]
    return {"cleaned": client.get(f"{base}/cleaned.csv").content, "charts": charts, "scores": scores,
            "report": client.get(f"{base}/report").content}


def _reproducibility(client: TestClient, name: str, raw: bytes, target: str | None, sid: str,
                     executed: list[dict], narration: str) -> dict[str, Any]:
    """NFR-11: replay the executed steps as a manual plan in a fresh session and compare."""
    first = _artifacts(client, sid)
    _expect("rerender", client.post(f"{API}/{sid}/report"), 201)
    rerender = client.get(f"{API}/{sid}/report").content == first["report"]

    replay = _upload(client, name, raw)
    if target:
        _expect("target", client.put(f"{API}/{replay}/target", json={"target": target}), 200)
    manual = {"schema_version": "v1", "steps": [{k: s.get(k) for k in _STEP_FIELDS} for s in executed]}
    plan = _expect("replay_plan", client.post(f"{API}/{replay}/plan", json=manual), 201).json()
    _approve(client, replay, plan["steps"], {})
    second_narration = _execute_model_report(client, replay)["narration_source"]
    second = _artifacts(client, replay)

    cross: bool | None = None
    if narration == "template" and second_narration == "template":
        masked = [a["report"].replace(s.encode(), b"SESSION") for a, s in ((first, sid), (second, replay))]
        cross = masked[0] == masked[1]
    return {
        "replay_session": replay,
        "cleaned_csv": first["cleaned"] == second["cleaned"],
        "charts": first["charts"] == second["charts"],
        "chart_count": len(first["charts"]),
        "model_scores": first["scores"] == second["scores"],
        "report_rerender": rerender,
        "report_cross_session": cross,
    }


def run_dataset(client: TestClient, name: str, golden: dict[str, Any], *,
                replay: bool = True) -> dict[str, Any]:
    """One full eval run on `samples/<name>` (NFR-09); never raises for a stage failure."""
    raw = (SAMPLES / name).read_bytes()
    target = golden.get("target")
    clock = _Clock()
    result: dict[str, Any] = {"name": name, "target": target, "status": "ok"}
    sid: str | None = None
    try:
        t = time.perf_counter()
        sid = _upload(client, name, raw)
        clock.lap("upload_profile", t)
        result["session_id"] = sid
        if target:
            _expect("target", client.put(f"{API}/{sid}/target", json={"target": target}), 200)

        t = time.perf_counter()
        plan_response = client.post(f"{API}/{sid}/plan")  # no body: the LLM plans
        clock.lap("plan", t)
        result["planner_calls"] = [
            {k: c[k] for k in ("attempt", "valid", "error", "prompt_tokens", "output_tokens", "duration_ms")
             if k in c}
            for c in session_store.list_llm_calls(settings.db_path, sid) if c["stage"] == "planner"]
        steps = _expect("plan", plan_response, 201).json()["steps"]
        result["plan"] = [{k: s.get(k) for k in ("step_id", "op", "column", "params")} for s in steps]

        score = metrics.score_plan(steps, golden)
        result["score"] = score
        decisions = {r["step_id"]: r["decision"] for r in score["review"]}
        _approve(client, sid, steps, decisions)

        outcome = _execute_model_report(client, sid, clock)
        runs = outcome["runs"]
        primary = runs["primary_metric"]
        best = next(m for m in runs["models"] if m["name"] == runs["best_model"])
        dummy = next(m for m in runs["models"] if m["name"] == "dummy")
        result.update(best_model=runs["best_model"], problem_type=runs.get("problem_type"),
                      primary_metric=primary, best_cv=best["cv"][primary]["mean"],
                      dummy_cv=dummy["cv"][primary]["mean"], narration_source=outcome["narration_source"])
        result["timings_ms"] = {**clock.timings, "total": int((time.perf_counter() - clock.start) * 1000)}

        if replay:
            executed = [s for s in steps if decisions.get(s["step_id"]) == "approve"]
            result["reproducibility"] = _reproducibility(client, name, raw, target, sid, executed,
                                                         outcome["narration_source"])
    except StageFailed as exc:
        result.update(status="failed", failed_stage=exc.stage, http_status=exc.status_code, detail=exc.detail)
        result.setdefault("timings_ms", {**clock.timings,
                                         "total": int((time.perf_counter() - clock.start) * 1000)})
        if sid and "planner_calls" not in result:
            result["planner_calls"] = []
    return result


def perf_baseline(client: TestClient, rows: int | None = None) -> dict[str, Any]:
    """NFR-12: Telco rows repeated to `rows` (default MAX_ROWS); time upload+profile and execute."""
    rows = rows or settings.max_rows
    header, *body = (SAMPLES / "telco_churn.csv").read_text(encoding="utf-8").splitlines()
    lines = [header] + [body[i % len(body)] for i in range(rows)]
    raw = ("\n".join(lines) + "\n").encode("utf-8")

    t = time.perf_counter()
    sid = _upload(client, "perf.csv", raw)
    upload_ms = int((time.perf_counter() - t) * 1000)
    manual = {"schema_version": "v1", "steps": [
        {"op": "standardize_text", "column": "gender", "params": {"ops": ["trim", "lowercase"]}},
        {"op": "standardize_text", "column": "PaymentMethod", "params": {"ops": ["trim", "collapse_spaces"]}},
        {"op": "clip_outliers", "column": "MonthlyCharges", "params": {"method": "iqr"}},
    ]}
    plan = _expect("perf_plan", client.post(f"{API}/{sid}/plan", json=manual), 201).json()
    _approve(client, sid, plan["steps"], {})
    t = time.perf_counter()
    _expect("perf_execute", client.post(f"{API}/{sid}/execute"), 202)
    execute_ms = int((time.perf_counter() - t) * 1000)
    if client.get(f"{API}/{sid}").json()["state"] != "executed":
        raise StageFailed("perf_execute", client.get(f"{API}/{sid}"))
    budget_ms = PERF_BUDGET_S * 1000
    return {"rows": rows, "columns": header.count(",") + 1, "size_mb": round(len(raw) / 1_048_576, 2),
            "upload_profile_ms": upload_ms, "execute_ms": execute_ms, "budget_s": PERF_BUDGET_S,
            "within_budget": upload_ms <= budget_ms and execute_ms <= budget_ms}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _yes(value: bool | None) -> str:
    return "n/a" if value is None else ("yes" if value else "**NO**")


def to_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    out = [f"# Eval results — {report['provider']}", ""]
    if report.get("model"):
        out += [f"LLM: `{report['model']}`", ""]
    out += ["| Metric (PRD §9) | Value |", "|---|---|",
            f"| Schema validity (first attempt) | {_pct(s['schema_validity'])} |",
            f"| Mean planner attempts | {s['mean_planner_attempts']} |",
            f"| Planner transport errors (API, not the plan) | {s.get('transport_errors', 0)} |",
            f"| Plan quality (sensible plans) | {_pct(s['plan_quality'])} |",
            f"| Approval rate (golden reviewer) | {_pct(s['approval_rate'])} |",
            f"| Mean time to report | {(s['mean_time_to_report_ms'] or 0) / 1000:.1f} s |", ""]
    out += ["## Datasets", "",
            "| Dataset | Status | Plan | Sensible | Recall | Approved | Attempts "
            "| Best model | Score (dummy) | Summary | Time |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in report["datasets"]:
        sc = d.get("score") or {}
        plan = ", ".join(f"{p['op']}({','.join(metrics.step_columns(p))})" for p in d.get("plan", [])) or "—"
        status = d["status"] if d["status"] == "ok" else f"failed at {d.get('failed_stage')}"
        score = (f"{d['primary_metric']} {d['best_cv']:.3f} ({d['dummy_cv']:.3f})"
                 if d.get("best_cv") is not None else "—")
        out.append(f"| {d['name']} | {status} | {plan} | {_yes(sc.get('sensible'))} | "
                   f"{sc.get('expected_recall', '—')} | {sc.get('approved', 0)}/{sc.get('proposed', 0)} | "
                   f"{len(d.get('planner_calls', []))} | {d.get('best_model', '—')} | {score} | "
                   f"{d.get('narration_source', '—')} | {d['timings_ms']['total'] / 1000:.1f} s |")
    issues = [(d["name"], d["score"]) for d in report["datasets"]
              if d.get("score") and (d["score"]["missing"] or d["score"]["forbidden_hits"])]
    if issues:
        out += ["", "Plan issues:"]
        for name, sc in issues:
            out += [f"- {name}: missing {sc['missing']}; forbidden {sc['forbidden_hits']}"]
    out += ["", "## Stage times (ms)", "", "| Dataset | Upload+profile | Plan | Execute (+charts) | Models "
            "| Report |", "|---|---|---|---|---|---|"]
    for d in report["datasets"]:
        t = d["timings_ms"]
        cells = (str(t.get(k, "—")) for k in ("upload_profile", "plan", "execute", "model", "report"))
        out.append(f"| {d['name']} | " + " | ".join(cells) + " |")
    out += ["", "## Reproducibility (NFR-11: executed plan replayed in a fresh session)", "",
            "| Dataset | Cleaned CSV | Charts | Model scores | Report re-render | Report across sessions |",
            "|---|---|---|---|---|---|"]
    for d in report["datasets"]:
        r = d.get("reproducibility")
        if r:
            out.append(f"| {d['name']} | {_yes(r['cleaned_csv'])} | {_yes(r['charts'])} ({r['chart_count']}) "
                       f"| {_yes(r['model_scores'])} | {_yes(r['report_rerender'])} | "
                       f"{_yes(r['report_cross_session'])} |")
    perf = report.get("perf")
    if perf:
        out += ["", "## Performance baseline (NFR-12)", "",
                f"{perf['rows']:,} rows × {perf['columns']} columns ({perf['size_mb']} MB): upload+profile "
                f"{perf['upload_profile_ms']} ms, execute (+re-profile, charts) {perf['execute_ms']} ms; "
                f"budget {perf['budget_s']} s each — "
                f"{'within budget' if perf['within_budget'] else '**over budget**'}."]
    if report.get("environment"):
        out += ["", f"Environment: {report['environment']}"]
    return "\n".join(out) + "\n"


def write_results(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{report['provider']}.json"
    md_path = out_dir / f"{report['provider']}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path
