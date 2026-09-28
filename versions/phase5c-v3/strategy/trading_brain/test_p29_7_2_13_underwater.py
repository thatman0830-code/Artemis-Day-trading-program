from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_12_recovery import RecoveryHistory, RecoveryStatisticsEngine
from strategy.trading_brain.p29_7_2_13_underwater import *
from strategy.trading_brain.test_p29_7_2_12_recovery import sources


def scope(**changes):
    return replace(UnderwaterScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def bundle(pnls=(), *, starting="100", as_of=40):
    drawdown, baseline = sources(pnls, starting=starting, as_of=as_of)
    from strategy.trading_brain.p29_7_2_12_recovery import RecoveryScope
    recovery = RecoveryStatisticsEngine().calculate(
        scope=RecoveryScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"),
        drawdown=drawdown, starting_equity=baseline, as_of_time=as_of,
    ).snapshot
    return drawdown, recovery, baseline


def calculate(pnls=(), *, starting="100", as_of=40, history=UnderwaterHistory(), **changes):
    drawdown, recovery, baseline = bundle(pnls, starting=starting, as_of=as_of)
    values = dict(scope=scope(), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=as_of, history=history)
    values.update(changes)
    return UnderwaterStatisticsEngine().calculate(**values)


def test_empty_and_flat_history_have_baseline_states_and_canonical_nulls():
    empty = calculate().snapshot
    assert empty.episode_count == empty.recovered_episode_count == empty.active_episode_count == 0
    assert empty.total_historical_time_underwater == empty.current_time_underwater == 0
    assert empty.maximum_completed_time_underwater is empty.average_completed_time_underwater is empty.median_completed_time_underwater is None
    assert len(empty.states) == 1 and not empty.states[0].underwater
    flat = calculate(("0", "0")).snapshot
    assert flat.episodes == () and all(not state.underwater for state in flat.states)


def test_recovered_episode_and_point_states_copy_authoritative_lineage():
    drawdown, recovery, baseline = bundle(("-10", "-10", "20"))
    snapshot = UnderwaterStatisticsEngine().calculate(scope=scope(), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=40).snapshot
    episode = snapshot.episodes[0]
    assert episode.recovery_episode_id == recovery.episodes[0].id
    assert (episode.start_time, episode.end_time, episode.duration) == (26, 28, 2)
    assert (episode.episode_peak_equity, episode.trough_equity, episode.recovery_equity) == tuple(map(Decimal, ("100", "80", "100")))
    assert [state.underwater for state in snapshot.states] == [False, True, True, False]
    assert [state.current_time_underwater for state in snapshot.states] == [0, 0, 1, 0]
    assert snapshot.total_historical_time_underwater == snapshot.maximum_completed_time_underwater == 2


def test_active_episode_is_excluded_from_completed_statistics_and_uses_last_finalized_time():
    snapshot = calculate(("-10", "-5"), as_of=40).snapshot
    episode = snapshot.episodes[0]
    assert episode.active and not episode.recovered and episode.duration is None
    assert episode.current_duration == 1  # last finalized point 27, not wall-clock as_of 40
    assert snapshot.current_time_underwater == 1 and snapshot.current_underwater
    assert snapshot.total_historical_time_underwater == 0
    assert snapshot.maximum_completed_time_underwater is snapshot.average_completed_time_underwater is snapshot.median_completed_time_underwater is None


def test_completed_distribution_average_median_and_maximum_use_completed_only():
    snapshot = calculate(("-10", "10", "-10", "0", "10", "-5")).snapshot
    assert snapshot.episode_count == 3 and snapshot.recovered_episode_count == 2 and snapshot.active_episode_count == 1
    assert snapshot.completed_duration_distribution == (1, 2)
    assert snapshot.total_historical_time_underwater == 3
    assert snapshot.average_completed_time_underwater == snapshot.median_completed_time_underwater == Decimal("1.5")
    assert snapshot.maximum_completed_time_underwater == 2


def test_tied_maximum_completed_episodes_preserve_chronological_identities():
    snapshot = calculate(("-10", "0", "10", "-5", "0", "5")).snapshot
    assert snapshot.completed_duration_distribution == (2, 2)
    assert snapshot.maximum_completed_episode_ids == tuple(item.id for item in snapshot.episodes)


def test_zero_and_nonpositive_equity_boundaries_preserve_null_percentages():
    snapshot = calculate(("-1", "1"), starting="0").snapshot
    assert snapshot.states[0].drawdown_pct is None
    assert snapshot.states[1].underwater and snapshot.states[1].drawdown_pct is None
    assert snapshot.episodes[0].recovery_depth_pct is None


def test_trough_and_maximum_drawdown_lineage_are_preserved_not_recomputed():
    drawdown, recovery, baseline = bundle(("-10", "10", "-20", "20"))
    snapshot = UnderwaterStatisticsEngine().calculate(scope=scope(), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=40).snapshot
    assert snapshot.episodes[1].trough_point_id == recovery.episodes[1].trough_point_id
    assert snapshot.episodes[1].maximum_drawdown_source_point_ids == drawdown.maximum_drawdown_abs_point_ids


def test_point_in_time_history_does_not_retroactively_close_active_episode():
    early_drawdown, early_recovery, early_baseline = bundle(("-10", "-10", "20"), as_of=27)
    engine = UnderwaterStatisticsEngine()
    early = engine.calculate(scope=scope(), drawdown=early_drawdown, recovery=early_recovery, starting_equity=early_baseline, as_of_time=27)
    assert early.snapshot.active_episode_count == 1
    later_drawdown, later_recovery, later_baseline = bundle(("-10", "-10", "20"), as_of=40)
    later = engine.calculate(scope=scope(), drawdown=later_drawdown, recovery=later_recovery, starting_equity=later_baseline, as_of_time=40, history=early.history)
    assert later.snapshot.recovered_episode_count == 1
    assert later.history.snapshots[0] == early.snapshot


@pytest.mark.parametrize("field", ["scope", "drawdown", "recovery", "starting_equity"])
def test_missing_inputs_fail_closed(field):
    drawdown, recovery, baseline = bundle()
    values = dict(scope=scope(), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=40)
    values[field] = None
    assert UnderwaterStatisticsEngine().calculate(**values).error.reason == "REQUIRED_UNDERWATER_INPUT_MISSING"


def test_duplicate_recovery_and_drawdown_facts_have_integrity_precedence():
    drawdown, recovery, baseline = bundle(("-10", "10", "-10", "10")); engine = UnderwaterStatisticsEngine()
    duplicate_episode = replace(recovery.episodes[1], id=recovery.episodes[0].id)
    result = engine.calculate(scope=scope(), drawdown=drawdown, recovery=replace(recovery, episodes=(recovery.episodes[0], duplicate_episode)), starting_equity=baseline, as_of_time=40)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    duplicate_point = replace(drawdown.points[1], id=drawdown.points[0].id)
    result = engine.calculate(scope=scope(), drawdown=replace(drawdown, points=(drawdown.points[0], duplicate_point, *drawdown.points[2:])), recovery=recovery, starting_equity=baseline, as_of_time=40)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_scope_version_chronology_nonfinite_and_source_mismatches_fail_closed():
    drawdown, recovery, baseline = bundle(("-10", "10")); engine = UnderwaterStatisticsEngine()
    assert engine.calculate(scope=scope(symbol="ETH"), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=40).error.reason == "UNDERWATER_DRAWDOWN_SCOPE_OR_VERSION_MISMATCH"
    assert engine.calculate(scope=scope(), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=39).error.reason == "UNDERWATER_POINT_IN_TIME_MISMATCH"
    assert engine.calculate(scope=scope(), drawdown=drawdown, recovery=replace(recovery, source_drawdown_series_id="other"), starting_equity=baseline, as_of_time=40).error.reason == "UNDERWATER_SOURCE_SERIES_MISMATCH"
    point = replace(drawdown.points[0], equity=Decimal("NaN"))
    assert engine.calculate(scope=scope(), drawdown=replace(drawdown, points=(point, *drawdown.points[1:])), recovery=recovery, starting_equity=baseline, as_of_time=40).error.reason == "NON_FINITE_UNDERWATER_INPUT"
    assert engine.calculate(scope=scope(), drawdown=replace(drawdown, points=tuple(reversed(drawdown.points))), recovery=recovery, starting_equity=baseline, as_of_time=40).error.reason == "UNDERWATER_SOURCE_POINT_IDENTITY_MISMATCH"


def test_idempotent_replay_conflict_prevention_and_immutability():
    engine = UnderwaterStatisticsEngine(); drawdown, recovery, baseline = bundle(("-10", "10"))
    first = engine.calculate(scope=scope(), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=40)
    replay = engine.calculate(scope=scope(), drawdown=drawdown, recovery=recovery, starting_equity=baseline, as_of_time=40, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    other_drawdown, other_recovery, other_baseline = bundle(("-20", "20"))
    conflict = engine.calculate(scope=scope(), drawdown=other_drawdown, recovery=other_recovery, starting_equity=other_baseline, as_of_time=40, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    with pytest.raises(FrozenInstanceError):
        first.snapshot.total_historical_time_underwater = 9
