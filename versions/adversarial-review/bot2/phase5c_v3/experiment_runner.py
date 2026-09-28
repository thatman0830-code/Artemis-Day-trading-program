"""Manifest-bound Phase 5C experiment runner; Phase 5C-Y is synthetic-only.

This module has no broker, order, network, or protected-dataset read path.
Protected OOS execution is unconditionally denied until a later authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Mapping

import numpy as np

from .calibration import (fit_temperature_calibrator, select_abstention_threshold,
                          verify_abstention_artifact, verify_calibration_artifact)
from .data_integrity import MarketObservation, build_authorized_split, validate_authorized_split
from .experiment_controls import (create_ablation_contract, create_model_input_contract,
    execute_ablation_control, execute_shuffled_label_control, validate_model_input_contract,
    verify_ablation_execution, verify_shuffled_label_control)
from .manifest import (VerifiedManifest, canonical_bytes, canonical_hash,
                       is_verified_manifest, load_verified_manifest, verify_git_binding)
from .experiment_matrix import (derive_walk_forward_windows, expected_cell_ledger,
    common_comparison_record, create_cell_result_artifact,
    reconcile_matrix_dispatch, validate_walk_forward_rows,
    load_cell_result_artifact, transition_cell, evaluate_complete_matrix,
    mark_matrix_dispatched, select_engineering_coverage_cells,
    verify_engineering_coverage, implementation_source_identity)
from .model import CausalTemporalConv, HEADS, TrainingOnlyStandardizer

RUNNER_SCHEMA = "bot2-phase5c-v3-experiment-runner-v1"
PREDICTION_SCHEMA = "bot2-phase5c-v3-prediction-contract-v1"
SYNTHETIC_SOURCE = "SYNTHETIC_ENGINEERING_DATASET_V1"
_A0 = ("A0_PREVIOUS_LABEL_PERSISTENCE", "A0_TRAIN_MAJORITY", "A0_TRAIN_TRANSITION_MATRIX")
_NEURAL = ("A1_NUMPY_MULTIHEAD_MLP", "A2_LEARNED_CAUSAL_TCN")


class ExecutionMode(str, Enum):
    PREFLIGHT = "PREFLIGHT"
    SYNTHETIC_VALIDATION = "SYNTHETIC_VALIDATION"
    PROTECTED_OOS = "PROTECTED_OOS"


class Phase5CExecutionError(ValueError):
    """Exception with a stable machine-readable failure code."""
    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class SyntheticDataset:
    source_id: str
    rows_by_partition: Mapping[str, tuple[MarketObservation, ...]]
    seed: int


def _sha(payload: object) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _dispatch_synthetic_cell(cell: Mapping) -> dict:
    """Route one canonical cell without claiming that model computation ran."""
    if not isinstance(cell, Mapping) or not isinstance(cell.get("identity"), Mapping):
        raise Phase5CExecutionError("CELL_IDENTITY_MISMATCH")
    return {"cell_sha256": cell.get("cell_sha256"),
        "identity": dict(cell["identity"]), "status": "DISPATCHED",
        "reason_code": "COMPUTE_NOT_RUN_IN_ORCHESTRATION_VALIDATION"}


def _validate_synthetic_walk_forward_coverage(verified: VerifiedManifest) -> dict:
    """Exercise frozen windows with synthetic rows and actual identity hashes."""
    manifest = _manifest(verified)
    windows = derive_walk_forward_windows(verified)
    roots = tuple(sorted(manifest["source_dataset"]["contracts"]))
    horizons = tuple(manifest["target_specification"]["horizons_minutes"])
    records = []
    for root in roots:
        contract = manifest["source_dataset"]["contracts"][root][0]
        for horizon in horizons:
            for window in windows:
                spans = {"TRAIN": window.train,
                    "VALIDATION_AND_CALIBRATION": window.validation,
                    "OOS_TEST": window.test}
                partitions = {}
                for index, (partition, span) in enumerate(spans.items()):
                    partitions[partition] = _generate_partition(verified, market=root,
                        seed=17000 + len(records) * 3 + index, part=f"{window.window_id}-{partition}",
                        day=span[0], contract=contract, count=72, horizon=horizon)
                checked = validate_walk_forward_rows(verified, root=root,
                    horizon_minutes=horizon, window_id=window.window_id,
                    rows_by_partition=partitions)
                scaler = TrainingOnlyStandardizer().fit_observations(partitions["TRAIN"],
                    market=root, verified_manifest=verified,
                    code_commit=verified.pin["review_candidate_commit"])
                split = build_authorized_split(verified, market=root,
                    horizon_minutes=horizon, partition_rows=partitions,
                    preprocessor=scaler, walk_forward_window_id=window.window_id)
                validate_authorized_split(split, verified)
                if split.partition_fingerprints != checked["partition_fingerprints"]:
                    raise Phase5CExecutionError("WALK_FORWARD_PARTITION_FINGERPRINT_MISMATCH")
                if len(split.validation.x) == 0 or len(split.train.x) == 0:
                    raise Phase5CExecutionError("WALK_FORWARD_SYNTHETIC_ROWS_INSUFFICIENT")
                # Execute causal A0 baselines, aligned to exact authorized
                # validation sequences, for every root × horizon × WF window.
                # OOS remains partition-validated only, never used for fitting.
                baseline_predictions = _a0_predictions(split)
                prediction_row_ids = [_sha({"contract": seq[-1][0],
                    "session_id": seq[-1][1], "exchange_timestamp_utc": seq[-1][2]})
                    for seq in split.validation.sequence_keys]
                if any(len(probs[head]) != len(prediction_row_ids)
                       for probs in baseline_predictions.values() for head in HEADS):
                    raise Phase5CExecutionError("WALK_FORWARD_PREDICTION_ALIGNMENT_FAILED")
                baseline_metrics = {model_id: {head: _metrics(probs[head],
                    split.validation.targets[head]) for head in HEADS}
                    for model_id, probs in baseline_predictions.items()}
                records.append({"root": root, "horizon_minutes": horizon,
                    "window_id": window.window_id,
                    "window_fingerprint": checked["window_fingerprint"],
                    "partition_fingerprints": checked["partition_fingerprints"],
                    "eligible_row_ids_sha256": _sha(checked["eligible_row_ids"]),
                    "eligible_sequence_ids_sha256": _sha(
                        checked["eligible_sequence_observation_ids"]),
                    "excluded_row_ids_sha256": _sha(checked["excluded_row_ids"]),
                    "oos_engineering_row_identity_sha256": _sha(
                        checked["eligible_row_ids"]["OOS_TEST"]),
                    "oos_engineering_row_count": len(checked["eligible_row_ids"]["OOS_TEST"]),
                    "validation_prediction_row_identity_sha256": _sha(prediction_row_ids),
                    "validation_prediction_row_count": len(prediction_row_ids),
                    "baseline_model_ids": sorted(baseline_predictions),
                    "baseline_metrics_by_head": baseline_metrics,
                    "classification": "SYNTHETIC ENGINEERING RESULT"})
    expected = len(roots) * len(horizons) * len(windows)
    if len(records) != expected:
        raise Phase5CExecutionError("WALK_FORWARD_COVERAGE_INCOMPLETE")
    return {"status": "SYNTHETIC_PARTITION_VALIDATION_COMPLETE",
        "classification": "SYNTHETIC ENGINEERING RESULT",
        "expected_combinations": expected, "validated_combinations": len(records),
        "records": records, "protected_models_scored": 0,
        "protected_oos_scores_produced": 0, "trading_authority": "NONE"}


def _orchestrate_synthetic_matrix(verified: VerifiedManifest, *, dispatcher=None) -> dict:
    """Dispatch every manifest-required cell and reconcile all identities."""
    ledger = expected_cell_ledger(verified)
    route = dispatcher or _dispatch_synthetic_cell
    receipts = [route(cell) for cell in ledger["cells"]]
    reconciliation = reconcile_matrix_dispatch(verified, receipts)
    reconciliation["dispatch_mode"] = "SYNTHETIC_ORCHESTRATION_ONLY"
    if not reconciliation["dispatch_reconciled"]:
        raise Phase5CExecutionError("MATRIX_DISPATCH_RECONCILIATION_FAILED")
    if reconciliation["expected_cell_count"] != len(ledger["cells"]):
        raise Phase5CExecutionError("FROZEN_MATRIX_EXPECTED_COUNT_MISMATCH")
    reconciliation["walk_forward_coverage"] = _validate_synthetic_walk_forward_coverage(verified)
    return reconciliation


def execute_synthetic_matrix_cells(verified: VerifiedManifest, *,
        result_directory: str | Path, cell_ids: list[str], executor=None) -> dict:
    """Execute selected frozen cells with immutable results and recoverable ledger.

    All manifest cells are dispatched and reconciled on every invocation, but
    training is limited to the explicit ``cell_ids`` selection. Existing result
    files are verified and can recover a RUNNING ledger cell after interruption.
    No protected data or scoring path is available here.
    """
    if not isinstance(cell_ids, list) or not cell_ids:
        raise Phase5CExecutionError("MATRIX_EXECUTION_CELL_SELECTION_REQUIRED")
    ledger = expected_cell_ledger(verified)
    expected_by_id = {item["cell_sha256"]: item for item in ledger["cells"]}
    if (len(set(cell_ids)) != len(cell_ids)
            or any(cell_id not in expected_by_id for cell_id in cell_ids)):
        raise Phase5CExecutionError("MATRIX_EXECUTION_CELL_SELECTION_INVALID")
    root = Path(result_directory)
    if root.is_symlink():
        raise Phase5CExecutionError("MATRIX_RESULT_ROOT_SYMLINK_REJECTED")
    if root.exists() and not root.is_dir():
        raise Phase5CExecutionError("MATRIX_RESULT_PATH_NOT_DIRECTORY")
    root.mkdir(parents=True, exist_ok=True)
    ledger_path = root / "matrix_ledger.json"
    if ledger_path.is_symlink():
        raise Phase5CExecutionError("MATRIX_LEDGER_SYMLINK_REJECTED")
    if ledger_path.exists():
        try:
            saved = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Phase5CExecutionError("MATRIX_LEDGER_PARTIAL_OR_MALFORMED") from exc
        if (saved.get("schema_version") != ledger["schema_version"]
                or saved.get("manifest_sha256") != verified.sha256
                or saved.get("implementation_commit") != ledger["implementation_commit"]
                or saved.get("ledger_sha256") != _sha({k: v for k, v in saved.items()
                    if k != "ledger_sha256"})
                or [(cell.get("cell_sha256"), cell.get("identity"))
                    for cell in saved.get("cells", [])]
                   != [(cell["cell_sha256"], cell["identity"])
                    for cell in ledger["cells"]]):
            raise Phase5CExecutionError("MATRIX_LEDGER_LINEAGE_OR_CONTENT_INVALID")
        ledger = saved
    else:
        _atomic_json_replace(ledger_path, ledger)

    receipts = [_dispatch_synthetic_cell(cell) for cell in expected_by_id.values()]
    reconciliation = reconcile_matrix_dispatch(verified, receipts)
    if not reconciliation["dispatch_reconciled"]:
        raise Phase5CExecutionError("MATRIX_DISPATCH_RECONCILIATION_FAILED")
    ledger = mark_matrix_dispatched(ledger, verified=verified)
    _atomic_json_replace(ledger_path, ledger)
    artifact_directory = root / "cell_results"
    if artifact_directory.is_symlink():
        raise Phase5CExecutionError("MATRIX_CELL_ARTIFACT_DIRECTORY_SYMLINK_REJECTED")
    allowed_artifacts = {f"{cell_id}.json" for cell_id in expected_by_id}
    if artifact_directory.exists():
        if not artifact_directory.is_dir():
            raise Phase5CExecutionError("MATRIX_CELL_ARTIFACT_DIRECTORY_INVALID")
        for existing in artifact_directory.iterdir():
            if (existing.is_symlink() or not existing.is_file()
                    or existing.name not in allowed_artifacts):
                raise Phase5CExecutionError("MATRIX_CELL_ARTIFACT_SET_INVALID")
    compute = executor or execute_synthetic_cell
    for cell_id in cell_ids:
        cell = expected_by_id[cell_id]
        artifact_path = artifact_directory / f"{cell_id}.json"
        current = next(item for item in ledger["cells"]
                       if item["cell_sha256"] == cell_id)
        if artifact_path.exists():
            try:
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                load_cell_result_artifact(verified, cell=cell, artifact=artifact)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise Phase5CExecutionError("MATRIX_EXISTING_CELL_RESULT_INVALID") from exc
            if current["status"] == "COMPLETE":
                if current.get("result_artifact_sha256") != artifact["artifact_sha256"]:
                    raise Phase5CExecutionError("MATRIX_LEDGER_RESULT_HASH_MISMATCH")
                continue
            if current["status"] in {"PENDING", "PARTIAL"}:
                ledger = transition_cell(ledger, verified=verified,
                    cell_sha256=cell_id, status="DISPATCHED")
                current_status = "DISPATCHED"
            else:
                current_status = current["status"]
            if current_status == "DISPATCHED":
                ledger = transition_cell(ledger, verified=verified,
                    cell_sha256=cell_id, status="RUNNING")
            ledger = transition_cell(ledger, verified=verified,
                cell_sha256=cell_id, status="COMPLETE", result_artifact=artifact)
            _atomic_json_replace(ledger_path, ledger)
            continue
        if current["status"] == "COMPLETE":
            raise Phase5CExecutionError("MATRIX_COMPLETED_CELL_ARTIFACT_MISSING")
        if current["status"] in {"PENDING", "PARTIAL"}:
            ledger = transition_cell(ledger, verified=verified,
                cell_sha256=cell_id, status="DISPATCHED")
        current = next(item for item in ledger["cells"]
                       if item["cell_sha256"] == cell_id)
        if current["status"] == "DISPATCHED":
            ledger = transition_cell(ledger, verified=verified,
                cell_sha256=cell_id, status="RUNNING")
        _atomic_json_replace(ledger_path, ledger)
        try:
            artifact = compute(verified, cell=cell)
            load_cell_result_artifact(verified, cell=cell, artifact=artifact)
            _immutable_write(artifact_path, artifact)
            # Verify the bytes actually published, not just the in-memory result.
            published = json.loads(artifact_path.read_text(encoding="utf-8"))
            load_cell_result_artifact(verified, cell=cell, artifact=published)
            ledger = transition_cell(ledger, verified=verified,
                cell_sha256=cell_id, status="COMPLETE", result_artifact=published)
        except (OSError, TypeError, ValueError) as exc:
            reason = (exc.reason_code if isinstance(exc, Phase5CExecutionError)
                      else "CELL_COMPUTE_OR_PUBLICATION_FAILED")
            ledger = transition_cell(ledger, verified=verified,
                cell_sha256=cell_id, status="FAILED", failure_reason_code=reason)
            _atomic_json_replace(ledger_path, ledger)
            raise Phase5CExecutionError(reason) from exc
        _atomic_json_replace(ledger_path, ledger)

    artifacts = {}
    for cell in ledger["cells"]:
        path = root / "cell_results" / f"{cell['cell_sha256']}.json"
        if path.exists():
            try:
                artifact = json.loads(path.read_text(encoding="utf-8"))
                artifacts[cell["cell_sha256"]] = load_cell_result_artifact(
                    verified, cell=cell, artifact=artifact)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise Phase5CExecutionError("MATRIX_CELL_ARTIFACT_SET_INVALID") from exc
    summary = evaluate_complete_matrix(ledger, verified=verified,
        result_artifacts=artifacts)
    report = {"schema_version": "bot2-phase5c-v3-matrix-execution-report-v1",
        "manifest_sha256": verified.sha256,
        "expected_cell_count": reconciliation["expected_cell_count"],
        "dispatched_cell_count": reconciliation["dispatched_cell_count"],
        "verified_result_artifact_count": len(artifacts),
        "matrix_summary": summary, "dispatch_reconciled": True,
        "protected_models_scored": 0, "protected_oos_scores_produced": 0,
        "protected_oos_execution": "NOT AUTHORIZED", "trading_authority": "NONE"}
    report["report_sha256"] = _sha(report)
    _atomic_json_replace(root / "matrix_report.json", report)
    return report


def _atomic_json_replace(path: Path, payload: Mapping) -> None:
    """Atomically update a mutable progress ledger/report without partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
            dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(_canonical_json_bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _engineering_comparison_records(verified: VerifiedManifest, *,
        coverage_manifest: Mapping, result_artifacts: Mapping[str, Mapping]) -> list[dict]:
    """Build performance-blind common-row records from actual cell artifacts."""
    expected_by_id = {cell["cell_sha256"]: cell
        for cell in expected_cell_ledger(verified)["cells"]}
    comparisons = []
    for group in coverage_manifest["comparison_groups"]:
        identity = group["identity"]
        ids_by_model = group["cell_ids_by_model"]
        rows_by_model, metadata_by_model = {}, {}
        validation_fingerprints = set()
        for model_id, cell_id in ids_by_model.items():
            cell = expected_by_id.get(cell_id)
            artifact = result_artifacts.get(cell_id)
            if (cell is None or artifact is None
                    or cell["identity"]["model_id"] != model_id
                    or any(cell["identity"].get(key) != identity.get(key)
                        for key in ("root", "horizon_minutes", "walk_forward_window",
                                    "ablation_id", "control_condition", "head"))
                    or cell["identity"].get("seed") != ("DETERMINISTIC"
                        if model_id.startswith("A0_") else identity["seed"])):
                raise Phase5CExecutionError("COMPARISON_GROUP_CELL_LINEAGE_MISMATCH")
            result = artifact["result"]
            information = result["information_contract"]
            prediction = result["prediction_artifact"]
            row_ids = prediction["row_identities"]
            if (artifact.get("common_comparison_row_identity") != _sha(row_ids)
                    or information.get("root") != identity["root"]
                    or information.get("horizon_minutes") != identity["horizon_minutes"]
                    or information.get("walk_forward_window") != identity["walk_forward_window"]
                    or information.get("ablation_id") != identity["ablation_id"]
                    or information.get("control_identity") != identity["control_condition"]
                    or information.get("head") != identity["head"]):
                raise Phase5CExecutionError("COMPARISON_INFORMATION_CONTRACT_INCOMPATIBLE")
            rows_by_model[model_id] = row_ids
            validation_fingerprints.add(artifact["partition_fingerprints"][
                "VALIDATION_AND_CALIBRATION"])
            metadata_by_model[model_id] = {"model_artifact_sha256":
                artifact["model_artifact_sha256"], "manifest_sha256": verified.sha256,
                "dataset_identity": artifact["dataset_identity"], **identity,
                "information_contract_identity": artifact["information_contract_identity"],
                "eligible_row_count": len(row_ids), "eligible_row_ids": row_ids,
                "eligible_row_ids_sha256": _sha(row_ids),
                "prediction_artifact_sha256": artifact["prediction_artifact_sha256"],
                "metric_definition_identity": artifact["metric_definition_identity"],
                "metrics": result["metrics"],
                "partition_fingerprints": artifact["partition_fingerprints"]}
        if len(validation_fingerprints) != 1:
            raise Phase5CExecutionError("COMPARISON_PARTITION_FINGERPRINT_MISMATCH")
        record = common_comparison_record(model_eligible_rows=rows_by_model,
            model_metadata=metadata_by_model,
            metric_identity=_sha({"head": identity["head"],
                "metric_definitions": verified.data["metrics"]}))
        record.update({"group_id": group["group_id"], "identity": dict(identity),
            "comparison_status": "COMPLETE_SYNTHETIC_ENGINEERING_ONLY",
            "alignment_policy": "AUTHORIZED_ELIGIBILITY_INTERSECTION_ONLY",
            "performance_used_for_row_selection": False,
            "partition_fingerprint": next(iter(validation_fingerprints)),
            "classification": "SYNTHETIC ENGINEERING RESULT"})
        record["record_sha256"] = _sha({key: value for key, value in record.items()
            if key != "record_sha256"})
        comparisons.append(record)
    return comparisons


def execute_synthetic_engineering_coverage(verified: VerifiedManifest, *,
        result_directory: str | Path) -> dict:
    """Run the minimal, manifest-derived engineering coverage set on fixtures."""
    coverage_manifest = select_engineering_coverage_cells(verified)
    root = Path(result_directory)
    root.mkdir(parents=True, exist_ok=True)
    matrix = execute_synthetic_matrix_cells(verified,
        result_directory=root / "matrix",
        cell_ids=coverage_manifest["selected_cell_ids"],
        executor=lambda manifest, cell: execute_synthetic_cell(manifest,
            cell=cell, stage_directory=root / "stages"))
    expected_by_id = {cell["cell_sha256"]: cell
        for cell in expected_cell_ledger(verified)["cells"]}
    artifacts = {}
    artifact_dir = root / "matrix" / "cell_results"
    for cell_id in coverage_manifest["selected_cell_ids"]:
        path = artifact_dir / f"{cell_id}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            artifacts[cell_id] = load_cell_result_artifact(verified,
                cell=expected_by_id[cell_id], artifact=raw)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise Phase5CExecutionError("ENGINEERING_COVERAGE_RESULT_INVALID") from exc
    comparisons = _engineering_comparison_records(verified,
        coverage_manifest=coverage_manifest, result_artifacts=artifacts)
    coverage_gate = verify_engineering_coverage(verified,
        coverage_manifest=coverage_manifest, result_artifacts=artifacts,
        comparison_records=comparisons)
    manifest_path = root / "engineering_coverage_manifest.json"
    comparison_path = root / "common_comparison_records.json"
    if manifest_path.is_symlink() or comparison_path.is_symlink():
        raise Phase5CExecutionError("ENGINEERING_COVERAGE_ARTIFACT_SYMLINK_REJECTED")
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != coverage_manifest:
            raise Phase5CExecutionError("ENGINEERING_COVERAGE_MANIFEST_CONFLICT")
    else:
        _immutable_write(manifest_path, coverage_manifest)
    comparison_payload = {"schema_version": "bot2-phase5c-v3-comparison-coverage-v1",
        "manifest_sha256": verified.sha256, "records": comparisons,
        "record_count": len(comparisons), "performance_used_for_alignment": False}
    comparison_payload["artifact_sha256"] = _sha(comparison_payload)
    if comparison_path.exists():
        if json.loads(comparison_path.read_text(encoding="utf-8")) != comparison_payload:
            raise Phase5CExecutionError("COMPARISON_COVERAGE_ARTIFACT_CONFLICT")
    else:
        _immutable_write(comparison_path, comparison_payload)
    report = {"schema_version": "bot2-phase5c-v3-engineering-coverage-report-v1",
        "manifest_sha256": verified.sha256,
        "coverage_manifest_sha256": coverage_gate["coverage_manifest_sha256"],
        "ENGINEERING_COVERAGE_STATUS": coverage_gate["status"],
        "FROZEN_EXPERIMENT_STATUS": "NOT_EXECUTED",
        "selected_cell_count": coverage_gate["selected_cell_count"],
        "verified_cell_result_count": coverage_gate["verified_cell_result_count"],
        "full_frozen_matrix_expected_cell_count": matrix["expected_cell_count"],
        "full_frozen_matrix_dispatched_cell_count": matrix["dispatched_cell_count"],
        "common_comparison_group_count": coverage_gate["verified_comparison_group_count"],
        "common_comparison_row_alignment": "VERIFIED",
        "protected_models_scored": 0, "protected_oos_scores_produced": 0,
        "protected_oos_execution": "NOT AUTHORIZED", "trading_authority": "NONE"}
    report["report_sha256"] = _sha(report)
    report_path = root / "engineering_coverage_report.json"
    if report_path.exists():
        if json.loads(report_path.read_text(encoding="utf-8")) != report:
            raise Phase5CExecutionError("ENGINEERING_COVERAGE_REPORT_CONFLICT")
    else:
        _immutable_write(report_path, report)
    return report


def _bind_matrix_orchestration(result: dict, matrix_status: Mapping) -> dict:
    """Bind dispatch proof and mark the full experiment incomplete."""
    result.pop("result_artifact_sha256", None)
    result["matrix_orchestration"] = dict(matrix_status)
    result["status"] = "REPRESENTATIVE_COMPUTE_COMPLETE_MATRIX_INCOMPLETE"
    result["experiment_status"] = "INCOMPLETE_MATRIX"
    result["result_content_sha256"] = ""
    result["result_content_sha256"] = _sha({k: v for k, v in result.items()
                                             if k != "result_content_sha256"})
    result["result_artifact_sha256"] = _sha(result)
    return result


def _manifest(verified: VerifiedManifest) -> dict:
    if not is_verified_manifest(verified) or not verified.external_anchor_content_verified:
        raise Phase5CExecutionError("VERIFIED_FROZEN_MANIFEST_REQUIRED")
    value = verified.data
    if (value.get("evaluation_permitted") is not False
            or value.get("oos_model_scoring_performed") is not False
            or value.get("trading_authority") is not False):
        raise Phase5CExecutionError("FROZEN_SAFETY_GATE_MISMATCH")
    return value


def _generate_partition(verified: VerifiedManifest, *, market: str, seed: int,
                        part: str, day: str, contract: str, count: int,
                        horizon: int) -> tuple[MarketObservation, ...]:
    m = verified.data
    names = tuple(m["feature_specification"]["features"])
    values = np.random.default_rng(seed).normal(size=(count, len(names)))
    start = datetime.fromisoformat(f"{day}T14:30:00+00:00")
    session = f"SYNTHETIC-{part}-{day}-{contract}"
    offsets = {"direction": 0, "volatility": 1, "structure": 2}
    rows = []
    for i in range(count):
        ts = start + timedelta(minutes=i)
        rows.append(MarketObservation(market, contract, session, ts.isoformat(), start.isoformat(),
            names, tuple(float(x) for x in values[i]),
            {h: (i + offsets[h]) % 3 for h in HEADS},
            (ts + timedelta(minutes=horizon)).isoformat(),
            m["source_dataset_manifest_sha256"], m["feature_specification"]["schema_version"],
            m["target_specification"]["version"]))
    return tuple(rows)


def build_synthetic_dataset(verified: VerifiedManifest, *, seed: int, market: str,
                            horizon_minutes: int) -> SyntheticDataset:
    """Build fixture rows in memory. This function never opens market-data files."""
    m = _manifest(verified)
    if market not in ("ES", "NQ") or horizon_minutes not in m["target_specification"]["horizons_minutes"]:
        raise Phase5CExecutionError("SYNTHETIC_FIXTURE_SCOPE_INVALID")
    contracts = m["source_dataset"]["contracts"][market]
    train_day = m["chronological_partitions_inclusive"]["TRAIN"][0]
    valid_day = m["chronological_partitions_inclusive"]["VALIDATION_AND_CALIBRATION"][0]
    return SyntheticDataset(SYNTHETIC_SOURCE, {
        "TRAIN": _generate_partition(verified, market=market, seed=seed,
            part="TRAIN", day=train_day, contract=contracts[0], count=72, horizon=horizon_minutes),
        "VALIDATION_AND_CALIBRATION": _generate_partition(verified, market=market,
            seed=seed + 1, part="VALIDATION_AND_CALIBRATION", day=valid_day,
            contract=contracts[-1], count=72, horizon=horizon_minutes),
    }, seed)


def _metrics(p: np.ndarray, y: np.ndarray) -> dict:
    p, y = np.asarray(p, dtype=np.float64), np.asarray(y, dtype=np.int64)
    if p.shape != (len(y), 3) or not len(y) or not np.isfinite(p).all():
        raise Phase5CExecutionError("METRIC_INPUT_INVALID")
    pred = np.argmax(p, axis=1)  # frozen lowest-index argmax tie break
    precision, recall, f1 = [], [], []
    for k in range(3):
        tp = int(np.sum((pred == k) & (y == k)))
        fp = int(np.sum((pred == k) & (y != k)))
        fn = int(np.sum((pred != k) & (y == k)))
        pr = tp / (tp + fp) if tp + fp else 0.0
        re = tp / (tp + fn) if tp + fn else 0.0
        precision.append(pr); recall.append(re)
        f1.append(2 * pr * re / (pr + re) if pr + re else 0.0)
    onehot = np.eye(3)[y]
    conf = p[np.arange(len(y)), pred]
    bins, ece = [], 0.0
    for i in range(10):
        mask = (conf >= i / 10) & ((conf < (i + 1) / 10) if i < 9 else (conf <= 1.0))
        n = int(mask.sum())
        accuracy = float(np.mean(pred[mask] == y[mask])) if n else None
        avg_conf = float(np.mean(conf[mask])) if n else None
        bins.append({"bin": i, "count": n, "accuracy": accuracy, "mean_confidence": avg_conf})
        if n: ece += n / len(y) * abs(accuracy - avg_conf)
    return {"macro_f1": float(np.mean(f1)),
        "categorical_log_loss": float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-15)).mean()),
        "multiclass_brier_score": float(np.mean(np.sum((p - onehot) ** 2, axis=1) / 3)),
        "balanced_accuracy": float(np.mean(recall)), "per_class_precision": precision,
        "per_class_recall": recall,
        "fixed_order_3x3_confusion_matrix": [[int(np.sum((y == r) & (pred == c)))
            for c in range(3)] for r in range(3)],
        "10_bin_equal_width_top_label_reliability": bins,
        "top_label_expected_calibration_error": float(ece),
        "accuracy_descriptive_only": float(np.mean(pred == y))}


def _softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    x = np.asarray(logits, dtype=np.float64) / float(temperature)
    x -= x.max(axis=1, keepdims=True)
    ex = np.exp(x)
    return ex / ex.sum(axis=1, keepdims=True)


def _a0_predictions(split) -> dict[str, dict[str, np.ndarray]]:
    train, valid = split.canonical_rows["TRAIN"], split.canonical_rows["VALIDATION_AND_CALIBRATION"]
    count = len(split.validation.x)
    majority = {}
    for h in HEADS:
        counts = np.bincount(split.train.targets[h], minlength=3)
        result = np.zeros((count, 3)); result[:, int(np.argmax(counts))] = 1.0
        majority[h] = result
    previous, transition = {h: [] for h in HEADS}, {h: [] for h in HEADS}
    for seq in split.validation.sequence_keys:
        contract, session, end_ts = seq[-1]
        t = datetime.fromisoformat(end_ts)
        eligible = [r for r in valid if r.contract == contract and r.session_id == session
            and datetime.fromisoformat(r.exchange_timestamp_utc) < t
            and datetime.fromisoformat(r.label_end_utc) <= t]
        if not eligible: raise Phase5CExecutionError("A0_PRIOR_LABEL_INELIGIBLE")
        prior = max(eligible, key=lambda r: r.exchange_timestamp_utc)
        for h in HEADS:
            q = np.full(3, 1e-15); q[int(prior.targets[h])] = 1 - 2e-15
            previous[h].append(q)
            counts = np.ones(3, dtype=np.float64)  # Laplace alpha=1
            for a, b in zip(train, train[1:]):
                if a.contract == b.contract and a.session_id == b.session_id and int(a.targets[h]) == int(prior.targets[h]):
                    counts[int(b.targets[h])] += 1
            transition[h].append(counts / counts.sum())
    return {"A0_PREVIOUS_LABEL_PERSISTENCE": {h: np.asarray(v) for h, v in previous.items()},
        "A0_TRAIN_MAJORITY": majority,
        "A0_TRAIN_TRANSITION_MATRIX": {h: np.asarray(v) for h, v in transition.items()}}


def _make_model_artifact(model_id: str, seed: int, weights: Mapping, split,
                         verified: VerifiedManifest, scaler: TrainingOnlyStandardizer,
                         ablation: Mapping) -> dict:
    architecture = verified.data["architectures"][model_id]
    arch_version = architecture.get("architecture_version", model_id) if isinstance(architecture, dict) else model_id
    value = {"schema_version": "bot2-phase5c-v3-runner-model-artifact-v1",
        "model_id": model_id, "architecture_version": arch_version, "random_seed": seed,
        "weights": dict(weights), "weights_sha256": canonical_hash(dict(weights)),
        "manifest_sha256": verified.sha256,
        "dataset_manifest_sha256": split.dataset_manifest_sha256,
        "preprocessing_sha256": scaler.sha256,
        "training_partition_fingerprint": split.partition_fingerprints["TRAIN"],
        "validation_partition_fingerprint": split.partition_fingerprints["VALIDATION_AND_CALIBRATION"],
        "market": split.market, "horizon_minutes": split.horizon_minutes,
        "ablation_id": ablation["ablation_id"], "ablation_sha256": ablation["ablation_sha256"],
        "code_commit": verified.pin["review_candidate_commit"],
        "oos_scoring_performed": False, "trading_authority": False}
    value["artifact_sha256"] = canonical_hash(value)
    return value


def execute_synthetic_cell(verified: VerifiedManifest, *, cell: Mapping,
        stage_directory: str | Path | None = None,
        interrupt_after_stage: str | None = None) -> dict:
    """Execute one exact manifest-derived cell on deterministic synthetic rows.

    This produces engineering evidence only. The cell's frozen identity drives
    the instrument, target horizon, WF dates, model, ablation, control, seed,
    and head; caller-supplied result metadata is never accepted.
    """
    manifest = _manifest(verified)
    expected = expected_cell_ledger(verified)
    frozen = next((item for item in expected["cells"]
        if item["cell_sha256"] == cell.get("cell_sha256")), None)
    if frozen is None or cell.get("identity") != frozen["identity"]:
        raise Phase5CExecutionError("EXPERIMENT_CELL_IDENTITY_MISMATCH")
    identity = frozen["identity"]
    model_id, head = identity["model_id"], identity["head"]
    neural = model_id in _NEURAL
    if neural and identity["seed"] not in manifest["random_seeds"]:
        raise Phase5CExecutionError("CELL_SEED_NOT_IN_FROZEN_MANIFEST")
    if not neural and identity["seed"] != "DETERMINISTIC":
        raise Phase5CExecutionError("DETERMINISTIC_BASELINE_SEED_INVALID")
    if head not in HEADS:
        raise Phase5CExecutionError("CELL_HEAD_NOT_IN_FROZEN_MANIFEST")

    windows = {item.window_id: item for item in derive_walk_forward_windows(verified)}
    window = windows.get(identity["walk_forward_window"])
    if window is None:
        raise Phase5CExecutionError("WALK_FORWARD_WINDOW_NOT_IN_MANIFEST")
    root, horizon = identity["root"], identity["horizon_minutes"]
    model_seed = int(identity["seed"]) if neural else int(manifest["random_seeds"][0])
    contract = manifest["source_dataset"]["contracts"][root][0]
    # Synthetic comparison fixtures must be shared across models, ablations,
    # seeds, controls, and heads within a frozen root/horizon/WF group. Cell-
    # specific seeds would make row intersections meaningless.
    fixture_seed = int(_sha({"manifest_sha256": verified.sha256, "root": root,
        "horizon_minutes": horizon,
        "walk_forward_window": identity["walk_forward_window"]})[:8], 16)
    spans = {"TRAIN": window.train,
        "VALIDATION_AND_CALIBRATION": window.validation, "OOS_TEST": window.test}
    partitions = {name: _generate_partition(verified, market=root,
        seed=fixture_seed + offset, part=f"CELL-{identity['walk_forward_window']}-{name}",
        day=span[0], contract=contract, count=72, horizon=horizon)
        for offset, (name, span) in enumerate(spans.items())}
    validate_walk_forward_rows(verified, root=root, horizon_minutes=horizon,
        window_id=identity["walk_forward_window"], rows_by_partition=partitions)

    split_ablation = identity["ablation_id"] if neural else "ALL"
    scaler = TrainingOnlyStandardizer().fit_observations(partitions["TRAIN"],
        market=root, verified_manifest=verified,
        code_commit=verified.pin["review_candidate_commit"])
    split = build_authorized_split(verified, market=root, horizon_minutes=horizon,
        partition_rows=partitions, preprocessor=scaler,
        ablation_id=split_ablation,
        walk_forward_window_id=identity["walk_forward_window"])
    validate_authorized_split(split, verified)
    ablation_execution = None
    if neural:
        ablation_execution = execute_ablation_control(partitions["TRAIN"],
            verified_manifest=verified, preprocessor=scaler,
            model_id=model_id, seed=model_seed,
            ablation_id=identity["ablation_id"])
        verify_ablation_execution(ablation_execution, rows=partitions["TRAIN"],
            preprocessor=scaler, verified_manifest=verified)
        if (ablation_execution.artifact["input_channels"] != 24
                or ablation_execution.artifact["ablation_sha256"]
                   != split.ablation_contract["ablation_sha256"]):
            raise Phase5CExecutionError("CELL_ABLATION_EXECUTION_CONTRACT_FAILED")
    partition_fingerprints = dict(split.partition_fingerprints)
    if set(partition_fingerprints) != set(spans):
        raise Phase5CExecutionError("CELL_PARTITION_FINGERPRINT_SET_INVALID")

    input_contract = create_model_input_contract(verified, model_id=model_id,
        seed=model_seed, ablation_id=(identity["ablation_id"] if neural else "ALL"))
    control = None
    if identity["control_condition"] != "NONE":
        prefix = "SHUFFLED_TRAIN_LABELS:"
        if not neural or not identity["control_condition"].startswith(prefix):
            raise Phase5CExecutionError("CELL_CONTROL_CONDITION_INVALID")
        try:
            shuffle_seed = int(identity["control_condition"][len(prefix):])
            run_index = tuple(manifest["shuffled_label_control"]["seeds"]).index(shuffle_seed) + 1
        except (ValueError, TypeError) as exc:
            raise Phase5CExecutionError("CELL_SHUFFLE_SEED_NOT_IN_FROZEN_MANIFEST") from exc
        control = execute_shuffled_label_control(split, verified_manifest=verified,
            candidate_id=model_id, candidate_seed=model_seed, run_index=run_index)
        verify_shuffled_label_control(control, split=split, verified_manifest=verified)

    # The first safely reusable durable intermediate in the real training path
    # is the fitted model state plus validation logits. It is only valid for the
    # exact frozen cell and the exact upstream data/preprocessing/control hashes.
    stage_path = None
    stage_lineage = None
    cached_training = None
    if neural and stage_directory is not None:
        from .experiment_matrix import (create_stage_checkpoint,
            load_stage_checkpoint, publish_stage_checkpoint)
        stage_root = Path(stage_directory)
        if stage_root.is_symlink():
            raise Phase5CExecutionError("STAGE_CHECKPOINT_ROOT_SYMLINK_REJECTED")
        stage_root.mkdir(parents=True, exist_ok=True)
        expected_stage_files = {f"{item['cell_sha256']}.model_training.json"
            for item in expected["cells"] if item["identity"]["model_id"] in _NEURAL}
        for existing in stage_root.iterdir():
            if (existing.is_symlink() or not existing.is_file()
                    or existing.name not in expected_stage_files):
                raise Phase5CExecutionError("STAGE_CHECKPOINT_ARTIFACT_SET_INVALID")
        stage_path = stage_root / f"{frozen['cell_sha256']}.model_training.json"
        if stage_path.is_symlink():
            raise Phase5CExecutionError("STAGE_CHECKPOINT_SYMLINK_REJECTED")
        upstream = {"partition_fingerprints": _sha(partition_fingerprints),
            "preprocessing_sha256": scaler.sha256,
            "input_contract_sha256": _sha(input_contract),
            "control_sha256": (control.artifact["control_sha256"] if control is not None
                else _sha({"control_identity": "NONE"})),
            "ablation_execution_sha256": (ablation_execution.artifact["execution_sha256"]
                if ablation_execution is not None else _sha({"ablation": "NONE"})),
            "implementation_identity_sha256": implementation_source_identity()}
        template = create_stage_checkpoint(verified, cell=frozen,
            stage="MODEL_TRAINING_COMPLETE",
            partition_fingerprints=partition_fingerprints,
            upstream_artifact_hashes=upstream,
            payload={"state": {}, "validation_logits": []})
        stage_lineage = dict(template["lineage"])
        if stage_path.exists():
            try:
                cached_training = load_stage_checkpoint(stage_path,
                    expected_lineage=stage_lineage)["payload"]
            except (OSError, TypeError, ValueError) as exc:
                raise Phase5CExecutionError("STAGE_CHECKPOINT_REJECTED") from exc

    checkpoint_artifact = None
    if not neural:
        baseline_predictions = _a0_predictions(split)
        probabilities = baseline_predictions[model_id][head]
        state = {"baseline_id": model_id, "fit_partition": "TRAIN",
            "walk_forward_window": identity["walk_forward_window"],
            "training_partition_fingerprint": split.partition_fingerprints["TRAIN"]}
        artifact_ablation = {"ablation_id": "NOT_APPLICABLE_NO_FEATURE_INPUT",
            "ablation_sha256": None}
        model_artifact = _make_model_artifact(model_id, "DETERMINISTIC", state,
            split, verified, scaler, artifact_ablation)
        logits = np.log(np.maximum(probabilities, 1e-15))
    else:
        validate_model_input_contract(input_contract, verified,
            actual_features=input_contract["features"],
            actual_sequence_shape=input_contract["sequence_shape"],
            actual_feature_mask=input_contract["input_feature_mask"],
            latest_input_timestamp_utc=split.validation.sequence_keys[-1][-1][2],
            decision_timestamp_utc=split.validation.sequence_keys[-1][-1][2])
        if model_id == "A1_NUMPY_MULTIHEAD_MLP":
            from bot2.neural.model import MultiHeadMLP
            spec = manifest["architectures"][model_id]
            model = MultiHeadMLP(input_width=input_contract["flattened_width"],
                hidden_width=spec["hidden_width"], seed=model_seed)
            if cached_training is not None:
                state = cached_training.get("state")
                try:
                    model.w = np.asarray(state["w"], dtype=np.float64)
                    model.b = np.asarray(state["b"], dtype=np.float64)
                    model.heads = {key: np.asarray(value, dtype=np.float64)
                        for key, value in state["heads"].items()}
                    model.bias = {key: np.asarray(value, dtype=np.float64)
                        for key, value in state["bias"].items()}
                    if (set(model.heads) != set(HEADS) or set(model.bias) != set(HEADS)
                            or model.w.shape != (input_contract["flattened_width"], spec["hidden_width"])
                            or model.b.shape != (spec["hidden_width"],)
                            or any(model.heads[name].shape != (spec["hidden_width"], 3)
                                or model.bias[name].shape != (3,) for name in HEADS)):
                        raise ValueError("A1_STAGE_MODEL_STATE_SHAPE_INVALID")
                    logits = np.asarray(cached_training["validation_logits"], dtype=np.float64)
                    if logits.shape != (len(split.validation.x), 3) or not np.isfinite(logits).all():
                        raise ValueError("A1_STAGE_LOGITS_INVALID")
                except (KeyError, TypeError, ValueError) as exc:
                    raise Phase5CExecutionError("STAGE_CHECKPOINT_PAYLOAD_INVALID") from exc
            else:
                train_targets = split.train.targets
                if control is not None:
                    rows_by_key = {(row.contract, row.session_id, row.exchange_timestamp_utc): row
                        for row in split.canonical_rows["TRAIN"]}
                    shuffled = {name: [] for name in HEADS}
                    for sequence in split.train.sequence_keys:
                        row = rows_by_key.get(sequence[-1])
                        if row is None or row.observation_id not in control.train_targets_by_observation:
                            raise Phase5CExecutionError("SHUFFLED_LABEL_TRAIN_IDENTITY_MISMATCH")
                        for name in HEADS:
                            shuffled[name].append(control.train_targets_by_observation[row.observation_id][name])
                    train_targets = {name: np.asarray(values, dtype=np.int64)
                        for name, values in shuffled.items()}
                model.fit(split.train.x.reshape(len(split.train.x), -1), train_targets,
                    epochs=manifest["a1_training"]["epochs"],
                    learning_rate=manifest["a1_training"]["learning_rate"])
                probabilities = model.predict(split.validation.x.reshape(len(split.validation.x), -1))[head]
                logits = np.log(np.maximum(probabilities, 1e-15))
                state = {"w": model.w.tolist(), "b": model.b.tolist(),
                    "heads": {key: value.tolist() for key, value in model.heads.items()},
                    "bias": {key: value.tolist() for key, value in model.bias.items()}}
                if stage_path is not None:
                    from .experiment_matrix import create_stage_checkpoint, publish_stage_checkpoint
                    stage = create_stage_checkpoint(verified, cell=frozen,
                        stage="MODEL_TRAINING_COMPLETE",
                        partition_fingerprints=partition_fingerprints,
                        upstream_artifact_hashes=upstream,
                        payload={"state": state, "validation_logits": logits.tolist()})
                    try:
                        publish_stage_checkpoint(stage_path, stage)
                    except ValueError as exc:
                        raise Phase5CExecutionError("STAGE_CHECKPOINT_PUBLICATION_FAILED") from exc
                    if interrupt_after_stage == "MODEL_TRAINING_COMPLETE":
                        raise Phase5CExecutionError("ENGINEERING_INTERRUPTION_INJECTED_MODEL_TRAINING_COMPLETE")
            if cached_training is not None:
                probabilities = model.predict(split.validation.x.reshape(len(split.validation.x), -1))[head]
                recomputed_logits = np.log(np.maximum(probabilities, 1e-15))
                if not np.array_equal(logits, recomputed_logits):
                    raise Phase5CExecutionError("STAGE_CHECKPOINT_RECOMPUTATION_MISMATCH")
        else:
            model = CausalTemporalConv(verified, seed=model_seed,
                ablation_id=identity["ablation_id"])
            if cached_training is not None:
                try:
                    saved_state = cached_training["state"]
                    if set(saved_state) != set(model.params):
                        raise ValueError("A2_STAGE_PARAMETER_SET_INVALID")
                    restored = {key: np.asarray(value, dtype=np.float32)
                        for key, value in saved_state.items()}
                    if any(restored[key].shape != model.params[key].shape
                            or not np.isfinite(restored[key]).all() for key in model.params):
                        raise ValueError("A2_STAGE_PARAMETER_SHAPE_INVALID")
                    model.params = restored
                    model.trained_epochs = int(cached_training["selected_epoch"])
                    model.best_validation_loss = float(cached_training["validation_loss"])
                    logits = np.asarray(cached_training["validation_logits"], dtype=np.float64)
                    if logits.shape != (len(split.validation.x), 3) or not np.isfinite(logits).all():
                        raise ValueError("A2_STAGE_LOGITS_INVALID")
                except (KeyError, TypeError, ValueError) as exc:
                    raise Phase5CExecutionError("STAGE_CHECKPOINT_PAYLOAD_INVALID") from exc
            else:
                model.fit(split, shuffled_label_control=control)
                logits = model.predict_logits(split.validation.x)[head]
            if model.parameter_count != 7417 or split.validation.x.shape[1:] != (8, 24):
                raise Phase5CExecutionError("A2_FIXED_ARCHITECTURE_CONTRACT_FAILED")
            state = model.state()
            checkpoint_artifact = {"selected_state": state,
                "selected_epoch": model.trained_epochs,
                "validation_loss": model.best_validation_loss,
                "selection_partition": "VALIDATION_AND_CALIBRATION"}
            if cached_training is not None:
                recomputed_logits = model.predict_logits(split.validation.x)[head]
                if not np.array_equal(logits, recomputed_logits):
                    raise Phase5CExecutionError("STAGE_CHECKPOINT_RECOMPUTATION_MISMATCH")
            if cached_training is None and stage_path is not None:
                from .experiment_matrix import create_stage_checkpoint, publish_stage_checkpoint
                stage = create_stage_checkpoint(verified, cell=frozen,
                    stage="MODEL_TRAINING_COMPLETE",
                    partition_fingerprints=partition_fingerprints,
                    upstream_artifact_hashes=upstream,
                    payload={"state": state, "selected_epoch": model.trained_epochs,
                        "validation_loss": model.best_validation_loss,
                        "validation_logits": np.asarray(logits).tolist()})
                try:
                    publish_stage_checkpoint(stage_path, stage)
                except ValueError as exc:
                    raise Phase5CExecutionError("STAGE_CHECKPOINT_PUBLICATION_FAILED") from exc
                if interrupt_after_stage == "MODEL_TRAINING_COMPLETE":
                    raise Phase5CExecutionError("ENGINEERING_INTERRUPTION_INJECTED_MODEL_TRAINING_COMPLETE")
        model_artifact = _make_model_artifact(model_id, model_seed, state,
            split, verified, scaler, create_ablation_contract(verified, identity["ablation_id"]))

    model_artifact.pop("artifact_sha256", None)
    model_artifact["control_identity"] = identity["control_condition"]
    model_artifact["training_label_control_sha256"] = (
        control.artifact["control_sha256"] if control is not None else None)
    model_artifact["ablation_execution_artifact"] = (
        dict(ablation_execution.artifact) if ablation_execution is not None else None)
    if neural:
        model_artifact["input_shape"] = list(input_contract["sequence_shape"])
    if model_id == "A2_LEARNED_CAUSAL_TCN":
        model_artifact["parameter_count"] = model.parameter_count
    model_artifact["artifact_sha256"] = canonical_hash(model_artifact)
    if checkpoint_artifact is not None:
        checkpoint_artifact["model_artifact_sha256"] = model_artifact["artifact_sha256"]
        checkpoint_artifact["partition_fingerprints"] = partition_fingerprints
        checkpoint_artifact["checkpoint_sha256"] = _sha({key: value
            for key, value in checkpoint_artifact.items() if key != "checkpoint_sha256"})
    calibration = fit_temperature_calibrator(logits, split=split,
        verified_manifest=verified, model_artifact=model_artifact, head=head)
    verify_calibration_artifact(calibration, split=split,
        verified_manifest=verified, model_artifact=model_artifact, expected_head=head)
    calibrated = _softmax(logits, calibration["temperature"])
    abstention = select_abstention_threshold(calibrated, split=split,
        verified_manifest=verified, model_artifact=model_artifact, head=head,
        target_coverage=manifest["uncertainty_abstention"]["coverage_points"][0])
    verify_abstention_artifact(abstention, split=split,
        verified_manifest=verified, model_artifact=model_artifact)
    row_lookup = {(row.contract, row.session_id, row.exchange_timestamp_utc): row
        for row in split.canonical_rows["VALIDATION_AND_CALIBRATION"]}
    row_ids = [row_lookup[sequence[-1]].observation_id
        for sequence in split.validation.sequence_keys]
    metric_definition = {"head": head, "definitions": manifest["metrics"]}
    metric_definition["metric_definition_sha256"] = _sha(metric_definition)
    information_contract = {"model_input_contract": input_contract,
        "root": root, "horizon_minutes": horizon,
        "seed": identity["seed"], "walk_forward_window": identity["walk_forward_window"],
        "model_id": model_id, "ablation_id": identity["ablation_id"],
        "control_identity": identity["control_condition"], "head": head,
        "partition_fingerprints": partition_fingerprints}
    information_contract["contract_sha256"] = _sha(information_contract)
    prediction_artifact = {"target_head": head, "row_identities": row_ids,
        "predictions": calibrated.tolist(),
        "prediction_sha256": ""}
    prediction_artifact["prediction_sha256"] = _sha({key: value for key, value
        in prediction_artifact.items() if key != "prediction_sha256"})
    result = {"information_contract": information_contract,
        "preprocessing_artifact": scaler.state(), "model_artifact": model_artifact,
        "checkpoint_artifact": checkpoint_artifact,
        "calibration_artifact": calibration, "abstention_artifact": abstention,
        "prediction_artifact": prediction_artifact,
        "common_comparison_row_identity": _sha(row_ids),
        "metric_definition": metric_definition,
        "metrics": _metrics(calibrated, split.validation.targets[head])}
    return create_cell_result_artifact(verified, cell=frozen,
        partition_fingerprints=partition_fingerprints, result=result)


def _calibrated_predictions(*, model_id: str, seed: int, logits_by_head: Mapping,
        artifact: Mapping, split, verified: VerifiedManifest, scaler: TrainingOnlyStandardizer,
        ablation: Mapping, include_records: bool = True) -> tuple[dict, list[dict]]:
    metrics, cal_hashes, abstain_hashes, records = {}, {}, {}, []
    for head in HEADS:
        logits = np.asarray(logits_by_head[head], dtype=np.float64)
        cal = fit_temperature_calibrator(logits, split=split, verified_manifest=verified,
            model_artifact=artifact, head=head)
        verify_calibration_artifact(cal, split=split, verified_manifest=verified,
            model_artifact=artifact, expected_head=head)
        prob = _softmax(logits, cal["temperature"])
        abstain = select_abstention_threshold(prob, split=split, verified_manifest=verified,
            model_artifact=artifact, head=head,
            target_coverage=verified.data["uncertainty_abstention"]["coverage_points"][0])
        verify_abstention_artifact(abstain, split=split, verified_manifest=verified,
            model_artifact=artifact)
        metrics[head] = _metrics(prob, split.validation.targets[head])
        cal_hashes[head], abstain_hashes[head] = cal["calibration_sha256"], abstain["artifact_sha256"]
        if include_records:
            entropy = -np.sum(prob * np.log(np.maximum(prob, 1e-15)), axis=1) / math.log(3)
            for i, seq in enumerate(split.validation.sequence_keys):
                contract, session, ts = seq[-1]
                records.append({"schema_version": PREDICTION_SCHEMA,
                    "experiment_id": verified.data["experiment_id"], "model_id": model_id,
                    "architecture_version": artifact["architecture_version"],
                    "instrument": split.market, "contract_identity": contract,
                    "horizon_minutes": split.horizon_minutes, "head": head,
                    "observation_row_identity": f"{contract}|{session}|{ts}",
                    "exchange_timestamp_utc": ts, "raw_prediction": int(np.argmax(logits[i])),
                    "raw_logits": logits[i].tolist(), "calibrated_probability": prob[i].tolist(),
                    "uncertainty": float(entropy[i]),
                    "abstention_threshold": abstain["entropy_threshold"],
                    "threshold_source_partition": abstain["fit_partition"],
                    "abstain": bool(entropy[i] > abstain["entropy_threshold"]),
                    "manifest_sha256": verified.sha256,
                    "implementation_commit": artifact["code_commit"],
                    "model_artifact_sha256": artifact["artifact_sha256"],
                    "preprocessing_artifact_sha256": scaler.sha256,
                    "calibration_artifact_sha256": cal["calibration_sha256"],
                    "ablation_id": ablation["ablation_id"],
                    "ablation_sha256": ablation["ablation_sha256"], "seed": seed,
                    "partition_identity": split.validation.partition,
                    "partition_fingerprint": split.partition_fingerprints[split.validation.partition]})
    return {"metrics": metrics, "calibration_hashes": cal_hashes,
        "abstention_hashes": abstain_hashes}, records


def _immutable_write(path: Path, obj: Mapping) -> str:
    if path.exists(): raise Phase5CExecutionError("IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _canonical_json_bytes(obj)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        # Publish without replacement: an atomic hard-link cannot clobber a
        # file that appeared after the preliminary existence check.
        os.link(name, path)
        os.unlink(name)
    except FileExistsError as exc:
        try: os.unlink(name)
        except OSError: pass
        raise Phase5CExecutionError("IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS") from exc
    except Exception:
        try: os.unlink(name)
        except OSError: pass
        raise
    return hashlib.sha256(content).hexdigest()


def verify_runner_result(result: Mapping, verified: VerifiedManifest) -> None:
    """Reconcile the immutable result envelope with its actual prediction payload."""
    value = dict(result)
    digest = value.pop("result_artifact_sha256", None)
    predictions = result.get("predictions")
    expected_cells = expected_cell_ledger(verified)["expected_cell_count"]
    expected_wf = {(root, horizon, window.window_id)
        for root in verified.data["source_dataset"]["contracts"]
        for horizon in verified.data["target_specification"]["horizons_minutes"]
        for window in derive_walk_forward_windows(verified)}
    if (not is_verified_manifest(verified)
            or digest != _sha(value)
            or result.get("schema_version") != RUNNER_SCHEMA
            or result.get("manifest_sha256") != verified.sha256
            or result.get("execution_mode") != ExecutionMode.SYNTHETIC_VALIDATION.value
            or result.get("dataset_identity") != SYNTHETIC_SOURCE
            or not isinstance(predictions, Mapping)
            or result.get("prediction_artifact_sha256") != _sha(predictions)
            or result.get("prediction_schema") != PREDICTION_SCHEMA
            or result.get("protected_models_scored") != 0
            or result.get("protected_oos_scores_produced") != 0
            or result.get("protected_oos_execution") != "NOT AUTHORIZED"
            or result.get("trading_authority") != "NONE"
            or result.get("broker_path") is not False
            or result.get("shuffled_label_model_training_executed") is not True
            or result.get("status") != "REPRESENTATIVE_COMPUTE_COMPLETE_MATRIX_INCOMPLETE"
            or result.get("experiment_status") != "INCOMPLETE_MATRIX"):
        raise Phase5CExecutionError("RUNNER_RESULT_CONTENT_OR_PROVENANCE_INVALID")
    matrix = result.get("matrix_orchestration")
    if (not isinstance(matrix, Mapping)
            or matrix.get("manifest_sha256") != verified.sha256
            or matrix.get("expected_cell_count") != expected_cells
            or matrix.get("dispatched_cell_count") != expected_cells
            or matrix.get("unique_dispatched_cell_count") != expected_cells
            or matrix.get("complete_cell_count") != 0
            or matrix.get("failed_cell_count") != 0
            or matrix.get("incomplete_cell_count") != expected_cells
            or matrix.get("missing_cell_count") != 0
            or matrix.get("duplicate_cell_count") != 0
            or matrix.get("unknown_cell_count") != 0
            or matrix.get("identity_mismatch_count") != 0
            or matrix.get("dispatch_reconciled") is not True
            or matrix.get("experiment_complete") is not False
            or matrix.get("completion_reason_code") != "CELL_RESULT_ARTIFACTS_REQUIRED"
            or matrix.get("dispatch_mode") != "SYNTHETIC_ORCHESTRATION_ONLY"
            or not isinstance(matrix.get("walk_forward_coverage"), Mapping)):
        raise Phase5CExecutionError("RUNNER_MATRIX_RECONCILIATION_INVALID")
    coverage = matrix["walk_forward_coverage"]
    records = coverage.get("records")
    observed_wf = ({(record.get("root"), record.get("horizon_minutes"), record.get("window_id"))
                    for record in records if isinstance(record, Mapping)}
                   if isinstance(records, list) else set())
    if (coverage.get("status") != "SYNTHETIC_PARTITION_VALIDATION_COMPLETE"
            or coverage.get("classification") != "SYNTHETIC ENGINEERING RESULT"
            or coverage.get("expected_combinations") != len(expected_wf)
            or coverage.get("validated_combinations") != len(expected_wf)
            or observed_wf != expected_wf
            or len(observed_wf) != len(records or ())
            or coverage.get("protected_models_scored") != 0
            or coverage.get("protected_oos_scores_produced") != 0
            or coverage.get("trading_authority") != "NONE"):
        raise Phase5CExecutionError("RUNNER_WALK_FORWARD_COVERAGE_INVALID")
    for record in records:
        metrics = record.get("baseline_metrics_by_head")
        if (record.get("baseline_model_ids") != list(_A0)
                or record.get("oos_engineering_row_count", 0) <= 0
                or record.get("validation_prediction_row_count", 0) <= 0
                or not isinstance(record.get("oos_engineering_row_identity_sha256"), str)
                or len(record["oos_engineering_row_identity_sha256"]) != 64
                or not isinstance(record.get("validation_prediction_row_identity_sha256"), str)
                or len(record["validation_prediction_row_identity_sha256"]) != 64
                or not isinstance(metrics, Mapping) or set(metrics) != set(_A0)
                or any(not isinstance(metrics[model], Mapping)
                    or set(metrics[model]) != set(HEADS) for model in _A0)):
            raise Phase5CExecutionError("RUNNER_WALK_FORWARD_COMPUTE_COVERAGE_INVALID")
    required = set(_A0)
    required.update(f"{model}:{ablation['id']}" for model in _NEURAL
                    for ablation in verified.data["feature_ablations"])
    if set(result.get("model_results", {})) != required:
        raise Phase5CExecutionError("RUNNER_RESULT_MODEL_MATRIX_INCOMPLETE")
    if len(result.get("shuffled_label_controls", [])) != len(_NEURAL) * len(
            verified.data["feature_ablations"]) * verified.data["shuffled_label_control"]["runs_per_candidate_seed"]:
        raise Phase5CExecutionError("RUNNER_RESULT_CONTROL_MATRIX_INCOMPLETE")
    if (not isinstance(result.get("result_content_sha256"), str)
            or result["result_content_sha256"] != _sha({k:v for k,v in value.items()
                                                        if k != "result_content_sha256"})):
        raise Phase5CExecutionError("RUNNER_RESULT_CONTENT_HASH_MISMATCH")
    comparisons = result.get("comparison_records")
    expected_comparisons = len(verified.data["feature_ablations"]) * len(HEADS)
    expected_models = set(_A0 + _NEURAL)
    if not isinstance(comparisons, list) or len(comparisons) != expected_comparisons:
        raise Phase5CExecutionError("RUNNER_COMPARISON_MATRIX_INCOMPLETE")
    seen_comparisons = set()
    for record in comparisons:
        body = {key: item for key, item in record.items() if key != "record_sha256"}
        key = (record.get("ablation_id"), record.get("head"))
        if (key in seen_comparisons
                or record.get("classification") != "SYNTHETIC ENGINEERING RESULT"
                or set(record.get("models", {})) != expected_models
                or record.get("metrics_must_use_identical_rows") is not True
                or record.get("common_comparison_row_sha256") != _sha(
                    record.get("common_comparison_row_ids"))
                or record.get("record_sha256") != _sha(body)):
            raise Phase5CExecutionError("RUNNER_COMPARISON_RECORD_INVALID")
        seen_comparisons.add(key)


def load_runner_result(path: str | Path, verified: VerifiedManifest) -> dict:
    """Load only a self-consistent immutable synthetic result and prediction pair."""
    folder = Path(path)
    if folder.is_symlink():
        raise Phase5CExecutionError("RUNNER_ARTIFACT_DIRECTORY_SYMLINK")
    result_path, predictions_path = folder / "result.json", folder / "predictions.json"
    integrity_path = folder / "integrity.json"
    try:
        entries = tuple(folder.iterdir())
        names = {entry.name for entry in entries}
        expected_names = {"result.json", "predictions.json", "integrity.json"}
        if expected_names - names:
            raise Phase5CExecutionError("RUNNER_ARTIFACT_FILE_MISSING")
        if (names - expected_names
                or any(entry.is_symlink() or not entry.is_file() for entry in entries)):
            raise Phase5CExecutionError("RUNNER_ARTIFACT_FILE_SET_INVALID")
        result_bytes = result_path.read_bytes()
        predictions_bytes = predictions_path.read_bytes()
        integrity_bytes = integrity_path.read_bytes()
    except Phase5CExecutionError:
        raise
    except FileNotFoundError as exc:
        raise Phase5CExecutionError("RUNNER_ARTIFACT_FILE_MISSING") from exc
    except OSError as exc:
        raise Phase5CExecutionError("RUNNER_ARTIFACT_IO_ERROR") from exc
    try:
        result = json.loads(result_bytes.decode("utf-8"))
        predictions = json.loads(predictions_bytes.decode("utf-8"))
        integrity = json.loads(integrity_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase5CExecutionError("RUNNER_ARTIFACT_JSON_INVALID") from exc
    if not all(isinstance(item, dict) for item in (result, predictions, integrity)):
        raise Phase5CExecutionError("RUNNER_ARTIFACT_SCHEMA_INVALID")
    if (result.get("schema_version") != RUNNER_SCHEMA
            or predictions.get("schema_version") != PREDICTION_SCHEMA
            or integrity.get("schema_version") != "bot2-phase5c-v3-runner-integrity-v1"):
        raise Phase5CExecutionError("RUNNER_ARTIFACT_SCHEMA_INVALID")
    if result.get("predictions") != predictions:
        raise Phase5CExecutionError("RUNNER_PREDICTION_ARTIFACT_CONTENT_MISMATCH")
    integrity_digest = integrity.get("integrity_sha256")
    if integrity_digest != _sha({k: v for k, v in integrity.items() if k != "integrity_sha256"}):
        raise Phase5CExecutionError("RUNNER_INTEGRITY_SIDECAR_HASH_MISMATCH")
    if (integrity.get("manifest_sha256") != verified.sha256
            or integrity.get("result_sha256") != _sha(result)
            or integrity.get("predictions_sha256") != _sha(predictions)
            or _sha(predictions) != result.get("prediction_artifact_sha256")
            or predictions_bytes != _canonical_json_bytes(predictions)
            or result_bytes != _canonical_json_bytes(result)
            or integrity_bytes != _canonical_json_bytes(integrity)):
        raise Phase5CExecutionError("RUNNER_ARTIFACT_FILE_HASH_MISMATCH")
    result["result_artifact_sha256"] = integrity["result_sha256"]
    verify_runner_result(result, verified)
    return result


def _verify_resume_identity(result: Mapping, verified: VerifiedManifest, *,
        market: str, horizon_minutes: int, seed: int) -> dict:
    """Permit reuse only for a complete immutable result with matching lineage."""
    verify_runner_result(result, verified)
    matrix = _orchestrate_synthetic_matrix(verified)
    if (result.get("market") != market or result.get("horizon_minutes") != horizon_minutes
            or result.get("seed") != seed
            or result.get("implementation_commit") != verified.pin["review_candidate_commit"]
            or result.get("dataset_manifest_sha256")
               != verified.data["source_dataset_manifest_sha256"]
            or result.get("matrix_orchestration") != matrix):
        raise Phase5CExecutionError("RESUME_LINEAGE_MISMATCH")
    for model_id, item in result["model_results"].items():
        artifact = item.get("artifact")
        if (not isinstance(artifact, Mapping)
                or artifact.get("model_id") != model_id.split(":", 1)[0]
                or artifact.get("manifest_sha256") != verified.sha256
                or artifact.get("dataset_manifest_sha256")
                   != verified.data["source_dataset_manifest_sha256"]
                or artifact.get("code_commit") != verified.pin["review_candidate_commit"]
                or artifact.get("market") != market
                or artifact.get("horizon_minutes") != horizon_minutes
                or artifact.get("random_seed") != seed
                or artifact.get("weights_sha256") != _sha(artifact.get("weights"))
                or artifact.get("artifact_sha256") != canonical_hash(
                    {key: value for key, value in artifact.items()
                     if key != "artifact_sha256"})):
            raise Phase5CExecutionError("RESUME_MODEL_ARTIFACT_LINEAGE_MISMATCH")
        if (set(item.get("calibration_hashes", {})) != set(HEADS)
                or set(item.get("abstention_hashes", {})) != set(HEADS)):
            raise Phase5CExecutionError("RESUME_CALIBRATION_OR_ABSTENTION_LINEAGE_MISSING")
    for record in result["predictions"]["predictions"]:
        item = result["model_results"].get(record["model_id"])
        if item is None and record["model_id"] in _NEURAL:
            item = result["model_results"].get(
                f"{record['model_id']}:{record.get('ablation_id')}")
        if (item is None
                or record.get("manifest_sha256") != verified.sha256
                or record.get("implementation_commit") != verified.pin["review_candidate_commit"]
                or record.get("calibration_artifact_sha256")
                   != item["calibration_hashes"].get(record.get("head"))
                or record.get("abstention_threshold") is None):
            raise Phase5CExecutionError("RESUME_PREDICTION_LINEAGE_MISMATCH")
    return dict(result)


def _run_synthetic_validation(verified: VerifiedManifest, *, market: str = "ES",
        horizon_minutes: int = 5, seed: int = 1,
        _stage_ref: dict | None = None,
        _matrix_status: Mapping | None = None) -> dict:
    """End-to-end synthetic cell using frozen settings; synthetic validation only."""
    m = _manifest(verified)
    if _matrix_status is None:
        _matrix_status = _orchestrate_synthetic_matrix(verified)
    if _stage_ref is not None: _stage_ref["stage"] = "synthetic_fixture_generation"
    if seed not in m["random_seeds"]: raise Phase5CExecutionError("SEED_NOT_IN_MANIFEST")
    dataset = build_synthetic_dataset(verified, seed=seed + 9000, market=market,
                                      horizon_minutes=horizon_minutes)
    if dataset.source_id != SYNTHETIC_SOURCE: raise Phase5CExecutionError("SYNTHETIC_SOURCE_REQUIRED")
    if _stage_ref is not None: _stage_ref["stage"] = "train_only_preprocessing"
    scaler = TrainingOnlyStandardizer().fit_observations(dataset.rows_by_partition["TRAIN"],
        market=market, verified_manifest=verified,
        code_commit=verified.pin["review_candidate_commit"])
    if _stage_ref is not None: _stage_ref["stage"] = "temporal_split_and_a0"
    predictions_by_a0 = _a0_predictions(build_authorized_split(verified, market=market,
        horizon_minutes=horizon_minutes, partition_rows=dataset.rows_by_partition,
        preprocessor=scaler, ablation_id="ALL"))
    split_all = build_authorized_split(verified, market=market, horizon_minutes=horizon_minutes,
        partition_rows=dataset.rows_by_partition, preprocessor=scaler, ablation_id="ALL")
    validate_authorized_split(split_all, verified)
    labels = split_all.validation.targets
    raw_a0_metrics = {model_id: {h: _metrics(probs[h], labels[h]) for h in HEADS}
                      for model_id, probs in predictions_by_a0.items()}
    selected_a0 = {h: min(_A0, key=lambda mid: (raw_a0_metrics[mid][h]["categorical_log_loss"],
        -raw_a0_metrics[mid][h]["macro_f1"], mid)) for h in HEADS}
    model_results, records, fairness = {}, [], []
    # All frozen A0 baselines share the same eligible evaluation observations.
    for model_id, per_head in predictions_by_a0.items():
        contract = create_model_input_contract(verified, model_id=model_id, seed=seed)
        for seq in split_all.validation.sequence_keys:
            contract_id, session_id, timestamp = seq[-1]
            decision_time = datetime.fromisoformat(timestamp)
            prior_rows = [row for row in split_all.canonical_rows["VALIDATION_AND_CALIBRATION"]
                if row.contract == contract_id and row.session_id == session_id
                and datetime.fromisoformat(row.exchange_timestamp_utc) < decision_time
                and datetime.fromisoformat(row.label_end_utc) <= decision_time]
            if model_id != "A0_TRAIN_MAJORITY" and not prior_rows:
                raise Phase5CExecutionError("A0_PRIOR_LABEL_INELIGIBLE")
            prior_end = (max(prior_rows, key=lambda row: row.exchange_timestamp_utc).label_end_utc
                         if model_id != "A0_TRAIN_MAJORITY" else None)
            validate_model_input_contract(contract, verified, actual_features=contract["features"],
                actual_sequence_shape=contract["sequence_shape"], actual_feature_mask=None,
                contains_target_labels=model_id != "A0_TRAIN_MAJORITY",
                latest_input_timestamp_utc=timestamp, decision_timestamp_utc=timestamp,
                label_information_end_utc=prior_end)
        state = {"baseline": model_id, "fit_partition": "TRAIN"}
        artifact = _make_model_artifact(model_id, seed, state, split_all, verified, scaler,
                                        {"ablation_id": "ALL", "ablation_sha256": "0" * 64})
        logits = {h: np.log(np.maximum(per_head[h], 1e-15)) for h in HEADS}
        summary, recs = _calibrated_predictions(model_id=model_id, seed=seed,
            logits_by_head=logits, artifact=artifact, split=split_all, verified=verified,
            scaler=scaler, ablation={"ablation_id": "ALL", "ablation_sha256": "0" * 64})
        model_results[model_id] = {"artifact": artifact, **summary,
            "raw_validation_metrics": raw_a0_metrics[model_id]}
        records.extend(recs)
        for condition in m["feature_ablations"]:
            condition_contract = create_ablation_contract(verified, condition["id"])
            fairness.append({"model_id": model_id, "input_contract_sha256": contract["contract_sha256"],
                "input_width": 0, "features": [], "input_ablation_id": "NO_FEATURE_INPUT",
                "condition_ablation_id": condition["id"],
                "condition_ablation_sha256": condition_contract["ablation_sha256"], "passed": True})

    ablation_runs = []
    shuffle_records = []
    for ablation_spec in m["feature_ablations"]:
        ablation_id = ablation_spec["id"]
        if _stage_ref is not None: _stage_ref["stage"] = f"real_model_ablation:{ablation_id}"
        contract = create_ablation_contract(verified, ablation_id)
        split = build_authorized_split(verified, market=market, horizon_minutes=horizon_minutes,
            partition_rows=dataset.rows_by_partition, preprocessor=scaler, ablation_id=ablation_id)
        for model_id in _NEURAL:
            input_contract = create_model_input_contract(verified, model_id=model_id,
                seed=seed, ablation_id=ablation_id)
            validate_model_input_contract(input_contract, verified,
                actual_features=input_contract["features"],
                actual_sequence_shape=input_contract["sequence_shape"],
                actual_feature_mask=input_contract["input_feature_mask"],
                latest_input_timestamp_utc=split.validation.sequence_keys[-1][-1][2],
                decision_timestamp_utc=split.validation.sequence_keys[-1][-1][2])
            if model_id == "A1_NUMPY_MULTIHEAD_MLP":
                from bot2.neural.model import MultiHeadMLP
                spec = m["architectures"][model_id]
                model = MultiHeadMLP(input_width=input_contract["flattened_width"],
                    hidden_width=spec["hidden_width"], seed=seed)
                model.fit(split.train.x.reshape(len(split.train.x), -1), split.train.targets,
                    epochs=m["a1_training"]["epochs"], learning_rate=m["a1_training"]["learning_rate"])
                probs = model.predict(split.validation.x.reshape(len(split.validation.x), -1))
                logits = {h: np.log(np.maximum(probs[h], 1e-15)) for h in HEADS}
                state = {"w": model.w.tolist(), "b": model.b.tolist(),
                    "heads": {k:v.tolist() for k,v in model.heads.items()},
                    "bias": {k:v.tolist() for k,v in model.bias.items()}}
                arch = "A1_NUMPY_MULTIHEAD_MLP"
            else:
                model = CausalTemporalConv(verified, seed=seed, ablation_id=ablation_id).fit(split)
                if model.parameter_count != 7417 or split.train.x.shape[1:] != (8, 24):
                    raise Phase5CExecutionError("A2_FIXED_ARCHITECTURE_CONTRACT_FAILED")
                logits, state, arch = model.predict_logits(split.validation.x), model.state(), "bot2-phase5c-a2-causal-tcn-v3"
            artifact = _make_model_artifact(model_id, seed, state, split, verified, scaler, contract)
            artifact["architecture_version"] = arch
            artifact["artifact_sha256"] = canonical_hash({k:v for k,v in artifact.items() if k != "artifact_sha256"})
            summary, recs = _calibrated_predictions(model_id=model_id, seed=seed,
                logits_by_head=logits, artifact=artifact, split=split, verified=verified,
                scaler=scaler, ablation=contract)
            model_results[f"{model_id}:{ablation_id}"] = {"artifact": artifact, **summary}
            records.extend(recs)
            fairness.append({"model_id": model_id,
                "input_contract_sha256": input_contract["contract_sha256"],
                "ablation_id": ablation_id, "ablation_sha256": contract["ablation_sha256"],
                "input_shape": list(split.validation.x.shape[1:]), "passed": True})
        mask_exec = execute_ablation_control(dataset.rows_by_partition["TRAIN"],
            verified_manifest=verified, preprocessor=scaler,
            model_id="A2_LEARNED_CAUSAL_TCN", seed=seed, ablation_id=ablation_id)
        verify_ablation_execution(mask_exec, rows=dataset.rows_by_partition["TRAIN"],
            preprocessor=scaler, verified_manifest=verified)
        if mask_exec.artifact["input_channels"] != 24: raise Phase5CExecutionError("ABLATION_WIDTH_CHANGED")
        ablation_runs.append(dict(mask_exec.artifact))
        for model_id in _NEURAL:
            for run_index in range(1, m["shuffled_label_control"]["runs_per_candidate_seed"] + 1):
                if _stage_ref is not None: _stage_ref["stage"] = f"shuffled_label_control:{model_id}:{ablation_id}:{run_index}"
                control = execute_shuffled_label_control(split, verified_manifest=verified,
                    candidate_id=model_id, candidate_seed=seed, run_index=run_index)
                verify_shuffled_label_control(control, split=split, verified_manifest=verified)
                assignment = control.train_targets_by_observation
                by_key = {(row.contract, row.session_id, row.exchange_timestamp_utc): row
                    for row in split.canonical_rows["TRAIN"]}
                shuffled_targets = {h: [] for h in HEADS}
                for sequence in split.train.sequence_keys:
                    row = by_key.get(sequence[-1])
                    if row is None or row.observation_id not in assignment:
                        raise Phase5CExecutionError("SHUFFLED_LABEL_TRAIN_IDENTITY_MISMATCH")
                    for head in HEADS:
                        shuffled_targets[head].append(assignment[row.observation_id][head])
                shuffled_targets = {h: np.asarray(v, dtype=np.int64)
                                   for h, v in shuffled_targets.items()}
                if model_id == "A1_NUMPY_MULTIHEAD_MLP":
                    from bot2.neural.model import MultiHeadMLP
                    spec = m["architectures"][model_id]
                    control_model = MultiHeadMLP(input_width=input_contract["flattened_width"],
                        hidden_width=spec["hidden_width"], seed=seed)
                    control_model.fit(split.train.x.reshape(len(split.train.x), -1),
                        shuffled_targets, epochs=m["a1_training"]["epochs"],
                        learning_rate=m["a1_training"]["learning_rate"])
                    control_probs = control_model.predict(
                        split.validation.x.reshape(len(split.validation.x), -1))
                    control_logits = {h: np.log(np.maximum(control_probs[h], 1e-15)) for h in HEADS}
                    control_state = {"w": control_model.w.tolist(), "b": control_model.b.tolist(),
                        "heads": {k:v.tolist() for k,v in control_model.heads.items()},
                        "bias": {k:v.tolist() for k,v in control_model.bias.items()}}
                else:
                    control_model = CausalTemporalConv(verified, seed=seed,
                        ablation_id=ablation_id).fit(split, shuffled_label_control=control)
                    control_logits = control_model.predict_logits(split.validation.x)
                    control_state = control_model.state()
                control_metrics = {h: _metrics(_softmax(control_logits[h]),
                    split.validation.targets[h]) for h in HEADS}
                shuffle_records.append({**dict(control.artifact),
                    "model_training_executed": True,
                    "model_artifact_sha256": canonical_hash(control_state),
                    "validation_metrics": control_metrics,
                    "validation_labels_changed": False,
                    "result_classification": "SYNTHETIC ENGINEERING RESULT"})

    if _stage_ref is not None: _stage_ref["stage"] = "prediction_alignment_and_result_provenance"
    identity_sets = {}
    for result_key in model_results:
        model_id = result_key.split(":", 1)[0]
        subset = [r for r in records if r["model_id"] == model_id and r["head"] == "direction"]
        identity_sets[model_id] = {r["observation_row_identity"] for r in subset}
    if not identity_sets or len({tuple(sorted(v)) for v in identity_sets.values()}) != 1:
        raise Phase5CExecutionError("PREDICTION_ALIGNMENT_MISMATCH")
    comparison_records = []
    for ablation_spec in m["feature_ablations"]:
        ablation_id = ablation_spec["id"]
        for head in HEADS:
            eligible_by_model, metadata_by_model = {}, {}
            for model_id in _A0 + _NEURAL:
                result_key = model_id if model_id in _A0 else f"{model_id}:{ablation_id}"
                model_result = model_results[result_key]
                model_records = [record for record in records
                    if record["model_id"] == model_id and record["head"] == head
                    and (model_id in _A0 or record["ablation_id"] == ablation_id)]
                row_ids = [record["observation_row_identity"] for record in model_records]
                eligible_by_model[model_id] = row_ids
                input_contract = create_model_input_contract(verified,
                    model_id=model_id, seed=seed,
                    ablation_id=("ALL" if model_id in _A0 else ablation_id))
                metadata_by_model[model_id] = {
                    "model_identity": model_result["artifact"]["artifact_sha256"],
                    "root": market, "horizon_minutes": horizon_minutes, "seed": seed,
                    "walk_forward_window": "GLOBAL_STATIC_VALIDATION_FIXTURE",
                    "ablation_id": ablation_id,
                    "control_condition": "REAL_LABELS",
                    "information_contract_identity": input_contract["contract_sha256"],
                    "eligible_observation_identity_sha256": _sha(row_ids),
                    "prediction_identity_sha256": _sha(model_records),
                    "calibration_identity": model_result["calibration_hashes"][head],
                    "abstention_identity": model_result["abstention_hashes"][head],
                    "metric_identity": _sha({"head": head, "definition": m["metrics"]}),
                        "metric_artifact_identity_sha256": _sha(
                            model_result["metrics"][head] if "metrics" in model_result
                            else model_result["raw_validation_metrics"][head]),
                    "result_evidence_identity_sha256": _sha({
                        "model_artifact_sha256": model_result["artifact"]["artifact_sha256"],
                        "prediction_identity_sha256": _sha(model_records),
                        "calibration_identity": model_result["calibration_hashes"][head]})}
            comparison = common_comparison_record(
                model_eligible_rows=eligible_by_model,
                model_metadata=metadata_by_model,
                metric_identity=_sha({"head": head, "ablation_id": ablation_id,
                                      "metric_definitions": m["metrics"]}))
            comparison_record = {"root": market, "horizon_minutes": horizon_minutes,
                "seed": seed, "ablation_id": ablation_id, "control_condition": "REAL_LABELS",
                "head": head, "classification": "SYNTHETIC ENGINEERING RESULT",
                **comparison}
            comparison_record["record_sha256"] = _sha({key: item for key, item
                in comparison_record.items() if key != "record_sha256"})
            comparison_records.append(comparison_record)
    pred_payload = {"schema_version": PREDICTION_SCHEMA,
        "classification": ["SYNTHETIC ENGINEERING RESULT", "NOT ES/NQ MARKET EVIDENCE",
            "NOT VALID FOR TRADING", "NOT VALID FOR MODEL-SELECTION CLAIMS"], "predictions": records}
    prediction_sha = _sha(pred_payload)
    result = {"schema_version": RUNNER_SCHEMA, "experiment_id": m["experiment_id"],
        "execution_mode": ExecutionMode.SYNTHETIC_VALIDATION.value,
        "status": "COMPLETE_SYNTHETIC_ENGINEERING_ONLY", "dataset_identity": dataset.source_id,
        "manifest_sha256": verified.sha256, "implementation_commit": verified.pin["review_candidate_commit"],
        "protocol_version": m["schema_version"], "dataset_manifest_sha256": split_all.dataset_manifest_sha256,
        "market": market, "horizon_minutes": horizon_minutes, "seed": seed,
        "training_partition_fingerprint": split_all.partition_fingerprints["TRAIN"],
        "validation_partition_fingerprint": split_all.partition_fingerprints["VALIDATION_AND_CALIBRATION"],
        "preprocessing": scaler.state(), "preprocessing_sha256": scaler.sha256,
        "model_results": model_results, "strongest_A0_by_head_validation_only": selected_a0,
        "metric_definitions": m["metrics"], "prediction_schema": PREDICTION_SCHEMA,
        "prediction_artifact_sha256": prediction_sha, "predictions": pred_payload,
        "prediction_alignment": {"same_validation_rows": True, "eligible_count": len(split_all.validation.x),
            "excluded_count": 0, "exclusion_reasons": {}},
        "ablation_executions": ablation_runs,
        "ablation_hashes": {x["ablation_id"]: x["ablation_sha256"] for x in ablation_runs},
        "shuffled_label_controls": shuffle_records,
        "shuffled_label_model_training_executed": True,
        "fairness_records": fairness,
        "comparison_records": comparison_records,
        "result_content_sha256": "", "protected_models_scored": 0,
        "protected_oos_scores_produced": 0, "protected_oos_execution": "NOT AUTHORIZED",
        "trading_authority": "NONE", "broker_path": False,
        "resume_policy": "Immutable completed artifact only; automatic resume disabled"}
    result["result_content_sha256"] = _sha({k:v for k,v in result.items() if k != "result_content_sha256"})
    result["result_artifact_sha256"] = _sha(result)
    result = _bind_matrix_orchestration(result, _matrix_status)
    verify_runner_result(result, verified)
    return result


def _run_synthetic_validation_bundle(verified: VerifiedManifest, *, output_directory: str | Path | None = None,
        market: str = "ES", horizon_minutes: int = 5, seed: int = 1) -> dict:
    """Internal fixture helper; supported execution goes through the bound public entry point.

    Existing output paths are immutable. A failed run is saved as a distinct
    failure-only artifact; it is never mistaken for a partial successful result.
    The runner never resumes from partial artifacts: retries use a new directory.
    """
    if output_directory is None:
        matrix_status = _orchestrate_synthetic_matrix(verified)
        result = _run_synthetic_validation(verified, market=market,
            horizon_minutes=horizon_minutes, seed=seed, _matrix_status=matrix_status)
        return result
    out = Path(output_directory)
    if os.path.lexists(out):
        raise Phase5CExecutionError("IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS")
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    stage = {"stage": "manifest_verification"}
    try:
        stage["stage"] = "matrix_orchestration"
        matrix_status = _orchestrate_synthetic_matrix(verified)
        result = _run_synthetic_validation(verified, market=market,
            horizon_minutes=horizon_minutes, seed=seed, _stage_ref=stage,
            _matrix_status=matrix_status)
        _immutable_write(staging / "predictions.json", result["predictions"])
        result.pop("result_artifact_sha256", None)
        result_sha = _immutable_write(staging / "result.json", result)
        integrity = {"schema_version": "bot2-phase5c-v3-runner-integrity-v1",
            "manifest_sha256": verified.sha256, "implementation_commit": verified.pin["review_candidate_commit"],
            "seed": seed, "execution_mode": ExecutionMode.SYNTHETIC_VALIDATION.value,
            "result_sha256": result_sha, "predictions_sha256": _sha(result["predictions"]),
            "integrity_sha256": ""}
        integrity["integrity_sha256"] = _sha({k: v for k, v in integrity.items()
                                              if k != "integrity_sha256"})
        _immutable_write(staging / "integrity.json", integrity)
        result["result_artifact_sha256"] = result_sha
        verify_runner_result(result, verified)
        os.rename(staging, out)
        return result
    except Exception as exc:
        # Remove any success-looking intermediate pair before recording failure.
        shutil.rmtree(staging, ignore_errors=True)
        # Publication is no-replace. If another writer claimed the path after
        # preflight, preserve its directory instead of turning it into our
        # failure receipt or replacing an empty directory.
        if os.path.lexists(out):
            if isinstance(exc, Phase5CExecutionError):
                raise
            raise Phase5CExecutionError("IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS") from exc
        staging.mkdir(parents=True, exist_ok=False)
        reason = getattr(exc, "reason_code", None) or str(exc) or type(exc).__name__
        failure = {"schema_version": "bot2-phase5c-v3-runner-failure-v1",
            "status": "FAILED", "execution_mode": ExecutionMode.SYNTHETIC_VALIDATION.value,
            "failure_stage": stage["stage"], "reason_code": reason,
            "manifest_sha256": verified.sha256 if is_verified_manifest(verified) else None,
            "market": market, "horizon_minutes": horizon_minutes, "seed": seed,
            "protected_models_scored": 0, "protected_oos_scores_produced": 0,
            "protected_oos_execution": "NOT AUTHORIZED", "trading_authority": "NONE",
            "broker_path": False, "resume_policy": "No partial artifact reuse; retry requires a new output path",
            "failure_artifact_sha256": ""}
        failure["failure_artifact_sha256"] = _sha({k:v for k,v in failure.items()
                                                  if k != "failure_artifact_sha256"})
        _immutable_write(staging / "failure.json", failure)
        try:
            os.rename(staging, out)
        except OSError as publish_error:
            shutil.rmtree(staging, ignore_errors=True)
            raise Phase5CExecutionError("FAILURE_ARTIFACT_PUBLISH_FAILED") from publish_error
        raise


def run_phase5c_experiment(mode: ExecutionMode | str, *, manifest_path: str | Path,
        external_anchor_path: str | Path, repo_root: str | Path | None = None,
        dataset_root: str | Path | None = None, output_directory: str | Path | None = None,
        market: str = "ES", horizon_minutes: int = 5, seed: int = 1,
        resume_existing: bool = False) -> dict:
    """Public entry point. Protected mode fails before manifest or data access."""
    try: selected = ExecutionMode(mode)
    except ValueError as exc: raise Phase5CExecutionError("EXECUTION_MODE_INVALID") from exc
    if selected is ExecutionMode.PROTECTED_OOS:
        raise Phase5CExecutionError("PROTECTED_OOS_NOT_AUTHORIZED")
    verified = load_verified_manifest(manifest_path, external_anchor_path=external_anchor_path)
    if selected is ExecutionMode.SYNTHETIC_VALIDATION:
        if repo_root is None:
            raise Phase5CExecutionError("IMPLEMENTATION_REPOSITORY_REQUIRED")
        try:
            verify_git_binding(repo_root, expected_commit=verified.pin["review_candidate_commit"])
        except ValueError as exc:
            raise Phase5CExecutionError(str(exc)) from exc
        if resume_existing:
            if output_directory is None:
                raise Phase5CExecutionError("RESUME_OUTPUT_DIRECTORY_REQUIRED")
            try:
                saved = load_runner_result(output_directory, verified)
            except Phase5CExecutionError as exc:
                raise Phase5CExecutionError("RESUME_ARTIFACT_NOT_REUSABLE") from exc
            return _verify_resume_identity(saved, verified, market=market,
                horizon_minutes=horizon_minutes, seed=seed)
        return _run_synthetic_validation_bundle(verified, output_directory=output_directory,
            market=market, horizon_minutes=horizon_minutes, seed=seed)
    if repo_root is None or dataset_root is None:
        raise Phase5CExecutionError("PREFLIGHT_PATHS_REQUIRED")
    from .runner import run_preflight
    return run_preflight(repo_root, dataset_root, external_anchor_path=external_anchor_path)
