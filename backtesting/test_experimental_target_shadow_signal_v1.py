from datetime import datetime, timezone
from decimal import Decimal

from backtesting.experimental_target_shadow_signal_v1 import *
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket as Market
from backtesting.ninjatrader_shadow_profile_comparison_v1 import ShadowSide
from backtesting.target_liquidity_ab_research_v1 import TargetCandidateV1

T = datetime(2026, 9, 14, tzinfo=timezone.utc)


def target(identity, level, source="PDH", clustered=False):
    return TargetCandidateV1(identity, "BSL", Decimal(level), source, clustered, True)


def test_major_single_can_create_only_shadow_signal():
    result = build_experimental_target_shadow_signal(source_candidate_id="candidate-1",
        market=Market.ES, side=ShadowSide.LONG, signal_time=T,
        entry_price=Decimal("100"), stop_price=Decimal("95"),
        candidates=(target("pdh", "110"),))
    assert result.state is ExperimentalShadowState.SHADOW_SIGNAL_AVAILABLE
    assert result.target_price == Decimal("110") and result.signal_id
    assert result.canonical_policy_changed is result.paper_execution_permitted is result.trading_authority is False


def test_clustered_target_is_left_to_canonical_lane():
    result = build_experimental_target_shadow_signal(source_candidate_id="candidate-1",
        market=Market.ES, side=ShadowSide.LONG, signal_time=T,
        entry_price=Decimal("100"), stop_price=Decimal("95"),
        candidates=(target("pool", "110", "EQUAL_HIGH", True),))
    assert result.state is ExperimentalShadowState.CANONICAL_TARGET_ALREADY_AVAILABLE
    assert result.signal_id is None and result.target_price is None


def test_missing_target_and_invalid_price_order_fail_closed():
    missing = build_experimental_target_shadow_signal(source_candidate_id="candidate-1",
        market=Market.ES, side=ShadowSide.LONG, signal_time=T,
        entry_price=Decimal("100"), stop_price=Decimal("95"), candidates=())
    invalid = build_experimental_target_shadow_signal(source_candidate_id="candidate-2",
        market=Market.ES, side=ShadowSide.LONG, signal_time=T,
        entry_price=Decimal("100"), stop_price=Decimal("105"),
        candidates=(target("pdh", "110"),))
    assert missing.state is ExperimentalShadowState.NO_EXPERIMENTAL_TARGET
    assert invalid.state is ExperimentalShadowState.INVALID_PRICE_ORDER
    assert missing.signal_id is invalid.signal_id is None
