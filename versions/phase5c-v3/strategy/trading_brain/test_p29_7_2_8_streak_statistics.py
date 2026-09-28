from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_8_streak_statistics import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def trade(result, suffix, closed):
    return accounting(result, suffix, closed)


def test_maximum_winning_streak():
    results = (TradeResult.WIN, TradeResult.WIN, TradeResult.LOSS, TradeResult.WIN, TradeResult.WIN, TradeResult.WIN, TradeResult.LOSS, TradeResult.WIN)
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=tuple(trade(result, str(i), 26 + i) for i, result in enumerate(results)), as_of_time=40).snapshot
    assert snapshot.maximum_winning_streak == 3 and snapshot.maximum_losing_streak == 1


def test_maximum_losing_streak_and_breakeven_interrupt():
    results = (TradeResult.LOSS, TradeResult.LOSS, TradeResult.BREAKEVEN, TradeResult.LOSS, TradeResult.LOSS, TradeResult.LOSS, TradeResult.WIN)
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=tuple(trade(result, str(i), 26 + i) for i, result in enumerate(results)), as_of_time=40).snapshot
    assert snapshot.maximum_losing_streak == 3 and snapshot.maximum_winning_streak == 1


def test_breakeven_interrupts_wins_and_losses():
    results = (TradeResult.WIN, TradeResult.WIN, TradeResult.BREAKEVEN, TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN, TradeResult.LOSS)
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=tuple(trade(result, str(i), 26 + i) for i, result in enumerate(results)), as_of_time=40).snapshot
    assert (snapshot.maximum_winning_streak, snapshot.maximum_losing_streak) == (2, 1)


@pytest.mark.parametrize("results,expected", [
    ((), (0, 0)), ((TradeResult.BREAKEVEN,), (0, 0)),
    ((TradeResult.WIN,), (1, 0)), ((TradeResult.LOSS,), (0, 1)),
])
def test_empty_zero_and_single_trade_boundaries(results, expected):
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=tuple(trade(result, str(i), 26 + i) for i, result in enumerate(results)), as_of_time=30).snapshot
    assert (snapshot.maximum_winning_streak, snapshot.maximum_losing_streak) == expected


def test_tied_maxima_preserve_every_group_in_order():
    results = (TradeResult.WIN, TradeResult.WIN, TradeResult.LOSS, TradeResult.WIN, TradeResult.WIN, TradeResult.LOSS, TradeResult.LOSS, TradeResult.WIN)
    items = tuple(trade(result, str(i), 26 + i) for i, result in enumerate(results))
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=items, as_of_time=40).snapshot
    assert snapshot.maximum_winning_streak_trade_id_groups == (("trade-0", "trade-1"), ("trade-3", "trade-4"))
    assert snapshot.maximum_losing_streak_trade_id_groups == (("trade-5", "trade-6"),)


def test_canonical_tie_order_and_point_in_time_exclusion():
    items = (trade(TradeResult.WIN, "b", 27), trade(TradeResult.WIN, "future", 31), trade(TradeResult.WIN, "a", 27), trade(TradeResult.LOSS, "z", 26))
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.source_trade_ids == ("trade-z", "trade-a", "trade-b")
    assert snapshot.maximum_winning_streak == 2
    assert snapshot.future_excluded_trade_ids == ("trade-future",)


def test_authoritative_results_are_not_reclassified_from_pnl():
    item = replace(trade(TradeResult.LOSS, "odd", 26), net_pnl=Decimal("10"), net_r=Decimal("1"))
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert snapshot.maximum_losing_streak == 1 and snapshot.maximum_winning_streak == 0


@pytest.mark.parametrize("field", ["scope", "trades"])
def test_missing_inputs_fail_closed(field):
    values = {"scope": scope(), "trades": ()}; values[field] = None
    assert StreakStatisticsEngine().calculate(**values, as_of_time=30).error.reason == "REQUIRED_STREAK_INPUT_MISSING"


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id": "other"}, "STREAK_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol": "ETH"}, "STREAK_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe": "5m"}, "STREAK_TIMEFRAME_MISMATCH"),
    ({"model": SetupModel.REVERSAL_1}, "STREAK_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction": StructuralRegime.BEARISH}, "STREAK_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version": "v2"}, "STREAK_INPUT_VERSION_MISMATCH"),
])
def test_scope_and_version_separation(change, reason):
    item = replace(trade(TradeResult.WIN, "one", 26), **change)
    assert StreakStatisticsEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).error.reason == reason


def test_duplicate_keys_have_data_integrity_precedence():
    item = trade(TradeResult.WIN, "same", 26)
    result = StreakStatisticsEngine().calculate(scope=scope(), trades=(item, replace(item, id="other", immutable=False)), as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_nonfinal_nonfinite_and_invalid_chronology_fail_closed():
    engine = StreakStatisticsEngine(); item = trade(TradeResult.WIN, "one", 26)
    assert engine.calculate(scope=scope(), trades=(replace(item, immutable=False),), as_of_time=30).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), trades=(replace(item, net_r=Decimal("NaN")),), as_of_time=30).error.reason == "NON_FINITE_ACCOUNTING_INPUT"
    assert engine.calculate(scope=scope(), trades=(replace(item, opened_time=27),), as_of_time=30).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    engine = StreakStatisticsEngine(); item = trade(TradeResult.WIN, "one", 26)
    first = engine.calculate(scope=scope(), trades=(item,), as_of_time=30)
    replay = engine.calculate(scope=scope(), trades=(item,), as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(scope=scope(), trades=(item, trade(TradeResult.WIN, "two", 27)), as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_is_immutable_and_sources_unchanged():
    item = trade(TradeResult.WIN, "one", 26); original = item
    snapshot = StreakStatisticsEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert item == original
    with pytest.raises(FrozenInstanceError):
        snapshot.maximum_winning_streak = 9
