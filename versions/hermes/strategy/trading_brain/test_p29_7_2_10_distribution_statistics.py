from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_10_distribution_statistics import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(DistributionScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "source-v1", "analytics-v1", "history-v1"), **changes)


def trade(result, suffix, closed, pnl, net_r):
    return replace(accounting(result, suffix, closed), net_pnl=Decimal(pnl), net_r=Decimal(net_r))


def test_all_and_classified_distributions_are_exact_and_sorted():
    items = (trade(TradeResult.WIN, "w2", 28, "5", "0.5"), trade(TradeResult.LOSS, "l", 27, "-2", "-0.2"), trade(TradeResult.BREAKEVEN, "b", 29, "0", "0"), trade(TradeResult.WIN, "w1", 26, "3", "0.3"))
    snapshot = DistributionStatisticsEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert (snapshot.trade_count, snapshot.win_count, snapshot.loss_count, snapshot.breakeven_count) == (4, 2, 1, 1)
    assert snapshot.net_pnl_distribution == tuple(map(Decimal, ("-2", "0", "3", "5")))
    assert snapshot.net_r_distribution == tuple(map(Decimal, ("-0.2", "0", "0.3", "0.5")))
    assert snapshot.winning_net_pnl_distribution == (Decimal("3"), Decimal("5"))
    assert snapshot.losing_net_r_distribution == (Decimal("-0.2"),)
    assert snapshot.breakeven_net_pnl_distribution == (Decimal("0"),)


def test_empty_input_has_empty_distributions_not_invented_statistics():
    snapshot = DistributionStatisticsEngine().calculate(scope=scope(), trades=(), as_of_time=30).snapshot
    assert snapshot.trade_count == snapshot.win_count == snapshot.loss_count == snapshot.breakeven_count == 0
    assert snapshot.observations == snapshot.net_pnl_distribution == snapshot.net_r_distribution == ()
    assert snapshot.winning_net_r_distribution == snapshot.losing_net_r_distribution == snapshot.breakeven_net_r_distribution == ()


@pytest.mark.parametrize("result,pnl,net_r,field", [
    (TradeResult.WIN, "0", "0", "winning_net_r_distribution"),
    (TradeResult.LOSS, "0", "0", "losing_net_r_distribution"),
    (TradeResult.BREAKEVEN, "0", "0", "breakeven_net_r_distribution"),
])
def test_single_zero_record_uses_authoritative_classification(result, pnl, net_r, field):
    snapshot = DistributionStatisticsEngine().calculate(scope=scope(), trades=(trade(result, "one", 26, pnl, net_r),), as_of_time=30).snapshot
    assert snapshot.trade_count == 1 and getattr(snapshot, field) == (Decimal("0"),)


def test_tied_values_are_all_retained_without_arbitrary_deduplication():
    items = (trade(TradeResult.WIN, "b", 27, "1", "0.1"), trade(TradeResult.WIN, "a", 27, "1", "0.1"))
    snapshot = DistributionStatisticsEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.net_pnl_distribution == (Decimal("1"), Decimal("1"))
    assert snapshot.source_trade_ids == ("trade-a", "trade-b")


def test_chronological_observations_are_separate_from_sorted_distribution_values():
    items = (trade(TradeResult.WIN, "later", 27, "-5", "-0.5"), trade(TradeResult.LOSS, "early", 26, "10", "1"))
    snapshot = DistributionStatisticsEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert tuple(item.trade_id for item in snapshot.observations) == ("trade-early", "trade-later")
    assert snapshot.net_pnl_distribution == (Decimal("-5"), Decimal("10"))
    assert snapshot.winning_net_pnl_distribution == (Decimal("-5"),)
    assert snapshot.losing_net_pnl_distribution == (Decimal("10"),)


def test_point_in_time_excludes_future_without_rewriting_past():
    past = trade(TradeResult.WIN, "past", 29, "1", "0.1"); future = trade(TradeResult.LOSS, "future", 31, "-100", "-10")
    snapshot = DistributionStatisticsEngine().calculate(scope=scope(), trades=(future, past), as_of_time=30).snapshot
    assert snapshot.net_pnl_distribution == (Decimal("1"),)
    assert snapshot.future_excluded_trade_ids == ("trade-future",)


@pytest.mark.parametrize("field", ["scope", "trades"])
def test_missing_inputs_fail_closed(field):
    values = {"scope": scope(), "trades": ()}; values[field] = None
    assert DistributionStatisticsEngine().calculate(**values, as_of_time=30).error.reason == "REQUIRED_DISTRIBUTION_INPUT_MISSING"


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id": "other"}, "DISTRIBUTION_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol": "ETH"}, "DISTRIBUTION_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe": "5m"}, "DISTRIBUTION_TIMEFRAME_MISMATCH"),
    ({"model": SetupModel.REVERSAL_1}, "DISTRIBUTION_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction": StructuralRegime.BEARISH}, "DISTRIBUTION_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version": "v2"}, "DISTRIBUTION_INPUT_VERSION_MISMATCH"),
])
def test_scope_separation(change, reason):
    item = replace(trade(TradeResult.WIN, "one", 26, "1", "0.1"), **change)
    assert DistributionStatisticsEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).error.reason == reason


def test_source_calculation_and_historical_versions_isolate_snapshots():
    engine = DistributionStatisticsEngine(); item = trade(TradeResult.WIN, "one", 26, "1", "0.1")
    first = engine.calculate(scope=scope(), trades=(item,), as_of_time=30)
    second_scope = scope(source_version="source-v2", calculation_version="analytics-v2", historical_version="history-v2")
    second = engine.calculate(scope=second_scope, trades=(item,), as_of_time=30, history=first.history)
    assert second.valid and second.snapshot.id != first.snapshot.id


def test_duplicate_keys_have_data_integrity_precedence():
    item = trade(TradeResult.WIN, "same", 26, "1", "0.1")
    result = DistributionStatisticsEngine().calculate(scope=scope(), trades=(item, replace(item, id="other", immutable=False)), as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_nonfinal_nonfinite_and_chronologically_invalid_records_fail_closed():
    engine = DistributionStatisticsEngine(); item = trade(TradeResult.WIN, "one", 26, "1", "0.1")
    assert engine.calculate(scope=scope(), trades=(replace(item, immutable=False),), as_of_time=30).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), trades=(replace(item, net_r=Decimal("NaN")),), as_of_time=30).error.reason == "NON_FINITE_DISTRIBUTION_INPUT"
    assert engine.calculate(scope=scope(), trades=(replace(item, opened_time=27),), as_of_time=30).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_invalid_or_incomplete_version_scope_fails_closed():
    assert DistributionStatisticsEngine().calculate(scope=scope(source_version=""), trades=(), as_of_time=30).error.reason == "DISTRIBUTION_SCOPE_INVALID"
    assert DistributionStatisticsEngine().calculate(scope=replace(scope(), immutable=False), trades=(), as_of_time=30).error.reason == "DISTRIBUTION_SCOPE_INVALID"


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    engine = DistributionStatisticsEngine(); item = trade(TradeResult.WIN, "one", 26, "1", "0.1")
    first = engine.calculate(scope=scope(), trades=(item,), as_of_time=30)
    replay = engine.calculate(scope=scope(), trades=(item,), as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(scope=scope(), trades=(item, trade(TradeResult.LOSS, "two", 27, "-1", "-0.1")), as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_and_observations_are_immutable_and_source_unchanged():
    item = trade(TradeResult.WIN, "one", 26, "1", "0.1"); original = item
    snapshot = DistributionStatisticsEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert item == original
    with pytest.raises(FrozenInstanceError):
        snapshot.trade_count = 9
    with pytest.raises(FrozenInstanceError):
        snapshot.observations[0].net_r = Decimal("9")
