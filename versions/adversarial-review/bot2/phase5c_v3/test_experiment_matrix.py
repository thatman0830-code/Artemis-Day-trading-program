from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta

import pytest

from bot2.phase5c_v3.data_integrity import (MarketObservation, build_authorized_split,
    validate_authorized_split)
from bot2.phase5c_v3.experiment_matrix import (
    LEDGER_SCHEMA, RESUME_SCHEMA, _A0, _NEURAL, _sha,
    classify_resume_artifact, classify_stage_checkpoint, common_comparison_record,
    create_cell_result_artifact, create_stage_checkpoint, load_cell_result_artifact,
    load_stage_checkpoint, publish_stage_checkpoint,
    derive_walk_forward_windows, evaluate_complete_matrix, expected_cell_ledger,
    plan_stage_resume, reconcile_matrix_dispatch, transition_cell, validate_walk_forward_rows,
    select_engineering_coverage_cells,
)
from bot2.phase5c_v3.manifest import canonical_bytes
from bot2.phase5c_v3.test_phase5c_v3 import (
    DATASET_HASH, FEATURE_NAMES, TEST_COMMIT, VERIFIED,
)


def _row(day: str, minute: int, *, root="ES", contract="ESM5", offset=5,
         start_time="14:30:00"):
    session_open = datetime.fromisoformat(f"{day}T{start_time}+00:00")
    timestamp = session_open + timedelta(minutes=minute)
    return MarketObservation(root, contract, f"RTH-{day}-{contract}", timestamp.isoformat(),
        session_open.isoformat(), FEATURE_NAMES, tuple(float(i) for i in range(24)),
        {"direction": 1, "volatility": 1, "structure": 1},
        (timestamp + timedelta(minutes=offset)).isoformat(), DATASET_HASH,
        "bot2-feature-row-v3", "bot2-future-market-state-v3")


def _partition(day: str, *, root="ES", contract="ESM5", start_time="14:30:00",
               count=40, start_minute=0):
    return [_row(day, start_minute + i, root=root, contract=contract,
                 start_time=start_time) for i in range(count)]


def _wf_rows(train_day="2025-06-02"):
    return {
        "TRAIN": _partition(train_day),
        "VALIDATION_AND_CALIBRATION": _partition("2025-08-01"),
        "OOS_TEST": _partition("2025-09-02"),
    }


def test_windows_are_derived_from_frozen_manifest_and_fingerprinted():
    windows = derive_walk_forward_windows(VERIFIED)
    assert [item.window_id for item in windows] == ["WF1", "WF2", "WF3", "WF4"]
    assert all(item.calibration == item.validation for item in windows)
    assert all(item.purge_minutes == item.embargo_minutes == 30 for item in windows)
    assert all(len(item.fingerprint) == 64 for item in windows)


def test_expected_ledger_is_manifest_derived_complete_and_collision_free():
    ledger = expected_cell_ledger(VERIFIED)
    assert ledger["schema_version"] == LEDGER_SCHEMA
    assert ledger["expected_cell_count"] == 5184
    assert len({cell["cell_sha256"] for cell in ledger["cells"]}) == 5184
    assert all(cell["status"] == "PENDING" for cell in ledger["cells"])
    ids = [cell["identity"] for cell in ledger["cells"]]
    assert {cell["identity"]["root"] for cell in ledger["cells"]} == {"ES", "NQ"}
    assert {cell["identity"]["walk_forward_window"] for cell in ledger["cells"]} == {"WF1", "WF2", "WF3", "WF4"}
    assert any(cell["identity"]["model_id"] in _A0 for cell in ledger["cells"])
    assert any(cell["identity"]["model_id"] in _NEURAL for cell in ledger["cells"])
    assert any(cell["identity"]["control_condition"].startswith("SHUFFLED_TRAIN_LABELS:")
               for cell in ledger["cells"])
    assert ledger["ledger_sha256"] == _sha({k: v for k, v in ledger.items() if k != "ledger_sha256"})


def test_engineering_coverage_selection_is_structural_complete_and_not_experiment_complete():
    coverage = select_engineering_coverage_cells(VERIFIED)
    digest = coverage.pop("coverage_manifest_sha256")
    assert digest == _sha(coverage)
    assert coverage["selected_cell_count"] == len(coverage["selected_cell_ids"])
    assert coverage["expected_frozen_matrix_cell_count"] == 5184
    assert coverage["frozen_experiment_status"] == "NOT_EXECUTED"
    assert coverage["selection_uses_predictive_performance"] is False
    req = coverage["requirements_to_cell_ids"]
    assert set(req["roots"]) == {"ES", "NQ"}
    assert set(req["horizons_minutes"]) == {"5", "15", "30"}
    assert set(req["walk_forward_windows"]) == {"WF1", "WF2", "WF3", "WF4"}
    assert set(req["models"]) == set(_A0 + _NEURAL)
    assert len(coverage["comparison_groups"]) == 24
    assert all(set(group["cell_ids_by_model"]) == set(_A0 + _NEURAL)
        for group in coverage["comparison_groups"])


def test_dispatch_reconciliation_counts_cells_and_fails_closed_for_identity_errors():
    ledger = expected_cell_ledger(VERIFIED)
    records = [{"cell_sha256": cell["cell_sha256"],
        "identity": copy.deepcopy(cell["identity"]), "status": "DISPATCHED"}
        for cell in ledger["cells"]]
    reconciled = reconcile_matrix_dispatch(VERIFIED, records)
    assert reconciled["expected_cell_count"] == 5184
    assert reconciled["dispatched_cell_count"] == 5184
    assert reconciled["unique_dispatched_cell_count"] == 5184
    assert reconciled["incomplete_cell_count"] == 5184
    assert reconciled["complete_cell_count"] == reconciled["failed_cell_count"] == 0
    assert reconciled["dispatch_reconciled"] is True
    assert reconciled["experiment_complete"] is False

    cases = []
    cases.append((records[:-1], "MISSING_CELL"))
    cases.append((records + [copy.deepcopy(records[0])], "DUPLICATE_CELL"))
    unknown = copy.deepcopy(records)
    unknown[-1]["cell_sha256"] = "f" * 64
    cases.append((unknown, "UNKNOWN_CELL"))
    mismatch = copy.deepcopy(records)
    mismatch[-1]["identity"]["root"] = "ES" if mismatch[-1]["identity"]["root"] == "NQ" else "NQ"
    cases.append((mismatch, "CELL_IDENTITY_MISMATCH"))
    for receipts, reason in cases:
        result = reconcile_matrix_dispatch(VERIFIED, receipts)
        assert result["dispatch_reconciled"] is False
        assert reason in result["reason_codes"]
        assert result["experiment_complete"] is False


def test_matrix_gate_keeps_pending_and_failed_cells_incomplete():
    ledger = expected_cell_ledger(VERIFIED)
    result = evaluate_complete_matrix(ledger, verified=VERIFIED)
    assert result["status"] == "INCOMPLETE"
    assert result["pending"] == 5184
    ledger["cells"][0]["status"] = "FAILED"
    ledger["cells"][0]["failure_reason_code"] = "SYNTHETIC_FAILURE"
    ledger["ledger_sha256"] = _sha({k: v for k, v in ledger.items() if k != "ledger_sha256"})
    result = evaluate_complete_matrix(ledger, verified=VERIFIED)
    assert result["status"] == "INCOMPLETE" and result["failed"] == 1


def test_matrix_gate_rejects_ledger_mutation_and_duplicate_cell():
    ledger = expected_cell_ledger(VERIFIED)
    ledger["cells"].pop()
    with pytest.raises(ValueError, match="MATRIX_LEDGER_HASH_MISMATCH"):
        evaluate_complete_matrix(ledger, verified=VERIFIED)

    ledger = expected_cell_ledger(VERIFIED)
    ledger["cells"][-1] = copy.deepcopy(ledger["cells"][0])
    ledger["ledger_sha256"] = _sha({k: v for k, v in ledger.items() if k != "ledger_sha256"})
    result = evaluate_complete_matrix(ledger, verified=VERIFIED)
    assert result["status"] == "INCOMPLETE"
    assert result["invalid_or_duplicated"] >= 1


def test_cell_transition_requires_identity_bound_synthetic_artifact():
    ledger = expected_cell_ledger(VERIFIED)
    cell = ledger["cells"][0]
    fingerprints = {key: hashlib.sha256(key.encode()).hexdigest()
        for key in ("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")}
    artifact = create_cell_result_artifact(VERIFIED, cell=cell,
        partition_fingerprints=fingerprints,
        result=_cell_result_payload(cell, fingerprints))
    dispatched = transition_cell(ledger, verified=VERIFIED,
        cell_sha256=cell["cell_sha256"], status="DISPATCHED")
    running = transition_cell(dispatched, verified=VERIFIED,
        cell_sha256=cell["cell_sha256"], status="RUNNING")
    updated = transition_cell(running, verified=VERIFIED,
        cell_sha256=cell["cell_sha256"], status="COMPLETE", result_artifact=artifact)
    updated_cell = next(item for item in updated["cells"]
                        if item["cell_sha256"] == cell["cell_sha256"])
    assert updated_cell["status"] == "COMPLETE"
    result = evaluate_complete_matrix(updated, verified=VERIFIED,
        result_artifacts={cell["cell_sha256"]: artifact})
    assert result["status"] == "INCOMPLETE" and result["pending"] == 5183
    corrupted = dict(artifact, result={"evidence": "modified"})
    with pytest.raises(ValueError, match="MATRIX_CELL_RESULT_CONTENT_HASH_MISMATCH"):
        transition_cell(running, verified=VERIFIED,
            cell_sha256=cell["cell_sha256"], status="COMPLETE", result_artifact=corrupted)
    with pytest.raises(ValueError, match="MATRIX_CELL_RESULT_ARTIFACT_REQUIRED"):
        transition_cell(running, verified=VERIFIED,
            cell_sha256=cell["cell_sha256"], status="COMPLETE")


def _cell_result_payload(cell, partition_fingerprints):
    identity = cell["identity"]
    info = {"root": identity["root"], "horizon_minutes": identity["horizon_minutes"],
        "seed": identity["seed"], "walk_forward_window": identity["walk_forward_window"],
        "model_id": identity["model_id"], "ablation_id": identity["ablation_id"],
        "control_identity": identity["control_condition"], "head": identity["head"],
        "partition_fingerprints": dict(partition_fingerprints)}
    info["contract_sha256"] = _sha(info)
    preprocessing = {"fit_partition": "TRAIN", "mean": [0.0],
        "training_partition_fingerprint": partition_fingerprints["TRAIN"]}
    model = {"model_id": identity["model_id"], "random_seed": identity["seed"],
        "manifest_sha256": VERIFIED.sha256,
        "dataset_manifest_sha256": identity["dataset_identity"],
        "market": identity["root"], "horizon_minutes": identity["horizon_minutes"],
        "ablation_id": (identity["ablation_id"] if identity["model_id"] in _NEURAL
                        else "NOT_APPLICABLE_NO_FEATURE_INPUT"),
        "control_identity": identity["control_condition"],
        "training_label_control_sha256": (None if identity["control_condition"] == "NONE"
            else _sha({"control": identity["control_condition"]})),
        "preprocessing_sha256": _sha(preprocessing),
        "training_partition_fingerprint": partition_fingerprints["TRAIN"],
        "validation_partition_fingerprint": partition_fingerprints[
            "VALIDATION_AND_CALIBRATION"],
        "code_commit": identity["implementation_commit"], "weights": [0.1],
        "ablation_execution_artifact": None}
    if identity["model_id"] in _NEURAL:
        from bot2.phase5c_v3.experiment_controls import (
            create_ablation_contract, create_model_input_contract)
        ablation = create_ablation_contract(VERIFIED, identity["ablation_id"])
        input_contract = create_model_input_contract(VERIFIED,
            model_id=identity["model_id"], seed=identity["seed"],
            ablation_id=identity["ablation_id"])
        execution = {"schema_version": "bot2-phase5c-v3-fixed-dimension-ablation-v2",
            "execution_type": "ENGINEERING_FIXED_DIMENSION_MASK_ONLY",
            "manifest_sha256": VERIFIED.sha256,
            "implementation_candidate_commit": identity["implementation_commit"],
            "ablation_id": identity["ablation_id"],
            "ablation_sha256": ablation["ablation_sha256"],
            "model_id": identity["model_id"], "seed": identity["seed"],
            "input_contract_sha256": input_contract["contract_sha256"],
            "input_feature_order": list(ablation["canonical_feature_order"]),
            "feature_mask": list(ablation["feature_mask"]), "input_channels": 24,
            "preprocessing_version": "train-unique-row-population-zscore-v1",
            "preprocessing_sha256": _sha(preprocessing),
            "transformed_rows_sha256": _sha(["fixture-row"]), "row_count": 1,
            "predictions_generated": False, "metrics_generated": False,
            "protected_models_scored": [], "trading_authority": "NONE"}
        execution["execution_sha256"] = _sha(execution)
        model["ablation_execution_artifact"] = execution
        model["input_shape"] = [8, 24]
        if identity["model_id"] == "A2_LEARNED_CAUSAL_TCN":
            model["parameter_count"] = 7417
    model["artifact_sha256"] = _sha({key: value for key, value in model.items()
        if key != "manifest_sha256"})
    prediction = {"target_head": identity["head"],
        "row_identities": ["row-1", "row-2"], "predictions": [0, 1]}
    prediction["prediction_sha256"] = _sha(prediction)
    metric_definition = {"name": "accuracy", "head": identity["head"]}
    metric_definition["metric_definition_sha256"] = _sha(metric_definition)
    calibration = None
    abstention = None
    if identity["model_id"] in _NEURAL:
        calibration = {"head": identity["head"], "market": identity["root"],
            "horizon_minutes": identity["horizon_minutes"],
            "model_artifact_sha256": model["artifact_sha256"]}
        calibration["calibration_sha256"] = _sha(calibration)
        abstention = {"head": identity["head"],
            "model_artifact_sha256": model["artifact_sha256"], "threshold": 0.5}
    checkpoint = None
    if identity["model_id"] == "A2_LEARNED_CAUSAL_TCN":
        checkpoint = {"selected_state": {"weights": [0.1]}, "selected_epoch": 1,
            "validation_loss": 1.0, "selection_partition": "VALIDATION_AND_CALIBRATION",
            "model_artifact_sha256": model["artifact_sha256"],
            "partition_fingerprints": dict(partition_fingerprints)}
        checkpoint["checkpoint_sha256"] = _sha(checkpoint)
    return {"information_contract": info,
        "preprocessing_artifact": preprocessing,
        "model_artifact": model,
        "checkpoint_artifact": checkpoint,
        "calibration_artifact": calibration,
        "abstention_artifact": abstention,
        "common_comparison_row_identity": _sha(["row-1", "row-2"]),
        "prediction_artifact": prediction,
        "metric_definition": metric_definition, "metrics": {"accuracy": 0.5}}


def test_cell_artifact_cannot_be_substituted_across_frozen_identity_axes():
    ledger = expected_cell_ledger(VERIFIED)
    cell_a = ledger["cells"][0]
    fingerprints = {key: _sha(key) for key in
        ("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")}
    artifact = create_cell_result_artifact(VERIFIED, cell=cell_a,
        partition_fingerprints=fingerprints,
        result=_cell_result_payload(cell_a, fingerprints))
    for field in ("root", "horizon_minutes", "seed", "walk_forward_window", "model_id",
                  "ablation_id", "control_condition", "head"):
        cell_b = next(item for item in ledger["cells"]
                      if item["identity"][field] != cell_a["identity"][field])
        with pytest.raises(ValueError, match="MATRIX_CELL_RESULT_LINEAGE_OR_SAFETY_MISMATCH"):
            load_cell_result_artifact(VERIFIED, cell=cell_b, artifact=artifact)

    forged = dict(artifact, model_id="A2_LEARNED_CAUSAL_TCN")
    forged["artifact_sha256"] = _sha({k:v for k,v in forged.items() if k != "artifact_sha256"})
    with pytest.raises(ValueError, match="MATRIX_CELL_RESULT_LINEAGE_OR_SAFETY_MISMATCH"):
        load_cell_result_artifact(VERIFIED, cell=cell_a, artifact=forged)

    partition_forgery = copy.deepcopy(artifact)
    partition_forgery["partition_fingerprints"]["TRAIN"] = _sha("foreign-partition")
    partition_forgery["artifact_sha256"] = _sha({k: v for k, v in partition_forgery.items()
        if k != "artifact_sha256"})
    with pytest.raises(ValueError, match="MATRIX_CELL_RESULT_COMPONENT_LINEAGE_MISMATCH"):
        load_cell_result_artifact(VERIFIED, cell=cell_a, artifact=partition_forgery)


def test_stage_checkpoint_recovery_rejects_partial_corrupt_and_wrong_lineage():
    cell = expected_cell_ledger(VERIFIED)["cells"][0]
    partitions = {key: _sha(key) for key in
        ("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")}
    checkpoint = create_stage_checkpoint(VERIFIED, cell=cell,
        stage="PREPROCESSING_COMPLETE", partition_fingerprints=partitions,
        upstream_artifact_hashes={"dataset": _sha("dataset")},
        payload={"mean": [0.0], "scale": [1.0]})
    assert classify_stage_checkpoint(expected_lineage=checkpoint["lineage"],
        artifact=checkpoint)["status"] == "REUSABLE_COMPLETE"
    partial = create_stage_checkpoint(VERIFIED, cell=cell,
        stage="MODEL_TRAINING_COMPLETE", partition_fingerprints=partitions,
        upstream_artifact_hashes={"preprocessing": checkpoint["artifact_sha256"]},
        payload={"weights": [0.1]}, status="PARTIAL")
    assert classify_stage_checkpoint(expected_lineage=partial["lineage"],
        artifact=partial)["status"] == "PARTIAL"
    wrong_lineage = dict(checkpoint["lineage"], seed=999)
    assert classify_stage_checkpoint(expected_lineage=wrong_lineage,
        artifact=checkpoint)["status"] == "LINEAGE_MISMATCH"
    corrupt = dict(checkpoint, payload={"mean": [9.0]})
    assert classify_stage_checkpoint(expected_lineage=checkpoint["lineage"],
        artifact=corrupt)["status"] == "CORRUPTED"


def test_stage_checkpoint_publish_is_atomic_and_never_overwrites(tmp_path):
    cell = expected_cell_ledger(VERIFIED)["cells"][0]
    partitions = {key: _sha(key) for key in
        ("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")}
    checkpoint = create_stage_checkpoint(VERIFIED, cell=cell,
        stage="DATA_PARTITION_VERIFIED", partition_fingerprints=partitions,
        upstream_artifact_hashes={}, payload={"fixture": "synthetic"})
    target = tmp_path / "data-stage.json"
    digest = publish_stage_checkpoint(target, checkpoint)
    assert digest == hashlib.sha256(target.read_bytes()).hexdigest()
    assert load_stage_checkpoint(target,
        expected_lineage=checkpoint["lineage"]) == checkpoint
    with pytest.raises(ValueError, match="STAGE_CHECKPOINT_ALREADY_PUBLISHED"):
        publish_stage_checkpoint(target, checkpoint)

    partial_path = tmp_path / "partial.json"
    partial_path.write_text('{"schema_version":', encoding="utf-8")
    with pytest.raises(ValueError, match="STAGE_CHECKPOINT_PARTIAL_OR_MALFORMED"):
        load_stage_checkpoint(partial_path, expected_lineage=checkpoint["lineage"])


def test_resume_restarts_after_each_interrupted_stage_without_skipping():
    stages = ("DATA_PARTITION_VERIFIED", "PREPROCESSING_COMPLETE",
        "MODEL_TRAINING_COMPLETE", "CHECKPOINT_SELECTED", "CALIBRATION_COMPLETE",
        "PREDICTIONS_COMPLETE", "METRICS_COMPLETE", "RESULT_PUBLISHED")
    cell = expected_cell_ledger(VERIFIED)["cells"][0]
    partitions = {key: _sha(key) for key in
        ("TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST")}
    completed = {}
    for stage in stages:
        prior_stage = stages[stages.index(stage) - 1] if stages.index(stage) else None
        upstream = ({prior_stage: completed[prior_stage]["artifact_sha256"]}
                    if prior_stage else {})
        completed[stage] = create_stage_checkpoint(VERIFIED, cell=cell,
            stage=stage, partition_fingerprints=partitions,
            upstream_artifact_hashes=upstream, payload={"stage": stage})
    expected = {stage: completed[stage]["lineage"] for stage in stages}
    for interrupted_index in range(len(stages)):
        observed = {stage: completed[stage] for stage in stages[:interrupted_index]}
        plan = plan_stage_resume(checkpoints=observed, expected_lineage_by_stage=expected)
        assert plan["reused_stages"] == list(stages[:interrupted_index])
        assert plan["resume_from"] == stages[interrupted_index]
    plan = plan_stage_resume(checkpoints=completed, expected_lineage_by_stage=expected)
    assert plan["reused_stages"] == list(stages) and plan["resume_from"] is None

    partial = dict(completed)
    partial["CALIBRATION_COMPLETE"] = create_stage_checkpoint(VERIFIED, cell=cell,
        stage="CALIBRATION_COMPLETE", partition_fingerprints=partitions,
        upstream_artifact_hashes={"CHECKPOINT_SELECTED":
            completed["CHECKPOINT_SELECTED"]["artifact_sha256"]},
        payload={"stage": "CALIBRATION_COMPLETE"}, status="PARTIAL")
    plan = plan_stage_resume(checkpoints=partial, expected_lineage_by_stage=expected)
    assert plan["reused_stages"] == list(stages[:4])
    assert plan["resume_from"] == "CALIBRATION_COMPLETE"

    wrong_upstream = dict(expected)
    wrong_upstream["PREPROCESSING_COMPLETE"] = dict(
        expected["PREPROCESSING_COMPLETE"],
        upstream_artifact_hashes={"DATA_PARTITION_VERIFIED": "0" * 64})
    plan = plan_stage_resume(checkpoints=completed,
        expected_lineage_by_stage=wrong_upstream)
    assert plan["resume_from"] == "PREPROCESSING_COMPLETE"
    assert plan["reused_stages"] == ["DATA_PARTITION_VERIFIED"]


def test_cell_state_machine_requires_computation_before_completion():
    ledger = expected_cell_ledger(VERIFIED)
    cell_id = ledger["cells"][0]["cell_sha256"]
    with pytest.raises(ValueError, match="MATRIX_CELL_TRANSITION_INVALID"):
        transition_cell(ledger, verified=VERIFIED, cell_sha256=cell_id, status="COMPLETE")
    dispatched = transition_cell(ledger, verified=VERIFIED,
        cell_sha256=cell_id, status="DISPATCHED")
    with pytest.raises(ValueError, match="MATRIX_CELL_TRANSITION_INVALID"):
        transition_cell(dispatched, verified=VERIFIED,
            cell_sha256=cell_id, status="COMPLETE")
    running = transition_cell(dispatched, verified=VERIFIED,
        cell_sha256=cell_id, status="RUNNING")
    partial = transition_cell(running, verified=VERIFIED,
        cell_sha256=cell_id, status="PARTIAL")
    evaluation = evaluate_complete_matrix(partial, verified=VERIFIED)
    assert evaluation["partial"] == 1 and evaluation["status"] == "INCOMPLETE"


def test_walk_forward_rows_bind_data_fingerprints_and_embargo():
    result = validate_walk_forward_rows(VERIFIED, root="ES", horizon_minutes=5,
        window_id="WF1", rows_by_partition=_wf_rows())
    assert result["window_id"] == "WF1"
    assert set(result["partition_fingerprints"]) == {
        "TRAIN", "VALIDATION_AND_CALIBRATION", "OOS_TEST"}
    assert len(result["partition_fingerprints"]["TRAIN"]) == 64
    assert result["excluded_row_ids"]["VALIDATION_AND_CALIBRATION"]
    assert result["eligible_row_ids"]["VALIDATION_AND_CALIBRATION"]
    assert result["eligible_sequence_observation_ids"]["VALIDATION_AND_CALIBRATION"]
    assert result["excluded_row_ids"]["OOS_TEST"]


def test_authorized_split_accepts_only_manifest_derived_walk_forward_window():
    from bot2.phase5c_v3.model import TrainingOnlyStandardizer
    rows = _wf_rows()
    scaler = TrainingOnlyStandardizer().fit_observations(rows["TRAIN"], market="ES",
        verified_manifest=VERIFIED, code_commit=TEST_COMMIT)
    split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
        partition_rows=rows, preprocessor=scaler, walk_forward_window_id="WF1")
    assert split.walk_forward_window_id == "WF1"
    validate_authorized_split(split, VERIFIED)
    object.__setattr__(split, "walk_forward_window_id", "WF2")
    with pytest.raises(ValueError, match="PARTITION_TIMESTAMP_OUTSIDE_MANIFEST_WINDOW"):
        validate_authorized_split(split, VERIFIED)


def test_walk_forward_rejects_unauthorized_dates_overlap_and_purge():
    rows = _wf_rows()
    rows["TRAIN"][0] = _row("2025-08-01", 0)
    with pytest.raises(ValueError, match="CALLER_SUPPLIED_UNAUTHORIZED_WINDOW_DATE"):
        validate_walk_forward_rows(VERIFIED, root="ES", horizon_minutes=5,
            window_id="WF1", rows_by_partition=rows)

    rows = _wf_rows()
    rows["VALIDATION_AND_CALIBRATION"][0] = rows["TRAIN"][0]
    with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION_CROSSES_PARTITION"):
        validate_walk_forward_rows(VERIFIED, root="ES", horizon_minutes=5,
            window_id="WF1", rows_by_partition=rows)

    rows = _wf_rows(train_day="2025-07-31")
    rows["TRAIN"] = _partition("2025-07-31", count=40, start_minute=521)
    rows["VALIDATION_AND_CALIBRATION"] = _partition(
        "2025-08-01", start_time="00:00:00", count=40, start_minute=20)
    with pytest.raises(ValueError, match="WALK_FORWARD_PURGE_VIOLATION"):
        validate_walk_forward_rows(VERIFIED, root="ES", horizon_minutes=5,
            window_id="WF1", rows_by_partition=rows)


def test_common_comparison_record_hashes_raw_and_intersection_sets():
    models = _A0 + _NEURAL
    rows = {model: ["r1", "r2", "r3"] for model in models}
    rows[_NEURAL[1]] = ["r2", "r3", "r4"]
    metadata = {model: {"window": "WF1", "horizon": 5, "seed": 1,
                        "ablation": "ALL", "model_id": model} for model in models}
    result = common_comparison_record(model_eligible_rows=rows,
        model_metadata=metadata, metric_identity="categorical_log_loss")
    assert result["common_comparison_row_ids"] == ["r2", "r3"]
    assert result["common_comparison_row_count"] == 2
    assert result["record_sha256"] == _sha({k: v for k, v in result.items() if k != "record_sha256"})


def test_common_comparison_rejects_missing_model_or_duplicate_row():
    models = _A0 + _NEURAL
    rows = {model: ["r1"] for model in models}
    metadata = {model: {"model_id": model} for model in models}
    with pytest.raises(ValueError, match="COMPARISON_MODEL_SET_INCOMPLETE"):
        common_comparison_record(model_eligible_rows={"A0": ["r1"]},
            model_metadata=metadata, metric_identity="metric-v1")
    rows[_A0[0]] = ["r1", "r1"]
    with pytest.raises(ValueError, match="COMPARISON_DUPLICATE_ELIGIBLE_ROW"):
        common_comparison_record(model_eligible_rows=rows,
            model_metadata=metadata, metric_identity="metric-v1")


def test_resume_requires_every_frozen_lineage_field_and_content_hash():
    fields = ("protocol_version", "manifest_sha256", "implementation_commit",
        "dataset_identity", "experiment_cell_sha256", "partition_fingerprints",
        "model_identity", "ablation_identity", "seed", "preprocessing_sha256",
        "model_sha256", "calibration_sha256", "prediction_sha256")
    lineage = {key: f"value-{key}" for key in fields}
    payload = {"predictions": [0, 1], "metrics": {"synthetic": 1.0}}
    artifact = {"schema_version": RESUME_SCHEMA, "status": "COMPLETE",
        "lineage": lineage, "payload": payload, "payload_sha256": _sha(payload)}
    artifact["artifact_sha256"] = _sha(artifact)
    assert classify_resume_artifact(expected_lineage=lineage, artifact=artifact)["status"] == "REUSABLE_COMPLETE"
    wrong = dict(lineage, dataset_identity="wrong")
    assert classify_resume_artifact(expected_lineage=wrong, artifact=artifact)["status"] == "LINEAGE_MISMATCH"
    corrupted = dict(artifact, payload={"predictions": [9]})
    assert classify_resume_artifact(expected_lineage=lineage, artifact=corrupted)["status"] == "CORRUPTED"
    partial = dict(artifact, status="PARTIAL")
    assert classify_resume_artifact(expected_lineage=lineage, artifact=partial)["status"] == "PARTIAL"
