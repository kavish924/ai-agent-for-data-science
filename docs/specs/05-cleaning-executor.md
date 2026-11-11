# Spec 05 — Cleaning Executor

> **Status:** Done · **Source:** PRD §6.5 · **Milestone:** M2 · **Agent:** Executor (deterministic)

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
| FR-EX-01 | *(rev. M0)* Execute the **frozen approved plan** (`plans/v{n}.approved.json`) of a session in state `approved`; the execute request has no body. Steps with status `approved`/`edited`/`user_added` run; `disabled` steps are skipped and logged as such. |
| FR-EX-02 | Apply steps **in plan order**; each step operates on the output of the previous one. |
| FR-EX-03 | For each executed step, log: op, final params, `status`, `rows/cols/null_cells/outliers` before and after. |
| FR-EX-04 | `cast_type` performs a **dry-run validation** before mutating; if the cast would error on observed values, the step aborts per FR-EX-05 before any change. |
| FR-EX-05 | *(rev. M0)* On step failure: stop execution, persist the log of completed steps, and return the session to `awaiting_approval` with `error` (failing step + reason) and `failed_stage=execute`, so the plan can be edited and re-approved. No cleaned deliverable is exported until a run fully succeeds. |
| FR-EX-06 | The original `upload.csv` is never modified (verified by content hash before/after). |
| FR-EX-07 | On success, export `cleaned_<original_name>.csv` preserving original column names and order unless an approved `drop_column` removed columns. |
| FR-EX-08 | Determinism: same input CSV + same approved plan + same tool versions ⇒ byte-identical cleaned CSV (seeded ops only; no timestamps in data). |
| FR-EX-09 | Frame-level ops (`drop_duplicates`) log the same before/after fields with `column: null`. |
| FR-EX-10 | On success, session state → `executed` with duration recorded. |
| FR-EX-11 | *(M0)* **Any** exception during execution (not only step errors, e.g. an unreadable upload) is handled per FR-EX-05; a session can never remain stuck in `executing`. |
| FR-EX-12 | *(M0)* `cast_type` semantics: `int` parses strictly and uses nullable `Int64` (nulls allowed; non-integral or unparseable values fail the step); `float` parses strictly; `bool` maps only boolean-like values (`true/false/yes/no/y/n/1/0`, case-insensitive) and fails on anything else — never Python truthiness. |
| FR-EX-13 | *(M0)* `impute(mean/median)` and `clip_outliers` use the shared numeric parser (Spec 02 FR-PR-10). Values that don't parse are **kept unchanged** and counted in the step's `notes.unparseable_kept`; no value is silently turned into null. |

### Operation semantics (normative)

| Op | Implementation (pandas) |
|---|---|
| `drop_duplicates` | `df.drop_duplicates()` (default keep=first) |
| `drop_column` | `df.drop(columns=[...])`; missing column → step failure |
| `impute` | mean/median → numeric; mode → any; constant → provided value |
| `clip_outliers` | IQR fences at Q1−f·IQR / Q3+f·IQR, clip (same method as profiler) |
| `cast_type` | strict parse on a copy first (FR-EX-12), then commit |
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
- **AC-8** *(M0)* Given `cast_type(to=bool)` on `["True","False","no"]`, the result is
  `[True, False, False]`; on `["yes","maybe"]` the step fails.
- **AC-9** *(M0)* Given `cast_type(to=int)` on `[1.0, null]` the result is `[1, <NA>]`;
  on `[1.5]` the step fails.
- **AC-10** *(M0)* Given `clip_outliers` on `["1,000", "2", ..., "n/a"]`, parsed values
  are clipped, `"n/a"` is kept, and `notes.unparseable_kept == 1`.
- **AC-11** *(M0)* Given an unexpected exception inside execution, the session ends in
  `awaiting_approval` with `failed_stage=execute` and an error; never `executing`.

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

## Tasks

- [x] FR-EX-02..04, 06..10 (M2)
- [x] FR-EX-01 run frozen approved plan (no request body)
- [x] FR-EX-05 failure → `awaiting_approval` + `failed_stage`
- [x] FR-EX-11 catch-all failure handling
- [x] FR-EX-12 strict cast semantics
- [x] FR-EX-13 non-destructive numeric ops

## Changelog

- 2026-11-11 — M0: FR-EX-01/05 revised for the explicit approve step; added
  FR-EX-11..13 and AC-8..11. Fixes: `"False"` cast to `True`; numeric ops turned
  unparseable values into nulls; non-step exceptions left sessions in `executing`.
- 2026-11-11 — M0 complete: all ACs pass (see `traceability.md`).
