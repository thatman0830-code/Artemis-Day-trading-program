"""Controlled experiment runner for Phase 3 research artifacts."""
from __future__ import annotations

from typing import Sequence, Mapping, Any
from .baselines import fit_baseline
from .contracts import ExperimentResult, ExperimentSpec, MODEL_SCHEMA
from .metrics import classification_metrics, calibration_bins, regression_metrics
from .preprocess import TrainOnlyStandardizer
from .splits import chronological_split


def evaluate_experiment(rows: Sequence[Mapping[str, Any]], spec: ExperimentSpec, *, scale_training_only: bool = False) -> ExperimentResult:
    split = chronological_split(rows)
    def xy(part): return [tuple(float(v) for v in row["features"]) for row in part], [float(row["target"]) for row in part]
    x_train, y_train = xy(split.train); x_val, y_val = xy(split.validation); x_test, y_test = xy(split.test)
    if scale_training_only:
        scaler = TrainOnlyStandardizer().fit(x_train)
        x_train, x_val, x_test = scaler.transform(x_train), scaler.transform(x_val), scaler.transform(x_test)
    classification = spec.target in ("direction", "barrier_outcome") or "classification" in spec.model_type
    prediction_val, _, _ = fit_baseline(spec.model_type, x_train, y_train, x_val, hyperparameters=spec.hyperparameters)
    prediction_test, _, _ = fit_baseline(spec.model_type, x_train, y_train, x_test, hyperparameters=spec.hyperparameters)
    if classification:
        val_metrics = classification_metrics([int(v) for v in y_val], prediction_val)
        test_metrics = classification_metrics([int(v) for v in y_test], prediction_test)
        calibration = calibration_bins([int(v) for v in y_test], prediction_test)
    else:
        val_metrics = regression_metrics(y_val, prediction_val); test_metrics = regression_metrics(y_test, prediction_test); calibration = ()
    return ExperimentResult(MODEL_SCHEMA, spec, {"train": len(split.train), "validation": len(split.validation), "test": len(split.test),
                                                  "purged": split.purged_count, "embargoed": split.embargoed_count},
                            {"validation": val_metrics, "out_of_sample_test": test_metrics, "test_cost_per_unit": spec.cost_model.total_per_unit}, calibration)
