"""Session endpoints (Specs 01, 02, 04, 05, 07 FR-ML-10, 09).

Every mutating endpoint is a state transition guarded by the normative state table
in docs/specs/09-api-contracts.md; transitions that race use a conditional update.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Body, File, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..db import session_store
from ..errors import ApiError
from ..schemas.plan import PlanIn
from ..schemas.profile import ProfileOut
from ..schemas.session import SessionOut, TargetIn
from ..services import executor, gate, ingestion, profiler
from ..services.plan_review import ReviewError, assign_ids, reconcile, unreviewed
from ..storage import artifacts

logger = logging.getLogger("sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])

_CHUNK = 1 << 20
_PLANNABLE = ("profiled", "awaiting_approval", "approved")
_REVIEWABLE = ("awaiting_approval", "approved")
_TARGET_SETTABLE = ("profiled", "awaiting_approval")
_EXECUTED_OR_LATER = ("executed", "modeled", "reported")


# --- helpers ------------------------------------------------------------------

def _get_row_or_404(session_id: str) -> dict:
    row = session_store.get_session(settings.db_path, session_id)
    if row is None:
        raise ApiError(404, "session_not_found", f"Session '{session_id}' does not exist.")
    return row


def _require_state(row: dict, allowed: tuple[str, ...], code: str, message: str) -> None:
    if row["state"] not in allowed:
        raise ApiError(409, code, message, details={"state": row["state"]})


def _load_profile(session_id: str, row: dict) -> dict:
    profile_file = artifacts.profile_path(settings.storage_root, session_id)
    if not profile_file.exists():
        raise ApiError(
            409, "profile_pending", "Profile is not available for this session.",
            details={"state": row["state"], "error": row["error"]},
        )
    return json.loads(profile_file.read_text(encoding="utf-8"))


def _read_plan(path) -> PlanIn:
    return PlanIn.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _write_plan(path, plan: PlanIn) -> None:
    path.write_text(plan.model_dump_json(), encoding="utf-8")


def _gate_or_422(plan: PlanIn, profile: dict, target: str | None) -> None:
    issues = gate.validate_plan(plan, profile, target=target)
    if issues:
        raise ApiError(
            422, "invalid_plan", "Plan rejected by the validation gate.", details={"issues": issues}
        )


def _generated_plan(session_id: str, row: dict) -> PlanIn:
    version = row["plan_version"]
    path = artifacts.plan_version_path(settings.storage_root, session_id, version, "generated")
    if version is None or not path.exists():
        raise ApiError(409, "plan_pending", "No plan has been created for this session yet.",
                       details={"state": row["state"]})
    return _read_plan(path)


def _reconcile_or_422(generated: PlanIn, submitted: PlanIn) -> PlanIn:
    try:
        return reconcile(generated, submitted)
    except ReviewError as exc:
        raise ApiError(422, exc.code, exc.message, details=exc.details) from exc


def _transition_or_409(session_id: str, from_states: tuple[str, ...], **fields) -> None:
    if not session_store.transition(settings.db_path, session_id, from_states, **fields):
        row = _get_row_or_404(session_id)
        raise ApiError(409, "state_conflict", "The session changed state; reload and retry.",
                       details={"state": row["state"]})


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
    return SessionOut.from_row(_get_row_or_404(session_id))


@router.get("/{session_id}", response_model=SessionOut,
            summary="Session status for progress polling (FR-AP-07)")
def get_session(session_id: str) -> SessionOut:
    return SessionOut.from_row(_get_row_or_404(session_id))


@router.get("/{session_id}/profile", response_model=ProfileOut,
            summary="Fetch the data profile (FR-AP-02)")
def get_profile(session_id: str) -> ProfileOut:
    row = _get_row_or_404(session_id)
    if row["state"] == "uploaded":
        raise ApiError(409, "profile_pending", "Profiling has not completed for this session.",
                       details={"state": row["state"], "error": row["error"]})
    return ProfileOut.model_validate(_load_profile(session_id, row))


@router.post("/{session_id}/profile", status_code=202,
             summary="Retry profiling after a failure or restart (FR-AP-14)")
def retry_profiling(session_id: str, background_tasks: BackgroundTasks) -> dict:
    row = _get_row_or_404(session_id)
    _require_state(row, ("uploaded",), "not_retryable",
                   "Profiling can only be retried while the session is 'uploaded'.")
    _transition_or_409(session_id, ("uploaded",), error=None, failed_stage=None)
    background_tasks.add_task(
        profiler.run_profiling, settings.db_path, settings.storage_root, session_id
    )
    return {"session_id": session_id, "state": "uploaded", "detail": "profiling restarted"}


@router.put("/{session_id}/target", response_model=SessionOut,
            summary="Choose (or clear) the target column before planning (FR-AP-13)")
def set_target(session_id: str, body: TargetIn) -> SessionOut:
    row = _get_row_or_404(session_id)
    _require_state(row, _TARGET_SETTABLE, "target_locked",
                   "The target can only be changed before the plan is approved.")
    profile = _load_profile(session_id, row)
    if body.target is not None:
        types = {c["name"]: c["type"] for c in profile["columns"]}
        if body.target not in types:
            raise ApiError(422, "invalid_target", f"Unknown column '{body.target}'.")
        if types[body.target] == "id_like":
            raise ApiError(422, "invalid_target",
                           f"'{body.target}' looks like an identifier and cannot be a target.")
        plan_file = artifacts.plan_path(settings.storage_root, session_id)
        if plan_file.exists():
            issues = gate.validate_plan(_read_plan(plan_file), profile, target=body.target)
            if issues:
                raise ApiError(422, "target_conflicts_plan",
                               "The current plan changes this column; edit the plan first.",
                               details={"issues": issues})
    _transition_or_409(session_id, _TARGET_SETTABLE, target=body.target)
    return SessionOut.from_row(_get_row_or_404(session_id))


# --- plan ---------------------------------------------------------------------

@router.get("/{session_id}/plan", response_model=PlanIn,
            summary="Fetch the current review copy of the plan (FR-AP-10)")
def get_plan(session_id: str) -> PlanIn:
    row = _get_row_or_404(session_id)
    plan_file = artifacts.plan_path(settings.storage_root, session_id)
    if not plan_file.exists():
        raise ApiError(409, "plan_pending", "No plan has been created for this session yet.",
                       details={"state": row["state"]})
    return _read_plan(plan_file)


@router.get("/{session_id}/plan/history", summary="All stored plan versions (FR-AP-10)")
def get_plan_history(session_id: str) -> dict:
    _get_row_or_404(session_id)
    versions = [
        {"version": version, "kind": kind,
         "plan": json.loads(path.read_text(encoding="utf-8"))}
        for version, kind, path in artifacts.list_plan_versions(settings.storage_root, session_id)
    ]
    return {"session_id": session_id, "versions": versions}


@router.post("/{session_id}/plan", status_code=201, response_model=PlanIn,
             summary="Create a new plan version (manual in M0; LLM-generated from M3)")
def create_plan(session_id: str, body: PlanIn) -> PlanIn:
    row = _get_row_or_404(session_id)
    _require_state(row, _PLANNABLE, "not_plannable",
                   "A plan can only be created after profiling and before execution.")
    profile = _load_profile(session_id, row)
    version = (row["plan_version"] or 0) + 1
    plan = assign_ids(body).model_copy(update={"version": version})
    _gate_or_422(plan, profile, row["target"])

    _write_plan(artifacts.plan_version_path(settings.storage_root, session_id, version,
                                            "generated"), plan)
    _write_plan(artifacts.plan_path(settings.storage_root, session_id), plan)
    _transition_or_409(session_id, _PLANNABLE, state="awaiting_approval", plan_version=version,
                       error=None, failed_stage=None)
    logger.info("plan.validated", extra={"session_id": session_id, "stage": "plan",
                                         "plan_version": version})
    return plan


@router.put("/{session_id}/plan", response_model=PlanIn,
            summary="Save review edits; statuses are derived server-side (FR-AP-11)")
def save_review(session_id: str, body: PlanIn) -> PlanIn:
    row = _get_row_or_404(session_id)
    _require_state(row, _REVIEWABLE, "not_reviewable", "There is no plan under review.")
    plan = _reconcile_or_422(_generated_plan(session_id, row), body)
    _gate_or_422(plan, _load_profile(session_id, row), row["target"])
    _write_plan(artifacts.plan_path(settings.storage_root, session_id), plan)
    _transition_or_409(session_id, _REVIEWABLE, state="awaiting_approval")
    return plan


@router.post("/{session_id}/plan/approve", response_model=PlanIn,
             summary="Approve the reviewed plan, optionally with final edits (FR-AP-12)")
def approve_plan(session_id: str, body: PlanIn | None = Body(default=None)) -> PlanIn:
    row = _get_row_or_404(session_id)
    _require_state(row, ("awaiting_approval",), "not_approvable",
                   "Approval requires session state 'awaiting_approval'.")
    if body is not None:
        plan = _reconcile_or_422(_generated_plan(session_id, row), body)
    else:
        plan = _read_plan(artifacts.plan_path(settings.storage_root, session_id))
    _gate_or_422(plan, _load_profile(session_id, row), row["target"])
    pending = unreviewed(plan)
    if pending:
        raise ApiError(422, "unreviewed_steps",
                       "Every step must be approved, edited or disabled before approval.",
                       details={"step_ids": pending})

    version = row["plan_version"]
    _write_plan(artifacts.plan_version_path(settings.storage_root, session_id, version,
                                            "approved"), plan)
    _write_plan(artifacts.plan_path(settings.storage_root, session_id), plan)
    _transition_or_409(session_id, ("awaiting_approval",), state="approved")
    logger.info("plan.approved", extra={"session_id": session_id, "stage": "plan",
                                        "plan_version": version})
    return plan


# --- execute & deliverables ---------------------------------------------------

@router.post("/{session_id}/execute", status_code=202,
             summary="Run the frozen approved plan (FR-AP-04); no request body")
def execute_plan(session_id: str, background_tasks: BackgroundTasks) -> dict:
    row = _get_row_or_404(session_id)
    _require_state(row, ("approved",), "not_approved",
                   "Execution requires an approved plan (POST /plan/approve).")
    version = row["plan_version"]
    approved = _read_plan(artifacts.plan_version_path(settings.storage_root, session_id,
                                                      version, "approved"))
    if not session_store.transition(settings.db_path, session_id, ("approved",),
                                     state="executing", error=None, failed_stage=None):
        raise ApiError(409, "not_approved", "Execution already started for this plan.",
                       details={"state": _get_row_or_404(session_id)["state"]})
    background_tasks.add_task(
        executor.run_execution, settings.db_path, settings.storage_root, session_id,
        [step.model_dump() for step in approved.steps], version,
    )
    logger.info("execute.started", extra={"session_id": session_id, "stage": "execute",
                                          "plan_version": version})
    return {"session_id": session_id, "state": "executing", "plan_version": version,
            "detail": "execution started; poll GET /sessions/{id}"}


@router.get("/{session_id}/cleaned.csv", response_class=FileResponse,
            summary="Download deliverable 1: the cleaned dataset (FR-AP-15)")
def download_cleaned(session_id: str) -> FileResponse:
    row = _get_row_or_404(session_id)
    path = artifacts.cleaned_csv_path(settings.storage_root, session_id, row["original_filename"])
    if row["state"] not in _EXECUTED_OR_LATER or not path.exists():
        raise ApiError(404, "cleaned_not_ready", "The cleaned dataset is not available yet.",
                       details={"state": row["state"]})
    return FileResponse(path, media_type="text/csv",
                        filename=artifacts.cleaned_filename(row["original_filename"]))
