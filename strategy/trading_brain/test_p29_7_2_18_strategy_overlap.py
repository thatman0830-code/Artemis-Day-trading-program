from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_18_strategy_overlap import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


AS_OF = 100


def scope(**changes):
    return replace(OverlapScope("overlap-scope", "v1", "overlap-calc-v1", "history-v1"), **changes)


def trade(strategy, suffix, opened, closed, risk="10", **changes):
    source = accounting(TradeResult.WIN, suffix, closed)
    return replace(
        source, strategy_id=strategy, opened_time=opened, closed_time=closed,
        accounting_time=closed, actual_risk_dollars=Decimal(risk), input_version="v1", **changes,
    )


def ordered(*trades):
    return tuple(sorted(trades, key=lambda item: (item.closed_time, item.trade_id)))


def calculate(trades, *, selected_scope=None, as_of=AS_OF, history=OverlapHistory()):
    return StrategyOverlapEngine().calculate(
        scope=selected_scope or scope(), trades=trades, as_of_time=as_of, history=history,
    )


def test_union_not_pairwise_sum_and_exact_trade_pair_records():
    trades = ordered(trade("A", "a1", 0, 10), trade("A", "a2", 4, 8), trade("B", "b", 2, 9))
    snapshot = calculate(trades).snapshot
    pair = snapshot.strategy_pair_overlaps[0]
    assert pair.overlap_trade_pair_count == 2
    assert tuple(row.overlap_duration for row in snapshot.overlaps) == (7, 4)
    assert pair.total_overlap_duration == 7
    assert tuple((row.overlap_start, row.overlap_end) for row in pair.union_intervals) == ((2, 9),)
    assert snapshot.total_pair_overlap_duration == 7


def test_timestamp_touch_same_strategy_and_zero_duration_do_not_overlap():
    trades = ordered(
        trade("A", "a1", 0, 5), trade("A", "a2", 1, 4),
        trade("B", "b", 5, 8), trade("C", "c", 3, 3),
    )
    snapshot = calculate(trades).snapshot
    assert snapshot.overlaps == () and snapshot.overlap_trade_pair_count == 0
    assert all(not pair.co_occurrence and pair.total_overlap_duration == 0 for pair in snapshot.strategy_pair_overlaps)


def test_empty_single_strategy_and_single_trade_boundaries():
    empty = calculate(()).snapshot
    assert (empty.strategy_count, empty.maximum_simultaneous_strategies, empty.total_pair_overlap_duration) == (0, 0, 0)
    assert empty.strategy_pair_overlaps == empty.overlaps == empty.strategy_count_observations == ()
    single = calculate((trade("A", "one", 1, 5),)).snapshot
    assert single.strategy_count == single.maximum_simultaneous_strategies == 1
    assert single.strategy_pair_count == single.overlap_trade_pair_count == 0
    same = calculate(ordered(trade("A", "one", 1, 5), trade("A", "two", 2, 6))).snapshot
    assert same.maximum_simultaneous_strategies == 1 and same.overlaps == ()


def test_simultaneous_strategy_count_and_exact_finalized_risk_observations():
    trades = ordered(trade("A", "a1", 0, 10, "10"), trade("A", "a2", 4, 8, "20"), trade("B", "b", 2, 9, "30"))
    snapshot = calculate(trades).snapshot
    assert snapshot.maximum_simultaneous_strategies == 2
    assert snapshot.maximum_simultaneous_risk == Decimal("60")
    middle = next(row for row in snapshot.strategy_count_observations if row.timestamp == 4)
    assert middle.active_strategy_ids == ("A", "B") and middle.active_strategy_count == 2
    assert middle.active_trade_ids == ("trade-a1", "trade-a2", "trade-b")
    assert middle.simultaneous_risk == 60 and middle.simultaneous_notional_exposure is None


def test_direction_symbol_model_timeframe_and_breakeven_are_descriptive_only():
    a = trade("A", "a", 0, 10, symbol="BTC", timeframe="1m", model=SetupModel.CONTINUATION, direction=StructuralRegime.BULLISH)
    b = trade("B", "b", 2, 8, symbol="ETH", timeframe="5m", model=SetupModel.REVERSAL_1, direction=StructuralRegime.BEARISH, trade_result=TradeResult.BREAKEVEN, net_pnl=Decimal("0"), net_r=Decimal("0"))
    overlap = calculate(ordered(a, b)).snapshot.overlaps[0]
    assert (overlap.symbol_a, overlap.symbol_b, overlap.timeframe_a, overlap.timeframe_b) == ("BTC", "ETH", "1m", "5m")
    assert overlap.direction_a != overlap.direction_b and overlap.overlap_duration == 6


def test_pair_matrix_order_is_symmetric_by_canonical_pair_key_with_zero_diagonal_implicit():
    snapshot = calculate(ordered(trade("C", "c", 0, 4), trade("A", "a", 1, 5), trade("B", "b", 10, 12))).snapshot
    assert snapshot.strategy_ids == ("A", "B", "C")
    assert tuple((row.strategy_a_id, row.strategy_b_id) for row in snapshot.strategy_pair_overlaps) == (("A", "B"), ("A", "C"), ("B", "C"))
    assert tuple(row.total_overlap_duration for row in snapshot.strategy_pair_overlaps) == (0, 3, 0)


def test_point_in_time_excludes_future_finalized_records_without_lookahead():
    past = trade("A", "past", 0, 20)
    future = trade("B", "future", 10, 110)
    snapshot = calculate(ordered(past, future), as_of=100).snapshot
    assert snapshot.source_trade_ids == ("trade-past",)
    assert snapshot.future_excluded_trade_ids == ("trade-future",)
    assert snapshot.overlaps == ()


def test_later_snapshot_preserves_previously_finalized_overlap_object():
    old = ordered(trade("A", "a", 0, 5), trade("B", "b", 1, 4))
    earlier = calculate(old, as_of=10).snapshot
    later = calculate(ordered(*old, trade("C", "c", 20, 25)), as_of=30).snapshot
    assert later.overlaps[0] == earlier.overlaps[0]
    assert earlier.overlaps[0].created_time == 5


def test_closed_time_trade_id_input_order_and_chronology_are_strict():
    a = trade("A", "a", 0, 10); b = trade("B", "b", 1, 9)
    assert calculate((a, b)).error.reason == "OVERLAP_TRADE_ORDER_INVALID"
    assert calculate((replace(a, opened_time=11),)).error.reason == "OVERLAP_TRADE_CHRONOLOGY_INVALID"
    assert calculate((replace(a, accounting_time=9),)).error.reason == "OVERLAP_TRADE_CHRONOLOGY_INVALID"


def test_duplicate_trade_accounting_or_position_key_fails_closed():
    first = trade("A", "same", 0, 5)
    for duplicate in (
        replace(first, id="accounting-other"),
        replace(trade("B", "other", 1, 4), id=first.id),
        replace(trade("B", "other", 1, 4), position_id=first.position_id),
    ):
        result = calculate(ordered(first, duplicate))
        assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_source_version_identity_nonfinite_and_invalid_numeric_facts_fail_closed():
    source = trade("A", "a", 0, 5)
    assert calculate((replace(source, input_version="v2"),)).error.reason == "OVERLAP_SOURCE_VERSION_MISMATCH"
    assert calculate((replace(source, actual_risk_dollars=Decimal("NaN")),)).error.reason == "NON_FINITE_OVERLAP_INPUT"
    assert calculate((replace(source, actual_risk_dollars=Decimal("0")),)).error.reason == "OVERLAP_ACCOUNTING_FACT_INVALID"
    assert calculate((replace(source, strategy_id=""),)).error.reason == "OVERLAP_TRADE_IDENTITY_MISSING"


def test_missing_nonfinal_scope_and_versions_fail_closed():
    assert StrategyOverlapEngine().calculate(scope=scope(), trades=None, as_of_time=AS_OF).error.reason == "REQUIRED_OVERLAP_INPUT_MISSING"
    assert calculate((replace(trade("A", "a", 0, 5), immutable=False),)).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert calculate((), selected_scope=scope(source_version="")).error.reason == "OVERLAP_SCOPE_INVALID"


def test_identical_replay_is_idempotent_conflicts_rejected_and_history_immutable():
    trades = ordered(trade("A", "a", 0, 5), trade("B", "b", 1, 4))
    first = calculate(trades)
    replay = calculate(trades, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    changed = ordered(*trades, trade("C", "c", 2, 3))
    conflict = calculate(changed, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert conflict.error.reason == "CONFLICTING_OVERLAP_SNAPSHOT"
    with pytest.raises(FrozenInstanceError):
        first.snapshot.maximum_simultaneous_strategies = 9
