# Spec 04 — Plan Review UI

> **Status:** Draft v0.1 · **Source:** PRD §6.4 · **Milestone:** M7 · **Agent:** Frontend + Orchestrator

## Purpose

Give the user full control before any data changes: display the proposed plan with
rationales, allow toggling and parameter edits, and require explicit approval.

## User Story

> As a user, I want to review, toggle, and edit each proposed cleaning step, so that
> only changes I approve are applied to my data.

## Requirements

| ID | Requirement |
|---|---|
| FR-RV-01 | Display plan steps as an ordered list showing: index, operation, target column, parameters, and the LLM's rationale. |
| FR-RV-02 | Allow each step to be enabled/disabled via toggle; disabled steps remain visible and recorded, but are excluded from execution. |
| FR-RV-03 | Allow editing of parameters per step, constrained by the same whitelist rules server-side (client hints only — the server Gate re-validates). |
| FR-RV-04 | Require an explicit **Approve** action before execution; no approval → no execution (state machine enforces `awaiting_approval`). |
| FR-RV-05 | Offer a **Regenerate plan** action that re-runs Spec 03 and replaces the proposal (previous plan retained in history for audit). |
| FR-RV-06 | Record per-step status transitions: `proposed → approved / disabled / edited → executed`. |
| FR-RV-07 | Show a warning affordance for destructive steps (`drop_column`, `drop_duplicates`) including what will be lost (e.g., column names, row counts). |
| FR-RV-08 | Validation errors from edited parameters are shown inline and block approval until resolved. |

## Interfaces

- Reads `plan.json` (Spec 03) via `GET /sessions/{id}/plan` (see `09-api-contracts.md`)
- Submits the approved/edited step list with `POST /sessions/{id}/execute` (Spec 05)
- Server re-validates every submitted step through the Gate — client-side checks are
  UX only, never the security boundary

## Acceptance Criteria

- **AC-1** Given a 5-step plan, when displayed, then all steps show op, column, params,
  and rationale in order.
- **AC-2** Given step 2 disabled and the rest approved, when submitted, then execution
  applies steps 1,3,4,5 in order and the log records step 2 as `disabled`.
- **AC-3** Given an edited `impute` strategy `mean → constant` without a value, when
  submitted, then an inline error blocks approval (server rejects too).
- **AC-4** Given an edited valid step, when executed, then the execution log records the
  step as `edited` with the final parameters used.
- **AC-5** Given no Approve action, when the user attempts to proceed, then execution
  cannot start (UI prevents; API rejects `execute` while state is `awaiting_approval`).
- **AC-6** Given Regenerate is clicked, then a new plan is fetched and displayed, and
  the prior plan remains retrievable in session history.

## Dependencies

- Requires Specs 02, 03 (profile + plan). Feeds Spec 05. Frontend per `tech-stack.md`
  (Next.js + Tailwind); progress polling per `09-api-contracts.md` §4.

## Test Plan

- **Component:** step list rendering; toggle state; inline validation messages;
  destructive-step warnings.
- **Integration (LLM mocked):** approve-only-defaults flow; disable + execute flow;
  edit + reject + fix flow; regenerate replaces display, preserves history.
- **API-level:** `execute` rejected unless state is `awaiting_approval` (AC-5).

## Out of Scope

- Per-step undo/redo (stretch, PRD §12), follow-up chat (stretch), drag-to-reorder
  steps (plan order is the LLM's proposed order in v1; reordering is a possible
  fast-follow), multi-plan comparison.

## Open Questions

- ~~Dependency warnings~~ **Resolved:** best-effort dependency warning when a step another
  step depends on is disabled. Accepted for v1.
