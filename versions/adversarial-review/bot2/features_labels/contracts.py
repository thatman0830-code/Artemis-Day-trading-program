"""Versioned, serialisable contracts for the Phase 2 feature/label boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

FEATURE_SCHEMA_V1 = "bot2-feature-row-v1"
FEATURE_SCHEMA_V2 = "bot2-feature-row-v2"
FEATURE_SCHEMA = "bot2-feature-row-v3"
LABEL_SCHEMA = "bot2-label-row-v1"
FEATURE_REGISTRY_VERSION = "bot2-feature-registry-v3"

VALID = "VALID"
UNAVAILABLE = "UNAVAILABLE"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
INVALID_SOURCE_DATA = "INVALID_SOURCE_DATA"
SYNCHRONIZATION_UNAVAILABLE = "SYNCHRONIZATION_UNAVAILABLE"
INSUFFICIENT_FUTURE_DATA = "INSUFFICIENT_FUTURE_DATA"
SESSION_BOUNDARY = "SESSION_BOUNDARY"
AMBIGUOUS_OUTCOME = "AMBIGUOUS_OUTCOME"


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def config_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    version: str = FEATURE_REGISTRY_VERSION
    expected_cadence_seconds: int = 60
    return_horizons: tuple[int, ...] = (1, 3, 5)
    rolling_windows: tuple[int, ...] = (3, 5)
    relative_volume_window: int = 3
    session_phase_minutes: tuple[int, ...] = (30, 120)
    normalization: str = "NONE_CAUSAL"

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "expected_cadence_seconds": self.expected_cadence_seconds,
                "temporal_semantics": "ELAPSED_TIME_STRICT_CADENCE", "return_horizons_minutes": list(self.return_horizons),
                "rolling_windows_minutes": list(self.rolling_windows),
                "relative_volume_window_minutes": self.relative_volume_window,
                "session_phase_minutes": list(self.session_phase_minutes),
                "normalization": self.normalization}


@dataclass(frozen=True, slots=True)
class LabelConfig:
    version: str = "bot2-label-config-v1"
    horizons: tuple[int, ...] = (3, 5)
    favorable_barrier: float = 0.001
    adverse_barrier: float = 0.001
    direction_threshold: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "horizons": list(self.horizons),
                "favorable_barrier": self.favorable_barrier,
                "adverse_barrier": self.adverse_barrier,
                "direction_threshold": self.direction_threshold}


@dataclass(frozen=True, slots=True)
class FeatureRow:
    instrument: str
    observation_time: str
    cutoff_time: str
    feature_version: str
    source_dataset_id: str
    source_dataset_sha256: str
    session_id: str
    validity: str
    reason_codes: tuple[str, ...]
    values: Mapping[str, float | str | None]
    configuration_sha256: str
    code_commit: str
    generated_at: str
    trading_authority: bool = False
    schema_version: str = FEATURE_SCHEMA
    contract_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"reason_codes": list(self.reason_codes), "values": dict(self.values)}


@dataclass(frozen=True, slots=True)
class LabelRow:
    instrument: str
    observation_time: str
    cutoff_time: str
    label_version: str
    source_dataset_id: str
    source_dataset_sha256: str
    session_id: str
    horizon_events: int
    validity: str
    reason_codes: tuple[str, ...]
    forward_return: float | None
    direction: str | None
    mfe: float | None
    mae: float | None
    future_realized_volatility: float | None
    barrier_outcome: str | None
    configuration_sha256: str
    code_commit: str
    generated_at: str
    uses_future_observations: bool = True
    trading_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"reason_codes": list(self.reason_codes)}
