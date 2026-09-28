from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode, TradeCountScope
from strategy.trading_brain.p29_7_2_9_period_statistics import *
from strategy.trading_brain.test_p29_7_2_1_trade_classification_count import accounting


def ts(year, month, day, hour=0):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp())


def scope(**changes):
    return replace(TradeCountScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1"), **changes)


def period(kind, start, end, **changes):
    return replace(PeriodDefinition(kind, "UTC", start, end, "source-v1", "history-v1"), **changes)


def trade(result, suffix, closed, pnl, net_r):
    return replace(accounting(result, suffix, closed), net_pnl=Decimal(pnl), net_r=Decimal(net_r))


def test_daily_period_counts_totals_ratios_and_exact_denominator():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    items = (trade(TradeResult.WIN, "w", start + 1, "10", "1"), trade(TradeResult.LOSS, "l", start + 2, "-4", "-0.4"), trade(TradeResult.BREAKEVEN, "b", start + 3, "0", "0"))
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=items, as_of_time=end).snapshot
    assert (snapshot.trade_count, snapshot.win_count, snapshot.loss_count, snapshot.breakeven_count) == (3, 1, 1, 1)
    assert (snapshot.total_net_pnl, snapshot.total_net_r) == (Decimal("6"), Decimal("0.6"))
    assert snapshot.win_rate == Decimal("0.3333333333333333333333333333")
    assert (snapshot.average_net_pnl, snapshot.average_net_r) == (Decimal("2"), Decimal("0.2"))


def test_half_open_boundary_assigns_start_and_excludes_end():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    at_start = trade(TradeResult.WIN, "start", start, "1", "0.1")
    at_end = trade(TradeResult.WIN, "end", end, "100", "10")
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(at_end, at_start), as_of_time=end + 86400).snapshot
    assert snapshot.source_trade_ids == ("trade-start",)
    assert snapshot.excluded_other_period_trade_ids == ("trade-end",)


def test_weekly_iso_monday_sunday_boundary():
    start, end = ts(2026, 8, 10), ts(2026, 8, 17)
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.WEEKLY, start, end), trades=(trade(TradeResult.WIN, "sun", ts(2026, 8, 16, 23), "2", "0.2"),), as_of_time=end).snapshot
    assert snapshot.trade_count == 1 and snapshot.period_type == PeriodType.WEEKLY


def test_monthly_calendar_boundary():
    start, end = ts(2026, 2, 1), ts(2026, 3, 1)
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.MONTHLY, start, end), trades=(trade(TradeResult.WIN, "feb", ts(2026, 2, 28, 23), "2", "0.2"),), as_of_time=end).snapshot
    assert snapshot.trade_count == 1 and snapshot.period_end == end


def test_full_history_uses_explicit_requested_range():
    start, end = ts(2026, 1, 1), ts(2027, 1, 1)
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.FULL_HISTORY, start, end), trades=(trade(TradeResult.WIN, "one", ts(2026, 6, 1), "3", "0.3"),), as_of_time=end).snapshot
    assert snapshot.trade_count == 1 and snapshot.total_net_r == Decimal("0.3")


def test_requested_no_trade_period_is_zero_and_null_not_missing():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    result = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(), as_of_time=end)
    snapshot = result.snapshot
    assert snapshot.trade_count == snapshot.win_count == snapshot.loss_count == snapshot.breakeven_count == 0
    assert snapshot.total_net_pnl == snapshot.total_net_r == 0
    assert snapshot.win_rate is snapshot.average_net_pnl is snapshot.average_net_r is None
    assert len(result.history.snapshots) == 1


def test_unrequested_period_is_missing_no_record():
    history = PeriodStatisticsHistory()
    assert history.snapshots == ()


def test_single_trade_and_zero_return_are_real_observations():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    item = trade(TradeResult.BREAKEVEN, "one", start + 1, "0", "0")
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(item,), as_of_time=end).snapshot
    assert snapshot.trade_count == 1 and snapshot.total_net_r == snapshot.average_net_r == 0
    assert snapshot.win_rate == 0


def test_canonical_ordering_and_future_exclusion():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    items = (trade(TradeResult.WIN, "b", start + 2, "1", "0.1"), trade(TradeResult.WIN, "future", end + 86400, "100", "10"), trade(TradeResult.WIN, "a", start + 2, "1", "0.1"))
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=items, as_of_time=end).snapshot
    assert snapshot.source_trade_ids == ("trade-a", "trade-b")
    assert snapshot.future_excluded_trade_ids == ("trade-future",)


@pytest.mark.parametrize("field", ["scope", "period", "trades"])
def test_missing_inputs_fail_closed(field):
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    values = {"scope": scope(), "period": period(PeriodType.DAILY, start, end), "trades": ()}; values[field] = None
    assert PeriodStatisticsEngine().calculate(**values, as_of_time=end).error.reason == "REQUIRED_PERIOD_INPUT_MISSING"


@pytest.mark.parametrize("change,reason", [
    ({"strategy_id": "other"}, "PERIOD_SCOPE_IDENTITY_MISMATCH"),
    ({"symbol": "ETH"}, "PERIOD_SCOPE_IDENTITY_MISMATCH"),
    ({"timeframe": "5m"}, "PERIOD_TIMEFRAME_MISMATCH"),
    ({"model": SetupModel.REVERSAL_1}, "PERIOD_MODEL_OR_DIRECTION_MISMATCH"),
    ({"direction": StructuralRegime.BEARISH}, "PERIOD_MODEL_OR_DIRECTION_MISMATCH"),
    ({"input_version": "v2"}, "PERIOD_INPUT_VERSION_MISMATCH"),
])
def test_scope_and_version_separation(change, reason):
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    item = replace(trade(TradeResult.WIN, "one", start + 1, "1", "0.1"), **change)
    result = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(item,), as_of_time=end)
    assert result.error.reason == reason


def test_period_source_historical_and_calculation_versions_isolate_identity():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15); engine = PeriodStatisticsEngine()
    first = engine.calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(), as_of_time=end)
    second = engine.calculate(scope=scope(calculation_version="analytics-v2"), period=period(PeriodType.DAILY, start, end, source_version="source-v2", historical_version="history-v2"), trades=(), as_of_time=end, history=first.history)
    assert second.valid and second.snapshot.period_id != first.snapshot.period_id


def test_duplicate_keys_have_data_integrity_precedence():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15)
    item = trade(TradeResult.WIN, "same", start + 1, "1", "0.1")
    result = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(item, replace(item, id="other", immutable=False)), as_of_time=end)
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_invalid_timezone_boundaries_and_unfinalized_period_fail_closed():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15); engine = PeriodStatisticsEngine()
    assert engine.calculate(scope=scope(), period=period(PeriodType.DAILY, start, end, account_timezone="Invalid/Zone"), trades=(), as_of_time=end).error.reason == "ACCOUNT_TIMEZONE_INVALID"
    assert engine.calculate(scope=scope(), period=period(PeriodType.DAILY, start + 1, end), trades=(), as_of_time=end).error.reason == "PERIOD_BOUNDARY_INVALID"
    assert engine.calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(), as_of_time=end - 1).error.reason == "PERIOD_NOT_FINAL"


def test_nonfinal_nonfinite_and_invalid_chronology_fail_closed():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15); engine = PeriodStatisticsEngine()
    item = trade(TradeResult.WIN, "one", start + 1, "1", "0.1"); definition = period(PeriodType.DAILY, start, end)
    assert engine.calculate(scope=scope(), period=definition, trades=(replace(item, immutable=False),), as_of_time=end).error.reason == "NON_FINAL_ACCOUNTING_RECORD"
    assert engine.calculate(scope=scope(), period=definition, trades=(replace(item, net_r=Decimal("NaN")),), as_of_time=end).error.reason == "NON_FINITE_PERIOD_INPUT"
    assert engine.calculate(scope=scope(), period=definition, trades=(replace(item, opened_time=start + 2),), as_of_time=end).error.reason == "ACCOUNTING_RECORD_CHRONOLOGY_INVALID"


def test_idempotent_replay_and_conflicting_period_snapshot():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15); engine = PeriodStatisticsEngine(); definition = period(PeriodType.DAILY, start, end)
    item = trade(TradeResult.WIN, "one", start + 1, "1", "0.1")
    first = engine.calculate(scope=scope(), period=definition, trades=(item,), as_of_time=end)
    replay = engine.calculate(scope=scope(), period=definition, trades=(item,), as_of_time=end, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(scope=scope(), period=definition, trades=(item, trade(TradeResult.WIN, "two", start + 2, "2", "0.2")), as_of_time=end, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_snapshot_is_immutable_and_sources_unchanged():
    start, end = ts(2026, 8, 14), ts(2026, 8, 15); item = trade(TradeResult.WIN, "one", start + 1, "1", "0.1"); original = item
    snapshot = PeriodStatisticsEngine().calculate(scope=scope(), period=period(PeriodType.DAILY, start, end), trades=(item,), as_of_time=end).snapshot
    assert item == original
    with pytest.raises(FrozenInstanceError):
        snapshot.total_net_pnl = Decimal("9")
