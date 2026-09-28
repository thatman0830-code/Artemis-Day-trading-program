from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p29_7_2_owner_performance_readiness import (
    OWNER_WIN_RATE_OBJECTIVE_V1, PerformanceObjectiveOutcome,
    PerformanceReadinessEngine,
)
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_2_1_trade_classification_count import TradeClassificationCount
from strategy.trading_brain.p29_7_2_3_expectancy import ExpectancySnapshot


def facts(*, count=200, wins=120, symbol="BTC", expectancy=Decimal("1"), as_of=100):
    losses = count - wins
    trade_ids = tuple(f"t{i}" for i in range(count))
    accounting_ids = tuple(f"a{i}" for i in range(count))
    c = TradeClassificationCount("count", "scope", "strategy", symbol, "5m",
        SetupModel.CONTINUATION, StructuralRegime.BULLISH, "input-v1", "calc-v1",
        as_of, count, wins, losses, 0, trade_ids, accounting_ids, ())
    e = ExpectancySnapshot("expectancy", "scope", "strategy", symbol, "5m",
        SetupModel.CONTINUATION, StructuralRegime.BULLISH, "input-v1", "calc-v1",
        as_of, count, expectancy * count, Decimal("0"), expectancy, Decimal("0"),
        trade_ids, accounting_ids, (), "ROUND_HALF_UP_28_SIGNIFICANT_DIGITS")
    return c, e


def evaluate(**kwargs):
    c, e = facts(**kwargs)
    return PerformanceReadinessEngine().evaluate(
        count=c, expectancy=e, dataset_id="dataset", period_id="oos-period",
        as_of_time=c.as_of_time,
    )


def test_sample_boundary_and_exact_win_rate_objective():
    assert evaluate(count=199, wins=199).snapshot.outcome == PerformanceObjectiveOutcome.INSUFFICIENT_SAMPLE
    exact = evaluate(count=200, wins=120).snapshot
    assert exact.outcome == PerformanceObjectiveOutcome.OBJECTIVE_MET
    assert exact.win_rate == Decimal("0.60") and exact.sample_size == 200
    assert exact.eligible_for_live_pilot_review and not exact.live_trading_authorized
    assert evaluate(count=200, wins=119).snapshot.outcome == PerformanceObjectiveOutcome.OBJECTIVE_NOT_MET
    assert evaluate(count=200, wins=121).snapshot.outcome == PerformanceObjectiveOutcome.OBJECTIVE_MET


def test_positive_expectancy_required_and_market_scopes_are_isolated():
    assert evaluate(expectancy=Decimal("0")).snapshot.reason == "NET_EXPECTANCY_NOT_POSITIVE"
    assert evaluate(expectancy=Decimal("-1")).snapshot.outcome == PerformanceObjectiveOutcome.OBJECTIVE_NOT_MET
    for market in ("BTC", "ES", "NQ"):
        assert evaluate(symbol=market).snapshot.market == market
    assert evaluate(symbol="ETH").snapshot.outcome == PerformanceObjectiveOutcome.INVALID_INPUT


def test_scope_lineage_mismatch_invalid_replay_idempotent_and_immutable():
    count, expectancy = facts()
    engine = PerformanceReadinessEngine()
    first = engine.evaluate(count=count, expectancy=expectancy, dataset_id="d", period_id="p", as_of_time=100)
    second = engine.evaluate(count=count, expectancy=expectancy, dataset_id="d", period_id="p", as_of_time=100,
                             history=first.history)
    assert second.snapshot is first.snapshot and second.history == first.history
    mismatch = engine.evaluate(count=count, expectancy=replace(expectancy, input_version="other"),
                               dataset_id="d", period_id="p", as_of_time=100)
    assert mismatch.snapshot.outcome == PerformanceObjectiveOutcome.INVALID_INPUT
    with pytest.raises(FrozenInstanceError):
        first.snapshot.live_trading_authorized = True


def test_objective_is_analytics_only_and_has_no_trade_authority_fields():
    forbidden = {"arm", "reject_trade", "size", "order", "fill", "open", "close", "authorize"}
    assert forbidden.isdisjoint(PerformanceReadinessEngine.__dict__)
    assert OWNER_WIN_RATE_OBJECTIVE_V1.target_win_rate == Decimal("0.60")
