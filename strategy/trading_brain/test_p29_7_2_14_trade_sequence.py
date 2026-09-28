from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_5_cumulative_pnl_r import CumulativePnLREngine
from strategy.trading_brain.p29_7_2_8_streak_statistics import StreakStatisticsEngine
from strategy.trading_brain.p29_7_2_14_trade_sequence import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(TradeSequenceScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "source-v1", "analytics-v1", "history-v1"), **changes)


def upstream_scope():
    return TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1")


def trade(result, suffix, closed, pnl=None, net_r=None):
    item = accounting(result, suffix, closed)
    pnl = {TradeResult.WIN: "10", TradeResult.LOSS: "-5", TradeResult.BREAKEVEN: "0"}[result] if pnl is None else pnl
    net_r = {TradeResult.WIN: "1", TradeResult.LOSS: "-0.5", TradeResult.BREAKEVEN: "0"}[result] if net_r is None else net_r
    return replace(item, net_pnl=Decimal(pnl), gross_pnl=Decimal(pnl), net_r=Decimal(net_r), gross_r=Decimal(net_r))


def bundle(items=(), as_of=40):
    cumulative = CumulativePnLREngine().calculate(scope=upstream_scope(), trades=items, as_of_time=as_of).snapshot
    streaks = StreakStatisticsEngine().calculate(scope=upstream_scope(), trades=items, as_of_time=as_of).snapshot
    return cumulative, streaks


def calculate(items=(), *, as_of=40, history=TradeSequenceHistory(), **changes):
    cumulative, streaks = bundle(items, as_of)
    values = dict(scope=scope(), trades=items, cumulative=cumulative, streaks=streaks, as_of_time=as_of, history=history)
    values.update(changes)
    return TradeSequenceEngine().calculate(**values)


def statistic(snapshot, source, target):
    return next(item for item in snapshot.transition_statistics if item.from_result == source and item.to_result == target)


def test_normal_path_order_transitions_probabilities_runs_and_current_facts():
    results = (TradeResult.WIN, TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN, TradeResult.LOSS)
    items = tuple(trade(result, str(index), 26 + index) for index, result in enumerate(results))
    snapshot = calculate(items).snapshot
    assert snapshot.result_sequence == results and snapshot.sequence_length == 5
    assert snapshot.transition_count == 4 and sum(item.transition_count for item in snapshot.transition_statistics) == 4
    assert statistic(snapshot, TradeResult.WIN, TradeResult.WIN).probability == Decimal("0.5")
    assert statistic(snapshot, TradeResult.WIN, TradeResult.LOSS).probability == Decimal("0.5")
    assert statistic(snapshot, TradeResult.LOSS, TradeResult.BREAKEVEN).probability == Decimal("1")
    assert statistic(snapshot, TradeResult.BREAKEVEN, TradeResult.LOSS).probability == Decimal("1")
    assert [run.result for run in snapshot.runs] == [TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN, TradeResult.LOSS]
    assert [run.length for run in snapshot.runs] == [2, 1, 1, 1]
    assert snapshot.current_trade_id == items[-1].trade_id and snapshot.current_run_id == snapshot.runs[-1].id


def test_empty_history_has_nine_null_transition_cells_and_zero_boundaries():
    snapshot = calculate().snapshot
    assert snapshot.sequence_length == snapshot.transition_count == snapshot.run_count == 0
    assert len(snapshot.transition_statistics) == 9
    assert all(item.transition_count == item.source_state_outgoing_count == 0 and item.probability is None for item in snapshot.transition_statistics)
    assert snapshot.maximum_winning_run == snapshot.maximum_losing_run == 0
    assert snapshot.current_trade_id is snapshot.current_run_id is None


def test_single_trade_has_one_run_no_outgoing_probability():
    snapshot = calculate((trade(TradeResult.WIN, "one", 26),)).snapshot
    assert snapshot.sequence_length == snapshot.run_count == 1 and snapshot.transition_count == 0
    assert snapshot.runs[0].length == 1
    assert all(item.probability is None for item in snapshot.transition_statistics)


def test_breakeven_is_independent_state_and_interrupts_win_loss_runs():
    results = (TradeResult.WIN, TradeResult.BREAKEVEN, TradeResult.WIN, TradeResult.LOSS, TradeResult.BREAKEVEN, TradeResult.LOSS)
    snapshot = calculate(tuple(trade(result, str(i), 26 + i) for i, result in enumerate(results))).snapshot
    assert snapshot.run_count == 6
    assert snapshot.maximum_winning_run == snapshot.maximum_losing_run == 1
    assert statistic(snapshot, TradeResult.BREAKEVEN, TradeResult.WIN).transition_count == 1
    assert statistic(snapshot, TradeResult.BREAKEVEN, TradeResult.LOSS).transition_count == 1


def test_authoritative_results_are_never_reclassified_from_pnl_or_r():
    item = trade(TradeResult.LOSS, "odd", 26, pnl="100", net_r="10")
    snapshot = calculate((item,)).snapshot
    assert snapshot.result_sequence == (TradeResult.LOSS,)
    assert snapshot.maximum_losing_run == 1 and snapshot.maximum_winning_run == 0


def test_canonical_closed_time_trade_id_order_and_cumulative_lineage():
    items = (trade(TradeResult.LOSS, "b", 27), trade(TradeResult.WIN, "a", 27), trade(TradeResult.BREAKEVEN, "z", 26))
    snapshot = calculate(items).snapshot
    assert snapshot.source_trade_ids == ("trade-z", "trade-a", "trade-b")
    assert tuple(item.sequence for item in snapshot.observations) == (1, 2, 3)
    assert snapshot.source_cumulative_point_ids == tuple(item.cumulative_point_id for item in snapshot.observations)
    assert snapshot.observations[-1].cumulative_net_pnl == Decimal("5")


def test_tied_maximum_streak_groups_are_consumed_unchanged():
    results = (TradeResult.WIN, TradeResult.WIN, TradeResult.LOSS, TradeResult.WIN, TradeResult.WIN)
    snapshot = calculate(tuple(trade(result, str(i), 26 + i) for i, result in enumerate(results))).snapshot
    assert snapshot.maximum_winning_run == 2
    assert snapshot.maximum_winning_streak_trade_id_groups == (("trade-0", "trade-1"), ("trade-3", "trade-4"))


def test_point_in_time_excludes_future_without_altering_past_positions():
    past = trade(TradeResult.WIN, "past", 29)
    future = trade(TradeResult.LOSS, "future", 31)
    snapshot = calculate((future, past), as_of=30).snapshot
    assert snapshot.source_trade_ids == ("trade-past",)
    assert snapshot.future_excluded_trade_ids == ("trade-future",)
    assert snapshot.current_trade_id == "trade-past"


@pytest.mark.parametrize("field", ["scope", "trades", "cumulative", "streaks"])
def test_missing_inputs_fail_closed(field):
    cumulative, streaks = bundle(())
    values = dict(scope=scope(), trades=(), cumulative=cumulative, streaks=streaks, as_of_time=40)
    values[field] = None
    assert TradeSequenceEngine().calculate(**values).error.reason == "REQUIRED_TRADE_SEQUENCE_INPUT_MISSING"


def test_cumulative_and_streak_compatibility_fail_closed_without_reconstruction():
    items = (trade(TradeResult.WIN, "one", 26),)
    cumulative, streaks = bundle(items); engine = TradeSequenceEngine()
    bad_point = replace(cumulative.points[0], cumulative_net_pnl=Decimal("999"))
    assert engine.calculate(scope=scope(), trades=items, cumulative=replace(cumulative, points=(bad_point,)), streaks=streaks, as_of_time=40).error.reason == "CUMULATIVE_TRANSITION_INVALID"
    assert engine.calculate(scope=scope(), trades=items, cumulative=cumulative, streaks=replace(streaks, maximum_winning_streak=9), as_of_time=40).error.reason == "STREAK_FACT_MISMATCH"


def test_scope_source_calculation_historical_versions_are_isolated():
    items = (trade(TradeResult.WIN, "one", 26),)
    first = calculate(items).snapshot
    second = calculate(items, scope=scope(source_version="source-v2", historical_version="history-v2")).snapshot
    assert first.id != second.id and second.source_version == "source-v2" and second.historical_version == "history-v2"
    cumulative, streaks = bundle(items)
    assert TradeSequenceEngine().calculate(scope=scope(calculation_version="analytics-v2"), trades=items, cumulative=cumulative, streaks=streaks, as_of_time=40).error.reason == "TRADE_SEQUENCE_CUMULATIVE_SCOPE_OR_VERSION_MISMATCH"


def test_duplicate_nonfinal_nonfinite_chronology_and_order_fail_closed():
    item = trade(TradeResult.WIN, "same", 26); cumulative, streaks = bundle((item,)); engine = TradeSequenceEngine()
    result = engine.calculate(scope=scope(), trades=(item, replace(item, id="other")), cumulative=cumulative, streaks=streaks, as_of_time=40)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert engine.calculate(scope=scope(), trades=(replace(item, immutable=False),), cumulative=cumulative, streaks=streaks, as_of_time=40).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), trades=(replace(item, net_r=Decimal("NaN")),), cumulative=cumulative, streaks=streaks, as_of_time=40).error.reason == "NON_FINITE_TRADE_SEQUENCE_INPUT"
    assert engine.calculate(scope=scope(), trades=(replace(item, opened_time=27),), cumulative=cumulative, streaks=streaks, as_of_time=40).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"
    reversed_cumulative = replace(cumulative, source_trade_ids=("other",))
    assert engine.calculate(scope=scope(), trades=(item,), cumulative=reversed_cumulative, streaks=streaks, as_of_time=40).error.reason == "CUMULATIVE_SEQUENCE_POPULATION_MISMATCH"


def test_idempotent_replay_conflict_prevention_and_immutability():
    engine = TradeSequenceEngine(); items = (trade(TradeResult.WIN, "one", 26),); cumulative, streaks = bundle(items)
    args = dict(scope=scope(), trades=items, cumulative=cumulative, streaks=streaks, as_of_time=40)
    first = engine.calculate(**args)
    replay = engine.calculate(**args, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    other = (trade(TradeResult.LOSS, "one", 26),); other_cumulative, other_streaks = bundle(other)
    conflict = engine.calculate(scope=scope(), trades=other, cumulative=other_cumulative, streaks=other_streaks, as_of_time=40, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    with pytest.raises(FrozenInstanceError):
        first.snapshot.sequence_length = 9
