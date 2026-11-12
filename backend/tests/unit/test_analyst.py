"""Baseline modeling rules, leakage safety and determinism (Spec 07) - pure service."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from app.services.analyst import (
    TargetError,
    build_pipeline,
    replay_structural,
    suggest_targets,
    train_baselines,
)
from app.services.profiler import profile_dataframe

SAMPLES = Path(__file__).resolve().parents[3] / "samples"
TITANIC = pd.read_csv(SAMPLES / "titanic.csv")
TITANIC_PROFILE = profile_dataframe("sid", TITANIC)

APPROVED_PLAN = [
    {"op": "drop_column", "column": None, "params": {"columns": ["Cabin"]}, "status": "approved"},
    {"op": "impute", "column": "Age", "params": {"strategy": "mean"}, "status": "approved"},
    {"op": "clip_outliers", "column": "Fare", "params": {"factor": 3}, "status": "edited"},
    {"op": "impute", "column": "Embarked", "params": {"strategy": "mode"}, "status": "disabled"},
]


def _train(df, target, steps=(), max_rows=50_000):
    return train_baselines(df, list(steps), target=target, seed=42, max_rows=max_rows)


@pytest.fixture(scope="module")
def titanic_runs():
    return _train(TITANIC, "Survived", APPROVED_PLAN)


def _regression_frame(rows: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    size = rng.normal(120, 30, rows)
    rooms = rng.integers(1, 6, rows)
    price = 1500 * size + 9000 * rooms + rng.normal(0, 8000, rows)
    size[::17] = np.nan  # features with gaps (AC-6)
    return pd.DataFrame({"Size": size, "Rooms": rooms, "City": rng.choice(["a", "b", "c"], rows),
                         "HousePrice": price})


def test_ml_ac1_titanic_is_classification_with_three_baselines(titanic_runs):
    assert titanic_runs["problem_type"] == "classification"
    assert [m["name"] for m in titanic_runs["models"]] == ["dummy", "logistic_regression", "random_forest"]
    assert titanic_runs["cv"] == {"folds": 5, "kind": "StratifiedKFold", "shuffle": True, "seed": 42}
    for model in titanic_runs["models"]:
        assert len(model["cv"]["f1_macro"]["folds"]) == 5
        assert set(model["cv"]) >= {"accuracy", "f1_macro", "roc_auc"}
        assert set(model["holdout"]) >= {"accuracy", "f1_macro", "roc_auc"}


def test_ml_ac2_continuous_target_is_regression():
    runs = _train(_regression_frame(), "HousePrice")
    assert runs["problem_type"] == "regression"
    assert [m["name"] for m in runs["models"]] == ["dummy", "linear_regression", "random_forest"]
    assert set(runs["models"][1]["cv"]) == {"rmse", "mae", "r2"}
    assert runs["cv"]["kind"] == "KFold"


def test_ml_ac3_identifier_target_rejected():
    with pytest.raises(TargetError) as exc:
        _train(TITANIC, "PassengerId")
    assert exc.value.code == "invalid_target"
    assert "identifier" in exc.value.message


def test_ml_ac4_preprocessing_lives_inside_the_pipeline():
    frame, _ = replay_structural(TITANIC, APPROVED_PLAN)
    pipeline = build_pipeline(
        "random_forest", "classification",
        numeric=["Age", "Fare", "Pclass"], categorical=["Sex"], steps=APPROVED_PLAN, seed=42,
    )
    assert isinstance(pipeline, Pipeline)
    assert list(pipeline.named_steps) == ["preprocess", "model"]
    assert isinstance(pipeline.named_steps["preprocess"], ColumnTransformer)
    assert frame["Age"].isna().sum() == 177  # nothing was fitted on the full data


def test_ml_ac5_scores_are_reproducible(titanic_runs):
    again = _train(TITANIC, "Survived", APPROVED_PLAN)
    strip = lambda runs: [{k: v for k, v in m.items() if k != "fit_seconds"} for m in runs["models"]]  # noqa: E731
    assert strip(again) == strip(titanic_runs)
    assert again["params_fingerprint"] == titanic_runs["params_fingerprint"]


def test_ml_ac6_feature_nulls_are_handled_in_pipeline():
    runs = _train(_regression_frame(), "HousePrice")
    assert all(np.isfinite(m["cv"]["rmse"]["mean"]) for m in runs["models"])


def test_ml_ac7_statistical_steps_are_not_replayed():
    frame, replayed = replay_structural(TITANIC, APPROVED_PLAN)
    assert "Cabin" not in frame.columns  # structural op replayed
    assert frame["Age"].isna().sum() == 177  # impute NOT replayed
    assert frame["Fare"].max() == TITANIC["Fare"].max()  # clip NOT replayed
    assert replayed == ["drop_column"]

    pipeline = build_pipeline("random_forest", "classification", numeric=["Age", "Fare"],
                              categorical=["Sex"], steps=APPROVED_PLAN, seed=42)
    numeric = dict((name, t) for name, t, _ in pipeline.named_steps["preprocess"].transformers)
    age_steps = numeric["num_Age"].named_steps
    assert isinstance(age_steps["impute"], SimpleImputer)
    assert age_steps["impute"].strategy == "mean"  # the plan's choice, fitted per fold
    assert numeric["num_Fare"].named_steps["clip"].factor == 3


def test_ml_ac8_target_suggestions_for_titanic():
    suggestions = suggest_targets(TITANIC_PROFILE)
    assert suggestions[0]["column"] == "Survived"
    assert suggestions[0]["problem_type"] == "classification"
    assert suggestions[0]["reason"]
    assert not {s["column"] for s in suggestions} & {"PassengerId", "Name", "Ticket"}


def test_ml_ac10_best_model_is_never_the_dummy(titanic_runs):
    assert titanic_runs["best_model"] in {"logistic_regression", "random_forest"}
    assert titanic_runs["primary_metric"] == "f1_macro"
    assert titanic_runs["beats_dummy"] is True


def test_ml_fr02_small_integer_target_is_classification():
    runs = _train(TITANIC, "Pclass")
    assert runs["problem_type"] == "classification"


def test_ml_fr02_single_class_target_rejected():
    df = TITANIC.assign(Constant=1)
    with pytest.raises(TargetError):
        _train(df, "Constant")


def test_ml_fr02_rows_without_target_are_dropped_and_counted():
    df = _regression_frame()
    df.loc[:9, "HousePrice"] = np.nan
    runs = _train(df, "HousePrice")
    assert runs["rows"]["dropped_missing_target"] == 10
    assert runs["rows"]["used"] == 290


def test_ml_fr13_large_data_is_sampled_with_the_seed():
    runs = _train(TITANIC, "Survived", max_rows=400)
    assert runs["rows"]["used"] == 400
    assert runs["rows"]["sampled"] is True
    excluded = set(runs["features"]["excluded"])
    assert {"PassengerId", "Name", "Ticket"} <= excluded
