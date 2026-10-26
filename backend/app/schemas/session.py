"""Session API schemas (Spec 01, Spec 09 FR-AP-01/07)."""

from __future__ import annotations

from pydantic import BaseModel

# Session states (system-guide.md §4); later states arrive with M2+/M3+
STATE_UPLOADED = "uploaded"
STATE_PROFILED = "profiled"


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

    @classmethod
    def from_row(cls, row: dict) -> "SessionOut":
        return cls(**row)
