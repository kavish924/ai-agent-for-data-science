"""Baseline modeling endpoints (Spec 07, Spec 09 FR-AP-05/20/21)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Body
from pydantic import BaseModel

from ..config import settings
from ..errors import ApiError
from ..services import analyst
from ..storage import artifacts
from ._common import get_row_or_404, load_profile, require_state, transition_or_409

logger = logging.getLogger("models")

router = APIRouter(prefix="/sessions", tags=["models"])

_TRAINABLE = ("executed", "modeled", "reported")
# Executed ops that change a column's values: such a column can't become the target later
_TARGET_CHANGING_OPS = {"impute", "clip_outliers", "cast_type", "drop_column"}


class ModelIn(BaseModel):
    target: str | None = None


def _changed_by_run(session_id: str) -> set[str]:
    """Columns an executed step dropped or changed (Spec 07 FR-ML-15); empty before a run."""
    log_file = artifacts.execution_log_path(settings.storage_root, session_id)
    if not log_file.exists():
        return set()
    changed: set[str] = set()
    for step in json.loads(log_file.read_text(encoding="utf-8")).get("steps", []):
        if step.get("status") != "executed" or step.get("op") not in _TARGET_CHANGING_OPS:
            continue
        if step.get("column"):
            changed.add(step["column"])
        changed.update((step.get("params") or {}).get("columns", []))
    return changed


@router.get("/{session_id}/targets", summary="Ranked target suggestions (FR-AP-21)")
def get_target_suggestions(session_id: str) -> dict:
    row = get_row_or_404(session_id)
    changed = _changed_by_run(session_id)
    suggestions = [
        {**s, "changed_by_plan": s["column"] in changed}
        for s in analyst.suggest_targets(load_profile(session_id, row))
    ]
    return {"session_id": session_id, "suggestions": suggestions}


@router.post("/{session_id}/model", status_code=202,
             summary="Train and compare baseline models in the background (FR-AP-05)")
def train_models(
    session_id: str, background_tasks: BackgroundTasks, body: ModelIn | None = Body(default=None)
) -> dict:
    row = get_row_or_404(session_id)
    require_state(row, _TRAINABLE, "not_trainable", "Models can be trained once the plan has run.")
    target = (body.target if body else None) or row["target"]
    if not target:
        raise ApiError(422, "target_required", "Choose the column to predict.")

    upload, steps = analyst.load_inputs(settings.storage_root, session_id, row)
    if target != row["target"]:  # chosen after planning: the Gate never protected it
        touched = [
            s for s in steps
            if s.get("status") in ("approved", "edited", "user_added")
            and s["op"] in _TARGET_CHANGING_OPS
            and (s.get("column") == target or target in (s.get("params") or {}).get("columns", []))
        ]
        if touched:
            message = f"The plan changed '{target}' ({touched[0]['op']}), so it can't be the target now."
            raise ApiError(422, "target_changed_by_plan", message,
                           details={"steps": [s.get("step_id") for s in touched]})
    try:
        frame, _ = analyst.replay_structural(upload, steps)
        if target not in frame.columns:
            raise analyst.TargetError("invalid_target", f"'{target}' is not in the data after the plan.")
        analyst.problem_type(frame[target], target)
    except analyst.TargetError as exc:
        raise ApiError(422, exc.code, exc.message) from exc

    transition_or_409(session_id, _TRAINABLE, state="modeling", target=target, error=None,
                      failed_stage=None)
    background_tasks.add_task(analyst.run_training, settings.db_path, settings.storage_root,
                              session_id, target, settings.random_seed, settings.model_max_rows)
    logger.info("model.started", extra={"session_id": session_id, "stage": "model"})
    return {"session_id": session_id, "state": "modeling", "target": target,
            "detail": "training started; poll GET /sessions/{id}"}


@router.get("/{session_id}/model", summary="Latest baseline comparison (FR-AP-20)")
def get_model_runs(session_id: str) -> dict:
    get_row_or_404(session_id)
    path = artifacts.model_runs_path(settings.storage_root, session_id)
    if not path.exists():
        raise ApiError(404, "model_not_ready", "No models have been trained for this session yet.")
    runs: dict = json.loads(path.read_text(encoding="utf-8"))
    return runs
