from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe, HistoricalCandle, candle_identity
from backtesting.moving_average_channel_research_v1 import (
    ChannelLocation, ChannelResearchError,
    extract_moving_average_channel_features,
)


def candles(closes, *, symbol="MES"):
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    result = []
    for index, close in enumerate(closes):
        opened = start + timedelta(minutes=index)
        if isinstance(close, tuple):
            item_open, item_high, item_low, item_close = (
                Decimal(str(value)) for value in close
            )
        else:
            item_open = item_high = item_low = item_close = Decimal(str(close))
        identity = candle_identity(
            dataset_id="fixture", schema_version="v1", source="test",
            exchange="CME", symbol=symbol, timeframe=CanonicalTimeframe.M1,
            open_time=opened, close_time=opened + timedelta(minutes=1),
        )
        result.append(HistoricalCandle(
            identity, "fixture", "v1", "test", "CME", symbol,
            CanonicalTimeframe.M1, opened, opened + timedelta(minutes=1),
            item_open, item_high, item_low, item_close, Decimal("1"), True,
        ))
    return tuple(result)


def test_two_completed_bars_above_prior_channel_create_advisory_candidate():
    source = candles([100] * 10 + [101, 102])
    result = extract_moving_average_channel_features(
        source, market=FuturesCanonicalMarket.ES,
    )
    assert [item.location for item in result] == [ChannelLocation.ABOVE] * 2
    assert result[0].candidate_setup is False
    assert result[1].candidate_setup is True
    assert result[1].consecutive_outside_bars == 2
    assert result[1].trading_authority is False
    assert result[1].paper_execution_permitted is False


def test_inside_bar_resets_confirmation_count():
    source = candles([100] * 10 + [101, (100, 101, 100, 100), 102])
    result = extract_moving_average_channel_features(
        source, market=FuturesCanonicalMarket.ES,
    )
    assert result[1].location is ChannelLocation.INSIDE
    assert result[1].consecutive_outside_bars == 0
    assert result[2].consecutive_outside_bars == 1
    assert result[2].candidate_setup is False


def test_current_bar_is_excluded_from_its_channel():
    source = candles([100] * 10 + [200])
    result = extract_moving_average_channel_features(
        source, market=FuturesCanonicalMarket.ES,
    )[0]
    assert result.channel_high == Decimal("100")
    assert result.channel_low == Decimal("100")


def test_wrong_market_gap_or_bad_parameter_fails_closed():
    source = candles([100] * 12, symbol="MNQ")
    with pytest.raises(ChannelResearchError, match="does not match"):
        extract_moving_average_channel_features(source, market=FuturesCanonicalMarket.ES)
    with pytest.raises(ChannelResearchError, match="contiguous"):
        extract_moving_average_channel_features(
            source[:5] + source[6:], market=FuturesCanonicalMarket.NQ,
        )
    with pytest.raises(ChannelResearchError, match="positive integer"):
        extract_moving_average_channel_features(
            source, market=FuturesCanonicalMarket.NQ, confirmation_bars=0,
        )
