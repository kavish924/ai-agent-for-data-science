"""Session endpoints: upload+profiling, status, profile (Specs 01, 02, 09)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from ..config import settings
from ..db import session_store
from ..errors import ApiError
from ..schemas.plan import PlanIn
from ..schemas.profile import ProfileOut
from ..schemas.session import SessionOut
from ..services import executor, gate, ingestion, profiler
from ..storage import artifacts

logger = logging.getLogger("sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    status_code=201,
    response_model=SessionOut,
    summary="Upload a CSV and start profiling (FR-AP-01)",
)
async def create_session(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
) -> SessionOut:
    data = await file.read()
    if not data:
        raise ApiError(422, "empty_file", "Uploaded file is empty.")
    if len(data) > settings.max_file_size_mb * 1024 * 1024:
        raise ApiError(
            413,
            "file_too_large",
            f"File exceeds the {settings.max_file_size_mb:g} MB limit.",
        )

    df, encoding, delimiter = ingestion.parse_upload(data)

    if len(df) > settings.max_rows:
        raise ApiError(
            413, "too_many_rows", f"File exceeds the {settings.max_rows} row limit."
        )

    session_id = session_store.new_id()
    artifacts.save_upload(settings.storage_root, session_id, data)
    session_store.create_session(
        settings.db_path,
        session_id=session_id,
        original_filename=file.filename or "upload.csv",
        state="uploaded",
        n_rows=int(len(df)),
        n_columns=int(df.shape[1]),
        encoding=encoding,
        delimiter=delimiter,
        retention_days=settings.retention_days,
    )
    background_tasks.add_task(
        profiler.run_profiling, settings.db_path, settings.storage_root, session_id
    )
    logger.info(
        "session.created",
        extra={"session_id": session_id, "stage": "upload"},
    )
    return SessionOut.from_row(session_store.get_session(settings.db_path, session_id))


@router.get(
    "/{session_id}",
    response_model=SessionOut,
    summary="Session status for progress polling (FR-AP-07)",
)
def get_session(session_id: str) -> SessionOut:
    row = session_store.get_session(settings.db_path, session_id)
    if row is None:
        raise ApiError(404, "session_not_found", f"Session '{session_id}' does not exist.")
    return SessionOut.from_row(row)


@router.get(
    "/{session_id}/profile",
    response_model=ProfileOut,
    summary="Fetch the data profile (FR-AP-02)",
)
def get_profile(session_id: str) -> ProfileOut:
    row = session_store.get_session(settings.db_path, session_id)
    if row is None:
        raise ApiError(404, "session_not_found", f"Session '{session_id}' does not exist.")
    if row["state"] == "uploaded":
        raise ApiError(
            409,
            "profile_pending",
            "Profiling has not completed for this session.",
            details={"state": row["state"], "error": row["error"]},
        )
    profile_file = artifacts.profile_path(settings.storage_root, session_id)
    if not profile_file.exists():
        raise ApiError(404, "profile_not_found", "Profile artifact is missing for this session.")
    return ProfileOut.model_validate(json.loads(profile_file.read_text(encoding="utf-8")))


def _get_row_or_404(session_id: str) -> dict:
    row = session_store.get_session(settings.db_path, session_id)
    if row is None:
        raise ApiError(404, "session_not_found", f"Session '{session_id}' does not exist.")
    return row


def _load_profile(session_id: str, row: dict) -> dict:
    profile_file = artifacts.profile_path(settings.storage_root, session_id)
    if not profile_file.exists():
        raise ApiError(
            409,
            "profile_pending",
            "Profile is not available for this session.",
            details={"state": row["state"]},
        )
    return json.loads(profile_file.read_text(encoding="utf-8"))


@router.get(
    "/{session_id}/plan",
    response_model=PlanIn,
    summary="Fetch the stored plan (consumed by the review UI)",
)
def get_plan(session_id: str) -> PlanIn:
    row = _get_row_or_404(session_id)
    plan_file = artifacts.plan_path(settings.storage_root, session_id)
    if not plan_file.exists():
        if row["state"] in ("uploaded", "profiled"):
            raise ApiError(
                409,
                "plan_pending",
                "No plan has been created for this session yet.",
                details={"state": row["state"]},
            )
        raise ApiError(404, "plan_not_found", "Plan artifact is missing for this session.")
    return PlanIn.model_validate(json.loads(plan_file.read_text(encoding="utf-8")))


@router.post(
    "/{session_id}/plan",
    status_code=201,
    response_model=PlanIn,
    summary="Submit a cleaning plan (manual in M2; LLM generation arrives in M3)",
)
def create_plan(session_id: str, body: PlanIn) -> PlanIn:
    row = _get_row_or_404(session_id)
    if row["state"] not in ("profiled", "awaiting_approval"):
        raise ApiError(
            409,
            "not_plannable",
            "A plan can only be created from 'profiled' or regenerated from 'awaiting_approval'.",
            details={"state": row["state"]},
        )
    profile = _load_profile(session_id, row)
    issues = gate.validate_plan(body, profile)
    if issues:
        raise ApiError(
            422,
            "invalid_plan",
            "Plan rejected by the validation gate.",
            details={"issues": issues},
        )
    artifacts.plan_path(settings.storage_root, session_id).write_text(
        body.model_dump_json(), encoding="utf-8"
    )
    session_store.update_session(
        settings.db_path, session_id, state="awaiting_approval", error=None
    )
    return body


@router.post(
    "/{session_id}/execute",
    status_code=202,
    summary="Run the approved plan (FR-AP-04); the server re-validates every step",
)
def execute_plan(
    session_id: str, body: PlanIn, background_tasks: BackgroundTasks
) -> dict:
    row = _get_row_or_404(session_id)
    if row["state"] != "awaiting_approval":
        raise ApiError(
            409,
            "not_approvable",
            "Execution requires session state 'awaiting_approval'.",
            details={"state": row["state"]},
        )
    profile = _load_profile(session_id, row)
    issues = gate.validate_plan(body, profile)
    if issues:
        raise ApiError(
            422,
            "invalid_plan",
            "Plan rejected by the validation gate.",
            details={"issues": issues},
        )
    # Audit: plan.json stores the approved version of the plan
    artifacts.plan_path(settings.storage_root, session_id).write_text(
        body.model_dump_json(), encoding="utf-8"
    )
    session_store.update_session(settings.db_path, session_id, state="executing", error=None)
    background_tasks.add_task(
        executor.run_execution,
        settings.db_path,
        settings.storage_root,
        session_id,
        [step.model_dump() for step in body.steps],
    )
    logger.info("execute.started", extra={"session_id": session_id, "stage": "execute"})
    return {
        "session_id": session_id,
        "state": "executing",
        "detail": "execution started; poll GET /sessions/{id}",
    }
