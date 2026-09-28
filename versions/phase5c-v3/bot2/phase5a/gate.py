"""Fail-closed eligibility checks for Phase 5A supervised comparison."""
from __future__ import annotations

from collections.abc import Mapping


def phase5a_blockers(*, manifest: Mapping, source_has_receipt_timestamps: bool,
                     independent_targets_available: bool,
                     synchronized_cross_market_coverage: float) -> tuple[str, ...]:
    """Return objective reasons why Model A evaluation must not proceed.

    Phase 5A labels created by the Phase 4 rule on the same endpoint features
    are teacher labels, not independent outcomes. Missing historical receipt
    clocks and unavailable paired-market features are likewise surfaced rather
    than replaced by synthetic values or forward-filled data.
    """
    blockers: list[str] = []
    source = manifest.get("source_data", {})
    targets = manifest.get("targets", {})
    if not source_has_receipt_timestamps:
        blockers.append("SOURCE_RECEIPT_TIMESTAMP_UNAVAILABLE")
    if (not independent_targets_available and
            targets.get("target_source") == "Phase 4 deterministic RegimeAssignment from the same endpoint causal feature row"):
        blockers.append("TARGET_SELF_LABEL_IMITATION")
    if synchronized_cross_market_coverage <= 0:
        blockers.append("CROSS_MARKET_FEATURE_COVERAGE_UNAVAILABLE")
    return tuple(blockers)
