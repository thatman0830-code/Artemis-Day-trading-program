"""The protected no-score execution state rejects every model-output API."""
from __future__ import annotations

import numpy as np
import pytest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from bot2.neural.model import MultiHeadMLP
from bot2.phase5c_v3 import calibration, experiment_matrix, experiment_runner
from bot2.phase5c_v3.model import CausalTemporalConv
from bot2.phase5c_v3.no_score_boundary import (
    NoScoreBoundaryViolation,
    no_score_active,
    protected_no_score_boundary,
)
from bot2.phase5c_v3.protected_preflight import (
    _bar_event,
    _apply_walk_forward_purge,
    _validate_oos_sequence_structure,
)
from bot2.phase5c_v3.data_integrity import MarketObservation


def _protected_model() -> CausalTemporalConv:
    # Guards must run before model state or input arrays are examined.
    return object.__new__(CausalTemporalConv)


@pytest.mark.parametrize("operation", [
    lambda: CausalTemporalConv._forward(_protected_model(), None),
    lambda: CausalTemporalConv.temporal_logits(_protected_model(), None),
    lambda: CausalTemporalConv.predict_logits(_protected_model(), None),
    lambda: CausalTemporalConv.predict_probabilities(_protected_model(), None),
    lambda: CausalTemporalConv._loss_and_gradients(_protected_model(), None, None),
    lambda: CausalTemporalConv.fit(_protected_model(), None),
    lambda: CausalTemporalConv.evaluate_loss(_protected_model(), None),
    lambda: MultiHeadMLP._forward(MultiHeadMLP(2), None),
    lambda: MultiHeadMLP.predict(MultiHeadMLP(2), None),
    lambda: MultiHeadMLP.fit(MultiHeadMLP(2), None, None),
    lambda: experiment_runner._softmax(np.zeros((1, 3))),
    lambda: experiment_runner._metrics(np.zeros((1, 3)), np.zeros(1)),
    lambda: experiment_runner._a0_predictions(None),
    lambda: experiment_runner._calibrated_predictions(model_id="", seed=0,
        logits_by_head={}, artifact={}, split=None, verified=None, scaler=None,
        ablation={}),
    lambda: calibration._probabilities(np.zeros((1, 3)), 1.0),
    lambda: calibration.fit_temperature_calibrator(None, split=None,
        verified_manifest=None, model_artifact={}, head="direction"),
    lambda: calibration.select_abstention_threshold(None, split=None,
        verified_manifest=None, model_artifact={}, head="direction", target_coverage=0.5),
    lambda: experiment_matrix.evaluate_complete_matrix({}, verified=None),
])
def test_scoring_and_model_output_apis_fail_closed_inside_no_score_boundary(operation):
    with protected_no_score_boundary():
        assert no_score_active()
        with pytest.raises(NoScoreBoundaryViolation,
                match="PROTECTED_PREFLIGHT_SCORING_OPERATION_BLOCKED"):
            operation()
    assert not no_score_active()


def test_boundary_resets_after_exception():
    with pytest.raises(RuntimeError):
        with protected_no_score_boundary():
            raise RuntimeError("fixture")
    assert not no_score_active()


def test_archive_content_contract_hash_is_not_used_as_experiment_contract_identity():
    bar = SimpleNamespace(instrument_id="ESM5", contract_id="f" * 64,
        close_time=datetime(2025, 6, 2, tzinfo=timezone.utc),
        close=6000.0, volume=12.0, sequence=1, id="event-1", session_id="CME-2025-06-02")
    event = _bar_event(SimpleNamespace(bar=bar))
    assert event.instrument == "ESM5"
    assert event.contract_id == "ESM5"
    assert event.event_id == "event-1"


def test_oos_structure_builds_chronological_inputs_without_exposing_targets():
    start = datetime(2025, 6, 2, 14, 30, tzinfo=timezone.utc)
    names = tuple(f"f{i}" for i in range(24))
    rows = tuple(MarketObservation("ES", "ESM5", "session-1",
        (start + timedelta(minutes=i)).isoformat(), start.isoformat(), names,
        tuple(float(i + j) for j in range(24)),
        {"direction": 0, "volatility": 1, "structure": 2},
        (start + timedelta(minutes=i + 5)).isoformat(), "d" * 64,
        "bot2-feature-row-v3", "bot2-future-market-state-v3") for i in range(10))
    split = SimpleNamespace(canonical_rows={"OOS_TEST": rows}, horizon_minutes=5)
    verified = SimpleNamespace(data={"feature_specification": {
        "sequence_length": 8, "sequence_cadence_seconds": 60,
        "features": list(names)}})
    scaler = SimpleNamespace(transform=lambda raw: np.asarray(raw, dtype=np.float32))
    result = _validate_oos_sequence_structure(split, scaler, verified)
    assert result["count"] == 3
    assert result["sample_x"].shape == (1, 8, 24)
    assert len(result["fingerprint"]) == 64
    assert set(result) == {"count", "fingerprint", "sample_x"}


def test_partition_preflight_applies_manifest_elapsed_time_purge_boundaries():
    names = tuple(f"f{i}" for i in range(24))

    def row(day, hour, minute):
        timestamp = datetime(2025, 6, int(day), hour, minute, tzinfo=timezone.utc)
        session = timestamp.replace(hour=14, minute=30)
        return MarketObservation("ES", "ESM5", f"session-{day}",
            timestamp.isoformat(), session.isoformat(), names, tuple(float(i) for i in range(24)),
            {"direction": 0, "volatility": 1, "structure": 2},
            (timestamp + timedelta(minutes=5)).isoformat(), "d" * 64,
            "bot2-feature-row-v3", "bot2-future-market-state-v3")

    parts = {"TRAIN": (row("02", 13, 18), row("02", 13, 19)),
        "VALIDATION_AND_CALIBRATION": (row("02", 13, 54), row("02", 13, 55)),
        "OOS_TEST": (row("02", 14, 30),)}
    purge_exclusions = _apply_walk_forward_purge(parts, purge_minutes=30)
    assert [item.exchange_timestamp_utc for item in parts["TRAIN"]] == [
        "2025-06-02T13:18:00+00:00"]
    assert [item.exchange_timestamp_utc for item in parts["VALIDATION_AND_CALIBRATION"]] == [
        "2025-06-02T13:54:00+00:00"]
    assert purge_exclusions == {"TRAIN": 1,
        "VALIDATION_AND_CALIBRATION": 1, "OOS_TEST": 0}
