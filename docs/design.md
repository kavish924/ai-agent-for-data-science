# Design — AI Data Science Agent

> **Status:** Draft v0.1 · **Traces to:** PRD §3, §6, §7, §10 · **Companion docs:** `architecture.md`, `agents.md`

## 1. Design Principles

1. **The LLM plans and narrates; all data work is deterministic.** The LLM never touches
   raw data and never emits executable code. This is the PRD's core principle (§1) and
   every decision below serves it.
2. **Human approval is mandatory before data changes** (§6.4). The system is an
   assistant, not an autonomous rewriter.
3. **Originals are immutable.** Cleaning always produces new artifacts; the upload is
   never modified (§6.5).
4. **Every action is explainable and auditable.** Each plan step carries a rationale and
   a before/after log entry (§6.5, §7 Observability).
5. **Honest recommendations.** Model suggestions come from real cross-validated
   baselines, not vibes (§3 Goals).
6. **Fail loud, fail early.** Invalid input, invalid LLM output, and invalid targets are
   rejected with specific messages rather than silently "fixed".

## 2. Key Decisions & Trade-offs

| # | Decision | Rationale | Alternative rejected |
|---|---|---|---|
| D1 | **Whitelisted operation vocabulary** instead of LLM-written code | Eliminates arbitrary code execution (PRD §7 Safety, §10 Risk 1); every op is reviewable, testable, reversible | Sandboxed code execution (prompt-injection and correctness risk; hard to audit) |
| D2 | **Profile-only LLM input** | Privacy (PRD §7): aggregate statistics leak far less than rows; also shrinks tokens/cost | Sending sample rows (better plans, but privacy risk — kept as an *open question* in PRD §13.3) |
| D3 | **Pydantic gate + bounded retries** on all LLM output | Wrong/unknown ops are rejected deterministically; the validation error is fed back to the LLM (§6.3) | Trusting JSON mode alone (schema-conform output can still contain unknown ops) |
| D4 | **Session state machine** with per-stage artifacts | Any stage can fail and retry independently; artifacts make the report fully reconstructible | One-shot pipeline (a single failure would lose everything) |
| D5 | **SQLite + filesystem behind interfaces** | Zero-ops local MVP; interfaces keep the hosted swap (Postgres/object storage) cheap (PRD §8) | Starting with Postgres + S3 (ops burden with no MVP benefit) |
| D6 | **HTML-first report**, PDF as stretch | HTML is renderable in-process with no extra binaries (PRD §6.8) | weasyprint/wkhtmltopdf from day one (heavy dependency, layout pain) |
| D7 | **Rule-based problem-type detection** (target dtype + cardinality) | Deterministic and explainable; matches §6.7 | LLM-decided problem type (non-deterministic, unverifiable) |
| D8 | **Narration from computed numbers only** | Prevents the LLM from inventing findings (PRD §10 Risk 4); report numbers stay byte-stable across runs | Free-form LLM summary over raw outputs |

## 3. Data Model

### 3.1 Sessions (SQLite)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Session ID returned by `POST /sessions` |
| `original_filename` | text | Display only |
| `state` | enum | `uploaded → profiled → planned → awaiting_approval → executing → executed → modeled → reported` (+ per-stage `error` fields) |
| `n_rows`, `n_columns` | int | From ingestion |
| `created_at`, `updated_at` | timestamp | Retention clock runs from `created_at` |
| `retention_expires_at` | timestamp | Upload deletion time (privacy, PRD §7) |

### 3.2 Plan Steps

| Field | Type | Notes |
|---|---|---|
| `session_id` | FK | |
| `step_index` | int | Execution order |
| `op` | enum | Whitelist (§4) — anything else is rejected by the gate |
| `column` | text \| null | Target column (null for frame-wide ops like `drop_duplicates`) |
| `params` | JSON | Constrained per op (§4) |
| `rationale` | text | LLM-provided, shown in review UI |
| `status` | enum | `proposed → approved / disabled / edited → executed` |
| `before` / `after` | JSON | Row/col counts, null count, outlier count — filled at execution |

### 3.3 Other Records

- **`artifacts`** — `session_id`, `kind` (`profile|plan|cleaned_csv|chart|model_runs|narration|report`), `path`, `created_at`
- **`model_runs`** — `session_id`, `target`, `problem_type`, `model_name`, `cv_scores` (fold list), `mean`, `std`, `params_fingerprint` (for reproducibility)
- **`llm_calls`** — `session_id`, `stage`, `attempt`, `valid` (bool), `error`, token counts; **never** payload contents (privacy)

## 4. Operation Whitelist (PRD §6.3)

The planner may only emit these operations. Each op has a Pydantic schema; params are
validated against column type from the profile.

| Op | Params | Constraints / validation |
|---|---|---|
| `drop_duplicates` | — | Frame-wide; no params |
| `drop_column` | `columns: list[str]` | Columns must exist; never the target later (checked at model stage) |
| `impute` | `strategy: mean\|median\|mode\|constant`, `value?` (constant only) | mean/median → numeric columns; mode → any; constant requires `value` |
| `clip_outliers` | `method: iqr`, `factor?: float = 1.5` | Numeric columns only; same IQR method as profiler |
| `cast_type` | `to: int\|float\|str\|bool\|category` | Rejected if the cast would error on observed values (dry-run first) |
| `parse_datetime` | `format?: str` | Text/date-like columns; failure at execution is logged, not fatal |
| `standardize_text` | `ops: [trim, lowercase, collapse_spaces]` | Text/categorical columns |

**Gate rules:** unknown op → reject; missing/extra params → reject; unknown column →
reject; type-incompatible op → reject. Rejection returns a structured error to the LLM
for a bounded number of retries (default 3), then the stage fails visibly (D3).

**Versioning:** the whitelist is versioned in the plan JSON (`"schema": "v1"`), so old
sessions remain interpretable as ops evolve.

## 5. LLM Interaction Design

### 5.1 Planner prompt contract

- **Input:** compact profile JSON only (D2). Includes column names, types, null counts/%,
  unique counts, top values, outlier counts, duplicate-row count.
- **Output:** `{"schema": "v1", "steps": [{op, column, params, rationale}, ...]}` — no prose.
- **Retry loop:** `generate → validate → (reject: append error, regenerate) ≤ N → fail`.
  Each retry is logged to `llm_calls` (schema validity rate metric, PRD §9).
- **Temperature:** low (deterministic-leaning); seed pinned when supported (reproducibility).

### 5.2 Narrator prompt contract

- **Input:** computed numbers only — profile deltas, execution-log summary, model
  comparison table (D8).
- **Output:** short plain-language sections; the report's **numbers themselves are never
  LLM-generated** — the template inserts computed values, narration only surrounds them.

## 6. Execution Semantics (PRD §6.5)

- Steps apply **in approved order**; each step runs on the output of the previous one
- Before each step: snapshot counts (`rows`, `cols`, `null_cells`, `outliers`); same after → `before`/`after` log
- `cast_type` performs a **dry-run validation** before mutating; a failing step aborts
  execution, keeps the log, and marks the session `error` (retry with edited plan)
- Column names/order preserved unless an approved `drop_column` (or future rename) applies (§6.5)
- Reproducibility: same upload + same approved plan + same tool versions ⇒ identical
  cleaned CSV (random_state pinned everywhere; no time-dependent transforms in v1)

## 7. Chart Selection Rules (PRD §6.6)

| Column profile | Chart |
|---|---|
| Numeric | Histogram + box plot |
| Categorical (low cardinality) | Top-category bar chart |
| Dataset-wide (numeric cols ≥ 2) | Correlation heatmap |
| Dataset-wide (any nulls) | Missing-value map |

Cap total charts (default 12); when over the cap, prioritize by issue severity
(nulls > outliers > cardinality), then column order — documented so the cap is
predictable, not arbitrary.

## 8. Baseline Modeling Design (PRD §6.7)

**Problem-type detection (rules, D7):**

| Target looks like | Problem type |
|---|---|
| Boolean, or object/category with cardinality 2–`max_cat` (e.g., ≤ 50) and non-ID-like | Classification |
| Numeric, continuous | Regression |
| ID-like / near-unique | Rejected before training |

**Baselines:** classification → logistic regression, random forest (+ dummy classifier
as a floor); regression → linear regression, random forest (+ dummy regressor).
`random_state=42`, fixed CV (e.g., StratifiedKFold-5 / KFold-5).

**Leakage prevention (PRD §10):** imputers, encoders, and scalers are fit **on the
training split only** via a single `sklearn.Pipeline` per model; CV is done with
`cross_validate` so every fold re-fits preprocessing inside the pipeline.

**Explaining results:** the Narrator receives the comparison table (per-model mean/std)
and explains trade-offs in plain language; it never declares a "production-ready" model —
these are baselines (PRD §3 Non-Goals).

## 9. Report Structure (PRD §6.8)

Rendered in order, all sections present even when sparse:

1. Dataset snapshot (before/after shape, types)
2. Issues found (from profile)
3. Cleaning plan & actions — each with rationale, approval status, before/after counts
4. Before-vs-after comparison
5. Charts
6. ML analysis — detection, baselines, CV table
7. Narrated summary

## 10. Traceability

| PRD | Design element |
|---|---|
| §1 principle | §1.1, D1–D3, D8 |
| §6.3 planner | §4, §5.1 |
| §6.4 review | §3.2 `status`, review flow in `system-guide.md` §3 |
| §6.5 executor | §6 |
| §6.6 charts | §7 |
| §6.7 models | §8 |
| §6.8/§6.9 report & deliverables | §9 |
| §7 NFRs | §1, §6 (reproducibility), `architecture.md` §7 (observability), D2 (privacy) |
| §10 risks | D1, D3 (harmful step); §8 (leakage); D8 (narration); §3.1 + D2 (sensitive data) |
