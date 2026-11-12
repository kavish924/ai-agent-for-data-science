# Spec 10 — Non-Functional Requirements & Observability

> **Status:** Done · **Source:** PRD §7, §9, §10 · **Milestone:** cross-cutting (M1–M8)

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
| NFR-07 **Recovery** | *(M0)* On startup, sessions left in an in-flight state by a crash or restart are recovered: `executing` → `awaiting_approval` with `failed_stage=execute`; *(M5)* `modeling` → `executed` with `failed_stage=model`; `uploaded` without a profile → recorded error, `failed_stage=profile` (retryable per Spec 01 FR-UP-12). |
| NFR-09 **Evaluation harness** | *(M8)* `python -m eval.run [--live]` (from `backend/`) runs the whole pipeline in-process (upload → target → LLM plan → scripted review → approve → execute → charts → models → report) on every dataset in `eval/golden.json` (the three `samples/`). It uses the offline `RuleBasedLLM` by default, or real Gemini with `--live`, and writes `eval/results/<offline\|live>.json` plus a Markdown summary. |
| NFR-10 **Eval metrics** | *(M8)* Computed per dataset and overall. **Schema validity** = planner runs whose first attempt passed / planner runs (from `llm_calls`). Planner attempts that failed in transport are counted separately (`transport_errors`), so an API outage is not read as a bad plan. **Plan quality**: a plan is *sensible* when every golden `expected` step is present and no `forbidden` step is proposed; reported with expected-step recall. **Approval rate** = steps the scripted reviewer approves unedited / steps proposed; the reviewer approves a step that matches `expected` or `acceptable` and nothing `forbidden`. **Time to report** = wall time from upload to report, with per-stage times. A golden entry matches a step when the ops are equal and the entry's column is the step's column, is listed in a `drop_column`'s `columns`, or is `*`. |
| NFR-11 **Reproducibility harness** | *(M8)* Each eval run replays the executed steps as a manual plan in a fresh session. The cleaned CSV, every chart PNG and the model scores must be identical (bytes or values). Re-rendering the report in the original session must be byte-identical. Across sessions, the report must be identical after masking the session id whenever both narrations come from the template (LLM narration is a stored artifact per session, NFR-01). |
| NFR-12 **Performance baseline** | *(M8)* The eval records upload+profile and execute times for a max-size fixture (Telco rows repeated up to `MAX_ROWS`) against a 60 s budget each. Recorded, not enforced in CI. |
| NFR-08 **Retention sweep** | *(M0)* The retention sweep runs at startup and then every `RETENTION_SWEEP_MINUTES` (default 60); it deletes the DB row and the whole session directory and logs `retention.sweep`. |

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
| Plan quality | Eval runs on `samples/` datasets (M8); sensible plans (golden `expected` present, nothing `forbidden`) / total |
| Schema validity rate | `llm_calls` where `attempt=1 ∧ valid=true` / total planner calls |
| Time to report | `session.created` → `report.generated` timestamps |
| Approval rate | in the app: plan steps with status `approved` (unedited) / executed steps; in the eval: steps the golden reviewer approves / steps proposed |
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
- **AC-8** *(M8)* Given a plan and a golden entry, when the plan is scored, then expected-step recall,
  forbidden hits, `sensible` and the reviewer's approve/skip per step follow NFR-10's matching rule
  (column, `drop_column` list, `*`).
- **AC-9** *(M8)* Given per-dataset results, when they are summarised, then schema validity, plan
  quality, approval rate and mean time to report are computed as in NFR-10 (first-attempt validity
  from `llm_calls`).
- **AC-10** *(M8)* Given the offline LLM, when the eval runs on a sample, then every stage completes,
  each metric and stage time is recorded, and the JSON and Markdown results are written.
- **AC-7** *(M0)* Given a session stored in `executing` and one in `uploaded` with no
  profile, when the app starts, then the first is `awaiting_approval` with
  `failed_stage=execute` and the second has an error with `failed_stage=profile`.
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

## Tasks

- [x] NFR-06 JSON logging (M1)
- [x] NFR-07 startup recovery sweep (M0)
- [x] NFR-08 retention sweep, startup + periodic (M0)
- [x] NFR-03/06 privacy of logs and `llm_calls` (AC-2), LLM failure recovery (AC-5) (M3)
- [x] NFR-06 AC-4: one completion log line with `duration_ms` per stage (M6)
- [x] NFR-09 eval harness `backend/eval/` + golden expectations (M8)
- [x] NFR-10 metrics (AC-8, AC-9) (M8)
- [x] NFR-11 reproducibility replay (AC-1) (M8)
- [x] NFR-12 performance baseline (AC-6) (M8)
- [x] Offline eval results recorded (AC-10) (M8)
- [ ] Full live eval results (`--live`), blocked by the Gemini key's quota (429) on 2026-11-12

## Changelog

- 2026-11-11 — M0: added NFR-07 (recovery), NFR-08 (retention schedule), AC-7.
- 2026-11-11 — M3: AC-2 and AC-5 pass.
- 2026-11-12 — M8 (Approved): added NFR-09..12 (eval harness, metrics, reproducibility replay, performance baseline) and AC-8..10; AC-1 and AC-6 are now met through the harness.
- 2026-11-12 — M8 complete: AC-1..10 pass. Offline eval on all samples recorded in `backend/eval/results/offline.md` (100k-row baseline: profile 11 s, execute 20 s).
