"""Profile API schema (Spec 02, architecture.md §3 example)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopValue(BaseModel):
    value: str
    count: int


class NumericStats(BaseModel):
    min: float
    max: float
    mean: float
    std: float


class ColumnProfile(BaseModel):
    name: str
    type: str = Field(pattern="^(numeric|categorical|datetime|boolean|text|id_like)$")
    nulls: int
    null_pct: float
    unique: int
    top_values: list[TopValue] = Field(default_factory=list)
    outliers_iqr: int | None = None
    stats: NumericStats | None = None
    flags: list[str] = Field(default_factory=list)


class ProfileOut(BaseModel):
    session_id: str
    n_rows: int
    n_columns: int
    duplicate_rows: int
    total_null_cells: int
    inference: dict
    columns: list[ColumnProfile]
    issues: dict
