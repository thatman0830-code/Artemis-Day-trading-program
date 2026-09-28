from __future__ import annotations

import math
from collections import Counter
from typing import Sequence


def classification_metrics(y: Sequence[int], probabilities: Sequence[float], *, threshold=.5) -> dict:
    pred = [1 if p >= threshold else 0 for p in probabilities]; n = len(y)
    tp = sum(a == b == 1 for a, b in zip(y, pred)); tn = sum(a == b == 0 for a, b in zip(y, pred))
    fp = sum(a == 0 and b == 1 for a, b in zip(y, pred)); fn = sum(a == 1 and b == 0 for a, b in zip(y, pred))
    logloss = -sum(yi * math.log(max(pi, 1e-15)) + (1 - yi) * math.log(max(1 - pi, 1e-15)) for yi, pi in zip(y, probabilities)) / n
    brier = sum((pi - yi) ** 2 for yi, pi in zip(y, probabilities)) / n
    pairs = [(p, yi) for p, yi in zip(probabilities, y)]; pos = sum(y); neg = n - pos
    auc = None if not pos or not neg else sum(1 if p1 > p0 else .5 if p1 == p0 else 0 for p1, y1 in pairs if y1 for p0, y0 in pairs if not y0) / (pos * neg)
    return {"log_loss": logloss, "brier_score": brier, "roc_auc": auc, "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0, "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            "accuracy": (tp + tn) / n}


def calibration_bins(y: Sequence[int], probabilities: Sequence[float], bins: int = 5) -> tuple[dict, ...]:
    result = []
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        members = [(yi, p) for yi, p in zip(y, probabilities) if low <= p < high or (index == bins - 1 and p <= high)]
        if members:
            result.append({"bin": index, "count": len(members), "mean_predicted": sum(p for _, p in members) / len(members),
                           "observed_frequency": sum(yi for yi, _ in members) / len(members)})
    return tuple(result)


def regression_metrics(y: Sequence[float], predictions: Sequence[float]) -> dict:
    n = len(y); errors = [p - a for a, p in zip(y, predictions)]; my, mp = sum(y) / n, sum(predictions) / n
    den = math.sqrt(sum((a - my) ** 2 for a in y) * sum((p - mp) ** 2 for p in predictions))
    return {"mae": sum(abs(e) for e in errors) / n, "rmse": math.sqrt(sum(e * e for e in errors) / n),
            "correlation": sum((a - my) * (p - mp) for a, p in zip(y, predictions)) / den if den else None,
            "directional_relationship": sum((a * p) > 0 for a, p in zip(y, predictions)) / n}
