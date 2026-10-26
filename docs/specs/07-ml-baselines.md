# Spec 07 — ML Baselines

> **Status:** Draft v0.1 · **Source:** PRD §6.7, §10 · **Milestone:** M5 · **Agent:** Analyst (deterministic)

## Purpose

Detect the prediction problem from a user-confirmed target column, train 2–3 honest
baseline models with cross-validation, and compare them without data leakage.

## User Story

> As a user, I want to pick a target and get a truthful comparison of simple baseline
> models, so I know what performance looks like before investing in anything complex.

## Requirements

| ID | Requirement |
|---|---|
| FR-ML-01 | The user selects or confirms the target column; the system also presents suggested candidates with reasons (e.g., `Survived` flagged from name/cardinality/type heuristics). |
| FR-ML-02 | Problem type is determined **by rules** on target dtype and cardinality: boolean or low-cardinality categorical (≤ 50 distinct, not `id_like`) → classification; continuous numeric → regression; `id_like`/near-unique → rejected with explanation. |
| FR-ML-03 | Train 2–3 baselines: classification → logistic regression + random forest (+ dummy classifier floor); regression → linear regression + random forest (+ dummy regressor floor). |
| FR-ML-04 | Use a proper train/test split (e.g., 80/20, stratified when classification) **and** cross-validation (StratifiedKFold-5 / KFold-5) on the training portion. |
| FR-ML-05 | **No leakage:** imputers, encoders, and scalers live inside a single sklearn `Pipeline` per model, so they are fit on training folds only. |
| FR-ML-06 | Fixed `RANDOM_SEED` everywhere; seeds and key hyperparameters recorded in `model_runs.json` (`params_fingerprint`) for reproducibility. |
| FR-ML-07 | Metrics: classification → accuracy, F1 (macro), ROC-AUC where applicable; regression → RMSE, MAE, R². Report per-fold scores, mean, and std per model. |
| FR-ML-08 | Persist `model_runs.json` (target, problem type, per-model results, split/CV config) and set session state `modeled`. |
| FR-ML-09 | Provide the comparison table to the Narrator (Spec 08) as **computed numbers only**. |

## Interfaces

- **Input:** `cleaned_<name>.csv` (Spec 05) + confirmed target from the UI
  (`POST /sessions/{id}/model`)
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
