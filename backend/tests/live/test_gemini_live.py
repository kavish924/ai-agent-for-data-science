"""Live Gemini check (Spec 03). Excluded from CI; runs only with GEMINI_API_KEY set.

    pytest -m live
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.db import session_store
from app.llm.gemini import GeminiClient
from app.services.gate import validate_plan
from app.services.planner import generate_plan
from app.services.profiler import profile_dataframe

pytestmark = pytest.mark.live

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


@pytest.mark.skipif(not settings.gemini_api_key, reason="GEMINI_API_KEY not set")
def test_live_gemini_plans_titanic(tmp_path):
    db = tmp_path / "app.db"
    session_store.init_db(db)
    session_store.create_session(db, session_id="live", original_filename="t.csv", state="profiled")
    profile = profile_dataframe("live", pd.read_csv(SAMPLES / "titanic.csv"))

    client = GeminiClient(api_key=settings.gemini_api_key or "", model=settings.gemini_model,
                          seed=settings.random_seed, timeout_s=settings.llm_timeout_s)
    plan = generate_plan(client, profile, target="Survived", max_retries=3, db_path=db,
                         session_id="live")

    assert plan.steps
    assert validate_plan(plan, profile, target="Survived") == []
    assert all((step.rationale or "").strip() for step in plan.steps)
