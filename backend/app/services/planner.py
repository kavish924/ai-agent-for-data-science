"""LLM cleaning planner with a bounded validate-and-retry loop (Spec 03).

    generate -> parse JSON -> Pydantic schema -> rationale check -> Gate
             -> (rejected: feed the issues back, retry) <= max_retries -> fail visibly

The LLM only proposes. Its output never executes: an accepted plan is stored with every
step `proposed` and still needs the user's explicit approval (Spec 04).
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from pydantic import ValidationError

from ..db import session_store
from ..llm.client import LLMClient, LLMError
from ..llm.prompts import SYSTEM_PROMPT, build_plan_prompt
from ..schemas.plan import PlanIn
from .gate import validate_plan
from .profiler import llm_profile

logger = logging.getLogger("planner")

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class PlanningFailed(Exception):
    """No valid plan after the retry budget (Spec 03 FR-PL-08)."""

    def __init__(self, attempts: int, issues: list[str]):
        self.attempts = attempts
        self.issues = issues
        super().__init__(f"no valid plan after {attempts} attempt(s)")


class _Rejected(Exception):
    def __init__(self, error_class: str, issues: list[str]):
        self.error_class = error_class
        self.issues = issues
        super().__init__(error_class)


def _parse(text: str) -> PlanIn:
    """LLM text -> PlanIn, or _Rejected with issues phrased for a re-prompt."""
    fenced = _FENCE.match(text)
    try:
        data = json.loads(fenced.group(1) if fenced else text)
    except json.JSONDecodeError as exc:
        raise _Rejected("invalid_json", [f"the answer was not valid JSON ({exc.msg})"]) from exc
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list):
        raise _Rejected("schema_invalid", ['the answer must be an object with a "steps" list'])
    try:
        return PlanIn.model_validate({"schema_version": "v1", "steps": steps})
    except ValidationError as exc:
        issues = []
        for error in exc.errors():
            where = ".".join(str(part) for part in error["loc"])
            message = f"{where}: {error['msg']}"
            # Echo a rejected op name so the model knows what to replace. This is the
            # model's own output (never user data); other inputs are not echoed.
            if error["loc"][-1:] == ("op",) and isinstance(error.get("input"), str):
                message += f" (got {error['input'][:40]!r})"
            issues.append(message)
        raise _Rejected("schema_invalid", issues) from exc


def _check(plan: PlanIn, profile: dict, target: str | None) -> None:
    missing = [i for i, step in enumerate(plan.steps) if not (step.rationale or "").strip()]
    if missing:
        raise _Rejected(
            "missing_rationale",
            [f"step {i}: a non-empty rationale citing profile facts is required" for i in missing],
        )
    gate_issues = validate_plan(plan, profile, target=target)
    if gate_issues:
        raise _Rejected(
            "gate_rejected", [f"step {issue['step']}: {issue['issue']}" for issue in gate_issues]
        )


def generate_plan(
    client: LLMClient,
    profile: dict,
    *,
    target: str | None,
    max_retries: int,
    db_path: Path,
    session_id: str,
) -> PlanIn:
    """Ask the LLM for a plan until one passes every check, or raise PlanningFailed."""
    projected = llm_profile(profile, target=target)  # FR-PL-01: the only data in a prompt
    issues: list[str] = []
    attempts = max(1, max_retries)

    for attempt in range(1, attempts + 1):
        prompt = build_plan_prompt(projected, issues or None)
        started = time.perf_counter()
        prompt_tokens = output_tokens = None
        model: str | None = getattr(client, "model", None)
        error_class: str | None = None
        plan: PlanIn | None = None
        try:
            response = client.generate_json(system=SYSTEM_PROMPT, prompt=prompt)
            model, prompt_tokens, output_tokens = (
                response.model, response.prompt_tokens, response.output_tokens
            )
            plan = _parse(response.text)
            _check(plan, profile, target)
        except LLMError as exc:  # FR-PL-16: transport failures use the same budget
            error_class = f"transport:{type(exc).__name__}"
            issues = ["the previous request failed; please answer again"]
            plan = None
        except _Rejected as exc:
            error_class, issues, plan = exc.error_class, exc.issues, None

        duration_ms = int((time.perf_counter() - started) * 1000)
        session_store.record_llm_call(
            db_path, session_id=session_id, stage="planner", attempt=attempt,
            valid=plan is not None, error=error_class, model=model,
            prompt_tokens=prompt_tokens, output_tokens=output_tokens, duration_ms=duration_ms,
        )
        logger.info(
            "llm.call",
            extra={"session_id": session_id, "stage": "planner", "attempt": attempt,
                   "valid": plan is not None, "model": model, "prompt_tokens": prompt_tokens,
                   "output_tokens": output_tokens, "duration_ms": duration_ms,
                   "error": error_class, "issue_count": 0 if plan else len(issues)},
        )
        if plan is not None:
            return plan

    raise PlanningFailed(attempts, issues)
