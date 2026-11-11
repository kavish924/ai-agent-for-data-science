# Spec 03 — Cleaning Planner (LLM)

> **Status:** Approved (Gate rules FR-PL-12/13 built in M0; LLM in M3) · **Source:** PRD §6.3, §10 · **Milestone:** M3 · **Agent:** Planner (LLM) + Schema Gate (deterministic)

## Purpose

Turn the data profile into a structured, reviewable cleaning plan: an ordered list of
whitelisted operations, each with parameters and a short rationale. The LLM proposes;
code validates; nothing executes here.

## User Story

> As a user, I want a proposed cleaning plan with a reason for every step, so I can
> decide what happens to my data before anything changes.

## Requirements

| ID | Requirement |
|---|---|
| FR-PL-01 | Send **only `llm_profile()`** (Spec 02 FR-PR-12) to the LLM (design D2). Raw rows and raw values beyond profile aggregates MUST NOT be included in any prompt. |
| FR-PL-02 | Output MUST conform to plan schema `v1`: `{"schema":"v1","steps":[{op, column, params, rationale}, …]}` — validated by Pydantic. |
| FR-PL-03 | `op` MUST be one of the whitelist: `drop_duplicates`, `drop_column`, `impute`, `clip_outliers`, `cast_type`, `parse_datetime`, `standardize_text`. Any other value is rejected by the Gate. |
| FR-PL-04 | Params MUST satisfy per-op constraints (see §Whitelist); type-incompatible ops (e.g., `impute(mean)` on text) are rejected. |
| FR-PL-05 | Referenced columns MUST exist in the profile. |
| FR-PL-06 | Every step MUST include a non-empty `rationale` referencing profile facts. |
| FR-PL-07 | On Gate rejection, re-prompt the LLM with the validation error, up to `PLAN_MAX_RETRIES` (default 3). Each attempt is logged to `llm_calls` (valid/error/attempts — never payloads). |
| FR-PL-08 | After exhausting retries without a valid plan, the stage fails visibly; session remains `profiled` with a recorded error; user may retry. |
| FR-PL-09 | The validated plan is stored at `storage/sessions/{id}/plan.json` and the session moves to `planned` → `awaiting_approval` once presented. |
| FR-PL-10 | Generation parameters: low temperature; deterministic seed where supported. |
| FR-PL-11 | The Gate and whitelist are versioned in code; the plan records `"schema":"v1"` for forward compatibility. |
| FR-PL-12 | *(M0)* The Gate validates each step against the **running schema**: the column set and types after all earlier enabled steps (`drop_column` removes columns; `cast_type`/`parse_datetime` change types). Referencing a dropped column is rejected with the dropping step named. |
| FR-PL-13 | *(M0)* When a target column is set (Spec 07 FR-ML-10), the Gate rejects `drop_column`, `impute`, `clip_outliers` and `cast_type` on it, and the planner prompt names the target as protected. |

### Whitelist summary (normative details in `design.md` §4)

| Op | Params | Applies to |
|---|---|---|
| `drop_duplicates` | — | frame |
| `drop_column` | `columns: list[str]` | any |
| `impute` | `strategy: mean\|median\|mode\|constant`, `value?` | numeric (mean/median), any (mode), any (constant) |
| `clip_outliers` | `method: iqr`, `factor?: float=1.5` | numeric |
| `cast_type` | `to: int\|float\|str\|bool\|category` | per dry-run (Spec 05) |
| `parse_datetime` | `format?: str` | text/datetime |
| `standardize_text` | `ops: [trim, lowercase, collapse_spaces]` | text/categorical |

## Interfaces

- **Input:** `profile.json` (Spec 02)
- **Output:** `plan.json` validated by `schemas/plan.py`; consumed by the review UI
  (Spec 04) and Executor (Spec 05, approved steps only)
- **LLM:** Google Gemini (`google-genai` SDK) `generateContent` with JSON output
  (`response_mime_type="application/json"` + response schema); model from `GEMINI_MODEL`

## Acceptance Criteria

- **AC-1** Given the Titanic profile, when planned, then the plan proposes e.g.
  `impute(Age, median)` with rationale citing the null percentage, and only whitelisted ops.
- **AC-2** Given a mocked LLM response containing op `"drop_outliers"` (not whitelisted),
  when gated, then the step is rejected, a re-prompt occurs, and the attempt is logged.
- **AC-3** Given a mocked response referencing column `"Aeg"` (typo), when gated, then
  rejected with an unknown-column error and re-prompted.
- **AC-4** Given `PLAN_MAX_RETRIES=3` and a persistently invalid responder, then exactly
  3 attempts occur and the stage fails with a clear message (no silent partial plan).
- **AC-5** Given any successful planning run, then `llm_calls` rows contain
  attempt/valid/error/token fields and **no** profile or data content.
- **AC-7** *(M0)* Given `drop_column(Age)` then `impute(Age)`, the Gate rejects step 2
  citing step 1; given `cast_type(x, str)` then `standardize_text(x)`, the Gate accepts.
- **AC-8** *(M0)* Given target `Survived`, a step `impute(Survived)` or
  `drop_column([Survived])` is rejected by the Gate.
- **AC-6** Given the same profile and a seeded/stubbed LLM, planning behavior is
  stable; stored `plan.json` is the artifact of record (execution reproducibility does
  not depend on re-calling the LLM).

## Dependencies

- Requires Spec 02 (`profile.json`). Blocked by nothing else. Feeds Spec 04 (review)
  and Spec 05 (execution of approved steps).

## Test Plan

- **Unit (Gate):** every op's valid/invalid param matrix; unknown op/column; type
  incompatibility; rationale-missing rejection; schema-version check.
- **Integration (LLM mocked):** happy path; each rejection class → retry → recovery;
  retry exhaustion → visible failure; `llm_calls` privacy assertion.

## Out of Scope

- Executing steps (Spec 05), user edits (Spec 04), follow-up chat about the plan
  (stretch, PRD §12), sample values in prompts (PRD §13.3 — default: profile-only).

## Open Questions

- Whether a top-value hint (e.g., inconsistent category spellings) should be added to
  the profile to help `standardize_text` proposals — needs an eval on Telco-like data.

## Tasks

- [x] FR-PL-02..05, 11 schema + Gate (M2)
- [x] FR-PL-12 running-schema Gate (M0)
- [x] FR-PL-13 target protection (M0)
- [ ] FR-PL-01, 06..10 LLM planner (M3)

## Changelog

- 2026-11-11 — M0: FR-PL-01 now references `llm_profile()`; added FR-PL-12/13, AC-7/8.
