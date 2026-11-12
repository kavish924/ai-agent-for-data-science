"""Baseline modeling (Spec 07). Deterministic, no LLM.

Leakage safety (FR-ML-05/11): the Analyst never trains on the cleaned CSV. It replays
only the approved *structural* steps on the original upload; the plan's *statistical*
steps (impute, clip) become per-column pipeline transformers, so every statistic is
learned on the training fold it is applied to.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..schemas.plan import EXECUTABLE_STATUSES, OP_CLASS
from .executor import apply_step
from .numeric import parse_numeric
from .profiler import infer_column_type
from .transformers import IQRClipper

logger = logging.getLogger("analyst")

N_SPLITS = 5
TEST_SIZE = 0.2
MAX_CLASSES = 50
SMALL_INT_CLASSES = 10
TARGET_HINTS = ("target", "label", "class", "outcome", "survived", "churn", "default", "fraud",
                "price", "value", "response", "result", "y")

MODELS = {
    "classification": ["dummy", "logistic_regression", "random_forest"],
    "regression": ["dummy", "linear_regression", "random_forest"],
}
PRIMARY = {"classification": "f1_macro", "regression": "rmse"}
NOTE = ("These are baselines: simple models with default settings, to show what a first "
        "attempt achieves. They are not tuned and are not production models.")


class TargetError(Exception):
    """The chosen target can't be modeled (HTTP 422)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# --- target rules (FR-ML-01/02) ---------------------------------------------------

def _hinted(name: str) -> bool:
    lowered = name.lower()
    words = lowered.replace("-", "_").replace(" ", "_").split("_")
    return any(hint == lowered or hint in words or (len(hint) > 3 and hint in lowered)
               for hint in TARGET_HINTS)


def suggest_targets(profile: dict, limit: int = 5) -> list[dict]:
    """Rank plausible prediction targets with a plain-language reason (FR-ML-01)."""
    columns = profile.get("columns", [])
    ranked = []
    for index, column in enumerate(columns):
        kind, flags = column["type"], column.get("flags", [])
        if kind in ("id_like", "text", "datetime") or {"all_empty", "single_value"} & set(flags):
            continue
        score, reasons = 0.0, []
        if _hinted(column["name"]):
            score += 3
            reasons.append("its name looks like an outcome")
        if kind == "boolean":
            score += 2
            reasons.append("it has yes/no values")
            problem = "classification"
        elif kind == "categorical":
            score += 1 if column["unique"] <= SMALL_INT_CLASSES else 0.5
            reasons.append(f"it has {column['unique']} categories")
            problem = "classification"
        else:  # numeric
            small = column["unique"] <= SMALL_INT_CLASSES
            score += 1 if small else 0.5
            reasons.append(
                f"it has {column['unique']} distinct values" if small else "it is a continuous number"
            )
            problem = "classification" if small else "regression"
        if index == len(columns) - 1:
            score += 1
            reasons.append("it is the last column")
        if column.get("nulls"):
            score -= 0.5
        reason = reasons[0][0].upper() + "; ".join(reasons)[1:]
        ranked.append((-score, index, {"column": column["name"], "problem_type": problem, "reason": reason}))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def problem_type(series: pd.Series, name: str) -> str:
    """Rule-based problem type for a target column (FR-ML-02). Raises TargetError."""
    present = series.dropna()
    kind, _ = infer_column_type(series.rename(name))
    if kind == "id_like":
        raise TargetError("invalid_target", f"'{name}' looks like an identifier, so it can't be predicted.")
    if kind in ("text", "datetime"):
        raise TargetError(
            "invalid_target", f"'{name}' is a {kind} column; pick a number or category to predict."
        )
    if present.nunique() < 2:
        raise TargetError("invalid_target", f"'{name}' needs at least two different values to predict.")
    if kind == "boolean":
        return "classification"
    if kind == "categorical":
        if present.nunique() > MAX_CLASSES:
            raise TargetError("invalid_target", f"'{name}' has more than {MAX_CLASSES} categories.")
        return "classification"
    values = parse_numeric(present)[0].dropna()
    if (values == values.round()).all() and values.nunique() <= SMALL_INT_CLASSES:
        return "classification"
    return "regression"


# --- data preparation (FR-ML-11/13) -----------------------------------------------

def replay_structural(upload: pd.DataFrame, steps: list[dict]) -> tuple[pd.DataFrame, list[str]]:
    """Apply only the approved structural steps; statistical ones go into the pipeline."""
    frame, replayed = upload, []
    for step in steps:
        if step.get("status") in EXECUTABLE_STATUSES and OP_CLASS[step["op"]] == "structural":
            frame, _ = apply_step(frame, step)
            replayed.append(step["op"])
    return frame, replayed


def _statistical_steps(steps: list[dict]) -> dict[str, dict[str, dict]]:
    """Per column: the approved impute / clip parameters (later steps win)."""
    found: dict[str, dict[str, dict]] = {}
    for step in steps:
        if step.get("status") in EXECUTABLE_STATUSES and OP_CLASS[step["op"]] == "statistical":
            found.setdefault(step["column"], {})[step["op"]] = step.get("params") or {}
    return found


def _imputer(params: dict | None, numeric: bool) -> SimpleImputer:
    strategy = (params or {}).get("strategy")
    if strategy == "constant":
        value = params.get("value") if params else None
        if numeric and not isinstance(value, (int, float)):
            return SimpleImputer(strategy="median")
        return SimpleImputer(strategy="constant", fill_value=value)
    if strategy in ("mean", "median") and numeric:
        return SimpleImputer(strategy=strategy)
    if strategy == "mode" or not numeric:
        return SimpleImputer(strategy="most_frequent")
    return SimpleImputer(strategy="median")


def build_pipeline(
    model_name: str,
    problem: str,
    *,
    numeric: list[str],
    categorical: list[str],
    steps: list[dict],
    seed: int,
) -> Pipeline:
    """One leakage-safe Pipeline: per-column preprocessing + the estimator (FR-ML-05)."""
    statistical = _statistical_steps(steps)
    scale = model_name in ("logistic_regression", "linear_regression")
    transformers: list[tuple[str, Any, list[str]]] = []
    for column in numeric:
        parts: list[tuple[str, Any]] = []
        clip = statistical.get(column, {}).get("clip_outliers")
        if clip is not None:
            parts.append(("clip", IQRClipper(factor=float(clip.get("factor", 1.5)))))
        parts.append(("impute", _imputer(statistical.get(column, {}).get("impute"), numeric=True)))
        if scale:
            parts.append(("scale", StandardScaler()))
        transformers.append((f"num_{column}", Pipeline(parts), [column]))
    for column in categorical:
        transformers.append((f"cat_{column}", Pipeline([
            ("impute", _imputer(statistical.get(column, {}).get("impute"), numeric=False)),
            ("encode", OneHotEncoder(handle_unknown="ignore", max_categories=20)),
        ]), [column]))
    preprocess = ColumnTransformer(transformers, remainder="drop", sparse_threshold=0)

    estimator: Any
    if model_name == "dummy":
        estimator = (DummyClassifier(strategy="most_frequent") if problem == "classification"
                     else DummyRegressor(strategy="mean"))
    elif model_name == "logistic_regression":
        estimator = LogisticRegression(max_iter=2000)
    elif model_name == "linear_regression":
        estimator = LinearRegression()
    else:
        cls = RandomForestClassifier if problem == "classification" else RandomForestRegressor
        estimator = cls(n_estimators=100, min_samples_leaf=2, random_state=seed, n_jobs=-1)
    return Pipeline([("preprocess", preprocess), ("model", estimator)])


def _features(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    numeric, categorical, excluded = [], [], []
    columns: dict[str, pd.Series] = {}
    for column in frame.columns:
        if column == target:
            continue
        kind, _ = infer_column_type(frame[column].rename(column))
        if kind == "numeric":
            numeric.append(column)
            columns[column] = parse_numeric(frame[column])[0]  # row-wise parse: no leakage
        elif kind in ("categorical", "boolean"):
            categorical.append(column)
            series = frame[column]
            columns[column] = series.astype(object).where(series.isna(), series.astype(str))
        else:
            excluded.append(column)
    return pd.DataFrame(columns, index=frame.index), numeric, categorical, excluded


# --- training (FR-ML-03..08, 12, 13) ----------------------------------------------

def _clean(value: Any) -> float | None:
    number = float(value)
    return None if not np.isfinite(number) else round(number, 6)


def _summary(scores: np.ndarray) -> dict:
    folds = [_clean(v) for v in scores]
    present = np.array([v for v in folds if v is not None], dtype="float64")
    return {"folds": folds,
            "mean": _clean(present.mean()) if present.size else None,
            "std": _clean(present.std()) if present.size else None}


def _scoring(problem: str, n_classes: int) -> dict[str, str]:
    if problem == "classification":
        return {"accuracy": "accuracy", "f1_macro": "f1_macro",
                "roc_auc": "roc_auc" if n_classes == 2 else "roc_auc_ovr"}
    return {"rmse": "neg_root_mean_squared_error", "mae": "neg_mean_absolute_error", "r2": "r2"}


def _holdout(pipeline: Pipeline, problem: str, X: pd.DataFrame, y: pd.Series) -> dict:
    predicted = pipeline.predict(X)
    if problem == "regression":
        return {"rmse": _clean(np.sqrt(mean_squared_error(y, predicted))),
                "mae": _clean(mean_absolute_error(y, predicted)),
                "r2": _clean(r2_score(y, predicted))}
    scores: dict[str, float | None] = {"accuracy": _clean(accuracy_score(y, predicted)),
                                       "f1_macro": _clean(f1_score(y, predicted, average="macro"))}
    try:
        proba = pipeline.predict_proba(X)
        classes = pipeline.classes_
        scores["roc_auc"] = _clean(roc_auc_score(y, proba[:, 1]) if len(classes) == 2
                                   else roc_auc_score(y, proba, multi_class="ovr", labels=classes))
    except (ValueError, AttributeError):
        scores["roc_auc"] = None
    return scores


def train_baselines(
    upload: pd.DataFrame,
    steps: list[dict],
    *,
    target: str,
    seed: int,
    max_rows: int,
) -> dict:
    """Train and compare the baseline set for `target`; returns the model_runs document."""
    frame, replayed = replay_structural(upload, steps)
    if target not in frame.columns:
        raise TargetError("invalid_target", f"'{target}' is not in the data after the approved plan.")
    problem = problem_type(frame[target], target)

    total = len(frame)
    frame = frame[frame[target].notna()]
    dropped = total - len(frame)
    if problem == "classification":
        y_all = frame[target].astype(str)
        counts = y_all.value_counts()
        if counts.min() < 2:
            raise TargetError("invalid_target", f"Every value of '{target}' needs at least 2 rows.")
    else:
        y_all = parse_numeric(frame[target])[0]
        keep = y_all.notna()
        frame, y_all = frame[keep], y_all[keep]

    sampled = len(frame) > max_rows
    if sampled:
        frame, _ = train_test_split(
            frame, train_size=max_rows, random_state=seed,
            stratify=y_all if problem == "classification" else None,
        )
        frame = frame.sort_index()
        y_all = y_all.loc[frame.index]

    X, numeric, categorical, excluded = _features(frame, target)
    if not numeric and not categorical:
        raise TargetError("invalid_target", "No usable feature columns remain to predict from.")
    stratify = y_all if problem == "classification" else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_all, test_size=TEST_SIZE, random_state=seed, stratify=stratify)
    splitter = (StratifiedKFold(N_SPLITS, shuffle=True, random_state=seed) if problem == "classification"
                else KFold(N_SPLITS, shuffle=True, random_state=seed))
    n_classes = int(y_all.nunique()) if problem == "classification" else 0
    scoring = _scoring(problem, n_classes)

    models: list[dict[str, Any]] = []
    fingerprint_parts: dict[str, str] = {}
    for name in MODELS[problem]:
        pipeline = build_pipeline(name, problem, numeric=numeric, categorical=categorical,
                                  steps=steps, seed=seed)
        started = time.perf_counter()
        cv = cross_validate(pipeline, X_train, y_train, cv=splitter, scoring=scoring,
                            error_score=np.nan)
        pipeline.fit(X_train, y_train)
        cv_summary = {}
        for metric in scoring:
            raw = np.asarray(cv[f"test_{metric}"], dtype="float64")
            cv_summary[metric] = _summary(-raw if metric in ("rmse", "mae") else raw)
        models.append({
            "name": name,
            "cv": cv_summary,
            "holdout": _holdout(pipeline, problem, X_test, y_test),
            "fit_seconds": round(time.perf_counter() - started, 3),
        })
        fingerprint_parts[name] = repr(sorted(pipeline.named_steps["model"].get_params().items()))

    primary = PRIMARY[problem]
    higher_is_better = primary != "rmse"
    candidates = [m for m in models if m["name"] != "dummy" and m["cv"][primary]["mean"] is not None]
    pick = max if higher_is_better else min
    best = pick(candidates, key=lambda m: m["cv"][primary]["mean"])
    dummy_score = next(m for m in models if m["name"] == "dummy")["cv"][primary]["mean"]
    best_score = best["cv"][primary]["mean"]
    margin = None if dummy_score is None else _clean(
        (best_score - dummy_score) if higher_is_better else (dummy_score - best_score))

    config = {"seed": seed, "n_splits": N_SPLITS, "test_size": TEST_SIZE, "sklearn": sklearn.__version__,
              "models": fingerprint_parts}
    return {
        "target": target,
        "problem_type": problem,
        "classes": sorted(y_all.unique().tolist()) if problem == "classification" else None,
        "primary_metric": primary,
        "best_model": best["name"],
        "beats_dummy": margin is not None and margin > 0,
        "margin_over_dummy": margin,
        "models": models,
        "cv": {"folds": N_SPLITS, "kind": type(splitter).__name__, "shuffle": True, "seed": seed},
        "split": {"test_size": TEST_SIZE, "stratified": stratify is not None, "seed": seed},
        "rows": {"total": total, "dropped_missing_target": dropped, "used": len(frame),
                 "sampled": sampled, "train": len(X_train), "test": len(X_test)},
        "features": {"numeric": numeric, "categorical": categorical, "excluded": excluded},
        "replayed_ops": replayed,
        "in_pipeline": [{"column": column, "op": op, "params": params}
                        for column, ops in _statistical_steps(steps).items() for op, params in ops.items()],
        "params_fingerprint": hashlib.sha256(
            json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:16],
        "versions": {"sklearn": sklearn.__version__, "pandas": pd.__version__},
        "note": NOTE,
    }


# --- background job (FR-ML-08) ----------------------------------------------------

def load_inputs(storage_root: Path, session_id: str, row: dict) -> tuple[pd.DataFrame, list[dict]]:
    """The original upload and the approved plan's steps for a session."""
    from ..storage.artifacts import plan_version_path, upload_path

    upload = pd.read_csv(upload_path(storage_root, session_id), sep=row["delimiter"] or ",",
                         encoding=row["encoding"] or "utf-8", engine="python")
    approved = plan_version_path(storage_root, session_id, row["plan_version"], "approved")
    steps = json.loads(approved.read_text(encoding="utf-8"))["steps"] if approved.exists() else []
    return upload, steps


def run_training(db_path: Path, storage_root: Path, session_id: str, target: str,
                 seed: int, max_rows: int) -> None:
    """Background task: train, persist model_runs.json, move the session to `modeled`."""
    from ..db import session_store
    from ..storage.artifacts import model_runs_path

    started = time.perf_counter()
    row = session_store.get_session(db_path, session_id)
    if row is None:
        return
    try:
        upload, steps = load_inputs(storage_root, session_id, row)
        runs = train_baselines(upload, steps, target=target, seed=seed, max_rows=max_rows)
        model_runs_path(storage_root, session_id).write_text(
            json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # never leave the session in `modeling`
        message = exc.message if isinstance(exc, TargetError) else f"training failed: {exc}"
        session_store.update_session(db_path, session_id, state="executed", error=message,
                                     failed_stage="model")
        logger.error("model.failed", extra={"session_id": session_id, "stage": "model", "error": message})
        return
    session_store.update_session(db_path, session_id, state="modeled", error=None, failed_stage=None)
    logger.info("model.completed", extra={
        "session_id": session_id, "stage": "model",
        "duration_ms": int((time.perf_counter() - started) * 1000),
    })
