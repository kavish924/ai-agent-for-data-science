# Project Checklist — AI Data Science Agent

> Living task list. Update it in the same branch as the work: tick `[x]` when a task is
> done **and verified** (tests/smoke green), add the branch name, and bump "Last updated".
> Detailed requirements live in `docs/specs/`; this file tracks progress only.
>
> **Last updated:** 2026-11-11 · **Current branch:** `m0-hardening` (pushed, PR not opened)

Legend: `[x]` done · `[ ]` to do · `[~]` partly done (see note)

## Progress

| Milestone | Branch | Status |
|---|---|---|
| M1 Ingestion + profiler | `main` (initial commit) | ✅ done |
| M2 Whitelisted executor + Gate | `main` (initial commit) | ✅ done |
| M0 Hardening | `m0-hardening` | ✅ done · awaiting PR → `main` |
| M3 LLM planner (Gemini) | `m3-llm-planner` | ⬜ not started |
| M3.5 Thin UI slice | `m3.5-thin-ui` | ⬜ not started |
| M4 Charts | `m4-charts` | ⬜ not started |
| M5 ML baselines | `m5-ml-baselines` | ⬜ not started |
| M6 Report + narration | `m6-report` | ⬜ not started |
| M7 UI polish | `m7-ui-polish` | ⬜ not started |
| M8 Evaluation + demo | `m8-eval-demo` | ⬜ not started |

---

## Planning & process

- [x] Review PRD, docs and specs; record flaws and fixes (plan, 2026-11-11)
- [x] Resolve open decisions: Gemini · target chosen early · thin UI early · extend `docs/specs`
- [x] `CLAUDE.md` with spec-driven workflow rules
- [x] Revised milestone order in Spec 00
- [x] Branching rule: never commit/push to `main`; one branch per milestone, merged by PR
- [x] This checklist
- [ ] Open PR `m0-hardening` → `main` and merge it (user)
- [ ] First green CI run on GitHub

## M1 — Ingestion + profiler *(done before M0)*

- [x] CSV upload with encoding detection and delimiter sniffing
- [x] File-size and row limits (413), non-CSV rejection (415/422)
- [x] Session ID + SQLite session store + immutable `upload.csv`
- [x] Deterministic profiler: 6 types, nulls, duplicates, top-K, IQR outliers, stats
- [x] Structured JSON logging + common error envelope

## M2 — Executor + Gate *(done before M0)*

- [x] Whitelist of 7 ops with Pydantic param schemas
- [x] Semantic Gate (column exists, type compatibility)
- [x] Executor with per-step before/after log; original upload never modified
- [x] Deterministic cleaned CSV export

## M0 — Hardening · branch `m0-hardening`

- [x] Specs first: new FRs/ACs in specs 01, 02, 03, 04, 05, 07, 09, 10
- [x] A1 `.gitignore` fixed; `backend/app/storage/` tracked (fresh-export test passes)
- [x] A2 Steps default to `proposed`; stable `step_id`s
- [x] A2 Versioned plans (`plans/v{n}.generated|approved.json`) + `GET /plan/history`
- [x] A2 `PUT /plan` review reconciliation; `POST /plan/approve`; body-less `POST /execute`
- [x] A3.1 Gate checks the running schema (drop-then-use rejected)
- [x] A3.1 Executor catches every exception; no session stuck in `executing`
- [x] A3.2 Strict casts: bool mapping, nullable `Int64`, strict float
- [x] A3.3 Shared numeric parser; unparseable values kept and counted
- [x] A3.4 Integer identifier columns typed `id_like`
- [x] A3.5 Conditional state transitions (no double execute)
- [x] A3.6 Startup recovery of in-flight sessions
- [x] A3.7 Normative state table in Spec 09; `failed_stage` field
- [x] A4 (part 1) `PUT /target` + Gate protection of the target column
- [x] A5 `llm_profile()` privacy projection
- [x] A7 (part 1) `GET /cleaned.csv` download; `POST /profile` retry
- [x] A7 (part 1) Chunked upload size cap; retention sweep at startup + hourly
- [x] A8 Docs drift fixed (Gemini only, repo layout, state model)
- [x] Extra: upload filename sanitized (path traversal); SQLite connections closed
- [x] Tooling: ruff, mypy, traceability matrix + checker, OpenAPI drift test
- [x] Tooling: CI workflow, pre-commit config, `smoke_m0.py` on all 3 samples
- [x] Specs 01, 02, 05 marked `Done`; 128 tests green

## M3 — LLM planner · branch `m3-llm-planner`

- [ ] Spec 03 FR-PL-01, 06–10 approved (prompt contract, retry loop, `llm_calls`)
- [ ] Add `google-genai` dependency; `GEMINI_API_KEY` handling
- [ ] `app/llm/`: `LLMClient` protocol, `GeminiClient` (JSON schema output, temperature 0)
- [ ] Prompt built from `llm_profile()` only; target named as protected
- [ ] `services/planner.py`: generate → Gate → feed issues back → retry ≤ `PLAN_MAX_RETRIES`
- [ ] `llm_calls` table (attempt, valid, error, tokens, duration — no payloads)
- [ ] `POST /plan` without a body generates via LLM; manual plans still possible for tests
- [ ] Mocked-LLM tests for Spec 03 AC-1..8; one optional `@pytest.mark.live` test
- [ ] Spec 10 AC-2 (no data in logs) and AC-5 (LLM failure is recoverable)
- [ ] `smoke_m3.py`

## M3.5 — Thin UI slice · branch `m3.5-thin-ui`

- [ ] Scaffold `frontend/` (Next.js 15 + Tailwind), API client typed from OpenAPI
- [ ] Upload page with limit/error messages and an LLM privacy notice
- [ ] Profile summary + target picker (suggested candidates)
- [ ] Plan review: toggle, edit params, inline Gate errors, destructive-step warnings
- [ ] Approve → execute with progress polling → download cleaned CSV
- [ ] Spec 04 component tests

## M4 — Charts · branch `m4-charts`

- [ ] Spec 06 approved; add `matplotlib` (Agg backend)
- [ ] After-cleaning re-profile → `profile.after.json`
- [ ] `services/charts.py`: histogram, box plot, top categories, correlation heatmap, missingness map
- [ ] Chart cap + documented priority order; deterministic file names and bytes
- [ ] Orchestrator: execute → re-profile → charts automatically
- [ ] Chart endpoints + UI gallery

## M5 — ML baselines · branch `m5-ml-baselines`

- [ ] Spec 07 approved; add `scikit-learn`
- [ ] Candidate-target suggestions (FR-ML-01)
- [ ] Rule-based problem-type detection; id_like targets rejected
- [ ] Structural-op replay on the upload (FR-ML-11) — no leakage from cleaning
- [ ] Pipelines: imputer + `IQRClipper` + encoders/scalers inside each model
- [ ] Dummy floor + 2 baselines; 80/20 holdout + 5-fold CV; fixed seed
- [ ] `model_runs.json` with params fingerprint; `POST /model`
- [ ] Spec 10 AC-1 determinism harness (scores); UI results table

## M6 — Report + narration · branch `m6-report`

- [ ] Spec 08 approved
- [ ] Narrator: placeholder JSON, numeral validator, template fallback
- [ ] Reporter: Jinja2 HTML in PRD section order; tool versions; "ML skipped" path
- [ ] `POST /report`, `GET /report`; optional zip bundle
- [ ] Report states the structural/statistical split (FR-ML-11)
- [ ] Spec 10 AC-4 (one log line per stage)

## M7 — UI polish · branch `m7-ui-polish`

- [ ] Report view, charts, model results in the UI
- [ ] Plan history + regenerate
- [ ] Progress UX, error states, accessibility pass

## M8 — Evaluation + demo · branch `m8-eval-demo`

- [ ] `backend/eval/` harness on titanic / housing / telco with the live LLM
- [ ] Metrics: schema-validity rate, plan quality (golden ops), approval rate, time to report
- [ ] Reproducibility: double-run byte-identical cleaned CSV and report
- [ ] Spec 10 AC-6 performance baseline
- [ ] README, demo script, screenshots

## Known follow-ups / tech debt

- [ ] SQLite open/close per call is slow on Windows (~1 s per API flow in tests); consider WAL or a pooled connection
- [ ] Rotating log handler keeps `app.log` open (temp-dir cleanup on Windows)
- [ ] Titanic `Name` is typed `id_like` (every name is unique) — confirm this is desired
- [ ] Split `routers/sessions.py` per stage before M3 to reduce merge conflicts
