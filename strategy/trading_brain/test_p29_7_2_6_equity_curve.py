from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import TradeCountScope
from strategy.trading_brain.p29_7_2_5_cumulative_pnl_r import CumulativePnLREngine
from strategy.trading_brain.p29_7_2_6_equity_curve import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def trade(suffix, closed, net_pnl, net_r, result=TradeResult.WIN):
    return replace(accounting(result, suffix, closed), net_pnl=Decimal(net_pnl), net_r=Decimal(net_r))


def cumulative(items=(), as_of=30, scoped=None):
    return CumulativePnLREngine().calculate(scope=scoped or scope(), trades=tuple(items), as_of_time=as_of).snapshot


def test_positive_and_negative_sequence_uses_exact_cumulative_values():
    source = cumulative((trade("1", 26, "100", "1"), trade("2", 27, "-150", "-1.5", TradeResult.LOSS), trade("3", 28, "75", "0.75")))
    snapshot = EquityCurveEngine().calculate(cumulative=source, starting_equity=Decimal("1000"), as_of_time=30).snapshot
    assert [point.equity for point in snapshot.points] == list(map(Decimal, ("1100", "950", "1025")))
    assert snapshot.ending_equity == Decimal("1025")


def test_empty_series_preserves_explicit_starting_equity():
    snapshot = EquityCurveEngine().calculate(cumulative=cumulative(), starting_equity=Decimal("1000"), as_of_time=30).snapshot
    assert snapshot.trade_count == 0 and snapshot.points == () and snapshot.ending_equity == Decimal("1000")


@pytest.mark.parametrize("starting", [Decimal("0"), Decimal("-10")])
def test_zero_and_negative_starting_equity_follow_exact_formula(starting):
    source = cumulative((trade("one", 26, "5", "0.5"),))
    snapshot = EquityCurveEngine().calculate(cumulative=source, starting_equity=starting, as_of_time=30).snapshot
    assert snapshot.ending_equity == starting + Decimal("5")


def test_breakeven_point_and_equity_tie_remain_unchanged():
    source = cumulative((trade("w", 26, "5", "0.5"), trade("be", 27, "0", "0", TradeResult.BREAKEVEN)))
    snapshot = EquityCurveEngine().calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30).snapshot
    assert snapshot.points[0].equity == snapshot.points[1].equity == Decimal("105")


def test_source_order_and_point_identities_are_preserved():
    source = cumulative((trade("b", 27, "2", "0.2"), trade("a", 27, "1", "0.1"), trade("z", 26, "3", "0.3")))
    snapshot = EquityCurveEngine().calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30).snapshot
    assert [point.trade_id for point in snapshot.points] == ["trade-z", "trade-a", "trade-b"]
    assert snapshot.source_cumulative_point_ids == tuple(point.id for point in source.points)


def test_future_exclusion_is_preserved_without_raw_trade_reconstruction():
    source = cumulative((trade("past", 29, "2", "0.2"), trade("future", 31, "100", "10")), as_of=30)
    snapshot = EquityCurveEngine().calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30).snapshot
    assert snapshot.ending_equity == 102 and snapshot.future_excluded_trade_ids == ("trade-future",)


@pytest.mark.parametrize("field", ["cumulative", "starting_equity"])
def test_missing_required_input_fails_closed(field):
    values = {"cumulative": cumulative(), "starting_equity": Decimal("100")}; values[field] = None
    assert EquityCurveEngine().calculate(**values, as_of_time=30).error.reason == "REQUIRED_EQUITY_INPUT_MISSING"


@pytest.mark.parametrize("starting", [Decimal("NaN"), Decimal("Infinity")])
def test_nonfinite_starting_equity_fails_closed(starting):
    assert EquityCurveEngine().calculate(cumulative=cumulative(), starting_equity=starting, as_of_time=30).error.reason == "STARTING_EQUITY_INVALID"


def test_point_in_time_mismatch_rejects_future_or_stale_source_snapshot():
    source = cumulative(as_of=31)
    assert EquityCurveEngine().calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30).error.reason == "CUMULATIVE_POINT_IN_TIME_MISMATCH"
    assert EquityCurveEngine().calculate(cumulative=cumulative(as_of=29), starting_equity=Decimal("100"), as_of_time=30).error.reason == "CUMULATIVE_POINT_IN_TIME_MISMATCH"


@pytest.mark.parametrize("change", [
    {"strategy_id": "other"}, {"symbol": "ETH"}, {"timeframe": "5m"},
    {"setup_model": SetupModel.REVERSAL_1}, {"direction": StructuralRegime.BEARISH},
    {"input_version": "v2"}, {"calculation_version": "analytics-v2"},
])
def test_scope_and_version_are_preserved_without_cross_scope_combination(change):
    source = replace(cumulative(), **change)
    snapshot = EquityCurveEngine().calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30).snapshot
    for key, value in change.items():
        assert getattr(snapshot, key) == value


def test_missing_noncontiguous_duplicate_and_misordered_points_fail_closed():
    source = cumulative((trade("a", 26, "1", "0.1"), trade("b", 27, "2", "0.2")))
    engine = EquityCurveEngine()
    assert engine.calculate(cumulative=replace(source, trade_count=3), starting_equity=Decimal("100"), as_of_time=30).error.reason == "CUMULATIVE_POINT_MISSING"
    duplicate = replace(source.points[1], id=source.points[0].id)
    duplicate_result = engine.calculate(cumulative=replace(source, points=(source.points[0], duplicate)), starting_equity=Decimal("100"), as_of_time=30)
    assert duplicate_result.error.reason == "DUPLICATE_CUMULATIVE_POINT"
    assert duplicate_result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert engine.calculate(cumulative=replace(source, points=tuple(reversed(source.points)), source_trade_ids=tuple(reversed(source.source_trade_ids)), source_accounting_ids=tuple(reversed(source.source_accounting_ids))), starting_equity=Decimal("100"), as_of_time=30).error.reason == "CUMULATIVE_ORDER_INVALID"
    bad_sequence = replace(source.points[1], sequence=3)
    assert engine.calculate(cumulative=replace(source, points=(source.points[0], bad_sequence)), starting_equity=Decimal("100"), as_of_time=30).error.reason == "CUMULATIVE_POINT_NONCONTIGUOUS"


def test_nonfinite_and_invalid_cumulative_transition_fail_closed():
    source = cumulative((trade("one", 26, "1", "0.1"),)); engine = EquityCurveEngine()
    nonfinite = replace(source.points[0], cumulative_net_pnl=Decimal("NaN"))
    assert engine.calculate(cumulative=replace(source, points=(nonfinite,)), starting_equity=Decimal("100"), as_of_time=30).error.reason == "NON_FINITE_CUMULATIVE_VALUE"
    invalid = replace(source.points[0], cumulative_net_pnl=Decimal("2"))
    assert engine.calculate(cumulative=replace(source, points=(invalid,), final_cumulative_net_pnl=Decimal("2")), starting_equity=Decimal("100"), as_of_time=30).error.reason == "CUMULATIVE_TRANSITION_INVALID"


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    source = cumulative((trade("one", 26, "1", "0.1"),)); engine = EquityCurveEngine()
    first = engine.calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30)
    replay = engine.calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(cumulative=source, starting_equity=Decimal("200"), as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_equity_snapshot_and_points_are_immutable_and_source_unchanged():
    source = cumulative((trade("one", 26, "1", "0.1"),)); original = source
    snapshot = EquityCurveEngine().calculate(cumulative=source, starting_equity=Decimal("100"), as_of_time=30).snapshot
    assert source == original
    with pytest.raises(FrozenInstanceError):
        snapshot.ending_equity = Decimal("9")
    with pytest.raises(FrozenInstanceError):
        snapshot.points[0].equity = Decimal("9")
