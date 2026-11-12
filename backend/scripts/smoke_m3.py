"""End-to-end smoke test for M3: the LLM generates the cleaning plan.

upload -> profile -> target -> POST /plan (no body: LLM) -> approve -> execute -> download,
on every sample dataset, in-process with a temporary storage root.

Usage (from backend/):
    python scripts/smoke_m3.py          # offline: deterministic RuleBasedLLM
    python scripts/smoke_m3.py --live   # real Gemini (needs GEMINI_API_KEY in .env)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import session_store  # noqa: E402
from app.llm.fake import RuleBasedLLM  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
TARGETS = {"titanic.csv": "Survived", "housing.csv": "median_house_value", "telco_churn.csv": "Churn"}


def run_case(client: TestClient, name: str, target: str) -> None:
    started = time.perf_counter()
    raw = (SAMPLES / name).read_bytes()
    sid = client.post("/api/v1/sessions", files={"file": (name, raw, "text/csv")}).json()["id"]
    base = f"/api/v1/sessions/{sid}"
    assert client.put(f"{base}/target", json={"target": target}).status_code == 200

    created = client.post(f"{base}/plan")  # no body: the LLM plans
    assert created.status_code == 201, created.json()
    plan = created.json()
    review = {"steps": [{**s, "status": "approved"} for s in plan["steps"]]}
    approved = client.post(f"{base}/plan/approve", json=review)
    assert approved.status_code == 200, approved.json()
    assert client.post(f"{base}/execute").status_code == 202

    status = client.get(base).json()
    assert status["state"] == "executed", status
    assert client.get(f"{base}/cleaned.csv").status_code == 200
    stored = (settings.storage_root / "sessions" / sid / "upload.csv").read_bytes()
    assert hashlib.sha256(stored).digest() == hashlib.sha256(raw).digest(), "upload modified!"

    charts = client.get(f"{base}/charts").json()  # M4: charts come with every run
    assert charts["status"] == "completed" and charts["charts"], charts
    assert client.get(f"{base}/profile/after").status_code == 200

    calls = session_store.list_llm_calls(settings.db_path, sid)
    ops = ", ".join(f"{s['op']}({s.get('column') or ''})" for s in plan["steps"]) or "no steps"
    ms = int((time.perf_counter() - started) * 1000)
    print(f"[ok] {name:16} attempts={len(calls)} valid_first={bool(calls[0]['valid'])} "
          f"charts={len(charts['charts'])} {ms} ms")
    print(f"     plan: {ops}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="use real Gemini instead of the fake")
    args = parser.parse_args()
    if args.live and not settings.gemini_api_key:
        print("--live needs GEMINI_API_KEY (in the repo-root .env)")
        return 2

    # ignore_cleanup_errors: the rotating log handler keeps app.log open on Windows
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings.storage_root = Path(tmp) / "storage"
        settings.db_path = settings.storage_root / "app.db"
        from app.main import create_app
        from app.routers.plans import get_llm

        app = create_app()
        if not args.live:
            app.dependency_overrides[get_llm] = RuleBasedLLM
        with TestClient(app) as client:
            for name, target in TARGETS.items():
                run_case(client, name, target)
    print(f"smoke M3 ({'live Gemini' if args.live else 'offline fake LLM'}): all samples passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
