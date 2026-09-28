"""Small deterministic baselines; intentionally no neural or large ML dependency."""
from __future__ import annotations

import math
from typing import Sequence
from .metrics import classification_metrics, calibration_bins, regression_metrics


def _sigmoid(x): return 1 / (1 + math.exp(-max(min(x, 40), -40)))


def _logistic_fit(x, y, steps=300, learning_rate=.05):
    if not x: raise ValueError("empty training data")
    w = [0.0] * (len(x[0]) + 1)
    for _ in range(steps):
        grad = [0.0] * len(w)
        for row, yi in zip(x, y):
            p = _sigmoid(w[0] + sum(a * b for a, b in zip(w[1:], row))); error = p - yi
            grad[0] += error
            for j, value in enumerate(row, 1): grad[j] += error * value
        w = [a - learning_rate * b / len(x) for a, b in zip(w, grad)]
    return w


def fit_baseline(model_type: str, x_train: Sequence[Sequence[float]], y_train: Sequence[float],
                 x_eval: Sequence[Sequence[float]], *, hyperparameters=None) -> tuple[list[float], dict, tuple[dict, ...]]:
    hyperparameters = hyperparameters or {}
    if model_type == "majority_class":
        p = sum(y_train) / len(y_train); probabilities = [p] * len(x_eval)
        return probabilities, classification_metrics([int(v) for v in y_train[:len(x_eval)]], probabilities), calibration_bins([int(v) for v in y_train[:len(x_eval)]], probabilities)
    if model_type == "prior_probability":
        p = sum(y_train) / len(y_train); return [p] * len(x_eval), {}, ()
    if model_type == "logistic_regression":
        w = _logistic_fit(x_train, [int(v) for v in y_train], hyperparameters.get("steps", 300), hyperparameters.get("learning_rate", .05))
        probabilities = [_sigmoid(w[0] + sum(a * b for a, b in zip(w[1:], row))) for row in x_eval]
        return probabilities, {}, ()
    if model_type in ("zero_return", "prior_mean", "ridge_regression"):
        if model_type == "zero_return": predictions = [0.0] * len(x_eval)
        elif model_type == "prior_mean": predictions = [sum(y_train) / len(y_train)] * len(x_eval)
        else:
            alpha = float(hyperparameters.get("alpha", 1.0)); n = len(x_train[0]); w = [0.0] * n
            for j in range(n):
                denom = sum(row[j] ** 2 for row in x_train) + alpha; w[j] = sum(row[j] * yi for row, yi in zip(x_train, y_train)) / denom
            predictions = [sum(a * b for a, b in zip(w, row)) for row in x_eval]
        return predictions, {}, ()
    raise ValueError(f"unsupported baseline: {model_type}")
