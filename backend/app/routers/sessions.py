"""Session endpoints: upload, status, profile, profiling retry, target (Specs 01, 02, 07, 09)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from ..config import settings
from ..db import session_store
from ..errors import ApiError
from ..schemas.profile import ProfileOut
from ..schemas.session import SessionOut, TargetIn
from ..services import gate, ingestion, profiler
from ..storage import artifacts
from ._common import (
    TARGET_SETTABLE,
    get_row_or_404,
    load_profile,
    read_plan,
    require_state,
    transition_or_409,
)

logger = logging.getLogger("sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])

_CHUNK = 1 << 20


# --- upload & profile ---------------------------------------------------------

@router.post("", status_code=201, response_model=SessionOut,
             summary="Upload a CSV and start profiling (FR-AP-01)")
async def create_session(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
) -> SessionOut:
    limit = int(settings.max_file_size_mb * 1024 * 1024)
    data = bytearray()
    while chunk := await file.read(_CHUNK):  # FR-UP-11: stop at the cap, never buffer more
        data.extend(chunk)
        if len(data) > limit:
            raise ApiError(413, "file_too_large",
                           f"File exceeds the {settings.max_file_size_mb:g} MB limit.")
    if not data:
        raise ApiError(422, "empty_file", "Uploaded file is empty.")

    df, encoding, delimiter = ingestion.parse_upload(bytes(data))
    if len(df) > settings.max_rows:
        raise ApiError(413, "too_many_rows", f"File exceeds the {settings.max_rows} row limit.")

    session_id = session_store.new_id()
    artifacts.save_upload(settings.storage_root, session_id, bytes(data))
    session_store.create_session(
        settings.db_path,
        session_id=session_id,
        original_filename=artifacts.safe_filename(file.filename or "upload.csv"),
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
    logger.info("session.created", extra={"session_id": session_id, "stage": "upload"})
    return SessionOut.from_row(get_row_or_404(session_id))


@router.get("/{session_id}", response_model=SessionOut,
            summary="Session status for progress polling (FR-AP-07)")
def get_session(session_id: str) -> SessionOut:
    return SessionOut.from_row(get_row_or_404(session_id))


@router.get("/{session_id}/profile", response_model=ProfileOut,
            summary="Fetch the data profile (FR-AP-02)")
def get_profile(session_id: str) -> ProfileOut:
    row = get_row_or_404(session_id)
    if row["state"] == "uploaded":
        raise ApiError(409, "profile_pending", "Profiling has not completed for this session.",
                       details={"state": row["state"], "error": row["error"]})
    return ProfileOut.model_validate(load_profile(session_id, row))


@router.post("/{session_id}/profile", status_code=202,
             summary="Retry profiling after a failure or restart (FR-AP-14)")
def retry_profiling(session_id: str, background_tasks: BackgroundTasks) -> dict:
    row = get_row_or_404(session_id)
    require_state(row, ("uploaded",), "not_retryable",
                   "Profiling can only be retried while the session is 'uploaded'.")
    transition_or_409(session_id, ("uploaded",), error=None, failed_stage=None)
    background_tasks.add_task(
        profiler.run_profiling, settings.db_path, settings.storage_root, session_id
    )
    return {"session_id": session_id, "state": "uploaded", "detail": "profiling restarted"}


@router.put("/{session_id}/target", response_model=SessionOut,
            summary="Choose (or clear) the target column before planning (FR-AP-13)")
def set_target(session_id: str, body: TargetIn) -> SessionOut:
    row = get_row_or_404(session_id)
    require_state(row, TARGET_SETTABLE, "target_locked",
                   "The target can only be changed before the plan is approved.")
    profile = load_profile(session_id, row)
    if body.target is not None:
        types = {c["name"]: c["type"] for c in profile["columns"]}
        if body.target not in types:
            raise ApiError(422, "invalid_target", f"Unknown column '{body.target}'.")
        if types[body.target] == "id_like":
            raise ApiError(422, "invalid_target",
                           f"'{body.target}' looks like an identifier and cannot be a target.")
        plan_file = artifacts.plan_path(settings.storage_root, session_id)
        if plan_file.exists():
            issues = gate.validate_plan(read_plan(plan_file), profile, target=body.target)
            if issues:
                raise ApiError(422, "target_conflicts_plan",
                               "The current plan changes this column; edit the plan first.",
                               details={"issues": issues})
    transition_or_409(session_id, TARGET_SETTABLE, target=body.target)
    return SessionOut.from_row(get_row_or_404(session_id))
