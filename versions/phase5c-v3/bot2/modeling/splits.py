"""Chronological split and purged walk-forward utilities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Sequence, Any


@dataclass(frozen=True, slots=True)
class TemporalSplit:
    train: tuple[Any, ...]
    validation: tuple[Any, ...]
    test: tuple[Any, ...]
    purged_count: int = 0
    embargoed_count: int = 0


def _time(row: Any) -> datetime:
    value = row.observation_time if hasattr(row, "observation_time") else row["observation_time"]
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value


def _future_end(row: Any) -> datetime:
    value = getattr(row, "label_end_time", None)
    if value is None and isinstance(row, dict):
        value = row.get("label_end_time")
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else (value or _time(row))


def chronological_split(rows: Sequence[Any], *, train_fraction: float = .6, validation_fraction: float = .2,
                        purge: timedelta = timedelta(0), embargo: timedelta = timedelta(0)) -> TemporalSplit:
    ordered = tuple(sorted(rows, key=_time))
    if not ordered or not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 or train_fraction + validation_fraction >= 1:
        raise ValueError("invalid split fractions or empty rows")
    train_end = int(len(ordered) * train_fraction)
    validation_end = train_end + int(len(ordered) * validation_fraction)
    train_cut = _time(ordered[train_end])
    validation_cut = _time(ordered[validation_end])
    train = list(ordered[:train_end]); validation = list(ordered[train_end:validation_end]); test = list(ordered[validation_end:])
    purged = embargoed = 0
    if purge or embargo:
        validation_start = _time(validation[0]); test_start = _time(test[0])
        kept_train = []
        for row in train:
            if _future_end(row) + purge >= validation_start:
                purged += 1
            else:
                kept_train.append(row)
        train = kept_train
        kept_validation = []
        for row in validation:
            if _future_end(row) + purge >= test_start:
                purged += 1
            elif _time(row) < validation_start + embargo:
                embargoed += 1
            else:
                kept_validation.append(row)
        validation = kept_validation
        if embargo:
            kept_test = []
            for row in test:
                if _time(row) < test_start + embargo:
                    embargoed += 1
                else:
                    kept_test.append(row)
            test = kept_test
    if not train or not validation or not test:
        raise ValueError("temporal split empty after purge/embargo")
    return TemporalSplit(tuple(train), tuple(validation), tuple(test), purged, embargoed)


def walk_forward_splits(rows: Sequence[Any], *, train_size: int, validation_size: int, test_size: int,
                        step: int | None = None, purge: timedelta = timedelta(0), embargo: timedelta = timedelta(0)) -> tuple[TemporalSplit, ...]:
    ordered = tuple(sorted(rows, key=_time)); step = step or test_size
    if min(train_size, validation_size, test_size, step) <= 0:
        raise ValueError("window sizes must be positive")
    result = []
    start = 0
    while start + train_size + validation_size + test_size <= len(ordered):
        block = ordered[start:start + train_size + validation_size + test_size]
        result.append(chronological_split(block, train_fraction=train_size / len(block),
                                          validation_fraction=validation_size / len(block), purge=purge, embargo=embargo))
        start += step
    return tuple(result)
