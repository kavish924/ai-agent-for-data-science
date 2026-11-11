# Spec 09 — API Contracts

> **Status:** In progress (M0) · **Source:** PRD §8 · **Milestone:** M1–M7 (grows with each) · **Boundary:** Next.js ↔ FastAPI

## Purpose

Define the HTTP surface between the frontend and backend: endpoints, request/response
schemas, status codes, and error conventions.

## User Story

> As a frontend developer, I want a stable, documented API contract, so I can build UI
> flows against the backend without guessing payloads.

## Requirements

All paths are under the `/api/v1` prefix (normative; other docs may abbreviate).

| ID | Requirement |
|---|---|
| FR-AP-01 | `POST /sessions` — multipart CSV upload; starts profiling in the background. `201 SessionOut` · `413` limits · `415/422` non-CSV or empty. |
| FR-AP-02 | `GET /sessions/{id}/profile` — `200 profile.json` · `404` unknown session · `409` if not yet profiled. |
| FR-AP-03 | *(rev. M0)* `POST /sessions/{id}/plan` — create a new plan version. With no body the LLM generates it (M3, Spec 03 FR-PL-14); with a body it stores a manual plan. Server assigns `step_id`s (`s1..sN`), forces every status to `proposed`, Gate-validates, stores `plans/v{n}.generated.json`, sets state `awaiting_approval`. `201 PlanOut` · `409` wrong state · `422` Gate rejection · `502 planner_failed` after retries · `503 llm_not_configured` when generation is requested without an API key. From `approved` this revokes the approval. |
| FR-AP-04 | *(rev. M0)* `POST /sessions/{id}/execute` — **no body**; runs the frozen approved plan. `202` · `409` unless state `approved`. Exactly one of two concurrent calls succeeds (conditional state transition). |
| FR-AP-05 | `POST /sessions/{id}/model` — body `{target: "col"}`. `200 model_runs.json` · `409` unless `executed` · `422` invalid target. *(M5)* |
| FR-AP-06 | `GET /sessions/{id}/report` — `200 text/html` · `404` until the report exists. *(M6)* |
| FR-AP-07 | `GET /sessions/{id}` — session status for polling: `SessionOut` incl. `state`, `error`, `failed_stage`, `target`, `plan_version`. |
| FR-AP-08 | All errors use a common envelope: `{"error": {"code", "message", "details"?}}`; messages are user-presentable. |
| FR-AP-09 | Endpoints never mutate the upload artifact; all mutating actions are state transitions guarded by the state table below. |
| FR-AP-10 | *(M0)* `GET /sessions/{id}/plan` returns the current review copy (`plan.json`); `GET /sessions/{id}/plan/history` lists every stored version (`generated`, `approved`) for audit. |
| FR-AP-11 | *(M0)* `PUT /sessions/{id}/plan` — save review edits (Spec 04 FR-RV-09 reconciliation + Gate). `200 PlanOut` · `409` unless `awaiting_approval`/`approved` (an edit revokes approval) · `422` reconciliation/Gate errors. |
| FR-AP-12 | *(M0)* `POST /sessions/{id}/plan/approve` — optional body = final edits (same as PUT). Rejects any remaining `proposed` step (`422 unreviewed_steps`); freezes `plans/v{n}.approved.json`; state → `approved`. |
| FR-AP-13 | *(M0)* `PUT /sessions/{id}/target` — body `{target: "col" \| null}` (Spec 07 FR-ML-10). `200 SessionOut` · `409` unless `profiled`/`awaiting_approval` · `422` invalid target or plan conflict. |
| FR-AP-14 | *(M0)* `POST /sessions/{id}/profile` — retry profiling (Spec 01 FR-UP-12). `202` · `409` unless `uploaded`. |
| FR-AP-15 | *(M0)* `GET /sessions/{id}/cleaned.csv` — download deliverable 1 as an attachment named `cleaned_<original>.csv`. `200 text/csv` · `404` until `executed`. |

### Session state table (normative)

| State | Meaning | Entered by |
|---|---|---|
| `uploaded` | stored; profiling queued/running/failed | `POST /sessions` |
| `profiled` | `profile.json` ready | profiling success |
| `awaiting_approval` | a plan version exists and is under review | `POST /plan`, `PUT /plan`, execution failure |
| `approved` | plan frozen; ready to execute | `POST /plan/approve` |
| `executing` | background execution running | `POST /execute` |
| `executed` | cleaned CSV + execution log ready | execution success |
| `modeled` / `reported` | M5 / M6 | — |

`planned` from earlier drafts is merged into `awaiting_approval`. Failures never add a
state: the session stays in (or returns to) its last good state with `error` and
`failed_stage` (`profile` \| `plan` \| `execute` \| …) set; a successful transition
clears both.

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
| `POST /profile` (retry) | `uploaded` |
| `PUT /target` | `profiled`, `awaiting_approval` |
| `POST /plan` | `profiled`, `awaiting_approval`, `approved` (new version; revokes approval) |
| `PUT /plan` | `awaiting_approval`, `approved` (revokes approval) |
| `POST /plan/approve` | `awaiting_approval` |
| `POST /execute` | `approved` only |
| `GET /cleaned.csv` | `executed` and later |
| `POST /model` | `executed` and later |
| `GET /report` | `reported` only |

Violations return `409` with the current state in `details`.

## Acceptance Criteria

- **AC-1** Every endpoint returns the documented status codes for the listed cases
  (contract tests).
- **AC-2** Every error response conforms to `ErrorEnvelope` (tested globally).
- **AC-3** *(rev. M0)* Any altered step submitted via `PUT /plan` or `approve` is
  re-validated by the Gate and returns `422` when invalid — the client is never trusted
  (Spec 04).
- **AC-4** `GET /sessions/{id}` reflects each state transition within polling interval
  during a mocked full-pipeline run.
- **AC-5** OpenAPI docs at `/docs` match this spec (schema-drift test).
- **AC-6** *(M0)* `execute` before `approve` → `409`; approve with a `proposed` step →
  `422 unreviewed_steps`; after approve, `execute` runs exactly the frozen steps.
- **AC-7** *(M0)* A second `execute` racing the first gets `409` (conditional update).
- **AC-8** *(M0)* After two `POST /plan` calls, `GET /plan/history` lists both generated
  versions plus any approved version; nothing is overwritten.
- **AC-9** *(M0)* `GET /cleaned.csv` returns the deliverable with a
  `Content-Disposition` filename of `cleaned_<original>.csv`.

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

## Tasks

- [x] FR-AP-01, 02, 07, 08 (M1)
- [x] FR-AP-03, 04 revised plan/execute contract (M0)
- [x] FR-AP-10..15 history, review, approve, target, profile retry, cleaned.csv (M0)
- [ ] FR-AP-05, 06 (M5, M6)

## Changelog

- 2026-11-11 — M0: explicit approve step; body-less execute; versioned plans; target,
  profile-retry and cleaned-CSV endpoints; normative state table (`planned` merged into
  `awaiting_approval`; failures recorded via `error` + `failed_stage`).
- 2026-11-11 — M3: `POST /plan` body is optional (LLM generation); added `502 planner_failed` and `503 llm_not_configured`.
