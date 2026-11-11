# Spec 00 — Project Overview

> **Status:** Draft v0.1 · **Source:** PRD §1–§4, §11–§13 · **Type:** Context (no FRs)

## 1. Vision

An agent that takes a CSV from upload to a complete, honest analysis report in minutes:
profiling, LLM-proposed cleaning under human approval, deterministic execution, charts,
and cross-validated baseline models — delivered as two files: the cleaned dataset and a
process report.

## 2. Core Principle

> **The LLM plans and narrates; all data work is deterministic.**
> The LLM never touches raw rows and never writes free-form code. It returns structured
> plans validated against a whitelist and executed by pandas/scikit-learn.

This principle bounds every requirement in Specs 01–10. Any feature that would let LLM
output execute or reach raw data is out of scope by definition.

## 3. Goals (PRD §3)

- CSV upload → complete report in a few minutes with minimal manual effort
- Every transformation reproducible, auditable, reversible
- User in control: approve/edit step before any data is changed
- Honest, measured model recommendations from real baseline results

## 4. Non-Goals (PRD §3)

- Not AutoML: no tuning or deployment of production models
- No databases, streaming data, or files beyond CSV
- No deep learning, NLP, or image models
- No multi-user accounts or collaboration in v1

## 5. Target Users (PRD §4)

| User | Need |
|---|---|
| **Primary:** students, junior data scientists | Fast, guided starting point on an unfamiliar dataset |
| **Secondary:** analysts, developers | Quick look at an unfamiliar CSV |

## 6. Pipeline & Milestone Map

| Stage | Spec | Milestone |
|---|---|---|
| Upload & ingestion | `01-upload-ingestion.md` | M1 ✅ |
| Data profiler | `02-data-profiler.md` | M1 ✅ |
| Cleaning executor | `05-cleaning-executor.md` | M2 ✅ |
| Hardening: approval flow, Gate/executor fixes, privacy projection, state table | 01, 02, 05, 09, 10 | **M0** (new) |
| Cleaning planner (LLM) | `03-cleaning-planner.md` | M3 |
| Thin UI slice: upload → target → review → approve → execute → download | `04-plan-review-ui.md` | **M3.5** (new) |
| Chart generation | `06-chart-generation.md` | M4 |
| ML baselines | `07-ml-baselines.md` | M5 |
| Report generation | `08-report-generation.md` | M6 |
| UI polish | `04-plan-review-ui.md` | M7 |
| Evaluation & polish | all (success metrics, PRD §9) | M8 |

Order revised 2026-11-11: hardening (M0) runs before M3 and a thin UI follows M3, so the
flow can be demoed end to end early. The PRD order is preserved otherwise.

Cross-cutting: `09-api-contracts.md` (API), `10-nfr-observability.md` (NFRs).

## 7. Companion Docs

- `docs/system-guide.md` — end-user/operator walkthrough
- `docs/architecture.md` — components, diagrams, data flow
- `docs/design.md` — decisions (D1–D8), data model, whitelist design
- `docs/tech-stack.md` — stack, layout, setup
- `docs/agents.md` — agent responsibilities and contracts

## 8. Standing Assumptions

Open PRD questions (§13) resolved by default for v1 — revisit before launch:

| Question | Default |
|---|---|
| LLM provider | **Google Gemini** (`google-genai`), behind a provider-agnostic client interface. *Deliberate deviation from PRD §8, which names OpenAI.* |
| Target column | User confirms; system suggests candidates (Spec 07) |
| Model scope | Tabular classification + regression only |
| Data privacy | Aggregate profile only to the LLM — no sample values |
| Deployment | Local demo only (SQLite + filesystem) |
| Report format | HTML for MVP; PDF is stretch |
| Audience | Portfolio/MVP first |

## 9. Glossary

| Term | Meaning |
|---|---|
| **Profile** | Compact JSON of column-level statistics; the only data the LLM sees |
| **Plan** | Ordered list of whitelisted cleaning operations with rationales |
| **Gate** | Code-owned Pydantic validation every LLM output must pass |
| **Session** | One upload's full lifecycle: state + artifacts under `storage/sessions/{id}/` |
| **Whitelist** | The seven allowed cleaning operations (Spec 03 §4) |
| **Execution log** | Per-step before/after record produced by the Executor |
| **Deliverables** | `cleaned_<name>.csv` + `report.html` (PRD §6.9) |
