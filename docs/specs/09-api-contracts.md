# Spec 09 — API Contracts

> **Status:** Draft v0.1 · **Source:** PRD §8 · **Milestone:** M1–M7 (grows with each) · **Boundary:** Next.js ↔ FastAPI

## Purpose

Define the HTTP surface between the frontend and backend: endpoints, request/response
schemas, status codes, and error conventions.

## User Story

> As a frontend developer, I want a stable, documented API contract, so I can build UI
> flows against the backend without guessing payloads.

## Requirements

| ID | Requirement |
|---|---|
| FR-AP-01 | `POST /sessions` — multipart CSV upload; starts profiling in the background. `201 {session_id, state, n_rows, n_columns}` · `413` limits · `415/422` non-CSV. |
| FR-AP-02 | `GET /sessions/{id}/profile` — `200 profile.json` · `404` unknown session · `409` if not yet profiled. |
| FR-AP-03 | `POST /sessions/{id}/plan` — generate the cleaning plan (LLM; bounded retries server-side). `200 plan.json` · `409` wrong state · `502` planner failed after retries. |
| FR-AP-04 | `POST /sessions/{id}/execute` — body: approved/edited steps; server re-validates via the Gate. `202 {run_id}` + poll status · `409` unless state `awaiting_approval` · `422` Gate rejection. |
| FR-AP-05 | `POST /sessions/{id}/model` — body `{target: "col"}`. `200 model_runs.json` · `409` unless `executed` · `422` invalid target. |
| FR-AP-06 | `GET /sessions/{id}/report` — `200 text/html` · `404` until state `reported`. |
| FR-AP-07 | `GET /sessions/{id}` — **(addition)** session status for polling: `{state, stage_progress, error?}` — supports background-job progress (PRD §8 Job handling). |
| FR-AP-08 | All errors use a common envelope: `{"error": {"code", "message", "details"?}}`; messages are user-presentable. |
| FR-AP-09 | Endpoints are stateful per session but never mutate the upload artifact; all mutating actions are stage transitions guarded by the state machine (`system-guide.md` §4). |

## Canonical Schemas

Defined in `backend/app/schemas/` (Pydantic, single source of truth; OpenAPI auto-docs
at `/docs`):

| Schema | Used by |
|---|---|
| `SessionOut` | FR-AP-01/07 |
| `ProfileOut` | FR-AP-02 (Spec 02) |
| `PlanOut`, `PlanStepIn` | FR-AP-03/04 (Spec 03/04; whitelist Gate) |
| `ExecutionRunOut` | FR-AP-04 (Spec 05) |
| `ModelRequestIn`, `ModelRunsOut` | FR-AP-05 (Spec 07) |
| `ErrorEnvelope` | FR-AP-08 (all) |

Payload shapes are illustrated in `architecture.md` §3; normative definitions live in
code and the generated OpenAPI spec, not in docs (docs link, never duplicate).

## State-Transition Guards

| Endpoint | Allowed source states |
|---|---|
| `GET /profile` | `profiled` and later |
| `POST /plan` | `profiled` (or `awaiting_approval` for regenerate) |
| `POST /execute` | `awaiting_approval` only |
| `POST /model` | `executed` and later |
| `GET /report` | `reported` only |

Violations return `409` with the current state in `details`.

## Acceptance Criteria

- **AC-1** Every endpoint returns the documented status codes for the listed cases
  (contract tests).
- **AC-2** Every error response conforms to `ErrorEnvelope` (tested globally).
- **AC-3** `execute` with any altered step (vs. what the Gate allows) returns `422` —
  the client is never trusted (Spec 04).
- **AC-4** `GET /sessions/{id}` reflects each state transition within polling interval
  during a mocked full-pipeline run.
- **AC-5** OpenAPI docs at `/docs` match this spec (schema-drift test).

## Dependencies

- Definitions depend on schemas from Specs 02, 03, 05, 07, 08; consumed by Spec 04 UI.

## Test Plan

- **Contract tests:** per-endpoint happy path + each error class; envelope conformance;
  state-guard matrix; OpenAPI drift check.
- **E2E (LLM mocked):** upload → profile → plan → approve → execute → model → report
  via HTTP only.

## Out of Scope

- Auth/API keys (local MVP — non-goal v1), websockets (polling suffices for MVP),
  rate limiting, pagination of session lists (admin listing endpoint is a fast-follow).

## Open Questions

- ~~URL versioning~~ **Resolved:** `/api/v1/...` prefix adopted from the start.
