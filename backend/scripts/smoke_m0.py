"""End-to-end smoke test for the M0 flow (no LLM, no server needed).

upload -> profile -> target -> plan -> review/approve -> execute -> download cleaned CSV,
on every sample dataset, in-process with an isolated temporary storage root.

Usage (from backend/):
    python scripts/smoke_m0.py
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "samples"

CASES = {
    "titanic.csv": {
        "target": "Survived",
        "steps": [
            {"op": "drop_duplicates", "rationale": "Remove exact duplicate rows"},
            {"op": "drop_column", "params": {"columns": ["Cabin"]}, "rationale": "77% missing"},
            {"op": "impute", "column": "Age", "params": {"strategy": "median"},
             "rationale": "~20% missing; median is robust"},
            {"op": "impute", "column": "Embarked", "params": {"strategy": "mode"},
             "rationale": "2 missing values"},
            {"op": "clip_outliers", "column": "Fare", "params": {}, "rationale": "extreme fares"},
        ],
    },
    "housing.csv": {
        "target": "median_house_value",
        "steps": [
            {"op": "impute", "column": "total_bedrooms", "params": {"strategy": "median"},
             "rationale": "~1% missing"},
            {"op": "standardize_text", "column": "ocean_proximity",
             "params": {"ops": ["trim", "lowercase"]}, "rationale": "consistent categories"},
        ],
    },
    "telco_churn.csv": {
        "target": "Churn",
        "steps": [
            {"op": "impute", "column": "TotalCharges", "params": {"strategy": "median"},
             "rationale": "blank strings for new customers"},
            {"op": "clip_outliers", "column": "MonthlyCharges", "params": {}, "rationale": "IQR fence"},
        ],
    },
}


def run_case(client: TestClient, name: str, case: dict) -> None:
    started = time.perf_counter()
    raw = (SAMPLES / name).read_bytes()
    sid = client.post("/api/v1/sessions", files={"file": (name, raw, "text/csv")}).json()["id"]
    base = f"/api/v1/sessions/{sid}"

    profile = client.get(f"{base}/profile").json()
    types = {c["name"]: c["type"] for c in profile["columns"]}
    assert client.put(f"{base}/target", json={"target": case["target"]}).status_code == 200

    created = client.post(f"{base}/plan", json={"steps": case["steps"]})
    assert created.status_code == 201, created.json()
    review = {"steps": [{**s, "status": "approved"} for s in created.json()["steps"]]}
    approved = client.post(f"{base}/plan/approve", json=review)
    assert approved.status_code == 200, approved.json()
    assert client.post(f"{base}/execute").status_code == 202

    status = client.get(base).json()
    assert status["state"] == "executed", status
    cleaned = client.get(f"{base}/cleaned.csv")
    assert cleaned.status_code == 200
    upload_sha = hashlib.sha256((settings.storage_root / "sessions" / sid / "upload.csv").read_bytes())
    assert upload_sha.hexdigest() == hashlib.sha256(raw).hexdigest(), "upload modified!"

    ms = int((time.perf_counter() - started) * 1000)
    id_cols = [c for c, t in types.items() if t == "id_like"]
    print(f"[ok] {name:16} rows={profile['n_rows']:>6} id_like={id_cols} "
          f"cleaned_bytes={len(cleaned.content):>8} {ms} ms")


def main() -> int:
    # ignore_cleanup_errors: the rotating log handler keeps app.log open on Windows
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings.storage_root = Path(tmp) / "storage"
        settings.db_path = settings.storage_root / "app.db"
        from app.main import create_app

        with TestClient(create_app()) as client:
            for name, case in CASES.items():
                run_case(client, name, case)
    print("smoke M0: all samples passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
