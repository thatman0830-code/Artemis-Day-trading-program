"""Validation-only calibration and abstention artifacts for synthetic/mechanical checks.

This module never loads or scores protected OOS rows. Callers must supply the
factory-issued split, and all artifacts bind to the model artifact and the exact
validation partition fingerprint.
"""
from __future__ import annotations

import hashlib
import math
from decimal import Decimal
from typing import Mapping

import numpy as np

from .data_integrity import AuthorizedSplit, _utc, validate_authorized_split
from .manifest import VerifiedManifest, canonical_bytes, canonical_hash, is_verified_manifest

CALIBRATION_SCHEMA = "bot2-phase5c-validation-calibration-v1"
ABSTENTION_SCHEMA = "bot2-phase5c-validation-abstention-v1"
RESULT_SCHEMA = "bot2-phase5c-result-lineage-v1"
_HEADS = {"direction", "volatility", "structure"}


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _validation_guard(split: AuthorizedSplit, verified_manifest: VerifiedManifest,
                      fit_partition: str) -> None:
    if not is_verified_manifest(verified_manifest) or not verified_manifest.external_anchor_content_verified:
        raise ValueError("EXTERNALLY_ANCHORED_MANIFEST_REQUIRED")
    if fit_partition != "VALIDATION_AND_CALIBRATION":
        raise ValueError("OOS_CALIBRATION_OR_THRESHOLD_FIT_FORBIDDEN")
    validate_authorized_split(split, verified_manifest)


def _temperature_grid(spec: Mapping) -> list[float]:
    grid = spec["deterministic_grid"]
    start, stop, step = (Decimal(str(grid[key])) for key in ("start", "stop", "step"))
    values = []
    value = start
    while value <= stop:
        values.append(float(value))
        value += step
    return values


def _probabilities(logits: np.ndarray, temperature: float) -> np.ndarray:
    from .no_score_boundary import require_scoring_allowed
    require_scoring_allowed("calibration._probabilities")
    scaled = np.asarray(logits, dtype=np.float64) / temperature
    scaled -= np.max(scaled, axis=1, keepdims=True)
    exp = np.exp(scaled)
    return exp / exp.sum(axis=1, keepdims=True)


def fit_temperature_calibrator(logits: np.ndarray, *, split: AuthorizedSplit,
                               verified_manifest: VerifiedManifest,
                               model_artifact: Mapping, head: str,
                               fit_partition: str = "VALIDATION_AND_CALIBRATION") -> dict:
    from .no_score_boundary import require_scoring_allowed
    require_scoring_allowed("fit_temperature_calibrator")
    """Fit frozen scalar temperature grid on validation labels, never OOS."""
    _validation_guard(split, verified_manifest, fit_partition)
    if head not in _HEADS:
        raise ValueError("CALIBRATION_HEAD_NOT_IN_MANIFEST")
    candidate_commit = verified_manifest.pin["review_candidate_commit"]
    if model_artifact.get("manifest_sha256") != verified_manifest.sha256:
        raise ValueError("CALIBRATION_MODEL_MANIFEST_MISMATCH")
    if (model_artifact.get("code_commit") != candidate_commit
            or not isinstance(model_artifact.get("preprocessing_sha256"), str)
            or len(model_artifact["preprocessing_sha256"]) != 64):
        raise ValueError("CALIBRATION_MODEL_IMPLEMENTATION_OR_PREPROCESSING_MISMATCH")
    model_hash = model_artifact.get("artifact_sha256")
    if not isinstance(model_hash, str) or len(model_hash) != 64:
        raise ValueError("CALIBRATION_MODEL_ARTIFACT_HASH_MISSING")
    values = np.asarray(logits, dtype=np.float64)
    labels = np.asarray(split.validation.targets[head], dtype=np.int64)
    if values.shape != (len(split.validation.x), 3) or not np.isfinite(values).all():
        raise ValueError("CALIBRATION_LOGITS_SHAPE_OR_VALUE_INVALID")
    if labels.shape != (len(values),) or np.any(labels < 0) or np.any(labels > 2):
        raise ValueError("CALIBRATION_LABELS_INVALID")
    policy = verified_manifest.data["calibration"]
    best_temperature, best_loss = None, math.inf
    for temperature in _temperature_grid(policy):
        probabilities = _probabilities(values, temperature)
        loss = float(-np.log(np.maximum(probabilities[np.arange(len(labels)), labels], 1e-15)).mean())
        if loss < best_loss:  # ascending deterministic grid supplies smallest-T tie break
            best_temperature, best_loss = temperature, loss
    artifact = {
        "schema_version": CALIBRATION_SCHEMA,
        "method": policy["method"],
        "method_version": "temperature-grid-v1",
        "fit_partition": "VALIDATION_AND_CALIBRATION",
        "manifest_sha256": verified_manifest.sha256,
        "dataset_manifest_sha256": split.dataset_manifest_sha256,
        "model_artifact_sha256": model_hash,
        "preprocessing_artifact_sha256": model_artifact["preprocessing_sha256"],
        "implementation_candidate_commit": candidate_commit,
        "calibration_policy_sha256": canonical_hash(policy),
        "validation_partition_fingerprint": split.partition_fingerprints["VALIDATION_AND_CALIBRATION"],
        "target_version": verified_manifest.data["target_specification"]["version"],
        "market": split.market,
        "horizon_minutes": split.horizon_minutes,
        "head": head,
        "seed": model_artifact["random_seed"],
        "code_commit": model_artifact["code_commit"],
        "temperature": best_temperature,
        "input_logits_sha256": _digest(values.tolist()),
        "calibration_labels_sha256": _digest(labels.tolist()),
        "oos_fitting_performed": False,
    }
    artifact["calibration_sha256"] = canonical_hash(artifact, excluded_key="calibration_sha256")
    return artifact


def fit_model_temperature_calibrator(model, *, split: AuthorizedSplit,
                                     verified_manifest: VerifiedManifest,
                                     model_artifact: Mapping, head: str,
                                     fit_partition: str = "VALIDATION_AND_CALIBRATION") -> dict:
    """Derive calibration logits from the exact bound model artifact and authorized split."""
    _validation_guard(split, verified_manifest, fit_partition)
    if getattr(model, "verified_manifest", None) is not verified_manifest:
        raise ValueError("CALIBRATION_MODEL_MANIFEST_MISMATCH")
    if (model.seed != model_artifact.get("random_seed")
            or model.manifest_sha256 != model_artifact.get("manifest_sha256")
            or model.preprocessing_sha256_ != model_artifact.get("preprocessing_sha256")
            or model.state() != model_artifact.get("weights")
            or model.training_partition_fingerprint_ != model_artifact.get("training_partition_fingerprint")
            or model.validation_partition_fingerprint_ != model_artifact.get("validation_partition_fingerprint")
            or model_artifact.get("weights_sha256") != canonical_hash(model.state())
            or model_artifact.get("artifact_sha256") != canonical_hash(dict(model_artifact), excluded_key="artifact_sha256")):
        raise ValueError("CALIBRATION_MODEL_ARTIFACT_CONTENT_MISMATCH")
    logits_by_head = model.predict_logits(split.validation.x)
    if head not in logits_by_head:
        raise ValueError("CALIBRATION_HEAD_NOT_IN_MANIFEST")
    return fit_temperature_calibrator(logits_by_head[head], split=split,
        verified_manifest=verified_manifest, model_artifact=model_artifact,
        head=head, fit_partition=fit_partition)


def verify_calibration_artifact(artifact: Mapping, *, split: AuthorizedSplit,
                                verified_manifest: VerifiedManifest,
                                model_artifact: Mapping,
                                expected_head: str | None = None) -> None:
    _validation_guard(split, verified_manifest, str(artifact.get("fit_partition", "")))
    if artifact.get("schema_version") != CALIBRATION_SCHEMA:
        raise ValueError("CALIBRATION_SCHEMA_MISMATCH")
    if canonical_hash(dict(artifact), excluded_key="calibration_sha256") != artifact.get("calibration_sha256"):
        raise ValueError("CALIBRATION_CONTENT_HASH_MISMATCH")
    expected = {
        "method": verified_manifest.data["calibration"]["method"],
        "manifest_sha256": verified_manifest.sha256,
        "dataset_manifest_sha256": split.dataset_manifest_sha256,
        "model_artifact_sha256": model_artifact.get("artifact_sha256"),
        "preprocessing_artifact_sha256": model_artifact.get("preprocessing_sha256"),
        "implementation_candidate_commit": verified_manifest.pin["review_candidate_commit"],
        "calibration_policy_sha256": canonical_hash(verified_manifest.data["calibration"]),
        "validation_partition_fingerprint": split.partition_fingerprints["VALIDATION_AND_CALIBRATION"],
        "target_version": verified_manifest.data["target_specification"]["version"],
        "market": split.market, "horizon_minutes": split.horizon_minutes,
        "seed": model_artifact.get("random_seed"), "code_commit": model_artifact.get("code_commit"),
    }
    if any(artifact.get(key) != value for key, value in expected.items()):
        raise ValueError("CALIBRATION_LINEAGE_MISMATCH")
    if artifact.get("oos_fitting_performed") is not False or artifact.get("fit_partition") != "VALIDATION_AND_CALIBRATION":
        raise ValueError("OOS_CALIBRATION_OR_THRESHOLD_FIT_FORBIDDEN")
    if (artifact.get("head") not in _HEADS
            or (expected_head is not None and artifact.get("head") != expected_head)
            or artifact.get("implementation_candidate_commit") != verified_manifest.pin["review_candidate_commit"]
            or artifact.get("temperature") not in _temperature_grid(verified_manifest.data["calibration"])):
        raise ValueError("CALIBRATION_PARAMETERS_INVALID")


def select_abstention_threshold(probabilities: np.ndarray, *, split: AuthorizedSplit,
                                verified_manifest: VerifiedManifest,
                                model_artifact: Mapping, head: str,
                                target_coverage: float,
                                fit_partition: str = "VALIDATION_AND_CALIBRATION") -> dict:
    from .no_score_boundary import require_scoring_allowed
    require_scoring_allowed("select_abstention_threshold")
    """Choose entropy cutoff on validation only; retain complete cutoff tie groups."""
    _validation_guard(split, verified_manifest, fit_partition)
    policy = verified_manifest.data["uncertainty_abstention"]
    if target_coverage not in policy["coverage_points"]:
        raise ValueError("ABSTENTION_COVERAGE_NOT_IN_MANIFEST")
    if head not in _HEADS:
        raise ValueError("ABSTENTION_HEAD_NOT_IN_MANIFEST")
    values = np.asarray(probabilities, dtype=np.float64)
    count = len(split.validation.x)
    if (values.shape != (count, 3) or not np.isfinite(values).all()
            or np.any(values < 0) or not np.allclose(values.sum(axis=1), 1.0, atol=1e-7)):
        raise ValueError("ABSTENTION_PROBABILITIES_INVALID")
    entropy = -np.sum(values * np.log(np.maximum(values, 1e-15)), axis=1) / math.log(3.0)
    terminals = [sequence[-1] for sequence in split.validation.sequence_keys]
    order = sorted(range(count), key=lambda i: (float(entropy[i]),
        _utc(terminals[i][2]), split.market, terminals[i][0]))
    requested = max(1, int(math.ceil(target_coverage * count)))
    threshold = float(entropy[order[requested - 1]])
    retained = int(np.count_nonzero(entropy <= threshold))
    artifact = {
        "schema_version": ABSTENTION_SCHEMA,
        "method": policy["normalized_entropy"],
        "fit_partition": "VALIDATION_AND_CALIBRATION",
        "manifest_sha256": verified_manifest.sha256,
        "dataset_manifest_sha256": split.dataset_manifest_sha256,
        "model_artifact_sha256": model_artifact.get("artifact_sha256"),
        "validation_partition_fingerprint": split.partition_fingerprints["VALIDATION_AND_CALIBRATION"],
        "market": split.market, "horizon_minutes": split.horizon_minutes,
        "head": head, "seed": model_artifact.get("random_seed"),
        "target_coverage": target_coverage, "entropy_threshold": threshold,
        "requested_rows": requested, "retained_rows": retained,
        "realized_coverage": retained / count,
        "ties_retained": policy["ranking"].endswith("retain full cutoff tie group and report realized coverage."),
        "probabilities_sha256": _digest(values.tolist()),
        "oos_threshold_selection_performed": False,
    }
    artifact["artifact_sha256"] = canonical_hash(artifact, excluded_key="artifact_sha256")
    return artifact


def verify_abstention_artifact(artifact: Mapping, *, split: AuthorizedSplit,
                               verified_manifest: VerifiedManifest,
                               model_artifact: Mapping) -> None:
    _validation_guard(split, verified_manifest, str(artifact.get("fit_partition", "")))
    if artifact.get("schema_version") != ABSTENTION_SCHEMA:
        raise ValueError("ABSTENTION_SCHEMA_MISMATCH")
    if canonical_hash(dict(artifact), excluded_key="artifact_sha256") != artifact.get("artifact_sha256"):
        raise ValueError("ABSTENTION_CONTENT_HASH_MISMATCH")
    expected = (verified_manifest.sha256, split.dataset_manifest_sha256,
        model_artifact.get("artifact_sha256"), split.partition_fingerprints["VALIDATION_AND_CALIBRATION"],
        split.market, split.horizon_minutes, model_artifact.get("random_seed"))
    actual = (artifact.get("manifest_sha256"), artifact.get("dataset_manifest_sha256"),
        artifact.get("model_artifact_sha256"), artifact.get("validation_partition_fingerprint"),
        artifact.get("market"), artifact.get("horizon_minutes"), artifact.get("seed"))
    if actual != expected:
        raise ValueError("ABSTENTION_LINEAGE_MISMATCH")
    if artifact.get("oos_threshold_selection_performed") is not False:
        raise ValueError("OOS_CALIBRATION_OR_THRESHOLD_FIT_FORBIDDEN")


def create_result_lineage_contract(*, verified_manifest: VerifiedManifest,
                                   model_artifact: Mapping,
                                   preprocessing_sha256: str,
                                   calibration_sha256: str | None,
                                   market: str, horizon_minutes: int, head: str,
                                   walk_forward_window: str) -> dict:
    """Describe required future result bindings without generating any metrics."""
    if not is_verified_manifest(verified_manifest):
        raise ValueError("EXTERNALLY_ANCHORED_MANIFEST_REQUIRED")
    manifest = verified_manifest.data
    allowed_windows = {window["id"] for window in manifest["walk_forward_windows_inclusive"]}
    if (market not in {"ES", "NQ"}
            or horizon_minutes not in manifest["target_specification"]["horizons_minutes"]
            or head not in _HEADS or walk_forward_window not in allowed_windows
            or model_artifact.get("manifest_sha256") != verified_manifest.sha256
            or not isinstance(preprocessing_sha256, str) or len(preprocessing_sha256) != 64
            or (calibration_sha256 is not None and len(calibration_sha256) != 64)):
        raise ValueError("RESULT_IDENTITY_NOT_IN_MANIFEST")
    return {
        "schema_version": RESULT_SCHEMA,
        "manifest_sha256": verified_manifest.sha256,
        "dataset_manifest_sha256": manifest["source_dataset_manifest_sha256"],
        "model_artifact_sha256": model_artifact["artifact_sha256"],
        "preprocessing_sha256": preprocessing_sha256,
        "calibration_sha256": calibration_sha256,
        "market": market, "horizon_minutes": horizon_minutes,
        "head": head, "seed": model_artifact["random_seed"],
        "walk_forward_window": walk_forward_window,
        "code_commit": model_artifact["code_commit"],
        "result_sha256": None,
        "evaluation_authorized": manifest.get("evaluation_permitted") is True,
        "oos_scoring_performed": False,
    }


def validate_result_lineage_contract(contract: Mapping, *, verified_manifest: VerifiedManifest,
                                     model_artifact: Mapping) -> None:
    """Validate only a no-results contract; never authorize score generation."""
    manifest = verified_manifest.data
    if contract.get("schema_version") != RESULT_SCHEMA:
        raise ValueError("RESULT_CONTRACT_SCHEMA_MISMATCH")
    allowed_windows = {window["id"] for window in manifest["walk_forward_windows_inclusive"]}
    expected = {
        "manifest_sha256": verified_manifest.sha256,
        "dataset_manifest_sha256": manifest["source_dataset_manifest_sha256"],
        "model_artifact_sha256": model_artifact.get("artifact_sha256"),
        "seed": model_artifact.get("random_seed"),
        "code_commit": model_artifact.get("code_commit"),
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ValueError("RESULT_LINEAGE_MISMATCH")
    if (contract.get("walk_forward_window") not in allowed_windows
            or contract.get("market") not in {"ES", "NQ"}
            or contract.get("horizon_minutes") not in manifest["target_specification"]["horizons_minutes"]
            or contract.get("head") not in _HEADS):
        raise ValueError("RESULT_IDENTITY_NOT_IN_MANIFEST")
    if (contract.get("evaluation_authorized") is not False
            or contract.get("result_sha256") is not None
            or contract.get("oos_scoring_performed") is not False
            or any(key in contract for key in ("accuracy", "f1", "log_loss", "brier", "confusion_matrix"))):
        raise ValueError("PROTECTED_OOS_EXECUTION_NOT_AUTHORIZED")
