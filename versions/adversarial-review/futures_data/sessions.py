from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from .contracts import utc

CHICAGO = ZoneInfo("America/Chicago")


class IntervalClassification(str, Enum):
    OPEN = "OPEN"
    MAINTENANCE = "MAINTENANCE"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"
    EARLY_CLOSE = "EARLY_CLOSE"
    LEGITIMATE_NO_TRADE = "LEGITIMATE_NO_TRADE"
    UNEXPLAINED_MISSING = "UNEXPLAINED_MISSING"


@dataclass(frozen=True)
class SessionCalendar:
    holidays: frozenset[date] = frozenset()
    early_closes: tuple[tuple[date, time], ...] = ()
    version: str = "owner-cme-session-v1"

    def __post_init__(self) -> None:
        if tuple(sorted(self.early_closes)) != self.early_closes:
            raise ValueError("early-close facts must be deterministic")

    def trading_date(self, instant: datetime) -> date:
        local = utc(instant, "instant").astimezone(CHICAGO)
        return local.date() + timedelta(days=1) if local.time() >= time(17) else local.date()

    def classify(self, instant: datetime, *, observed_no_trade: bool = False) -> IntervalClassification:
        local = utc(instant, "instant").astimezone(CHICAGO)
        trading = self.trading_date(instant)
        if trading in self.holidays: return IntervalClassification.HOLIDAY
        if local.weekday() == 5 or (local.weekday() == 6 and local.time() < time(17)):
            return IntervalClassification.WEEKEND
        if time(16) <= local.time() < time(17): return IntervalClassification.MAINTENANCE
        early = dict(self.early_closes).get(trading)
        if early is not None and early <= local.time() < time(16): return IntervalClassification.EARLY_CLOSE
        return IntervalClassification.LEGITIMATE_NO_TRADE if observed_no_trade else IntervalClassification.OPEN


@dataclass(frozen=True)
class GapFact:
    start: datetime
    end: datetime
    classification: IntervalClassification
    missing_minutes: int


def classify_gaps(times: tuple[datetime, ...], calendar: SessionCalendar) -> tuple[GapFact, ...]:
    if tuple(sorted(times)) != times or len(set(times)) != len(times):
        raise ValueError("timestamps must be unique and ordered")
    facts = []
    for left, right in zip(times, times[1:]):
        utc(left, "timestamp"); utc(right, "timestamp")
        cursor = left + timedelta(minutes=1)
        while cursor < right:
            kind = calendar.classify(cursor)
            run_start = cursor
            while cursor < right and calendar.classify(cursor) is kind:
                cursor += timedelta(minutes=1)
            facts.append(GapFact(run_start, cursor, kind, int((cursor-run_start).total_seconds()/60)))
    return tuple(facts)

