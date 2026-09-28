from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import subprocess
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from bot2.phase5c_v3.artifacts import (create_artifact, load_artifact, save_artifact,
                                        verify_provenance_chain)
from bot2.phase5c_v3.manifest import (VerifiedManifest, canonical_hash, load_verified_manifest,
    load_and_verify_manifest, require_manifest_overrides_match, verify_git_binding,
    _VERIFIED_TOKEN)
from bot2.phase5c_v3.model import (ARCHITECTURE_VERSION, DILATIONS, HEADS,
    CausalTemporalConv, PartitionData, TrainingOnlyStandardizer,
    _conv_forward, expected_parameter_count, validate_partition_disjointness,
    validate_sequence_identities)
from bot2.phase5c_v3.runner import _frozen_control_checks, _verify_archive_audit_report
from bot2.phase5c_v3.data_integrity import (MarketObservation, build_authorized_split,
    feature_partition_fingerprint, validate_authorized_split)
from bot2.phase5c_v3.calibration import (fit_temperature_calibrator, fit_model_temperature_calibrator,
    verify_calibration_artifact, select_abstention_threshold,
    verify_abstention_artifact, create_result_lineage_contract,
    validate_result_lineage_contract)
from bot2.phase5c_v3.experiment_controls import (create_ablation_contract,
    create_model_input_contract, execute_ablation_control, execute_shuffled_label_control,
    apply_ablation_mask, validate_model_input_contract, verify_ablation_contract, verify_ablation_execution,
    verify_shuffled_label_control)
from bot2.phase5c_v3.results import (create_engineering_result_artifact,
    verify_engineering_result_artifact)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "config" / "bot2_phase5c_experiment_manifest_v3.json"
TEST_COMMIT = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
    check=True, capture_output=True, text=True, timeout=15).stdout.strip()
TEST_ANCHOR_PATH = Path(tempfile.gettempdir()) / "bot2-phase5c-v3-test-anchor.json"
TEST_ANCHOR_PATH.write_text(json.dumps({
    "anchor_type": "bot2-phase5c-v3-user-preserved-anchor-v1",
    "protocol_version": "bot2-phase5c-experiment-manifest-v3",
    "manifest_filename": MANIFEST_PATH.name,
    "canonical_manifest_sha256": "c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19",
    "dataset_manifest_sha256": "e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67",
    "raw_archive_tree_sha256": "405ff5602600fbe361c7136b85be0b26d46567c1c080dfefab2e506e109a775b",
    "feature_version": "bot2-feature-row-v3",
    "target_version": "bot2-future-market-state-v3",
    "frozen_protocol_anchor_commit": "9a1ecfaf08077252049dd187d44f8641da1186aa",
    "reviewed_implementation_commit": TEST_COMMIT,
    "review_candidate_commit": TEST_COMMIT,
    "phase5c_u_remediation_base_commit": "4f1d70620a230149046ee52565315de8b9166712",
    "anchor_created_utc": "2026-09-22T00:00:00Z",
    "signature_status": "UNSIGNED",
    "independent_custody_status": "NOT_CRYPTOGRAPHICALLY_PROVEN",
}, sort_keys=True), encoding="utf-8")
VERIFIED = load_verified_manifest(MANIFEST_PATH, external_anchor_path=TEST_ANCHOR_PATH)
FULL_COMMIT = TEST_COMMIT
DATASET_HASH = VERIFIED.data["source_dataset_manifest_sha256"]
FEATURE_NAMES = tuple(VERIFIED.data["feature_specification"]["features"])


def targets(n, offset=0):
    return {head: (np.arange(n, dtype=np.int64) + offset) % 3 for head in HEADS}


def seq_keys(n, *, start_minute=0, start_date="2026-01-05", contract="ESU6", session="RTH-2026-01-05"):
    origin = datetime.fromisoformat(start_date + "T14:30:00+00:00") + timedelta(minutes=start_minute)
    return tuple(tuple((contract, session, (origin + timedelta(minutes=i + j)).isoformat())
                       for j in range(8)) for i in range(n))


def model(seed=1):
    return CausalTemporalConv(VERIFIED, seed=seed)


def observations(day: str, contract: str, count: int, *, seed: int = 7,
                 start_time: str = "14:30:00") -> list[MarketObservation]:
    rng = np.random.default_rng(seed)
    origin = datetime.fromisoformat(f"{day}T{start_time}+00:00")
    session = f"RTH-{day}-{contract}"
    values = rng.normal(size=(count, len(FEATURE_NAMES)))
    return [MarketObservation("ES", contract, session,
        (origin + timedelta(minutes=i)).isoformat(), origin.isoformat(), FEATURE_NAMES,
        tuple(float(v) for v in values[i]),
        {head: (i + offset) % 3 for offset, head in enumerate(HEADS)},
        (origin + timedelta(minutes=i + 5)).isoformat(), DATASET_HASH,
        "bot2-feature-row-v3", "bot2-future-market-state-v3", row_id=f"caller-fake-{i}")
        for i in range(count)]


def partition_data(x, y, partition, keys, *, preprocessing_sha="0" * 64,
                   feature_version="bot2-feature-row-v3", target_version="bot2-future-market-state-v3",
                   dataset_hash=DATASET_HASH, market="ES", horizon_minutes=5):
    return PartitionData(x, y, partition, keys, feature_version, target_version, market, horizon_minutes,
                         dataset_hash, preprocessing_sha)


def test_causal_padding_dilation_final_t_and_receptive_field():
    x = np.arange(1, 9, dtype=np.float32).reshape(1, 8, 1)
    out, _ = _conv_forward(x, np.ones((3, 1, 1), np.float32), np.zeros(1, np.float32), 2)
    np.testing.assert_array_equal(out[0, :, 0], [1, 2, 4, 6, 9, 12, 15, 18])
    assert DILATIONS == (1, 2, 4)
    a = model(2)
    assert a.parameter_count == expected_parameter_count(24) == 7417
    assert a.receptive_field == 15
    values = np.random.default_rng(8).normal(size=(2, 8, 24)).astype(np.float32)
    final = a.predict_logits(values)
    temporal = a.temporal_logits(values)
    for head in HEADS:
        np.testing.assert_array_equal(final[head], temporal[head][:, -1, :])


def test_future_mutation_does_not_change_any_prior_timestep():
    a = model(2)
    x = np.random.default_rng(8).normal(size=(2, 8, 24)).astype(np.float32)
    changed = x.copy(); changed[:, 6:, :] += 1000
    before, after = a.temporal_logits(x), a.temporal_logits(changed)
    for head in HEADS:
        np.testing.assert_array_equal(before[head][:, :6], after[head][:, :6])
        np.testing.assert_allclose(a.predict_probabilities(x)[head].sum(1), 1.0, atol=2e-7)


def test_fixed_dimension_ablation_is_bound_through_split_and_fit():
    train_rows = observations("2025-06-02", "ESM5", 45, seed=1101)
    valid_rows = observations("2026-01-02", "ESH6", 45, seed=1102)
    scaler = TrainingOnlyStandardizer().fit_observations(train_rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    ablation_id = "MINUS_VWAP"
    split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
        partition_rows={"TRAIN": train_rows,
                        "VALIDATION_AND_CALIBRATION": valid_rows},
        preprocessor=scaler, ablation_id=ablation_id)
    contract = create_ablation_contract(VERIFIED, ablation_id)
    assert split.ablation_contract == contract
    assert split.train.x.shape[1:] == (8, 24)
    assert split.validation.x.shape[1:] == (8, 24)
    masked = [i for i, enabled in enumerate(contract["feature_mask"]) if not enabled]
    active = [i for i, enabled in enumerate(contract["feature_mask"]) if enabled]
    assert masked
    assert np.count_nonzero(split.train.x[:, :, masked]) == 0
    assert np.count_nonzero(split.validation.x[:, :, masked]) == 0
    raw_first = np.asarray([[row.features for row in train_rows[0:8]]], dtype=np.float64)
    expected_standardized = scaler.transform(raw_first)
    np.testing.assert_array_equal(split.train.x[0][:, active], expected_standardized[0][:, active])
    validate_authorized_split(split, VERIFIED)
    network = CausalTemporalConv(VERIFIED, seed=1, ablation_id=ablation_id)
    network.fit(split)
    assert network.parameter_count == expected_parameter_count(24)
    with pytest.raises(ValueError, match="MODEL_ABLATION_SPLIT_MISMATCH"):
        CausalTemporalConv(VERIFIED, seed=1, ablation_id="ALL").fit(split)
    tampered = replace(split, ablation_contract=create_ablation_contract(VERIFIED, "ALL"))
    with pytest.raises(ValueError, match="PREPARED_PARTITION_ABLATION_MISMATCH"):
        validate_authorized_split(tampered, VERIFIED)


def test_machine_readable_ablation_contract_matches_frozen_manifest():
    contract_path = ROOT / "config" / "bot2_phase5c_v3_ablation_contract.json"
    contract_file = json.loads(contract_path.read_text(encoding="utf-8"))
    features = VERIFIED.data["feature_specification"]["features"]
    assert contract_file["source_manifest_sha256"] == VERIFIED.sha256
    assert contract_file["canonical_feature_order"] == features
    expected_membership = {
        name: [item["id"] for item in VERIFIED.data["feature_ablations"]
               if name in item["excluded_features"]]
        for name in features
    }
    assert contract_file["feature_family_membership"] == expected_membership
    assert contract_file["input_channels"] == len(features) == 24
    assert set(contract_file["ablations"]) == {
        item["id"] for item in VERIFIED.data["feature_ablations"]}
    for ablation_id, serialized in contract_file["ablations"].items():
        generated = create_ablation_contract(VERIFIED, ablation_id)
        assert serialized["feature_mask"] == generated["feature_mask"]
        assert generated["feature_family_membership"] == expected_membership
        assert serialized["active_features"] == generated["active_features"]
        assert serialized["ablated_features"] == generated["ablated_features"]
        assert len(serialized["feature_mask"]) == 24


def test_training_is_deterministic_and_enforces_partition_identity():
    train_rows = observations("2025-06-02", "ESM5", 45, seed=21)
    valid_rows = observations("2026-01-02", "ESH6", 45, seed=22)
    scaler = TrainingOnlyStandardizer().fit_observations(train_rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
        partition_rows={"TRAIN": train_rows,
                        "VALIDATION_AND_CALIBRATION": valid_rows}, preprocessor=scaler)
    a, b = model(1), model(1)
    initial = {k: v.copy() for k, v in a.params.items()}
    a.fit(split); b.fit(split)
    assert any(not np.array_equal(initial[k], a.params[k]) for k in initial)
    for key in a.params: np.testing.assert_array_equal(a.params[key], b.params[key])
    assert a.training_partition_fingerprint_ == split.partition_fingerprints["TRAIN"]
    assert a.validation_partition_fingerprint_ == split.partition_fingerprints["VALIDATION_AND_CALIBRATION"]
    with pytest.raises(ValueError, match="AUTHORIZED_SPLIT_OBJECT_REQUIRED"):
        a.fit(split.train, split.validation)
    validate_authorized_split(split, VERIFIED)
    # Early validation rows are sequence context, never calibration examples.
    assert all(datetime.fromisoformat(start) >= datetime.fromisoformat("2026-01-02T15:00:00+00:00")
               for start, _ in split.validation.sequence_label_intervals)
    forged = replace(split, validation=replace(split.validation,
        sequence_label_intervals=(("2026-01-02T14:30:00+00:00", "2026-01-02T14:35:00+00:00"),)
        + split.validation.sequence_label_intervals[1:]))
    with pytest.raises(ValueError, match="OBSERVATION_INSIDE_EMBARGO"):
        model(1).fit(forged)


def test_data_derived_identity_rejects_fake_ids_and_cross_partition_duplicate():
    train_rows = observations("2025-06-02", "ESM5", 45)
    valid_rows = observations("2026-01-02", "ESH6", 45)
    scaler = TrainingOnlyStandardizer().fit_observations(train_rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    duplicate = replace(train_rows[0], row_id="a-different-caller-id")
    with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION_CROSSES_PARTITION"):
        build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
            partition_rows={"TRAIN": train_rows,
                            "VALIDATION_AND_CALIBRATION": valid_rows,
                            "OOS_TEST": [duplicate]}, preprocessor=scaler)


def test_partition_fingerprint_changes_on_mutation_and_fit_enforces_purge_edges():
    train_rows = observations("2025-12-31", "ESZ5", 90, seed=91,
                              start_time="22:30:00")
    valid_rows = observations("2026-01-01", "ESH6", 45, seed=92,
                              start_time="00:00:00")
    scaler = TrainingOnlyStandardizer().fit_observations(train_rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    original_fp = feature_partition_fingerprint(train_rows, partition="TRAIN")
    changed = [replace(train_rows[0], features=(train_rows[0].features[0] + 1.0,)
                       + train_rows[0].features[1:]), *train_rows[1:]]
    assert feature_partition_fingerprint(changed, partition="TRAIN") != original_fp
    split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
        partition_rows={"TRAIN": train_rows,
                        "VALIDATION_AND_CALIBRATION": valid_rows}, preprocessor=scaler)
    cutoff = datetime.fromisoformat("2026-01-01T00:00:00+00:00") - timedelta(minutes=30)
    assert all(datetime.fromisoformat(end) < cutoff
               for _, end in split.train.sequence_label_intervals)
    # The latest eligible label ends one minute before cutoff; labels touching
    # or crossing cutoff are not retained as training terminal rows.
    assert datetime.fromisoformat(max(end for _, end in split.train.sequence_label_intervals)) == cutoff - timedelta(minutes=1)
    model(1).fit(split)
    unsafe_intervals = list(split.train.sequence_label_intervals)
    unsafe_intervals[-1] = (unsafe_intervals[-1][0], cutoff.isoformat())
    unsafe_train = replace(split.train, sequence_label_intervals=tuple(unsafe_intervals))
    unsafe_split = replace(split, train=unsafe_train)
    with pytest.raises(ValueError, match="LABEL_INTERVAL_VIOLATES_PURGE"):
        model(1).fit(unsafe_split)

    tampered_rows = dict(split.canonical_rows)
    tampered_rows["TRAIN"] = tuple(changed)
    with pytest.raises(ValueError, match="PARTITION_FINGERPRINT_MISMATCH"):
        validate_authorized_split(replace(split, canonical_rows=tampered_rows), VERIFIED)


def test_validation_only_calibration_abstention_and_result_lineage_contract():
    train_rows = observations("2025-06-02", "ESM5", 45, seed=73)
    valid_rows = observations("2026-01-02", "ESH6", 45, seed=74)
    scaler = TrainingOnlyStandardizer().fit_observations(train_rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
        partition_rows={"TRAIN": train_rows,
                        "VALIDATION_AND_CALIBRATION": valid_rows}, preprocessor=scaler)
    synthetic_model_artifact = {"artifact_sha256": "a" * 64,
        "manifest_sha256": VERIFIED.sha256, "random_seed": 1, "code_commit": FULL_COMMIT,
        "preprocessing_sha256": split.preprocessing_sha256}
    rng = np.random.default_rng(991)
    logits = rng.normal(size=(len(split.validation.x), 3))
    calibration = fit_temperature_calibrator(logits, split=split,
        verified_manifest=VERIFIED, model_artifact=synthetic_model_artifact, head="direction")
    verify_calibration_artifact(calibration, split=split, verified_manifest=VERIFIED,
        model_artifact=synthetic_model_artifact)
    with pytest.raises(ValueError, match="OOS_CALIBRATION_OR_THRESHOLD_FIT_FORBIDDEN"):
        fit_temperature_calibrator(logits, split=split, verified_manifest=VERIFIED,
            model_artifact=synthetic_model_artifact, head="direction", fit_partition="OOS_TEST")
    wrong_model = {**synthetic_model_artifact, "artifact_sha256": "b" * 64}
    with pytest.raises(ValueError, match="CALIBRATION_LINEAGE_MISMATCH"):
        verify_calibration_artifact(calibration, split=split, verified_manifest=VERIFIED,
            model_artifact=wrong_model)
    with pytest.raises(ValueError, match="CALIBRATION_LINEAGE_MISMATCH"):
        verify_calibration_artifact(calibration, split=split, verified_manifest=VERIFIED,
            model_artifact={**synthetic_model_artifact, "preprocessing_sha256": "f" * 64})
    wrong_partition_fingerprints = dict(split.partition_fingerprints)
    wrong_partition_fingerprints["VALIDATION_AND_CALIBRATION"] = "f" * 64
    with pytest.raises(ValueError):
        verify_calibration_artifact(calibration, split=replace(split,
            partition_fingerprints=wrong_partition_fingerprints),
            verified_manifest=VERIFIED, model_artifact=synthetic_model_artifact)
    wrong_head = copy.deepcopy(calibration)
    wrong_head["head"] = "volatility"
    wrong_head["calibration_sha256"] = canonical_hash(wrong_head,
        excluded_key="calibration_sha256")
    with pytest.raises(ValueError, match="CALIBRATION_PARAMETERS_INVALID"):
        verify_calibration_artifact(wrong_head, split=split, verified_manifest=VERIFIED,
            model_artifact=synthetic_model_artifact, expected_head="direction")
    corrupt_calibrator = copy.deepcopy(calibration)
    corrupt_calibrator["temperature"] = float(corrupt_calibrator["temperature"]) + 0.01
    with pytest.raises(ValueError, match="CALIBRATION_CONTENT_HASH_MISMATCH"):
        verify_calibration_artifact(corrupt_calibrator, split=split, verified_manifest=VERIFIED,
            model_artifact=synthetic_model_artifact)
    altered_data = VERIFIED.data
    altered_data["calibration"]["deterministic_grid"]["step"] = 0.02
    altered_manifest = VerifiedManifest(altered_data, VERIFIED.pin, VERIFIED.sha256,
        VERIFIED.pin_sha256, VERIFIED.anchor_path, _token=_VERIFIED_TOKEN)
    with pytest.raises(ValueError, match="EXTERNALLY_ANCHORED_MANIFEST_REQUIRED"):
        verify_calibration_artifact(calibration, split=split,
            verified_manifest=altered_manifest, model_artifact=synthetic_model_artifact)
    wrong_manifest_data = VERIFIED.data
    wrong_manifest_data["experiment_id"] = "tampered-experiment"
    wrong_manifest = VerifiedManifest(wrong_manifest_data, VERIFIED.pin, VERIFIED.sha256,
        VERIFIED.pin_sha256, VERIFIED.anchor_path, _token=_VERIFIED_TOKEN)
    with pytest.raises(ValueError, match="EXTERNALLY_ANCHORED_MANIFEST_REQUIRED"):
        verify_calibration_artifact(calibration, split=split,
            verified_manifest=wrong_manifest, model_artifact=synthetic_model_artifact)

    tied_probabilities = np.full((len(split.validation.x), 3), 1 / 3)
    abstention = select_abstention_threshold(tied_probabilities, split=split,
        verified_manifest=VERIFIED, model_artifact=synthetic_model_artifact,
        head="direction", target_coverage=0.75)
    verify_abstention_artifact(abstention, split=split, verified_manifest=VERIFIED,
        model_artifact=synthetic_model_artifact)
    assert abstention["realized_coverage"] == 1.0  # the full entropy tie group is retained
    with pytest.raises(ValueError, match="OOS_CALIBRATION_OR_THRESHOLD_FIT_FORBIDDEN"):
        select_abstention_threshold(tied_probabilities, split=split,
            verified_manifest=VERIFIED, model_artifact=synthetic_model_artifact,
            head="direction", target_coverage=0.75, fit_partition="OOS_TEST")

    result_contract = create_result_lineage_contract(verified_manifest=VERIFIED,
        model_artifact=synthetic_model_artifact, preprocessing_sha256=scaler.sha256,
        calibration_sha256=calibration["calibration_sha256"], market="ES",
        horizon_minutes=5, head="direction", walk_forward_window="WF4")
    validate_result_lineage_contract(result_contract, verified_manifest=VERIFIED,
        model_artifact=synthetic_model_artifact)
    assert result_contract["result_sha256"] is None
    assert result_contract["evaluation_authorized"] is False
    assert result_contract["oos_scoring_performed"] is False
    with pytest.raises(ValueError, match="RESULT_LINEAGE_MISMATCH"):
        validate_result_lineage_contract({**result_contract, "model_artifact_sha256": "f" * 64},
            verified_manifest=VERIFIED, model_artifact=synthetic_model_artifact)


def test_frozen_executable_controls_inputs_shuffle_ablation_calibration_results():
    train_rows = observations("2025-06-02", "ESM5", 45, seed=801)
    valid_rows = observations("2026-01-02", "ESH6", 45, seed=802)
    scaler = TrainingOnlyStandardizer().fit_observations(train_rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
        partition_rows={"TRAIN": train_rows,
                        "VALIDATION_AND_CALIBRATION": valid_rows}, preprocessor=scaler)

    shuffled = execute_shuffled_label_control(split, verified_manifest=VERIFIED,
        candidate_id="A1_NUMPY_MULTIHEAD_MLP", candidate_seed=1, run_index=1)
    verify_shuffled_label_control(shuffled, split=split, verified_manifest=VERIFIED)
    replay = execute_shuffled_label_control(split, verified_manifest=VERIFIED,
        candidate_id="A1_NUMPY_MULTIHEAD_MLP", candidate_seed=1, run_index=1)
    assert dict(shuffled.artifact) == dict(replay.artifact)
    for head in HEADS:
        assert sorted(row.targets[head] for row in train_rows) == sorted(
            target[head] for target in shuffled.train_targets_by_observation.values())
    assert shuffled.artifact["evaluation_labels_changed"] is False
    assert shuffled.artifact["predictions_generated"] is False
    with pytest.raises(ValueError, match="SHUFFLE_RUN_NOT_IN_FROZEN_POLICY"):
        execute_shuffled_label_control(split, verified_manifest=VERIFIED,
            candidate_id="A1_NUMPY_MULTIHEAD_MLP", candidate_seed=1, run_index=4)

    manifest = VERIFIED.data
    approved_ablations = [item["id"] for item in manifest["feature_ablations"]]
    for ablation_id in approved_ablations:
        contract = create_ablation_contract(VERIFIED, ablation_id)
        verify_ablation_contract(contract, VERIFIED)
        execution = execute_ablation_control(train_rows, verified_manifest=VERIFIED,
            preprocessor=scaler, model_id="A1_NUMPY_MULTIHEAD_MLP", seed=1, ablation_id=ablation_id)
        verify_ablation_execution(execution, rows=train_rows, preprocessor=scaler,
            verified_manifest=VERIFIED)
        assert execution.artifact["metrics_generated"] is False
        assert len(execution.transformed_rows[0]["features"]) == 24
        assert execution.artifact["input_channels"] == 24
        assert execution.transformed_rows[0]["feature_mask"] == contract["feature_mask"]
        masked_indexes = [i for i, value in enumerate(contract["feature_mask"]) if value == 0]
        assert all(execution.transformed_rows[0]["features"][i] == 0.0 for i in masked_indexes)
        model_contract = create_model_input_contract(VERIFIED,
            model_id="A2_LEARNED_CAUSAL_TCN", seed=1, ablation_id=ablation_id)
        a1_contract = create_model_input_contract(VERIFIED,
            model_id="A1_NUMPY_MULTIHEAD_MLP", seed=1, ablation_id=ablation_id)
        assert model_contract["sequence_shape"] == [8, 24]
        assert model_contract["input_channels"] == 24
        assert model_contract["input_feature_mask"] == contract["feature_mask"]
        assert a1_contract["sequence_shape"] == [8, 24]
        assert a1_contract["input_feature_mask"] == model_contract["input_feature_mask"]
        assert a1_contract["ablated_features"] == model_contract["ablated_features"]
        a2 = CausalTemporalConv(VERIFIED, seed=1, ablation_id=ablation_id)
        assert a2.parameter_count == expected_parameter_count(24) == 7417
        assert a2.verified_manifest.data["architectures"]["A2_LEARNED_CAUSAL_TCN"]["architecture_version"] == "bot2-phase5c-a2-causal-tcn-v3"
        assert a2.params["conv1_w"].shape == (3, 24, 32)
        assert a2.params["conv2_w"].shape == (3, 32, 32)
        assert a2.params["conv3_w"].shape == (3, 32, 16)
        assert all(a2.params[f"{head}_w"].shape == (16, 3) for head in HEADS)
        variant_split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
            partition_rows={"TRAIN": train_rows,
                            "VALIDATION_AND_CALIBRATION": valid_rows},
            preprocessor=scaler, ablation_id=ablation_id)
        a2.fit(variant_split)
        assert a2.training_partition_fingerprint_ == variant_split.partition_fingerprints["TRAIN"]
        assert a2.validation_partition_fingerprint_ == variant_split.partition_fingerprints["VALIDATION_AND_CALIBRATION"]
    with pytest.raises(ValueError, match="ABLATION_INPUT_WIDTH_MISMATCH"):
        apply_ablation_mask(np.zeros((2, 23), dtype=np.float32),
            contract=create_ablation_contract(VERIFIED, "MINUS_VWAP"),
            verified_manifest=VERIFIED,
            feature_order=VERIFIED.data["feature_specification"]["features"])
    with pytest.raises(ValueError, match="ABLATION_SOURCE_FEATURE_ORDER_MISMATCH"):
        apply_ablation_mask(np.zeros((2, 24), dtype=np.float32),
            contract=create_ablation_contract(VERIFIED, "MINUS_VWAP"),
            verified_manifest=VERIFIED,
            feature_order=list(reversed(VERIFIED.data["feature_specification"]["features"])))
    invalid = dict(create_ablation_contract(VERIFIED, "ALL"))
    invalid["feature_mask"] = invalid["feature_mask"][:-1]
    with pytest.raises(ValueError, match="ABLATION_MANIFEST_BINDING_MISMATCH"):
        verify_ablation_contract(invalid, VERIFIED)
    with pytest.raises(ValueError, match="ABLATION_NOT_IN_MANIFEST"):
        create_ablation_contract(VERIFIED, "MINUS_UNAPPROVED_FAMILY")

    decision_time = seq_keys(1)[0][-1][2]
    for model_id, ablation in (("A0_TRAIN_MAJORITY", "ALL"),
                              ("A1_NUMPY_MULTIHEAD_MLP", "ALL"),
                              ("A2_LEARNED_CAUSAL_TCN", "ALL")):
        contract = create_model_input_contract(VERIFIED, model_id=model_id,
            seed=1, ablation_id=ablation)
        if model_id.startswith("A0"):
            actual_features, shape = [], []
        else:
            actual_features = contract["features"]
            shape = contract["sequence_shape"]
        validate_model_input_contract(contract, VERIFIED,
            actual_features=actual_features, actual_sequence_shape=shape,
            actual_feature_mask=contract["input_feature_mask"],
            latest_input_timestamp_utc=decision_time,
            decision_timestamp_utc=decision_time)
        with pytest.raises(ValueError, match="UNAUTHORIZED_MODEL_FEATURE_INPUT"):
            validate_model_input_contract(contract, VERIFIED,
                actual_features=[*actual_features, "future_feature"],
                actual_sequence_shape=shape,
                actual_feature_mask=contract["input_feature_mask"],
                latest_input_timestamp_utc=decision_time,
                decision_timestamp_utc=decision_time)
        if model_id in {"A1_NUMPY_MULTIHEAD_MLP", "A2_LEARNED_CAUSAL_TCN"}:
            wrong_mask = list(contract["input_feature_mask"])
            wrong_mask[0] = 1 - wrong_mask[0]
            with pytest.raises(ValueError, match="MODEL_ABLATION_MASK_MISMATCH"):
                validate_model_input_contract(contract, VERIFIED,
                    actual_features=actual_features, actual_sequence_shape=shape,
                    actual_feature_mask=wrong_mask,
                    latest_input_timestamp_utc=decision_time,
                    decision_timestamp_utc=decision_time)
    a0 = create_model_input_contract(VERIFIED, model_id="A0_PREVIOUS_LABEL_PERSISTENCE", seed=1)
    with pytest.raises(ValueError, match="A0_PRIOR_LABEL_INPUT_REQUIRED"):
        validate_model_input_contract(a0, VERIFIED, actual_features=[], actual_sequence_shape=[],
            actual_feature_mask=[],
            latest_input_timestamp_utc=decision_time, decision_timestamp_utc=decision_time)
    validate_model_input_contract(a0, VERIFIED, actual_features=[], actual_sequence_shape=[],
        actual_feature_mask=[],
        latest_input_timestamp_utc=decision_time, decision_timestamp_utc=decision_time,
        contains_target_labels=True, label_information_end_utc=decision_time)
    with pytest.raises(ValueError, match="FUTURE_LABEL_INFORMATION_REACHES_MODEL"):
        validate_model_input_contract(a0, VERIFIED, actual_features=[], actual_sequence_shape=[],
            actual_feature_mask=[],
            latest_input_timestamp_utc=decision_time, decision_timestamp_utc=decision_time,
            contains_target_labels=True,
            label_information_end_utc=(datetime.fromisoformat(decision_time) + timedelta(minutes=1)).isoformat())

    neural = model(1)
    neural.preprocessing_sha256_ = split.preprocessing_sha256
    neural.training_partition_fingerprint_ = split.partition_fingerprints["TRAIN"]
    neural.validation_partition_fingerprint_ = split.partition_fingerprints["VALIDATION_AND_CALIBRATION"]
    weights = neural.state()
    model_artifact = {
        "schema_version": "synthetic-engineering-model-artifact-v1",
        "artifact_sha256": None,
        "manifest_sha256": VERIFIED.sha256,
        "dataset_manifest_sha256": split.dataset_manifest_sha256,
        "market": "ES", "horizon_minutes": 5,
        "random_seed": 1, "code_commit": FULL_COMMIT,
        "preprocessing_sha256": split.preprocessing_sha256,
        "training_partition_fingerprint": split.partition_fingerprints["TRAIN"],
        "validation_partition_fingerprint": split.partition_fingerprints["VALIDATION_AND_CALIBRATION"],
        "weights": weights, "weights_sha256": canonical_hash(weights),
        "trading_authority": False, "oos_scoring_performed": False,
    }
    model_artifact["artifact_sha256"] = canonical_hash(model_artifact, excluded_key="artifact_sha256")
    calibration = fit_model_temperature_calibrator(neural, split=split,
        verified_manifest=VERIFIED, model_artifact=model_artifact, head="direction")
    verify_calibration_artifact(calibration, split=split, verified_manifest=VERIFIED,
        model_artifact=model_artifact, expected_head="direction")
    with pytest.raises(ValueError, match="CALIBRATION_LINEAGE_MISMATCH"):
        verify_calibration_artifact(calibration, split=split, verified_manifest=VERIFIED,
            model_artifact={**model_artifact, "preprocessing_sha256": "f" * 64})

    import hashlib as _hashlib
    result = create_engineering_result_artifact(verified_manifest=VERIFIED, split=split,
        model_artifact=model_artifact, head="direction",
        fixture_sha256=_hashlib.sha256(b"phase5c-v synthetic fixture").hexdigest(),
        metrics_configuration=VERIFIED.data["metrics"],
        calibration_artifact=calibration,
        ablation_contract=create_ablation_contract(VERIFIED, "ALL"),
        shuffled_control_artifact=shuffled.artifact)
    verify_engineering_result_artifact(result, verified_manifest=VERIFIED, split=split,
        model_artifact=model_artifact, calibration_artifact=calibration,
        ablation_contract=create_ablation_contract(VERIFIED, "ALL"),
        shuffled_control_artifact=shuffled.artifact)
    corrupted = copy.deepcopy(result)
    corrupted["result_content"]["fixture_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="RESULT_ARTIFACT_CONTENT_CORRUPT_OR_UNAUTHORIZED"):
        verify_engineering_result_artifact(corrupted, verified_manifest=VERIFIED, split=split,
            model_artifact=model_artifact, calibration_artifact=calibration,
            ablation_contract=create_ablation_contract(VERIFIED, "ALL"),
            shuffled_control_artifact=shuffled.artifact)


def test_exact_commit_and_clean_worktree_binding(tmp_path, monkeypatch):
    repo = tmp_path / "candidate"
    repo.mkdir()
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
            capture_output=True, text=True, timeout=15).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "phase5c-test@example.invalid")
    git("config", "user.name", "Phase5C engineering test")
    tracked = repo / "sentinel.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    git("add", "sentinel.txt")
    git("commit", "-qm", "synthetic candidate")
    candidate = git("rev-parse", "HEAD")
    monkeypatch.setattr("bot2.phase5c_v3.manifest.V3_PROTOCOL_ANCHOR_COMMIT", candidate)
    result = verify_git_binding(repo, expected_commit=candidate)
    assert result["exact_commit_match"] is True and result["clean_worktree"] is True
    with pytest.raises(ValueError, match="REVIEWED_COMMIT_MISMATCH"):
        verify_git_binding(repo, expected_commit="0" * 40)
    tracked.write_text("modified\n", encoding="utf-8")
    with pytest.raises(ValueError, match="IMPLEMENTATION_WORKTREE_NOT_CLEAN"):
        verify_git_binding(repo, expected_commit=candidate)
    tracked.write_text("clean\n", encoding="utf-8")
    assert verify_git_binding(repo, expected_commit=candidate)["clean_worktree"] is True


def test_partition_identity_rejects_gap_session_contract_and_cross_split_duplicates():
    x = np.zeros((1, 8, 24), dtype=np.float32)
    good = seq_keys(1)[0]
    data = partition_data(x, targets(1), "TRAIN", (good,))
    assert len(validate_sequence_identities(data, sequence_length=8)) == 8
    gapped = list(good); gapped[4] = (gapped[4][0], gapped[4][1],
        (datetime.fromisoformat(gapped[3][2]) + timedelta(minutes=2)).isoformat())
    with pytest.raises(ValueError, match="SEQUENCE_CADENCE_GAP_OR_REGRESSION"):
        validate_sequence_identities(partition_data(x, targets(1), "TRAIN", (tuple(gapped),)), sequence_length=8)
    boundary = list(good); boundary[-1] = ("ESZ6", boundary[-1][1], boundary[-1][2])
    with pytest.raises(ValueError, match="SEQUENCE_CONTRACT_BOUNDARY_CROSSING"):
        validate_sequence_identities(partition_data(x, targets(1), "TRAIN", (tuple(boundary),)), sequence_length=8)
    boundary = list(good); boundary[-1] = (boundary[-1][0], "RTH-OTHER", boundary[-1][2])
    with pytest.raises(ValueError, match="SEQUENCE_SESSION_BOUNDARY_CROSSING"):
        validate_sequence_identities(partition_data(x, targets(1), "TRAIN", (tuple(boundary),)), sequence_length=8)

    def part(label, keys):
        return partition_data(np.zeros((len(keys), 8, 24), np.float32), targets(len(keys)), label, tuple(keys))
    # Exercise all explicitly protected partition pairs independently.
    for left, right in (("TRAIN", "VALIDATION"), ("TRAIN", "CALIBRATION"),
                        ("TRAIN", "OOS_TEST"), ("VALIDATION", "OOS_TEST")):
        with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION_CROSSES_PARTITION"):
            validate_partition_disjointness({left: part(left, [good]), right: part(right, [good])})


def test_preprocessing_is_train_only_and_verifies_unique_canonical_rows():
    rows = observations("2025-06-02", "ESM5", 2)
    rows = [replace(rows[0], features=(1.0,) * 24), replace(rows[1], features=(3.0,) * 24)]
    scaler = TrainingOnlyStandardizer().fit_observations(rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    assert scaler.state()["mean"] == [2.0] * 24
    assert scaler.transform(np.stack([[r.features for r in rows], [r.features for r in rows]])).shape == (2, 2, 24)
    with pytest.raises(ValueError, match="PREPROCESSING_FIT_NOT_TRAIN"):
        TrainingOnlyStandardizer().fit(
            np.zeros((2, 24)), partition="OOS_TEST", row_ids=[], market="ES",
            verified_manifest=VERIFIED)
    with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION_IDENTITY"):
        TrainingOnlyStandardizer().fit_observations([rows[0], rows[0]], market="ES",
            verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    with pytest.raises(ValueError, match="DUPLICATE_IDENTITY_CONFLICTING_VALUES"):
        TrainingOnlyStandardizer().fit_observations(
            [rows[0], replace(rows[0], features=(9.0,) * 24)], market="ES",
            verified_manifest=VERIFIED, code_commit=FULL_COMMIT)


def test_numerical_gradients_cover_all_convolution_blocks_shared_and_head():
    a = model(2)
    x = (np.random.default_rng(109).normal(size=(2, 8, 24)) * 0.07 + 0.03).astype(np.float32)
    y = targets(2, 1)
    _, analytic = a._loss_and_gradients(x, y)
    probes = (("conv1_w", (1, 2, 3)), ("conv2_w", (1, 2, 3)),
              ("conv3_w", (1, 2, 3)), ("shared_w", (2, 3)),
              ("direction_w", (4, 1)))
    eps, abs_tol, rel_tol = 1e-3, 2e-3, 3e-2
    max_abs = max_rel = 0.0
    for name, index in probes:
        param = a.params[name]
        original = float(param[index])
        param[index] = np.float32(original + eps)
        plus = a._loss_and_gradients(x, y)[0]
        param[index] = np.float32(original - eps)
        minus = a._loss_and_gradients(x, y)[0]
        param[index] = np.float32(original)
        numeric = (plus - minus) / (2 * eps)
        observed = float(analytic[name][index])
        absolute = abs(numeric - observed)
        relative = absolute / max(abs(numeric), abs(observed), 1e-7)
        max_abs, max_rel = max(max_abs, absolute), max(max_rel, relative)
        assert absolute <= abs_tol or relative <= rel_tol, f"gradient mismatch for {name}{index}: {numeric} vs {observed}"
    assert max_abs < abs_tol
    assert max_rel < rel_tol


def test_manifest_external_pin_and_protected_configuration_authority(tmp_path):
    loaded, digest = load_and_verify_manifest(MANIFEST_PATH, external_anchor_path=TEST_ANCHOR_PATH)
    assert digest == VERIFIED.sha256 == loaded["manifest_sha256"]
    mutable_copy = VERIFIED.data
    mutable_copy["a2_training"]["learning_rate"] = 7
    assert VERIFIED.data["a2_training"]["learning_rate"] == 0.001
    assert all(passed for _, passed, _ in _frozen_control_checks(loaded))
    overrides = {"sequence_length": loaded["feature_specification"]["sequence_length"],
                 "horizons_minutes": loaded["target_specification"]["horizons_minutes"]}
    require_manifest_overrides_match(VERIFIED, overrides)
    for key, wrong in (("sequence_length", 9), ("horizons_minutes", [1]),
                       ("feature_version", "mutated"), ("target_version", "mutated"),
                       ("architecture", {}), ("training", {}), ("random_seeds", [99]),
                       ("partitions", {}), ("walk_forward_windows", []), ("purge_embargo", {}),
                       ("calibration", {}), ("abstention", {}), ("ablations", []), ("metrics", {})):
        with pytest.raises(ValueError, match="PROTECTED_OVERRIDE_MISMATCH"):
            require_manifest_overrides_match(VERIFIED, {key: wrong})
    with pytest.raises(ValueError, match="UNRECOGNIZED_PROTECTED_OVERRIDE"):
        require_manifest_overrides_match(VERIFIED, {"partition_tag": "OOS"})
    with pytest.raises(ValueError, match="EXTERNAL_TRUST_ANCHOR_REQUIRED"):
        load_and_verify_manifest(MANIFEST_PATH)
    with pytest.raises(ValueError, match="TRUST_ANCHOR_MUST_BE_OUTSIDE_REPOSITORY"):
        load_and_verify_manifest(MANIFEST_PATH,
            external_anchor_path=ROOT / "docs" / "phase5c_v3_external_anchor.txt")
    with pytest.raises(ValueError, match="EXTERNALLY_ANCHORED_MANIFEST_REQUIRED"):
        CausalTemporalConv(object(), seed=1)
    with pytest.raises(ValueError, match="SEED_NOT_AUTHORIZED_BY_MANIFEST"):
        CausalTemporalConv(VERIFIED, seed=99)
    altered = copy.deepcopy(loaded)
    altered["a2_training"]["learning_rate"] = 0.5
    altered_path = tmp_path / MANIFEST_PATH.name
    altered_path.write_text(json.dumps(altered), encoding="utf-8")
    (tmp_path / "bot2_phase5c_v3_manifest.lock.json").write_bytes(
        (MANIFEST_PATH.parent / "bot2_phase5c_v3_manifest.lock.json").read_bytes())
    with pytest.raises(ValueError, match="MANIFEST_HASH_MISMATCH"):
        load_and_verify_manifest(altered_path, external_anchor_path=TEST_ANCHOR_PATH)


def test_artifact_manifest_binding_provenance_atomicity_and_concurrency(tmp_path):
    a = model(1)
    train_rows = observations("2025-06-02", "ESM5", 45, seed=88)
    valid_rows = observations("2026-01-02", "ESH6", 45, seed=89)
    scaler = TrainingOnlyStandardizer().fit_observations(train_rows, market="ES",
        verified_manifest=VERIFIED, code_commit=FULL_COMMIT)
    split = build_authorized_split(VERIFIED, market="ES", horizon_minutes=5,
        partition_rows={"TRAIN": train_rows,
                        "VALIDATION_AND_CALIBRATION": valid_rows}, preprocessor=scaler)
    a.fit(split)
    prep = scaler.state()
    windows = VERIFIED.data["chronological_partitions_inclusive"]
    identity = {"experiment_id": VERIFIED.data["experiment_id"],
        "protocol_version": VERIFIED.data["schema_version"], "manifest_sha256": VERIFIED.sha256,
        "dataset_manifest_sha256": DATASET_HASH, "feature_version": "bot2-feature-row-v3",
        "feature_registry_sha256": VERIFIED.data["feature_specification"]["registry_sha256"],
        "target_version": "bot2-future-market-state-v3",
        "target_spec_sha256": VERIFIED.data["target_specification"]["spec_sha256"],
        "architecture_version": ARCHITECTURE_VERSION, "random_seed": 1,
        "market": "ES", "horizon_minutes": 5,
        "sequence_spec": {"length": 8, "cadence_seconds": 60},
        "partition_identity": windows,
        "training_window": {"partition": "TRAIN", "window": windows["TRAIN"]},
        "validation_window": {"partition": "VALIDATION_AND_CALIBRATION", "window": windows["VALIDATION_AND_CALIBRATION"]},
        "raw_archive_sha256": VERIFIED.pin["raw_archive_tree_sha256"]}
    lineage = {**identity, "model_id": "fixture",
        "dataset_sha256": DATASET_HASH,
        "preprocessing": prep, "code_commit": FULL_COMMIT,
        "dependency_versions": {"numpy": np.__version__}}
    lineage["training_partition_fingerprint"] = split.partition_fingerprints["TRAIN"]
    lineage["validation_partition_fingerprint"] = split.partition_fingerprints["VALIDATION_AND_CALIBRATION"]
    artifact = create_artifact(a, verified_manifest=VERIFIED, lineage=lineage)
    for field, value, reason in (
        ("dataset_sha256", "0" * 64, "DATASET_MANIFEST_BINDING_MISMATCH"),
        ("target_version", "not-pinned", "ARTIFACT_PROVENANCE_MISMATCH:target_version"),
        ("market", "MES", "ARTIFACT_MARKET_OR_HORIZON_NOT_IN_MANIFEST"),
        ("code_commit", "not-a-commit", "INVALID_CODE_COMMIT"),
    ):
        with pytest.raises(ValueError, match=reason):
            create_artifact(a, verified_manifest=VERIFIED, lineage={**lineage, field: value})
    path = tmp_path / "model.json"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(save_artifact, path, artifact) for _ in range(2)]
        results = []
        for future in futures:
            try: results.append(("ok", future.result()))
            except FileExistsError as exc: results.append(("exists", str(exc)))
    assert sorted(result[0] for result in results) == ["exists", "ok"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == next(value for status, value in results if status == "ok")
    assert load_artifact(path, verified_manifest=VERIFIED)["manifest_sha256"] == VERIFIED.sha256
    with pytest.raises(FileExistsError, match="IMMUTABLE_ARTIFACT_ALREADY_EXISTS"):
        save_artifact(path, artifact)
    bad = dict(artifact); bad["manifest_sha256"] = "0" * 64
    bad["artifact_sha256"] = "x"
    bad_path = tmp_path / "bad.json"; bad_path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="ARTIFACT_CONTENT_CORRUPT"):
        load_artifact(bad_path, verified_manifest=VERIFIED)
    bad_preprocessing = copy.deepcopy(artifact)
    bad_preprocessing["preprocessing"]["mean"][0] = 999
    bad_preprocessing["artifact_sha256"] = __import__("bot2.phase5c_v3.manifest", fromlist=["canonical_hash"]).canonical_hash(
        bad_preprocessing, excluded_key="artifact_sha256")
    bad_prep_path = tmp_path / "bad-preprocessing.json"
    bad_prep_path.write_text(json.dumps(bad_preprocessing))
    with pytest.raises(ValueError, match="ARTIFACT_PREPROCESSING_CORRUPT"):
        load_artifact(bad_prep_path, verified_manifest=VERIFIED)
    bad_chain = dict(artifact["provenance_chain"]); bad_chain["target_spec_sha256"] = "bad"
    with pytest.raises(ValueError, match="PROVENANCE_HASH_INVALID:target_spec_sha256"):
        verify_provenance_chain(bad_chain, allow_pending_final=True)


def test_archive_audit_hashes_fail_closed_on_payload_mutation(tmp_path):
    repo = tmp_path / "repo"; root = repo / "data/backtests/es_nq_pass_b_archive_3"
    payload = root / "ES/normalized/fixture.jsonl"; payload.parent.mkdir(parents=True)
    payload.write_bytes(b"fixture\n")
    rel = "data/backtests/es_nq_pass_b_archive_3/ES/normalized/fixture.jsonl"
    entry = {"path": rel, "bytes": payload.stat().st_size,
             "sha256": hashlib.sha256(payload.read_bytes()).hexdigest()}
    tree = hashlib.sha256((json.dumps([entry], sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
    report = repo / "outputs/archive_audits/final.json"; report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"state": "FINAL_ES_NQ_ARCHIVE_AUDIT_PASS", "archive_tree_sha256": tree, "artifact_hashes": [entry]}))
    ok, reason, details = _verify_archive_audit_report(report, root, {"archive_tree_sha256": tree})
    assert ok and reason == "ARCHIVE_PAYLOAD_HASHES_VALID" and details["file_count"] == 1
    payload.write_bytes(b"corrupt\n")
    ok, reason, _ = _verify_archive_audit_report(report, root, {"archive_tree_sha256": tree})
    assert not ok and reason == "ARCHIVE_PAYLOAD_HASH_OR_SIZE_MISMATCH"
