"""Plan review reconciliation (Spec 04 FR-RV-09/10).

The client is never trusted: a submitted review is compared step by step (by
`step_id`) with the generated plan, and statuses are derived server-side.
"""

from __future__ import annotations

from app.schemas.plan import PlanIn, PlanStep, StepStatus, normalized_params

USER_ADDED_RATIONALE = "Added by the user during review."


class ReviewError(Exception):
    """A submitted review cannot be reconciled with the generated plan (HTTP 422)."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def assign_ids(plan: PlanIn) -> PlanIn:
    """A freshly generated plan: ids s1..sN, every step `proposed`, client ids ignored."""
    steps = [
        step.model_copy(update={"step_id": f"s{i}", "status": "proposed"})
        for i, step in enumerate(plan.steps, start=1)
    ]
    return plan.model_copy(update={"steps": steps})


def reconcile(generated: PlanIn, submitted: PlanIn) -> PlanIn:
    """Derive each step's status from what the user actually changed."""
    originals = {step.step_id: step for step in generated.steps}
    seen: set[str] = set()
    result: list[PlanStep] = []
    user_added = 0

    for step in submitted.steps:
        original = originals.get(step.step_id) if step.step_id else None
        if original is None or original.step_id is None:
            user_added += 1
            result.append(
                step.model_copy(
                    update={
                        "step_id": f"u{user_added}",
                        "status": "disabled" if step.status == "disabled" else "user_added",
                        "rationale": step.rationale or USER_ADDED_RATIONALE,
                    }
                )
            )
            continue

        step_id = original.step_id
        if step_id in seen:
            raise ReviewError(
                "duplicate_step", f"step '{step_id}' appears more than once", {"step_id": step_id}
            )
        seen.add(step_id)
        if step.op != original.op:
            raise ReviewError(
                "op_changed",
                f"step '{step_id}' cannot change its operation; disable it and add a new step",
                {"step_id": step_id},
            )

        changed = step.column != original.column or normalized_params(
            step.op, step.params
        ) != normalized_params(original.op, original.params)
        status: StepStatus
        if step.status == "disabled":
            status = "disabled"
        elif changed:
            status = "edited"
        elif step.status == "proposed":
            status = "proposed"
        else:
            status = "approved"
        result.append(step.model_copy(update={"status": status, "rationale": original.rationale}))

    missing = [sid for sid in originals if sid is not None and sid not in seen]
    if missing:
        raise ReviewError(
            "missing_steps",
            "every proposed step must be present; disable a step instead of removing it",
            {"step_ids": missing},
        )
    return submitted.model_copy(update={"steps": result, "version": generated.version})


def unreviewed(plan: PlanIn) -> list[str]:
    """Step ids still awaiting a decision (approval is blocked while any remain)."""
    return [step.step_id or "?" for step in plan.steps if step.status == "proposed"]
