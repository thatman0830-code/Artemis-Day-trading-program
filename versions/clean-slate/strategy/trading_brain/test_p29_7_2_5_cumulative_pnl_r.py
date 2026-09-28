from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_5_cumulative_pnl_r import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def trade(suffix, closed, net_pnl, net_r, result=TradeResult.WIN):
    return replace(accounting(result, suffix, closed), net_pnl=Decimal(net_pnl), net_r=Decimal(net_r))


def test_canonical_cumulative_pnl_and_r_series():
    items = (trade("1", 26, "100", "1"), trade("2", 27, "-50", "-0.5", TradeResult.LOSS), trade("3", 28, "200", "2"), trade("4", 29, "-75", "-0.75", TradeResult.LOSS))
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert [point.cumulative_net_pnl for point in snapshot.points] == list(map(Decimal, ("100", "50", "250", "175")))
    assert [point.cumulative_net_r for point in snapshot.points] == list(map(Decimal, ("1", "0.5", "2.5", "1.75")))
    assert (snapshot.final_cumulative_net_pnl, snapshot.final_cumulative_net_r) == (Decimal("175"), Decimal("1.75"))


def test_empty_population_has_zero_baseline_totals_and_no_points():
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=(), as_of_time=30).snapshot
    assert snapshot.trade_count == 0 and snapshot.points == ()
    assert snapshot.starting_cumulative_net_pnl == snapshot.starting_cumulative_net_r == 0
    assert snapshot.final_cumulative_net_pnl == snapshot.final_cumulative_net_r == 0


def test_single_trade_boundary_starts_from_zero():
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=(trade("one", 26, "7", "0.7"),), as_of_time=30).snapshot
    point = snapshot.points[0]
    assert point.sequence == 1 and point.prior_cumulative_net_pnl == point.prior_cumulative_net_r == 0
    assert (point.cumulative_net_pnl, point.cumulative_net_r) == (Decimal("7"), Decimal("0.7"))


def test_breakeven_zero_values_leave_cumulative_unchanged():
    items = (trade("w", 26, "5", "0.5"), trade("be", 27, "0", "0", TradeResult.BREAKEVEN))
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.points[1].prior_cumulative_net_pnl == snapshot.points[1].cumulative_net_pnl == 5
    assert snapshot.points[1].prior_cumulative_net_r == snapshot.points[1].cumulative_net_r == Decimal("0.5")


def test_point_in_time_exclusion_and_tie_break_ordering():
    items = (trade("b", 27, "2", "0.2"), trade("future", 31, "100", "10"), trade("a", 27, "1", "0.1"), trade("z", 26, "3", "0.3"))
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.source_trade_ids == ("trade-z", "trade-a", "trade-b")
    assert snapshot.future_excluded_trade_ids == ("trade-future",)
    assert snapshot.final_cumulative_net_pnl == 6


def test_exact_decimal_addition_preserves_components():
    items = (trade("a", 26, "0.1", "0.01"), trade("b", 27, "0.2", "0.02"))
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=items, as_of_time=30).snapshot
    assert snapshot.final_cumulative_net_pnl == Decimal("0.3")
    assert snapshot.points[1].net_pnl == Decimal("0.2") and snapshot.points[1].prior_cumulative_net_pnl == Decimal("0.1")


def test_authoritative_outcome_is_not_reclassified_or_mutated():
    item = trade("odd", 26, "5", "0.5", TradeResult.LOSS)
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert snapshot.final_cumulative_net_pnl == 5 and item.trade_result == TradeResult.LOSS


@pytest.mark.parametrize("field", ["scope", "trades"])
def test_missing_inputs_fail_closed(field):
    values = {"scope": scope(), "trades": ()}; values[field] = None
    assert CumulativePnLREngine().calculate(**values, as_of_time=30).error.reason == "REQUIRED_CUMULATIVE_INPUT_MISSING"


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id": "other"}, "CUMULATIVE_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol": "ETH"}, "CUMULATIVE_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe": "5m"}, "CUMULATIVE_TIMEFRAME_MISMATCH"),
    ({"model": SetupModel.REVERSAL_1}, "CUMULATIVE_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction": StructuralRegime.BEARISH}, "CUMULATIVE_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version": "v2"}, "CUMULATIVE_INPUT_VERSION_MISMATCH"),
])
def test_scope_and_version_separation(change, reason):
    item = replace(trade("one", 26, "1", "1"), **change)
    assert CumulativePnLREngine().calculate(scope=scope(), trades=(item,), as_of_time=30).error.reason == reason


def test_duplicate_keys_have_data_integrity_precedence():
    item = trade("same", 26, "1", "1")
    result = CumulativePnLREngine().calculate(scope=scope(), trades=(item, replace(item, id="other", immutable=False)), as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_nonfinal_nonfinite_and_chronologically_invalid_inputs_fail_closed():
    engine = CumulativePnLREngine(); item = trade("one", 26, "1", "1")
    assert engine.calculate(scope=scope(), trades=(replace(item, immutable=False),), as_of_time=30).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), trades=(replace(item, net_r=Decimal("NaN")),), as_of_time=30).error.reason == "NON_FINITE_CUMULATIVE_INPUT"
    assert engine.calculate(scope=scope(), trades=(replace(item, opened_time=27),), as_of_time=30).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    engine = CumulativePnLREngine(); item = trade("one", 26, "1", "1")
    first = engine.calculate(scope=scope(), trades=(item,), as_of_time=30)
    replay = engine.calculate(scope=scope(), trades=(item,), as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(scope=scope(), trades=(item, trade("two", 27, "2", "2")), as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_and_points_are_immutable_and_source_unchanged():
    item = trade("one", 26, "1", "1"); original = item
    snapshot = CumulativePnLREngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert item == original
    with pytest.raises(FrozenInstanceError):
        snapshot.final_cumulative_net_r = Decimal("9")
    with pytest.raises(FrozenInstanceError):
        snapshot.points[0].cumulative_net_r = Decimal("9")
