from dataclasses import FrozenInstanceError, replace

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccountingEngine, TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import *
from strategy.trading_brain.test_p29_7_1_trade_accounting import completed


def accounting(result=TradeResult.WIN, suffix="1", closed=26):
    source=completed(); record=TradeAccountingEngine().calculate(**source).record
    return replace(record, id=f"accounting-{suffix}", trade_id=f"trade-{suffix}", position_id=f"position-{suffix}", position_snapshot_id=f"snapshot-{suffix}", closed_time=closed, accounting_time=max(closed, 28), trade_result=result)


def scope(**changes):
    base=TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1")
    return replace(base, **changes)


def test_counts_authoritative_classifications_without_rederiving():
    trades=(accounting(TradeResult.WIN, "1"), accounting(TradeResult.LOSS, "2", 27), accounting(TradeResult.BREAKEVEN, "3", 28))
    # Deliberately inconsistent PnL proves .1 consumes TradeResult rather than reclassifying.
    trades=(trades[0], replace(trades[1], net_pnl=abs(trades[1].net_pnl)), trades[2])
    result=TradeClassificationCountEngine().calculate(scope=scope(), trades=trades, as_of_time=30)
    assert result.valid
    assert (result.snapshot.trade_count, result.snapshot.win_count, result.snapshot.loss_count, result.snapshot.breakeven_count) == (3, 1, 1, 1)
    assert result.snapshot.source_trade_ids == ("trade-1", "trade-2", "trade-3")


def test_empty_population_is_valid_zero_count():
    result=TradeClassificationCountEngine().calculate(scope=scope(), trades=(), as_of_time=30)
    assert result.valid and result.snapshot.trade_count == 0
    assert result.snapshot.win_count == result.snapshot.loss_count == result.snapshot.breakeven_count == 0


def test_future_finalized_trade_is_excluded_without_lookahead():
    past=accounting(TradeResult.WIN, "past", 29); future=accounting(TradeResult.LOSS, "future", 31)
    result=TradeClassificationCountEngine().calculate(scope=scope(), trades=(future, past), as_of_time=30)
    assert result.snapshot.trade_count == 1
    assert result.snapshot.source_trade_ids == ("trade-past",)
    assert result.snapshot.future_excluded_trade_ids == ("trade-future",)


def test_canonical_order_uses_close_time_then_trade_id():
    trades=(accounting(TradeResult.WIN, "b", 27), accounting(TradeResult.WIN, "a", 27), accounting(TradeResult.WIN, "z", 26))
    result=TradeClassificationCountEngine().calculate(scope=scope(), trades=trades, as_of_time=30)
    assert result.snapshot.source_trade_ids == ("trade-z", "trade-a", "trade-b")


@pytest.mark.parametrize("field", ["scope", "trades"])
def test_missing_inputs_fail_closed(field):
    values={"scope":scope(), "trades":()}; values[field]=None
    result=TradeClassificationCountEngine().calculate(**values, as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.PERFORMANCE_DATA_INVALID


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id":"other"}, "ANALYTICS_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol":"ETH"}, "ANALYTICS_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe":"5m"}, "ANALYTICS_TIMEFRAME_MISMATCH"),
    ({"model":SetupModel.REVERSAL_1}, "ANALYTICS_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction":StructuralRegime.BEARISH}, "ANALYTICS_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version":"v2"}, "ANALYTICS_INPUT_VERSION_MISMATCH"),
])
def test_scope_identity_and_version_mismatches(change, reason):
    trade=replace(accounting(), **change)
    result=TradeClassificationCountEngine().calculate(scope=scope(), trades=(trade,), as_of_time=30)
    assert result.error.reason == reason


def test_duplicate_trade_or_accounting_identity_is_global_fail_closed():
    engine=TradeClassificationCountEngine(); first=accounting(suffix="same"); duplicate=replace(first, id="other-accounting")
    result=engine.calculate(scope=scope(), trades=(first, duplicate), as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    duplicate_id=replace(accounting(suffix="two"), id=first.id)
    assert engine.calculate(scope=scope(), trades=(first, duplicate_id), as_of_time=30).error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_nonfinal_and_impossible_chronology_fail_closed():
    engine=TradeClassificationCountEngine()
    assert engine.calculate(scope=scope(), trades=(replace(accounting(), immutable=False),), as_of_time=30).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    invalid=replace(accounting(), opened_time=29, closed_time=28)
    assert engine.calculate(scope=scope(), trades=(invalid,), as_of_time=30).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_idempotent_replay_and_conflicting_snapshot_prevention():
    engine=TradeClassificationCountEngine(); first_trade=accounting(suffix="one")
    first=engine.calculate(scope=scope(), trades=(first_trade,), as_of_time=30)
    replay=engine.calculate(scope=scope(), trades=(first_trade,), as_of_time=30, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict=engine.calculate(scope=scope(), trades=(first_trade, accounting(suffix="two")), as_of_time=30, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert conflict.error.reason == "CONFLICTING_ANALYTICS_SNAPSHOT"


def test_snapshot_is_immutable_and_sources_unchanged():
    trade=accounting(); original=trade
    result=TradeClassificationCountEngine().calculate(scope=scope(), trades=(trade,), as_of_time=30)
    assert trade == original
    with pytest.raises(FrozenInstanceError):
        result.snapshot.trade_count = 99
