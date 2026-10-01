"""Completed-bar data model, loaders and causal multi-timeframe aggregation.

A bar is usable only at ``end`` (its availability time). Aggregated bars are
emitted only when their bucket is complete, i.e. when the first M1 bar of the
next bucket arrives or the bucket's end time has passed. Nothing here looks at
a bar before it is complete.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import glob
import json
import math

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
ONE_MIN = timedelta(minutes=1)


@dataclass(frozen=True)
class Bar:
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    contract: str
    tf: int  # minutes

    @property
    def available_at(self) -> datetime:
        return self.end

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_bar(bar: Bar) -> str | None:
    """Return a fault code, or None when the bar is structurally valid."""
    if bar.start.tzinfo is None or bar.end.tzinfo is None:
        return "NAIVE_TIMESTAMP"
    if bar.end - bar.start != timedelta(minutes=bar.tf):
        return "BAR_DURATION_MISMATCH"
    if bar.tf == 1 and (bar.start.second or bar.start.microsecond):
        return "MISALIGNED_TIMESTAMP"
    prices = (bar.open, bar.high, bar.low, bar.close)
    if any(not _finite_number(p) or p <= 0 for p in prices):
        return "NON_POSITIVE_OR_NAN_PRICE"
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.low > bar.high:
        return "OHLC_INCONSISTENT"
    if not _finite_number(bar.volume) or bar.volume < 0:
        return "NEGATIVE_OR_NAN_VOLUME"
    return None


def _from_archive_row(row: dict) -> Bar:
    start = datetime.fromtimestamp(int(row["window_start_ns"]) / 1e9, tz=UTC)
    return Bar(start, start + ONE_MIN, float(row["open"]), float(row["high"]), float(row["low"]),
               float(row["close"]), float(row["volume"]), str(row["ticker"]), 1)


def _from_live_row(row: dict) -> Bar:
    start = datetime.fromisoformat(str(row["open_time"]).replace("Z", "+00:00"))
    end = datetime.fromisoformat(str(row["close_time"]).replace("Z", "+00:00"))
    return Bar(start, end, float(row["open"]), float(row["high"]), float(row["low"]),
               float(row["close"]), float(row.get("volume") or 0), str(row["symbol"]), 1)


@dataclass(frozen=True)
class SessionBars:
    session_date: date
    contract: str
    bars: tuple[Bar, ...]
    source: str


def load_archive_sessions(roots: list[Path], *, root_symbol: str = "ES",
                          start: date | None = None, end: date | None = None) -> list[SessionBars]:
    """Load normalized ES/NQ archive rows grouped by CME session date.

    The archive assigns exactly one contract per session (its pre-declared roll
    schedule), so no look-ahead roll choice is made here.
    """
    per_session: dict[str, dict[str, list[Bar]]] = {}
    sources: dict[str, str] = {}
    for root in roots:
        for path in sorted(glob.glob(str(Path(root) / "normalized" / "*.jsonl"))):
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("root") != root_symbol:
                        continue
                    day = row["session_date"]
                    if start and date.fromisoformat(day) < start:
                        continue
                    if end and date.fromisoformat(day) > end:
                        continue
                    per_session.setdefault(day, {}).setdefault(row["ticker"], []).append(_from_archive_row(row))
                    sources.setdefault(day, str(Path(path).parent.parent))
    sessions = []
    for day in sorted(per_session):
        tickers = per_session[day]
        if len(tickers) != 1:
            raise ValueError(f"{day}: expected one contract per session, got {sorted(tickers)}")
        (contract, bars), = tickers.items()
        unique: dict[datetime, Bar] = {}
        for b in bars:
            prev = unique.get(b.start)
            if prev is not None and prev != b:
                raise ValueError(f"{day}: conflicting duplicate rows for {contract} at {b.start.isoformat()}")
            unique[b.start] = b
        ordered = tuple(unique[k] for k in sorted(unique))
        sessions.append(SessionBars(date.fromisoformat(day), contract, ordered, sources[day]))
    return sessions


def load_live_bars(path: Path, symbol_prefix: str = "ES") -> list[Bar]:
    bars = {}
    if not Path(path).exists():
        return []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not str(row.get("symbol", "")).startswith(symbol_prefix):
            continue
        bar = _from_live_row(row)
        bars[(bar.contract, bar.start)] = bar
    return [bars[k] for k in sorted(bars, key=lambda k: k[1])]


def session_date_for(ts: datetime, rollover_hour: int = 18) -> date:
    """CME equity trading day: 18:00 ET starts the next day's session.

    Pure clock rule (DST-aware). It does not merge exchange-holiday mornings
    into the next trade date the way the archive's ``session_date`` does
    (e.g. archive 2025-06-20 contains the 2025-06-19 Juneteenth halted
    session); use ``is_exchange_holiday`` to recognise those days.
    """
    if ts.tzinfo is None:
        raise ValueError("naive timestamp")
    local = ts.astimezone(ET)
    return (local + timedelta(days=1)).date() if local.hour >= rollover_hour else local.date()


# --------------------------------------------------------------------------- CME calendar
# CME Globex equity-index futures (ES/MES) closures, ET wall clock.
# EARLY_HALTS: calendar date -> ET time trading halts; Globex reopens 18:00 ET
# (the reopened session belongs to the next trade date). Exchange holidays with
# an abbreviated Globex session (MLK, Presidents, Memorial, Juneteenth, July 4,
# Labor, Thanksgiving) halt at 13:00 ET; day-before/after early closes at 13:15 ET.
# FULL_CLOSURES: no trading from 18:00 ET the evening before until 18:00 ET.
# Sources: CME holiday calendars; every 2025-06..2026-09 entry is confirmed by
# the last bar of that day in the ES archive. 2026-11/12 entries are scheduled,
# not yet observed -- re-verify against the CME holiday calendar each year.
CME_EQUITY_EARLY_HALTS_ET: dict[date, time] = {
    date(2025, 1, 20): time(13, 0), date(2025, 2, 17): time(13, 0), date(2025, 5, 26): time(13, 0),
    date(2025, 6, 19): time(13, 0), date(2025, 7, 3): time(13, 15), date(2025, 7, 4): time(13, 0),
    date(2025, 9, 1): time(13, 0), date(2025, 11, 27): time(13, 0), date(2025, 11, 28): time(13, 15),
    date(2025, 12, 24): time(13, 15),
    date(2026, 1, 19): time(13, 0), date(2026, 2, 16): time(13, 0), date(2026, 4, 3): time(9, 15),
    date(2026, 5, 25): time(13, 0), date(2026, 6, 19): time(13, 0), date(2026, 7, 3): time(13, 0),
    date(2026, 9, 7): time(13, 0), date(2026, 11, 26): time(13, 0), date(2026, 11, 27): time(13, 15),
    date(2026, 12, 24): time(13, 15),
}
CME_EQUITY_FULL_CLOSURES: frozenset[date] = frozenset({
    date(2025, 1, 1), date(2025, 4, 18), date(2025, 12, 25), date(2026, 1, 1), date(2026, 12, 25), date(2027, 1, 1),
})
# Calendar dates that are exchange holidays (cash market closed). A pilot
# should not treat their thin, halted Globex mornings as normal sessions.
CME_EQUITY_HOLIDAYS: frozenset[date] = frozenset(
    {d for d, t in CME_EQUITY_EARLY_HALTS_ET.items() if t == time(13, 0)} | {date(2026, 4, 3)}
) | CME_EQUITY_FULL_CLOSURES
CALENDAR_VALID_THROUGH = date(2027, 1, 1)

OPEN = "OPEN"
MAINTENANCE = "MAINTENANCE"
WEEKEND = "WEEKEND"
EARLY_HALT = "EARLY_HALT"
HOLIDAY_CLOSED = "HOLIDAY_CLOSED"
UNEXPECTED = "UNEXPECTED_MISSING"


def market_state(ts: datetime) -> str:
    """Expected CME Globex equity-index state for the minute starting at ``ts``."""
    if ts.tzinfo is None:
        raise ValueError("naive timestamp")
    local = ts.astimezone(ET)
    day, clock, wd = local.date(), local.time(), local.weekday()
    if wd == 5 or (wd == 4 and clock >= time(17)) or (wd == 6 and clock < time(18)):
        return WEEKEND
    if day in CME_EQUITY_FULL_CLOSURES and clock < time(18):
        return HOLIDAY_CLOSED
    if (day + timedelta(days=1)) in CME_EQUITY_FULL_CLOSURES and clock >= time(18):
        return HOLIDAY_CLOSED
    halt = CME_EQUITY_EARLY_HALTS_ET.get(day)
    if halt is not None and halt <= clock < time(18):
        return EARLY_HALT
    if time(17) <= clock < time(18):
        return MAINTENANCE
    return OPEN


@dataclass(frozen=True)
class GapSegment:
    start: datetime
    end: datetime
    kind: str        # MAINTENANCE | WEEKEND | EARLY_HALT | HOLIDAY_CLOSED | UNEXPECTED_MISSING
    minutes: int


def classify_gap(prev_end: datetime, next_start: datetime) -> tuple[GapSegment, ...]:
    """Classify the missing minutes in [prev_end, next_start) between two M1 bars.

    Minutes the exchange is expected to be open are UNEXPECTED_MISSING (a
    data fault or a no-trade minute); scheduled closures are labelled so they
    are not mistaken for faults.
    """
    if prev_end.tzinfo is None or next_start.tzinfo is None:
        raise ValueError("naive timestamp")
    segments: list[GapSegment] = []
    cursor = prev_end.astimezone(UTC)
    stop = next_start.astimezone(UTC)
    while cursor < stop:
        state = market_state(cursor)
        kind = UNEXPECTED if state == OPEN else state
        run_start = cursor
        while cursor < stop and (UNEXPECTED if market_state(cursor) == OPEN else market_state(cursor)) == kind:
            cursor += ONE_MIN
        segments.append(GapSegment(run_start, cursor, kind, int((cursor - run_start).total_seconds() // 60)))
    return tuple(segments)


def unexpected_gap_minutes(prev_end: datetime, next_start: datetime) -> int:
    return sum(seg.minutes for seg in classify_gap(prev_end, next_start) if seg.kind == UNEXPECTED)


def is_exchange_holiday(day: date) -> bool:
    return day in CME_EQUITY_HOLIDAYS


def bucket_bounds(ts: datetime, tf: int) -> tuple[datetime, datetime]:
    """UTC [start, end) of the tf-minute bucket containing ``ts``.

    tf <= 60: aligned to the clock (ET offsets are whole hours, so UTC and ET
    minute/hour alignment coincide, including the repeated fall-back hour).
    tf > 60 (H4): boundaries sit on the ET wall clock at 18:00 + k*tf
    (18,22,02,06,10,14 ET for H4), so the 18:00 ET anchor is stable across
    DST. A bucket containing a DST transition is longer/shorter than tf in
    real time; CME equity futures are closed at 02:00 ET on Sundays, so this
    never affects a traded bar.
    """
    if ts.tzinfo is None:
        raise ValueError("naive timestamp")
    utc_ts = ts.astimezone(UTC)
    if tf <= 60:
        if 60 % tf:
            raise ValueError(f"unsupported timeframe {tf}")
        floor = utc_ts.replace(second=0, microsecond=0)
        start = floor - timedelta(minutes=floor.minute % tf)
        return start, start + timedelta(minutes=tf)
    if tf % 60 or 24 % (tf // 60):
        raise ValueError(f"unsupported timeframe {tf}")
    hours = tf // 60
    local = utc_ts.astimezone(ET)
    anchor_day = local.date() if local.hour >= 18 else local.date() - timedelta(days=1)
    anchor = datetime(anchor_day.year, anchor_day.month, anchor_day.day, 18)  # naive ET wall time
    bounds = [datetime.combine((anchor + timedelta(hours=hours * k)).date(),
                               (anchor + timedelta(hours=hours * k)).time(), ET).astimezone(UTC)
              for k in range(24 // hours + 1)]
    for left, right in zip(bounds, bounds[1:]):
        if left <= utc_ts < right:
            return left, right
    raise AssertionError("bucket bounds not found")  # pragma: no cover


def bucket_start(ts: datetime, tf: int) -> datetime:
    """Start (UTC) of the ET-anchored tf-minute bucket containing ``ts``."""
    return bucket_bounds(ts, tf)[0]


class Aggregator:
    """Incrementally builds completed higher-timeframe bars from M1 bars.

    A bucket is emitted only when (a) the M1 bar ending at the bucket's end
    arrives, (b) the first M1 bar of a later bucket arrives, or (c)
    ``flush_if_due`` is called with a clock at/after the bucket end. A bucket
    is therefore never emitted before its end time. Buckets with missing
    minutes are emitted at their end with the minutes that exist.
    """

    def __init__(self, tf: int):
        self.tf = tf
        self._bucket: datetime | None = None
        self._bucket_end: datetime | None = None
        self._parts: list[Bar] = []
        self._last_emitted_start: datetime | None = None

    def _emit(self) -> Bar | None:
        parts, start, end = self._parts, self._bucket, self._bucket_end
        self._parts, self._bucket, self._bucket_end = [], None, None
        if not parts or start is None:
            return None
        if self._last_emitted_start is not None and start <= self._last_emitted_start:
            return None
        self._last_emitted_start = start
        return Bar(start, end, parts[0].open, max(p.high for p in parts), min(p.low for p in parts),
                   parts[-1].close, sum(p.volume for p in parts), parts[-1].contract, self.tf)

    def push(self, bar: Bar) -> list[Bar]:
        """Add an M1 bar; return any higher-timeframe bars completed by it."""
        out = []
        start, end = bucket_bounds(bar.start, self.tf)
        if self._last_emitted_start is not None and start <= self._last_emitted_start:
            return out  # late bar for an already-emitted bucket: never re-open it
        if self._bucket is not None and start != self._bucket:
            if start < self._bucket:
                return out  # out-of-order bar for an earlier bucket
            done = self._emit()
            if done is not None:
                out.append(done)
        self._bucket, self._bucket_end = start, end
        self._parts.append(bar)
        if bar.end >= end:
            done = self._emit()
            if done is not None:
                out.append(done)
        return out

    def flush_if_due(self, now: datetime) -> list[Bar]:
        """Close a bucket whose end time has passed with missing trailing minutes."""
        if self._bucket_end is not None and now >= self._bucket_end:
            done = self._emit()
            return [done] if done else []
        return []

    def reset(self):
        self._bucket = None
        self._bucket_end = None
        self._parts = []
        self._last_emitted_start = None
