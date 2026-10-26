# Spec 02 — Data Profiler

> **Status:** Draft v0.1 · **Source:** PRD §6.2 · **Milestone:** M1 · **Agent:** Profiler (deterministic, no LLM)

## Purpose

Produce a compact, typed JSON profile of the uploaded dataset — the factual basis for
the cleaning plan and the report's "issues found" section. Runs with no LLM and no
network access.

## User Story

> As a user, I want an accurate summary of my dataset's column types, missing data,
> duplicates, and outliers, so I understand its problems before anything is changed.

## Requirements

| ID | Requirement |
|---|---|
| FR-PR-01 | Infer exactly one type per column: `numeric`, `categorical`, `datetime`, `boolean`, `text`, `id_like`. Rules evaluated in priority order (see §Types below); decision is recorded. |
| FR-PR-02 | Report null count and null percentage per column, and total null cells for the frame. |
| FR-PR-03 | Report duplicate-row count for the frame. |
| FR-PR-04 | Report unique-value count per column; for categorical/text columns, report top-K values with frequencies (default K=10). |
| FR-PR-05 | Detect outliers per numeric column using **IQR** (factor 1.5 default); record the method and factor in the profile. |
| FR-PR-06 | Report basic stats per numeric column: min, max, mean, std. |
| FR-PR-07 | Emit the profile as compact JSON at `storage/sessions/{id}/profile.json`, sized for an LLM prompt (no raw values beyond top-K categories). |
| FR-PR-08 | On completion, set session state `profiled` and record duration. |
| FR-PR-09 | All-empty columns and single-value columns are profiled and flagged (they are valid profile output, not errors). |

### Type inference rules (priority order)

1. All values boolean-like → `boolean`
2. Parseable as datetime (with/without format inference) → `datetime`
3. Numeric parseable (≥ 90% of non-nulls) → `numeric`
4. Near-unique strings (unique/non-null ≥ 0.95) → `id_like`
5. Low cardinality relative to length (e.g., unique ≤ 50 or ≤ 5% of rows) → `categorical`
6. Otherwise → `text`

Exact thresholds live in code, are constants, and are recorded inside the profile for
auditability.

## Interfaces

- **Input:** `upload.csv` + session `encoding`/`delimiter` (Spec 01)
- **Output:** `profile.json` — shape documented in `architecture.md` §3 and validated by
  `schemas/profile.py`; consumed by Planner (Spec 03), Visualizer (Spec 06), Reporter (Spec 08)

## Acceptance Criteria

- **AC-1** Given Titanic-like data, when profiled, then `Age` is `numeric` with
  nulls=177 (19.9%), and `Sex` is `categorical` with top values `male/female`.
- **AC-2** Given a column of unique user IDs as strings, when profiled, then the column
  type is `id_like` (which Spec 07 later refuses as a target).
- **AC-3** Given a column with 12 IQR outliers, when profiled, then `outliers_iqr=12`
  and `outlier_method: {name: "iqr", factor: 1.5}` are present.
- **AC-4** Given a dataset with duplicated rows, when profiled, then `duplicate_rows`
  equals the pandas duplicate count.
- **AC-5** Given any dataset, `profile.json` contains **no full raw rows** (privacy,
  design D2) — only aggregates and top-K values.
- **AC-6** Given a file with an entirely empty column, profiling succeeds and the column
  is flagged (no crash, PRD §7 Reliability).

## Dependencies

- Requires Spec 01 (uploaded file). Blocks Specs 03 (planner input), 06, 08.

## Test Plan

- **Unit:** each type-inference rule with crafted columns; IQR computation vs hand-computed;
  top-K truncation; empty/all-null columns.
- **Golden-file:** run on `samples/` datasets (Titanic, Housing, Telco) and compare
  profile JSON against checked-in golden files (determinism check, PRD §9).

## Out of Scope

- Distribution tests/normality, correlation computation (Spec 06 renders correlations
  at chart time), semantic column meaning ("this looks like an email").

## Open Questions

- None blocking. Datetime inference with mixed formats may need a `parse_datetime`
  plan step to resolve (Spec 03 covers the fix path).
