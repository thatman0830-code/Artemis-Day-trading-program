"""Fail-closed checks for research-plane feature provenance and holdout use."""
from __future__ import annotations

from datetime import datetime


def validate_feature_cutoff(*, observation_time: str, cutoff_time: str, feature_source_max_time: str) -> None:
    observation = datetime.fromisoformat(observation_time.replace("Z", "+00:00"))
    cutoff = datetime.fromisoformat(cutoff_time.replace("Z", "+00:00"))
    source_max = datetime.fromisoformat(feature_source_max_time.replace("Z", "+00:00"))
    if cutoff != observation:
        raise ValueError("feature cutoff must equal observation time")
    if source_max > cutoff:
        raise ValueError("future-derived feature rejected")


def assert_holdout_not_for_tuning(designation: str, feedback_loop: bool = False) -> None:
    if designation != "UNTOUCHED_FINAL_HOLDOUT_NOT_USED" or feedback_loop:
        raise ValueError("final holdout is protected from development feedback")
