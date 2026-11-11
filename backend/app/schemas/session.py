"""Session API schemas (Spec 01, Spec 09 FR-AP-01/07)."""

from __future__ import annotations

from pydantic import BaseModel

# Session states: normative table in docs/specs/09-api-contracts.md
STATE_UPLOADED = "uploaded"
STATE_PROFILED = "profiled"
STATE_AWAITING_APPROVAL = "awaiting_approval"
STATE_APPROVED = "approved"
STATE_EXECUTING = "executing"
STATE_EXECUTED = "executed"


class SessionOut(BaseModel):
    id: str
    original_filename: str
    state: str
    n_rows: int | None = None
    n_columns: int | None = None
    encoding: str | None = None
    delimiter: str | None = None
    created_at: str
    updated_at: str
    retention_expires_at: str
    error: str | None = None
    failed_stage: str | None = None  # Spec 09 state table
    target: str | None = None  # Spec 07 FR-ML-10
    plan_version: int | None = None

    @classmethod
    def from_row(cls, row: dict) -> SessionOut:
        return cls.model_validate({key: row[key] for key in cls.model_fields if key in row})


class TargetIn(BaseModel):
    target: str | None = None
