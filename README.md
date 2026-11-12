# AI Data Science Agent

Upload a CSV and get back a cleaned dataset, charts, baseline models and a process report. An AI
writes the cleaning plan and the summary. **You approve every step, and all data work is deterministic code.**

> The LLM plans and narrates. It never sees raw rows, and nothing it writes is executed.

## What it does

1. **Upload and profile.** Encoding and delimiter are detected, then columns are typed (numeric, categorical,
   boolean, datetime, text, identifier) with missing values, duplicates and outliers counted.
2. **Pick a target (optional).** You get ranked suggestions with reasons. The target is protected: no
   step may impute, clip or drop it.
3. **AI cleaning plan.** Gemini proposes steps from a 7-op whitelist. It sees only aggregate
   statistics (`llm_profile()`), and every plan passes a code-owned Gate before you see it.
4. **Review and approve.** Approve, skip or edit each step. Destructive steps are flagged, and plan
   versions are kept.
5. **Run.** The approved plan executes with a before/after log, and the original upload is never changed.
   The cleaned data is re-profiled and up to 12 charts are drawn.
6. **Baseline models.** A dummy floor, linear or logistic regression, and a random forest. Imputation
   and clipping live inside sklearn pipelines, so nothing leaks from the test folds.
7. **Report.** A self-contained HTML report and a zip bundle. The AI summary may cite numbers only
   through placeholders, and a digit validator rejects anything else (with a template fallback).

## Quick start

Requirements: Python 3.11, Node 20+.

```bash
cp .env.example .env
```

Put your key in `.env` as `GEMINI_API_KEY=...`, or set `LLM_PROVIDER=offline` to run with no key.
The key belongs in `.env` (gitignored), never in `.env.example`.

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
```

On macOS/Linux use `.venv/bin/pip`, and `.venv/bin/python` below.

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000. The frontend proxies `/api/v1` to the backend on port 8000. API
docs are at http://localhost:8000/docs.

## Evaluation (M8)

```bash
cd backend && .venv/Scripts/python -m eval.run
```

This runs the full pipeline in-process on `samples/` (titanic, housing, telco) and scores it against
golden expectations ([backend/eval/golden.json](backend/eval/golden.json)). It writes the results to
[backend/eval/results/](backend/eval/results/). Add `--live` to plan and narrate with real Gemini.

Each run measures:
- **schema validity:** the share of first attempts that are valid;
- **plan quality:** a plan is sensible when every expected step is there and nothing forbidden is;
- **approval rate:** the share of proposed steps a scripted reviewer would approve;
- **time to report**, with per-stage times;
- **reproducibility:** the approved plan is replayed in a fresh session, and the cleaned CSV, charts,
  model scores and report must come out identical;
- **performance:** a 100k-row fixture must profile and execute within 60 s each.

Latest offline run ([offline.md](backend/eval/results/offline.md)): all 3 plans sensible, 100%
first-attempt validity, every reproducibility check identical, and the 100k × 21 fixture profiled in
11 s and executed in 20 s. Live notes are in [live-2026-11-12.md](backend/eval/results/live-2026-11-12.md).

## Development

Spec-driven: requirements live in [docs/specs/](docs/specs/) as FR/AC tables. Every AC has a test
named `test_<prefix>_ac<N>_…`, which [docs/specs/traceability.md](docs/specs/traceability.md) maps and
`scripts/check_traceability.py` enforces. The working rules are in [CLAUDE.md](CLAUDE.md), and progress is in
[docs/CHECKLIST.md](docs/CHECKLIST.md).

```bash
cd backend && .venv/Scripts/python -m pytest -m "not live" && .venv/Scripts/ruff check . && .venv/Scripts/mypy && .venv/Scripts/python scripts/check_traceability.py
```

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

A walkthrough for presenting the app is in [docs/demo.md](docs/demo.md). Architecture and
design are in [docs/architecture.md](docs/architecture.md) and [docs/design.md](docs/design.md).

## Stack

FastAPI · pandas · scikit-learn · matplotlib · Jinja2 · SQLite · Google Gemini (`google-genai`) ·
Next.js 15 · React 19 · Tailwind 4 · Motion · Vitest
