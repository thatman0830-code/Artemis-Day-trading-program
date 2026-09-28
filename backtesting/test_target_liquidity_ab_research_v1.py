from decimal import Decimal

from backtesting.target_liquidity_ab_research_v1 import (
    TargetCandidateV1, TargetLane, evaluate_ab,
)


def candidate(identity, level, source, clustered=False, external=True, side="BSL"):
    return TargetCandidateV1(identity, side, Decimal(level), source, clustered, external)


def test_baseline_uses_cluster_and_experimental_can_use_nearer_major_single():
    baseline, experimental = evaluate_ab(candidates=(
        candidate("pool", "110", "EQUAL_HIGH", clustered=True),
        candidate("pdh", "105", "PDH"),
        candidate("minor", "103", "SESSION_HIGH"),
    ), current_price=Decimal("100"), required_side="BSL")
    assert baseline.lane is TargetLane.BASELINE_CLUSTERED and baseline.selected.candidate_id == "pool"
    assert experimental.selected.candidate_id == "pdh"
    assert "minor" not in experimental.eligible_candidate_ids
    for result in (baseline, experimental):
        assert result.comparison_only and not result.canonical_policy_changed
        assert not result.paper_execution_permitted and not result.trading_authority


def test_direction_and_external_requirement_fail_closed():
    baseline, experimental = evaluate_ab(candidates=(
        candidate("behind", "99", "PDH"),
        candidate("internal", "105", "PDH", external=False),
    ), current_price=Decimal("100"), required_side="BSL")
    assert baseline.selected is None and experimental.selected is None
