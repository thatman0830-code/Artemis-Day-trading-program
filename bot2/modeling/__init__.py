"""BOT 2.0 Phase 3 research-plane baseline modeling (no execution authority)."""

from .contracts import CostModel, ExperimentSpec, ExperimentResult
from .splits import chronological_split, walk_forward_splits
from .preprocess import TrainOnlyStandardizer
from .baselines import fit_baseline
from .registry import ExperimentRegistry
from .guards import validate_feature_cutoff, assert_holdout_not_for_tuning

__all__ = ["CostModel", "ExperimentSpec", "ExperimentResult", "chronological_split",
           "walk_forward_splits", "TrainOnlyStandardizer", "fit_baseline", "ExperimentRegistry",
           "validate_feature_cutoff", "assert_holdout_not_for_tuning"]
