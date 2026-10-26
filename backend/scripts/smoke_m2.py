"""End-to-end smoke test for the M2 flow (no LLM): upload -> plan -> execute -> deliverables.

Usage:
    1. start the API:  uvicorn app.main:app --port 8000
    2. run:            python scripts/smoke_m2.py [path-to-csv]
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"

PLAN = {
    "schema": "v1",
    "steps": [
        {
            "op": "drop_duplicates",
            "params": {},
            "rationale": "Remove exact duplicate rows",
        },
        {
            "op": "impute",
            "column": "Age",
            "params": {"strategy": "median"},
            "rationale": "Age is ~20% missing; median is robust to outliers",
        },
        {
            "op": "clip_outliers",
            "column": "Fare",
            "params": {},
            "rationale": "Cap extreme fares at the IQR fence",
        },
    ],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "../samples/titanic.csv")
    client = httpx.Client(timeout=60)

    print(f"[1] uploading {csv_path.name} ...")
    response = client.post(f"{BASE}/sessions", files={"file": (csv_path.name, csv_path.read_bytes(), "text/csv")})
    response.raise_for_status()
    session = response.json()
    sid = session["id"]
    print(f"    session {sid}  rows={session['n_rows']} cols={session['n_columns']}")

    print("[2] waiting for profiling ...")
    for _ in range(60):
        state = client.get(f"{BASE}/sessions/{sid}").json()["state"]
        if state != "uploaded":
            break
        time.sleep(0.5)
    print(f"    state={state}")

    print("[3] submitting plan (manual mode, Gate-validated) ...")
    response = client.post(f"{BASE}/sessions/{sid}/plan", json=PLAN)
    response.raise_for_status()
    print(f"    {len(response.json()['steps'])} steps accepted -> awaiting_approval")

    print("[4] executing approved plan ...")
    response = client.post(f"{BASE}/sessions/{sid}/execute", json=PLAN)
    response.raise_for_status()
    for _ in range(120):
        state = client.get(f"{BASE}/sessions/{sid}").json()["state"]
        if state in ("executed",):
            break
        time.sleep(0.5)
    final = client.get(f"{BASE}/sessions/{sid}").json()
    print(f"    state={final['state']}  error={final['error']}")

    session_dir = Path(__file__).resolve().parents[2] / "storage" / "sessions" / sid
    log = (session_dir / "execution_log.json").read_text()
    print("[5] execution log:")
    import json

    data = json.loads(log)
    print(f"    status={data['status']}  duration={data['duration_ms']}ms")
    for step in data["steps"]:
        before, after = step.get("before"), step.get("after")
        print(
            f"    step {step['index']}: {step['op']:<16} {step['status']:<8} "
            f"rows {before['rows']}->{after['rows'] if after else '-'}  "
            f"nulls {before['null_cells']}->{after['null_cells'] if after else '-'}  "
            f"notes={step.get('notes', {})}"
        )

    cleaned = session_dir / f"cleaned_{csv_path.name}"
    print(f"[6] deliverable: {cleaned.name} ({cleaned.stat().st_size} bytes)")
    print(f"[7] original untouched: {sha256(csv_path) == sha256(session_dir / 'upload.csv')}")


if __name__ == "__main__":
    main()
