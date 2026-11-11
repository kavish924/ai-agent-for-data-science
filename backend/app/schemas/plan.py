"""Plan schemas: the operation whitelist (Spec 03 §4, Spec 05, design.md §4).

Schema-level validation lives here (Pydantic); semantic validation against the
session profile (column existence, type compatibility) lives in services/gate.py.
Unknown ops, unknown params, and param type mismatches are rejected at this layer.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SCHEMA_VERSION = "v1"

WhitelistOp = Literal[
    "drop_duplicates",
    "drop_column",
    "impute",
    "clip_outliers",
    "cast_type",
    "parse_datetime",
    "standardize_text",
]

# proposed: awaiting a decision (never executes) · approved / edited / user_added: run
# disabled: recorded but skipped (Spec 04 FR-RV-06/09)
StepStatus = Literal["proposed", "approved", "edited", "disabled", "user_added"]
EXECUTABLE_STATUSES = frozenset({"approved", "edited", "user_added"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown params are rejected (FR-PL-03)


class DropDuplicatesParams(_Strict):
    pass


class DropColumnParams(_Strict):
    columns: list[str] = Field(min_length=1)


class ImputeParams(_Strict):
    strategy: Literal["mean", "median", "mode", "constant"]
    value: str | int | float | bool | None = None

    @model_validator(mode="after")
    def _constant_value_rule(self) -> ImputeParams:
        if self.strategy == "constant" and self.value is None:
            raise ValueError("'value' is required when strategy is 'constant'")
        if self.strategy != "constant" and self.value is not None:
            raise ValueError("'value' is only allowed when strategy is 'constant'")
        return self


class ClipOutliersParams(_Strict):
    method: Literal["iqr"] = "iqr"
    factor: float = Field(default=1.5, gt=0)


class CastTypeParams(_Strict):
    to: Literal["int", "float", "str", "bool", "category"]


class ParseDatetimeParams(_Strict):
    format: str | None = None


class StandardizeTextParams(_Strict):
    ops: list[Literal["trim", "lowercase", "collapse_spaces"]] = Field(min_length=1)


PARAM_MODELS: dict[str, type[BaseModel]] = {
    "drop_duplicates": DropDuplicatesParams,
    "drop_column": DropColumnParams,
    "impute": ImputeParams,
    "clip_outliers": ClipOutliersParams,
    "cast_type": CastTypeParams,
    "parse_datetime": ParseDatetimeParams,
    "standardize_text": StandardizeTextParams,
}

# Ops that target a single column; the others are frame-level
COLUMN_OPS = {"impute", "clip_outliers", "cast_type", "parse_datetime", "standardize_text"}

# Spec 07 FR-ML-11: statistical ops are fit on data, so modeling re-creates them inside
# the sklearn Pipeline instead of replaying them on the full dataset (no leakage).
OP_CLASS: dict[str, Literal["structural", "statistical"]] = {
    "drop_duplicates": "structural",
    "drop_column": "structural",
    "cast_type": "structural",
    "parse_datetime": "structural",
    "standardize_text": "structural",
    "impute": "statistical",
    "clip_outliers": "statistical",
}


def normalized_params(op: str, params: dict[str, Any]) -> dict[str, Any]:
    """Params with defaults filled in, for comparing two versions of a step."""
    return PARAM_MODELS[op].model_validate(params).model_dump()


class PlanStep(BaseModel):
    step_id: str | None = Field(default=None, max_length=32)  # assigned by the server
    op: WhitelistOp
    column: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = "proposed"  # no explicit decision => never approved (FR-RV-10)
    rationale: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _validate_shape(self) -> PlanStep:
        if self.op == "drop_duplicates" and self.column is not None:
            raise ValueError("'drop_duplicates' is frame-level; 'column' must be null")
        if self.op == "drop_column" and self.column is not None:
            raise ValueError("'drop_column' takes 'columns' in params; 'column' must be null")
        if self.op in COLUMN_OPS and not self.column:
            raise ValueError(f"op '{self.op}' requires a 'column'")
        try:
            PARAM_MODELS[self.op].model_validate(self.params)
        except ValidationError as exc:
            raise ValueError(f"invalid params for op '{self.op}': {exc}") from exc
        return self


class PlanIn(BaseModel):
    """A full plan: as generated (M3), as submitted for review, and as approved (execute)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"] = "v1"
    version: int | None = None  # plan version number, set by the server (FR-AP-03)
    steps: list[PlanStep] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_schema_alias(cls, data: Any) -> Any:
        # Accept the PRD's {"schema": "v1"} spelling alongside schema_version
        if isinstance(data, dict) and "schema" in data and "schema_version" not in data:
            data = dict(data)  # copy before mutating
            data["schema_version"] = data.pop("schema")
        return data
