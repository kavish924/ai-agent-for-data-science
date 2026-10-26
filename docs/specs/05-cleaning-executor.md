# Spec 05 — Cleaning Executor

> **Status:** Draft v0.1 · **Source:** PRD §6.5 · **Milestone:** M2 · **Agent:** Executor (deterministic)

## Purpose

Apply the **approved** cleaning steps in order with pandas, recording a before/after
audit log per step, and export the cleaned dataset — leaving the original upload
untouched.

## User Story

> As a user, I want the approved steps applied exactly as I approved them, with a
> record of what each step changed, so I can trust and reproduce the result.

## Requirements

| ID | Requirement |
|---|---|
| FR-EX-01 | Execute only steps with status `approved`/`edited` from a session in state `awaiting_approval`; disabled/proposed steps are skipped and logged as such. |
| FR-EX-02 | Apply steps **in plan order**; each step operates on the output of the previous one. |
| FR-EX-03 | For each executed step, log: op, final params, `status`, `rows/cols/null_cells/outliers` before and after. |
| FR-EX-04 | `cast_type` performs a **dry-run validation** before mutating; if the cast would error on observed values, the step aborts per FR-EX-05 before any change. |
| FR-EX-05 | On step failure: stop execution, persist the log of completed steps, mark the session `error` with the failing step and reason; completed-step changes remain in the working artifact but no cleaned deliverable is exported until a run fully succeeds. |
| FR-EX-06 | The original `upload.csv` is never modified (verified by content hash before/after). |
| FR-EX-07 | On success, export `cleaned_<original_name>.csv` preserving original column names and order unless an approved `drop_column` removed columns. |
| FR-EX-08 | Determinism: same input CSV + same approved plan + same tool versions ⇒ byte-identical cleaned CSV (seeded ops only; no timestamps in data). |
| FR-EX-09 | Frame-level ops (`drop_duplicates`) log the same before/after fields with `column: null`. |
| FR-EX-10 | On success, session state → `executed` with duration recorded. |

### Operation semantics (normative)

| Op | Implementation (pandas) |
|---|---|
| `drop_duplicates` | `df.drop_duplicates()` (default keep=first) |
| `drop_column` | `df.drop(columns=[...])`; missing column → step failure |
| `impute` | mean/median → numeric; mode → any; constant → provided value |
| `clip_outliers` | IQR fences at Q1−f·IQR / Q3+f·IQR, clip (same method as profiler) |
| `cast_type` | dry-run `astype` on a copy first, then commit |
| `parse_datetime` | `pd.to_datetime(errors="coerce")`; unparseable values become nulls and are counted in the log |
| `standardize_text` | apply selected ops (trim / lowercase / collapse spaces) |

## Interfaces

- **Input:** `upload.csv` + approved steps (from Spec 04 submission)
- **Output:** `cleaned_<name>.csv` artifact, `execution_log.json`; consumed by Specs
  06 (charts), 07 (models), 08 (report)

## Acceptance Criteria

- **AC-1** Given an approved 3-step plan, when executed, then steps run in order and the
  log has 3 entries each with before/after counts.
- **AC-2** Given a disabled step 2 of 4, then the log has 4 entries: 3 executed + step 2
  recorded as `disabled` (no changes from it).
- **AC-3** Given `cast_type(to=int)` on a column containing `"abc"`, then the dry-run
  fails, execution aborts, the session is `error`, and `upload.csv` is unchanged.
- **AC-4** Given any full run, then SHA-256 of `upload.csv` is identical before and after.
- **AC-5** Given approved `drop_column(X)`, then the cleaned CSV lacks X and other
  columns retain original names and relative order.
- **AC-6** Given the same CSV and plan executed twice, then the two cleaned CSVs are
  byte-identical (PRD §9 Reproducibility).
- **AC-7** Given `parse_datetime` over mixed junk dates, then unparseable entries become
  null and the log reports the count introduced.

## Dependencies

- Requires Spec 01 (upload) and an approved plan via Spec 04's submit path. Feeds
  Specs 06–08. No LLM involvement.

## Test Plan

- **Unit:** each op against crafted frames incl. edge cases (all-null column, constant
  column, mode ties, IQR fences); dry-run cast success/failure.
- **Integration:** full happy path; disabled-step path; abort path (AC-3) with log
  persistence; determinism double-run (AC-6); immutability hash check (AC-4).

## Out of Scope

- Per-step undo/redo (stretch), step reordering, interactive partial re-execution
  (v1 re-runs the whole approved plan), chunked execution for huge files.

## Open Questions

- ~~Retry semantics~~ **Resolved:** full plan re-run on failure in v1 (simpler,
  deterministic); retry-from-failed-step is a fast-follow.
