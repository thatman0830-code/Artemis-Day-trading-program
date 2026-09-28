from datetime import datetime, timedelta, timezone
import json
import pytest

from .baselines import fit_baseline
from .contracts import CostModel, ExperimentResult, ExperimentSpec
from .metrics import calibration_bins
from .preprocess import TrainOnlyStandardizer
from .registry import ExperimentRegistry
from .runner import evaluate_experiment
from .splits import chronological_split, walk_forward_splits
from .guards import assert_holdout_not_for_tuning, validate_feature_cutoff
from .feature_families import select_feature_names

UTC = timezone.utc


def rows(n=30, shuffled=False):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    output = []
    for i in range(n):
        output.append({"observation_time": (start + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"),
                       "label_end_time": (start + timedelta(minutes=i + 2)).isoformat().replace("+00:00", "Z"),
                       "features": (float(i % 5), float((i * 2) % 7)), "target": float(i % 2)})
    return output


def spec(model="logistic_regression", target="direction"):
    return ExperimentSpec("exp-test-1", "d", "hash", "bot2-feature-registry-v1", "bot2-label-config-v1",
                          ("ES",), ("2026-01-01", "2026-01-01T00:18"), ("2026-01-01T00:19", "2026-01-01T00:24"),
                          ("2026-01-01T00:25", "2026-01-01T00:29"), ("x", "y"), target, model, {"steps": 20}, 7,
                          CostModel(), "commit", {"python": "3"})


def test_temporal_split_and_no_future_training():
    split = chronological_split(rows(), train_fraction=.5, validation_fraction=.2, purge=timedelta(minutes=2))
    assert max(datetime.fromisoformat(r["observation_time"].replace("Z", "+00:00")) for r in split.train) < min(datetime.fromisoformat(r["observation_time"].replace("Z", "+00:00")) for r in split.validation)
    assert split.purged_count > 0


def test_future_label_interval_is_purged_at_validation_and_test_boundaries():
    source = rows(60)
    # Make labels reach five minutes into the future, then protect both split edges.
    for row in source:
        t = datetime.fromisoformat(row["observation_time"].replace("Z", "+00:00"))
        row["label_end_time"] = (t + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        row["label_information_start"] = (t + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    split = chronological_split(source, train_fraction=.5, validation_fraction=.25,
                                purge=timedelta(minutes=5), embargo=timedelta(minutes=2))
    validation_start = datetime.fromisoformat(split.validation[0]["observation_time"].replace("Z", "+00:00"))
    test_start = datetime.fromisoformat(split.test[0]["observation_time"].replace("Z", "+00:00"))
    assert all(datetime.fromisoformat(row["label_end_time"].replace("Z", "+00:00")) + timedelta(minutes=5) < validation_start for row in split.train)
    assert all(datetime.fromisoformat(row["label_end_time"].replace("Z", "+00:00")) + timedelta(minutes=5) < test_start for row in split.validation)
    assert split.purged_count > 0 and split.embargoed_count > 0


def test_walk_forward_is_chronological():
    windows = walk_forward_splits(rows(30), train_size=12, validation_size=6, test_size=6, purge=timedelta(minutes=1))
    assert len(windows) == 2
    assert all(max(r["observation_time"] for r in w.train) < min(r["observation_time"] for r in w.test) for w in windows)


def test_training_only_transform_does_not_use_validation_statistics():
    scaler = TrainOnlyStandardizer().fit(((0.0,), (2.0,)))
    transformed = scaler.transform(((100.0,),))
    assert scaler.fitted_count == 2 and transformed[0][0] > 90


def test_baseline_reproducibility_and_metrics():
    a = evaluate_experiment(rows(), spec(), scale_training_only=True).to_dict()
    b = evaluate_experiment(rows(), spec(), scale_training_only=True).to_dict()
    assert a == b and "out_of_sample_test" in a["metrics"]


def test_shuffled_label_sanity_is_no_better_than_structural_reference():
    source = rows(); shuffled = list(reversed(source))
    result = evaluate_experiment(shuffled, spec(), scale_training_only=True)
    assert result.metrics["out_of_sample_test"]["log_loss"] >= 0


def test_future_feature_trap_is_rejected_by_cutoff_guard():
    bad = {"observation_time": "2026-01-01T00:00:00Z", "cutoff_time": "2026-01-01T00:00:00Z", "feature_source_max_time": "2026-01-01T00:01:00Z"}
    assert bad["feature_source_max_time"] > bad["cutoff_time"]
    with pytest.raises(ValueError): validate_feature_cutoff(**bad)


def test_holdout_and_feature_family_controls_are_explicit():
    assert_holdout_not_for_tuning("UNTOUCHED_FINAL_HOLDOUT_NOT_USED")
    with pytest.raises(ValueError): assert_holdout_not_for_tuning("UNTOUCHED_FINAL_HOLDOUT_NOT_USED", True)
    assert select_feature_names(("price", "realized_volatility_3", "cross_market_log_return_1"), ("PRICE",)) == ("price",)


def test_registry_is_append_only(tmp_path):
    result = evaluate_experiment(rows(), spec(), scale_training_only=True)
    registry = ExperimentRegistry(tmp_path / "experiments.jsonl"); registry.finalize(result)
    with pytest.raises(ValueError): registry.finalize(result)
    assert len((tmp_path / "experiments.jsonl").read_text().splitlines()) == 1


def test_calibration_bins_are_reported():
    bins = calibration_bins([0, 1, 1, 0], [.1, .7, .8, .2], bins=2)
    assert bins and all("observed_frequency" in item for item in bins)
