from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_2_return_statistics import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def scope(**changes):
    return replace(TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def trade(suffix, closed, net_pnl, net_r, gross_pnl, gross_r):
    return replace(accounting(TradeResult.WIN, suffix, closed), net_pnl=Decimal(net_pnl), net_r=Decimal(net_r), gross_pnl=Decimal(gross_pnl), gross_r=Decimal(gross_r))


def test_population_totals_averages_and_extrema():
    trades=(trade("1",26,"10","1","12","1.2"), trade("2",27,"-4","-0.4","-3","-0.3"), trade("3",28,"0","0","1","0.1"))
    s=ReturnStatisticsEngine().calculate(scope=scope(), trades=trades, as_of_time=30).snapshot
    assert s.sample_size == 3
    assert (s.total_net_pnl, s.total_net_r, s.total_gross_pnl, s.total_gross_r) == (Decimal("6"), Decimal("0.6"), Decimal("10"), Decimal("1.0"))
    assert (s.average_net_pnl, s.average_net_r) == (Decimal("2"), Decimal("0.2"))
    assert s.average_gross_pnl == Decimal("3.333333333333333333333333333")
    assert (s.minimum_net_pnl, s.maximum_net_pnl) == (Decimal("-4"), Decimal("10"))
    assert (s.minimum_gross_r, s.maximum_gross_r) == (Decimal("-0.3"), Decimal("1.2"))


def test_empty_sample_has_zero_totals_and_null_observation_statistics():
    s=ReturnStatisticsEngine().calculate(scope=scope(), trades=(), as_of_time=30).snapshot
    assert s.sample_size == 0
    assert s.total_net_pnl == s.total_net_r == s.total_gross_pnl == s.total_gross_r == 0
    assert s.average_net_pnl is None and s.minimum_net_pnl is None and s.maximum_gross_r is None


def test_single_trade_denominator_boundary_equals_trade_values():
    item=trade("one",26,"7","0.7","8","0.8")
    s=ReturnStatisticsEngine().calculate(scope=scope(), trades=(item,), as_of_time=30).snapshot
    assert s.sample_size == 1 and s.average_net_pnl == item.net_pnl and s.average_gross_r == item.gross_r


def test_point_in_time_excludes_future_trade():
    past=trade("past",29,"2","0.2","2","0.2"); future=trade("future",31,"100","10","100","10")
    s=ReturnStatisticsEngine().calculate(scope=scope(), trades=(future,past), as_of_time=30).snapshot
    assert s.sample_size == 1 and s.total_net_pnl == 2
    assert s.future_excluded_trade_ids == ("trade-future",)


def test_ordering_is_close_time_then_trade_id():
    trades=(trade("b",27,"1","1","1","1"), trade("a",27,"1","1","1","1"), trade("z",26,"1","1","1","1"))
    s=ReturnStatisticsEngine().calculate(scope=scope(), trades=trades, as_of_time=30).snapshot
    assert s.source_trade_ids == ("trade-z","trade-a","trade-b")


@pytest.mark.parametrize("field", ["scope","trades"])
def test_missing_inputs_fail_closed(field):
    values={"scope":scope(),"trades":()}; values[field]=None
    assert ReturnStatisticsEngine().calculate(**values,as_of_time=30).error.reason == "REQUIRED_RETURN_INPUT_MISSING"


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id":"other"},"RETURN_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol":"ETH"},"RETURN_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe":"5m"},"RETURN_TIMEFRAME_MISMATCH"),
    ({"model":SetupModel.REVERSAL_1},"RETURN_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction":StructuralRegime.BEARISH},"RETURN_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version":"v2"},"RETURN_INPUT_VERSION_MISMATCH"),
])
def test_scope_and_version_separation(change, reason):
    item=replace(trade("one",26,"1","1","1","1"),**change)
    assert ReturnStatisticsEngine().calculate(scope=scope(),trades=(item,),as_of_time=30).error.reason == reason


def test_duplicate_keys_fail_closed_before_calculation():
    item=trade("same",26,"1","1","1","1"); duplicate=replace(item,id="other")
    result=ReturnStatisticsEngine().calculate(scope=scope(),trades=(item,duplicate),as_of_time=30)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_nonfinal_nonfinite_and_invalid_chronology_fail_closed():
    engine=ReturnStatisticsEngine(); item=trade("one",26,"1","1","1","1")
    assert engine.calculate(scope=scope(),trades=(replace(item,immutable=False),),as_of_time=30).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(),trades=(replace(item,net_r=Decimal("NaN")),),as_of_time=30).error.reason == "NON_FINITE_RETURN_INPUT"
    assert engine.calculate(scope=scope(),trades=(replace(item,opened_time=27),),as_of_time=30).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_idempotent_replay_and_conflicting_snapshot():
    engine=ReturnStatisticsEngine(); item=trade("one",26,"1","1","1","1")
    first=engine.calculate(scope=scope(),trades=(item,),as_of_time=30)
    replay=engine.calculate(scope=scope(),trades=(item,),as_of_time=30,history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict=engine.calculate(scope=scope(),trades=(item,trade("two",27,"2","2","2","2")),as_of_time=30,history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_immutable_and_source_unchanged():
    item=trade("one",26,"1","1","1","1"); original=item
    result=ReturnStatisticsEngine().calculate(scope=scope(),trades=(item,),as_of_time=30)
    assert item == original
    with pytest.raises(FrozenInstanceError):
        result.snapshot.average_net_pnl=Decimal("9")
