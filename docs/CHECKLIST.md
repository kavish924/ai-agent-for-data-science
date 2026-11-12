# Project Checklist — AI Data Science Agent

> Living task list. Update it in the same branch as the work: tick `[x]` when a task is
> done **and verified** (tests/smoke green), add the branch name, and bump "Last updated".
> Detailed requirements live in `docs/specs/`; this file tracks progress only.
>
> **Last updated:** 2026-11-12 · **Current branch:** `m4-charts` (on top of `main`; pushed)

Legend: `[x]` done · `[ ]` to do · `[~]` partly done (see note)

## Progress

| Milestone | Branch | Status |
|---|---|---|
| M1 Ingestion + profiler | `main` (initial commit) | ✅ done |
| M2 Whitelisted executor + Gate | `main` (initial commit) | ✅ done |
| M0 Hardening | `m0-hardening` | ✅ done · merged to `main` (PR #1) |
| M3 LLM planner (Gemini) | `m3-llm-planner` | ✅ done · merged to `main` (PR #2) |
| graphify tooling | `chore/graphify` | ✅ merged to `main` (PR #3) |
| M3.5 Thin UI slice | `m3.5-thin-ui` | ✅ done · in `main` (fast-forward push, user-approved; no PR) |
| M4 Charts | `m4-charts` | ✅ done · pushed, awaiting PR → `main` |
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
- [x] Open PR `m0-hardening` → `main` and merge it (PR #1)
- [ ] First green CI run on GitHub (M3.5 reached `main` without a PR, so check the Actions tab for its push run)

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

- [x] Split `routers/sessions.py` into per-stage routers (`sessions`, `plans`, `execution`)
- [x] Spec 03 FR-PL-14..16 + AC-9..11 approved; Spec 09/10 updated
- [x] Add `google-genai` dependency; `GEMINI_API_KEY`, `LLM_TIMEOUT_S` settings
- [x] `app/llm/`: `LLMClient` protocol, `GeminiClient` (JSON mode, temperature 0, seed)
- [x] Prompt built from `llm_profile()` only; target named as protected; injection guard
- [x] `services/planner.py`: generate → schema → rationale → Gate → feed issues back → retry ≤ `PLAN_MAX_RETRIES`
- [x] `llm_calls` table (attempt, valid, error class, tokens, duration — no payloads)
- [x] `POST /plan` without a body generates via LLM (503 without key, 502 after retries); manual plans still work
- [x] Fake-LLM tests for Spec 03 AC-1..11; optional `@pytest.mark.live` Gemini test
- [x] Spec 10 AC-2 (no data in logs) and AC-5 (LLM failure is recoverable)
- [x] `smoke_m3.py` (offline fake by default, `--live` for Gemini); added to CI
- [ ] Run `pytest -m live` and `smoke_m3.py --live` with a real `GEMINI_API_KEY` (user)
- [x] Open PR `m3-llm-planner` → `main` and merge it (PR #2)

## M3.5 — Thin UI slice · branch `m3.5-thin-ui`

- [x] Screens designed on a Claude Design canvas ("Data Science Agent UI": Upload, Plan review, Run & download)
- [x] Spec 04 FR-RV-11..16 + AC-1..10; Spec 09 FR-AP-16 (`GET /execution-log`); Spec 03 FR-PL-17 (`LLM_PROVIDER=offline`)
- [x] Scaffold `frontend/` (Next.js 15.5 + Tailwind 4 + Framer Motion), `/api/v1` proxy, API types generated from OpenAPI (`npm run gen:api`)
- [x] Upload page: drag-and-drop, limits, one-click samples, server error messages
- [x] Profile summary + target picker (identifiers excluded) + LLM privacy notice
- [x] Plan review: Approve/Skip per step, param editors, inline hints, server Gate issues per step, destructive warnings, regenerate
- [x] Approve → execute with progress polling → run summary → download cleaned CSV; `?session=` resume
- [x] Reduced motion respected (`MotionConfig reducedMotion="user"`), focus ring, keyboard-reachable controls
- [x] Spec 04 component tests (12, Vitest); traceability checker reads frontend tests (67 ACs)
- [x] Verified end to end in the browser on titanic.csv (desktop + 375 px phone width)
- [x] CI: frontend job (lint, typecheck, tests, build)
- [x] Into `main` by a user-approved fast-forward push (the PR route was blocked by a signed-out browser)

## M4 — Charts · branch `m4-charts`

- [x] Spec 06 FR-CH-02 revised (one distribution chart = histogram + box strip), FR-CH-06 priority from the original profile, FR-CH-10..13 + AC-6..10; Spec 09 FR-AP-17..19 + AC-11
- [x] Tests written first (backend and frontend), watched fail, then implemented
- [x] Add `matplotlib`; `services/charts.py` with the object API, fixed style, no version stamp → byte-identical PNGs
- [x] Missing-value map, correlation heatmap, distribution, top-category bars; cap 12 with recorded skip reasons
- [x] "Before" outline on distributions of columns the plan changed
- [x] After-cleaning re-profile → `profile.after.json`
- [x] `services/orchestrator.py`: re-profile + charts inside the run, before `executed`; failures isolated (manifest `status: failed`)
- [x] Endpoints: `GET /charts`, `GET /charts/{file}` (manifest-whitelisted), `GET /profile/after`
- [x] UI gallery on the Download screen: thumbnails, enlarge with shared-layout animation, Escape to close, skipped list
- [x] Verified in the browser on titanic.csv (9 charts, before overlay on Age, enlarge/close)
- [x] No rebase needed: `main` fast-forwarded to M3.5, which `m4-charts` sits on
- [ ] Open PR `m4-charts` → `main` and merge it (user)

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
- [ ] Don't run `npm run build` while `npm run dev` is running: both write `frontend/.next` and the dev server breaks (500s) until restarted
- [ ] Titanic `Name` is typed `id_like` (every name is unique) — confirm this is desired
- [ ] Next.js bundles postcss/sharp with open advisories (build-time CSS only; image optimisation disabled) — bump Next when fixed
- [x] Frontend tests for M3.5 were written right after the components, not red-first; M4 went back to red-first
- [ ] Target candidates are "all non-identifier columns"; Spec 07 FR-ML-01 suggestions with reasons come in M5
- [x] Split `routers/sessions.py` per stage before M3 to reduce merge conflicts (M3)
- [ ] Profile doesn't count non-numeric values in numeric columns (Telco `TotalCharges` has 11 blanks), so the planner can't see or fix them — add an `unparseable` count per column
