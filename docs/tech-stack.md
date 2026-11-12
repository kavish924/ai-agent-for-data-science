# Tech Stack — AI Data Science Agent

> **Status:** Draft v0.1 · **Traces to:** PRD §7, §8 · **Design rationale:** `design.md` §2

## 1. Stack Overview

| Layer | Choice | Version | Why (PRD §8) |
|---|---|---|---|
| Frontend | **Next.js** (App Router) + **Tailwind CSS** | 15.x / 4.x | Upload, plan review with toggles, chart gallery, report view |
| Backend | **FastAPI** (Python) | 0.11x | Async endpoints, native Pydantic validation, `BackgroundTasks` |
| Data processing | **pandas** | 2.x | Deterministic cleaning execution |
| ML | **scikit-learn** | 1.5+ | Baselines + `cross_validate` + leakage-safe `Pipeline` |
| Charts | **matplotlib** | 3.x | Histograms, box plots, heatmap, missingness map, top categories (PNG artifacts) |
| LLM | **Google Gemini API** (`google-genai` SDK) | gemini-3.5-flash default | Structured JSON output (response schema + JSON mime type) for planning and narration; model configurable via env |
| Validation | **Pydantic v2** | 2.x | Schema gate on all LLM output; whitelist enforcement (ships inside FastAPI) |
| Metadata DB | **SQLite** | 3.x | Zero-ops session store; interface allows Postgres swap |
| Artifact store | **Filesystem** | — | `storage/sessions/{id}/…`; interface allows object-store swap |
| Jobs | **FastAPI BackgroundTasks** | — | Stage execution + UI progress polling (queue = upgrade path) |
| Config | **pydantic-settings** | 2.x | Typed env config |

## 2. Tooling & Quality

| Tool | Purpose |
|---|---|
| **uv** (or pip + venv) | Dependency management, locking |
| **pytest** + coverage | Unit/integration tests; **LLM calls always mocked** except a marked optional live suite |
| **ruff** | Lint + format |
| **mypy** | Type checking (strict on `services/` core) |
| **pre-commit** | Hooks: ruff, mypy, whitespace |

## 3. Repository Layout

```
ai-agent-for-datascience/
├── docs/                      # this documentation set + specs/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory, static export mount
│   │   ├── config.py          # pydantic-settings
│   │   ├── routers/           # sessions, profile, plan, execute, model, report
│   │   ├── services/          # profiler, planner, executor, charts, baselines, reporter, narrator
│   │   ├── agents/            # agent wrappers + orchestrator (see agents.md)
│   │   ├── llm/               # Gemini client (behind a provider-agnostic interface), prompts, retry loop
│   │   ├── schemas/           # Pydantic models: profile, plan ops (whitelist), reports
│   │   ├── db/                # SQLite session store, models, migrations
│   │   └── storage/           # artifact store interface + filesystem impl
│   ├── pyproject.toml         # backend package, pytest/ruff/mypy config
│   └── tests/
│       ├── unit/              # gate, profiler, executor rules (no LLM)
│       └── integration/       # API + pipeline with mocked LLM
├── frontend/                  # Next.js + Tailwind
│   └── app/                   # upload, review, progress, results pages
├── storage/                   # artifact root (gitignored)
├── samples/                   # Titanic / Housing / Telco for evals (PRD §9)
├── .env.example
└── CLAUDE.md                  # spec-driven workflow rules
```

## 4. Environment Variables

```bash
# .env.example
GEMINI_API_KEY=...               # required from M3 (planner/narrator)
GEMINI_MODEL=gemini-3.5-flash    # configurable, not hard-coded
MAX_FILE_SIZE_MB=25              # PRD §6.1 limits
MAX_ROWS=100000
MAX_CHARTS=12                    # PRD §6.6 cap
PLAN_MAX_RETRIES=3               # PRD §6.3 bounded retries
RETENTION_DAYS=7                 # PRD §7 privacy: upload deletion window
DB_PATH=storage/app.db
STORAGE_ROOT=storage
LOG_LEVEL=INFO
RANDOM_SEED=42                   # reproducibility (PRD §7)
```

## 5. Local Setup

```bash
# Backend
cd backend
uv sync                          # or: python -m venv .venv && pip install -e ".[dev]"
uvicorn app.main:app --reload    # http://localhost:8000 (API docs at /docs)

# Frontend
cd frontend
npm install
npm run dev                      # http://localhost:3000

# Quality gates
pytest                           # unit + integration (LLM mocked)
ruff check . && mypy app
```

## 6. Deliberate Exclusions (MVP)

| Excluded | Why | Revisit |
|---|---|---|
| Postgres, object storage | No local-MVP benefit (D5) | Hosted deployment |
| Celery/RQ/arq queue | BackgroundTasks sufficient for demo scale | Multi-worker isolation needs |
| PDF report (weasyprint) | HTML-first (D6) | Stretch (PRD §12) |
| Excel/Parquet ingestion | CSV-only v1 (PRD §3) | Stretch (PRD §12) |
| Auth/multi-user | Non-goal v1 (PRD §3) | Any hosted launch |
| AutoML / tuning / deployment | Non-goal (PRD §3) | — |

## 7. Version Pinning & Reproducibility

- `uv.lock` / `requirements.txt` pinned; Python `3.12.x`
- Tool versions recorded in each report (pandas/sklearn versions matter for
  byte-identical outputs — PRD §7 Determinism)
- `RANDOM_SEED` propagated to every model and sampler
- LLM outputs are the only non-deterministic artifacts; they are stored per session, so
  **re-execution and reporting remain deterministic** given a fixed plan
