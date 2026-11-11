# Spec 02 — Data Profiler

> **Status:** Done · **Source:** PRD §6.2 · **Milestone:** M1 · **Agent:** Profiler (deterministic, no LLM)

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
| FR-PR-10 | *(M0)* Numeric parsing uses one shared helper (`services/numeric.py`) for type inference, stats, and the executor, so a value counted as numeric here (e.g. `"1,234"`) is numeric everywhere. |
| FR-PR-11 | *(M0)* Integer columns that are fully unique and either monotonic (≥ 20 rows) or named like an identifier (`id`, `*_id`, `*Id`, `*ID`) are typed `id_like`, not `numeric`. |
| FR-PR-12 | *(M0, privacy)* The LLM never receives `profile.json` directly; it receives `llm_profile()`, a projection that keeps aggregates and keeps top values **only** for `categorical`/`boolean` columns (≤ 10 values, each ≤ 40 chars). `text` and `id_like` values are never included. |

### Type inference rules (priority order)

1. All values boolean-like → `boolean`
2. Parseable as datetime (with/without format inference) → `datetime`
3. Integer, fully unique, and monotonic or identifier-named → `id_like` (FR-PR-11)
4. Numeric parseable (≥ 90% of non-nulls) → `numeric`
5. Near-unique strings (unique/non-null ≥ 0.95) → `id_like`
6. Low cardinality relative to length (e.g., unique ≤ 50 or ≤ 5% of rows) → `categorical`
7. Otherwise → `text`

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
- **AC-7** *(M0)* Given Titanic, `PassengerId` is typed `id_like`; `Pclass`, `SibSp` and
  `Survived` are not.
- **AC-8** *(M0)* Given a column of `"1,234"`-style values, the profiler types it
  `numeric` and its stats use the parsed values (min 1234, not NaN).
- **AC-9** *(M0)* Given a profile with `text`/`id_like` columns, `llm_profile()` contains
  none of their values; categorical top values are capped at 10 entries of ≤ 40 chars.

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

## Tasks

- [x] FR-PR-01..09 (M1)
- [x] FR-PR-10 shared numeric parsing
- [x] FR-PR-11 integer id_like detection
- [x] FR-PR-12 `llm_profile()` privacy projection

## Changelog

- 2026-11-11 — M0: added FR-PR-10..12 and AC-7..9 (numeric consistency, numeric IDs,
  privacy projection). Fixes a privacy contradiction: top values of text/id_like
  columns were in the profile that the planner would have sent.
- 2026-11-11 — M0 complete: all ACs pass (see `traceability.md`).
