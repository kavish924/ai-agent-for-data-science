"""Execution endpoints: run the approved plan, download deliverables (Specs 05, 09)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from ..config import settings
from ..db import session_store
from ..errors import ApiError
from ..schemas.profile import ProfileOut
from ..services import executor
from ..storage import artifacts
from ._common import EXECUTED_OR_LATER, get_row_or_404, read_plan, require_state

logger = logging.getLogger("execution")

router = APIRouter(prefix="/sessions", tags=["execution"])


# --- execute & deliverables ---------------------------------------------------

@router.post("/{session_id}/execute", status_code=202,
             summary="Run the frozen approved plan (FR-AP-04); no request body")
def execute_plan(session_id: str, background_tasks: BackgroundTasks) -> dict:
    row = get_row_or_404(session_id)
    require_state(row, ("approved",), "not_approved",
                   "Execution requires an approved plan (POST /plan/approve).")
    version = row["plan_version"]
    approved = read_plan(artifacts.plan_version_path(settings.storage_root, session_id,
                                                      version, "approved"))
    if not session_store.transition(settings.db_path, session_id, ("approved",),
                                     state="executing", error=None, failed_stage=None):
        raise ApiError(409, "not_approved", "Execution already started for this plan.",
                       details={"state": get_row_or_404(session_id)["state"]})
    background_tasks.add_task(
        executor.run_execution, settings.db_path, settings.storage_root, session_id,
        [step.model_dump() for step in approved.steps], version,
    )
    logger.info("execute.started", extra={"session_id": session_id, "stage": "execute",
                                          "plan_version": version})
    return {"session_id": session_id, "state": "executing", "plan_version": version,
            "detail": "execution started; poll GET /sessions/{id}"}


@router.get("/{session_id}/execution-log",
            summary="The latest run's execution log, completed or failed (FR-AP-16)")
def get_execution_log(session_id: str) -> dict:
    get_row_or_404(session_id)
    path = artifacts.execution_log_path(settings.storage_root, session_id)
    if not path.exists():
        raise ApiError(404, "execution_log_not_found", "This session has not been executed yet.")
    log: dict = json.loads(path.read_text(encoding="utf-8"))
    return log


def _read_json_or_404(path: Path, code: str, message: str) -> dict:
    if not path.exists():
        raise ApiError(404, code, message)
    data: dict = json.loads(path.read_text(encoding="utf-8"))
    return data


@router.get("/{session_id}/charts", summary="Chart manifest for the latest run (FR-AP-17)")
def get_charts(session_id: str) -> dict:
    get_row_or_404(session_id)
    return _read_json_or_404(artifacts.charts_manifest_path(settings.storage_root, session_id),
                             "charts_not_ready", "Charts are created when a plan has run.")


@router.get("/{session_id}/charts/{file}", response_class=FileResponse,
            summary="One chart PNG listed in the manifest (FR-AP-18)")
def get_chart_file(session_id: str, file: str) -> FileResponse:
    get_row_or_404(session_id)
    manifest_path = artifacts.charts_manifest_path(settings.storage_root, session_id)
    listed = set()
    if manifest_path.exists():
        listed = {c["file"] for c in json.loads(manifest_path.read_text(encoding="utf-8"))["charts"]}
    path = artifacts.charts_dir(settings.storage_root, session_id) / file
    # Only names the manifest lists are served: nothing from the URL becomes a path otherwise
    if file not in listed or not path.is_file():
        raise ApiError(404, "chart_not_found", "No such chart for this session.")
    return FileResponse(path, media_type="image/png")


@router.get("/{session_id}/profile/after", response_model=ProfileOut,
            summary="Profile of the cleaned dataset (FR-AP-19)")
def get_after_profile(session_id: str) -> ProfileOut:
    get_row_or_404(session_id)
    data = _read_json_or_404(artifacts.after_profile_path(settings.storage_root, session_id),
                             "after_profile_not_found", "The cleaned profile is created when a plan has run.")
    return ProfileOut.model_validate(data)


@router.get("/{session_id}/cleaned.csv", response_class=FileResponse,
            summary="Download deliverable 1: the cleaned dataset (FR-AP-15)")
def download_cleaned(session_id: str) -> FileResponse:
    row = get_row_or_404(session_id)
    path = artifacts.cleaned_csv_path(settings.storage_root, session_id, row["original_filename"])
    if row["state"] not in EXECUTED_OR_LATER or not path.exists():
        raise ApiError(404, "cleaned_not_ready", "The cleaned dataset is not available yet.",
                       details={"state": row["state"]})
    return FileResponse(path, media_type="text/csv",
                        filename=artifacts.cleaned_filename(row["original_filename"]))
