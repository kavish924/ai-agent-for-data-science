# Spec 07 — ML Baselines

> **Status:** Done · **Source:** PRD §6.7, §10 · **Milestone:** M5 · **Agent:** Analyst (deterministic)

## Purpose

Detect the prediction problem from a user-confirmed target column, train 2–3 honest
baseline models with cross-validation, and compare them without data leakage.

## User Story

> As a user, I want to pick a target and get a truthful comparison of simple baseline
> models, so I know what performance looks like before investing in anything complex.

## Requirements

| ID | Requirement |
|---|---|
| FR-ML-01 | The user selects or confirms the target column; the system also presents suggested candidates with reasons (e.g., `Survived` flagged from name/cardinality/type heuristics). *(M5)* `GET /sessions/{id}/targets` ranks candidates (outcome-like names, yes/no or few-category columns, last column) with a plain-language reason and the problem type each would give; identifiers, free text and dates are never suggested. |
| FR-ML-02 | Problem type is determined **by rules** on target dtype and cardinality: boolean or low-cardinality categorical (≤ 50 distinct, not `id_like`) → classification; *(M5)* integer-valued numeric with ≤ 10 distinct values (e.g. `Pclass`) → classification; other numeric → regression; `id_like`, text and datetime → rejected with explanation. A target with fewer than two distinct values, or a class with fewer than 2 rows, is rejected. Rows whose target is missing are dropped and counted. |
| FR-ML-03 | Train 2–3 baselines: classification → logistic regression + random forest (+ dummy classifier floor); regression → linear regression + random forest (+ dummy regressor floor). |
| FR-ML-04 | Use a proper train/test split (e.g., 80/20, stratified when classification) **and** cross-validation (StratifiedKFold-5 / KFold-5) on the training portion. |
| FR-ML-05 | **No leakage:** imputers, encoders, and scalers live inside a single sklearn `Pipeline` per model, so they are fit on training folds only. |
| FR-ML-06 | Fixed `RANDOM_SEED` everywhere; seeds and key hyperparameters recorded in `model_runs.json` (`params_fingerprint`) for reproducibility. |
| FR-ML-07 | Metrics: classification → accuracy, F1 (macro), ROC-AUC where applicable; regression → RMSE, MAE, R². Report per-fold scores, mean, and std per model. |
| FR-ML-08 | Persist `model_runs.json` (target, problem type, per-model results, split/CV config) and set session state `modeled`. *(M5)* Training runs as a background job: `executed`/`modeled` → `modeling` → `modeled`; a failure returns the session to `executed` with `failed_stage=model` and keeps any previous results. |
| FR-ML-09 | Provide the comparison table to the Narrator (Spec 08) as **computed numbers only**. |
| FR-ML-10 | *(M0 API, M5 use)* The target is chosen **before planning** via `PUT /sessions/{id}/target` (allowed in `profiled`/`awaiting_approval`; `null` clears it). `id_like` or unknown columns are rejected with `422`; a target that conflicts with the current plan is rejected with `422` listing the conflicting steps. The Gate then protects it (Spec 03 FR-PL-13). |
| FR-ML-12 | *(M5)* The best model is chosen by the primary cross-validated metric (classification: F1 macro; regression: RMSE, lower is better), never the dummy; the result says whether it beats the dummy floor and by how much. Timing is recorded separately from scores so scores stay byte-stable across runs. |
| FR-ML-13 | *(M5)* Datasets above `MODEL_MAX_ROWS` (default 50,000) are down-sampled with the fixed seed (stratified for classification) before splitting; the sample size is recorded. Feature columns that are `id_like`, text or datetime are excluded and listed. |
| FR-ML-14 | *(M5, UI)* The Download screen offers **Train baseline models**: target preselected (session target, else the top suggestion), progress while training, then a comparison table (CV mean ± std and hold-out score per model, best marked, dummy shown as the floor) with a "baselines, not production models" note. |
| FR-ML-11 | *(M5)* **No leakage from cleaning.** Ops are classed *structural* (`drop_duplicates`, `drop_column`, `cast_type`, `parse_datetime`, `standardize_text`) or *statistical* (`impute`, `clip_outliers`). The Analyst replays only the approved structural ops on `upload.csv`; statistical ops are re-created inside each model's `Pipeline` (imputer, `IQRClipper`) so they are fit on training folds only. The cleaned CSV deliverable still applies all approved ops; the report states this split. |

## Interfaces

- **Input:** `upload.csv` + the approved plan (structural ops replayed, FR-ML-11) + the
  confirmed target (`POST /sessions/{id}/model`, body `{target?}`)
- **Code:** `services/analyst.py` (rules, replay, pipelines, CV), `IQRClipper` transformer,
  endpoints in `routers/models.py`
- **Output:** `model_runs.json`; consumed by Spec 08 (report + narration)
- **LLM:** none in this spec; the Narrator explains results afterwards (its guardrails:
  `agents.md` §8, `design.md` §5.2)

## Acceptance Criteria

- **AC-1** Given Titanic cleaned data with target `Survived`, then problem type is
  `classification` and logistic regression + random forest (+ dummy) are trained with
  5-fold stratified CV.
- **AC-2** Given target `HousePrice` (continuous), then problem type is `regression`
  with the regression baseline set.
- **AC-3** Given target `PassengerId` (id_like), then the request is rejected before any
  training with an explanatory message.
- **AC-4** Given any run, then every preprocessing transformer is fit within the CV
  folds only (verified structurally by Pipeline usage — no fit-on-full-data calls exist
  in the code path).
- **AC-5** Given the same cleaned CSV, target, and seed, then re-running produces
  identical per-fold scores (PRD §9 Reproducibility).
- **AC-6** Given a dataset with nulls in features, then baselines train successfully
  because imputation occurs inside each pipeline.
- **AC-7** *(M5)* Given an approved plan that imputes a feature, the frame the Analyst
  trains on still has that feature's nulls (the impute is not replayed); the model's
  pipeline contains the matching imputer.
- **AC-8** *(M5)* Given Titanic, `GET /targets` ranks `Survived` first with a reason; it
  never suggests `PassengerId`, `Name` or `Ticket`.
- **AC-9** *(M5)* Given `POST /model` before execution → `409`; with an `id_like` target →
  `422`; on success the session passes `modeling` → `modeled` and `GET /model` returns
  the runs; a training failure returns the session to `executed` with `failed_stage=model`.
- **AC-10** *(M5)* The best model is never the dummy, and `beats_dummy` is reported.
- **AC-11** *(M5, UI)* Given model runs, the results table lists each model with its CV
  score and marks the best; the train button sends the chosen target.

## Dependencies

- Requires Specs 05 (cleaned CSV) and 04 (target confirmation flow). Feeds Spec 08.
  No LLM.

## Test Plan

- **Unit:** problem-type decision table; candidate-target heuristics; metric computation.
- **Integration (deterministic):** full run on Titanic sample with pinned seed →
  golden JSON of scores; id_like rejection; dummy-floor sanity (dummy ≤ best model on
  the Titanic fixture).

## Out of Scope

- Hyperparameter tuning, model deployment, feature engineering suggestions,
  clustering/time series (PRD §13.2 — out of v1 scope), deep learning (PRD §3).

## Open Questions

- Candidate-target suggestion threshold tuning (FR-ML-01) — evaluate on Titanic/Housing/Telco.

## Tasks

- [x] FR-ML-01 target suggestions
- [x] FR-ML-02 problem-type rules + target validation
- [x] FR-ML-03..07, 12, 13 baselines, split + CV, leakage-safe pipelines, metrics, best model
- [x] FR-ML-08 background job + `model_runs.json`
- [x] FR-ML-11 structural replay
- [x] FR-ML-14 UI

## Changelog

- 2026-11-12 — M5: FR-ML-02 rule for small-integer targets; FR-ML-08 background job;
  added FR-ML-12..14 and AC-7..11; FR-ML-01 suggestions endpoint.
- 2026-11-12 — M5 complete: AC-1..11 pass. Titanic via the API: random forest F1 0.801 vs dummy 0.381 (5-fold CV), 2.3 s; only structural ops replayed.
