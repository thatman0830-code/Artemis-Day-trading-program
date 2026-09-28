"""Deterministic sequence construction with elapsed-time and identity gates."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Sequence, Mapping
import numpy as np

from bot2.data_foundation.cadence import EXPECTED_BAR_INTERVAL
DEFAULT_CATEGORICAL_ENCODINGS = {"session_phase": {"OPENING": 0.0, "EARLY": 1.0, "LATE": 2.0}}


@dataclass(frozen=True, slots=True)
class SequenceBatch:
    x: np.ndarray
    y_direction: np.ndarray
    y_volatility: np.ndarray
    y_structure: np.ndarray
    timestamps: tuple[str, ...]
    instruments: tuple[str, ...]
    boundary_ids: tuple[str, ...]
    rejection_counts: Mapping[str, int] = field(default_factory=dict)


def build_sequences(rows: Sequence[Any], *, sequence_length: int, feature_names: Sequence[str],
                    split_name: str | None = None,
                    expected_cadence: timedelta = EXPECTED_BAR_INTERVAL,
                    categorical_encodings: Mapping[str, Mapping[str, float]] | None = None) -> SequenceBatch:
    if sequence_length <= 0 or expected_cadence.total_seconds() <= 0:
        raise ValueError("sequence length and expected cadence must be positive")

    def field(row, name, default=None):
        return row.get(name, default) if isinstance(row, Mapping) else getattr(row, name, default)

    ordered = sorted(rows, key=lambda row: (field(row, "observation_time"), field(row, "instrument", ""), field(row, "contract_id", "")))
    encodings = categorical_encodings or DEFAULT_CATEGORICAL_ENCODINGS
    xs=[]; yd=[]; yv=[]; ys=[]; ts=[]; instruments=[]; boundaries=[]
    rejected: Counter[str] = Counter()
    if len(ordered) < sequence_length:
        rejected["INSUFFICIENT_CONTIGUOUS_HISTORY"] += 1
    for end in range(sequence_length - 1, len(ordered)):
        window = ordered[end-sequence_length+1:end+1]
        sessions = [field(row, "session_id", "") for row in window]
        symbols = [field(row, "instrument", "UNKNOWN") for row in window]
        contracts = [field(row, "contract_id", symbol) or symbol for row, symbol in zip(window, symbols)]
        if len(set(sessions)) != 1:
            rejected["SESSION_BOUNDARY"] += 1
            continue
        if len(set(symbols)) != 1 or len(set(contracts)) != 1:
            rejected["CONTRACT_BOUNDARY"] += 1
            continue
        parsed = [datetime.fromisoformat(field(row, "observation_time").replace("Z", "+00:00"))
                  if isinstance(field(row, "observation_time"), str) else field(row, "observation_time")
                  for row in window]
        deltas = [(right-left) for left, right in zip(parsed, parsed[1:])]
        if any(delta > expected_cadence for delta in deltas):
            rejected["SEQUENCE_GAP"] += 1
            continue
        if any(delta != expected_cadence for delta in deltas):
            rejected["CADENCE_VIOLATION"] += 1
            continue
        values = [field(row, "values", {}) for row in window]
        if any(any(value_map.get(name) is None for name in feature_names) for value_map in values):
            rejected["REQUIRED_FEATURE_UNAVAILABLE"] += 1
            continue
        try:
            encoded = [[float(encodings.get(name, {}).get(value_map.get(name), value_map.get(name)))
                        for name in feature_names] for value_map in values]
        except (TypeError, ValueError):
            rejected["INVALID_CATEGORICAL_FEATURE"] += 1
            continue
        row = window[-1]
        targets = field(row, "targets", {})
        if not all(key in targets and targets[key] is not None for key in ("direction", "volatility", "structure")):
            rejected["INVALID_TARGET"] += 1
            continue
        xs.append(encoded)
        yd.append(int(targets["direction"])); yv.append(int(targets["volatility"])); ys.append(int(targets["structure"]))
        ts.append(field(row, "observation_time")); instruments.append(symbols[-1])
        boundaries.append(f"{sessions[-1]}:{contracts[-1]}")
    feature_count = len(feature_names)
    return SequenceBatch(np.asarray(xs, dtype=float).reshape((-1, sequence_length, feature_count)),
        np.asarray(yd, dtype=int), np.asarray(yv, dtype=int), np.asarray(ys, dtype=int),
        tuple(ts), tuple(instruments), tuple(boundaries), dict(sorted(rejected.items())))
