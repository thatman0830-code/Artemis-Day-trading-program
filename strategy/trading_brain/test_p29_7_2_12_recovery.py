from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_7_drawdown import DrawdownEngine
from strategy.trading_brain.p29_7_2_12_recovery import *
from strategy.trading_brain.test_p29_7_2_7_drawdown import curve


def scope(**changes):
    return replace(RecoveryScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def sources(pnls=(), *, starting="100", as_of=40):
    equity_curve = curve(pnls, starting=starting, as_of=as_of)
    drawdown = DrawdownEngine().calculate(equity_curve=equity_curve, as_of_time=as_of).snapshot
    baseline = StartingEquityObservation("starting-equity", 0, Decimal(starting), equity_curve.id)
    return drawdown, baseline


def calculate(pnls=(), *, starting="100", as_of=40, history=RecoveryHistory(), **changes):
    drawdown, baseline = sources(pnls, starting=starting, as_of=as_of)
    values = dict(scope=scope(), drawdown=drawdown, starting_equity=baseline, as_of_time=as_of, history=history)
    values.update(changes)
    return RecoveryStatisticsEngine().calculate(**values)


def test_empty_and_flat_curves_have_no_artificial_episode():
    empty = calculate().snapshot
    assert empty.total_drawdowns == empty.recovered_drawdowns == empty.unrecovered_drawdowns == 0
    assert empty.recovery_ratio is empty.average_recovery_duration is empty.maximum_recovery_duration is None
    assert empty.current_recovery_status == CurrentRecoveryStatus.NO_ACTIVE_DRAWDOWN
    flat = calculate(("0", "0")).snapshot
    assert flat.episodes == () and flat.current_recovery_status == CurrentRecoveryStatus.NO_ACTIVE_DRAWDOWN


def test_one_complete_recovery_uses_strict_start_first_trough_and_equality_close():
    snapshot = calculate(("-10", "-10", "20")).snapshot
    episode = snapshot.episodes[0]
    assert (snapshot.total_drawdowns, snapshot.recovered_drawdowns, snapshot.unrecovered_drawdowns) == (1, 1, 0)
    assert episode.status == RecoveryEpisodeStatus.RECOVERED and episode.recovered
    assert (episode.peak_equity, episode.trough_equity, episode.recovery_equity) == tuple(map(Decimal, ("100", "80", "100")))
    assert episode.drawdown_start_time == 26 and episode.trough_time == 27 and episode.recovery_time == 28
    assert episode.recovery_duration == 2 and episode.recovery_depth == Decimal("20") and episode.recovery_depth_pct == Decimal("20")
    assert snapshot.recovery_ratio == 1 and snapshot.average_recovery_duration == 2 and snapshot.maximum_recovery_duration == 2


def test_unrecovered_episode_has_null_terminal_facts_and_current_elapsed_time():
    snapshot = calculate(("-10", "-5"), as_of=40).snapshot
    episode = snapshot.episodes[0]
    assert episode.status == RecoveryEpisodeStatus.UNRECOVERED and not episode.recovered
    assert episode.recovery_equity is episode.recovery_time is episode.recovery_duration is episode.finalized_time is None
    assert snapshot.current_recovery_status == CurrentRecoveryStatus.UNDERWATER
    assert snapshot.current_unrecovered_duration == 40 - 26
    assert snapshot.average_recovery_duration is snapshot.maximum_recovery_duration is None


def test_multiple_nonoverlapping_episodes_and_new_high_peak_reuse():
    snapshot = calculate(("-10", "20", "-15", "15")).snapshot
    assert snapshot.total_drawdowns == snapshot.recovered_drawdowns == 2
    assert [item.peak_equity for item in snapshot.episodes] == [Decimal("100"), Decimal("110")]
    assert [item.recovery_equity for item in snapshot.episodes] == [Decimal("110"), Decimal("110")]
    assert snapshot.current_recovery_status == CurrentRecoveryStatus.RECOVERED


def test_nested_lower_lows_remain_one_episode_and_first_tied_trough_wins():
    snapshot = calculate(("-2", "-2", "1", "-1", "0", "4")).snapshot
    episode = snapshot.episodes[0]
    assert snapshot.total_drawdowns == 1
    assert episode.trough_equity == Decimal("96")
    assert episode.trough_time == 27
    assert episode.source_drawdown_point_ids == tuple(point.id for point in snapshot_source(("-2", "-2", "1", "-1", "0", "4")).points)


def snapshot_source(pnls, starting="100", as_of=40):
    return sources(pnls, starting=starting, as_of=as_of)[0]


def test_gap_above_peak_records_observed_recovery_without_price_invention():
    episode = calculate(("-10", "15")).snapshot.episodes[0]
    assert episode.recovery_equity == Decimal("105") and episode.recovery_time == 27


def test_maximum_drawdown_lineage_is_preserved_on_owning_episode():
    drawdown, baseline = sources(("-10", "10", "-20", "20"))
    snapshot = RecoveryStatisticsEngine().calculate(scope=scope(), drawdown=drawdown, starting_equity=baseline, as_of_time=40).snapshot
    assert not snapshot.episodes[0].contains_maximum_drawdown
    assert snapshot.episodes[1].contains_maximum_drawdown
    assert snapshot.episodes[1].maximum_drawdown_source_point_ids == drawdown.maximum_drawdown_abs_point_ids


def test_zero_and_negative_starting_equity_use_absolute_depth_and_null_percentage():
    zero = calculate(("-1", "1"), starting="0").snapshot.episodes[0]
    assert zero.recovery_depth == 1 and zero.recovery_depth_pct is None and zero.recovered
    negative = calculate(("-1", "1"), starting="-10").snapshot.episodes[0]
    assert negative.peak_equity == -10 and negative.recovery_depth == 1 and negative.recovery_depth_pct is None


def test_point_in_time_snapshot_does_not_look_ahead_or_rewrite_history():
    early_drawdown, early_baseline = sources(("-10", "-10", "20"), as_of=27)
    engine = RecoveryStatisticsEngine()
    early = engine.calculate(scope=scope(), drawdown=early_drawdown, starting_equity=early_baseline, as_of_time=27)
    assert early.snapshot.episodes[0].status == RecoveryEpisodeStatus.UNRECOVERED
    later_drawdown, later_baseline = sources(("-10", "-10", "20"), as_of=40)
    later = engine.calculate(scope=scope(), drawdown=later_drawdown, starting_equity=later_baseline, as_of_time=40, history=early.history)
    assert later.snapshot.episodes[0].status == RecoveryEpisodeStatus.RECOVERED
    assert later.history.snapshots[0] == early.snapshot


@pytest.mark.parametrize("field", ["scope", "drawdown", "starting_equity"])
def test_missing_inputs_fail_closed(field):
    drawdown, baseline = sources()
    values = dict(scope=scope(), drawdown=drawdown, starting_equity=baseline, as_of_time=40)
    values[field] = None
    assert RecoveryStatisticsEngine().calculate(**values).error.reason == "REQUIRED_RECOVERY_INPUT_MISSING"


def test_duplicate_missing_misordered_and_noncontiguous_points_fail_closed():
    drawdown, baseline = sources(("-1", "1")); engine = RecoveryStatisticsEngine()
    duplicate = replace(drawdown.points[1], id=drawdown.points[0].id)
    result = engine.calculate(scope=scope(), drawdown=replace(drawdown, points=(drawdown.points[0], duplicate)), starting_equity=baseline, as_of_time=40)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert engine.calculate(scope=scope(), drawdown=replace(drawdown, trade_count=3), starting_equity=baseline, as_of_time=40).error.reason == "DRAWDOWN_SOURCE_INVALID_OR_INCOMPLETE"
    assert engine.calculate(scope=scope(), drawdown=replace(drawdown, points=tuple(reversed(drawdown.points))), starting_equity=baseline, as_of_time=40).error.reason == "DRAWDOWN_POINT_ORDER_INVALID"
    bad = replace(drawdown.points[1], sequence=3)
    assert engine.calculate(scope=scope(), drawdown=replace(drawdown, points=(drawdown.points[0], bad)), starting_equity=baseline, as_of_time=40).error.reason == "DRAWDOWN_POINT_NONCONTIGUOUS"


def test_future_nonfinite_scope_version_and_baseline_mismatches_fail_closed():
    drawdown, baseline = sources(("-1",)); engine = RecoveryStatisticsEngine()
    assert engine.calculate(scope=scope(), drawdown=drawdown, starting_equity=baseline, as_of_time=39).error.reason == "DRAWDOWN_POINT_IN_TIME_MISMATCH"
    point = replace(drawdown.points[0], equity=Decimal("NaN"))
    assert engine.calculate(scope=scope(), drawdown=replace(drawdown, points=(point,)), starting_equity=baseline, as_of_time=40).error.reason == "NON_FINITE_DRAWDOWN_INPUT"
    assert engine.calculate(scope=scope(symbol="ETH"), drawdown=drawdown, starting_equity=baseline, as_of_time=40).error.reason == "RECOVERY_DRAWDOWN_SCOPE_OR_VERSION_MISMATCH"
    assert engine.calculate(scope=scope(calculation_version="v2"), drawdown=drawdown, starting_equity=baseline, as_of_time=40).error.reason == "RECOVERY_DRAWDOWN_SCOPE_OR_VERSION_MISMATCH"
    assert engine.calculate(scope=scope(), drawdown=drawdown, starting_equity=replace(baseline, equity=Decimal("99")), as_of_time=40).error.reason == "STARTING_EQUITY_VALUE_MISMATCH"


def test_idempotent_replay_conflict_prevention_and_immutability():
    engine = RecoveryStatisticsEngine(); drawdown, baseline = sources(("-10", "10"))
    first = engine.calculate(scope=scope(), drawdown=drawdown, starting_equity=baseline, as_of_time=40)
    replay = engine.calculate(scope=scope(), drawdown=drawdown, starting_equity=baseline, as_of_time=40, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    other_drawdown, other_baseline = sources(("-20", "20"))
    conflict = engine.calculate(scope=scope(), drawdown=other_drawdown, starting_equity=other_baseline, as_of_time=40, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    with pytest.raises(FrozenInstanceError):
        first.snapshot.total_drawdowns = 9
