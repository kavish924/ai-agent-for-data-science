# Spec 10 — Non-Functional Requirements & Observability

> **Status:** Draft v0.1 · **Source:** PRD §7, §9, §10 · **Milestone:** cross-cutting (M1–M8)

## Purpose

Define the non-functional contract — determinism, safety, privacy, performance,
reliability — and the logging/observability that makes the system auditable and
measurable against PRD §9 success metrics.

## User Story

> As a user (and as the developer operating this), I want the system to be safe,
> private, predictable, and observable, so I can trust it with real data and debug it
> when it fails.

## Requirements

| ID | Requirement |
|---|---|
| NFR-01 **Determinism** | Same CSV + same approved plan + same tool versions ⇒ identical cleaned CSV, charts (bytes), and model scores. Seeds pinned; LLM outputs are stored artifacts, so re-execution never re-rolls the dice. |
| NFR-02 **Safety** | No LLM output is ever executed or interpreted as code; the whitelist + Pydantic Gate is the only path from LLM output to data operations. |
| NFR-03 **Privacy** | Only aggregate profile data leaves the system; `llm_calls` logs contain tokens/duration but never payloads; uploads + artifacts deleted after `RETENTION_DAYS`; UI displays a clear notice of what is sent to the LLM. |
| NFR-04 **Performance** | Profiling and cleaning complete in seconds for files up to the size limit; full pipeline (upload → report) in minutes; each stage records `duration_ms`. |
| NFR-05 **Reliability** | Graceful handling of malformed CSVs, empty columns, LLM failures, and invalid targets: specific errors, session stays recoverable, no silent data changes. |
| NFR-06 **Observability** | Structured JSON logs for every pipeline stage and LLM call (catalog below); log level from `LOG_LEVEL`; no data content in logs. |

### Log event catalog

| Event | Key fields |
|---|---|
| `session.created` | session_id, filename, size_bytes, encoding, delimiter |
| `profile.completed` | session_id, duration_ms, n_columns, issues_found |
| `plan.requested` / `plan.validated` / `plan.rejected` | session_id, attempt, error? |
| `llm.call` | stage, model, attempt, valid, tokens, duration_ms — **no content** |
| `execute.started` / `execute.step` / `execute.completed` / `execute.failed` | session_id, step_id, op, rows/cols/nulls/outliers before/after, error? |
| `charts.generated` | session_id, count, skipped (list+reasons) |
| `model.completed` | session_id, target, problem_type, best_model, cv_mean |
| `narration.completed` / `narration.fallback` | session_id, duration_ms |
| `report.generated` | session_id, duration_ms |
| `retention.sweep` | deleted_sessions, freed_bytes |

### Metrics mapping (PRD §9)

| Metric | Derived from |
|---|---|
| Plan quality | Eval runs on `samples/` datasets (M8); judged-sensible plans / total |
| Schema validity rate | `llm_calls` where `attempt=1 ∧ valid=true` / total planner calls |
| Time to report | `session.created` → `report.generated` timestamps |
| Approval rate | plan steps with status `approved` (unedited) / executed steps |
| Reproducibility | double-run byte-comparison harness on fixture datasets |

## Acceptance Criteria

- **AC-1** Determinism harness: fixed Titanic fixture double-run yields identical
  cleaned CSV bytes and identical `model_runs.json` scores.
- **AC-2** Grep-level test: no log line emitted during a full mocked run contains raw
  row values or full prompts (NFR-03/06).
- **AC-3** Retention sweep test: a session with expired `retention_expires_at` is fully
  removed (DB row + artifacts) by the sweep.
- **AC-4** Every stage transition emits exactly one stage log line with `duration_ms`.
- **AC-5** Forced LLM failure during planning: user-visible error, no data mutation,
  session retryable (NFR-05).
- **AC-6** Profiling + execution of the max-size fixture completes within the stated
  seconds budget on the dev machine baseline (recorded, not hard-enforced in CI).

## Dependencies

- Cross-cutting: applies to Specs 01–09. Retention sweep needs the session store +
  artifact store interfaces. Determinism harness needs `samples/` fixtures.

## Test Plan

- **Unit:** log formatter/redaction; envelope of `llm_calls`; retention calculator.
- **Integration:** full mocked run → assert event catalog coverage (each stage logged);
  privacy grep; retention sweep with fake clock; determinism harness (AC-1).

## Out of Scope

- Distributed tracing/metrics backends (Prometheus/OTel) — local JSON logs for v1;
  auth/audit for multi-user (non-goal); performance SLAs enforcement in CI.

## Open Questions

- ~~Log destination~~ **Resolved:** stdout + rotating file under `storage/logs/`.
