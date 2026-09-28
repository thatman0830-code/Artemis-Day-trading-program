"""Focused synthetic-only tests for the Phase 5C-Y orchestration boundary."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
import bot2.phase5c_v3.experiment_runner as experiment_runner
from bot2.phase5c_v3.experiment_runner import (Phase5CExecutionError, load_runner_result,
    run_phase5c_experiment, _run_synthetic_validation_bundle as run_synthetic_validation_for_fixture,
    _orchestrate_synthetic_matrix, _verify_resume_identity, execute_synthetic_cell,
    execute_synthetic_matrix_cells,
    verify_runner_result)
from bot2.phase5c_v3.test_phase5c_v3 import ROOT, TEST_ANCHOR_PATH, VERIFIED

def test_protected_mode_is_denied_before_opening_manifest_or_dataset(tmp_path):
    with pytest.raises(Phase5CExecutionError, match="PROTECTED_OOS_NOT_AUTHORIZED"):
        run_phase5c_experiment("PROTECTED_OOS", manifest_path=tmp_path/"missing.json",
            external_anchor_path=tmp_path/"missing-anchor.json", repo_root=ROOT,
            dataset_root=tmp_path/"protected-data")

def test_execution_mode_is_a_closed_set():
    with pytest.raises(Phase5CExecutionError, match="EXECUTION_MODE_INVALID"):
        run_phase5c_experiment("SYNTHETIC_VALIDATION --allow-oos",
            manifest_path=ROOT/"config/bot2_phase5c_experiment_manifest_v3.json",
            external_anchor_path=TEST_ANCHOR_PATH)

def test_public_synthetic_entrypoint_requires_clean_pinned_repository():
    with pytest.raises(Phase5CExecutionError, match="IMPLEMENTATION_WORKTREE_NOT_CLEAN"):
        run_phase5c_experiment("SYNTHETIC_VALIDATION",
            manifest_path=ROOT/"config/bot2_phase5c_experiment_manifest_v3.json",
            external_anchor_path=TEST_ANCHOR_PATH, repo_root=ROOT)

def test_runner_matrix_orchestration_routes_every_manifest_cell_without_scoring():
    result = _orchestrate_synthetic_matrix(VERIFIED)
    assert result["expected_cell_count"] == 5184
    assert result["dispatched_cell_count"] == result["unique_dispatched_cell_count"] == 5184
    assert result["dispatch_reconciled"] is True
    assert result["incomplete_cell_count"] == 5184
    assert result["experiment_complete"] is False
    assert result["protected_models_scored"] == result["protected_oos_scores_produced"] == 0
    assert result["trading_authority"] == "NONE"
    coverage = result["walk_forward_coverage"]
    expected_coverage = (len(VERIFIED.data["source_dataset"]["contracts"])
        * len(VERIFIED.data["target_specification"]["horizons_minutes"])
        * len(VERIFIED.data["walk_forward_windows_inclusive"]))
    assert coverage["expected_combinations"] == expected_coverage
    assert coverage["validated_combinations"] == expected_coverage
    assert all(record["baseline_model_ids"] == list(experiment_runner._A0)
        and record["validation_prediction_row_count"] > 0
        and record["oos_engineering_row_count"] > 0
        and set(record["baseline_metrics_by_head"]) == set(experiment_runner._A0)
        for record in coverage["records"])

    # A bad router receipt is rejected by the runner's reconciliation gate.
    first_cell_id = experiment_runner.expected_cell_ledger(VERIFIED)["cells"][0]["cell_sha256"]
    def altered_identity(cell):
        receipt = experiment_runner._dispatch_synthetic_cell(cell)
        if cell["cell_sha256"] == first_cell_id:
            receipt["identity"]["root"] = "INVALID"
        return receipt
    with pytest.raises(Phase5CExecutionError, match="MATRIX_DISPATCH_RECONCILIATION_FAILED"):
        _orchestrate_synthetic_matrix(VERIFIED, dispatcher=altered_identity)


def test_manifest_selected_cell_executes_and_publishes_its_own_result():
    ledger = experiment_runner.expected_cell_ledger(VERIFIED)
    cell = next(item for item in ledger["cells"]
        if item["identity"]["root"] == "NQ"
        and item["identity"]["horizon_minutes"] == 15
        and item["identity"]["walk_forward_window"] == "WF2"
        and item["identity"]["model_id"] == "A0_TRAIN_MAJORITY"
        and item["identity"]["head"] == "direction")
    artifact = execute_synthetic_cell(VERIFIED, cell=cell)
    assert artifact["cell_sha256"] == cell["cell_sha256"]
    assert artifact["root"] == "NQ" and artifact["horizon_minutes"] == 15
    assert artifact["walk_forward_window"] == "WF2"
    assert artifact["model_id"] == "A0_TRAIN_MAJORITY"
    from bot2.phase5c_v3.experiment_matrix import load_cell_result_artifact
    assert load_cell_result_artifact(VERIFIED, cell=cell,
        artifact=artifact)["artifact_sha256"] == artifact["artifact_sha256"]

def test_complete_a0_cell_path_covers_each_root_horizon_and_walk_forward_window():
    ledger = experiment_runner.expected_cell_ledger(VERIFIED)
    cells = {(item["identity"]["root"], item["identity"]["horizon_minutes"],
        item["identity"]["walk_forward_window"]): item for item in ledger["cells"]
        if item["identity"]["model_id"] == "A0_TRAIN_MAJORITY"
        and item["identity"]["ablation_id"] == "ALL"
        and item["identity"]["control_condition"] == "NONE"
        and item["identity"]["head"] == "direction"}
    expected = {(root, horizon, window.window_id)
        for root in VERIFIED.data["source_dataset"]["contracts"]
        for horizon in VERIFIED.data["target_specification"]["horizons_minutes"]
        for window in experiment_runner.derive_walk_forward_windows(VERIFIED)}
    assert set(cells) == expected
    completed = []
    from bot2.phase5c_v3.experiment_matrix import load_cell_result_artifact
    for combo in sorted(expected):
        cell = cells[combo]
        artifact = execute_synthetic_cell(VERIFIED, cell=cell)
        load_cell_result_artifact(VERIFIED, cell=cell, artifact=artifact)
        completed.append((artifact["root"], artifact["horizon_minutes"],
            artifact["walk_forward_window"]))
    assert set(completed) == expected and len(completed) == len(expected) == 24


def test_manifest_selected_a2_shuffled_control_cell_is_executed_exactly():
    ledger = experiment_runner.expected_cell_ledger(VERIFIED)
    cell = next(item for item in ledger["cells"]
        if item["identity"]["root"] == "ES"
        and item["identity"]["horizon_minutes"] == 5
        and item["identity"]["walk_forward_window"] == "WF1"
        and item["identity"]["model_id"] == "A2_LEARNED_CAUSAL_TCN"
        and item["identity"]["ablation_id"] == "ALL"
        and item["identity"]["control_condition"].startswith("SHUFFLED_TRAIN_LABELS:")
        and item["identity"]["seed"] == 1
        and item["identity"]["head"] == "direction")
    artifact = execute_synthetic_cell(VERIFIED, cell=cell)
    assert artifact["cell_sha256"] == cell["cell_sha256"]
    assert artifact["control_identity"] == cell["identity"]["control_condition"]
    assert artifact["result"]["model_artifact"]["training_label_control_sha256"]
    from bot2.phase5c_v3.experiment_matrix import load_cell_result_artifact
    assert load_cell_result_artifact(VERIFIED, cell=cell,
        artifact=artifact)["artifact_sha256"] == artifact["artifact_sha256"]


@pytest.mark.parametrize("model_id", ["A1_NUMPY_MULTIHEAD_MLP", "A2_LEARNED_CAUSAL_TCN"])
def test_real_model_training_stage_interrupt_resume_matches_clean_run(tmp_path, model_id):
    from bot2.phase5c_v3.experiment_matrix import load_cell_result_artifact
    cell = next(item for item in experiment_runner.expected_cell_ledger(VERIFIED)["cells"]
        if item["identity"]["root"] == "ES"
        and item["identity"]["horizon_minutes"] == 5
        and item["identity"]["walk_forward_window"] == "WF1"
        and item["identity"]["model_id"] == model_id
        and item["identity"]["ablation_id"] == "ALL"
        and item["identity"]["control_condition"] == "NONE"
        and item["identity"]["seed"] == 1
        and item["identity"]["head"] == "direction")
    clean = execute_synthetic_cell(VERIFIED, cell=cell)
    stage_directory = tmp_path / "stages"
    with pytest.raises(Phase5CExecutionError,
            match="ENGINEERING_INTERRUPTION_INJECTED_MODEL_TRAINING_COMPLETE"):
        execute_synthetic_cell(VERIFIED, cell=cell,
            stage_directory=stage_directory,
            interrupt_after_stage="MODEL_TRAINING_COMPLETE")
    stage_path = stage_directory / f"{cell['cell_sha256']}.model_training.json"
    assert stage_path.is_file()
    resumed = execute_synthetic_cell(VERIFIED, cell=cell,
        stage_directory=stage_directory)
    assert resumed["artifact_sha256"] == clean["artifact_sha256"]
    assert resumed["result"]["prediction_artifact"] == clean["result"]["prediction_artifact"]
    assert load_cell_result_artifact(VERIFIED, cell=cell,
        artifact=resumed)["artifact_sha256"] == clean["artifact_sha256"]


def test_real_stage_resume_rejects_wrong_cell_lineage_and_truncated_checkpoint(tmp_path):
    cell = next(item for item in experiment_runner.expected_cell_ledger(VERIFIED)["cells"]
        if item["identity"]["model_id"] == "A1_NUMPY_MULTIHEAD_MLP"
        and item["identity"]["head"] == "direction")
    stage_directory = tmp_path / "stages"
    with pytest.raises(Phase5CExecutionError, match="ENGINEERING_INTERRUPTION_INJECTED"):
        execute_synthetic_cell(VERIFIED, cell=cell, stage_directory=stage_directory,
            interrupt_after_stage="MODEL_TRAINING_COMPLETE")
    stage_path = stage_directory / f"{cell['cell_sha256']}.model_training.json"
    original = stage_path.read_text(encoding="utf-8")
    lineage_fields = ("manifest_sha256", "implementation_identity", "dataset_identity",
        "experiment_cell_sha256", "root", "horizon_minutes", "seed",
        "walk_forward_window", "model_id", "ablation_id", "control_identity",
        "target_head", "stage_schema", "stage", "partition_fingerprints",
        "upstream_artifact_hashes")
    for field in lineage_fields:
        wrong_lineage = json.loads(original)
        if field == "partition_fingerprints":
            wrong_lineage["lineage"][field]["TRAIN"] = "0" * 64
        elif field == "upstream_artifact_hashes":
            wrong_lineage["lineage"][field]["preprocessing_sha256"] = "0" * 64
        else:
            wrong_lineage["lineage"][field] = "WRONG_LINEAGE"
        stage_path.write_text(json.dumps(wrong_lineage), encoding="utf-8")
        with pytest.raises(Phase5CExecutionError, match="STAGE_CHECKPOINT_REJECTED"):
            execute_synthetic_cell(VERIFIED, cell=cell, stage_directory=stage_directory)
    stage_path.write_text(original, encoding="utf-8")
    corrupt = json.loads(original)
    corrupt["payload"]["validation_logits"][0][0] += 1.0
    stage_path.write_text(json.dumps(corrupt), encoding="utf-8")
    with pytest.raises(Phase5CExecutionError, match="STAGE_CHECKPOINT_REJECTED"):
        execute_synthetic_cell(VERIFIED, cell=cell, stage_directory=stage_directory)
    stage_path.write_text(original, encoding="utf-8")
    stage_path.write_text(original[:-10], encoding="utf-8")
    with pytest.raises(Phase5CExecutionError, match="STAGE_CHECKPOINT_REJECTED"):
        execute_synthetic_cell(VERIFIED, cell=cell, stage_directory=stage_directory)


def test_real_stage_resume_rejects_checkpoint_substitution_to_another_cell(tmp_path):
    ledger = experiment_runner.expected_cell_ledger(VERIFIED)
    cell = next(item for item in ledger["cells"]
        if item["identity"]["model_id"] == "A1_NUMPY_MULTIHEAD_MLP"
        and item["identity"]["root"] == "ES"
        and item["identity"]["horizon_minutes"] == 5
        and item["identity"]["walk_forward_window"] == "WF1"
        and item["identity"]["control_condition"] == "NONE"
        and item["identity"]["ablation_id"] == "ALL"
        and item["identity"]["head"] == "direction")
    foreign = next(item for item in ledger["cells"]
        if item["identity"]["model_id"] == "A1_NUMPY_MULTIHEAD_MLP"
        and item["identity"]["root"] == "ES"
        and item["identity"]["horizon_minutes"] == 15
        and item["identity"]["walk_forward_window"] == "WF1"
        and item["identity"]["control_condition"] == "NONE"
        and item["identity"]["ablation_id"] == "ALL"
        and item["identity"]["head"] == "direction")
    stage_directory = tmp_path / "stages"
    with pytest.raises(Phase5CExecutionError, match="ENGINEERING_INTERRUPTION_INJECTED"):
        execute_synthetic_cell(VERIFIED, cell=cell, stage_directory=stage_directory,
            interrupt_after_stage="MODEL_TRAINING_COMPLETE")
    foreign_path = stage_directory / f"{foreign['cell_sha256']}.model_training.json"
    stage_path = stage_directory / f"{cell['cell_sha256']}.model_training.json"
    foreign_path.write_bytes(stage_path.read_bytes())
    with pytest.raises(Phase5CExecutionError, match="STAGE_CHECKPOINT_REJECTED"):
        execute_synthetic_cell(VERIFIED, cell=foreign, stage_directory=stage_directory)


def test_real_stage_resume_rejects_unexpected_artifact_and_symlink(tmp_path, monkeypatch):
    from pathlib import Path
    cell = next(item for item in experiment_runner.expected_cell_ledger(VERIFIED)["cells"]
        if item["identity"]["model_id"] == "A1_NUMPY_MULTIHEAD_MLP"
        and item["identity"]["head"] == "direction")
    stage_directory = tmp_path / "stages"
    stage_directory.mkdir()
    (stage_directory / "unexpected.tmp").write_text("not a stage", encoding="utf-8")
    with pytest.raises(Phase5CExecutionError, match="STAGE_CHECKPOINT_ARTIFACT_SET_INVALID"):
        execute_synthetic_cell(VERIFIED, cell=cell, stage_directory=stage_directory)
    (stage_directory / "unexpected.tmp").unlink()
    target = stage_directory / f"{cell['cell_sha256']}.model_training.json"
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink",
        lambda self: True if self == target else original_is_symlink(self))
    with pytest.raises(Phase5CExecutionError, match="STAGE_CHECKPOINT_SYMLINK_REJECTED"):
        execute_synthetic_cell(VERIFIED, cell=cell, stage_directory=stage_directory)

def test_disk_matrix_executor_publishes_and_recovers_terminal_cell(tmp_path):
    ledger = experiment_runner.expected_cell_ledger(VERIFIED)
    cell = next(item for item in ledger["cells"]
        if item["identity"]["root"] == "ES"
        and item["identity"]["model_id"] == "A0_TRAIN_MAJORITY"
        and item["identity"]["head"] == "direction")
    out = tmp_path / "matrix"
    first = execute_synthetic_matrix_cells(VERIFIED, result_directory=out,
        cell_ids=[cell["cell_sha256"]])
    assert first["expected_cell_count"] == first["dispatched_cell_count"] == 5184
    assert first["verified_result_artifact_count"] == 1
    assert first["matrix_summary"]["status"] == "INCOMPLETE"
    assert first["matrix_summary"]["complete"] == 1
    assert first["matrix_summary"]["missing"] == 0
    assert first["matrix_summary"]["in_progress"] == 5183
    assert first["protected_models_scored"] == first["protected_oos_scores_produced"] == 0
    assert first["trading_authority"] == "NONE"

    # Simulate interruption after immutable artifact publication but before the
    # ledger's COMPLETE transition. The next invocation must validate and reuse it.
    ledger_path = out / "matrix_ledger.json"
    saved = json.loads(ledger_path.read_text(encoding="utf-8"))
    target = next(item for item in saved["cells"]
        if item["cell_sha256"] == cell["cell_sha256"])
    target["status"] = "RUNNING"
    target["result_artifact_sha256"] = None
    saved["ledger_sha256"] = experiment_runner._sha({k: v for k, v in saved.items()
        if k != "ledger_sha256"})
    ledger_path.write_text(json.dumps(saved), encoding="utf-8")
    recovered = execute_synthetic_matrix_cells(VERIFIED, result_directory=out,
        cell_ids=[cell["cell_sha256"]], executor=lambda *_args, **_kwargs:
            pytest.fail("verified published result should be recovered without recompute"))
    assert recovered["verified_result_artifact_count"] == 1
    recovered_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    recovered_cell = next(item for item in recovered_ledger["cells"]
        if item["cell_sha256"] == cell["cell_sha256"])
    assert recovered_cell["status"] == "COMPLETE"
    assert recovered_cell["result_artifact_sha256"]
    assert sum(item["status"] == "DISPATCHED" for item in recovered_ledger["cells"]) == 5183

def test_disk_matrix_executor_rejects_unknown_or_duplicate_selection(tmp_path):
    cell = experiment_runner.expected_cell_ledger(VERIFIED)["cells"][0]
    with pytest.raises(Phase5CExecutionError, match="MATRIX_EXECUTION_CELL_SELECTION_INVALID"):
        execute_synthetic_matrix_cells(VERIFIED, result_directory=tmp_path / "bad",
            cell_ids=[cell["cell_sha256"], cell["cell_sha256"]])

def test_existing_output_is_immutable_and_rejected_before_work(tmp_path):
    output=tmp_path/"run"; output.mkdir(); marker=output/"keep.txt"; marker.write_text("preserve")
    with pytest.raises(Phase5CExecutionError, match="IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS"):
        run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=99)
    assert marker.read_text()=="preserve"

def test_failure_is_atomic_machine_readable_and_non_resumable(tmp_path):
    output=tmp_path/"failed-run"
    with pytest.raises(Phase5CExecutionError, match="SEED_NOT_IN_MANIFEST"):
        run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=99)
    assert [p.name for p in output.iterdir()]==["failure.json"]
    failure=json.loads((output/"failure.json").read_text())
    assert failure["status"]=="FAILED" and failure["reason_code"]=="SEED_NOT_IN_MANIFEST"
    assert failure["protected_models_scored"]==failure["protected_oos_scores_produced"]==0
    digest=failure.pop("failure_artifact_sha256")
    from bot2.phase5c_v3.manifest import canonical_bytes
    import hashlib
    assert digest==hashlib.sha256(canonical_bytes(failure)).hexdigest()
    with pytest.raises(Phase5CExecutionError, match="IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS"):
        run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=1)

def test_synthetic_end_to_end_artifacts_are_reproducible_and_verifiable(tmp_path):
    first=run_synthetic_validation_for_fixture(VERIFIED, output_directory=tmp_path/"first", seed=1)
    second=run_synthetic_validation_for_fixture(VERIFIED, output_directory=tmp_path/"second", seed=1)
    assert first["result_artifact_sha256"]==second["result_artifact_sha256"]
    assert first["prediction_artifact_sha256"]==second["prediction_artifact_sha256"]
    assert first["status"]=="REPRESENTATIVE_COMPUTE_COMPLETE_MATRIX_INCOMPLETE"
    assert first["experiment_status"]=="INCOMPLETE_MATRIX"
    assert first["matrix_orchestration"]["expected_cell_count"]==5184
    assert first["matrix_orchestration"]["dispatched_cell_count"]==5184
    assert first["matrix_orchestration"]["experiment_complete"] is False
    assert len(first["comparison_records"]) == 18
    assert all(item["common_comparison_row_count"] > 0 for item in first["comparison_records"])
    assert all(item["metrics_must_use_identical_rows"] for item in first["comparison_records"])
    assert first["protected_models_scored"]==first["protected_oos_scores_produced"]==0
    assert first["trading_authority"]=="NONE" and first["broker_path"] is False
    assert len(first["model_results"])==15 and len(first["ablation_executions"])==6
    assert len(first["shuffled_label_controls"])==36
    assert all(r["model_training_executed"] for r in first["shuffled_label_controls"])
    loaded = load_runner_result(tmp_path/"first", VERIFIED)
    assert loaded["result_artifact_sha256"]==first["result_artifact_sha256"]
    resumed = _verify_resume_identity(loaded, VERIFIED, market="ES", horizon_minutes=5, seed=1)
    assert resumed["result_artifact_sha256"]==first["result_artifact_sha256"]
    with pytest.raises(Phase5CExecutionError, match="RESUME_LINEAGE_MISMATCH"):
        _verify_resume_identity(loaded, VERIFIED, market="NQ", horizon_minutes=5, seed=1)
    verify_runner_result(first, VERIFIED)

def test_corrupted_persisted_prediction_pair_is_rejected(tmp_path):
    output=tmp_path/"run"; run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=1)
    path=output/"predictions.json"; payload=json.loads(path.read_text()); payload["predictions"].clear()
    path.write_text(json.dumps(payload))
    with pytest.raises(Phase5CExecutionError): load_runner_result(output, VERIFIED)

def test_missing_extra_and_schema_invalid_artifacts_have_stable_reason_codes(tmp_path):
    output=tmp_path/"run"; run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=1)
    (output/"integrity.json").unlink()
    with pytest.raises(Phase5CExecutionError, match="RUNNER_ARTIFACT_FILE_MISSING"):
        load_runner_result(output, VERIFIED)

    output=tmp_path/"extra"; run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=1)
    (output/"notes.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(Phase5CExecutionError, match="RUNNER_ARTIFACT_FILE_SET_INVALID"):
        load_runner_result(output, VERIFIED)

    output=tmp_path/"schema"; run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=1)
    payload=json.loads((output/"integrity.json").read_text())
    payload["schema_version"]="unknown"
    (output/"integrity.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Phase5CExecutionError, match="RUNNER_ARTIFACT_SCHEMA_INVALID"):
        load_runner_result(output, VERIFIED)

def test_immutable_file_publish_race_does_not_overwrite_winner(tmp_path, monkeypatch):
    target=tmp_path/"artifact.json"
    real_link=experiment_runner.os.link
    def racing_link(source, destination):
        Path(destination).write_bytes(b"winner")
        return real_link(source, destination)
    monkeypatch.setattr(experiment_runner.os, "link", racing_link)
    with pytest.raises(Phase5CExecutionError, match="IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS"):
        experiment_runner._immutable_write(target, {"safe": True})
    assert target.read_bytes()==b"winner"

def test_output_directory_publish_race_preserves_existing_target(tmp_path, monkeypatch):
    output=tmp_path/"run"
    monkeypatch.setattr(experiment_runner, "_run_synthetic_validation",
        lambda *args, **kwargs: {"predictions": {}, "result_artifact_sha256": "unused"})
    monkeypatch.setattr(experiment_runner, "verify_runner_result", lambda *args: None)
    real_rename=experiment_runner.os.rename
    def racing_rename(source, destination):
        Path(destination).mkdir()
        (Path(destination)/"owner.txt").write_text("winner", encoding="utf-8")
        return real_rename(source, destination)
    monkeypatch.setattr(experiment_runner.os, "rename", racing_rename)
    with pytest.raises(Phase5CExecutionError, match="IMMUTABLE_RUN_ARTIFACT_ALREADY_EXISTS"):
        run_synthetic_validation_for_fixture(VERIFIED, output_directory=output, seed=1)
    assert (output/"owner.txt").read_text(encoding="utf-8")=="winner"
    assert not list(tmp_path.glob(".run.*"))
