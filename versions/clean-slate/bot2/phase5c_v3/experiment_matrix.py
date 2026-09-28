"""Manifest-derived Phase 5C-Y matrix, walk-forward, and evidence gates.

Engineering controls only: no protected-dataset reads, broker path, or OOS
authorization is added by this module.
"""
from __future__ import annotations

import hashlib
import copy
import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from itertools import product
from pathlib import Path
from typing import Mapping, Sequence

from .data_integrity import MarketObservation, partition_fingerprint
from .manifest import VerifiedManifest, canonical_bytes, canonical_hash, is_verified_manifest

CELL_SCHEMA = "bot2-phase5c-v3-experiment-cell-v1"
LEDGER_SCHEMA = "bot2-phase5c-v3-expected-cell-ledger-v1"
WINDOW_SCHEMA = "bot2-phase5c-v3-walk-forward-window-v1"
COMPARISON_SCHEMA = "bot2-phase5c-v3-common-comparison-v1"
RESUME_SCHEMA = "bot2-phase5c-v3-resume-artifact-v1"
CELL_RESULT_SCHEMA = "bot2-phase5c-v3-cell-result-v1"
STAGE_CHECKPOINT_SCHEMA = "bot2-phase5c-v3-stage-checkpoint-v1"
ENGINEERING_COVERAGE_SCHEMA = "bot2-phase5c-v3-engineering-coverage-v1"
_CELL_STAGES = ("DATA_PARTITION_VERIFIED", "PREPROCESSING_COMPLETE",
    "MODEL_TRAINING_COMPLETE", "CHECKPOINT_SELECTED", "CALIBRATION_COMPLETE",
    "PREDICTIONS_COMPLETE", "METRICS_COMPLETE", "RESULT_PUBLISHED")
_A0 = ("A0_PREVIOUS_LABEL_PERSISTENCE", "A0_TRAIN_MAJORITY",
       "A0_TRAIN_TRANSITION_MATRIX")
_NEURAL = ("A1_NUMPY_MULTIHEAD_MLP", "A2_LEARNED_CAUSAL_TCN")
_IDENTITY_FIELDS = ("protocol_version", "manifest_sha256", "implementation_commit",
    "dataset_identity", "root", "horizon_minutes", "seed", "walk_forward_window",
    "model_id", "ablation_id", "control_condition", "head")
_RESUME_LINEAGE_FIELDS = ("protocol_version", "manifest_sha256", "implementation_commit",
    "dataset_identity", "experiment_cell_sha256", "partition_fingerprints",
    "model_identity", "ablation_identity", "seed", "preprocessing_sha256",
    "model_sha256", "calibration_sha256", "prediction_sha256")


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def implementation_source_identity() -> str:
    """Digest the executable source that determines synthetic computation."""
    root = Path(__file__).parent
    paths = (root / "experiment_matrix.py", root / "experiment_runner.py",
        root / "data_integrity.py", root / "experiment_controls.py",
        root / "model.py", root.parent / "neural" / "model.py")
    return _sha({path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths})


def _manifest(verified: VerifiedManifest) -> dict:
    if not is_verified_manifest(verified) or not verified.external_anchor_content_verified:
        raise ValueError("EXTERNALLY_ANCHORED_MANIFEST_REQUIRED")
    return verified.data


def _is_sha256(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    """Frozen dates and policy mechanically derived from the manifest."""
    window_id: str
    train: tuple[str, str]
    validation: tuple[str, str]
    calibration: tuple[str, str]
    test: tuple[str, str]
    purge_minutes: int
    embargo_minutes: int
    max_label_horizon_minutes: int
    fingerprint: str

    def canonical_content(self) -> dict:
        return {"schema_version": WINDOW_SCHEMA, "window_id": self.window_id,
            "train_inclusive": list(self.train),
            "validation_inclusive": list(self.validation),
            "calibration_inclusive": list(self.calibration),
            "calibration_is_validation": self.calibration == self.validation,
            "test_inclusive": list(self.test), "purge_minutes": self.purge_minutes,
            "embargo_minutes": self.embargo_minutes,
            "max_label_horizon_minutes": self.max_label_horizon_minutes}


def derive_walk_forward_windows(verified: VerifiedManifest) -> tuple[WalkForwardWindow, ...]:
    """Use only frozen manifest windows; arbitrary caller date ranges are rejected."""
    manifest = _manifest(verified)
    policy = manifest["purge_embargo"]
    result, seen = [], set()
    for item in manifest["walk_forward_windows_inclusive"]:
        window_id = item.get("id")
        if not isinstance(window_id, str) or not window_id or window_id in seen:
            raise ValueError("WALK_FORWARD_WINDOW_ID_INVALID_OR_DUPLICATED")
        seen.add(window_id)
        train, validation, test = (tuple(item[key]) for key in ("train", "validation", "test"))
        if any(len(span) != 2 for span in (train, validation, test)):
            raise ValueError("WALK_FORWARD_DATE_RANGE_INVALID")
        parsed = [(date.fromisoformat(start), date.fromisoformat(end))
                  for start, end in (train, validation, test)]
        if any(start > end for start, end in parsed):
            raise ValueError("WALK_FORWARD_DATE_RANGE_REVERSED")
        if not (parsed[0][1] < parsed[1][0] and parsed[1][1] < parsed[2][0]):
            raise ValueError("WALK_FORWARD_PARTITIONS_OVERLAP_OR_REVERSED")
        # Frozen protocol declares validation and calibration as one partition.
        content = {"schema_version": WINDOW_SCHEMA, "window_id": window_id,
            "train_inclusive": list(train), "validation_inclusive": list(validation),
            "calibration_inclusive": list(validation), "calibration_is_validation": True,
            "test_inclusive": list(test), "purge_minutes": int(policy["purge_minutes"]),
            "embargo_minutes": int(policy["embargo_minutes"]),
            "max_label_horizon_minutes": int(policy["max_label_horizon_minutes"])}
        result.append(WalkForwardWindow(window_id, train, validation, validation, test,
            int(policy["purge_minutes"]), int(policy["embargo_minutes"]),
            int(policy["max_label_horizon_minutes"]), _sha(content)))
    if not result:
        raise ValueError("WALK_FORWARD_WINDOWS_MISSING")
    return tuple(result)


def _cell_identity(verified: VerifiedManifest, *, root: str, horizon: int,
        seed: int | str, window_id: str, model_id: str, ablation_id: str,
        control_condition: str, head: str) -> dict:
    manifest = _manifest(verified)
    return {"schema_version": CELL_SCHEMA, "protocol_version": manifest["schema_version"],
        "manifest_sha256": verified.sha256,
        "implementation_commit": verified.pin["review_candidate_commit"],
        "dataset_identity": manifest["source_dataset_manifest_sha256"],
        "root": root, "horizon_minutes": horizon, "seed": seed,
        "walk_forward_window": window_id, "model_id": model_id,
        "ablation_id": ablation_id, "control_condition": control_condition,
        "head": head}


def expected_cell_ledger(verified: VerifiedManifest) -> dict:
    """Generate all frozen model/ablation/control cells before execution.

    Deterministic A0 baselines use an explicit ``DETERMINISTIC`` seed token.
    A1/A2 cross the three frozen candidate seeds. Shuffled-label controls are
    ALL-feature only and cross each candidate seed with each frozen shuffle
    seed, as specified by the manifest.
    """
    manifest = _manifest(verified)
    roots = tuple(sorted(manifest["source_dataset"]["contracts"]))
    horizons = tuple(manifest["target_specification"]["horizons_minutes"])
    heads = tuple(manifest["target_specification"]["class_indices"])
    seeds = tuple(manifest["random_seeds"])
    ablations = tuple(item["id"] for item in manifest["feature_ablations"])
    windows = tuple(item.window_id for item in derive_walk_forward_windows(verified))
    if (roots != ("ES", "NQ") or not horizons or not heads or not seeds or not ablations
            or len(set(horizons)) != len(horizons) or len(set(heads)) != len(heads)
            or len(set(seeds)) != len(seeds) or len(set(ablations)) != len(ablations)):
        raise ValueError("FROZEN_MATRIX_DIMENSION_INVALID")
    cells = []

    def add(root: str, horizon: int, seed: int | str, window: str, model: str,
            ablation: str, control: str, head: str) -> None:
        identity = _cell_identity(verified, root=root, horizon=horizon, seed=seed,
            window_id=window, model_id=model, ablation_id=ablation,
            control_condition=control, head=head)
        cells.append({"cell_sha256": _sha({key: identity[key] for key in _IDENTITY_FIELDS}),
            "identity": identity, "status": "PENDING", "result_artifact_sha256": None,
            "failure_reason_code": None})

    for root, horizon, window, model, ablation, head in product(
            roots, horizons, windows, _A0, ablations, heads):
        add(root, horizon, "DETERMINISTIC", window, model, ablation, "NONE", head)
    for root, horizon, seed, window, model, ablation, head in product(
            roots, horizons, seeds, windows, _NEURAL, ablations, heads):
        add(root, horizon, seed, window, model, ablation, "NONE", head)
    for root, horizon, seed, shuffle_seed, window, model, head in product(
            roots, horizons, seeds, manifest["shuffled_label_control"]["seeds"],
            windows, _NEURAL, heads):
        add(root, horizon, seed, window, model, "ALL",
            f"SHUFFLED_TRAIN_LABELS:{shuffle_seed}", head)
    cells.sort(key=lambda cell: cell["cell_sha256"])
    if len({cell["cell_sha256"] for cell in cells}) != len(cells):
        raise ValueError("EXPERIMENT_CELL_IDENTITY_COLLISION")
    ledger = {"schema_version": LEDGER_SCHEMA, "manifest_sha256": verified.sha256,
        "implementation_commit": verified.pin["review_candidate_commit"],
        "expected_cell_count": len(cells), "cells": cells, "status": "PENDING"}
    ledger["ledger_sha256"] = _sha(ledger)
    return ledger


def select_engineering_coverage_cells(verified: VerifiedManifest) -> dict:
    """Select a deterministic, performance-blind coverage set from the ledger.

    The 24 comparison groups span every root/horizon/WF combination. Their
    ablations rotate structurally over the frozen list, and each group includes
    all three A0s plus A1/A2. Every frozen ablation is covered by both neural
    candidates; every shuffle seed is covered by both candidates as well.
    This is an engineering subset, never the frozen experiment itself.
    """
    manifest = _manifest(verified)
    ledger = expected_cell_ledger(verified)
    by_key = {}
    for cell in ledger["cells"]:
        identity = cell["identity"]
        key = (identity["root"], identity["horizon_minutes"],
            identity["walk_forward_window"], identity["model_id"],
            identity["ablation_id"], identity["control_condition"],
            identity["seed"], identity["head"])
        by_key[key] = cell
    roots = tuple(sorted(manifest["source_dataset"]["contracts"]))
    horizons = tuple(manifest["target_specification"]["horizons_minutes"])
    windows = tuple(item.window_id for item in derive_walk_forward_windows(verified))
    ablations = tuple(item["id"] for item in manifest["feature_ablations"])
    head = "direction"
    seed = tuple(manifest["random_seeds"])[0]
    selected: dict[str, dict] = {}
    comparison_groups = []
    group_number = 0
    for root in roots:
        for horizon in horizons:
            for window_id in windows:
                ablation = ablations[group_number % len(ablations)]
                members = {}
                for model_id in _A0:
                    cell = by_key[(root, horizon, window_id, model_id,
                        ablation, "NONE", "DETERMINISTIC", head)]
                    selected[cell["cell_sha256"]] = cell
                    members[model_id] = cell["cell_sha256"]
                for model_id in _NEURAL:
                    cell = by_key[(root, horizon, window_id, model_id,
                        ablation, "NONE", seed, head)]
                    selected[cell["cell_sha256"]] = cell
                    members[model_id] = cell["cell_sha256"]
                group_identity = {"root": root, "horizon_minutes": horizon,
                    "walk_forward_window": window_id, "ablation_id": ablation,
                    "seed": seed, "control_condition": "NONE", "head": head}
                comparison_groups.append({"group_id": _sha(group_identity),
                    "identity": group_identity, "cell_ids_by_model": members})
                group_number += 1
    shuffle_seeds = tuple(manifest["shuffled_label_control"]["seeds"])
    axes = tuple((root, horizon, window_id) for root in roots
        for horizon in horizons for window_id in windows)
    for model_index, model_id in enumerate(_NEURAL):
        for control_index, shuffle_seed in enumerate(shuffle_seeds):
            root, horizon, window_id = axes[(model_index * len(shuffle_seeds)
                + control_index) % len(axes)]
            cell = by_key[(root, horizon, window_id, model_id, "ALL",
                f"SHUFFLED_TRAIN_LABELS:{shuffle_seed}", seed, head)]
            selected[cell["cell_sha256"]] = cell

    selected_ids = sorted(selected)
    requirements = {"roots": {}, "horizons_minutes": {}, "walk_forward_windows": {},
        "models": {}, "neural_ablations": {}, "controls_by_model": {}}
    for cell_id in selected_ids:
        identity = selected[cell_id]["identity"]
        for section, value in (("roots", identity["root"]),
                ("horizons_minutes", identity["horizon_minutes"]),
                ("walk_forward_windows", identity["walk_forward_window"])):
            requirements[section].setdefault(str(value), []).append(cell_id)
        requirements["models"].setdefault(identity["model_id"], []).append(cell_id)
        if identity["model_id"] in _NEURAL:
            requirements["neural_ablations"].setdefault(
                f"{identity['model_id']}:{identity['ablation_id']}", []).append(cell_id)
            control = identity["control_condition"]
            requirements["controls_by_model"].setdefault(
                f"{identity['model_id']}:{control}", []).append(cell_id)
    result = {"schema_version": ENGINEERING_COVERAGE_SCHEMA,
        "classification": "SYNTHETIC ENGINEERING COVERAGE ONLY",
        "manifest_sha256": verified.sha256,
        "implementation_identity": verified.pin["review_candidate_commit"],
        "implementation_source_sha256": implementation_source_identity(),
        "selection_rule": "STRUCTURAL_DETERMINISTIC_COVERING_SET_V1",
        "selection_uses_predictive_performance": False,
        "expected_frozen_matrix_cell_count": ledger["expected_cell_count"],
        "selected_cell_count": len(selected_ids), "selected_cell_ids": selected_ids,
        "requirements_to_cell_ids": requirements,
        "comparison_groups": comparison_groups,
        "frozen_experiment_status": "NOT_EXECUTED",
        "protected_oos_execution": "NOT AUTHORIZED",
        "protected_models_scored": 0, "protected_oos_scores_produced": 0,
        "trading_authority": "NONE"}
    result["coverage_manifest_sha256"] = _sha(result)
    return result


def verify_engineering_coverage(verified: VerifiedManifest, *, coverage_manifest: Mapping,
        result_artifacts: Mapping[str, Mapping], comparison_records: Sequence[Mapping]) -> dict:
    """Verify that executed result artifacts cover every declared structural path."""
    expected = expected_cell_ledger(verified)
    expected_by_id = {cell["cell_sha256"]: cell for cell in expected["cells"]}
    coverage = copy.deepcopy(dict(coverage_manifest))
    digest = coverage.pop("coverage_manifest_sha256", None)
    selected = coverage.get("selected_cell_ids")
    if (digest != _sha(coverage) or coverage.get("schema_version") != ENGINEERING_COVERAGE_SCHEMA
            or coverage.get("manifest_sha256") != verified.sha256
            or coverage.get("implementation_source_sha256") != implementation_source_identity()
            or coverage.get("frozen_experiment_status") != "NOT_EXECUTED"
            or coverage.get("selection_uses_predictive_performance") is not False
            or not isinstance(selected, list) or len(selected) != len(set(selected))
            or any(cell_id not in expected_by_id for cell_id in selected)):
        raise ValueError("ENGINEERING_COVERAGE_MANIFEST_INVALID")
    expected_coverage = select_engineering_coverage_cells(verified)
    if dict(coverage_manifest) != expected_coverage:
        raise ValueError("ENGINEERING_COVERAGE_SELECTION_NOT_CANONICAL")
    if set(result_artifacts) != set(selected):
        raise ValueError("ENGINEERING_COVERAGE_RESULT_SET_INCOMPLETE")
    verified_results = {}
    for cell_id in selected:
        verified_results[cell_id] = load_cell_result_artifact(verified,
            cell=expected_by_id[cell_id], artifact=result_artifacts[cell_id])
        identity = expected_by_id[cell_id]["identity"]
        model_artifact = verified_results[cell_id]["result"]["model_artifact"]
        if identity["model_id"] == "A2_LEARNED_CAUSAL_TCN" and (
                model_artifact.get("input_shape") != [8, 24]
                or model_artifact.get("parameter_count") != 7417):
            raise ValueError("ENGINEERING_COVERAGE_A2_CONTRACT_INVALID")
        if identity["control_condition"] != "NONE" and not model_artifact.get(
                "training_label_control_sha256"):
            raise ValueError("ENGINEERING_COVERAGE_CONTROL_NOT_EXECUTED")
    requirements = coverage.get("requirements_to_cell_ids", {})
    for section, required_values in (("roots", set(verified.data["source_dataset"]["contracts"])),
            ("horizons_minutes", set(map(str, verified.data["target_specification"]["horizons_minutes"]))),
            ("walk_forward_windows", {window.window_id for window in derive_walk_forward_windows(verified)})):
        actual = requirements.get(section, {})
        if set(actual) != required_values or any(not ids or not (set(ids) & set(selected))
                for ids in actual.values()):
            raise ValueError("ENGINEERING_COVERAGE_DIMENSION_MISSING")
    model_values = set(_A0 + _NEURAL)
    if set(requirements.get("models", {})) != model_values or any(
            not ids for ids in requirements["models"].values()):
        raise ValueError("ENGINEERING_COVERAGE_MODEL_PATH_MISSING")
    ablation_values = {f"{model}:{ablation['id']}" for model in _NEURAL
        for ablation in verified.data["feature_ablations"]}
    if set(requirements.get("neural_ablations", {})) != ablation_values or any(
            not ids for ids in requirements["neural_ablations"].values()):
        raise ValueError("ENGINEERING_COVERAGE_ABLATION_PATH_MISSING")
    required_controls = {f"{model}:NONE" for model in _NEURAL}
    required_controls.update(f"{model}:SHUFFLED_TRAIN_LABELS:{seed}" for model in _NEURAL
        for seed in verified.data["shuffled_label_control"]["seeds"])
    if (set(requirements.get("controls_by_model", {})) != required_controls
            or any(not ids for ids in requirements["controls_by_model"].values())):
        raise ValueError("ENGINEERING_COVERAGE_CONTROL_PATH_MISSING")
    comparison_by_id = {record.get("group_id"): record for record in comparison_records}
    groups = coverage.get("comparison_groups", [])
    if (len(groups) != len(comparison_by_id)
            or {group.get("group_id") for group in groups} != set(comparison_by_id)):
        raise ValueError("ENGINEERING_COVERAGE_COMPARISON_GROUP_MISSING")
    for group in groups:
        record = comparison_by_id[group["group_id"]]
        if (record.get("comparison_status") != "COMPLETE_SYNTHETIC_ENGINEERING_ONLY"
                or record.get("identity") != group.get("identity")
                or record.get("common_comparison_row_count", 0) <= 0
                or record.get("common_comparison_row_sha256") is None
                or set(record.get("models", {})) != set(_A0 + _NEURAL)):
            raise ValueError("ENGINEERING_COVERAGE_COMPARISON_INVALID")
        artifacts = [verified_results[cell_id] for cell_id in group["cell_ids_by_model"].values()]
        row_sets = [artifact["result"]["prediction_artifact"]["row_identities"]
                    for artifact in artifacts]
        expected_common_rows = [row for row in row_sets[0]
            if all(row in set(other_rows) for other_rows in row_sets[1:])] if row_sets else []
        comparison_record = record
        model_records = comparison_record.get("models", {})
        universe_ordered = list(dict.fromkeys(row for rows in row_sets for row in rows))
        raw_rows_match = (set(model_records) == set(_A0 + _NEURAL)
            and all(model_records[model_id].get("raw_eligible_row_ids")
                == verified_results[group["cell_ids_by_model"][model_id]]["result"]
                    ["prediction_artifact"]["row_identities"]
                and model_records[model_id].get("raw_eligible_row_sha256")
                    == _sha(model_records[model_id].get("raw_eligible_row_ids"))
                and model_records[model_id].get("metadata", {}).get("metrics")
                    == verified_results[group["cell_ids_by_model"][model_id]]["result"]["metrics"]
                and model_records[model_id].get("metadata", {}).get("model_artifact_sha256")
                    == verified_results[group["cell_ids_by_model"][model_id]]["model_artifact_sha256"]
                and model_records[model_id].get("excluded_row_ids")
                    == [row for row in universe_ordered
                        if row not in set(model_records[model_id].get("raw_eligible_row_ids", []))]
                and model_records[model_id].get("excluded_row_count")
                    == len(universe_ordered) - len(model_records[model_id].get("raw_eligible_row_ids", []))
                for model_id in _A0 + _NEURAL))
        if (len(artifacts) != len(_A0 + _NEURAL)
                or len({artifact["partition_fingerprints"]["VALIDATION_AND_CALIBRATION"]
                        for artifact in artifacts}) != 1
                or not row_sets or any(rows != row_sets[0] for rows in row_sets[1:])
                or comparison_record.get("common_comparison_row_ids") != expected_common_rows
                or comparison_record.get("common_comparison_row_count") != len(expected_common_rows)
                or comparison_record.get("common_comparison_row_sha256") != _sha(expected_common_rows)
                or not raw_rows_match
                or comparison_record.get("performance_used_for_row_selection") is not False
                or comparison_record.get("alignment_policy") != "AUTHORIZED_ELIGIBILITY_INTERSECTION_ONLY"
                or comparison_record.get("record_sha256") != _sha({key: value
                    for key, value in comparison_record.items() if key != "record_sha256"})):
            raise ValueError("ENGINEERING_COVERAGE_ROW_ALIGNMENT_FAILED")
    return {"status": "COMPLETE", "selected_cell_count": len(selected),
        "verified_cell_result_count": len(verified_results),
        "verified_comparison_group_count": len(groups),
        "coverage_manifest_sha256": coverage_manifest["coverage_manifest_sha256"],
        "frozen_experiment_status": "NOT_EXECUTED",
        "protected_models_scored": 0, "protected_oos_scores_produced": 0,
        "trading_authority": "NONE"}


def reconcile_matrix_dispatch(verified: VerifiedManifest,
        dispatch_records: Sequence[Mapping]) -> dict:
    """Reconcile runner dispatch against the manifest-derived expected IDs.

    A dispatch receipt proves only that a canonical cell was handed to the
    execution router. It is not a result artifact and cannot make a cell
    COMPLETE. Missing, repeated, unknown, or identity-altered receipts are
    surfaced with stable reason codes.
    """
    expected = expected_cell_ledger(verified)
    expected_by_id = {cell["cell_sha256"]: cell for cell in expected["cells"]}
    observed, duplicates, unknown, mismatches = set(), set(), set(), set()
    reported_complete = reported_failed = 0
    for record in dispatch_records:
        cell_id = record.get("cell_sha256")
        if cell_id not in expected_by_id:
            unknown.add(str(cell_id))
            continue
        if cell_id in observed:
            duplicates.add(cell_id)
        observed.add(cell_id)
        if record.get("identity") != expected_by_id[cell_id]["identity"]:
            mismatches.add(cell_id)
        state = record.get("status")
        if state == "COMPLETE":
            reported_complete += 1
        elif state == "FAILED":
            reported_failed += 1
    missing = set(expected_by_id) - observed
    reason_codes = []
    if missing: reason_codes.append("MISSING_CELL")
    if duplicates: reason_codes.append("DUPLICATE_CELL")
    if unknown: reason_codes.append("UNKNOWN_CELL")
    if mismatches: reason_codes.append("CELL_IDENTITY_MISMATCH")
    structurally_valid = not reason_codes and len(observed) == len(expected_by_id)
    return {"schema_version": "bot2-phase5c-v3-matrix-dispatch-reconciliation-v1",
        "manifest_sha256": verified.sha256,
        "expected_cell_count": len(expected_by_id),
        "dispatched_cell_count": len(dispatch_records),
        "unique_dispatched_cell_count": len(observed),
        # Receipt labels are untrusted claims until terminal artifacts load.
        "complete_cell_count": 0, "failed_cell_count": 0,
        "reported_complete_receipt_count": reported_complete,
        "reported_failed_receipt_count": reported_failed,
        "incomplete_cell_count": len(expected_by_id),
        "missing_cell_count": len(missing), "duplicate_cell_count": len(duplicates),
        "unknown_cell_count": len(unknown), "identity_mismatch_count": len(mismatches),
        "reason_codes": reason_codes,
        "dispatch_reconciled": structurally_valid,
        "experiment_complete": False,
        "completion_reason_code": "CELL_RESULT_ARTIFACTS_REQUIRED",
        "classification": ["SYNTHETIC ENGINEERING RESULT", "NOT ES/NQ MARKET EVIDENCE",
            "NOT VALID FOR TRADING", "NOT VALID FOR MODEL-SELECTION CLAIMS"],
        "protected_models_scored": 0, "protected_oos_scores_produced": 0,
        "trading_authority": "NONE"}


def create_cell_result_artifact(verified: VerifiedManifest, *, cell: Mapping,
        partition_fingerprints: Mapping[str, str], result: Mapping) -> dict:
    """Create a versioned terminal artifact whose component hashes bind its contents.

    Result payloads are deliberately explicit. A caller cannot supply just a
    metric or a foreign artifact hash and have it promoted to a completed cell.
    """
    manifest = _manifest(verified)
    expected = expected_cell_ledger(verified)
    cell_id = cell.get("cell_sha256")
    frozen = next((item for item in expected["cells"] if item["cell_sha256"] == cell_id), None)
    if frozen is None or cell.get("identity") != frozen["identity"]:
        raise ValueError("EXPERIMENT_CELL_IDENTITY_MISMATCH")
    required_partitions = {"TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST"}
    if (set(partition_fingerprints) != required_partitions
            or not all(_is_sha256(value) for value in partition_fingerprints.values())):
        raise ValueError("WALK_FORWARD_PARTITION_FINGERPRINTS_INVALID")
    required_payload = {"information_contract", "preprocessing_artifact", "model_artifact",
        "checkpoint_artifact", "calibration_artifact", "abstention_artifact", "prediction_artifact",
        "common_comparison_row_identity", "metric_definition", "metrics"}
    if not isinstance(result, Mapping) or set(result) != required_payload:
        raise ValueError("CELL_RESULT_PAYLOAD_SCHEMA_INVALID")
    for key in ("information_contract", "prediction_artifact", "metric_definition", "metrics"):
        if not isinstance(result.get(key), Mapping) or not result[key]:
            raise ValueError("CELL_RESULT_PAYLOAD_INVALID")
    for key in ("preprocessing_artifact", "model_artifact", "checkpoint_artifact",
                "calibration_artifact", "abstention_artifact"):
        if result[key] is not None and not isinstance(result[key], Mapping):
            raise ValueError("CELL_RESULT_PAYLOAD_INVALID")
    row_identity = result["common_comparison_row_identity"]
    if row_identity is not None and not _is_sha256(row_identity):
        raise ValueError("COMMON_COMPARISON_ROW_IDENTITY_INVALID")
    component_hashes = {key: (_sha(result[key]) if result[key] is not None else None)
        for key in ("information_contract", "preprocessing_artifact", "model_artifact",
                    "checkpoint_artifact", "calibration_artifact", "abstention_artifact", "prediction_artifact",
                    "metric_definition", "metrics")}
    if not _is_sha256(result["information_contract"].get("contract_sha256", "")):
        raise ValueError("INFORMATION_CONTRACT_IDENTITY_INVALID")
    if not _is_sha256(result["prediction_artifact"].get("prediction_sha256", "")):
        raise ValueError("PREDICTION_ARTIFACT_IDENTITY_INVALID")
    if not _is_sha256(result["metric_definition"].get("metric_definition_sha256", "")):
        raise ValueError("METRIC_DEFINITION_IDENTITY_INVALID")
    if component_hashes["preprocessing_artifact"] is None or component_hashes["model_artifact"] is None:
        raise ValueError("REQUIRED_COMPUTATION_ARTIFACT_MISSING")
    classification = ["SYNTHETIC ENGINEERING RESULT", "NOT ES/NQ MARKET EVIDENCE",
        "NOT VALID FOR TRADING", "NOT VALID FOR MODEL-SELECTION CLAIMS"]
    identity = frozen["identity"]
    artifact = {"schema_version": CELL_RESULT_SCHEMA, "completion_status": "COMPLETE",
        "status": "COMPLETE",
        "cell_sha256": cell_id, "identity": frozen["identity"],
        "manifest_sha256": verified.sha256,
        "implementation_identity": identity["implementation_commit"],
        "dataset_identity": manifest["source_dataset_manifest_sha256"],
        "root": identity["root"], "horizon_minutes": identity["horizon_minutes"],
        "seed": identity["seed"], "walk_forward_window": identity["walk_forward_window"],
        "model_id": identity["model_id"], "ablation_id": identity["ablation_id"],
        "control_identity": identity["control_condition"], "target_head": identity["head"],
        "partition_fingerprints": dict(sorted(partition_fingerprints.items())),
        "information_contract_identity": result["information_contract"]["contract_sha256"],
        "preprocessing_artifact_sha256": component_hashes["preprocessing_artifact"],
        "model_artifact_sha256": component_hashes["model_artifact"],
        "checkpoint_sha256": component_hashes["checkpoint_artifact"],
        "calibration_artifact_sha256": component_hashes["calibration_artifact"],
        "abstention_artifact_sha256": component_hashes["abstention_artifact"],
        "prediction_artifact_sha256": result["prediction_artifact"]["prediction_sha256"],
        "common_comparison_row_identity": row_identity,
        "metric_definition_identity": result["metric_definition"]["metric_definition_sha256"],
        "component_hashes": component_hashes,
        "classification": classification, "result": dict(result),
        "protected_models_scored": 0, "protected_oos_scores_produced": 0,
        "protected_oos_execution": "NOT AUTHORIZED", "trading_authority": "NONE"}
    artifact["result_sha256"] = _sha(artifact["result"])
    artifact["artifact_sha256"] = _sha(artifact)
    _verify_cell_result(verified, frozen, artifact)
    return artifact


def transition_cell(ledger: Mapping, *, verified: VerifiedManifest, cell_sha256: str,
        status: str, result_artifact: Mapping | None = None,
        failure_reason_code: str | None = None) -> dict:
    """Apply a checked cell lifecycle transition; completion requires verified results."""
    if ledger.get("schema_version") != LEDGER_SCHEMA or ledger.get("manifest_sha256") != verified.sha256:
        raise ValueError("MATRIX_LEDGER_MANIFEST_MISMATCH")
    if ledger.get("ledger_sha256") != _sha({k: v for k, v in ledger.items()
                                             if k != "ledger_sha256"}):
        raise ValueError("MATRIX_LEDGER_HASH_MISMATCH")
    transitions = {"PENDING": {"DISPATCHED"}, "DISPATCHED": {"RUNNING", "FAILED"},
        "RUNNING": {"PARTIAL", "COMPLETE", "FAILED"},
        "PARTIAL": {"DISPATCHED", "RUNNING", "FAILED"},
        "COMPLETE": set(), "FAILED": set()}
    if status not in transitions:
        raise ValueError("MATRIX_CELL_STATUS_INVALID")
    updated = copy.deepcopy(dict(ledger))
    matches = [cell for cell in updated["cells"] if cell.get("cell_sha256") == cell_sha256]
    if len(matches) != 1:
        raise ValueError("MATRIX_CELL_MISSING_OR_DUPLICATED")
    cell = matches[0]
    current = cell.get("status")
    if status not in transitions.get(current, set()):
        raise ValueError("MATRIX_CELL_TRANSITION_INVALID")
    if status == "COMPLETE":
        if result_artifact is None:
            raise ValueError("MATRIX_CELL_RESULT_ARTIFACT_REQUIRED")
        _verify_cell_result(verified, cell, result_artifact)
        cell["result_artifact_sha256"] = result_artifact["artifact_sha256"]
        cell["failure_reason_code"] = None
    elif status == "FAILED":
        if not isinstance(failure_reason_code, str) or not failure_reason_code:
            raise ValueError("MATRIX_FAILURE_REASON_CODE_REQUIRED")
        cell["result_artifact_sha256"] = None
        cell["failure_reason_code"] = failure_reason_code
    elif status == "PARTIAL":
        cell["failure_reason_code"] = None
        cell["result_artifact_sha256"] = None
    else:
        if result_artifact is not None or failure_reason_code is not None:
            raise ValueError("NONTERMINAL_CELL_CANNOT_CARRY_TERMINAL_EVIDENCE")
    cell["status"] = status
    updated["ledger_sha256"] = ""
    updated["ledger_sha256"] = _sha({k: v for k, v in updated.items()
                                     if k != "ledger_sha256"})
    return updated


def mark_matrix_dispatched(ledger: Mapping, *, verified: VerifiedManifest) -> dict:
    """Atomically advance every expected pending/partial cell to DISPATCHED."""
    expected = expected_cell_ledger(verified)
    if (ledger.get("schema_version") != LEDGER_SCHEMA
            or ledger.get("manifest_sha256") != verified.sha256
            or ledger.get("ledger_sha256") != _sha({k: v for k, v in ledger.items()
                if k != "ledger_sha256"})):
        raise ValueError("MATRIX_LEDGER_MANIFEST_OR_HASH_MISMATCH")
    expected_by_id = {cell["cell_sha256"]: cell for cell in expected["cells"]}
    cells = ledger.get("cells")
    if not isinstance(cells, list) or len(cells) != len(expected_by_id):
        raise ValueError("MATRIX_LEDGER_CELL_SET_INVALID")
    updated = copy.deepcopy(dict(ledger))
    seen = set()
    for cell in updated["cells"]:
        cell_id = cell.get("cell_sha256")
        if (cell_id not in expected_by_id or cell_id in seen
                or cell.get("identity") != expected_by_id[cell_id]["identity"]):
            raise ValueError("MATRIX_LEDGER_CELL_IDENTITY_INVALID")
        seen.add(cell_id)
        if cell.get("status") in {"PENDING", "PARTIAL"}:
            cell["status"] = "DISPATCHED"
        elif cell.get("status") not in {"DISPATCHED", "RUNNING", "COMPLETE", "FAILED"}:
            raise ValueError("MATRIX_CELL_STATUS_INVALID")
    updated["ledger_sha256"] = ""
    updated["ledger_sha256"] = _sha({k: v for k, v in updated.items()
                                     if k != "ledger_sha256"})
    return updated


def _verify_cell_result(verified: VerifiedManifest, cell: Mapping,
                        artifact: Mapping) -> None:
    identity = cell.get("identity", {})
    if (artifact.get("schema_version") != CELL_RESULT_SCHEMA
            or artifact.get("status") != "COMPLETE"
            or artifact.get("completion_status") != "COMPLETE"
            or artifact.get("cell_sha256") != cell.get("cell_sha256")
            or artifact.get("identity") != identity
            or artifact.get("manifest_sha256") != verified.sha256
            or artifact.get("implementation_identity") != identity.get("implementation_commit")
            or artifact.get("dataset_identity") != _manifest(verified)["source_dataset_manifest_sha256"]
            or artifact.get("root") != identity.get("root")
            or artifact.get("horizon_minutes") != identity.get("horizon_minutes")
            or artifact.get("seed") != identity.get("seed")
            or artifact.get("walk_forward_window") != identity.get("walk_forward_window")
            or artifact.get("model_id") != identity.get("model_id")
            or artifact.get("ablation_id") != identity.get("ablation_id")
            or artifact.get("control_identity") != identity.get("control_condition")
            or artifact.get("target_head") != identity.get("head")
            or artifact.get("classification") != ["SYNTHETIC ENGINEERING RESULT",
                "NOT ES/NQ MARKET EVIDENCE", "NOT VALID FOR TRADING",
                "NOT VALID FOR MODEL-SELECTION CLAIMS"]
            or artifact.get("protected_models_scored") != 0
            or artifact.get("protected_oos_scores_produced") != 0
            or artifact.get("protected_oos_execution") != "NOT AUTHORIZED"
            or artifact.get("trading_authority") != "NONE"):
        raise ValueError("MATRIX_CELL_RESULT_LINEAGE_OR_SAFETY_MISMATCH")
    fingerprints = artifact.get("partition_fingerprints")
    if (not isinstance(fingerprints, Mapping)
            or set(fingerprints) != {"TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST"}
            or not all(_is_sha256(value) for value in fingerprints.values())):
        raise ValueError("WALK_FORWARD_PARTITION_FINGERPRINTS_INVALID")
    if artifact.get("result_sha256") != _sha(artifact.get("result")):
        raise ValueError("MATRIX_CELL_RESULT_CONTENT_HASH_MISMATCH")
    result = artifact.get("result")
    required = {"information_contract", "preprocessing_artifact", "model_artifact",
        "checkpoint_artifact", "calibration_artifact", "abstention_artifact", "prediction_artifact",
        "common_comparison_row_identity", "metric_definition", "metrics"}
    if not isinstance(result, Mapping) or set(result) != required:
        raise ValueError("MATRIX_CELL_RESULT_COMPONENT_SCHEMA_MISMATCH")
    identity = cell["identity"]
    model_payload = result["model_artifact"]
    prediction_payload = result["prediction_artifact"]
    information_payload = result["information_contract"]
    preprocessing_payload = result["preprocessing_artifact"]
    calibration_payload = result["calibration_artifact"]
    abstention_payload = result["abstention_artifact"]
    if any(not isinstance(value, Mapping) for value in
            (model_payload, prediction_payload, information_payload,
             preprocessing_payload, result["metric_definition"], result["metrics"])):
        raise ValueError("MATRIX_CELL_RESULT_COMPONENT_SCHEMA_MISMATCH")
    model_body = {key: value for key, value in model_payload.items()
                  if key not in {"artifact_sha256", "manifest_sha256"}}
    expected_model_ablation = (identity["ablation_id"] if identity["model_id"] in _NEURAL
                               else "NOT_APPLICABLE_NO_FEATURE_INPUT")
    control_sha = model_payload.get("training_label_control_sha256")
    if (model_payload.get("artifact_sha256") != _sha(model_body)
            or model_payload.get("model_id") != identity["model_id"]
            or model_payload.get("manifest_sha256") != verified.sha256
            or model_payload.get("dataset_manifest_sha256") != identity["dataset_identity"]
            or model_payload.get("market") != identity["root"]
            or model_payload.get("horizon_minutes") != identity["horizon_minutes"]
            or model_payload.get("random_seed") != identity["seed"]
            or model_payload.get("ablation_id") != expected_model_ablation
            or model_payload.get("control_identity") != identity["control_condition"]
            or (identity["control_condition"] == "NONE" and control_sha is not None)
            or (identity["control_condition"] != "NONE" and not _is_sha256(control_sha))
            or model_payload.get("code_commit") != identity["implementation_commit"]
            or model_payload.get("preprocessing_sha256") != canonical_hash(preprocessing_payload)
            or model_payload.get("training_partition_fingerprint")
                != artifact["partition_fingerprints"].get("TRAIN")
            or model_payload.get("validation_partition_fingerprint")
                != artifact["partition_fingerprints"].get("VALIDATION_AND_CALIBRATION")
            or information_payload.get("partition_fingerprints")
                != artifact["partition_fingerprints"]
            or information_payload.get("root") != identity["root"]
            or information_payload.get("horizon_minutes") != identity["horizon_minutes"]
            or information_payload.get("seed") != identity["seed"]
            or information_payload.get("walk_forward_window") != identity["walk_forward_window"]
            or information_payload.get("model_id") != identity["model_id"]
            or information_payload.get("ablation_id") != identity["ablation_id"]
            or information_payload.get("control_identity") != identity["control_condition"]
            or information_payload.get("head") != identity["head"]
            or preprocessing_payload.get("fit_partition") != "TRAIN"
            or prediction_payload.get("target_head") != identity["head"]
            or not isinstance(prediction_payload.get("row_identities"), list)
            or not isinstance(prediction_payload.get("predictions"), list)
            or not prediction_payload.get("row_identities")
            or len(set(prediction_payload.get("row_identities", []))) != len(prediction_payload.get("row_identities", []))
            or len(prediction_payload["row_identities"]) != len(prediction_payload["predictions"])
            or (result.get("common_comparison_row_identity") is not None
                and result.get("common_comparison_row_identity") != _sha(prediction_payload["row_identities"]))):
        raise ValueError("MATRIX_CELL_RESULT_COMPONENT_LINEAGE_MISMATCH")
    checkpoint_payload = result.get("checkpoint_artifact")
    if identity["model_id"] == "A2_LEARNED_CAUSAL_TCN":
        if (not isinstance(checkpoint_payload, Mapping)
                or checkpoint_payload.get("selection_partition") != "VALIDATION_AND_CALIBRATION"
                or checkpoint_payload.get("model_artifact_sha256") != model_payload.get("artifact_sha256")
                or checkpoint_payload.get("partition_fingerprints") != artifact["partition_fingerprints"]
                or checkpoint_payload.get("checkpoint_sha256") != _sha({key: value
                    for key, value in checkpoint_payload.items() if key != "checkpoint_sha256"})):
            raise ValueError("MATRIX_CELL_CHECKPOINT_LINEAGE_MISMATCH")
    elif checkpoint_payload is not None:
        raise ValueError("MATRIX_CELL_UNEXPECTED_CHECKPOINT")
    if identity["model_id"] in _NEURAL:
        from .experiment_controls import create_ablation_contract
        ablation = create_ablation_contract(verified, identity["ablation_id"])
        execution = model_payload.get("ablation_execution_artifact")
        if not isinstance(execution, Mapping):
            raise ValueError("MATRIX_CELL_ABLATION_EXECUTION_MISSING")
        execution_body = {key: value for key, value in execution.items()
                          if key != "execution_sha256"}
        if (execution.get("schema_version") != "bot2-phase5c-v3-fixed-dimension-ablation-v2"
                or execution.get("execution_type") != "ENGINEERING_FIXED_DIMENSION_MASK_ONLY"
                or execution.get("manifest_sha256") != verified.sha256
                or execution.get("implementation_candidate_commit") != identity["implementation_commit"]
                or execution.get("model_id") != identity["model_id"]
                or execution.get("seed") != identity["seed"]
                or execution.get("ablation_id") != identity["ablation_id"]
                or execution.get("ablation_sha256") != ablation["ablation_sha256"]
                or execution.get("feature_mask") != ablation["feature_mask"]
                or execution.get("input_channels") != 24
                or execution.get("preprocessing_sha256") != canonical_hash(preprocessing_payload)
                or execution.get("predictions_generated") is not False
                or execution.get("metrics_generated") is not False
                or execution.get("execution_sha256") != _sha(execution_body)
                or model_payload.get("input_shape") != [8, 24]):
            raise ValueError("MATRIX_CELL_ABLATION_EXECUTION_LINEAGE_MISMATCH")
        if (identity["model_id"] == "A2_LEARNED_CAUSAL_TCN"
                and model_payload.get("parameter_count") != 7417):
            raise ValueError("A2_FIXED_ARCHITECTURE_CONTRACT_FAILED")
    calibration_expected = (identity["model_id"] in _NEURAL)
    if calibration_expected and (not isinstance(calibration_payload, Mapping)
            or calibration_payload.get("head") != identity["head"]
            or calibration_payload.get("market") != identity["root"]
            or calibration_payload.get("horizon_minutes") != identity["horizon_minutes"]
            or calibration_payload.get("model_artifact_sha256") != model_payload.get("artifact_sha256")
            or calibration_payload.get("calibration_sha256") != _sha({key: value
                for key, value in calibration_payload.items() if key != "calibration_sha256"})):
        raise ValueError("MATRIX_CELL_RESULT_CALIBRATION_LINEAGE_MISMATCH")
    if calibration_expected and (not isinstance(abstention_payload, Mapping)
            or abstention_payload.get("head") != identity["head"]
            or abstention_payload.get("model_artifact_sha256") != model_payload.get("artifact_sha256")):
        raise ValueError("MATRIX_CELL_RESULT_ABSTENTION_LINEAGE_MISMATCH")
    components = {key: (_sha(result[key]) if result[key] is not None else None)
        for key in ("information_contract", "preprocessing_artifact", "model_artifact",
                    "checkpoint_artifact", "calibration_artifact", "abstention_artifact", "prediction_artifact",
                    "metric_definition", "metrics")}
    prediction_body = {key: value for key, value in result["prediction_artifact"].items()
                       if key != "prediction_sha256"}
    metric_body = {key: value for key, value in result["metric_definition"].items()
                   if key != "metric_definition_sha256"}
    info_body = {key: value for key, value in result["information_contract"].items()
                 if key != "contract_sha256"}
    if (result["prediction_artifact"].get("prediction_sha256") != _sha(prediction_body)
            or result["metric_definition"].get("metric_definition_sha256") != _sha(metric_body)
            or result["information_contract"].get("contract_sha256") != _sha(info_body)
            or artifact.get("component_hashes") != components
            or artifact.get("information_contract_identity") != result["information_contract"].get("contract_sha256")
            or artifact.get("prediction_artifact_sha256") != result["prediction_artifact"].get("prediction_sha256")
            or artifact.get("metric_definition_identity") != result["metric_definition"].get("metric_definition_sha256")
            or artifact.get("preprocessing_artifact_sha256") != components["preprocessing_artifact"]
            or artifact.get("model_artifact_sha256") != components["model_artifact"]
            or artifact.get("checkpoint_sha256") != components["checkpoint_artifact"]
            or artifact.get("calibration_artifact_sha256") != components["calibration_artifact"]
            or artifact.get("abstention_artifact_sha256") != components["abstention_artifact"]
            or artifact.get("common_comparison_row_identity") != result.get("common_comparison_row_identity")):
        raise ValueError("MATRIX_CELL_RESULT_COMPONENT_HASH_MISMATCH")
    if artifact.get("artifact_sha256") != _sha({k: v for k, v in artifact.items()
                                                  if k != "artifact_sha256"}):
        raise ValueError("MATRIX_CELL_RESULT_ARTIFACT_HASH_MISMATCH")


def load_cell_result_artifact(verified: VerifiedManifest, *, cell: Mapping,
                              artifact: Mapping) -> dict:
    """Validate an artifact against the frozen cell and the content it claims."""
    expected = expected_cell_ledger(verified)
    frozen = next((item for item in expected["cells"]
                   if item["cell_sha256"] == cell.get("cell_sha256")), None)
    if frozen is None or cell.get("identity") != frozen["identity"]:
        raise ValueError("EXPERIMENT_CELL_IDENTITY_MISMATCH")
    _verify_cell_result(verified, cell, artifact)
    return copy.deepcopy(dict(artifact))


def create_stage_checkpoint(verified: VerifiedManifest, *, cell: Mapping,
        stage: str, partition_fingerprints: Mapping[str, str],
        upstream_artifact_hashes: Mapping[str, str], payload: Mapping,
        status: str = "COMPLETE") -> dict:
    """Create a resumable immutable stage record bound to complete cell lineage."""
    expected = expected_cell_ledger(verified)
    frozen = next((item for item in expected["cells"]
                   if item["cell_sha256"] == cell.get("cell_sha256")), None)
    if frozen is None or cell.get("identity") != frozen["identity"]:
        raise ValueError("EXPERIMENT_CELL_IDENTITY_MISMATCH")
    if stage not in _CELL_STAGES:
        raise ValueError("STAGE_CHECKPOINT_STAGE_INVALID")
    if status not in {"COMPLETE", "PARTIAL"}:
        raise ValueError("STAGE_CHECKPOINT_STATUS_INVALID")
    partitions = dict(sorted(partition_fingerprints.items()))
    if (set(partitions) != {"TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST"}
            or not all(_is_sha256(value) for value in partitions.values())):
        raise ValueError("WALK_FORWARD_PARTITION_FINGERPRINTS_INVALID")
    upstream = dict(sorted(upstream_artifact_hashes.items()))
    if not all(_is_sha256(value) for value in upstream.values()):
        raise ValueError("STAGE_UPSTREAM_HASH_INVALID")
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError("STAGE_CHECKPOINT_PAYLOAD_INVALID")
    identity = frozen["identity"]
    lineage = {"manifest_sha256": verified.sha256,
        "implementation_identity": identity["implementation_commit"],
        "dataset_identity": identity["dataset_identity"],
        "experiment_cell_sha256": frozen["cell_sha256"],
        "partition_fingerprints": partitions,
        "root": identity["root"], "horizon_minutes": identity["horizon_minutes"],
        "seed": identity["seed"], "walk_forward_window": identity["walk_forward_window"],
        "model_id": identity["model_id"], "ablation_id": identity["ablation_id"],
        "control_identity": identity["control_condition"], "target_head": identity["head"],
        "stage_schema": STAGE_CHECKPOINT_SCHEMA, "stage": stage,
        "upstream_artifact_hashes": upstream}
    checkpoint = {"schema_version": STAGE_CHECKPOINT_SCHEMA, "status": status,
        "lineage": lineage, "payload": copy.deepcopy(dict(payload)),
        "payload_sha256": _sha(payload)}
    checkpoint["artifact_sha256"] = _sha(checkpoint)
    return checkpoint


def classify_stage_checkpoint(*, expected_lineage: Mapping,
                              artifact: Mapping | None) -> dict:
    """A partial, corrupted, or wrong-lineage stage is never reusable."""
    if artifact is None:
        return {"status": "REQUIRES_EXECUTION", "reason_code": "STAGE_CHECKPOINT_ABSENT"}
    if artifact.get("schema_version") != STAGE_CHECKPOINT_SCHEMA:
        return {"status": "SCHEMA_MISMATCH", "reason_code": "STAGE_CHECKPOINT_SCHEMA_MISMATCH"}
    if artifact.get("status") != "COMPLETE":
        return {"status": "PARTIAL", "reason_code": "STAGE_CHECKPOINT_NOT_COMPLETE"}
    lineage = artifact.get("lineage")
    if not isinstance(lineage, Mapping) or dict(lineage) != dict(expected_lineage):
        return {"status": "LINEAGE_MISMATCH", "reason_code": "STAGE_CHECKPOINT_LINEAGE_MISMATCH"}
    payload = artifact.get("payload")
    if (not isinstance(payload, Mapping)
            or artifact.get("payload_sha256") != _sha(payload)):
        return {"status": "CORRUPTED", "reason_code": "STAGE_CHECKPOINT_CONTENT_HASH_MISMATCH"}
    if artifact.get("artifact_sha256") != _sha({k: v for k, v in artifact.items()
                                                 if k != "artifact_sha256"}):
        return {"status": "CORRUPTED", "reason_code": "STAGE_CHECKPOINT_ARTIFACT_HASH_MISMATCH"}
    return {"status": "REUSABLE_COMPLETE", "reason_code": "STAGE_CHECKPOINT_LINEAGE_VERIFIED"}


def publish_stage_checkpoint(path: str | Path, checkpoint: Mapping) -> str:
    """Publish a complete stage checkpoint atomically without replacing a winner."""
    target = Path(path)
    payload = checkpoint.get("payload")
    if (checkpoint.get("schema_version") != STAGE_CHECKPOINT_SCHEMA
            or checkpoint.get("status") != "COMPLETE"
            or not isinstance(payload, Mapping)
            or checkpoint.get("payload_sha256") != _sha(payload)
            or checkpoint.get("artifact_sha256") != _sha({k: v for k, v in checkpoint.items()
                if k != "artifact_sha256"})):
        raise ValueError("STAGE_CHECKPOINT_NOT_VERIFIED_FOR_PUBLICATION")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp",
            dir=target.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical_bytes(checkpoint))
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link creation is atomic and fails if target already exists.
        os.link(temporary, target)
        return hashlib.sha256(target.read_bytes()).hexdigest()
    except FileExistsError as exc:
        raise ValueError("STAGE_CHECKPOINT_ALREADY_PUBLISHED") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def load_stage_checkpoint(path: str | Path, *, expected_lineage: Mapping) -> dict:
    """Read and validate a checkpoint; malformed or stale stages fail closed."""
    if Path(path).is_symlink():
        raise ValueError("STAGE_CHECKPOINT_SYMLINK_REJECTED")
    try:
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("STAGE_CHECKPOINT_ABSENT") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("STAGE_CHECKPOINT_PARTIAL_OR_MALFORMED") from exc
    classified = classify_stage_checkpoint(expected_lineage=expected_lineage,
        artifact=artifact)
    if classified["status"] != "REUSABLE_COMPLETE":
        raise ValueError(classified["reason_code"])
    return artifact


def plan_stage_resume(*, checkpoints: Mapping[str, Mapping | None],
        expected_lineage_by_stage: Mapping[str, Mapping]) -> dict:
    """Reuse only the verified contiguous stage prefix and restart at first gap.

    A later checkpoint is not reused across a missing, partial, corrupted, or
    wrong-lineage predecessor, preventing stage skipping after interruption.
    """
    if set(expected_lineage_by_stage) != set(_CELL_STAGES):
        raise ValueError("STAGE_RESUME_EXPECTED_LINEAGE_SET_INVALID")
    reusable, statuses = [], {}
    for stage in _CELL_STAGES:
        artifact = checkpoints.get(stage)
        expected = expected_lineage_by_stage[stage]
        if expected.get("stage") != stage:
            raise ValueError("STAGE_RESUME_EXPECTED_LINEAGE_STAGE_MISMATCH")
        upstream = expected.get("upstream_artifact_hashes")
        if not isinstance(upstream, Mapping):
            raise ValueError("STAGE_RESUME_UPSTREAM_LINEAGE_INVALID")
        if any(name not in reusable
                or not isinstance(checkpoints.get(name), Mapping)
                or checkpoints[name].get("artifact_sha256") != digest
                for name, digest in upstream.items()):
            statuses[stage] = {"status": "LINEAGE_MISMATCH",
                "reason_code": "STAGE_CHECKPOINT_UPSTREAM_HASH_MISMATCH"}
            return {"reused_stages": reusable, "resume_from": stage,
                "stage_status": statuses, "lineage_verified": False}
        if stage != _CELL_STAGES[0]:
            predecessor = _CELL_STAGES[_CELL_STAGES.index(stage) - 1]
            if predecessor not in reusable:
                statuses[stage] = {"status": "NOT_REACHED", "reason_code": "PREDECESSOR_NOT_REUSABLE"}
                return {"reused_stages": reusable, "resume_from": predecessor,
                    "stage_status": statuses, "lineage_verified": False}
        elif upstream:
            raise ValueError("STAGE_RESUME_ROOT_STAGE_HAS_UPSTREAM")
        classified = classify_stage_checkpoint(expected_lineage=expected, artifact=artifact)
        statuses[stage] = classified
        if classified["status"] != "REUSABLE_COMPLETE":
            return {"reused_stages": reusable, "resume_from": stage,
                "stage_status": statuses, "lineage_verified": True}
        reusable.append(stage)
    return {"reused_stages": reusable, "resume_from": None,
        "stage_status": statuses, "lineage_verified": True}


def evaluate_complete_matrix(ledger: Mapping, *, verified: VerifiedManifest,
        result_artifacts: Mapping[str, Mapping] | None = None) -> dict:
    """Fail closed unless every expected cell is COMPLETE with a hash-bound result."""
    expected = expected_cell_ledger(verified)
    if ledger.get("schema_version") != LEDGER_SCHEMA:
        raise ValueError("MATRIX_LEDGER_SCHEMA_MISMATCH")
    if ledger.get("manifest_sha256") != verified.sha256:
        raise ValueError("MATRIX_LEDGER_MANIFEST_MISMATCH")
    if ledger.get("ledger_sha256") != _sha({k: v for k, v in ledger.items()
                                             if k != "ledger_sha256"}):
        raise ValueError("MATRIX_LEDGER_HASH_MISMATCH")
    actual = ledger.get("cells")
    expected_by_id = {cell["cell_sha256"]: cell for cell in expected["cells"]}
    if not isinstance(actual, list) or len(actual) != len(expected_by_id):
        return {"status": "INCOMPLETE", "reason_code": "MATRIX_CELL_COUNT_MISMATCH",
            "expected_cell_count": len(expected_by_id),
            "actual_cell_count": len(actual) if isinstance(actual, list) else 0}
    seen, missing_evidence, in_progress, partial, complete_count = set(), 0, 0, 0, 0
    failed, invalid, lineage = 0, 0, 0
    artifacts = result_artifacts or {}
    if any(cell.get("status") == "COMPLETE" and cell.get("cell_sha256") not in artifacts
           for cell in actual):
        invalid += 1
    completed_ids = {cell.get("cell_sha256") for cell in actual
                     if cell.get("status") == "COMPLETE"}
    if set(artifacts) - completed_ids:
        invalid += 1
    for cell in actual:
        cell_id = cell.get("cell_sha256")
        if cell_id not in expected_by_id or cell_id in seen:
            invalid += 1
            continue
        seen.add(cell_id)
        if cell.get("identity") != expected_by_id[cell_id]["identity"]:
            lineage += 1
        elif cell.get("status") == "PENDING":
            missing_evidence += 1
        elif cell.get("status") in {"DISPATCHED", "RUNNING"}:
            in_progress += 1
        elif cell.get("status") == "PARTIAL":
            partial += 1
        elif cell.get("status") == "FAILED":
            if not cell.get("failure_reason_code"):
                invalid += 1
            failed += 1
        elif cell.get("status") == "COMPLETE":
            artifact = artifacts.get(cell_id)
            try:
                _verify_cell_result(verified, cell, artifact or {})
            except (TypeError, ValueError):
                invalid += 1
            if (not artifact or not _is_sha256(cell.get("result_artifact_sha256"))
                    or cell.get("result_artifact_sha256") != artifact.get("artifact_sha256")):
                invalid += 1
            else:
                complete_count += 1
        else:
            invalid += 1
    missing = len(set(expected_by_id) - seen)
    missing_evidence += missing
    engineering_artifacts_complete = not (missing_evidence or in_progress or partial
        or failed or invalid or lineage)
    return {"status": "ENGINEERING_ARTIFACTS_COMPLETE_NOT_EXPERIMENT_COMPLETE"
                       if engineering_artifacts_complete else "INCOMPLETE",
        "reason_code": "PROTECTED_EVALUATION_NOT_AUTHORIZED" if engineering_artifacts_complete
                       else "MATRIX_HAS_UNRESOLVED_OR_INVALID_CELLS",
        "engineering_artifacts_complete": engineering_artifacts_complete,
        "scientific_experiment_complete": False,
        "protected_evaluation_permitted": False,
        "expected_cell_count": len(expected_by_id), "complete": complete_count,
        "failed": failed, "partial": partial, "missing": missing_evidence,
        "in_progress": in_progress,
        "pending": missing_evidence, "invalid_or_duplicated": invalid,
        "lineage_mismatch": lineage}


def validate_walk_forward_rows(verified: VerifiedManifest, *, root: str,
        horizon_minutes: int, window_id: str,
        rows_by_partition: Mapping[str, Sequence[MarketObservation]]) -> dict:
    """Verify rows against frozen WF dates, purge, embargo, and identities."""
    manifest = _manifest(verified)
    if root not in manifest["source_dataset"]["contracts"]:
        raise ValueError("MARKET_NOT_IN_MANIFEST")
    if horizon_minutes not in manifest["target_specification"]["horizons_minutes"]:
        raise ValueError("TARGET_WINDOW_NOT_IN_MANIFEST")
    windows = {item.window_id: item for item in derive_walk_forward_windows(verified)}
    if window_id not in windows:
        raise ValueError("WALK_FORWARD_WINDOW_NOT_IN_MANIFEST")
    window = windows[window_id]
    spans = {"TRAIN": window.train, "VALIDATION_AND_CALIBRATION": window.validation,
             "OOS_TEST": window.test}
    if set(rows_by_partition) != set(spans):
        raise ValueError("WALK_FORWARD_PARTITION_SET_INVALID")
    contracts = set(manifest["source_dataset"]["contracts"][root])
    parsed: dict[str, list[tuple[datetime, MarketObservation]]] = {}
    identities: set[str] = set()
    for partition, span in spans.items():
        rows = list(rows_by_partition[partition])
        if not rows:
            raise ValueError("EMPTY_AUTHORIZED_PARTITION")
        values = []
        for row in rows:
            try:
                timestamp = datetime.fromisoformat(row.exchange_timestamp_utc.replace("Z", "+00:00"))
                label_end = datetime.fromisoformat(row.label_end_utc.replace("Z", "+00:00"))
            except (AttributeError, ValueError) as exc:
                raise ValueError("INVALID_OBSERVATION_TIMESTAMP") from exc
            if (timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0)
                    or label_end.tzinfo is None or label_end.utcoffset() != timedelta(0)):
                raise ValueError("OBSERVATION_TIMESTAMP_MUST_BE_UTC")
            if row.observation_id in identities:
                raise ValueError("DUPLICATE_OBSERVATION_CROSSES_PARTITION")
            identities.add(row.observation_id)
            if not (date.fromisoformat(span[0]) <= timestamp.date() <= date.fromisoformat(span[1])):
                raise ValueError("CALLER_SUPPLIED_UNAUTHORIZED_WINDOW_DATE")
            if row.market != root or row.contract not in contracts:
                raise ValueError("INSTRUMENT_OR_CONTRACT_NOT_IN_MANIFEST")
            if row.dataset_manifest_sha256 != manifest["source_dataset_manifest_sha256"]:
                raise ValueError("DATASET_MANIFEST_BINDING_MISMATCH")
            if (label_end != timestamp + timedelta(minutes=horizon_minutes)
                    or label_end.date() > date.fromisoformat(span[1])):
                raise ValueError("LABEL_INFORMATION_INTERVAL_INVALID")
            if (row.session_open_utc is None
                    or datetime.fromisoformat(row.session_open_utc.replace("Z", "+00:00")) > timestamp
                    or row.feature_names != tuple(manifest["feature_specification"]["features"])
                    or row.feature_version != manifest["feature_specification"]["schema_version"]
                    or row.target_version != manifest["target_specification"]["version"]
                    or set(row.targets) != set(manifest["target_specification"]["class_indices"])
                    or any(int(row.targets[head]) not in (0, 1, 2)
                           for head in manifest["target_specification"]["class_indices"])
                    or len(row.features) != len(manifest["feature_specification"]["features"])
                    or any(not math.isfinite(float(value)) for value in row.features)):
                raise ValueError("OBSERVATION_CONTRACT_INVALID")
            values.append((timestamp.astimezone(timezone.utc), row))
        if values != sorted(values, key=lambda pair: (pair[0], pair[1].contract)):
            raise ValueError("OBSERVATIONS_NOT_IN_CANONICAL_ORDER")
        parsed[partition] = values
    for earlier, later in (("TRAIN", "VALIDATION_AND_CALIBRATION"),
                            ("VALIDATION_AND_CALIBRATION", "OOS_TEST")):
        first_next = min(timestamp for timestamp, _ in parsed[later])
        cutoff = first_next - timedelta(minutes=window.purge_minutes)
        if any(datetime.fromisoformat(row.label_end_utc.replace("Z", "+00:00")) >= cutoff
               for _, row in parsed[earlier]):
            raise ValueError("WALK_FORWARD_PURGE_VIOLATION")
    eligible, excluded, fingerprints, sequences_by_partition = {}, {}, {}, {}
    sequence_length = int(manifest["feature_specification"]["sequence_length"])
    cadence = timedelta(seconds=int(manifest["feature_specification"]["sequence_cadence_seconds"]))
    for partition, values in parsed.items():
        rows = [row for _, row in values]
        fingerprints[partition] = partition_fingerprint(rows, partition=partition,
                                                        horizon_minutes=horizon_minutes)
        embargo_end = (None if partition == "TRAIN" else
            min(timestamp for timestamp, _ in values) + timedelta(minutes=window.embargo_minutes))
        first_next = None
        if partition == "TRAIN":
            first_next = min(timestamp for timestamp, _ in parsed["VALIDATION_AND_CALIBRATION"])
        elif partition == "VALIDATION_AND_CALIBRATION":
            first_next = min(timestamp for timestamp, _ in parsed["OOS_TEST"])
        cutoff = (first_next - timedelta(minutes=window.purge_minutes)
                  if first_next is not None else None)
        good_sequences = []
        eligible_ids = set()
        excluded_ids = set()
        for start in range(max(0, len(rows) - sequence_length + 1)):
            sample = rows[start:start + sequence_length]
            if len(sample) != sequence_length:
                continue
            if any(left.contract != right.contract or left.session_id != right.session_id
                    or datetime.fromisoformat(right.exchange_timestamp_utc.replace("Z", "+00:00"))
                       - datetime.fromisoformat(left.exchange_timestamp_utc.replace("Z", "+00:00")) != cadence
                    for left, right in zip(sample, sample[1:])):
                continue
            terminal = sample[-1]
            terminal_ts = datetime.fromisoformat(terminal.exchange_timestamp_utc.replace("Z", "+00:00"))
            embargoed = embargo_end is not None and terminal_ts < embargo_end
            purged = cutoff is not None and datetime.fromisoformat(
                terminal.label_end_utc.replace("Z", "+00:00")) >= cutoff
            if embargoed or purged:
                excluded_ids.add(terminal.observation_id)
                continue
            sequence_ids = [row.observation_id for row in sample]
            good_sequences.append(sequence_ids)
            eligible_ids.add(terminal.observation_id)
        if not good_sequences:
            raise ValueError("NO_VALID_CONTIGUOUS_SEQUENCES")
        sequences_by_partition[partition] = good_sequences
        eligible[partition] = [row for row in rows if row.observation_id in eligible_ids]
        excluded[partition] = [row for row in rows if row.observation_id in excluded_ids]
        if not eligible[partition]:
            raise ValueError("EMBARGO_REMOVES_ALL_PARTITION_ROWS")
    return {"schema_version": WINDOW_SCHEMA, "window_id": window.window_id,
        "window_fingerprint": window.fingerprint, "manifest_sha256": verified.sha256,
        "root": root, "horizon_minutes": horizon_minutes,
        "partition_fingerprints": fingerprints,
        "eligible_row_ids": {name: [row.observation_id for row in rows]
                             for name, rows in eligible.items()},
        "eligible_sequence_observation_ids": sequences_by_partition,
        "excluded_row_ids": {name: [row.observation_id for row in rows]
                             for name, rows in excluded.items()},
        "purge_minutes": window.purge_minutes, "embargo_minutes": window.embargo_minutes}


def common_comparison_record(*, model_eligible_rows: Mapping[str, Sequence[str]],
        model_metadata: Mapping[str, Mapping], metric_identity: str,
        excluded_reason_counts: Mapping[str, Mapping[str, int]] | None = None) -> dict:
    """Record raw eligible sets and their deterministic intersection."""
    required = set(_A0 + _NEURAL)
    if set(model_eligible_rows) != required or set(model_metadata) != required:
        raise ValueError("COMPARISON_MODEL_SET_INCOMPLETE")
    raw = {}
    for model, rows in model_eligible_rows.items():
        values = list(rows)
        if len(set(values)) != len(values):
            raise ValueError("COMPARISON_DUPLICATE_ELIGIBLE_ROW")
        raw[model] = values
    common = set.intersection(*(set(rows) for rows in raw.values()))
    common_ordered = [row for row in raw[_A0[0]] if row in common]
    universe = set().union(*(set(rows) for rows in raw.values()))
    universe_ordered = list(dict.fromkeys(row for model in sorted(raw)
        for row in raw[model]))
    records = {model: {"model_id": model, "metadata": dict(model_metadata[model]),
        "raw_eligible_row_count": len(raw[model]),
        "raw_eligible_row_ids": raw[model],
        "raw_eligible_row_sha256": _sha(raw[model]),
        "excluded_row_count": len(universe - set(raw[model])),
        "excluded_row_ids": [row for row in universe_ordered if row not in set(raw[model])],
        "exclusion_reason_counts": ({"NOT_ELIGIBLE_FOR_MODEL": len(universe - set(raw[model]))}
            if universe - set(raw[model]) else {}),
        "excluded_reason_counts": dict((excluded_reason_counts or {}).get(model, {}))}
        for model in sorted(required)}
    result = {"schema_version": COMPARISON_SCHEMA, "metric_identity": metric_identity,
        "models": records, "common_comparison_row_count": len(common_ordered),
        "common_comparison_row_ids": common_ordered,
        "common_comparison_row_sha256": _sha(common_ordered),
        "metrics_must_use_identical_rows": True}
    result["record_sha256"] = _sha(result)
    return result


def classify_resume_artifact(*, expected_lineage: Mapping,
                             artifact: Mapping | None) -> dict:
    """Classify a result for reuse only after exact lineage/content verification."""
    if artifact is None:
        return {"status": "REQUIRES_EXECUTION", "reason_code": "RESUME_ARTIFACT_ABSENT"}
    if artifact.get("schema_version") != RESUME_SCHEMA:
        return {"status": "SCHEMA_MISMATCH", "reason_code": "RESUME_SCHEMA_MISMATCH"}
    if artifact.get("status") != "COMPLETE":
        return {"status": "PARTIAL", "reason_code": "RESUME_ARTIFACT_NOT_COMPLETE"}
    lineage = artifact.get("lineage")
    if not isinstance(lineage, Mapping):
        return {"status": "LINEAGE_MISMATCH", "reason_code": "RESUME_LINEAGE_MISSING"}
    if any(lineage.get(key) != expected_lineage.get(key) for key in _RESUME_LINEAGE_FIELDS):
        return {"status": "LINEAGE_MISMATCH", "reason_code": "RESUME_LINEAGE_MISMATCH"}
    payload = artifact.get("payload")
    if not isinstance(payload, Mapping):
        return {"status": "CORRUPTED", "reason_code": "RESUME_PAYLOAD_INVALID"}
    if artifact.get("payload_sha256") != _sha(payload):
        return {"status": "CORRUPTED", "reason_code": "RESUME_CONTENT_HASH_MISMATCH"}
    if artifact.get("artifact_sha256") != _sha({k: v for k, v in artifact.items()
                                                 if k != "artifact_sha256"}):
        return {"status": "CORRUPTED", "reason_code": "RESUME_ARTIFACT_HASH_MISMATCH"}
    return {"status": "REUSABLE_COMPLETE", "reason_code": "RESUME_LINEAGE_VERIFIED"}
