"""Manifest-bound immutable A2 artifacts with atomic no-overwrite writes."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import math
from pathlib import Path
from typing import Any

import numpy as np

from .manifest import (VerifiedManifest, canonical_hash, is_verified_manifest,
                       sha256_file)
from .model import ARCHITECTURE_VERSION, FEATURE_VERSION, TARGET_VERSION, expected_parameter_count

ARTIFACT_SCHEMA = "bot2-phase5c-a2-artifact-v4"
_HEX = set("0123456789abcdef")


def _is_digest(value: object, *, lengths: tuple[int, ...] = (64,)) -> bool:
    return isinstance(value, str) and len(value) in lengths and set(value.lower()) <= _HEX


def _expected_artifact_identity(verified: VerifiedManifest, seed: int, *, market: str,
                               horizon_minutes: int) -> dict[str, Any]:
    manifest = verified.data
    if not is_verified_manifest(verified):
        raise ValueError("MANIFEST_NOT_VERIFIED")
    if seed not in manifest["random_seeds"]:
        raise ValueError("SEED_NOT_AUTHORIZED_BY_MANIFEST")
    if market not in {"ES", "NQ"} or horizon_minutes not in manifest["target_specification"]["horizons_minutes"]:
        raise ValueError("ARTIFACT_MARKET_OR_HORIZON_NOT_IN_MANIFEST")
    partitions = manifest["chronological_partitions_inclusive"]
    return {
        "experiment_id": manifest["experiment_id"],
        "protocol_version": manifest["schema_version"],
        "manifest_sha256": verified.sha256,
        "dataset_manifest_sha256": manifest["source_dataset_manifest_sha256"],
        "feature_version": manifest["feature_specification"]["schema_version"],
        "feature_registry_sha256": manifest["feature_specification"]["registry_sha256"],
        "target_version": manifest["target_specification"]["version"],
        "target_spec_sha256": manifest["target_specification"]["spec_sha256"],
        "architecture_version": manifest["architectures"]["A2_LEARNED_CAUSAL_TCN"]["architecture_version"],
        "random_seed": seed,
        "market": market,
        "horizon_minutes": horizon_minutes,
        "sequence_spec": {"length": manifest["feature_specification"]["sequence_length"],
                          "cadence_seconds": manifest["feature_specification"]["sequence_cadence_seconds"]},
        "partition_identity": manifest["chronological_partitions_inclusive"],
        "training_window": {"partition": "TRAIN", "window": partitions["TRAIN"]},
        "validation_window": {"partition": "VALIDATION_AND_CALIBRATION",
                              "window": partitions["VALIDATION_AND_CALIBRATION"]},
        "raw_archive_sha256": verified.pin["raw_archive_tree_sha256"],
    }


def create_artifact(model: Any, *, verified_manifest: VerifiedManifest,
                    lineage: dict) -> dict:
    required = ("raw_archive_sha256", "dataset_sha256", "code_commit", "market", "horizon_minutes",
                "dependency_versions", "preprocessing", "training_window",
                "validation_window", "training_partition_fingerprint",
                "validation_partition_fingerprint")
    missing = [field for field in required if field not in lineage]
    if missing:
        raise ValueError("ARTIFACT_LINEAGE_MISSING:" + ",".join(missing))
    if not is_verified_manifest(verified_manifest):
        raise ValueError("MANIFEST_NOT_VERIFIED")
    if getattr(model, "verified_manifest", None) is not verified_manifest:
        raise ValueError("MODEL_MANIFEST_BINDING_MISMATCH")
    if (getattr(model, "trained_epochs", 0) < 1
            or not _is_digest(getattr(model, "training_partition_fingerprint_", None))
            or not _is_digest(getattr(model, "validation_partition_fingerprint_", None))
            or not _is_digest(getattr(model, "preprocessing_sha256_", None))):
        raise ValueError("MODEL_NOT_FITTED_FROM_AUTHORIZED_SPLIT")
    seed = int(lineage.get("random_seed", model.seed))
    identity = _expected_artifact_identity(verified_manifest, seed, market=lineage["market"],
                                          horizon_minutes=int(lineage["horizon_minutes"]))
    if model.manifest_sha256 != identity["manifest_sha256"]:
        raise ValueError("MODEL_MANIFEST_BINDING_MISMATCH")
    for field, expected in identity.items():
        supplied = lineage.get(field, getattr(model, "seed", None) if field == "random_seed" else expected)
        if supplied != expected:
            raise ValueError("ARTIFACT_PROVENANCE_MISMATCH:" + field)
    if not _is_digest(lineage["raw_archive_sha256"]):
        raise ValueError("INVALID_RAW_ARCHIVE_HASH")
    if lineage["raw_archive_sha256"] != identity["raw_archive_sha256"]:
        raise ValueError("RAW_ARCHIVE_BINDING_MISMATCH")
    if lineage["dataset_sha256"] != identity["dataset_manifest_sha256"]:
        raise ValueError("DATASET_MANIFEST_BINDING_MISMATCH")
    if not _is_digest(lineage["code_commit"], lengths=(40, 64)):
        raise ValueError("INVALID_CODE_COMMIT")
    preprocessing = lineage["preprocessing"]
    if preprocessing.get("fit_partition") != "TRAIN":
        raise ValueError("PREPROCESSING_FIT_NOT_TRAIN")
    if preprocessing.get("version") != "train-unique-row-population-zscore-v1":
        raise ValueError("PREPROCESSING_VERSION_MISMATCH")
    if preprocessing.get("feature_count") != len(verified_manifest.data["feature_specification"]["features"]):
        raise ValueError("PREPROCESSING_FEATURE_WIDTH_MISMATCH")
    feature_order = verified_manifest.data["feature_specification"]["features"]
    mean, scale = preprocessing.get("mean"), preprocessing.get("scale")
    if (preprocessing.get("feature_order") != feature_order
            or not _is_digest(preprocessing.get("training_feature_fingerprint"))
            or not _is_digest(preprocessing.get("training_partition_fingerprint"))
            or not isinstance(mean, list) or not isinstance(scale, list)
            or len(mean) != len(feature_order) or len(scale) != len(feature_order)
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in mean + scale)
            or any(v <= 0 for v in scale)):
        raise ValueError("PREPROCESSING_ARTIFACT_CONTENT_INVALID")
    if (preprocessing.get("manifest_sha256") != verified_manifest.sha256
            or preprocessing.get("dataset_manifest_sha256") != identity["dataset_manifest_sha256"]
            or preprocessing.get("feature_version") != identity["feature_version"]
            or preprocessing.get("market") != identity["market"]
            or preprocessing.get("code_commit") != lineage["code_commit"]
            or preprocessing.get("unique_training_observation_count", 0) < 1):
        raise ValueError("PREPROCESSING_PROVENANCE_MISMATCH")
    if lineage["training_window"] != identity["training_window"] or lineage["validation_window"] != identity["validation_window"]:
        raise ValueError("ARTIFACT_PARTITION_LINEAGE_MISMATCH")
    if (lineage["training_partition_fingerprint"] != model.training_partition_fingerprint_
            or lineage["validation_partition_fingerprint"] != model.validation_partition_fingerprint_):
        raise ValueError("ARTIFACT_PARTITION_FINGERPRINT_MISMATCH")
    weights = model.state()
    preprocessing_hash = canonical_hash(preprocessing)
    if (preprocessing_hash != model.preprocessing_sha256_
            or model.seed != seed):
        raise ValueError("MODEL_PREPROCESSING_OR_SEED_BINDING_MISMATCH")
    weights_hash = canonical_hash(weights)
    chain = {
        "raw_archive_sha256": identity["raw_archive_sha256"],
        "dataset_manifest_sha256": identity["dataset_manifest_sha256"],
        "feature_registry_sha256": identity["feature_registry_sha256"],
        "target_spec_sha256": identity["target_spec_sha256"],
        "manifest_sha256": identity["manifest_sha256"],
        "preprocessing_sha256": preprocessing_hash,
        "training_partition_fingerprint": model.training_partition_fingerprint_,
        "validation_partition_fingerprint": model.validation_partition_fingerprint_,
        "model_weights_sha256": weights_hash,
        "code_commit": lineage["code_commit"],
        "calibration_sha256": lineage.get("calibration_sha256"),
        "result_sha256": lineage.get("result_sha256"),
    }
    verify_provenance_chain(chain, allow_pending_final=True)
    payload = {
        "schema_version": ARTIFACT_SCHEMA,
        "model_id": lineage.get("model_id", f"A2-seed-{seed}"),
        **identity,
        "raw_archive_sha256": lineage["raw_archive_sha256"],
        "dataset_sha256": lineage["dataset_sha256"],
        "training_window": dict(identity["training_window"]),
        "validation_window": dict(identity["validation_window"]),
        "preprocessing": dict(preprocessing),
        "preprocessing_sha256": preprocessing_hash,
        "training_partition_fingerprint": model.training_partition_fingerprint_,
        "validation_partition_fingerprint": model.validation_partition_fingerprint_,
        "weights": weights,
        "weights_sha256": weights_hash,
        "calibration_sha256": chain["calibration_sha256"],
        "provenance_chain": chain,
        "parameter_count": model.parameter_count,
        "code_commit": lineage["code_commit"],
        "dependency_versions": dict(lineage["dependency_versions"]),
        "training_summary": {"epochs_run": int(model.trained_epochs),
                             "best_validation_loss": model.best_validation_loss},
        "trading_authority": False,
        "oos_scoring_performed": False,
    }
    payload["artifact_sha256"] = canonical_hash(payload, excluded_key="artifact_sha256")
    return payload


def verify_provenance_chain(chain: dict, *, allow_pending_final: bool = False) -> None:
    required = ("raw_archive_sha256", "dataset_manifest_sha256", "feature_registry_sha256",
                "target_spec_sha256", "manifest_sha256", "preprocessing_sha256",
                "model_weights_sha256", "calibration_sha256", "result_sha256")
    if any(key not in chain for key in required):
        raise ValueError("PROVENANCE_CHAIN_INCOMPLETE")
    for key in required[:7]:
        if not _is_digest(chain[key]):
            raise ValueError("PROVENANCE_HASH_INVALID:" + key)
    for key in ("calibration_sha256", "result_sha256"):
        if chain[key] is None and allow_pending_final:
            continue
        if not _is_digest(chain[key]):
            raise ValueError("PROVENANCE_HASH_INVALID:" + key)


def save_artifact(path: str | Path, artifact: dict) -> str:
    """Flush a same-volume temp file then atomically link without replacement."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = (json.dumps(artifact, sort_keys=True, indent=2) + "\n").encode("utf-8")
    expected_file_hash = hashlib.sha256(serialized).hexdigest()
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp",
                                          dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise FileExistsError("IMMUTABLE_ARTIFACT_ALREADY_EXISTS") from exc
        actual = sha256_file(destination)
        if actual != expected_file_hash:
            destination.unlink(missing_ok=True)
            raise OSError("ARTIFACT_POST_WRITE_HASH_MISMATCH")
        return actual
    finally:
        temporary.unlink(missing_ok=True)


def load_artifact(path: str | Path, *, verified_manifest: VerifiedManifest) -> dict:
    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    if not is_verified_manifest(verified_manifest):
        raise ValueError("MANIFEST_NOT_VERIFIED")
    if artifact.get("schema_version") != ARTIFACT_SCHEMA:
        raise ValueError("ARTIFACT_SCHEMA_MISMATCH")
    if canonical_hash(artifact["weights"]) != artifact.get("weights_sha256"):
        raise ValueError("ARTIFACT_WEIGHTS_CORRUPT")
    if canonical_hash(artifact["preprocessing"]) != artifact.get("preprocessing_sha256"):
        raise ValueError("ARTIFACT_PREPROCESSING_CORRUPT")
    if canonical_hash(artifact, excluded_key="artifact_sha256") != artifact.get("artifact_sha256"):
        raise ValueError("ARTIFACT_CONTENT_CORRUPT")
    expected = _expected_artifact_identity(verified_manifest, int(artifact.get("random_seed", -1)),
        market=str(artifact.get("market", "")), horizon_minutes=int(artifact.get("horizon_minutes", -1)))
    if any(artifact.get(key) != value for key, value in expected.items()):
        raise ValueError("ARTIFACT_MANIFEST_BINDING_MISMATCH")
    if artifact.get("dataset_sha256") != expected["dataset_manifest_sha256"]:
        raise ValueError("ARTIFACT_DATASET_BINDING_MISMATCH")
    if artifact.get("training_window") != expected["training_window"] or artifact.get("validation_window") != expected["validation_window"]:
        raise ValueError("ARTIFACT_PARTITION_BINDING_MISMATCH")
    preprocessing = artifact["preprocessing"]
    feature_order = verified_manifest.data["feature_specification"]["features"]
    mean, scale = preprocessing.get("mean"), preprocessing.get("scale")
    if (preprocessing.get("fit_partition") != "TRAIN"
            or preprocessing.get("manifest_sha256") != verified_manifest.sha256
            or preprocessing.get("dataset_manifest_sha256") != expected["dataset_manifest_sha256"]
            or preprocessing.get("feature_version") != expected["feature_version"]
            or preprocessing.get("feature_order") != feature_order
            or preprocessing.get("market") != expected["market"]
            or not _is_digest(preprocessing.get("training_feature_fingerprint"))
            or not _is_digest(preprocessing.get("training_partition_fingerprint"))
            or not isinstance(mean, list) or not isinstance(scale, list)
            or len(mean) != len(feature_order) or len(scale) != len(feature_order)
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in mean + scale)
            or any(v <= 0 for v in scale)):
        raise ValueError("ARTIFACT_PREPROCESSING_PROVENANCE_MISMATCH")
    if (not _is_digest(artifact.get("training_partition_fingerprint"))
            or not _is_digest(artifact.get("validation_partition_fingerprint"))
            or artifact.get("training_partition_fingerprint") != artifact.get("provenance_chain", {}).get("training_partition_fingerprint")
            or artifact.get("validation_partition_fingerprint") != artifact.get("provenance_chain", {}).get("validation_partition_fingerprint")):
        raise ValueError("ARTIFACT_PARTITION_FINGERPRINT_MISMATCH")
    if not _is_digest(artifact.get("code_commit"), lengths=(40, 64)):
        raise ValueError("ARTIFACT_CODE_COMMIT_INVALID")
    if (preprocessing.get("code_commit") != artifact.get("code_commit")
            or not _is_digest(preprocessing.get("code_commit"), lengths=(40, 64))):
        raise ValueError("ARTIFACT_PREPROCESSING_CODE_BINDING_MISMATCH")
    if not isinstance(artifact.get("dependency_versions"), dict) or not artifact["dependency_versions"]:
        raise ValueError("ARTIFACT_DEPENDENCY_LINEAGE_MISSING")
    if (artifact.get("parameter_count") != expected_parameter_count(len(feature_order))
            or set(artifact["weights"]) == set()):
        raise ValueError("ARTIFACT_MODEL_CONTENT_MISMATCH")
    from .model import CausalTemporalConv
    template = CausalTemporalConv(verified_manifest, seed=int(artifact["random_seed"]))
    if set(artifact["weights"]) != set(template.params):
        raise ValueError("ARTIFACT_MODEL_PARAMETER_SET_MISMATCH")
    for name, shape in ((key, value.shape) for key, value in template.params.items()):
        values = artifact["weights"].get(name)
        array = np.asarray(values, dtype=float)
        if array.shape != shape or not np.isfinite(array).all():
            raise ValueError("ARTIFACT_MODEL_PARAMETER_SHAPE_OR_VALUE_INVALID")
    summary = artifact.get("training_summary")
    if (not isinstance(summary, dict) or not isinstance(summary.get("epochs_run"), int)
            or summary["epochs_run"] < 1
            or not isinstance(summary.get("best_validation_loss"), (int, float))
            or not math.isfinite(summary["best_validation_loss"])):
        raise ValueError("ARTIFACT_TRAINING_SUMMARY_INVALID")
    verify_provenance_chain(artifact.get("provenance_chain", {}), allow_pending_final=True)
    if artifact.get("provenance_chain", {}).get("manifest_sha256") != verified_manifest.sha256:
        raise ValueError("PROVENANCE_MANIFEST_BINDING_MISMATCH")
    chain = artifact["provenance_chain"]
    expected_chain = {"raw_archive_sha256": expected["raw_archive_sha256"],
        "dataset_manifest_sha256": expected["dataset_manifest_sha256"],
        "feature_registry_sha256": expected["feature_registry_sha256"],
        "target_spec_sha256": expected["target_spec_sha256"],
        "manifest_sha256": verified_manifest.sha256,
        "preprocessing_sha256": artifact["preprocessing_sha256"],
        "code_commit": artifact["code_commit"],
        "model_weights_sha256": artifact["weights_sha256"],
        "calibration_sha256": artifact.get("calibration_sha256"),
        "result_sha256": None,
        "training_partition_fingerprint": artifact["training_partition_fingerprint"],
        "validation_partition_fingerprint": artifact["validation_partition_fingerprint"]}
    if chain != expected_chain:
        raise ValueError("ARTIFACT_PROVENANCE_CONTENT_MISMATCH")
    if artifact.get("trading_authority") is not False or artifact.get("oos_scoring_performed") is not False:
        raise ValueError("UNAUTHORIZED_OR_PROTECTED_ARTIFACT")
    return artifact
