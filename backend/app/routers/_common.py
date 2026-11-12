"""Shared router helpers: session lookup, state guards, plan artifact I/O.

Every mutating endpoint is a state transition guarded by the normative state table
in docs/specs/09-api-contracts.md; transitions that race use a conditional update.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from ..db import session_store
from ..errors import ApiError
from ..schemas.plan import PlanIn
from ..services import gate
from ..services.plan_review import ReviewError, reconcile
from ..storage import artifacts

PLANNABLE = ("profiled", "awaiting_approval", "approved")
REVIEWABLE = ("awaiting_approval", "approved")
TARGET_SETTABLE = ("profiled", "awaiting_approval")
EXECUTED_OR_LATER = ("executed", "modeling", "modeled", "reported")


# --- shared helpers ------------------------------------------------------------------

def get_row_or_404(session_id: str) -> dict:
    row = session_store.get_session(settings.db_path, session_id)
    if row is None:
        raise ApiError(404, "session_not_found", f"Session '{session_id}' does not exist.")
    return row


def require_state(row: dict, allowed: tuple[str, ...], code: str, message: str) -> None:
    if row["state"] not in allowed:
        raise ApiError(409, code, message, details={"state": row["state"]})


def load_profile(session_id: str, row: dict) -> dict:
    profile_file = artifacts.profile_path(settings.storage_root, session_id)
    if not profile_file.exists():
        raise ApiError(
            409, "profile_pending", "Profile is not available for this session.",
            details={"state": row["state"], "error": row["error"]},
        )
    return json.loads(profile_file.read_text(encoding="utf-8"))


def read_plan(path: Path) -> PlanIn:
    return PlanIn.model_validate(json.loads(path.read_text(encoding="utf-8")))


def write_plan(path: Path, plan: PlanIn) -> None:
    path.write_text(plan.model_dump_json(), encoding="utf-8")


def gate_or_422(plan: PlanIn, profile: dict, target: str | None) -> None:
    issues = gate.validate_plan(plan, profile, target=target)
    if issues:
        raise ApiError(
            422, "invalid_plan", "Plan rejected by the validation gate.", details={"issues": issues}
        )


def generated_plan(session_id: str, row: dict) -> PlanIn:
    version = row["plan_version"]
    path = artifacts.plan_version_path(settings.storage_root, session_id, version, "generated")
    if version is None or not path.exists():
        raise ApiError(409, "plan_pending", "No plan has been created for this session yet.",
                       details={"state": row["state"]})
    return read_plan(path)


def reconcile_or_422(generated: PlanIn, submitted: PlanIn) -> PlanIn:
    try:
        return reconcile(generated, submitted)
    except ReviewError as exc:
        raise ApiError(422, exc.code, exc.message, details=exc.details) from exc


def transition_or_409(session_id: str, from_states: tuple[str, ...], **fields: object) -> None:
    if not session_store.transition(settings.db_path, session_id, from_states, **fields):
        row = get_row_or_404(session_id)
        raise ApiError(409, "state_conflict", "The session changed state; reload and retry.",
                       details={"state": row["state"]})
