# Spec 04 — Plan Review UI

> **Status:** Done · **Source:** PRD §6.4 · **Milestone:** M3.5 (thin slice), M7 (polish) · **Agent:** Frontend + Orchestrator

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
| FR-RV-09 | *(M0, server side)* Each step carries a stable `step_id`. Saved reviews are reconciled against the generated plan by `step_id`: a toggled-off step becomes `disabled`; a step whose column/params changed becomes `edited`; a step with an unknown or missing id becomes `user_added`; rationales of proposed steps cannot be rewritten by the client; omitting a proposed step is rejected (disable it instead). |
| FR-RV-10 | *(M0, server side)* Approval is rejected while any step is still `proposed`. |
| FR-RV-11 | *(M3.5)* Frontend stack: Next.js (App Router) + TypeScript + Tailwind CSS + Framer Motion in `frontend/`. Types for every request/response are generated from the backend's OpenAPI document (`npm run gen:api`), never hand-written. The browser calls the backend through a same-origin `/api/v1` proxy. |
| FR-RV-12 | *(M3.5)* One guided flow with a visible step indicator: **Upload → Profile & target → Review plan → Run → Download**, matching the design canvas "Data Science Agent UI". The current screen is derived from the session `state`, so a reload resumes where the user was (`?session=<id>` in the URL). |
| FR-RV-13 | *(M3.5)* Upload screen: file picker with drag-and-drop, the size/row limits stated, the three sample datasets as one-click options, and server errors (413/415/422) shown as the server's message. |
| FR-RV-14 | *(M3.5)* Profile screen: rows, columns, duplicate rows and per-column type/missing/outliers; a target picker listing every column except `id_like` ones (optional, "No target" allowed); a notice that only column statistics are sent to the LLM. Then **Generate plan with AI**; when the server answers `503 llm_not_configured`, say so plainly. |
| FR-RV-15 | *(M3.5)* Run screen: after Approve, start execution and poll `GET /sessions/{id}` until `executed` or a failure (`failed_stage=execute`), then show the execution log summary and a **Download cleaned CSV** link. A failure returns the user to review with the error shown. |
| FR-RV-17 | *(M7)* The Download screen groups results in **tabs**: Overview (run log + downloads), Charts, Models, Report. They follow the WAI-ARIA tabs pattern (`tablist`/`tab`/`tabpanel`, arrow keys + Home/End move between tabs, only the active tab is in the tab order) with an animated indicator, and the active tab is kept in the URL (`?tab=`) so a reload or shared link opens it. |
| FR-RV-18 | *(M7)* The Report tab shows the report inside the app in a **sandboxed** iframe (`sandbox="allow-same-origin"`: no scripts, forms, popups or navigation; same-origin only so embedded browsers that block opaque-origin frames still show it) with a title, plus Open in new tab and Download all; before a report exists it shows an empty state with a Create report action. |
| FR-RV-19 | *(M7)* The Review screen has a **Plan history** panel listing every stored version (`vN · generated` / `vN · approved`, step count) from `GET /plan/history`; choosing one shows its steps read-only, and the current version is marked. Completes AC-6. |
| FR-RV-20 | *(M7)* **Error and empty states** always offer a next step: an unknown or expired session shows "This analysis isn't available" with **Start a new analysis**; a network failure shows a banner with **Retry**; empty lists explain why and what to do. |
| FR-RV-21 | *(M7, a11y)* A **skip link** jumps to the main content; each screen has exactly one `h1`; after a screen change, focus moves to that screen's `h1` and a polite live region announces the new step (e.g. "Profile ready"); the step indicator marks finished steps with a check that screen readers read ("Upload, done"). |
| FR-RV-22 | *(M7)* One animation library: `motion` (`motion/react`) only, `framer-motion` removed; `MotionConfig reducedMotion="user"` stays at the root. |
| FR-RV-16 | *(M3.5, a11y)* Every control is keyboard reachable with a visible focus ring; motion uses Framer Motion and is disabled when the OS asks for reduced motion; text meets 4.5:1 contrast. |

## Interfaces

- Reads `plan.json` (Spec 03) via `GET /sessions/{id}/plan` (see `09-api-contracts.md`)
- Saves review edits with `PUT /sessions/{id}/plan`, approves with
  `POST /sessions/{id}/plan/approve` (optionally carrying the final edits), then starts
  execution with a body-less `POST /sessions/{id}/execute` (Spec 05)
- Server re-validates every submitted step through the Gate — client-side checks are
  UX only, never the security boundary

## Acceptance Criteria

- **AC-1** Given a 4-step plan, when displayed, then every step shows its operation, column,
  parameters and rationale, in plan order.
- **AC-2** Given step 2 switched off and the rest approved, when submitted, then the review
  sent to the server marks step 2 `disabled` and the others `approved`.
- **AC-3** Given an `impute` step edited to `constant` without a value, then an inline error
  is shown on that step and Approve is disabled until it is fixed.
- **AC-4** Given a step whose parameters were edited, then it is labelled `Edited` and the
  final parameters are what the review submits (the server records `edited`).
- **AC-5** Given any step still undecided, Approve is disabled; the API independently
  rejects `execute` unless the state is `approved`.
- **AC-6** Given Regenerate is clicked, then a new plan version is fetched and displayed;
  the previous version stays retrievable via plan history *(history view: M7)*.
- **AC-7** *(M3.5)* Given a `drop_column` or `drop_duplicates` step, a destructive warning
  names what will be lost (column names, or the duplicate-row count from the profile).
- **AC-8** *(M3.5)* Given the server rejects a review (422 `invalid_plan`), each issue is
  shown on the step it refers to.
- **AC-9** *(M3.5)* Given an upload error (413/415/422), the server's message is shown and
  the user stays on the upload screen.
- **AC-10** *(M3.5)* Given the profile screen, `id_like` columns are not offered as a target.
- **AC-11** *(M7)* Given the Download screen, the tabs are a `tablist`; ArrowRight/ArrowLeft/
  Home/End move selection and focus; the active tab is written to `?tab=`.
- **AC-12** *(M7)* Given a reported session, the Report tab renders an iframe pointing at
  `/report` with `sandbox="allow-same-origin"` (no `allow-scripts`) and a title; before a report, it shows the
  Create report empty state.
- **AC-13** *(M7)* Given two plan versions, the history panel lists both (and the approved
  copy) and shows a chosen version's steps read-only.
- **AC-14** *(M7)* Given a session id that returns `404`, the app shows "This analysis isn't
  available" with a Start a new analysis button that clears the session; a network error
  shows a Retry button that refetches.
- **AC-15** *(M7)* Given a screen change, focus lands on the new screen's `h1` and the live
  region announces it; a skip link targets `#main`.
- **AC-16** *(M7)* No source file imports `framer-motion`.

## Dependencies

- Requires Specs 02, 03 (profile + plan). Feeds Spec 05. Frontend per `tech-stack.md`
  (Next.js + Tailwind); progress polling per `09-api-contracts.md` §4.

## Test Plan

- **Component (Vitest + Testing Library, `frontend/src/**/*.test.tsx`):** step list
  rendering; toggle state; inline validation messages; destructive-step warnings; server
  issue mapping; upload errors; target picker. Test names follow `test_rv_ac<N>_<what>`.
- **End to end (manual, M3.5):** backend + frontend running, a sample dataset through every
  screen in the browser.
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

## Tasks

- [x] FR-RV-09, FR-RV-10 server-side review rules (M0)
- [x] FR-RV-11 frontend scaffold + generated API types (M3.5)
- [x] FR-RV-12..15 guided flow screens (M3.5)
- [x] FR-RV-01..05, 07, 08 review screen behaviors (M3.5)
- [x] FR-RV-16 accessibility + reduced motion (M3.5)
- [x] FR-RV-17..22 tabs, report view, plan history, error states, a11y, one motion library (M7)

## Changelog

- 2026-11-12 — M3.5: moved the thin slice ahead of M7; added FR-RV-11..16 and AC-7..10;
  rewrote AC-1..6 for the M0 approve flow. Visual design: Claude Design canvas
  "Data Science Agent UI".
- 2026-11-12 — M3.5 slice complete: AC-1..10 pass (Vitest); verified end to end in the browser on titanic.csv. Stays In progress for the M7 history view.
- 2026-11-12 — M7: added FR-RV-17..22 and AC-11..16 (results tabs, in-app report, plan history, error states, focus/announcements, motion/react).
- 2026-11-12 — M7 complete: AC-11..16 pass; every AC of Spec 04 now has tests.
- 2026-11-12 — M7: report iframe uses `sandbox="allow-same-origin"` instead of `sandbox=""`: the Claude app's browser blocked the opaque-origin frame (`ERR_BLOCKED_BY_CLIENT`); scripts stay forbidden.
