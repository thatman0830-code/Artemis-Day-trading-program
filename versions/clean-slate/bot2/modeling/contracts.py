from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping
import json

MODEL_SCHEMA = "bot2-experiment-result-v1"
SPLIT_SCHEMA = "bot2-temporal-split-v1"


@dataclass(frozen=True, slots=True)
class CostModel:
    commission_per_unit: float | None = None
    exchange_clearing_fee_per_unit: float | None = None
    spread_per_unit: float | None = None
    slippage_per_unit: float | None = None
    currency: str = "USD"
    assumptions_status: str = "CONFIGURABLE_UNKNOWN_VALUES"

    @property
    def total_per_unit(self) -> float:
        return sum(x or 0.0 for x in (self.commission_per_unit, self.exchange_clearing_fee_per_unit,
                                       self.spread_per_unit, self.slippage_per_unit))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"total_per_unit": self.total_per_unit}


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    experiment_id: str
    dataset_id: str
    dataset_hash: str
    feature_version: str
    label_version: str
    instruments: tuple[str, ...]
    training_period: tuple[str, str]
    validation_period: tuple[str, str]
    test_period: tuple[str, str]
    feature_list: tuple[str, ...]
    target: str
    model_type: str
    hyperparameters: Mapping[str, Any] = field(default_factory=dict)
    random_seed: int = 0
    cost_model: CostModel = field(default_factory=CostModel)
    git_commit: str = "UNKNOWN"
    environment: Mapping[str, str] = field(default_factory=dict)
    feature_families: tuple[str, ...] = ("ALL",)
    holdout_designation: str = "UNTOUCHED_FINAL_HOLDOUT_NOT_USED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"instruments": list(self.instruments), "feature_list": list(self.feature_list),
                               "feature_families": list(self.feature_families), "cost_model": self.cost_model.to_dict()}


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    schema_version: str
    spec: ExperimentSpec
    split_counts: Mapping[str, int]
    metrics: Mapping[str, Any]
    calibration: tuple[Mapping[str, Any], ...]
    status: str = "FINALIZED"
    trading_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "experiment": self.spec.to_dict(),
                "split_counts": dict(self.split_counts), "metrics": dict(self.metrics),
                "calibration": [dict(x) for x in self.calibration], "status": self.status,
                "trading_authority": self.trading_authority}

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
