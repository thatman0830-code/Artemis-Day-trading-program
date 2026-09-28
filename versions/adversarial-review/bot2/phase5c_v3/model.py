"""NumPy implementation of the frozen Phase 5C v3 causal TCN (A2).

Each causal kernel tap reads x[t - tap*dilation], or zero when the index is
negative. Explicit left-side zero padding makes future access impossible.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

import numpy as np

from .manifest import VerifiedManifest, canonical_hash, is_verified_manifest

ARCHITECTURE_VERSION = "bot2-phase5c-a2-causal-tcn-v3"
FEATURE_VERSION = "bot2-feature-row-v3"
TARGET_VERSION = "bot2-future-market-state-v3"
HEADS = ("direction", "volatility", "structure")
CLASS_COUNTS = {"direction": 3, "volatility": 3, "structure": 3}
KERNEL_WIDTH = 3
DILATIONS = (1, 2, 4)
CHANNELS = (32, 32, 16)


@dataclass(frozen=True, slots=True)
class PartitionData:
    """Partition payload carrying canonical exchange-event identities."""
    x: np.ndarray
    targets: Mapping[str, np.ndarray]
    partition: str
    sequence_keys: tuple[tuple[tuple[str, str, str], ...], ...]
    feature_version: str
    target_version: str
    market: str
    horizon_minutes: int
    dataset_manifest_sha256: str
    preprocessing_sha256: str
    partition_fingerprint: str = ""
    sequence_label_intervals: tuple[tuple[str, str], ...] = ()
    derived_from_observations: bool = False
    ablation_id: str = "ALL"
    ablation_sha256: str = ""
    feature_mask: tuple[int, ...] = ()


ObservationKey = tuple[str, str, str]  # (exact contract, session ID, exchange timestamp UTC)


def _utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_OBSERVATION_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("OBSERVATION_TIMESTAMP_MUST_BE_UTC")
    return parsed.astimezone(timezone.utc)


def validate_sequence_identities(data: PartitionData, *, sequence_length: int,
                                 cadence_seconds: int = 60) -> set[ObservationKey]:
    x = _validate_sequences(data.x)
    keys = data.sequence_keys
    if keys is None or len(keys) != len(x):
        raise ValueError("SEQUENCE_IDENTITY_MISSING_OR_COUNT_MISMATCH")
    terminals: set[ObservationKey] = set()
    observations: set[ObservationKey] = set()
    for sequence in keys:
        if len(sequence) != sequence_length:
            raise ValueError("SEQUENCE_IDENTITY_LENGTH_MISMATCH")
        if any(not isinstance(key, tuple) or len(key) != 3 or not all(isinstance(v, str) and v for v in key)
               for key in sequence):
            raise ValueError("INVALID_OBSERVATION_IDENTITY")
        if len({key[0] for key in sequence}) != 1:
            raise ValueError("SEQUENCE_CONTRACT_BOUNDARY_CROSSING")
        if len({key[1] for key in sequence}) != 1:
            raise ValueError("SEQUENCE_SESSION_BOUNDARY_CROSSING")
        times = [_utc_timestamp(key[2]) for key in sequence]
        if any(right - left != timedelta(seconds=cadence_seconds) for left, right in zip(times, times[1:])):
            raise ValueError("SEQUENCE_CADENCE_GAP_OR_REGRESSION")
        terminal = sequence[-1]
        if terminal in terminals:
            raise ValueError("DUPLICATE_SEQUENCE_IDENTITY")
        terminals.add(terminal)
        observations.update(sequence)
    return observations


def validate_partition_disjointness(partitions: Mapping[str, PartitionData], *,
                                    sequence_length: int = 8,
                                    cadence_seconds: int = 60) -> dict[str, int]:
    identities = {name: validate_sequence_identities(value, sequence_length=sequence_length,
                                                       cadence_seconds=cadence_seconds)
                  for name, value in partitions.items()}
    names = tuple(identities)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            if identities[left] & identities[right]:
                raise ValueError("DUPLICATE_OBSERVATION_CROSSES_PARTITION")
    return {name: len(rows) for name, rows in identities.items()}


class TrainingOnlyStandardizer:
    """Fit on unique TRAIN feature rows, then transform any authorized split."""
    def __init__(self) -> None:
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self.manifest_sha256_: str | None = None
        self.dataset_sha256_: str | None = None
        self.feature_version_: str | None = None
        self.market_: str | None = None
        self.unique_rows_: int = 0
        self._feature_order_: tuple[str, ...] | None = None
        self.code_commit_: str | None = None
        self.training_partition_fingerprint_: str | None = None
        self.training_feature_fingerprint_: str | None = None

    def fit(self, rows: np.ndarray, *, partition: str,
            row_ids: tuple[ObservationKey, ...] | list[ObservationKey], market: str,
            verified_manifest: VerifiedManifest) -> "TrainingOnlyStandardizer":
        # Legacy caller-supplied identifiers are retained as a fail-closed API
        # diagnostic; new fits must use fit_observations below.
        if partition != "TRAIN":
            raise ValueError("PREPROCESSING_FIT_NOT_TRAIN")
        raise ValueError("CALLER_ROW_IDS_NOT_AUTHORIZED")

    def fit_observations(self, observations, *, market: str,
                         verified_manifest: VerifiedManifest,
                         code_commit: str) -> "TrainingOnlyStandardizer":
        if not is_verified_manifest(verified_manifest) or not verified_manifest.external_anchor_content_verified:
            raise ValueError("EXTERNALLY_ANCHORED_MANIFEST_REQUIRED")
        if market not in {"ES", "NQ"}:
            raise ValueError("MARKET_NOT_IN_MANIFEST")
        manifest = verified_manifest.data
        allowed_contracts = set(manifest["source_dataset"]["contracts"][market])
        train_start, train_end = manifest["chronological_partitions_inclusive"]["TRAIN"]
        features = tuple(manifest["feature_specification"]["features"])
        rows = list(observations)
        if rows != sorted(rows, key=lambda row: (_utc_timestamp(row.exchange_timestamp_utc), row.contract)):
            raise ValueError("OBSERVATIONS_NOT_IN_CANONICAL_ORDER")
        x = np.asarray([row.features for row in rows], dtype=np.float64)
        if x.ndim != 2 or not np.isfinite(x).all():
            raise ValueError("INVALID_UNIQUE_FEATURE_ROWS")
        if x.shape[0] == 0:
            raise ValueError("EMPTY_TRAIN_ROWS")
        if x.shape[1] != len(features):
            raise ValueError("FEATURE_VERSION_OR_WIDTH_MISMATCH")
        first_by_id: dict[str, np.ndarray] = {}
        for observation, values in zip(rows, x):
            if (observation.market != market or observation.contract not in allowed_contracts
                    or tuple(observation.feature_names) != features):
                raise ValueError("CONTRACT_NOT_IN_MANIFEST")
            if observation.dataset_manifest_sha256 != manifest["source_dataset_manifest_sha256"]:
                raise ValueError("DATASET_MANIFEST_BINDING_MISMATCH")
            if observation.feature_version != manifest["feature_specification"]["schema_version"]:
                raise ValueError("FEATURE_VERSION_OR_WIDTH_MISMATCH")
            day = _utc_timestamp(observation.exchange_timestamp_utc).date().isoformat()
            if not train_start <= day <= train_end:
                raise ValueError("PREPROCESSING_ROW_OUTSIDE_TRAIN_WINDOW")
            row_id = observation.observation_id
            prior = first_by_id.get(row_id)
            if prior is not None:
                reason = "DUPLICATE_OBSERVATION_IDENTITY" if np.array_equal(prior, values) else "DUPLICATE_IDENTITY_CONFLICTING_VALUES"
                raise ValueError(reason)
            first_by_id[row_id] = values
        self.unique_rows_ = len(first_by_id)
        values = x.astype(np.float64, copy=False)
        self.mean_ = values.mean(axis=0)
        scale = values.std(axis=0, ddof=0)
        self.scale_ = np.where(scale == 0.0, 1e-12, scale)
        self.manifest_sha256_ = verified_manifest.sha256
        self.dataset_sha256_ = verified_manifest.data["source_dataset_manifest_sha256"]
        self.feature_version_ = verified_manifest.data["feature_specification"]["schema_version"]
        self.market_ = market
        self._feature_order_ = features
        if len(code_commit) != 40 or any(char not in "0123456789abcdef" for char in code_commit):
            raise ValueError("INVALID_CODE_COMMIT")
        self.code_commit_ = code_commit
        from .data_integrity import feature_partition_fingerprint, partition_fingerprint
        self.training_partition_fingerprint_ = partition_fingerprint(
            rows, partition="TRAIN", horizon_minutes=manifest["target_specification"]["horizons_minutes"][0])
        self.training_feature_fingerprint_ = feature_partition_fingerprint(rows, partition="TRAIN")
        return self

    def transform(self, rows: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.scale_ is None:
            raise ValueError("PREPROCESSOR_NOT_FITTED")
        x = np.asarray(rows)
        if x.ndim not in (2, 3) or x.shape[-1] != self.mean_.size or not np.isfinite(x).all():
            raise ValueError("FEATURE_VERSION_OR_WIDTH_MISMATCH")
        return ((x.astype(np.float64) - self.mean_) / self.scale_).astype(np.float32)

    def state(self) -> dict:
        if self.mean_ is None or self.scale_ is None:
            raise ValueError("PREPROCESSOR_NOT_FITTED")
        return {"version": "train-unique-row-population-zscore-v1", "fit_partition": "TRAIN",
                "mean": self.mean_.tolist(), "scale": self.scale_.tolist(),
                "feature_count": int(self.mean_.size), "manifest_sha256": self.manifest_sha256_,
                "dataset_manifest_sha256": self.dataset_sha256_, "feature_version": self.feature_version_,
                "market": self.market_,
                "feature_order": list(self._feature_order_),
                "code_commit": self.code_commit_,
                "training_partition_fingerprint": self.training_partition_fingerprint_,
                "training_feature_fingerprint": self.training_feature_fingerprint_,
                "identity_key": ["exact_contract", "session_id", "exchange_timestamp_utc"],
                "unique_training_observation_count": self.unique_rows_}

    @property
    def sha256(self) -> str:
        return canonical_hash(self.state())


def _validate_sequences(x: np.ndarray) -> np.ndarray:
    value = np.asarray(x)
    if value.ndim != 3 or not np.isfinite(value).all():
        raise ValueError("INVALID_OR_NONFINITE_SEQUENCE")
    return value


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


def _conv_forward(x: np.ndarray, weight: np.ndarray, bias: np.ndarray,
                  dilation: int) -> tuple[np.ndarray, tuple]:
    batch, length, _ = x.shape
    out = np.broadcast_to(bias, (batch, length, bias.size)).copy()
    shifted_inputs = []
    for tap in range(KERNEL_WIDTH):
        lag = tap * dilation
        shifted = np.zeros_like(x)
        if lag == 0:
            shifted[...] = x
        elif lag < length:
            shifted[:, lag:, :] = x[:, :length-lag, :]
        shifted_inputs.append(shifted)
        out += shifted @ weight[tap]
    return out, (x, tuple(shifted_inputs), weight, dilation)


def _conv_backward(grad_out: np.ndarray, cache: tuple) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, shifted_inputs, weight, dilation = cache
    _, length, in_channels = x.shape
    out_channels = grad_out.shape[-1]
    grad_x = np.zeros_like(x)
    grad_w = np.zeros_like(weight)
    for tap, shifted in enumerate(shifted_inputs):
        grad_w[tap] = shifted.reshape(-1, in_channels).T @ grad_out.reshape(-1, out_channels)
        lag = tap * dilation
        if lag == 0:
            grad_x += grad_out @ weight[tap].T
        elif lag < length:
            grad_x[:, :length-lag, :] += grad_out[:, lag:, :] @ weight[tap].T
    return grad_x, grad_w, grad_out.sum(axis=(0, 1))


class CausalTemporalConv:
    """Three-block learned causal TCN with three independent 3-class heads."""
    def __init__(self, verified_manifest: VerifiedManifest, *, seed: int,
                 ablation_id: str = "ALL"):
        if not is_verified_manifest(verified_manifest) or not verified_manifest.external_anchor_content_verified:
            raise ValueError("EXTERNALLY_ANCHORED_MANIFEST_REQUIRED")
        manifest = verified_manifest.data
        self.verified_manifest = verified_manifest
        self.ablation_id = ablation_id
        architecture = manifest["architectures"]["A2_LEARNED_CAUSAL_TCN"]
        training = manifest["a2_training"]
        expected_blocks = [
            {"type": "causal_conv1d", "in_channels": 24, "out_channels": 32,
             "kernel_width": 3, "stride": 1, "dilation": 1, "padding": "left-only-zero", "activation": "ReLU"},
            {"type": "causal_conv1d", "in_channels": 32, "out_channels": 32,
             "kernel_width": 3, "stride": 1, "dilation": 2, "padding": "left-only-zero", "activation": "ReLU"},
            {"type": "causal_conv1d", "in_channels": 32, "out_channels": 16,
             "kernel_width": 3, "stride": 1, "dilation": 4, "padding": "left-only-zero", "activation": "ReLU"},
        ]
        exact_blocks = [{key: block.get(key) for key in expected_blocks[0]} for block in architecture["blocks"]]
        if (manifest["feature_specification"]["schema_version"] != FEATURE_VERSION
                or manifest["target_specification"]["version"] != TARGET_VERSION
                or manifest["target_specification"]["horizons_minutes"] != [5, 15, 30]
                or manifest["feature_specification"]["sequence_cadence_seconds"] != 60
                or manifest["feature_specification"]["sequence_length"] != 8
                or exact_blocks != expected_blocks
                or architecture.get("receptive_field_timesteps") != 15
                or architecture.get("temporal_readout") != "final valid timestamp T only; no pooling over padded or future positions"
                or architecture.get("shared_representation") != {"dense": "16->16", "activation": "ReLU"}
                or architecture.get("heads") != {"direction": "16->3 logits", "volatility": "16->3 logits", "structure": "16->3 logits"}
                or architecture.get("dropout") is not False or architecture.get("batch_normalization") is not False
                or architecture.get("future_looking_or_bidirectional_operations") is not False
                or set(manifest["chronological_partitions_inclusive"]) != {"TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST"}
                or manifest["random_seeds"] != [1, 2, 3]
                or training["optimizer"] != "Adam"
                or training["learning_rate"] != 0.001
                or training["adam_beta1"] != 0.9 or training["adam_beta2"] != 0.999
                or training["adam_epsilon"] != 1e-8
                or training["batch_size"] != 256
                or training["batch_order"] != "chronological contiguous batches; no minibatch shuffle"
                or training["max_epochs"] != 50
                or training["early_stopping"].get("enabled") is not True
                or training["early_stopping"].get("partition") != "VALIDATION_AND_CALIBRATION"
                or training["early_stopping"]["patience"] != 5
                or training["early_stopping"].get("checkpoint") != "lowest authorized validation multi-head categorical cross-entropy"
                or training["gradient_clipping"].get("method") != "global L2 norm"
                or training["gradient_clipping"]["maximum_norm"] != 1.0
                or training["loss"].get("type") != "sum of categorical cross-entropies"
                or training["loss"].get("head_weights") != {"direction": 1.0, "volatility": 1.0, "structure": 1.0}
                or training["class_imbalance"] != "No class weights, resampling, or synthetic examples; equal per-head categorical loss, consistent with frozen v2 policy."
                or training["initialization"].get("rng") != "numpy.random.default_rng(seed)"
                or training["initialization"].get("dtype") != "float32"
                or not training["determinism"].startswith("Fixed seed")):
            raise ValueError("MANIFEST_MODEL_CONFIGURATION_MISMATCH")
        if seed not in manifest["random_seeds"]:
            raise ValueError("SEED_NOT_AUTHORIZED_BY_MANIFEST")
        input_features = len(manifest["feature_specification"]["features"])
        sequence_length = manifest["feature_specification"]["sequence_length"]
        if input_features < 1 or sequence_length < 1:
            raise ValueError("INVALID_MODEL_SHAPE")
        self.input_features = int(input_features)
        self.sequence_length = int(sequence_length)
        self.seed = int(seed)
        self.learning_rate = float(training["learning_rate"])
        self.batch_size = int(training["batch_size"])
        self.max_epochs = int(training["max_epochs"])
        self.patience = int(training["early_stopping"]["patience"])
        self.gradient_clip_norm = float(training["gradient_clipping"]["maximum_norm"])
        self.adam_beta1 = float(training["adam_beta1"])
        self.adam_beta2 = float(training["adam_beta2"])
        self.adam_epsilon = float(training["adam_epsilon"])
        self.partition_windows = manifest["chronological_partitions_inclusive"]
        self.active_walk_forward_window_id: str | None = None
        self.feature_version = manifest["feature_specification"]["schema_version"]
        self.target_version = manifest["target_specification"]["version"]
        self.dataset_manifest_sha256 = manifest["source_dataset_manifest_sha256"]
        self.contract_inventory = manifest["source_dataset"]["contracts"]
        self.manifest_sha256 = verified_manifest.sha256
        self.training_partition_fingerprint_: str | None = None
        self.validation_partition_fingerprint_: str | None = None
        self.preprocessing_sha256_: str | None = None
        rng = np.random.default_rng(self.seed)
        self.params: dict[str, np.ndarray] = {}

        def he(name: str, shape: tuple[int, ...], fan_in: int) -> None:
            self.params[name] = rng.normal(0.0, np.sqrt(2.0 / fan_in), shape).astype(np.float32)

        def zero(name: str, size: int) -> None:
            self.params[name] = np.zeros(size, dtype=np.float32)

        he("conv1_w", (3, self.input_features, 32), 3 * self.input_features); zero("conv1_b", 32)
        he("conv2_w", (3, 32, 32), 3 * 32); zero("conv2_b", 32)
        he("conv3_w", (3, 32, 16), 3 * 32); zero("conv3_b", 16)
        he("shared_w", (16, 16), 16); zero("shared_b", 16)
        for head in HEADS:
            bound = np.sqrt(6.0 / (16 + CLASS_COUNTS[head]))
            self.params[f"{head}_w"] = rng.uniform(-bound, bound, (16, 3)).astype(np.float32)
            zero(f"{head}_b", 3)
        self.trained_epochs = 0
        self.best_validation_loss: float | None = None

    @property
    def parameter_count(self) -> int:
        return int(sum(value.size for value in self.params.values()))

    @property
    def receptive_field(self) -> int:
        return 1 + (KERNEL_WIDTH - 1) * sum(DILATIONS)

    def _forward(self, x: np.ndarray) -> tuple[dict[str, np.ndarray], tuple]:
        x = _validate_sequences(x).astype(np.float32, copy=False)
        if x.shape[1:] != (self.sequence_length, self.input_features):
            raise ValueError("SEQUENCE_SHAPE_MISMATCH")
        z1, c1 = _conv_forward(x, self.params["conv1_w"], self.params["conv1_b"], DILATIONS[0])
        a1 = np.maximum(z1, 0.0)
        z2, c2 = _conv_forward(a1, self.params["conv2_w"], self.params["conv2_b"], DILATIONS[1])
        a2 = np.maximum(z2, 0.0)
        z3, c3 = _conv_forward(a2, self.params["conv3_w"], self.params["conv3_b"], DILATIONS[2])
        a3 = np.maximum(z3, 0.0)
        final_temporal = a3[:, -1, :]
        shared_z = final_temporal @ self.params["shared_w"] + self.params["shared_b"]
        shared = np.maximum(shared_z, 0.0)
        logits = {head: shared @ self.params[f"{head}_w"] + self.params[f"{head}_b"] for head in HEADS}
        cache = (z1, a1, z2, a2, z3, a3, c1, c2, c3, final_temporal, shared_z, shared)
        return logits, cache

    def predict_logits(self, x: np.ndarray) -> dict[str, np.ndarray]:
        return self._forward(x)[0]

    def predict_probabilities(self, x: np.ndarray) -> dict[str, np.ndarray]:
        return {head: _softmax(value) for head, value in self.predict_logits(x).items()}

    def temporal_logits(self, x: np.ndarray) -> dict[str, np.ndarray]:
        """Per-position logits for causality tests; never used for scoring."""
        value = _validate_sequences(x).astype(np.float32, copy=False)
        if value.shape[2] != self.input_features:
            raise ValueError("FEATURE_VERSION_OR_WIDTH_MISMATCH")
        z1, _ = _conv_forward(value, self.params["conv1_w"], self.params["conv1_b"], DILATIONS[0])
        z2, _ = _conv_forward(np.maximum(z1, 0.0), self.params["conv2_w"], self.params["conv2_b"], DILATIONS[1])
        z3, _ = _conv_forward(np.maximum(z2, 0.0), self.params["conv3_w"], self.params["conv3_b"], DILATIONS[2])
        shared = np.maximum(np.maximum(z3, 0.0) @ self.params["shared_w"] + self.params["shared_b"], 0.0)
        return {head: shared @ self.params[f"{head}_w"] + self.params[f"{head}_b"] for head in HEADS}

    def _loss_and_gradients(self, x: np.ndarray, targets: Mapping[str, np.ndarray]) -> tuple[float, dict[str, np.ndarray]]:
        logits, cache = self._forward(x)
        z1, a1, z2, a2, z3, a3, c1, c2, c3, final_temporal, shared_z, shared = cache
        count = x.shape[0]
        gradients = {name: np.zeros_like(param) for name, param in self.params.items()}
        grad_shared = np.zeros_like(shared)
        total_loss = 0.0
        for head in HEADS:
            y = np.asarray(targets[head], dtype=np.int64)
            if y.shape != (count,) or np.any(y < 0) or np.any(y >= CLASS_COUNTS[head]):
                raise ValueError("INVALID_TARGET_OR_TARGET_VERSION_MISMATCH")
            prob = _softmax(logits[head])
            total_loss += float(-np.log(np.maximum(prob[np.arange(count), y], 1e-12)).mean())
            grad_logits = prob.copy()
            grad_logits[np.arange(count), y] -= 1.0
            grad_logits /= count
            gradients[f"{head}_w"] = shared.T @ grad_logits
            gradients[f"{head}_b"] = grad_logits.sum(axis=0)
            grad_shared += grad_logits @ self.params[f"{head}_w"].T
        grad_shared_z = grad_shared * (shared_z > 0.0)
        gradients["shared_w"] = final_temporal.T @ grad_shared_z
        gradients["shared_b"] = grad_shared_z.sum(axis=0)
        grad_final = grad_shared_z @ self.params["shared_w"].T
        grad_a3 = np.zeros_like(a3); grad_a3[:, -1, :] = grad_final
        grad_a2, gradients["conv3_w"], gradients["conv3_b"] = _conv_backward(grad_a3 * (z3 > 0.0), c3)
        grad_a1, gradients["conv2_w"], gradients["conv2_b"] = _conv_backward(grad_a2 * (z2 > 0.0), c2)
        _, gradients["conv1_w"], gradients["conv1_b"] = _conv_backward(grad_a1 * (z1 > 0.0), c1)
        return total_loss, gradients

    def _apply_adam(self, grads: dict[str, np.ndarray], step: int,
                    first: dict[str, np.ndarray], second: dict[str, np.ndarray]) -> None:
        norm = float(np.sqrt(sum(float(np.square(g).sum()) for g in grads.values())))
        if not np.isfinite(norm):
            raise ValueError("NONFINITE_GRADIENT")
        if norm > self.gradient_clip_norm:
            scale = self.gradient_clip_norm / max(norm, 1e-12)
            grads = {key: grad * scale for key, grad in grads.items()}
        beta1, beta2, epsilon = self.adam_beta1, self.adam_beta2, self.adam_epsilon
        for name, grad in grads.items():
            first[name] = beta1 * first[name] + (1.0 - beta1) * grad
            second[name] = beta2 * second[name] + (1.0 - beta2) * np.square(grad)
            mhat = first[name] / (1.0 - beta1 ** step)
            vhat = second[name] / (1.0 - beta2 ** step)
            self.params[name] -= self.learning_rate * mhat / (np.sqrt(vhat) + epsilon)

    def fit(self, split, validation: PartitionData | None = None, *,
            shuffled_label_control: object | None = None) -> "CausalTemporalConv":
        from .data_integrity import AuthorizedSplit, validate_authorized_split
        if validation is not None or not isinstance(split, AuthorizedSplit):
            raise ValueError("AUTHORIZED_SPLIT_OBJECT_REQUIRED")
        validate_authorized_split(split, self.verified_manifest)
        if split.ablation_contract.get("ablation_id") != self.ablation_id:
            raise ValueError("MODEL_ABLATION_SPLIT_MISMATCH")
        from .experiment_controls import create_model_input_contract
        input_contract = create_model_input_contract(self.verified_manifest,
            model_id="A2_LEARNED_CAUSAL_TCN", seed=self.seed,
            ablation_id=self.ablation_id)
        if (input_contract["input_channels"] != self.input_features
                or input_contract["sequence_shape"] != [self.sequence_length, self.input_features]
                or tuple(input_contract["canonical_feature_order"])
                != tuple(split.ablation_contract["canonical_feature_order"])
                or tuple(input_contract["input_feature_mask"])
                != tuple(split.ablation_contract["feature_mask"])):
            raise ValueError("MODEL_ABLATION_INPUT_CONTRACT_MISMATCH")
        for data in (split.train, split.validation):
            if (data.ablation_id != self.ablation_id
                    or data.ablation_sha256 != split.ablation_contract["ablation_sha256"]
                    or data.feature_mask != tuple(split.ablation_contract["feature_mask"])):
                raise ValueError("MODEL_ABLATION_PARTITION_CONTRACT_MISMATCH")
        training, validation = split.train, split.validation
        self.active_walk_forward_window_id = split.walk_forward_window_id
        if training.partition != "TRAIN":
            raise ValueError("OOS_OR_NONTRAIN_DATA_CANNOT_FIT")
        if validation.partition != "VALIDATION_AND_CALIBRATION":
            raise ValueError("CHECKPOINT_SELECTION_NOT_VALIDATION")
        x = _validate_sequences(training.x).astype(np.float32, copy=False)
        vx = _validate_sequences(validation.x).astype(np.float32, copy=False)
        expected = (self.sequence_length, self.input_features)
        if x.shape[1:] != expected or vx.shape[1:] != expected:
            raise ValueError("SEQUENCE_SHAPE_MISMATCH")
        if not len(x) or not len(vx):
            raise ValueError("EMPTY_TRAIN_OR_VALIDATION")
        for data in (training, validation):
            if data.feature_version != self.feature_version:
                raise ValueError("FEATURE_VERSION_OR_WIDTH_MISMATCH")
            if data.target_version != self.target_version:
                raise ValueError("TARGET_VERSION_OR_TARGET_SPEC_MISMATCH")
            if data.dataset_manifest_sha256 != self.dataset_manifest_sha256:
                raise ValueError("DATASET_MANIFEST_BINDING_MISMATCH")
            if data.market not in {"ES", "NQ"} or data.horizon_minutes not in {5, 15, 30}:
                raise ValueError("TARGET_WINDOW_NOT_IN_MANIFEST")
        if training.market != validation.market or training.horizon_minutes != validation.horizon_minutes:
            raise ValueError("PARTITION_INSTRUMENT_OR_HORIZON_MISMATCH")
        if (not training.preprocessing_sha256 or
                training.preprocessing_sha256 != validation.preprocessing_sha256):
            raise ValueError("PREPROCESSING_ARTIFACT_MISMATCH")
        validate_partition_disjointness({"TRAIN": training, "VALIDATION_AND_CALIBRATION": validation},
                                        sequence_length=self.sequence_length)
        self._validate_partition_window(training, split.walk_forward_window_id)
        self._validate_partition_window(validation, split.walk_forward_window_id)
        for head in HEADS:
            if head not in training.targets or head not in validation.targets:
                raise ValueError("TARGET_VERSION_OR_HEAD_MISMATCH")
        fit_targets = training.targets
        self.training_label_control_sha256_ = None
        if shuffled_label_control is not None:
            # The only supported override is the frozen, TRAIN-only shuffled-label
            # control. It is verified against this exact split before labels enter
            # the optimizer; evaluation labels and split identities remain intact.
            from .experiment_controls import verify_shuffled_label_control
            verify_shuffled_label_control(shuffled_label_control, split=split,
                                          verified_manifest=self.verified_manifest)
            control = shuffled_label_control
            if control.artifact.get("candidate_id") != "A2_LEARNED_CAUSAL_TCN":
                raise ValueError("SHUFFLED_LABEL_CANDIDATE_MISMATCH")
            rows_by_key = {(row.contract, row.session_id,
                _utc_timestamp(row.exchange_timestamp_utc).isoformat()): row
                for row in split.canonical_rows["TRAIN"]}
            assignments = control.train_targets_by_observation
            shuffled = {head: [] for head in HEADS}
            for sequence in training.sequence_keys:
                terminal = sequence[-1]
                row = rows_by_key.get(terminal)
                if row is None or row.observation_id not in assignments:
                    raise ValueError("SHUFFLED_LABEL_TRAIN_IDENTITY_MISMATCH")
                for head in HEADS:
                    shuffled[head].append(int(assignments[row.observation_id][head]))
            fit_targets = {head: np.asarray(values, dtype=np.int64)
                           for head, values in shuffled.items()}
            self.training_label_control_sha256_ = str(control.artifact["control_sha256"])
        first = {key: np.zeros_like(value) for key, value in self.params.items()}
        second = {key: np.zeros_like(value) for key, value in self.params.items()}
        best_loss, best_state, stale_epochs, step, epochs_run = float("inf"), None, 0, 0, 0
        for epoch in range(self.max_epochs):
            # Frozen no-shuffle policy: deterministic, chronological contiguous batches.
            for start in range(0, len(x), self.batch_size):
                stop = min(start + self.batch_size, len(x))
                batch_targets = {head: np.asarray(fit_targets[head])[start:stop] for head in HEADS}
                _, grads = self._loss_and_gradients(x[start:stop], batch_targets)
                step += 1
                self._apply_adam(grads, step, first, second)
            val_loss = self.evaluate_loss(validation)
            epochs_run = epoch + 1
            if val_loss < best_loss:
                best_loss = val_loss
                best_state = {name: value.copy() for name, value in self.params.items()}
                stale_epochs = 0
            else:
                stale_epochs += 1
                if stale_epochs >= self.patience:
                    break
        if best_state is None:
            raise ValueError("NO_VALIDATION_CHECKPOINT")
        self.params = best_state
        self.trained_epochs = epochs_run
        self.best_validation_loss = best_loss
        self.training_partition_fingerprint_ = split.partition_fingerprints["TRAIN"]
        self.validation_partition_fingerprint_ = split.partition_fingerprints["VALIDATION_AND_CALIBRATION"]
        self.preprocessing_sha256_ = split.preprocessing_sha256
        return self

    def _validate_partition_window(self, data: PartitionData,
                                   walk_forward_window_id: str | None = None) -> None:
        if data.partition not in {"TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST"}:
            raise ValueError("PARTITION_TAG_NOT_IN_MANIFEST")
        if data.market not in {"ES", "NQ"} or data.horizon_minutes not in {5, 15, 30}:
            raise ValueError("TARGET_WINDOW_NOT_IN_MANIFEST")
        walk_forward_window_id = walk_forward_window_id or self.active_walk_forward_window_id
        windows = self.partition_windows
        if walk_forward_window_id is not None:
            matches = [window for window in self.verified_manifest.data.get(
                "walk_forward_windows_inclusive", [])
                if window.get("id") == walk_forward_window_id]
            if len(matches) != 1:
                raise ValueError("WALK_FORWARD_WINDOW_NOT_IN_MANIFEST")
            selected = matches[0]
            windows = {"TRAIN": selected["train"],
                "VALIDATION_AND_CALIBRATION": selected["validation"],
                "OOS_TEST": selected["test"]}
        start, end = windows[data.partition]
        start_date, end_date = datetime.fromisoformat(start).date(), datetime.fromisoformat(end).date()
        for sequence in data.sequence_keys or ():
            for contract, _, timestamp in sequence:
                if contract not in self.contract_inventory[data.market]:
                    raise ValueError("CONTRACT_NOT_IN_MANIFEST")
                day = _utc_timestamp(timestamp).date()
                if not start_date <= day <= end_date:
                    raise ValueError("PARTITION_TIMESTAMP_OUTSIDE_MANIFEST_WINDOW")

    def evaluate_loss(self, data: PartitionData) -> float:
        if data.partition != "VALIDATION_AND_CALIBRATION":
            raise ValueError("CHECKPOINT_SELECTION_NOT_VALIDATION")
        if data.feature_version != self.feature_version or data.target_version != self.target_version:
            raise ValueError("FEATURE_OR_TARGET_VERSION_MISMATCH")
        if data.dataset_manifest_sha256 != self.dataset_manifest_sha256:
            raise ValueError("DATASET_MANIFEST_BINDING_MISMATCH")
        if data.market not in {"ES", "NQ"} or data.horizon_minutes not in {5, 15, 30}:
            raise ValueError("TARGET_WINDOW_NOT_IN_MANIFEST")
        if not data.preprocessing_sha256:
            raise ValueError("PREPROCESSING_ARTIFACT_MISSING")
        validate_sequence_identities(data, sequence_length=self.sequence_length)
        self._validate_partition_window(data)
        logits, _ = self._forward(data.x)
        losses = []
        for head in HEADS:
            y = np.asarray(data.targets[head], dtype=np.int64)
            if y.shape != (len(data.x),) or np.any(y < 0) or np.any(y >= CLASS_COUNTS[head]):
                raise ValueError("INVALID_TARGET_OR_TARGET_VERSION_MISMATCH")
            p = _softmax(logits[head])
            losses.append(float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-12)).mean()))
        return float(sum(losses))

    def state(self) -> dict[str, list]:
        return {name: value.tolist() for name, value in sorted(self.params.items())}


def expected_parameter_count(input_features: int = 24) -> int:
    return 3*input_features*32 + 32 + 3*32*32 + 32 + 3*32*16 + 16 + 16*16 + 16 + 3*(16*3 + 3)
