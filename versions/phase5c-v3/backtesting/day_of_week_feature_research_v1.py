"""Descriptive CME day-of-week observations with no trading authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe, HistoricalCandle


VERSION = "day-of-week-feature-research-v1"
_CHICAGO = ZoneInfo("America/Chicago")
_RTH_OPEN, _RTH_CLOSE = time(8, 30), time(15, 0)
_EXPECTED_M1_BARS = 390


class DayOfWeekResearchError(ValueError):
    pass


class PriorSessionDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"


class CalendarSetup(str, Enum):
    LONG_OBSERVATION = "LONG_OBSERVATION"
    SHORT_OBSERVATION = "SHORT_OBSERVATION"
    NONE = "NONE"
    DATA_QUALITY_FAILURE = "DATA_QUALITY_FAILURE"


@dataclass(frozen=True)
class DayOfWeekFeatureV1:
    market: FuturesCanonicalMarket
    session_date: date
    weekday: int
    prior_session_date: date | None
    prior_weekday: int | None
    crossed_iso_week: bool | None
    prior_direction: PriorSessionDirection | None
    calendar_setup: CalendarSetup
    reason_codes: tuple[str, ...]
    source_candle_ids: tuple[str, ...]
    schema_version: str = VERSION
    advisory_only: bool = True
    directional_signal_permitted: bool = False
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False


def _session_date(item: HistoricalCandle) -> date | None:
    opened, closed = item.open_time.astimezone(_CHICAGO), item.close_time.astimezone(_CHICAGO)
    if opened.date() != closed.date() or opened.time().replace(tzinfo=None) < _RTH_OPEN:
        return None
    if closed.time().replace(tzinfo=None) > _RTH_CLOSE:
        return None
    return opened.date()


def _complete(items: tuple[HistoricalCandle, ...]) -> bool:
    if len(items) != _EXPECTED_M1_BARS:
        return False
    first, last = items[0].open_time.astimezone(_CHICAGO), items[-1].close_time.astimezone(_CHICAGO)
    return (first.time().replace(tzinfo=None) == _RTH_OPEN and
            last.time().replace(tzinfo=None) == _RTH_CLOSE and
            all(current.open_time - previous.open_time == timedelta(minutes=1)
                for previous, current in zip(items, items[1:])))


def extract_day_of_week_features(
    candles: tuple[HistoricalCandle, ...], *, market: FuturesCanonicalMarket
) -> tuple[DayOfWeekFeatureV1, ...]:
    """Describe first-session-of-week context from complete RTH sessions."""
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ research market required")
    if not isinstance(candles, tuple) or not candles:
        raise DayOfWeekResearchError("nonempty immutable candle tuple required")
    if any(not isinstance(item, HistoricalCandle) for item in candles):
        raise TypeError("HistoricalCandle inputs required")
    if any(item.timeframe is not CanonicalTimeframe.M1 for item in candles):
        raise DayOfWeekResearchError("day-of-week research v1 requires canonical 1m candles")
    symbols = {FuturesCanonicalMarket.ES: {"ES", "MES"},
               FuturesCanonicalMarket.NQ: {"NQ", "MNQ"}}[market]
    if any(item.symbol.upper() not in symbols for item in candles):
        raise DayOfWeekResearchError("candle symbol does not match explicit research market")
    if tuple(sorted(candles, key=lambda item: item.open_time)) != candles or len({x.id for x in candles}) != len(candles):
        raise DayOfWeekResearchError("candles must be unique and chronologically ordered")

    grouped: dict[date, list[HistoricalCandle]] = {}
    for item in candles:
        day = _session_date(item)
        if day is not None:
            grouped.setdefault(day, []).append(item)

    results: list[DayOfWeekFeatureV1] = []
    prior_day: date | None = None
    prior: tuple[HistoricalCandle, ...] | None = None
    for day in sorted(grouped):
        current = tuple(grouped[day])
        ids = tuple(item.id for item in current)
        if prior is None:
            setup, direction, crossed = CalendarSetup.DATA_QUALITY_FAILURE, None, None
            reasons = ("NO_PRIOR_RTH_SESSION",)
        elif not _complete(prior) or not _complete(current):
            setup, direction = CalendarSetup.DATA_QUALITY_FAILURE, None
            crossed = prior_day.isocalendar()[:2] != day.isocalendar()[:2]
            reasons = tuple(code for condition, code in (
                (not _complete(prior), "INCOMPLETE_PRIOR_RTH_SESSION"),
                (not _complete(current), "INCOMPLETE_CURRENT_RTH_SESSION"),
            ) if condition)
        else:
            prior_open, prior_close = prior[0].open, prior[-1].close
            direction = (PriorSessionDirection.UP if prior_close > prior_open else
                         PriorSessionDirection.DOWN if prior_close < prior_open else
                         PriorSessionDirection.FLAT)
            crossed = prior_day.isocalendar()[:2] != day.isocalendar()[:2]
            if crossed and direction is PriorSessionDirection.UP:
                setup, reasons = CalendarSetup.LONG_OBSERVATION, ("FIRST_SESSION_AFTER_UP_PRIOR_SESSION",)
            elif crossed and direction is PriorSessionDirection.DOWN:
                setup, reasons = CalendarSetup.SHORT_OBSERVATION, ("FIRST_SESSION_AFTER_DOWN_PRIOR_SESSION",)
            elif crossed:
                setup, reasons = CalendarSetup.NONE, ("FIRST_SESSION_AFTER_FLAT_PRIOR_SESSION",)
            else:
                setup, reasons = CalendarSetup.NONE, ("SAME_ISO_WEEK",)
        results.append(DayOfWeekFeatureV1(
            market, day, day.weekday(), prior_day,
            prior_day.weekday() if prior_day else None, crossed, direction,
            setup, reasons, ids,
        ))
        prior_day, prior = day, current
    return tuple(results)
