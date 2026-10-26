"""Semantic validation of plans against the session profile (the "Schema Gate").

Schema-level validation happens in schemas/plan.py (Pydantic). This module checks
the plan against reality: every referenced column must exist in the profile and
each operation must be type-compatible with its target column (FR-PL-04/05,
Spec 04 FR-RV-03 server-side re-validation). Disabled steps are not checked —
they will not run.
"""

from __future__ import annotations

from app.schemas.plan import PlanIn

# Type-compatibility rules (design.md §4 whitelist table)
_STRING_TYPES = {"text", "categorical", "id_like"}
_DATETIME_SOURCE_TYPES = {"text", "categorical", "id_like", "datetime"}


def validate_plan(plan: PlanIn, profile: dict) -> list[dict]:
    """Return a list of issues (empty = plan is semantically valid)."""
    issues: list[dict] = []
    types = {column["name"]: column["type"] for column in profile.get("columns", [])}

    for index, step in enumerate(plan.steps):
        if step.status == "disabled":
            continue

        if step.column is not None and step.column not in types:
            issues.append({"step": index, "issue": f"unknown column '{step.column}'"})
            continue

        if step.op == "drop_column":
            for name in step.params.get("columns", []):
                if name not in types:
                    issues.append({"step": index, "issue": f"unknown column '{name}'"})
            continue

        column_type = types.get(step.column)
        if step.op == "impute" and step.params.get("strategy") in ("mean", "median"):
            if column_type != "numeric":
                issues.append({
                    "step": index,
                    "issue": f"impute mean/median requires a numeric column; "
                             f"'{step.column}' is '{column_type}'",
                })
        elif step.op == "clip_outliers" and column_type != "numeric":
            issues.append({
                "step": index,
                "issue": f"clip_outliers requires a numeric column; "
                         f"'{step.column}' is '{column_type}'",
            })
        elif step.op == "standardize_text" and column_type not in _STRING_TYPES:
            issues.append({
                "step": index,
                "issue": f"standardize_text requires a text-like column; "
                         f"'{step.column}' is '{column_type}'",
            })
        elif step.op == "parse_datetime" and column_type not in _DATETIME_SOURCE_TYPES:
            issues.append({
                "step": index,
                "issue": f"parse_datetime requires a date-like/text column; "
                         f"'{step.column}' is '{column_type}'",
            })

    return issues
