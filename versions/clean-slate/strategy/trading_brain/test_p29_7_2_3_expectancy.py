from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_3_expectancy import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def trade(suffix, closed, net_pnl, net_r, result=TradeResult.WIN):
    return replace(accounting(result, suffix, closed), net_pnl=Decimal(net_pnl), net_r=Decimal(net_r))


def test_exact_expectancy_uses_all_finalized_trades_and_trade_count_denominator():
    items = (trade("1", 26, "10", "1"), trade("2", 27, "-4", "-0.4", TradeResult.LOSS), trade("3", 28, "0", "0", TradeResult.BREAKEVEN))
    snapshot = ExpectancyEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.trade_count == 3
    assert (snapshot.total_net_pnl, snapshot.total_net_r) == (Decimal("6"), Decimal("0.6"))
    assert (snapshot.expectancy_net_pnl, snapshot.expectancy_net_r) == (Decimal("2"), Decimal("0.2"))


def test_empty_population_is_null_not_zero():
    snapshot = ExpectancyEngine().calculate(scope=scope(), trades=(), as_of_time=30).snapshot
    assert snapshot.trade_count == 0 and snapshot.total_net_pnl == snapshot.total_net_r == 0
    assert snapshot.expectancy_net_pnl is None and snapshot.expectancy_net_r is None


def test_one_trade_boundary_equals_authoritative_values():
    item = trade("one", 26, "7.25", "2")
    snapshot = ExpectancyEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert snapshot.expectancy_net_pnl == item.net_pnl and snapshot.expectancy_net_r == item.net_r


def test_point_in_time_exclusion_and_canonical_ordering():
    items = (trade("b", 27, "2", "2"), trade("future", 31, "100", "100"), trade("a", 27, "1", "1"), trade("z", 26, "3", "3"))
    snapshot = ExpectancyEngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.source_trade_ids == ("trade-z", "trade-a", "trade-b")
    assert snapshot.future_excluded_trade_ids == ("trade-future",)
    assert snapshot.expectancy_net_pnl == Decimal("2")


def test_authoritative_result_is_not_reclassified_from_pnl():
    item = trade("odd", 26, "5", "0.5", TradeResult.LOSS)
    snapshot = ExpectancyEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert snapshot.expectancy_net_pnl == Decimal("5")


@pytest.mark.parametrize("field", ["scope", "trades"])
def test_missing_input_fails_closed(field):
    values = {"scope": scope(), "trades": ()}; values[field] = None
    assert ExpectancyEngine().calculate(**values, as_of_time=30).error.reason == "REQUIRED_EXPECTANCY_INPUT_MISSING"


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id": "other"}, "EXPECTANCY_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol": "ETH"}, "EXPECTANCY_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe": "5m"}, "EXPECTANCY_TIMEFRAME_MISMATCH"),
    ({"model": SetupModel.REVERSAL_1}, "EXPECTANCY_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction": StructuralRegime.BEARISH}, "EXPECTANCY_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version": "v2"}, "EXPECTANCY_INPUT_VERSION_MISMATCH"),
])
def test_scope_and_version_separation(change, reason):
    item = replace(trade("one", 26, "1", "1"), **change)
    assert ExpectancyEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).error.reason == reason


def test_duplicate_trade_key_fails_with_data_integrity_error():
    item = trade("same", 26, "1", "1")
    result = ExpectancyEngine().calculate(scope=scope(), trades=(item, replace(item, id="other")), as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_incomplete_nonfinite_and_invalid_chronology_fail_closed():
    engine = ExpectancyEngine(); item = trade("one", 26, "1", "1")
    assert engine.calculate(scope=scope(), trades=(replace(item, immutable=False),), as_of_time=30).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), trades=(replace(item, net_r=Decimal("Infinity")),), as_of_time=30).error.reason == "NON_FINITE_EXPECTANCY_INPUT"
    assert engine.calculate(scope=scope(), trades=(replace(item, accounting_time=25),), as_of_time=30).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    engine = ExpectancyEngine(); item = trade("one", 26, "1", "1")
    first = engine.calculate(scope=scope(), trades=(item,), as_of_time=30)
    replay = engine.calculate(scope=scope(), trades=(item,), as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(scope=scope(), trades=(item, trade("two", 27, "2", "2")), as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_is_immutable_and_source_is_unchanged():
    item = trade("one", 26, "1", "1"); original = item
    snapshot = ExpectancyEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert item == original
    with pytest.raises(FrozenInstanceError):
        snapshot.expectancy_net_r = Decimal("9")
