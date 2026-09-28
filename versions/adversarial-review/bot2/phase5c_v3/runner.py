"""Strict Phase 5C v3 dry-run/preflight. This module cannot score models."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from .manifest import (V2_CANONICAL_SHA256, V2_COMMIT, canonical_hash,
                       load_verified_manifest, sha256_file, verify_git_binding)
from .model import (ARCHITECTURE_VERSION, DILATIONS, HEADS, KERNEL_WIDTH,
                    CausalTemporalConv, expected_parameter_count)

RESULT_DIRECTORY = Path("outputs/bot2_phase5c_v3/results")


def _record(checks: list[dict], check_id: str, passed: bool, reason: str,
            details: Any = None) -> None:
    item = {"check": check_id, "status": "PASS" if passed else "FAIL", "reason_code": reason}
    if details is not None:
        item["details"] = details
    checks.append(item)


def _normalized_source_sha256(path: str | Path) -> str:
    """Hash source after CRLF->LF normalization matching frozen Git blobs."""
    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _verify_archive_audit_report(report_path: Path, dataset_root: Path,
                                 expected_fingerprints: dict[str, str]) -> tuple[bool, str, dict]:
    """Verify every archived file listed in the frozen final audit report."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        entries = report["artifact_hashes"]
        expected_tree = expected_fingerprints["archive_tree_sha256"]
        if report.get("state") != "FINAL_ES_NQ_ARCHIVE_AUDIT_PASS" or report.get("archive_tree_sha256") != expected_tree:
            return False, "ARCHIVE_AUDIT_REPORT_OR_TREE_MISMATCH", {}
        root = dataset_root.resolve()
        normalized = []
        seen: set[str] = set()
        for entry in entries:
            rel = Path(entry["path"])
            if rel.is_absolute() or ".." in rel.parts or not rel.as_posix().startswith("data/backtests/es_nq_pass_b_archive_3/"):
                return False, "ARCHIVE_AUDIT_PATH_INVALID", {"path": entry.get("path")}
            path = (root.parent.parent.parent / rel).resolve()
            if not path.is_relative_to(root.parent.parent.parent.resolve()) or not path.is_file():
                return False, "ARCHIVE_AUDIT_FILE_MISSING_OR_ESCAPED", {"path": entry["path"]}
            if entry["path"] in seen:
                return False, "ARCHIVE_AUDIT_DUPLICATE_PATH", {"path": entry["path"]}
            seen.add(entry["path"])
            if path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
                return False, "ARCHIVE_PAYLOAD_HASH_OR_SIZE_MISMATCH", {"path": entry["path"]}
            normalized.append(entry)
        tree_bytes = (json.dumps(sorted(normalized, key=lambda item: item["path"]),
                                 sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        tree_hash = hashlib.sha256(tree_bytes).hexdigest()
        if tree_hash != expected_tree:
            return False, "ARCHIVE_TREE_FINGERPRINT_MISMATCH", {"actual": tree_hash}
        return True, "ARCHIVE_PAYLOAD_HASHES_VALID", {"file_count": len(seen), "archive_tree_sha256": tree_hash}
    except Exception as exc:
        return False, "ARCHIVE_AUDIT_UNAVAILABLE", {"error": type(exc).__name__}


def _frozen_control_checks(manifest: dict) -> list[tuple[str, bool, str]]:
    """Check frozen controls without reading or scoring OOS labels."""
    calibration = manifest.get("calibration", {})
    calibration_ok = (calibration.get("fit_partition") == "VALIDATION only"
                      and calibration.get("oos_fit") is False
                      and calibration.get("method") == "single scalar temperature scaling per root/head/horizon")
    uncertainty = manifest.get("uncertainty_abstention", {})
    uncertainty_ok = (uncertainty.get("threshold_selection_partition") == "VALIDATION only"
                      and uncertainty.get("oos_or_pnl_optimization") is False)
    shuffle = manifest.get("shuffled_label_control", {})
    shuffle_ok = (shuffle.get("partition_shuffled") == "TRAIN only"
                  and shuffle.get("evaluation_labels") == "Validation/test/OOS labels unchanged"
                  and bool(shuffle.get("seeds")))
    ablations = manifest.get("feature_ablations", [])
    expected_ablations = {"ALL", "MINUS_CROSS_MARKET", "MINUS_VWAP", "MINUS_VOLUME",
                          "MINUS_VOLATILITY", "MINUS_SESSION_TIME"}
    ablation_ids = {item.get("id") for item in ablations if isinstance(item, dict)}
    ablation_ok = ablation_ids == expected_ablations
    metrics = manifest.get("metrics", {})
    metrics_ok = (metrics.get("primary") == ["macro_f1", "categorical_log_loss"]
                  and metrics.get("accuracy") == "descriptive only, not primary")
    policy = manifest.get("implementation_commit_policy", "")
    lineage_ok = "exact full Git commit" in policy and "clean working tree" in policy
    return [
        ("calibration_policy", calibration_ok, "VALIDATION_ONLY_CALIBRATION_PINNED" if calibration_ok else "CALIBRATION_POLICY_MISMATCH"),
        ("uncertainty_abstention_policy", uncertainty_ok, "VALIDATION_ONLY_ABSTENTION_PINNED" if uncertainty_ok else "ABSTENTION_POLICY_MISMATCH"),
        ("shuffled_label_control", shuffle_ok, "TRAIN_ONLY_SHUFFLE_CONTROL_PINNED" if shuffle_ok else "SHUFFLE_CONTROL_MISMATCH"),
        ("feature_ablations", ablation_ok, "FROZEN_ABLATIONS_PRESENT" if ablation_ok else "ABLATION_SET_MISMATCH"),
        ("primary_metrics", metrics_ok, "FROZEN_PRIMARY_METRICS_PRESENT" if metrics_ok else "PRIMARY_METRIC_POLICY_MISMATCH"),
        ("artifact_lineage_policy", lineage_ok, "FULL_COMMIT_LINEAGE_REQUIRED" if lineage_ok else "ARTIFACT_LINEAGE_POLICY_MISMATCH"),
    ]


def run_preflight(repo_root: str | Path, dataset_root: str | Path,
                  *, output_directory: str | Path | None = None,
                  external_anchor_path: str | Path | None = None) -> dict:
    root = Path(repo_root).resolve()
    data_root = Path(dataset_root).resolve()
    checks: list[dict] = []
    manifest_path = root / "config" / "bot2_phase5c_experiment_manifest_v3.json"
    try:
        verified = load_verified_manifest(manifest_path, external_anchor_path=external_anchor_path)
        manifest, manifest_hash = verified.data, verified.sha256
        _record(checks, "v3_manifest", True, "EXTERNAL_ANCHOR_PATH_AND_MANIFEST_HASH_VALID",
                {"manifest_sha256": manifest_hash, "anchor_file_sha256": verified.pin_sha256,
                 "anchor_path": verified.anchor_path,
                 "repository_copy_is_not_anchor": True,
                 "content_integrity": "VERIFIED_AGAINST_SUPPLIED_DIGEST",
                 "signature_status": verified.anchor_signature_status,
                 "independent_custody": "NOT_CRYPTOGRAPHICALLY_PROVEN"})
    except Exception as exc:
        manifest, manifest_hash = {}, None
        _record(checks, "v3_manifest", False, str(exc).split(":")[0])
        return _result(checks, None, None)

    v2_path = root / "config" / "bot2_phase5c_experiment_manifest_v2.json"
    try:
        v2 = json.loads(v2_path.read_text(encoding="utf-8"))
        valid_v2 = canonical_hash(v2) == V2_CANONICAL_SHA256 and v2.get("manifest_sha256") == V2_CANONICAL_SHA256
        _record(checks, "v2_preserved", valid_v2, "V2_CANONICAL_HASH_VALID" if valid_v2 else "V2_CANONICAL_HASH_MISMATCH", V2_CANONICAL_SHA256)
    except Exception:
        v2 = {}
        _record(checks, "v2_preserved", False, "V2_MANIFEST_UNAVAILABLE")

    try:
        git_binding = verify_git_binding(
            root, expected_commit=verified.pin["review_candidate_commit"])
        _record(checks, "implementation_commit_binding", True,
                "EXACT_REVIEW_CANDIDATE_COMMIT_AND_CLEAN_TREE_VALID", git_binding)
    except Exception as exc:
        git_binding = {}
        _record(checks, "implementation_commit_binding", False,
                str(exc).split(":")[0] if str(exc) else "GIT_BINDING_UNAVAILABLE")

    source_path = root / "outputs" / "bot2_phase5b" / "real_es_nq_research_dataset_manifest_v2.json"
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source_hash = canonical_hash(source)
        source_ok = source_hash == manifest["source_dataset_manifest_sha256"] == source.get("manifest_sha256")
        _record(checks, "dataset_manifest", source_ok, "DATASET_MANIFEST_HASH_VALID" if source_ok else "DATASET_MANIFEST_HASH_MISMATCH", source_hash)
    except Exception:
        source = {}
        _record(checks, "dataset_manifest", False, "DATASET_MANIFEST_UNAVAILABLE")

    eligibility_path = root / manifest.get("data_eligibility_report", "")
    try:
        eligibility_hash = sha256_file(eligibility_path)
        eligibility = json.loads(eligibility_path.read_text(encoding="utf-8"))
        eligibility_ok = eligibility_hash == manifest["data_eligibility_report_sha256"] and eligibility.get("dataset_manifest_sha256") == manifest["source_dataset_manifest_sha256"]
        _record(checks, "eligibility_report", eligibility_ok, "ELIGIBILITY_HASH_VALID" if eligibility_ok else "ELIGIBILITY_HASH_OR_DATASET_MISMATCH", eligibility_hash)
    except Exception:
        eligibility = {}
        _record(checks, "eligibility_report", False, "ELIGIBILITY_REPORT_UNAVAILABLE")

    feature_path = root / manifest["feature_specification"]["registry_path"]
    feature_ok = False
    try:
        # v2 pins LF Git-blob bytes. Normalize checkout line endings so
        # core.autocrlf cannot invalidate an unchanged registry.
        feature_hash = _normalized_source_sha256(feature_path)
        feature_ok = feature_hash == manifest["feature_specification"]["registry_sha256"]
        _record(checks, "feature_registry", feature_ok, "FEATURE_VERSION_HASH_VALID" if feature_ok else "FEATURE_VERSION_HASH_MISMATCH", feature_hash)
    except Exception:
        _record(checks, "feature_registry", False, "FEATURE_REGISTRY_UNAVAILABLE")

    try:
        from bot2.features_labels.targets_v3 import TARGET_SPEC
        from bot2.features_labels.contracts import config_hash
        target_hash = config_hash(TARGET_SPEC)
        target_ok = (TARGET_SPEC["version"] == manifest["target_specification"]["version"]
                     and target_hash == manifest["target_specification"]["spec_sha256"])
        _record(checks, "target_specification", target_ok, "TARGET_VERSION_HASH_VALID" if target_ok else "TARGET_VERSION_HASH_MISMATCH", target_hash)
    except Exception:
        _record(checks, "target_specification", False, "TARGET_SPECIFICATION_UNAVAILABLE")

    data_available = True
    archive_details = {}
    for market in ("ES", "NQ"):
        market_dir = data_root / market / "normalized"
        files = list(market_dir.glob("*.jsonl")) if market_dir.is_dir() else []
        expected_contracts = sorted(source.get("markets", {}).get(market, {}).get("contract_inventory", {}).keys())
        market_rows = source.get("markets", {}).get(market, {}).get("rows")
        ok = bool(files) and bool(expected_contracts) and isinstance(market_rows, int) and market_rows > 0
        archive_details[market] = {"normalized_file_count": len(files), "expected_contract_count": len(expected_contracts), "manifest_rows": market_rows}
        data_available = data_available and ok
    _record(checks, "dataset_payload", data_available,
            "DATASET_PAYLOAD_PRESENT" if data_available else "DATASET_PAYLOAD_MISSING_OR_INCOMPLETE", archive_details)

    report_path = data_root.parents[2] / "outputs" / "archive_audits" / "es_nq_pass_b_final_audit.json"
    # The final archive audit pins a combined archive-tree digest. The frozen
    # source manifest repeats that digest under each root's source provenance.
    fingerprints = {"archive_tree_sha256": source.get("markets", {}).get("ES", {}).get("source_archive_sha256")}
    fingerprints_consistent = (fingerprints["archive_tree_sha256"] is not None
                               and fingerprints["archive_tree_sha256"] == source.get("markets", {}).get("NQ", {}).get("source_archive_sha256"))
    archive_ok, archive_reason, archive_details = _verify_archive_audit_report(report_path, data_root, fingerprints)
    archive_ok = archive_ok and fingerprints_consistent
    if not fingerprints_consistent:
        archive_reason = "FROZEN_SOURCE_ARCHIVE_FINGERPRINT_MISMATCH"
    _record(checks, "dataset_archive_integrity", archive_ok, archive_reason, archive_details)

    seq = manifest["feature_specification"]["sequence_length"]
    cadence = manifest["feature_specification"]["sequence_cadence_seconds"]
    target_seq_counts = eligibility.get("markets", {})
    sequence_counts_ok = seq == 8 and cadence == 60 and all(
        target_seq_counts.get(root_name, {}).get("sequence_windows_by_horizon_length_8") for root_name in ("ES", "NQ"))
    _record(checks, "cadence_and_sequences", sequence_counts_ok,
            "PINNED_CADENCE_AND_SEQUENCE_EVIDENCE_VALID" if sequence_counts_ok else "CADENCE_OR_SEQUENCE_EVIDENCE_INVALID",
            {"sequence_length": seq, "cadence_seconds": cadence})

    expected_contracts = manifest.get("source_dataset", {}).get("contracts", {})
    source_contracts = {m: sorted(source.get("markets", {}).get(m, {}).get("contract_inventory", {}).keys()) for m in ("ES", "NQ")}
    contract_ok = all(sorted(expected_contracts.get(m, [])) == source_contracts[m] for m in ("ES", "NQ"))
    _record(checks, "instrument_session_identity", contract_ok,
            "EXACT_CONTRACT_INVENTORY_MATCH" if contract_ok else "CONTRACT_INVENTORY_MISMATCH",
            source_contracts)

    sync_ok = bool(eligibility.get("es_nq_exact_alignment", {}).get("alignment_requires_same_session_and_exact_timestamp")) and bool(eligibility.get("es_nq_exact_alignment", {}).get("no_forward_fill"))
    _record(checks, "es_nq_alignment", sync_ok,
            "EXACT_SESSION_TIMESTAMP_ALIGNMENT_PINNED" if sync_ok else "CROSS_MARKET_ALIGNMENT_INVALID")

    windows = manifest.get("chronological_partitions_inclusive", {})
    split_ok = (windows.get("TRAIN") == ["2025-06-02", "2025-12-31"]
                and windows.get("VALIDATION_AND_CALIBRATION") == ["2026-01-01", "2026-02-27"]
                and windows.get("OOS_TEST") == ["2026-03-01", "2026-08-26"])
    _record(checks, "temporal_splits", split_ok, "FROZEN_SPLITS_MATCH" if split_ok else "TEMPORAL_WINDOW_MISMATCH", windows)

    purge = manifest.get("purge_embargo", {})
    purge_ok = (purge.get("max_label_horizon_minutes") == 30
                and purge.get("max_feature_lookback_minutes") == 30
                and purge.get("purge_minutes") == 30
                and purge.get("embargo_minutes") == 30
                and purge.get("identical_evaluation_intersection") is True
                and "< next partition's first timestamp minus 30 elapsed minutes" in purge.get("rule", "")
                and "Exclude first 30 elapsed minutes" in purge.get("rule_embargo", ""))
    _record(checks, "purge_embargo", purge_ok, "FROZEN_PURGE_EMBARGO_PRESENT" if purge_ok else "PURGE_OR_EMBARGO_MISSING_OR_CHANGED", purge)

    arch = manifest.get("architectures", {}).get("A2_LEARNED_CAUSAL_TCN", {})
    try:
        tcn = CausalTemporalConv(verified, seed=manifest["random_seeds"][0])
    except Exception as exc:
        tcn = None
        arch_ok = False
        arch_reason = "A2_MANIFEST_CONFIGURATION_REJECTED"
    else:
        arch_ok = (arch.get("architecture_version") == ARCHITECTURE_VERSION
                   and [block.get("dilation") for block in arch.get("blocks", [])] == list(DILATIONS)
                   and all(block.get("kernel_width") == KERNEL_WIDTH and block.get("padding") == "left-only-zero" for block in arch.get("blocks", []))
                   and tcn.parameter_count == expected_parameter_count(24)
                   and tcn.receptive_field == arch.get("receptive_field_timesteps"))
        arch_reason = "FROZEN_TCN_AVAILABLE" if arch_ok else "A2_ARCHITECTURE_UNAVAILABLE_OR_MISMATCH"
    _record(checks, "a2_architecture", arch_ok, arch_reason,
            {"parameter_count": tcn.parameter_count if tcn else None,
             "receptive_field": tcn.receptive_field if tcn else None})

    train_cfg = manifest.get("a2_training", {})
    train_ok = (train_cfg.get("optimizer") == "Adam" and train_cfg.get("learning_rate") == 0.001
                and train_cfg.get("batch_size") == 256 and train_cfg.get("max_epochs") == 50
                and train_cfg.get("batch_order") == "chronological contiguous batches; no minibatch shuffle"
                and train_cfg.get("early_stopping", {}).get("patience") == 5
                and train_cfg.get("early_stopping", {}).get("partition") == "VALIDATION_AND_CALIBRATION"
                and train_cfg.get("gradient_clipping", {}).get("maximum_norm") == 1.0
                and train_cfg.get("loss", {}).get("head_weights") == {"direction": 1.0, "volatility": 1.0, "structure": 1.0}
                and train_cfg.get("initialization", {}).get("rng") == "numpy.random.default_rng(seed)"
                and train_cfg.get("determinism", "").startswith("Fixed seed"))
    _record(checks, "training_configuration", train_ok, "FROZEN_TRAINING_CONFIG_VALID" if train_ok else "TRAINING_CONFIG_MISMATCH")

    seeds_ok = manifest.get("random_seeds") == [1, 2, 3]
    _record(checks, "seeds", seeds_ok, "FROZEN_SEEDS_VALID" if seeds_ok else "SEED_SET_MISMATCH")
    protected_closed = manifest.get("evaluation_permitted") is False and manifest.get("oos_model_scoring_performed") is False and manifest.get("trading_authority") is False
    _record(checks, "protected_scoring_gate", protected_closed, "OOS_SCORING_DISABLED" if protected_closed else "PROTECTED_GATE_MUST_REMAIN_CLOSED")

    for check_id, passed, reason in _frozen_control_checks(manifest):
        _record(checks, check_id, passed, reason)

    output_dir = (root / RESULT_DIRECTORY if output_directory is None else Path(output_directory).resolve())
    no_overwrite = not output_dir.exists() or (output_dir.is_dir() and not any(output_dir.iterdir()))
    _record(checks, "output_destination", no_overwrite, "APPEND_ONLY_DESTINATION_AVAILABLE" if no_overwrite else "OUTPUT_DESTINATION_NOT_EMPTY", str(output_dir))
    return _result(checks, manifest_hash, str(output_dir))


def _result(checks: list[dict], manifest_hash: str | None, output_directory: str | None) -> dict:
    passed = all(item["status"] == "PASS" for item in checks)
    return {
        "schema_version": "bot2-phase5c-v3-preflight-result-v1",
        "status": "PREFLIGHT_READY_NO_SCORING" if passed else "PREFLIGHT_BLOCKED",
        "manifest_sha256": manifest_hash,
        "checks": checks,
        "output_directory": output_directory,
        "models_scored": [],
        "oos_performance_scores_produced": 0,
        "trading_authority": False,
    }
