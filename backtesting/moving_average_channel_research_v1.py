"""Read-only moving-average-channel observations for ES/NQ research.

The channel parameters come from a photographed historical source and are
hypotheses only.  This module cannot create signals, orders, or authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import HistoricalCandle


VERSION = "moving-average-channel-research-v1"


class ChannelResearchError(ValueError):
    pass


class ChannelLocation(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    INSIDE = "INSIDE"


@dataclass(frozen=True)
class MovingAverageChannelFeatureV1:
    market: FuturesCanonicalMarket
    candle_id: str
    channel_high: Decimal
    channel_low: Decimal
    location: ChannelLocation
    consecutive_outside_bars: int
    candidate_setup: bool
    reason_codes: tuple[str, ...]
    high_lookback: int
    low_lookback: int
    required_confirmation_bars: int
    schema_version: str = VERSION
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False


def extract_moving_average_channel_features(
    candles: tuple[HistoricalCandle, ...],
    *,
    market: FuturesCanonicalMarket,
    high_lookback: int = 10,
    low_lookback: int = 8,
    confirmation_bars: int = 2,
) -> tuple[MovingAverageChannelFeatureV1, ...]:
    """Return channel observations using prior completed bars only.

    The current candle never participates in its own channel, which makes the
    anti-look-ahead rule explicit.  A candidate setup is descriptive evidence,
    not an executable entry signal.
    """
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ research market required")
    if not isinstance(candles, tuple) or not candles:
        raise ChannelResearchError("nonempty immutable candle tuple required")
    if any(not isinstance(item, HistoricalCandle) for item in candles):
        raise TypeError("HistoricalCandle inputs required")
    for name, value in (("high_lookback", high_lookback),
                        ("low_lookback", low_lookback),
                        ("confirmation_bars", confirmation_bars)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ChannelResearchError(f"{name} must be a positive integer")

    expected_symbols = {
        FuturesCanonicalMarket.ES: {"ES", "MES"},
        FuturesCanonicalMarket.NQ: {"NQ", "MNQ"},
    }[market]
    if any(item.symbol.upper() not in expected_symbols for item in candles):
        raise ChannelResearchError("candle symbol does not match explicit research market")
    first = candles[0]
    if any(item.symbol.upper() != first.symbol.upper() or
           item.timeframe is not first.timeframe for item in candles):
        raise ChannelResearchError("candles must use one symbol and timeframe")
    if tuple(sorted(candles, key=lambda item: item.open_time)) != candles:
        raise ChannelResearchError("candles must be chronologically ordered")
    if len({item.id for item in candles}) != len(candles):
        raise ChannelResearchError("candles must be unique")
    if any(current.open_time - previous.open_time != first.timeframe.duration
           for previous, current in zip(candles, candles[1:])):
        raise ChannelResearchError("candles must be contiguous")

    warmup = max(high_lookback, low_lookback)
    results: list[MovingAverageChannelFeatureV1] = []
    previous_location = ChannelLocation.INSIDE
    outside_count = 0
    for index in range(warmup, len(candles)):
        current = candles[index]
        high_window = candles[index - high_lookback:index]
        low_window = candles[index - low_lookback:index]
        channel_high = sum((item.high for item in high_window), Decimal("0")) / high_lookback
        channel_low = sum((item.low for item in low_window), Decimal("0")) / low_lookback

        if current.low > channel_high:
            location = ChannelLocation.ABOVE
        elif current.high < channel_low:
            location = ChannelLocation.BELOW
        else:
            location = ChannelLocation.INSIDE

        if location is ChannelLocation.INSIDE:
            outside_count = 0
        elif location is previous_location:
            outside_count += 1
        else:
            outside_count = 1
        candidate = outside_count >= confirmation_bars
        reason = (("COMPLETED_BARS_ABOVE_CHANNEL",) if location is ChannelLocation.ABOVE
                  else ("COMPLETED_BARS_BELOW_CHANNEL",) if location is ChannelLocation.BELOW
                  else ("BAR_INTERSECTS_CHANNEL",))
        results.append(MovingAverageChannelFeatureV1(
            market=market,
            candle_id=current.id,
            channel_high=channel_high,
            channel_low=channel_low,
            location=location,
            consecutive_outside_bars=outside_count,
            candidate_setup=candidate,
            reason_codes=reason,
            high_lookback=high_lookback,
            low_lookback=low_lookback,
            required_confirmation_bars=confirmation_bars,
        ))
        previous_location = location
    return tuple(results)
