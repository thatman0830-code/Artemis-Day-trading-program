from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodDefinition, PeriodStatisticsEngine, PeriodType
from strategy.trading_brain.p29_7_2_15_strategy_aggregation import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


DAY = 86400


def ts(year, month, day, tz="UTC"):
    return int(datetime(year, month, day, tzinfo=ZoneInfo(tz)).timestamp())


BASE = ts(2026, 8, 10)


def scope(**changes):
    return replace(StrategyAggregationScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "source-v1", "analytics-v1", "history-v1", PeriodType.DAILY, "UTC"), **changes)


def upstream_scope():
    return TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1")


def starting(value="1000", **changes):
    return replace(StrategyStartingEquity("starting", "canonical", Decimal(value), "source-v1", "history-v1"), **changes)


def trade(result, suffix, closed, gross, net, gross_r, net_r):
    return replace(accounting(result, suffix, closed), gross_pnl=Decimal(gross), net_pnl=Decimal(net), gross_r=Decimal(gross_r), net_r=Decimal(net_r))


def period(index, trades, *, timezone_name="UTC", period_type=PeriodType.DAILY, start=None):
    begin = BASE + index * DAY if start is None else start
    end = begin + DAY
    definition = PeriodDefinition(period_type, timezone_name, begin, end, "source-v1", "history-v1")
    return PeriodStatisticsEngine().calculate(scope=upstream_scope(), period=definition, trades=trades, as_of_time=end).snapshot


def calculate(trades=(), periods=(), *, as_of=BASE + 4 * DAY, history=StrategyAggregationHistory(), **changes):
    values = dict(scope=scope(), trades=trades, periods=periods, starting_equity=starting(), as_of_time=as_of, history=history)
    values.update(changes)
    return StrategyAggregationEngine().calculate(**values)


def test_normal_multi_period_conservation_expectancy_profit_factor_and_equity():
    items = (
        trade(TradeResult.WIN, "w", BASE + 1, "12", "10", "1.2", "1"),
        trade(TradeResult.LOSS, "l", BASE + DAY + 1, "-4", "-5", "-0.4", "-0.5"),
        trade(TradeResult.BREAKEVEN, "b", BASE + DAY + 2, "0", "0", "0", "0"),
    )
    periods = (period(0, items), period(1, items))
    snapshot = calculate(items, periods).snapshot
    assert (snapshot.trade_count, snapshot.win_count, snapshot.loss_count, snapshot.breakeven_count) == (3, 1, 1, 1)
    assert (snapshot.strategy_gross_pnl, snapshot.strategy_net_pnl) == (Decimal("8"), Decimal("5"))
    assert (snapshot.strategy_gross_r, snapshot.strategy_net_r) == (Decimal("0.8"), Decimal("0.5"))
    assert snapshot.win_rate == Decimal(1) / Decimal(3)
    assert snapshot.expectancy_net_pnl == Decimal(5) / Decimal(3)
    assert snapshot.expectancy_net_r == Decimal("0.5") / Decimal(3)
    assert snapshot.profit_factor == Decimal("2")
    assert [point.equity for point in snapshot.equity_points] == [Decimal("1010"), Decimal("1005"), Decimal("1005")]
    assert snapshot.ending_equity == Decimal("1005")
    assert [item.net_r for item in snapshot.period_observations] == [Decimal("1"), Decimal("-0.5")]


def test_empty_strategy_has_zero_additive_totals_and_null_observation_statistics():
    snapshot = calculate().snapshot
    assert snapshot.trade_count == snapshot.win_count == snapshot.loss_count == snapshot.breakeven_count == 0
    assert snapshot.strategy_gross_pnl == snapshot.strategy_net_pnl == snapshot.strategy_gross_r == snapshot.strategy_net_r == 0
    assert snapshot.win_rate is snapshot.expectancy_net_pnl is snapshot.expectancy_net_r is snapshot.profit_factor is None
    assert snapshot.ending_equity == snapshot.starting_equity == Decimal("1000") and snapshot.equity_points == ()


def test_single_positive_trade_has_infinite_profit_factor_and_defined_statistics():
    item = trade(TradeResult.WIN, "w", BASE + 1, "2", "2", "0.2", "0.2")
    snapshot = calculate((item,), (period(0, (item,)),)).snapshot
    assert snapshot.win_rate == 1 and snapshot.expectancy_net_pnl == 2
    assert snapshot.profit_factor == Decimal("Infinity")


def test_zero_trade_period_is_real_zero_observation_not_missing():
    empty_period = period(0, ())
    snapshot = calculate((), (empty_period,)).snapshot
    observation = snapshot.period_observations[0]
    assert observation.trade_count == 0 and observation.net_pnl == observation.net_r == 0
    assert observation.finalized and snapshot.zero_trade_period_ids == (empty_period.period_id,)


def test_missing_period_is_absent_and_gap_is_preserved_without_forward_fill():
    periods = (period(0, ()), period(2, ()))
    snapshot = calculate((), periods).snapshot
    assert snapshot.period_count == 2
    assert snapshot.period_gap_pairs == ((periods[0].period_id, periods[1].period_id),)
    assert tuple(item.period_id for item in snapshot.period_observations) == tuple(item.period_id for item in periods)


def test_exact_zero_and_loss_only_profit_factor_boundaries():
    zero = trade(TradeResult.BREAKEVEN, "zero", BASE + 1, "0", "0", "0", "0")
    assert calculate((zero,), (period(0, (zero,)),)).snapshot.profit_factor is None
    loss = trade(TradeResult.LOSS, "loss", BASE + 1, "-2", "-2", "-0.2", "-0.2")
    assert calculate((loss,), (period(0, (loss,)),)).snapshot.profit_factor == 0


def test_period_ties_retain_distinct_identity_and_canonical_order():
    periods = (period(0, ()), period(1, ()))
    snapshot = calculate((), periods).snapshot
    assert [item.net_r for item in snapshot.period_observations] == [Decimal(0), Decimal(0)]
    assert len({item.id for item in snapshot.period_observations}) == 2


def test_account_timezone_and_half_open_period_boundaries_are_preserved():
    timezone_name = "America/Phoenix"
    begin = ts(2026, 8, 10, timezone_name)
    at_start = trade(TradeResult.WIN, "start", begin, "1", "1", "0.1", "0.1")
    at_end = trade(TradeResult.WIN, "end", begin + DAY, "9", "9", "0.9", "0.9")
    snapshot_period = period(0, (at_start, at_end), timezone_name=timezone_name, start=begin)
    custom_scope = scope(account_timezone=timezone_name)
    snapshot = calculate((at_start, at_end), (snapshot_period,), as_of=begin + DAY, scope=custom_scope).snapshot
    observation = snapshot.period_observations[0]
    assert observation.account_timezone == timezone_name
    assert observation.period_start == begin and observation.period_end == begin + DAY
    assert observation.source_trade_ids == (at_start.trade_id,)


def test_future_trade_and_period_are_excluded_point_in_time():
    past = trade(TradeResult.WIN, "past", BASE + 1, "1", "1", "0.1", "0.1")
    future = trade(TradeResult.LOSS, "future", BASE + 2 * DAY + 1, "-9", "-9", "-0.9", "-0.9")
    periods = (period(0, (past, future)), period(2, (past, future)))
    snapshot = calculate((future, past), periods, as_of=BASE + DAY).snapshot
    assert snapshot.source_trade_ids == (past.trade_id,)
    assert snapshot.future_excluded_trade_ids == (future.trade_id,)
    assert snapshot.period_count == 1 and snapshot.future_excluded_period_ids == (periods[1].period_id,)


@pytest.mark.parametrize("field", ["scope", "trades", "periods", "starting_equity"])
def test_missing_inputs_fail_closed(field):
    values = dict(scope=scope(), trades=(), periods=(), starting_equity=starting(), as_of_time=BASE)
    values[field] = None
    assert StrategyAggregationEngine().calculate(**values).error.reason == "REQUIRED_STRATEGY_AGGREGATION_INPUT_MISSING"


def test_scope_period_type_timezone_and_version_separation():
    empty_period = period(0, ()); engine = StrategyAggregationEngine()
    assert engine.calculate(scope=scope(symbol="ETH"), trades=(), periods=(empty_period,), starting_equity=starting(), as_of_time=BASE + DAY).error.reason == "STRATEGY_PERIOD_SCOPE_MISMATCH"
    assert engine.calculate(scope=scope(period_type=PeriodType.MONTHLY), trades=(), periods=(empty_period,), starting_equity=starting(), as_of_time=BASE + DAY).error.reason == "STRATEGY_PERIOD_TYPE_OR_VERSION_MISMATCH"
    assert engine.calculate(scope=scope(account_timezone="America/Phoenix"), trades=(), periods=(empty_period,), starting_equity=starting(), as_of_time=BASE + DAY).error.reason == "STRATEGY_PERIOD_TYPE_OR_VERSION_MISMATCH"
    assert engine.calculate(scope=scope(source_version="source-v2"), trades=(), periods=(empty_period,), starting_equity=starting(source_version="source-v2"), as_of_time=BASE + DAY).error.reason == "STRATEGY_PERIOD_TYPE_OR_VERSION_MISMATCH"


def test_duplicates_nonfinal_nonfinite_order_overlap_and_population_mismatch_fail_closed():
    item = trade(TradeResult.WIN, "one", BASE + 1, "1", "1", "0.1", "0.1")
    snapshot_period = period(0, (item,)); engine = StrategyAggregationEngine()
    result = engine.calculate(scope=scope(), trades=(item, replace(item, id="other")), periods=(snapshot_period,), starting_equity=starting(), as_of_time=BASE + DAY)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert engine.calculate(scope=scope(), trades=(replace(item, immutable=False),), periods=(snapshot_period,), starting_equity=starting(), as_of_time=BASE + DAY).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), trades=(replace(item, net_r=Decimal("NaN")),), periods=(snapshot_period,), starting_equity=starting(), as_of_time=BASE + DAY).error.reason == "NON_FINITE_STRATEGY_AGGREGATION_INPUT"
    second = period(1, (item,))
    assert engine.calculate(scope=scope(), trades=(item,), periods=(second, snapshot_period), starting_equity=starting(), as_of_time=BASE + 2 * DAY).error.reason == "STRATEGY_PERIOD_ORDER_INVALID"
    overlap_first = replace(snapshot_period, period_end=snapshot_period.period_end + 1, finalized_time=snapshot_period.finalized_time + 1)
    assert engine.calculate(scope=scope(), trades=(item,), periods=(overlap_first, second), starting_equity=starting(), as_of_time=BASE + 2 * DAY).error.reason == "STRATEGY_PERIOD_OVERLAP_INVALID"
    wrong = replace(snapshot_period, total_net_r=Decimal("9"))
    assert engine.calculate(scope=scope(), trades=(item,), periods=(wrong,), starting_equity=starting(), as_of_time=BASE + DAY).error.reason == "STRATEGY_PERIOD_TOTAL_MISMATCH"


def test_idempotent_replay_conflict_prevention_and_immutability():
    engine = StrategyAggregationEngine(); item = trade(TradeResult.WIN, "one", BASE + 1, "1", "1", "0.1", "0.1"); periods = (period(0, (item,)),)
    args = dict(scope=scope(), trades=(item,), periods=periods, starting_equity=starting(), as_of_time=BASE + DAY)
    first = engine.calculate(**args)
    replay = engine.calculate(**args, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    changed = replace(item, net_pnl=Decimal("2"))
    changed_period = period(0, (changed,))
    conflict = engine.calculate(scope=scope(), trades=(changed,), periods=(changed_period,), starting_equity=starting(), as_of_time=BASE + DAY, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    with pytest.raises(FrozenInstanceError):
        first.snapshot.strategy_net_pnl = Decimal(9)
