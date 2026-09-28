"""Engineering-only result provenance envelope; protected evaluation is not implemented."""
from __future__ import annotations

import hashlib
from typing import Mapping

from .calibration import verify_calibration_artifact
from .data_integrity import AuthorizedSplit, validate_authorized_split
from .manifest import VerifiedManifest, canonical_bytes, canonical_hash, is_verified_manifest

RESULT_ARTIFACT_SCHEMA = "bot2-phase5c-v3-engineering-result-artifact-v1"
_HEADS = {"direction", "volatility", "structure"}


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def create_engineering_result_artifact(*, verified_manifest: VerifiedManifest,
        split: AuthorizedSplit, model_artifact: Mapping, head: str,
        fixture_sha256: str, metrics_configuration: Mapping,
        calibration_artifact: Mapping | None = None,
        ablation_contract: Mapping | None = None,
        shuffled_control_artifact: Mapping | None = None) -> dict:
    """Create provenance for a synthetic fixture only; no prediction or metric fields accepted."""
    if not is_verified_manifest(verified_manifest) or not split.valid():
        raise ValueError("RESULT_VERIFIED_CONTEXT_REQUIRED")
    validate_authorized_split(split, verified_manifest)
    manifest = verified_manifest.data
    expected_commit = verified_manifest.pin["review_candidate_commit"]
    model_sha = model_artifact.get("artifact_sha256")
    if (not _digest(model_sha)
            or model_sha != canonical_hash(dict(model_artifact), excluded_key="artifact_sha256")
            or model_artifact.get("manifest_sha256") != verified_manifest.sha256
            or model_artifact.get("code_commit") != expected_commit
            or model_artifact.get("preprocessing_sha256") != split.preprocessing_sha256
            or not isinstance(model_artifact.get("weights"), Mapping)
            or model_artifact.get("weights_sha256") != canonical_hash(model_artifact["weights"])
            or model_artifact.get("trading_authority") is not False
            or model_artifact.get("oos_scoring_performed") is not False
            or model_artifact.get("dataset_manifest_sha256") != split.dataset_manifest_sha256
            or model_artifact.get("market") != split.market
            or model_artifact.get("horizon_minutes") != split.horizon_minutes):
        raise ValueError("RESULT_MODEL_OR_PREPROCESSING_LINEAGE_MISMATCH")
    if head not in _HEADS or head not in manifest["target_specification"]["class_indices"]:
        raise ValueError("RESULT_HEAD_NOT_IN_MANIFEST")
    if not _digest(fixture_sha256):
        raise ValueError("RESULT_FIXTURE_DIGEST_INVALID")
    if dict(metrics_configuration) != manifest["metrics"]:
        raise ValueError("RESULT_METRIC_CONFIGURATION_MISMATCH")

    calibration_sha = None
    if calibration_artifact is not None:
        verify_calibration_artifact(calibration_artifact, split=split,
            verified_manifest=verified_manifest, model_artifact=model_artifact,
            expected_head=head)
        if calibration_artifact.get("head") != head:
            raise ValueError("RESULT_CALIBRATION_HEAD_MISMATCH")
        calibration_sha = calibration_artifact["calibration_sha256"]

    ablation_identity = None
    if ablation_contract is not None:
        from .experiment_controls import verify_ablation_contract
        verify_ablation_contract(ablation_contract, verified_manifest)
        ablation_identity = {"id": ablation_contract["ablation_id"],
                             "sha256": ablation_contract["ablation_sha256"]}

    shuffle_identity = None
    if shuffled_control_artifact is not None:
        control = dict(shuffled_control_artifact)
        digest = control.pop("control_sha256", None)
        if (digest != _sha(control)
                or control.get("manifest_sha256") != verified_manifest.sha256
                or control.get("implementation_candidate_commit") != expected_commit
                or control.get("predictions_generated") is not False
                or control.get("metrics_generated") is not False):
            raise ValueError("RESULT_SHUFFLE_CONTROL_LINEAGE_MISMATCH")
        shuffle_identity = {"id": control.get("candidate_id"),
                            "sha256": digest,
                            "assignment_sha256": control.get("assignment_sha256")}

    content = {"artifact_type": "ENGINEERING_FIXTURE", "fixture_sha256": fixture_sha256}
    artifact = {
        "schema_version": RESULT_ARTIFACT_SCHEMA,
        "protocol_version": manifest["schema_version"],
        "manifest_sha256": verified_manifest.sha256,
        "implementation_candidate_commit": expected_commit,
        "dataset_identity": manifest["source_dataset"]["archive"],
        "dataset_manifest_sha256": split.dataset_manifest_sha256,
        "partition": split.validation.partition,
        "partition_fingerprint": split.partition_fingerprints[split.validation.partition],
        "model_artifact_sha256": model_sha,
        "preprocessing_artifact_sha256": model_artifact["preprocessing_sha256"],
        "calibration_artifact_sha256": calibration_sha,
        "instrument": split.market,
        "horizon_minutes": split.horizon_minutes,
        "prediction_head": head,
        "seed": model_artifact["random_seed"],
        "feature_version": manifest["feature_specification"]["schema_version"],
        "target_version": manifest["target_specification"]["version"],
        "ablation_identity": ablation_identity,
        "shuffled_control_identity": shuffle_identity,
        "metrics_configuration_sha256": canonical_hash(dict(metrics_configuration)),
        "result_content": content,
        "result_content_sha256": _sha(content),
        "protected_models_scored": [],
        "oos_scoring_performed": False,
        "trading_authority": "NONE",
    }
    artifact["result_artifact_sha256"] = canonical_hash(artifact, excluded_key="result_artifact_sha256")
    return artifact


def verify_engineering_result_artifact(artifact: Mapping, *,
        verified_manifest: VerifiedManifest, split: AuthorizedSplit,
        model_artifact: Mapping, calibration_artifact: Mapping | None = None,
        ablation_contract: Mapping | None = None,
        shuffled_control_artifact: Mapping | None = None) -> None:
    """Reconcile all result metadata and content digests; reject any scoring payload."""
    value = dict(artifact)
    digest = value.pop("result_artifact_sha256", None)
    if (digest != canonical_hash(value, excluded_key="result_artifact_sha256")
            or artifact.get("schema_version") != RESULT_ARTIFACT_SCHEMA
            or artifact.get("result_content") != {
                "artifact_type": "ENGINEERING_FIXTURE",
                "fixture_sha256": artifact.get("result_content", {}).get("fixture_sha256")}
            or not _digest(artifact.get("result_content", {}).get("fixture_sha256"))
            or artifact.get("result_content_sha256") != _sha(artifact["result_content"])
            or artifact.get("protected_models_scored") != []
            or artifact.get("oos_scoring_performed") is not False
            or artifact.get("trading_authority") != "NONE"):
        raise ValueError("RESULT_ARTIFACT_CONTENT_CORRUPT_OR_UNAUTHORIZED")
    expected = create_engineering_result_artifact(verified_manifest=verified_manifest,
        split=split, model_artifact=model_artifact,
        head=str(artifact.get("prediction_head", "")),
        fixture_sha256=artifact["result_content"]["fixture_sha256"],
        metrics_configuration=verified_manifest.data["metrics"],
        calibration_artifact=calibration_artifact,
        ablation_contract=ablation_contract,
        shuffled_control_artifact=shuffled_control_artifact)
    if dict(expected) != dict(artifact):
        raise ValueError("RESULT_ARTIFACT_PROVENANCE_MISMATCH")
