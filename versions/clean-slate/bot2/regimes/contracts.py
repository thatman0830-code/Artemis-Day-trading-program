from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

REGIME_SCHEMA = "bot2-regime-assignment-v1"
REGIME_CONFIG_VERSION = "bot2-regime-config-v1"
CANDIDATE_STATES = ("TREND_UP", "TREND_DOWN", "RANGE", "VOLATILITY_EXPANSION", "VOLATILITY_CONTRACTION", "TRANSITION", "UNCERTAIN")


@dataclass(frozen=True, slots=True)
class RegimeConfig:
    version: str = REGIME_CONFIG_VERSION
    return_threshold: float = 0.001
    volatility_expansion_ratio: float = 1.20
    volatility_contraction_ratio: float = 0.80
    structure_return_threshold: float = 0.0005
    minimum_confidence: float = 0.55
    transition_lookback: int = 2

    def to_dict(self): return asdict(self)


@dataclass(frozen=True, slots=True)
class RegimeAssignment:
    instrument: str
    observation_time: str
    cutoff_time: str
    session_id: str
    direction_state: str
    volatility_state: str
    structure_state: str
    primary_state: str
    probabilities: Mapping[str, float]
    confidence: float
    validity: str
    reason_codes: tuple[str, ...]
    regime_version: str
    source_dataset_id: str
    source_dataset_sha256: str
    configuration_sha256: str
    code_commit: str
    trading_authority: bool = False

    def to_dict(self): return asdict(self) | {"probabilities": dict(self.probabilities), "reason_codes": list(self.reason_codes)}


@dataclass(frozen=True, slots=True)
class RegimeSequence:
    assignments: tuple[RegimeAssignment, ...]
    instrument: str
    transition_count: int
    churn_rate: float
    source_dataset_id: str
    regime_version: str
    trading_authority: bool = False
