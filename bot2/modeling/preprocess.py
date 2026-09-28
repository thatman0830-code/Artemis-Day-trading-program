from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class TrainOnlyStandardizer:
    means: tuple[float, ...] | None = None
    scales: tuple[float, ...] | None = None
    fitted_count: int = 0

    def fit(self, x_train: Sequence[Sequence[float]]) -> "TrainOnlyStandardizer":
        if not x_train:
            raise ValueError("cannot fit on empty training data")
        n = len(x_train[0]); means = tuple(sum(row[j] for row in x_train) / len(x_train) for j in range(n))
        scales = tuple(max(math.sqrt(sum((row[j] - means[j]) ** 2 for row in x_train) / len(x_train)), 1e-12) for j in range(n))
        return TrainOnlyStandardizer(means, scales, len(x_train))

    def transform(self, x: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
        if self.means is None or self.scales is None:
            raise ValueError("fit must precede transform")
        return tuple(tuple((value - self.means[j]) / self.scales[j] for j, value in enumerate(row)) for row in x)
