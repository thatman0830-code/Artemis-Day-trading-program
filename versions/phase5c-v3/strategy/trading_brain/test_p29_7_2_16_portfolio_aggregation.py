from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodDefinition, PeriodStatisticsEngine, PeriodType
from strategy.trading_brain.p29_7_2_15_strategy_aggregation import StrategyAggregationEngine, StrategyAggregationScope, StrategyStartingEquity
from strategy.trading_brain.p29_7_2_16_portfolio_aggregation import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


DAY = 86400
BASE = int(datetime(2026, 8, 10, tzinfo=ZoneInfo("UTC")).timestamp())
AS_OF = BASE + 4 * DAY


def definition(included=("A", "B"), excluded=(), **changes):
    return replace(PortfolioDefinition("portfolio", "v1", included, excluded, BASE - 1, PeriodType.DAILY, "UTC", "source-v1", "analytics-v1", "portfolio-calc-v1", "history-v1"), **changes)


def starting(value="100", **changes):
    return replace(PortfolioStartingEquity("portfolio-start", "portfolio", "v1", Decimal(value), "source-v1", "history-v1"), **changes)


def trade(strategy_id, result, suffix, closed, pnl, net_r):
    return replace(accounting(result, suffix, closed), strategy_id=strategy_id, gross_pnl=Decimal(pnl), net_pnl=Decimal(pnl), gross_r=Decimal(net_r), net_r=Decimal(net_r))


def strategy(strategy_id, trades=(), period_indices=(), *, as_of=AS_OF, timezone_name="UTC"):
    scope_id = f"scope-{strategy_id}"
    upstream_scope = TradeCountScope(scope_id, strategy_id, "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1")
    periods = []
    for index in period_indices:
        begin = BASE + index * DAY
        periods.append(PeriodStatisticsEngine().calculate(
            scope=upstream_scope,
            period=PeriodDefinition(PeriodType.DAILY, timezone_name, begin, begin + DAY, "source-v1", "history-v1"),
            trades=trades, as_of_time=begin + DAY,
        ).snapshot)
    aggregation_scope = StrategyAggregationScope(scope_id, strategy_id, "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "source-v1", "analytics-v1", "history-v1", PeriodType.DAILY, timezone_name)
    return StrategyAggregationEngine().calculate(
        scope=aggregation_scope, trades=trades, periods=tuple(periods),
        starting_equity=StrategyStartingEquity(f"start-{strategy_id}", strategy_id, Decimal("1000"), "source-v1", "history-v1"),
        as_of_time=as_of,
    ).snapshot


def calculate(strategies=(), *, portfolio_definition=None, as_of=AS_OF, history=PortfolioAggregationHistory(), **changes):
    values = dict(definition=portfolio_definition or definition(), strategies=strategies, starting_equity=starting(), as_of_time=as_of, history=history)
    values.update(changes)
    return PortfolioAggregationEngine().calculate(**values)


def test_normal_multi_strategy_conservation_unweighted_sums_and_merged_equity():
    a_trade = trade("A", TradeResult.WIN, "a", BASE + 2, "10", "1")
    b_trade = trade("B", TradeResult.LOSS, "b", BASE + 1, "-4", "-0.4")
    a = strategy("A", (a_trade,), (0,)); b = strategy("B", (b_trade,), (0,))
    snapshot = calculate((b, a)).snapshot
    assert snapshot.effective_strategy_ids == ("A", "B")
    assert (snapshot.trade_count, snapshot.win_count, snapshot.loss_count, snapshot.breakeven_count) == (2, 1, 1, 0)
    assert snapshot.portfolio_net_pnl == snapshot.portfolio_gross_pnl == Decimal("6")
    assert snapshot.portfolio_net_r == snapshot.portfolio_gross_r == Decimal("0.6")
    assert snapshot.win_rate == Decimal("0.5") and snapshot.expectancy_net_pnl == 3
    assert snapshot.profit_factor == Decimal("2.5")
    assert [point.trade_id for point in snapshot.equity_points] == (list((b_trade.trade_id, a_trade.trade_id)))
    assert [point.equity for point in snapshot.equity_points] == [Decimal("96"), Decimal("106")]
    assert sum(item.net_pnl for item in snapshot.strategy_contributions) == snapshot.portfolio_net_pnl


def test_single_strategy_preserves_strategy_totals_without_special_weighting():
    item = trade("A", TradeResult.WIN, "a", BASE + 1, "5", "0.5")
    source = strategy("A", (item,), (0,))
    snapshot = calculate((source,), portfolio_definition=definition(("A",))).snapshot
    assert snapshot.trade_count == 1 and snapshot.portfolio_net_pnl == 5 and snapshot.portfolio_net_r == Decimal("0.5")
    assert snapshot.strategy_contributions[0].strategy_snapshot_id == source.id


def test_empty_portfolio_has_zero_totals_and_null_observation_statistics():
    snapshot = calculate((), portfolio_definition=definition(())).snapshot
    assert snapshot.trade_count == snapshot.win_count == snapshot.loss_count == snapshot.breakeven_count == 0
    assert snapshot.portfolio_gross_pnl == snapshot.portfolio_net_pnl == snapshot.portfolio_gross_r == snapshot.portfolio_net_r == 0
    assert snapshot.win_rate is snapshot.expectancy_net_pnl is snapshot.profit_factor is None
    assert snapshot.ending_equity == snapshot.starting_equity == 100 and snapshot.equity_points == ()


def test_exclusion_wins_and_excluded_strategy_cannot_contribute():
    a = strategy("A", (trade("A", TradeResult.WIN, "a", BASE + 1, "1", "0.1"),), ())
    b = strategy("B", (trade("B", TradeResult.WIN, "b", BASE + 1, "100", "10"),), ())
    snapshot = calculate((a, b), portfolio_definition=definition(("A", "B"), ("B",))).snapshot
    assert snapshot.effective_strategy_ids == ("A",)
    assert snapshot.portfolio_net_pnl == 1 and snapshot.source_strategy_snapshot_ids == (a.id,)


def test_aligned_periods_sum_exact_strategy_period_net_r_and_pnl():
    a_item = trade("A", TradeResult.WIN, "a", BASE + 1, "3", "0.3")
    b_item = trade("B", TradeResult.LOSS, "b", BASE + 2, "-1", "-0.1")
    snapshot = calculate((strategy("A", (a_item,), (0,)), strategy("B", (b_item,), (0,)))).snapshot
    period = snapshot.period_observations[0]
    assert period.net_pnl == 2 and period.net_r == Decimal("0.2") and period.trade_count == 2
    assert period.contributing_strategy_ids == ("A", "B")
    assert len(period.source_strategy_period_observation_ids) == 2


def test_missing_period_is_not_forward_filled_and_only_intersection_is_emitted():
    a = strategy("A", (), (0, 1)); b = strategy("B", (), (0,))
    snapshot = calculate((a, b)).snapshot
    assert snapshot.aligned_period_count == 1
    assert snapshot.missing_period_ends == (BASE + 2 * DAY,)
    assert snapshot.period_observations[0].period_end == BASE + DAY


def test_real_zero_return_period_is_retained_not_treated_as_missing():
    snapshot = calculate((strategy("A", (), (0,)), strategy("B", (), (0,)))).snapshot
    assert snapshot.aligned_period_count == 1 and snapshot.period_observations[0].net_r == 0
    assert snapshot.zero_return_period_ids == (snapshot.period_observations[0].id,)


def test_positive_negative_zero_and_infinity_profit_factor_boundaries():
    win = strategy("A", (trade("A", TradeResult.WIN, "w", BASE + 1, "2", "0.2"),), ())
    assert calculate((win,), portfolio_definition=definition(("A",))).snapshot.profit_factor == Decimal("Infinity")
    loss = strategy("A", (trade("A", TradeResult.LOSS, "l", BASE + 1, "-2", "-0.2"),), ())
    assert calculate((loss,), portfolio_definition=definition(("A",))).snapshot.profit_factor == 0
    zero = strategy("A", (trade("A", TradeResult.BREAKEVEN, "z", BASE + 1, "0", "0"),), ())
    assert calculate((zero,), portfolio_definition=definition(("A",))).snapshot.profit_factor is None


def test_merged_chronology_and_tied_maximum_drawdown_identities():
    a_trades = (trade("A", TradeResult.LOSS, "a1", BASE + 1, "-10", "-1"), trade("A", TradeResult.LOSS, "a2", BASE + 3, "-10", "-1"))
    b_trade = trade("B", TradeResult.WIN, "b", BASE + 2, "10", "1")
    snapshot = calculate((strategy("A", a_trades), strategy("B", (b_trade,)))).snapshot
    assert [point.drawdown_abs for point in snapshot.equity_points] == [Decimal("10"), Decimal("0"), Decimal("10")]
    assert snapshot.maximum_drawdown_abs == 10
    assert snapshot.maximum_drawdown_equity_point_ids == (snapshot.equity_points[0].id, snapshot.equity_points[2].id)


def test_same_timestamp_uses_trade_id_tie_break_without_deduplication():
    a_trade = trade("A", TradeResult.WIN, "b", BASE + 1, "1", "0.1")
    b_trade = trade("B", TradeResult.WIN, "a", BASE + 1, "1", "0.1")
    snapshot = calculate((strategy("A", (a_trade,)), strategy("B", (b_trade,)))).snapshot
    assert snapshot.source_trade_ids == ("trade-a", "trade-b") and snapshot.trade_count == 2


def test_starting_equity_is_mandatory_with_canonical_error():
    result = calculate((), portfolio_definition=definition(()), starting_equity=None)
    assert result.error.code == PortfolioAggregationErrorCode.PORTFOLIO_STARTING_EQUITY_MISSING


def test_point_in_time_finality_and_stale_strategy_fail_closed():
    source = strategy("A", (), (), as_of=AS_OF)
    result = calculate((source,), portfolio_definition=definition(("A",)), as_of=AS_OF - 1)
    assert result.error.reason == "STRATEGY_POPULATION_NON_FINAL_OR_STALE"
    future_period = replace(strategy("A", (), (0,)).period_observations[0], period_end=AS_OF + 1)
    invalid = replace(strategy("A", (), (0,)), period_observations=(future_period,))
    assert calculate((invalid,), portfolio_definition=definition(("A",))).error.reason == "STRATEGY_PERIOD_NON_FINAL_OR_FUTURE"


def test_membership_scope_timezone_period_and_versions_are_isolated():
    source = strategy("A", (), ())
    assert calculate((), portfolio_definition=definition(("A",))).error.reason == "INCLUDED_STRATEGY_POPULATION_MISSING"
    assert calculate((source,), portfolio_definition=definition(("A",), account_timezone="America/Phoenix")).error.reason == "STRATEGY_POPULATION_SCOPE_OR_VERSION_MISMATCH"
    assert calculate((source,), portfolio_definition=definition(("A",), period_type=PeriodType.MONTHLY)).error.reason == "STRATEGY_POPULATION_SCOPE_OR_VERSION_MISMATCH"
    assert calculate((source,), portfolio_definition=definition(("A",), strategy_calculation_version="v2")).error.reason == "STRATEGY_POPULATION_SCOPE_OR_VERSION_MISMATCH"


def test_duplicate_trade_strategy_and_membership_keys_fail_closed():
    a = strategy("A", (trade("A", TradeResult.WIN, "same", BASE + 1, "1", "0.1"),))
    b = strategy("B", (trade("B", TradeResult.WIN, "same", BASE + 2, "1", "0.1"),))
    result = calculate((a, b))
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    result = calculate((a, replace(a, id="other")), portfolio_definition=definition(("A",)))
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert calculate((), portfolio_definition=definition(("A", "A"))).error.reason == "PORTFOLIO_MEMBERSHIP_DUPLICATE"


def test_nonfinite_incorrect_order_and_invalid_conservation_fail_closed():
    source = strategy("A", (trade("A", TradeResult.WIN, "a", BASE + 1, "1", "0.1"), trade("A", TradeResult.LOSS, "b", BASE + 2, "-1", "-0.1")))
    assert calculate((replace(source, strategy_net_pnl=Decimal("NaN")),), portfolio_definition=definition(("A",))).error.reason == "NON_FINITE_STRATEGY_POPULATION"
    assert calculate((replace(source, equity_points=tuple(reversed(source.equity_points))),), portfolio_definition=definition(("A",))).error.reason in ("STRATEGY_POPULATION_LINEAGE_MISMATCH", "STRATEGY_EQUITY_ORDER_INVALID")
    assert calculate((replace(source, win_count=9),), portfolio_definition=definition(("A",))).error.reason == "STRATEGY_POPULATION_COUNT_INVALID"


def test_idempotent_replay_conflict_prevention_and_upstream_immutability():
    engine = PortfolioAggregationEngine(); source = strategy("A", (trade("A", TradeResult.WIN, "a", BASE + 1, "1", "0.1"),))
    args = dict(definition=definition(("A",)), strategies=(source,), starting_equity=starting(), as_of_time=AS_OF)
    first = engine.calculate(**args)
    replay = engine.calculate(**args, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    changed = replace(source, strategy_net_pnl=Decimal("2"), equity_points=(replace(source.equity_points[0], net_pnl=Decimal("2"), equity=Decimal("1002")),))
    conflict = engine.calculate(definition=definition(("A",)), strategies=(changed,), starting_equity=starting(), as_of_time=AS_OF, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    with pytest.raises(FrozenInstanceError):
        first.snapshot.portfolio_net_pnl = Decimal(9)
