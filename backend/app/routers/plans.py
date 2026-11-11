"""Plan endpoints: create a version, review, approve, history (Specs 03, 04, 09)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Body, Depends

from ..config import settings
from ..db import session_store
from ..errors import ApiError
from ..llm.client import LLMClient
from ..schemas.plan import PlanIn
from ..services import planner
from ..services.plan_review import assign_ids, unreviewed
from ..storage import artifacts
from ._common import (
    PLANNABLE,
    REVIEWABLE,
    gate_or_422,
    generated_plan,
    get_row_or_404,
    load_profile,
    read_plan,
    reconcile_or_422,
    require_state,
    transition_or_409,
    write_plan,
)

logger = logging.getLogger("plans")

router = APIRouter(prefix="/sessions", tags=["plans"])


# --- plan ---------------------------------------------------------------------

@router.get("/{session_id}/plan", response_model=PlanIn,
            summary="Fetch the current review copy of the plan (FR-AP-10)")
def get_plan(session_id: str) -> PlanIn:
    row = get_row_or_404(session_id)
    plan_file = artifacts.plan_path(settings.storage_root, session_id)
    if not plan_file.exists():
        raise ApiError(409, "plan_pending", "No plan has been created for this session yet.",
                       details={"state": row["state"]})
    return read_plan(plan_file)


@router.get("/{session_id}/plan/history", summary="All stored plan versions (FR-AP-10)")
def get_plan_history(session_id: str) -> dict:
    get_row_or_404(session_id)
    versions = [
        {"version": version, "kind": kind,
         "plan": json.loads(path.read_text(encoding="utf-8"))}
        for version, kind, path in artifacts.list_plan_versions(settings.storage_root, session_id)
    ]
    return {"session_id": session_id, "versions": versions}


def get_llm() -> LLMClient | None:
    """FastAPI dependency: the configured LLM client, or None without an API key.

    Tests replace it via `app.dependency_overrides[get_llm]`.
    """
    if not settings.gemini_api_key:
        return None
    from ..llm.gemini import GeminiClient  # imported lazily: SDK only needed when used

    return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model,
                        seed=settings.random_seed, timeout_s=settings.llm_timeout_s)


@router.post("/{session_id}/plan", status_code=201, response_model=PlanIn,
             summary="Create a new plan version: LLM-generated without a body, manual with one")
def create_plan(
    session_id: str,
    body: PlanIn | None = Body(default=None),
    llm: LLMClient | None = Depends(get_llm),
) -> PlanIn:
    row = get_row_or_404(session_id)
    require_state(row, PLANNABLE, "not_plannable",
                   "A plan can only be created after profiling and before execution.")
    profile = load_profile(session_id, row)
    if body is None:  # Spec 03 FR-PL-14: LLM generation
        if llm is None:
            raise ApiError(503, "llm_not_configured",
                           "Plan generation needs GEMINI_API_KEY; submit a manual plan instead.")
        logger.info("plan.requested", extra={"session_id": session_id, "stage": "plan"})
        try:
            body = planner.generate_plan(
                llm, profile, target=row["target"], max_retries=settings.plan_max_retries,
                db_path=settings.db_path, session_id=session_id,
            )
        except planner.PlanningFailed as exc:  # FR-PL-08: visible, state kept, retryable
            message = f"planning failed after {exc.attempts} attempt(s)"
            session_store.update_session(settings.db_path, session_id, error=message,
                                         failed_stage="plan")
            logger.warning("plan.rejected", extra={"session_id": session_id, "stage": "plan",
                                                   "attempt": exc.attempts})
            raise ApiError(502, "planner_failed",
                           "The planner could not produce a valid plan. Try again.",
                           details={"attempts": exc.attempts, "issues": exc.issues[:10]}) from exc
    version = (row["plan_version"] or 0) + 1
    plan = assign_ids(body).model_copy(update={"version": version})
    gate_or_422(plan, profile, row["target"])

    write_plan(artifacts.plan_version_path(settings.storage_root, session_id, version,
                                            "generated"), plan)
    write_plan(artifacts.plan_path(settings.storage_root, session_id), plan)
    transition_or_409(session_id, PLANNABLE, state="awaiting_approval", plan_version=version,
                       error=None, failed_stage=None)
    logger.info("plan.validated", extra={"session_id": session_id, "stage": "plan",
                                         "plan_version": version})
    return plan


@router.put("/{session_id}/plan", response_model=PlanIn,
            summary="Save review edits; statuses are derived server-side (FR-AP-11)")
def save_review(session_id: str, body: PlanIn) -> PlanIn:
    row = get_row_or_404(session_id)
    require_state(row, REVIEWABLE, "not_reviewable", "There is no plan under review.")
    plan = reconcile_or_422(generated_plan(session_id, row), body)
    gate_or_422(plan, load_profile(session_id, row), row["target"])
    write_plan(artifacts.plan_path(settings.storage_root, session_id), plan)
    transition_or_409(session_id, REVIEWABLE, state="awaiting_approval")
    return plan


@router.post("/{session_id}/plan/approve", response_model=PlanIn,
             summary="Approve the reviewed plan, optionally with final edits (FR-AP-12)")
def approve_plan(session_id: str, body: PlanIn | None = Body(default=None)) -> PlanIn:
    row = get_row_or_404(session_id)
    require_state(row, ("awaiting_approval",), "not_approvable",
                   "Approval requires session state 'awaiting_approval'.")
    if body is not None:
        plan = reconcile_or_422(generated_plan(session_id, row), body)
    else:
        plan = read_plan(artifacts.plan_path(settings.storage_root, session_id))
    gate_or_422(plan, load_profile(session_id, row), row["target"])
    pending = unreviewed(plan)
    if pending:
        raise ApiError(422, "unreviewed_steps",
                       "Every step must be approved, edited or disabled before approval.",
                       details={"step_ids": pending})

    version = row["plan_version"]
    write_plan(artifacts.plan_version_path(settings.storage_root, session_id, version,
                                            "approved"), plan)
    write_plan(artifacts.plan_path(settings.storage_root, session_id), plan)
    transition_or_409(session_id, ("awaiting_approval",), state="approved")
    logger.info("plan.approved", extra={"session_id": session_id, "stage": "plan",
                                        "plan_version": version})
    return plan
