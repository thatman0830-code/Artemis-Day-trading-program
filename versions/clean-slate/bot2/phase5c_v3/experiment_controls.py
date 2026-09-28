"""Manifest-derived experimental controls; no protected model scoring lives here."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

import numpy as np

from .data_integrity import AuthorizedSplit, MarketObservation, validate_authorized_split
from .manifest import VerifiedManifest, canonical_bytes, is_verified_manifest

CONTROL_SCHEMA = "bot2-phase5c-v3-experiment-control-v1"
INPUT_CONTRACT_SCHEMA = "bot2-phase5c-v3-model-input-contract-v2"
ABLATION_SCHEMA = "bot2-phase5c-v3-fixed-dimension-ablation-v2"
PREPROCESSING_VERSION = "train-unique-row-population-zscore-v1"
_NEURAL_CANDIDATES = {"A1_NUMPY_MULTIHEAD_MLP", "A2_LEARNED_CAUSAL_TCN"}
_A0_CANDIDATES = {"A0_PREVIOUS_LABEL_PERSISTENCE", "A0_TRAIN_MAJORITY",
                  "A0_TRAIN_TRANSITION_MATRIX"}


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _utc_key(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("CONTROL_TIMESTAMP_NOT_UTC")
    return parsed


def create_ablation_contract(verified_manifest: VerifiedManifest, ablation_id: str) -> dict:
    if not is_verified_manifest(verified_manifest):
        raise ValueError("MANIFEST_NOT_VERIFIED")
    features = tuple(verified_manifest.data["feature_specification"]["features"])
    entries = [item for item in verified_manifest.data["feature_ablations"]
               if item.get("id") == ablation_id]
    if len(entries) != 1:
        raise ValueError("ABLATION_NOT_IN_MANIFEST")
    excluded = tuple(entries[0]["excluded_features"])
    if len(set(excluded)) != len(excluded) or not set(excluded).issubset(features):
        raise ValueError("FROZEN_ABLATION_FEATURES_INVALID")
    excluded_set = set(excluded)
    mask = [0 if name in excluded_set else 1 for name in features]
    feature_family_membership = {
        name: [str(item["id"]) for item in verified_manifest.data["feature_ablations"]
               if name in set(item["excluded_features"])]
        for name in features
    }
    result = {
        "schema_version": ABLATION_SCHEMA,
        "manifest_sha256": verified_manifest.sha256,
        "implementation_candidate_commit": verified_manifest.pin["review_candidate_commit"],
        "ablation_id": ablation_id,
        "canonical_feature_order": list(features),
        "feature_family_membership": feature_family_membership,
        "active_features": [name for name, enabled in zip(features, mask) if enabled],
        "ablated_features": [name for name, enabled in zip(features, mask) if not enabled],
        "feature_mask": mask,
        "input_channels": len(features),
        "preprocessing_version": PREPROCESSING_VERSION,
        "mask_stage": "after training-only standardization; before model input",
        "masked_value_standardized": 0.0,
        "transform": "preserve canonical channel order and width; set ablated standardized channels to exact zero",
        "feature_version": verified_manifest.data["feature_specification"]["schema_version"],
    }
    result["ablation_sha256"] = _sha(result)
    return result


def verify_ablation_contract(contract: Mapping, verified_manifest: VerifiedManifest) -> None:
    if contract.get("schema_version") != ABLATION_SCHEMA:
        raise ValueError("ABLATION_SCHEMA_MISMATCH")
    expected = create_ablation_contract(verified_manifest, str(contract.get("ablation_id", "")))
    actual = dict(contract)
    digest = actual.pop("ablation_sha256", None)
    if digest != _sha(actual) or actual != {key: value for key, value in expected.items()
                                           if key != "ablation_sha256"}:
        raise ValueError("ABLATION_MANIFEST_BINDING_MISMATCH")


def apply_ablation_mask(normalized_features: np.ndarray, *, contract: Mapping,
                        verified_manifest: VerifiedManifest,
                        feature_order: Sequence[str]) -> np.ndarray:
    """Mask post-standardization channels without changing order or tensor shape."""
    verify_ablation_contract(contract, verified_manifest)
    canonical = tuple(contract["canonical_feature_order"])
    if tuple(feature_order) != canonical:
        raise ValueError("ABLATION_SOURCE_FEATURE_ORDER_MISMATCH")
    values = np.asarray(normalized_features)
    if values.ndim not in (2, 3) or values.shape[-1] != len(canonical):
        raise ValueError("ABLATION_INPUT_WIDTH_MISMATCH")
    if not np.isfinite(values).all():
        raise ValueError("ABLATION_INPUT_NONFINITE")
    mask = np.asarray(contract["feature_mask"], dtype=np.float32)
    output = np.where(mask.astype(bool), values, np.zeros((), dtype=values.dtype))
    if output.shape != values.shape or not np.isfinite(output).all():
        raise ValueError("ABLATION_OUTPUT_SHAPE_OR_VALUE_INVALID")
    output.setflags(write=False)
    return output


def apply_ablation_to_rows(rows: Sequence[MarketObservation], *, contract: Mapping,
                           verified_manifest: VerifiedManifest,
                           preprocessor: object) -> tuple[dict, ...]:
    """Standardize with the authorized TRAIN scaler, then apply fixed-width mask."""
    verify_ablation_contract(contract, verified_manifest)
    from .model import TrainingOnlyStandardizer
    if not isinstance(preprocessor, TrainingOnlyStandardizer):
        raise ValueError("PREPROCESSING_ARTIFACT_MISSING")
    state = preprocessor.state()
    if (state.get("fit_partition") != "TRAIN"
            or state.get("manifest_sha256") != verified_manifest.sha256
            or state.get("feature_order") != contract["canonical_feature_order"]
            or state.get("version") != PREPROCESSING_VERSION):
        raise ValueError("PREPROCESSING_PROVENANCE_MISMATCH")
    from .data_integrity import feature_partition_fingerprint
    if state.get("training_feature_fingerprint") != feature_partition_fingerprint(
            rows, partition="TRAIN"):
        raise ValueError("PREPROCESSING_TRAINING_PARTITION_MISMATCH")
    canonical = tuple(contract["canonical_feature_order"])
    if any(tuple(row.feature_names) != canonical for row in rows):
        raise ValueError("ABLATION_SOURCE_FEATURE_ORDER_MISMATCH")
    raw = np.asarray([row.features for row in rows], dtype=np.float64)
    standardized = preprocessor.transform(raw)
    masked = apply_ablation_mask(standardized, contract=contract,
        verified_manifest=verified_manifest, feature_order=canonical)
    output = []
    for row, values in zip(rows, masked):
        output.append({
            "observation_id": row.observation_id,
            "feature_names": list(canonical),
            "features": [float(value) for value in values],
            "feature_mask": list(contract["feature_mask"]),
            "ablation_id": contract["ablation_id"],
            "ablation_sha256": contract["ablation_sha256"],
        })
    return tuple(output)


@dataclass(frozen=True, slots=True)
class AblationExecution:
    """Fixed-width mask execution record; contains no model results."""
    artifact: Mapping
    transformed_rows: tuple[Mapping, ...]


def execute_ablation_control(rows: Sequence[MarketObservation], *,
                             verified_manifest: VerifiedManifest,
                             preprocessor: object,
                             model_id: str, seed: int,
                             ablation_id: str) -> AblationExecution:
    """Execute a manifest-approved TRAIN-standardized mask; never scores a model."""
    contract = create_ablation_contract(verified_manifest, ablation_id)
    transformed = apply_ablation_to_rows(rows, contract=contract,
        verified_manifest=verified_manifest, preprocessor=preprocessor)
    input_contract = create_model_input_contract(verified_manifest, model_id=model_id,
        seed=seed, ablation_id=ablation_id)
    body = {
        "schema_version": ABLATION_SCHEMA,
        "execution_type": "ENGINEERING_FIXED_DIMENSION_MASK_ONLY",
        "manifest_sha256": verified_manifest.sha256,
        "implementation_candidate_commit": verified_manifest.pin["review_candidate_commit"],
        "ablation_id": ablation_id,
        "ablation_sha256": contract["ablation_sha256"],
        "model_id": model_id,
        "seed": seed,
        "input_contract_sha256": input_contract["contract_sha256"],
        "input_feature_order": list(contract["canonical_feature_order"]),
        "feature_mask": list(contract["feature_mask"]),
        "input_channels": contract["input_channels"],
        "preprocessing_version": contract["preprocessing_version"],
        "preprocessing_sha256": preprocessor.sha256,
        "transformed_rows_sha256": _sha([dict(row) for row in transformed]),
        "row_count": len(transformed),
        "predictions_generated": False,
        "metrics_generated": False,
        "protected_models_scored": [],
        "trading_authority": "NONE",
    }
    body["execution_sha256"] = _sha(body)
    return AblationExecution(body, transformed)


def verify_ablation_execution(execution: AblationExecution, *,
                              rows: Sequence[MarketObservation],
                              preprocessor: object,
                              verified_manifest: VerifiedManifest) -> None:
    artifact = dict(execution.artifact)
    expected = execute_ablation_control(rows, verified_manifest=verified_manifest,
        preprocessor=preprocessor,
        model_id=str(artifact.get("model_id", "")),
        seed=int(artifact.get("seed", verified_manifest.data["random_seeds"][0])),
        ablation_id=str(artifact.get("ablation_id", "")))
    if (dict(expected.artifact) != artifact
            or tuple(map(dict, expected.transformed_rows)) != tuple(map(dict, execution.transformed_rows))):
        raise ValueError("ABLATION_EXECUTION_PROVENANCE_MISMATCH")


def create_model_input_contract(verified_manifest: VerifiedManifest, *, model_id: str,
                                seed: int, ablation_id: str = "ALL") -> dict:
    """Create a machine-checkable contract from the frozen manifest, not caller settings."""
    if not is_verified_manifest(verified_manifest):
        raise ValueError("MANIFEST_NOT_VERIFIED")
    manifest = verified_manifest.data
    if seed not in manifest["random_seeds"]:
        raise ValueError("MODEL_SEED_NOT_IN_MANIFEST")
    full_features = tuple(manifest["feature_specification"]["features"])
    ablation = create_ablation_contract(verified_manifest, ablation_id)
    active_features = tuple(ablation["active_features"])
    seq_len = int(manifest["feature_specification"]["sequence_length"])
    if model_id in _A0_CANDIDATES:
        if model_id == "A0_TRAIN_MAJORITY":
            definition = manifest["architectures"][model_id]
            kind = "TRAIN_LABELS_ONLY"
            label_policy = "TRAIN_PARTITION_FIT_ONLY_NO_ROW_LABEL_INPUT"
        elif model_id == "A0_TRAIN_TRANSITION_MATRIX":
            definition = manifest["architectures"][model_id]
            kind = "TRAIN_LABEL_TRANSITIONS_PLUS_PRIOR_LABEL_ELIGIBLE_AT_T"
            label_policy = "PRIOR_LABEL_END_AT_OR_BEFORE_T"
        else:
            definition = manifest["architectures"][model_id]
            kind = "PRIOR_LABELS_WHOSE_INFORMATION_ENDS_BY_T"
            label_policy = "PRIOR_LABEL_END_AT_OR_BEFORE_T"
        shape = []
        temporal_scope = ("TRAIN_PARTITION_ONLY" if model_id == "A0_TRAIN_MAJORITY"
                          else "label_information_end_at_or_before_decision_time")
        contract_features = []
    elif model_id == "A1_NUMPY_MULTIHEAD_MLP":
        definition = manifest["architectures"][model_id]
        shape = [seq_len, len(full_features)]
        temporal_scope, contract_features = "ordered_features_through_decision_time_T", list(full_features)
        kind = "STANDARDIZED_CAUSAL_SEQUENCE_FLATTENED"
    elif model_id == "A2_LEARNED_CAUSAL_TCN":
        definition = manifest["architectures"][model_id]
        expected_channels = definition["blocks"][0]["in_channels"]
        if len(full_features) != expected_channels:
            raise ValueError("FROZEN_A2_FEATURE_COUNT_CONFLICT")
        shape = [seq_len, expected_channels]
        temporal_scope, contract_features = "ordered_causal_features_through_decision_time_T", list(full_features)
        kind = "STANDARDIZED_CAUSAL_SEQUENCE_TEMPORAL_ORDER_PRESERVED"
    else:
        raise ValueError("MODEL_NOT_IN_FROZEN_CANDIDATE_SET")
    body = {
        "schema_version": INPUT_CONTRACT_SCHEMA,
        "manifest_sha256": verified_manifest.sha256,
        "implementation_candidate_commit": verified_manifest.pin["review_candidate_commit"],
        "model_id": model_id,
        "seed": seed,
        "input_kind": kind,
        "feature_version": manifest["feature_specification"]["schema_version"],
        "target_version": manifest["target_specification"]["version"],
        "features": contract_features,
        "canonical_feature_order": list(full_features),
        "active_features": list(active_features) if model_id in _NEURAL_CANDIDATES else [],
        "ablated_features": list(ablation["ablated_features"]) if model_id in _NEURAL_CANDIDATES else [],
        "input_feature_mask": list(ablation["feature_mask"]) if model_id in _NEURAL_CANDIDATES else [],
        "input_channels": len(full_features) if model_id in _NEURAL_CANDIDATES else 0,
        "preprocessing_version": PREPROCESSING_VERSION if model_id in _NEURAL_CANDIDATES else "NOT_APPLICABLE",
        "ablation_scope": ("FEATURE_CHANNELS" if model_id in _NEURAL_CANDIDATES
                           else "NOT_APPLICABLE_NO_FEATURE_INPUT"),
        "label_input_policy": label_policy if model_id in _A0_CANDIDATES else "NO_LABEL_INPUT",
        "sequence_shape": shape,
        "flattened_width": int(np.prod(shape)) if shape else 0,
        "temporal_scope": temporal_scope,
        "architecture_definition_sha256": _sha(definition),
        "ablation_id": (ablation_id if model_id in _NEURAL_CANDIDATES
                        else "NOT_APPLICABLE_NO_FEATURE_INPUT"),
        "ablation_sha256": (ablation["ablation_sha256"]
                            if model_id in _NEURAL_CANDIDATES else None),
        "architecture_version": (definition.get("architecture_version", "UNVERSIONED")
                                 if isinstance(definition, Mapping)
                                 else f"BASELINE_RULE:{definition}"),
        "future_inputs_allowed": False,
        "target_labels_as_features_allowed": False,
        "training_partition": "TRAIN",
        "evaluation_partition_access": False,
    }
    body["contract_sha256"] = _sha(body)
    return body


def validate_model_input_contract(contract: Mapping, verified_manifest: VerifiedManifest, *,
                                  actual_features: Sequence[str],
                                  actual_sequence_shape: Sequence[int],
                                  actual_feature_mask: Sequence[int] | None = None,
                                  latest_input_timestamp_utc: str,
                                  decision_timestamp_utc: str,
                                  contains_target_labels: bool = False,
                                  label_information_end_utc: str | None = None) -> None:
    model_id = str(contract.get("model_id", ""))
    requested_ablation = ("ALL" if model_id in _A0_CANDIDATES
                          else str(contract.get("ablation_id", "")))
    expected = create_model_input_contract(verified_manifest,
        model_id=model_id, seed=int(contract.get("seed", -1)),
        ablation_id=requested_ablation)
    actual = dict(contract)
    digest = actual.pop("contract_sha256", None)
    if digest != _sha(actual) or actual != {key: value for key, value in expected.items()
                                           if key != "contract_sha256"}:
        raise ValueError("MODEL_INPUT_CONTRACT_MISMATCH")
    if tuple(actual_features) != tuple(expected["features"]):
        raise ValueError("UNAUTHORIZED_MODEL_FEATURE_INPUT")
    if tuple(actual_sequence_shape) != tuple(expected["sequence_shape"]):
        raise ValueError("MODEL_INPUT_SHAPE_MISMATCH")
    if actual["model_id"] in _NEURAL_CANDIDATES:
        if actual_feature_mask is None:
            raise ValueError("MODEL_ABLATION_MASK_REQUIRED")
        if tuple(actual_feature_mask) != tuple(expected["input_feature_mask"]):
            raise ValueError("MODEL_ABLATION_MASK_MISMATCH")
    elif actual_feature_mask not in (None, (), []):
        raise ValueError("A0_MUST_NOT_RECEIVE_FEATURE_MASK")
    if contains_target_labels:
        if label_information_end_utc is None:
            raise ValueError("MODEL_LABEL_INPUT_INFORMATION_INTERVAL_REQUIRED")
        if _utc_key(label_information_end_utc) > _utc_key(decision_timestamp_utc):
            raise ValueError("FUTURE_LABEL_INFORMATION_REACHES_MODEL")
    if actual["model_id"] == "A0_TRAIN_MAJORITY" and contains_target_labels:
        raise ValueError("A0_MAJORITY_HAS_NO_PER_ROW_LABEL_INPUT")
    if (actual["model_id"] in {"A0_PREVIOUS_LABEL_PERSISTENCE", "A0_TRAIN_TRANSITION_MATRIX"}
            and not contains_target_labels):
        raise ValueError("A0_PRIOR_LABEL_INPUT_REQUIRED")
    if actual["model_id"] not in _A0_CANDIDATES and contains_target_labels:
        raise ValueError("TARGET_LABELS_CANNOT_BE_MODEL_FEATURES")
    if _utc_key(latest_input_timestamp_utc) > _utc_key(decision_timestamp_utc):
        raise ValueError("FUTURE_INFORMATION_REACHES_MODEL")


@dataclass(frozen=True, slots=True)
class ShuffledLabelControl:
    """Engineering-only TRAIN label assignment. Contains no predictions or metrics."""
    artifact: Mapping
    train_targets_by_observation: Mapping[str, Mapping[str, int]]


def execute_shuffled_label_control(split: AuthorizedSplit, *,
                                   verified_manifest: VerifiedManifest,
                                   candidate_id: str, candidate_seed: int,
                                   run_index: int) -> ShuffledLabelControl:
    """Apply only frozen TRAIN-only, within-session/head permutations; never score."""
    if not is_verified_manifest(verified_manifest) or not split.valid():
        raise ValueError("AUTHORIZED_SPLIT_AND_MANIFEST_REQUIRED")
    validate_authorized_split(split, verified_manifest)
    if candidate_id not in _NEURAL_CANDIDATES:
        raise ValueError("SHUFFLE_CANDIDATE_NOT_IN_MANIFEST")
    manifest = verified_manifest.data
    if candidate_seed not in manifest["random_seeds"]:
        raise ValueError("SHUFFLE_CANDIDATE_SEED_NOT_IN_MANIFEST")
    policy = manifest["shuffled_label_control"]
    seeds = tuple(policy["seeds"])
    runs = int(policy["runs_per_candidate_seed"])
    if not 1 <= run_index <= runs or len(seeds) != runs:
        raise ValueError("SHUFFLE_RUN_NOT_IN_FROZEN_POLICY")
    shuffle_seed = int(seeds[run_index - 1])
    if policy.get("partition_shuffled") != "TRAIN only" or policy.get("evaluation_labels") != "Validation/test/OOS labels unchanged":
        raise ValueError("SHUFFLE_PARTITION_POLICY_MISMATCH")
    train_rows = tuple(split.canonical_rows["TRAIN"])
    from .model import HEADS
    heads = tuple(HEADS)
    groups: dict[tuple[str, str, str, str], list[MarketObservation]] = {}
    for row in train_rows:
        groups.setdefault((row.market, row.contract, row.session_id, split.horizon_minutes), []).append(row)
    rng = np.random.default_rng(shuffle_seed)
    assignments = {row.observation_id: dict(row.targets) for row in train_rows}
    for key in sorted(groups):
        ordered = sorted(groups[key], key=lambda row: _utc_key(row.exchange_timestamp_utc))
        for head in heads:
            labels = np.asarray([row.targets[head] for row in ordered], dtype=np.int64)
            if np.any(labels < 0) or np.any(labels > 2):
                raise ValueError("SHUFFLE_LABEL_OUT_OF_RANGE")
            permuted = labels[rng.permutation(len(labels))]
            for row, label in zip(ordered, permuted):
                assignments[row.observation_id][head] = int(label)
    body = {
        "schema_version": CONTROL_SCHEMA,
        "control_type": "TRAIN_ONLY_SHUFFLED_LABEL_ASSIGNMENT",
        "manifest_sha256": verified_manifest.sha256,
        "implementation_candidate_commit": verified_manifest.pin["review_candidate_commit"],
        "dataset_manifest_sha256": split.dataset_manifest_sha256,
        "training_partition_fingerprint": split.partition_fingerprints["TRAIN"],
        "candidate_id": candidate_id,
        "candidate_seed": candidate_seed,
        "run_index": run_index,
        "shuffle_seed": shuffle_seed,
        "partition_shuffled": "TRAIN",
        "permutation_unit": policy["permutation_unit"],
        "assignment_sha256": _sha(assignments),
        "records": len(assignments),
        "evaluation_labels_changed": False,
        "predictions_generated": False,
        "metrics_generated": False,
        "protected_models_scored": [],
        "trading_authority": "NONE",
    }
    body["control_sha256"] = _sha(body)
    return ShuffledLabelControl(body, assignments)


def verify_shuffled_label_control(control: ShuffledLabelControl, *,
                                  split: AuthorizedSplit,
                                  verified_manifest: VerifiedManifest) -> None:
    expected = execute_shuffled_label_control(split, verified_manifest=verified_manifest,
        candidate_id=str(control.artifact.get("candidate_id", "")),
        candidate_seed=int(control.artifact.get("candidate_seed", -1)),
        run_index=int(control.artifact.get("run_index", 0)))
    if dict(control.artifact) != dict(expected.artifact) or {
            key: dict(value) for key, value in control.train_targets_by_observation.items()
    } != {key: dict(value) for key, value in expected.train_targets_by_observation.items()}:
        raise ValueError("SHUFFLED_LABEL_CONTROL_PROVENANCE_MISMATCH")
