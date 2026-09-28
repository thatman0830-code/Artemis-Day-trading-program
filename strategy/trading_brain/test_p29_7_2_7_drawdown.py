from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_5_cumulative_pnl_r import CumulativePnLREngine
from strategy.trading_brain.p29_7_2_6_equity_curve import EquityCurveEngine
from strategy.trading_brain.p29_7_2_7_drawdown import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope():
    return TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1")


def trade(suffix, closed, pnl, result=TradeResult.WIN):
    return replace(accounting(result, suffix, closed), net_pnl=Decimal(pnl), net_r=Decimal(pnl) / Decimal("100"))


def curve(pnls=(), starting="1000", as_of=30):
    trades = tuple(trade(str(index), 25 + index, pnl, TradeResult.LOSS if Decimal(pnl) < 0 else TradeResult.BREAKEVEN if Decimal(pnl) == 0 else TradeResult.WIN) for index, pnl in enumerate(pnls, start=1))
    cumulative = CumulativePnLREngine().calculate(scope=scope(), trades=trades, as_of_time=as_of).snapshot
    return EquityCurveEngine().calculate(cumulative=cumulative, starting_equity=Decimal(starting), as_of_time=as_of).snapshot


def test_running_peaks_absolute_percentage_and_maximum_drawdown():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(("500", "-200", "700", "-300"), starting="50000"), as_of_time=30).snapshot
    assert [point.peak_equity for point in snapshot.points] == list(map(Decimal, ("50500", "50500", "51000", "51000")))
    assert [point.drawdown_abs for point in snapshot.points] == list(map(Decimal, ("0", "200", "0", "300")))
    assert snapshot.maximum_drawdown_abs == Decimal("300")
    assert snapshot.maximum_drawdown_pct == Decimal("300") / Decimal("51000") * Decimal("100")


def test_empty_curve_uses_explicit_starting_equity_baseline():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(), as_of_time=30).snapshot
    assert snapshot.points == () and snapshot.current_peak_equity == Decimal("1000")
    assert snapshot.current_drawdown_abs == snapshot.maximum_drawdown_abs == 0
    assert snapshot.current_drawdown_pct == Decimal("0") and snapshot.maximum_drawdown_pct is None


def test_flat_and_breakeven_points_remain_at_zero_drawdown():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(("0", "0")), as_of_time=30).snapshot
    assert all(point.peak_equity == 1000 and point.drawdown_abs == point.drawdown_pct == 0 for point in snapshot.points)


def test_starting_baseline_prevents_first_loss_from_becoming_peak():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(("-100",)), as_of_time=30).snapshot
    point = snapshot.points[0]
    assert point.peak_equity == 1000 and point.drawdown_abs == 100 and point.drawdown_pct == 10


def test_new_peaks_and_equality_to_peak_have_zero_drawdown():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(("100", "-50", "50", "25")), as_of_time=30).snapshot
    assert [point.drawdown_abs for point in snapshot.points] == list(map(Decimal, ("0", "50", "0", "0")))
    assert snapshot.current_peak_equity == Decimal("1125")


def test_multiple_troughs_and_full_recovery_preserve_historical_maximum():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(("100", "-40", "-30", "70")), as_of_time=30).snapshot
    assert [point.drawdown_abs for point in snapshot.points] == list(map(Decimal, ("0", "40", "70", "0")))
    assert snapshot.current_drawdown_abs == 0 and snapshot.maximum_drawdown_abs == 70


def test_unrecovered_decline_remains_current_drawdown_without_episode_invention():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(("100", "-20", "-30")), as_of_time=30).snapshot
    assert snapshot.current_drawdown_abs == snapshot.maximum_drawdown_abs == 50


def test_tied_maxima_preserve_all_source_point_identities_in_order():
    source = curve(("100", "-50", "50", "-50"))
    snapshot = DrawdownEngine().calculate(equity_curve=source, as_of_time=30).snapshot
    assert snapshot.maximum_drawdown_abs_point_ids == (source.points[1].id, source.points[3].id)
    assert snapshot.maximum_drawdown_pct_point_ids == (source.points[1].id, source.points[3].id)


@pytest.mark.parametrize("starting,pnls,expected_abs", [("0", ("-5",), Decimal("5")), ("-10", ("-5",), Decimal("5"))])
def test_nonpositive_peak_retains_absolute_drawdown_and_null_percentage(starting, pnls, expected_abs):
    snapshot = DrawdownEngine().calculate(equity_curve=curve(pnls, starting=starting), as_of_time=30).snapshot
    assert snapshot.maximum_drawdown_abs == expected_abs
    assert snapshot.points[0].drawdown_pct is None and snapshot.maximum_drawdown_pct is None


def test_negative_baseline_can_reach_zero_peak_without_inventing_percentage():
    snapshot = DrawdownEngine().calculate(equity_curve=curve(("10", "-1"), starting="-10"), as_of_time=30).snapshot
    assert [point.peak_equity for point in snapshot.points] == [Decimal("0"), Decimal("0")]
    assert [point.drawdown_pct for point in snapshot.points] == [None, None]


def test_point_in_time_mismatch_rejects_future_or_stale_curve():
    assert DrawdownEngine().calculate(equity_curve=curve(as_of=31), as_of_time=30).error.reason == "EQUITY_POINT_IN_TIME_MISMATCH"
    assert DrawdownEngine().calculate(equity_curve=curve(as_of=29), as_of_time=30).error.reason == "EQUITY_POINT_IN_TIME_MISMATCH"


def test_missing_and_duplicate_points_fail_closed_with_duplicate_precedence():
    source = curve(("1", "2")); engine = DrawdownEngine()
    assert engine.calculate(equity_curve=replace(source, trade_count=3), as_of_time=30).error.reason == "EQUITY_POINT_MISSING"
    duplicate = replace(source.points[1], id=source.points[0].id)
    result = engine.calculate(equity_curve=replace(source, points=(source.points[0], duplicate)), as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_noncontiguous_misordered_future_and_nonfinite_points_fail_closed():
    source = curve(("1", "2")); engine = DrawdownEngine()
    bad_sequence = replace(source.points[1], sequence=3)
    assert engine.calculate(equity_curve=replace(source, points=(source.points[0], bad_sequence)), as_of_time=30).error.reason == "EQUITY_POINT_NONCONTIGUOUS"
    reversed_points = tuple(reversed(source.points))
    assert engine.calculate(equity_curve=replace(source, points=reversed_points), as_of_time=30).error.reason == "EQUITY_ORDER_INVALID"
    assert engine.calculate(equity_curve=replace(source, points=(replace(source.points[0], time=31), source.points[1])), as_of_time=30).error.reason == "EQUITY_ORDER_INVALID"
    nonfinite = replace(source.points[0], equity=Decimal("NaN"))
    assert engine.calculate(equity_curve=replace(source, points=(nonfinite, source.points[1])), as_of_time=30).error.reason == "NON_FINITE_EQUITY_VALUE"


def test_scope_and_versions_are_preserved_without_combination():
    source = replace(curve(), strategy_id="other", symbol="ETH", timeframe="5m", setup_model=SetupModel.REVERSAL_1, direction=StructuralRegime.BEARISH, input_version="v2", calculation_version="analytics-v2")
    snapshot = DrawdownEngine().calculate(equity_curve=source, as_of_time=30).snapshot
    assert (snapshot.strategy_id, snapshot.symbol, snapshot.timeframe, snapshot.setup_model, snapshot.direction, snapshot.input_version, snapshot.calculation_version) == ("other", "ETH", "5m", SetupModel.REVERSAL_1, StructuralRegime.BEARISH, "v2", "analytics-v2")


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    source = curve(("1",)); engine = DrawdownEngine()
    first = engine.calculate(equity_curve=source, as_of_time=30)
    replay = engine.calculate(equity_curve=source, as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    alternative = replace(source, id="alternative", starting_equity=Decimal("999"), points=tuple(replace(point, starting_equity=Decimal("999"), equity=point.equity - 1) for point in source.points), ending_equity=source.ending_equity - 1)
    conflict = engine.calculate(equity_curve=alternative, as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_and_points_are_immutable_and_curve_unchanged():
    source = curve(("-1",)); original = source
    snapshot = DrawdownEngine().calculate(equity_curve=source, as_of_time=30).snapshot
    assert source == original
    with pytest.raises(FrozenInstanceError):
        snapshot.maximum_drawdown_abs = Decimal("9")
    with pytest.raises(FrozenInstanceError):
        snapshot.points[0].drawdown_abs = Decimal("9")
