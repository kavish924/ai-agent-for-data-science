# Project Checklist — AI Data Science Agent

> Living task list. Update it in the same branch as the work: tick `[x]` when a task is
> done **and verified** (tests/smoke green), add the branch name, and bump "Last updated".
> Detailed requirements live in `docs/specs/`; this file tracks progress only.
>
> **Last updated:** 2026-11-12 · **Current branch:** `m8-eval-demo` (not pushed)

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
| M4 Charts | `m4-charts` | ✅ done · merged to `main` (PR #4) |
| M5 ML baselines | `m5-ml-baselines` | ✅ done · in `main` (fast-forward push `62d4c5e..6707cec`, user-approved; no PR) |
| M6 Report + narration | `m6-report` | ✅ done · merged to `main` (PR #5) |
| M7 UI polish | `m7-ui-polish` | ✅ done · in `main` (fast-forward push `3cbc717..b7febdb`, user-approved; no PR) |
| M8 Evaluation + demo | `m8-eval-demo` | ✅ done · awaiting PR → `main` (full live eval pending Gemini quota) |

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
- [x] `pytest -m live` passes against real Gemini (2026-11-12, `gemini-3.5-flash`)
- [ ] Run `smoke_m3.py --live` on all three samples with the real key
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
- [x] Merged to `main` (PR #4)

## M5 — ML baselines · branch `m5-ml-baselines`

- [x] Spec 07 FR-ML-02 small-integer rule, FR-ML-08 background job, FR-ML-12..14 + AC-7..11; Spec 09 FR-AP-05 rev., FR-AP-20/21 + AC-12; `modeling` state + restart recovery
- [x] Tests written first (backend and frontend), watched fail, then implemented
- [x] Add `scikit-learn`; candidate-target suggestions with reasons (`GET /targets`)
- [x] Rule-based problem type; identifier / text / date / one-class targets rejected
- [x] Structural-op replay on the upload (FR-ML-11): impute/clip never applied before the split
- [x] Per-column pipelines: plan's imputer choice, `IQRClipper`, scaling (linear models), one-hot encoding
- [x] Dummy floor + logistic/linear regression + random forest; 80/20 hold-out + 5-fold CV; fixed seed
- [x] `model_runs.json` with fingerprint, best model (never the dummy), margin over the floor; `POST /model`, `GET /model`
- [x] Large data sampled to `MODEL_MAX_ROWS` (seeded, stratified)
- [x] UI: suggested target on the Profile screen; Baseline models panel (train, progress, comparison table, best marked)
- [x] Verified through the API on titanic.csv (RF F1 0.801 vs dummy 0.381, 2.3 s)
- [x] Clicked through in the browser pane: suggestion "Use it" → plan → approve & run → Train → results table (RF Best 0.801, dummy floor 0.381); screen stayed mounted during training
- [ ] Screenshot review of the model panel layout (the app window stopped drawing before it could be captured)
- [x] Gemini model fix: `gemini-2.5-flash` returns 404 for new keys → default `gemini-3.5-flash` (`1d89cd8`); `gemini-3.8-flash` was overloaded (503) at the time
- [x] `.claude/launch.json`: `backend` follows `.env` (Gemini), `backend-offline` for key-free demos
- [x] Into `main` by a user-approved fast-forward push (`62d4c5e..6707cec`); no PR record

## M6 — Report + narration · branch `m6-report`

- [x] Spec 08 FR-RP-07 revised (report from executed/modeled/reported), FR-RP-11..16 + AC-8..11; Spec 09 FR-AP-06 rev. + FR-AP-22 + AC-13; Spec 10 AC-4
- [x] Tests written first (backend and frontend), watched fail, then implemented
- [x] Narrator: named facts → `{{fact_id}}` placeholders; digit validator (known names allowed); retries; template fallback; `llm_calls` stage `narrator`
- [x] Reporter: Jinja2, seven sections in PRD order, self-contained HTML (charts embedded, no external requests), sparse paths, friendly type labels, version footer, no timestamps
- [x] Narration stored with a facts hash and reused → byte-identical re-renders; `renarrate` to force
- [x] ML section states replayed vs in-pipeline steps (FR-ML-11)
- [x] `POST /report`, `GET /report`, `GET /bundle.zip` (fixed zip timestamps → reproducible); `POST /model` allowed from `reported`
- [x] Spec 10 AC-4: one completion log line with `duration_ms` per stage (`plan.validated` gained its duration)
- [x] Fix: cleaned CSV download returned 404 while a model was training (`modeling` added to the allowed states)
- [x] UI: Process report card (Create report → Open report / Download all (.zip), summary source, Rewrite summary)
- [x] Live with real Gemini on titanic.csv: plan 9.8 s, narration passed the gate first try (7.3 s); every figure matches the artifacts
- [x] Report card clicked through in the app UI (Report tab, M7)
- [x] Merged to `main` (PR #5)

## M7 — UI polish · branch `m7-ui-polish`

- [x] Tooling: UI UX Pro Max (user skill), 21st skills (already current), Motion AI Kit (project: `motion` skill, `motion-reviewer`, `.mcp.json`)
- [x] One animation library: imports moved to `motion/react`, `framer-motion` removed; tests skip animations (`MotionGlobalConfig.skipAnimations`)
- [x] Spec 04 FR-RV-17..22 + AC-11..16; Spec 07 FR-ML-15 + AC-12; Spec 09 `changed_by_plan` — tests written first
- [x] Download screen in WAI-ARIA tabs (Overview · Charts · Models · Report), arrow/Home/End keys, animated indicator, `?tab=` deep link, next-step shortcuts
- [x] Report tab: report embedded in a fully sandboxed iframe; empty state with Create report
- [x] Plan history panel on the Review screen (read-only versions; completes Spec 04 AC-6)
- [x] Error states with a next step: unknown session → "This analysis isn't available" + Start a new analysis; network → Retry banner
- [x] Accessibility: skip link, one `h1` per screen, focus to the new heading after a screen change, polite announcements, "done" marks in the step indicator, 44 px header buttons; token contrast all ≥ WCAG AA (15 pairs checked)
- [x] Model panel hides targets the executed plan changed (`GET /targets` `changed_by_plan`)
- [x] Chart dialog: shared-layout morph replaced by scale + fade (layout exit never completed under Motion 14 in tests; cheaper in browsers)
- [x] Visual pass, part 1 (browser pane): Download screen with tabs, badges, step checkmarks and shortcuts; keyboard ArrowRight moves tab + `?tab=`; fixed a stray tab-bar scrollbar and a clipped tab focus ring
- [x] Visual pass, part 2: Charts thumbnails, Models table and the embedded report all render; found and fixed the report frame being blocked by the Claude app's browser (`sandbox=""` → `allow-same-origin`, still no scripts)
- [ ] Plan history panel not yet seen in the browser (covered by its component test)
- [x] Into `main` by a user-approved fast-forward push (`3cbc717..b7febdb`); no PR record

## M8 — Evaluation + demo · branch `m8-eval-demo`

- [x] Spec 10 NFR-09..12 + AC-8..10 (AC-1, AC-6 via the harness); Spec 03 FR-PL-18 + AC-13; Spec 08 FR-RP-17 + AC-12. Tests written first
- [x] `backend/eval/`: in-process harness through the real API (`python -m eval.run [--live]`), golden expectations (`golden.json`), JSON + Markdown results
- [x] Metrics: schema validity (first attempt), plan quality (sensible = expected present, nothing forbidden), approval rate (golden reviewer), time to report + stage times, transport errors counted apart
- [x] Reproducibility: executed plan replayed in a fresh session → cleaned CSV, chart PNGs, model scores identical; report re-render identical; report across sessions identical (template narration, session id masked). All 3 samples pass
- [x] Performance baseline: 100,000 × 21 Telco fixture (13 MB): upload+profile 11.3 s, execute (+re-profile, charts) 19.6 s; budget 60 s each
- [x] Offline eval on all 3 samples: 3/3 sensible, 100% first-attempt validity, 100% approval (`eval/results/offline.md`)
- [x] Live eval run 1 (Gemini): Titanic and Housing sensible, Telco planning failed on transient transport errors → **fix: backoff between transport retries + HTTP status in `llm_calls`** (FR-PL-18, FR-RP-17)
- [ ] Full live eval with the backoff (run 2 hit HTTP 429 `RESOURCE_EXHAUSTED`: key quota used up). Re-run `python -m eval.run --live` after the quota resets
- [x] Root `README.md` (setup, eval, development) and `docs/demo.md` (8-minute walkthrough + likely questions)
- [ ] Screenshots for the README (the browser pane can't save image files; take them by hand or add a Playwright script)
- [ ] Open PR `m8-eval-demo` → `main` and merge it (user)

## Known follow-ups / tech debt

- [ ] SQLite open/close per call is slow on Windows (~1 s per API flow in tests); consider WAL or a pooled connection
- [ ] Rotating log handler keeps `app.log` open (temp-dir cleanup on Windows)
- [ ] A 429 for a used-up *quota* (not a rate limit) can't be fixed by retrying; consider failing fast on `RESOURCE_EXHAUSTED` with a clearer message
- [ ] Don't run `npm run build` while `npm run dev` is running: both write `frontend/.next` and the dev server breaks (500s) until restarted
- [ ] Titanic `Name` is typed `id_like` (every name is unique) — confirm this is desired
- [ ] Next.js bundles postcss/sharp with open advisories (build-time CSS only; image optimisation disabled) — bump Next when fixed
- [x] Frontend tests for M3.5 were written right after the components, not red-first; M4 went back to red-first
- [x] Target candidates are "all non-identifier columns"; Spec 07 FR-ML-01 suggestions with reasons came in M5
- [x] Split `routers/sessions.py` per stage before M3 to reduce merge conflicts (M3)
- [x] Model panel offers targets the executed plan changed — filtered via `changed_by_plan` (M7)
- [ ] Consider moving to `gemini-3.8-flash` once its 503 "high demand" errors stop (one `GEMINI_MODEL` change in `.env`)
- [ ] Narration wording can still be inaccurate without a wrong number (live run said the charts cover "model evaluation results"; they don't) — tighten the prompt or add a facts-only phrasing check
- [ ] Reproducible Python script of the executed steps (Spec 08 FR-RP-06 stretch)
- [ ] Profile doesn't count non-numeric values in numeric columns (Telco `TotalCharges` has 11 blanks), so the planner can't see or fix them — add an `unparseable` count per column
