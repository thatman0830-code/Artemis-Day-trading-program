"""Read-only RTH gap features derived from immutable historical candles.

This module is deliberately outside strategy and execution.  It classifies an
observed session; it cannot create signals, orders, or trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe, HistoricalCandle


VERSION = "gap-feature-research-v1"
_CHICAGO = ZoneInfo("America/Chicago")
_RTH_OPEN = time(8, 30)
_RTH_CLOSE = time(15, 0)
_EXPECTED_M1_BARS = 390


class GapFeatureError(ValueError):
    pass


class GapSide(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NONE = "NONE"


class GapOutcome(str, Enum):
    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    NO_GAP = "NO_GAP"
    DATA_QUALITY_FAILURE = "DATA_QUALITY_FAILURE"


@dataclass(frozen=True)
class GapSessionFeatureV1:
    market: FuturesCanonicalMarket
    session_date: date
    prior_session_date: date | None
    prior_rth_high: Decimal | None
    prior_rth_low: Decimal | None
    session_open: Decimal | None
    gap_side: GapSide
    gap_points: Decimal | None
    gap_prior_range_ratio: Decimal | None
    triggered: bool | None
    trigger_time: datetime | None
    trigger_delay_seconds: int | None
    outcome: GapOutcome
    reason_codes: tuple[str, ...]
    source_candle_ids: tuple[str, ...]
    schema_version: str = VERSION
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False


def _rth_date(candle: HistoricalCandle) -> date | None:
    opened = candle.open_time.astimezone(_CHICAGO)
    closed = candle.close_time.astimezone(_CHICAGO)
    if opened.date() != closed.date():
        return None
    if opened.time().replace(tzinfo=None) < _RTH_OPEN:
        return None
    if closed.time().replace(tzinfo=None) > _RTH_CLOSE:
        return None
    return opened.date()


def _valid_session(candles: tuple[HistoricalCandle, ...]) -> bool:
    if len(candles) != _EXPECTED_M1_BARS:
        return False
    for previous, current in zip(candles, candles[1:]):
        if current.open_time - previous.open_time != timedelta(minutes=1):
            return False
    local_first = candles[0].open_time.astimezone(_CHICAGO)
    local_last = candles[-1].close_time.astimezone(_CHICAGO)
    return (local_first.time().replace(tzinfo=None) == _RTH_OPEN
            and local_last.time().replace(tzinfo=None) == _RTH_CLOSE)


def extract_gap_session_features(
    candles: tuple[HistoricalCandle, ...], *, market: FuturesCanonicalMarket
) -> tuple[GapSessionFeatureV1, ...]:
    """Classify complete CME RTH sessions without mutating data or trading state."""
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ research market required")
    if not isinstance(candles, tuple) or not candles:
        raise GapFeatureError("nonempty immutable candle tuple required")
    if any(not isinstance(item, HistoricalCandle) for item in candles):
        raise TypeError("HistoricalCandle inputs required")
    if any(item.timeframe is not CanonicalTimeframe.M1 for item in candles):
        raise GapFeatureError("gap research v1 requires canonical 1m candles")
    expected_symbols = {
        FuturesCanonicalMarket.ES: {"ES", "MES"},
        FuturesCanonicalMarket.NQ: {"NQ", "MNQ"},
    }[market]
    if any(item.symbol.upper() not in expected_symbols for item in candles):
        raise GapFeatureError("candle symbol does not match explicit research market")
    ordered = tuple(sorted(candles, key=lambda item: item.open_time))
    if ordered != candles or len({item.id for item in candles}) != len(candles):
        raise GapFeatureError("candles must be unique and chronologically ordered")

    grouped: dict[date, list[HistoricalCandle]] = {}
    for candle in candles:
        session_date = _rth_date(candle)
        if session_date is not None:
            grouped.setdefault(session_date, []).append(candle)

    results: list[GapSessionFeatureV1] = []
    prior_date: date | None = None
    prior: tuple[HistoricalCandle, ...] | None = None
    for session_date in sorted(grouped):
        current = tuple(grouped[session_date])
        source_ids = tuple(item.id for item in current)
        if prior is None:
            results.append(GapSessionFeatureV1(
                market, session_date, None, None, None, None, GapSide.NONE,
                None, None, None, None, None, GapOutcome.DATA_QUALITY_FAILURE,
                ("NO_PRIOR_RTH_SESSION",), source_ids,
            ))
        elif not _valid_session(prior) or not _valid_session(current):
            reasons = []
            if not _valid_session(prior):
                reasons.append("INCOMPLETE_PRIOR_RTH_SESSION")
            if not _valid_session(current):
                reasons.append("INCOMPLETE_CURRENT_RTH_SESSION")
            results.append(GapSessionFeatureV1(
                market, session_date, prior_date, None, None, None,
                GapSide.NONE, None, None, None, None, None,
                GapOutcome.DATA_QUALITY_FAILURE, tuple(reasons), source_ids,
            ))
        else:
            prior_high = max(item.high for item in prior)
            prior_low = min(item.low for item in prior)
            opening = current[0].open
            prior_range = prior_high - prior_low
            side = GapSide.NONE
            points = Decimal("0")
            boundary = None
            if opening > prior_high:
                side, points, boundary = GapSide.UP, opening - prior_high, prior_high
            elif opening < prior_low:
                side, points, boundary = GapSide.DOWN, prior_low - opening, prior_low
            ratio = points / prior_range if prior_range > 0 else None
            trigger = None
            if side is GapSide.UP:
                trigger = next((item for item in current if item.low <= boundary), None)
            elif side is GapSide.DOWN:
                trigger = next((item for item in current if item.high >= boundary), None)
            triggered = None if side is GapSide.NONE else trigger is not None
            trigger_time = trigger.open_time if trigger else None
            delay = (int((trigger_time - current[0].open_time).total_seconds())
                     if trigger_time else None)
            outcome = (GapOutcome.NO_GAP if side is GapSide.NONE else
                       GapOutcome.TRIGGERED if trigger else GapOutcome.NOT_TRIGGERED)
            reason = ("OPEN_INSIDE_PRIOR_RANGE",) if side is GapSide.NONE else (
                "PRIOR_RANGE_REENTRY",) if trigger else ("NO_PRIOR_RANGE_REENTRY",)
            results.append(GapSessionFeatureV1(
                market, session_date, prior_date, prior_high, prior_low,
                opening, side, points, ratio, triggered, trigger_time, delay,
                outcome, reason, source_ids,
            ))
        prior_date, prior = session_date, current
    return tuple(results)

