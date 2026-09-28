from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.gap_feature_research_v1 import (
    GapFeatureError, GapOutcome, GapSide, extract_gap_session_features,
)
from backtesting.market_data import (
    CanonicalTimeframe, candle_identity, HistoricalCandle,
)


def session(day, *, symbol="MES", opening=Decimal("100"),
            high=Decimal("101"), low=Decimal("99"), trigger_low=None):
    # January is CST: 08:30 Chicago == 14:30 UTC.
    start = datetime(day.year, day.month, day.day, 14, 30, tzinfo=timezone.utc)
    values = []
    for index in range(390):
        opened = start + timedelta(minutes=index)
        bar_low = trigger_low if index == 5 and trigger_low is not None else low
        item_open = opening
        item_high = max(high, item_open, bar_low)
        item_low = min(bar_low, item_open)
        identity = candle_identity(dataset_id="fixture", schema_version="v1",
            source="test", exchange="CME", symbol=symbol,
            timeframe=CanonicalTimeframe.M1, open_time=opened,
            close_time=opened + timedelta(minutes=1))
        values.append(HistoricalCandle(identity, "fixture", "v1", "test", "CME",
            symbol, CanonicalTimeframe.M1, opened, opened + timedelta(minutes=1),
            item_open, item_high, item_low, item_open, Decimal("1"), True))
    return tuple(values)


def test_up_gap_requires_reentry_trigger_and_preserves_no_trade_case():
    prior = session(date(2026, 1, 5), high=Decimal("101"), low=Decimal("99"))
    current = session(date(2026, 1, 6), opening=Decimal("102"),
                      high=Decimal("103"), low=Decimal("101.5"),
                      trigger_low=Decimal("101"))
    results = extract_gap_session_features(prior + current,
                                           market=FuturesCanonicalMarket.ES)
    assert results[0].outcome is GapOutcome.DATA_QUALITY_FAILURE
    result = results[1]
    assert result.gap_side is GapSide.UP
    assert result.gap_points == Decimal("1")
    assert result.gap_prior_range_ratio == Decimal("0.5")
    assert result.outcome is GapOutcome.TRIGGERED
    assert result.trigger_delay_seconds == 300
    assert result.trading_authority is False
    assert result.paper_execution_permitted is False


def test_unfilled_gap_is_retained_as_not_triggered():
    prior = session(date(2026, 1, 5), high=Decimal("101"), low=Decimal("99"))
    current = session(date(2026, 1, 6), opening=Decimal("102"),
                      high=Decimal("103"), low=Decimal("101.25"))
    result = extract_gap_session_features(prior + current,
                                          market=FuturesCanonicalMarket.ES)[1]
    assert result.outcome is GapOutcome.NOT_TRIGGERED
    assert result.triggered is False and result.trigger_time is None


def test_no_gap_and_incomplete_session_are_explicit():
    prior = session(date(2026, 1, 5))
    current = session(date(2026, 1, 6), opening=Decimal("100"))
    assert extract_gap_session_features(prior + current,
        market=FuturesCanonicalMarket.ES)[1].outcome is GapOutcome.NO_GAP
    incomplete = prior + current[:-1]
    failed = extract_gap_session_features(incomplete,
        market=FuturesCanonicalMarket.ES)[1]
    assert failed.outcome is GapOutcome.DATA_QUALITY_FAILURE
    assert "INCOMPLETE_CURRENT_RTH_SESSION" in failed.reason_codes


def test_market_symbol_and_timeframe_fail_closed():
    candles = session(date(2026, 1, 5), symbol="MNQ")
    with pytest.raises(GapFeatureError, match="does not match"):
        extract_gap_session_features(candles, market=FuturesCanonicalMarket.ES)
    with pytest.raises(TypeError, match="explicit ES or NQ"):
        extract_gap_session_features(candles, market="NQ")
