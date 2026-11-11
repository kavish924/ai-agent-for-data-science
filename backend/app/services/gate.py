"""Semantic validation of plans against the session profile (the "Schema Gate").

Schema-level validation happens in schemas/plan.py (Pydantic). This module checks the
plan against reality: every referenced column must exist **at that point of the plan**
(running schema, Spec 03 FR-PL-12), each op must be type-compatible with its column,
and the target column is protected (FR-PL-13). Disabled steps are not checked and have
no effect on the running schema - they will not run.
"""

from __future__ import annotations

from typing import Any

from app.schemas.plan import PlanIn

_STRING_TYPES = {"text", "categorical", "id_like"}
_DATETIME_SOURCE_TYPES = {"text", "categorical", "id_like", "datetime"}
_CAST_RESULT_TYPE = {
    "int": "numeric",
    "float": "numeric",
    "str": "text",
    "bool": "boolean",
    "category": "categorical",
}
TARGET_PROTECTED_OPS = {"drop_column", "impute", "clip_outliers", "cast_type"}


def validate_plan(plan: PlanIn, profile: dict, target: str | None = None) -> list[dict]:
    """Return a list of issues (empty = plan is semantically valid)."""
    issues: list[dict] = []
    types: dict[str, str] = {c["name"]: c["type"] for c in profile.get("columns", [])}
    dropped_by: dict[str, int] = {}

    for index, step in enumerate(plan.steps):
        if step.status == "disabled":
            continue

        referenced: list[str] = (
            list(step.params.get("columns", []))
            if step.op == "drop_column"
            else ([step.column] if step.column is not None else [])
        )
        missing = False
        for name in referenced:
            if name in dropped_by:
                issues.append(
                    {"step": index, "issue": f"column '{name}' was dropped by step {dropped_by[name]}"}
                )
                missing = True
            elif name not in types:
                issues.append({"step": index, "issue": f"unknown column '{name}'"})
                missing = True
        if missing:
            continue

        if target is not None and target in referenced and step.op in TARGET_PROTECTED_OPS:
            issues.append({
                "step": index,
                "issue": f"'{target}' is the target column; '{step.op}' may not change it",
            })
            continue

        column_type = types.get(step.column) if step.column else None
        problem = _type_problem(step.op, step.params, step.column, column_type)
        if problem:
            issues.append({"step": index, "issue": problem})
            continue

        # apply the step's effect to the running schema
        if step.op == "drop_column":
            for name in referenced:
                types.pop(name, None)
                dropped_by[name] = index
        elif step.op == "cast_type" and step.column:
            types[step.column] = _CAST_RESULT_TYPE[step.params["to"]]
        elif step.op == "parse_datetime" and step.column:
            types[step.column] = "datetime"

    return issues


def _type_problem(
    op: str, params: dict[str, Any], column: str | None, column_type: str | None
) -> str | None:
    if op == "impute" and params.get("strategy") in ("mean", "median"):
        if column_type != "numeric":
            return f"impute mean/median requires a numeric column; '{column}' is '{column_type}'"
    elif op == "clip_outliers" and column_type != "numeric":
        return f"clip_outliers requires a numeric column; '{column}' is '{column_type}'"
    elif op == "standardize_text" and column_type not in _STRING_TYPES:
        return f"standardize_text requires a text-like column; '{column}' is '{column_type}'"
    elif op == "parse_datetime" and column_type not in _DATETIME_SOURCE_TYPES:
        return f"parse_datetime requires a date-like/text column; '{column}' is '{column_type}'"
    return None
