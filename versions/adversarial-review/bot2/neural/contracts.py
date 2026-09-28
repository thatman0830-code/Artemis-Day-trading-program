from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping
import hashlib, json

MODEL_SCHEMA = "bot2-neural-model-artifact-v1"
PREDICTION_SCHEMA = "bot2-regime-prediction-v1"

@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    architecture: str
    feature_version: str
    regime_target_version: str
    dataset_version: str
    sequence_length: int = 8
    hidden_width: int = 8
    learning_rate: float = .01
    epochs: int = 50
    seed: int = 0
    feature_families: tuple[str, ...] = ("ALL",)
    lifecycle_state: str = "EXPERIMENTAL"

    def to_dict(self): return asdict(self) | {"feature_families": list(self.feature_families)}

@dataclass(frozen=True, slots=True)
class ModelArtifact:
    spec: ModelSpec
    weights: Mapping[str, list]
    preprocessing: Mapping[str, Any]
    weights_sha256: str
    preprocessing_sha256: str
    framework: str = "numpy"
    dependency_versions: Mapping[str, str] = field(default_factory=dict)
    git_commit: str = "UNKNOWN"
    calibration_sha256: str | None = None
    trading_authority: bool = False

    def to_dict(self): return {"schema_version": MODEL_SCHEMA, "spec": self.spec.to_dict(), "weights": dict(self.weights),
        "preprocessing": dict(self.preprocessing), "weights_sha256": self.weights_sha256,
        "preprocessing_sha256": self.preprocessing_sha256, "framework": self.framework,
        "dependency_versions": dict(self.dependency_versions), "git_commit": self.git_commit,
        "calibration_sha256": self.calibration_sha256, "trading_authority": False}

@dataclass(frozen=True, slots=True)
class RegimePrediction:
    timestamp: str
    instrument: str
    model_id: str
    direction_distribution: Mapping[str, float]
    volatility_distribution: Mapping[str, float]
    structure_distribution: Mapping[str, float]
    composite_regime: str
    raw_probabilities: Mapping[str, Mapping[str, float]]
    calibrated_probabilities: Mapping[str, Mapping[str, float]] | None
    uncertainty: Mapping[str, float]
    abstain: bool
    reason_codes: tuple[str, ...]
    inference_latency_ms: float
    trading_authority: bool = False

    def to_dict(self): return asdict(self) | {"reason_codes": list(self.reason_codes)}

def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
