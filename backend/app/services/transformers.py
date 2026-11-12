"""scikit-learn transformers used inside model pipelines (Spec 07 FR-ML-11)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class IQRClipper(TransformerMixin, BaseEstimator):
    """Clip each column to its IQR fences, learned from the data it is fitted on.

    The pipeline equivalent of the `clip_outliers` plan step: inside cross-validation it
    is fitted on the training fold only, so the fences never see validation rows.
    """

    def __init__(self, factor: float = 1.5) -> None:
        self.factor = factor

    def fit(self, X: Any, y: Any = None) -> IQRClipper:
        values = np.asarray(X, dtype="float64")
        q1 = np.nanpercentile(values, 25, axis=0)
        q3 = np.nanpercentile(values, 75, axis=0)
        iqr = q3 - q1
        self.low_ = q1 - self.factor * iqr
        self.high_ = q3 + self.factor * iqr
        self.n_features_in_ = values.shape[1]
        return self

    def transform(self, X: Any) -> np.ndarray:
        values = np.asarray(X, dtype="float64")
        return np.clip(values, self.low_, self.high_)  # NaN stays NaN for the imputer

    def get_feature_names_out(self, input_features: Any = None) -> Any:
        return np.asarray(input_features if input_features is not None else [], dtype=object)
