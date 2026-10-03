"""Scheduled-event risk filter (master spec page 9).

News is a risk/liquidity filter only; it never sets direction. A session whose
calendar coverage is missing or stale blocks NEW entries; protective exits
continue. Calendar files are normalized JSON written by
``scripts/import_mes_pilot_calendar.py`` (Forex Factory weekly feed).

Coverage semantics
------------------
* A Forex Factory weekly snapshot covers one week, Sunday..Saturday on the
  America/New_York calendar. A CME session date (Mon..Fri, the trade date that
  starts 18:00 ET the evening before) is covered when its date lies inside the
  week; the Sunday-evening open belongs to Monday's session, same week.
* Point-in-time (default when loading files): a snapshot can only be used for
  a decision at ``now`` if it was retrieved at or before ``now``. Among usable
  snapshots covering the session date the most recently retrieved one wins.
* Live staleness: ``max_snapshot_age`` (7 days for live sessions) further
  requires the chosen snapshot to be retrieved within that age of ``now``.
* No usable snapshot => ``CALENDAR_UNAVAILABLE`` when the calendar is required.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import glob
import json

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
SCHEMA_VERSION = "mes-pilot-calendar-v1"
LIVE_MAX_SNAPSHOT_AGE = timedelta(days=7)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Event:
    title: str
    currency: str
    impact: str
    scheduled_at: datetime


@dataclass(frozen=True)
class EventStatus:
    calendar_available: bool
    in_blackout: bool
    flatten_required: bool
    event_titles: tuple[str, ...]
    reason: str | None
    detail: str | None = None  # NO_COVERAGE | NOT_YET_RETRIEVED | STALE_SNAPSHOT | snapshot sha256


@dataclass(frozen=True)
class CalendarSnapshot:
    coverage_start: date
    coverage_end: date
    retrieved_at: datetime | None
    source_sha256: str
    events: tuple[Event, ...]

    def covers(self, day: date) -> bool:
        return self.coverage_start <= day <= self.coverage_end


def week_bounds(day: date) -> tuple[date, date]:
    """Sunday..Saturday week containing ``day`` (ET calendar dates)."""
    start = day - timedelta(days=(day.weekday() + 1) % 7)
    return start, start + timedelta(days=6)


def _parse_ts(text: str) -> datetime:
    ts = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        raise ValueError(f"naive timestamp in calendar: {text}")
    return ts.astimezone(UTC)


def _events(rows) -> tuple[Event, ...]:
    out: dict[tuple, Event] = {}
    for e in rows:
        ev = Event(str(e["title"]), str(e["currency"]), str(e["impact"]), _parse_ts(e["scheduled_at"]))
        out[(ev.title, ev.currency, ev.impact, ev.scheduled_at)] = ev
    return tuple(sorted(out.values(), key=lambda e: (e.scheduled_at, e.currency, e.title)))


class EventCalendar:
    def __init__(self, events: list[Event], covered_days: set[date], source: str, *,
                 snapshots: list[CalendarSnapshot] | None = None, point_in_time: bool = False,
                 max_snapshot_age: timedelta | None = None, load_errors: list[str] | None = None):
        self.events = sorted(events, key=lambda e: e.scheduled_at)
        self.covered_days = set(covered_days)
        self.source = source
        self.snapshots = sorted(snapshots or [], key=lambda s: s.retrieved_at or _EPOCH)
        self.point_in_time = point_in_time
        self.max_snapshot_age = max_snapshot_age
        self.load_errors = list(load_errors or [])

    # ------------------------------------------------------------------ loading
    @classmethod
    def load_dir(cls, directory: Path, *, point_in_time: bool = True,
                 max_snapshot_age: timedelta | None = None) -> "EventCalendar":
        """Load normalized weekly files. ``point_in_time`` refuses snapshots
        retrieved after the decision time; ``max_snapshot_age`` (live: 7 days)
        refuses stale snapshots. Unreadable files are skipped (no coverage) and
        listed in ``load_errors``."""
        snapshots: list[CalendarSnapshot] = []
        errors: list[str] = []
        for path in sorted(glob.glob(str(Path(directory) / "*.json"))):
            try:
                doc = json.loads(Path(path).read_text(encoding="utf-8"))
                if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_VERSION:
                    continue
                snapshots.extend(_snapshots_from_doc(doc))
            except (ValueError, KeyError, TypeError, OSError) as exc:
                errors.append(f"{Path(path).name}: {type(exc).__name__}: {exc}")
        events: dict[tuple, Event] = {}
        covered: set[date] = set()
        for snap in snapshots:
            day = snap.coverage_start
            while day <= snap.coverage_end:
                covered.add(day)
                day += timedelta(days=1)
            for ev in snap.events:
                events[(ev.title, ev.currency, ev.impact, ev.scheduled_at)] = ev
        return cls(list(events.values()), covered, str(directory), snapshots=snapshots,
                   point_in_time=point_in_time, max_snapshot_age=max_snapshot_age, load_errors=errors)

    @classmethod
    def load_for_live(cls, directory: Path) -> "EventCalendar":
        """Live sessions: point-in-time and a snapshot retrieved within 7 days."""
        return cls.load_dir(directory, point_in_time=True, max_snapshot_age=LIVE_MAX_SNAPSHOT_AGE)

    @classmethod
    def empty(cls) -> "EventCalendar":
        return cls([], set(), "NONE")

    # ------------------------------------------------------------------ coverage
    def coverage(self, session_day: date, now: datetime) -> tuple[bool, str, tuple[Event, ...]]:
        """Return (available, detail, events usable for a decision at ``now``)."""
        if not self.snapshots:
            # Hand-built calendar (tests / legacy constructor): plain day coverage.
            if session_day in self.covered_days:
                return True, "COVERED", tuple(self.events)
            return False, "NO_COVERAGE", ()
        covering = [s for s in self.snapshots if s.covers(session_day)]
        if not covering:
            return False, "NO_COVERAGE", ()
        if self.point_in_time or self.max_snapshot_age is not None:
            covering = [s for s in covering if s.retrieved_at is not None]
            if not covering:
                return False, "NO_RETRIEVAL_TIME", ()
        if self.point_in_time:
            covering = [s for s in covering if s.retrieved_at <= now]
            if not covering:
                return False, "NOT_YET_RETRIEVED", ()
        chosen = max(covering, key=lambda s: s.retrieved_at or _EPOCH)
        if self.max_snapshot_age is not None and now - chosen.retrieved_at > self.max_snapshot_age:
            return False, "STALE_SNAPSHOT", ()
        return True, chosen.source_sha256 or "COVERED", chosen.events

    def status(self, now: datetime, session_day: date, *, currencies, impacts, before_min: int,
               after_min: int, flatten_before_min: int, required: bool, holding_until: datetime | None = None) -> EventStatus:
        """Blackout: ``-before_min <= minutes(now - event) <= +after_min`` (both inclusive).

        Flatten: an open position that could still be held at the event is
        flattened from ``flatten_before_min`` before the event through the end
        of the after-window. Only events whose currency and impact match the
        configured sets (USD / High) count. Direction is never inferred.
        """
        if now.tzinfo is None:
            raise ValueError("naive decision time")
        available, detail, events = self.coverage(session_day, now)
        if not available:
            if required:
                return EventStatus(False, False, False, (), "CALENDAR_UNAVAILABLE", detail)
            return EventStatus(False, False, False, (), "CALENDAR_NOT_REQUIRED_DIAGNOSTIC", detail)
        cur = {str(c).upper() for c in currencies}
        imp = {str(i).lower() for i in impacts}
        relevant = [e for e in events if e.currency.upper() in cur and e.impact.lower() in imp]
        blackout, flatten, titles = False, False, []
        for e in relevant:
            delta_min = (now - e.scheduled_at).total_seconds() / 60
            if -before_min <= delta_min <= after_min:
                blackout = True
                titles.append(e.title)
            if (holding_until is not None and -flatten_before_min <= delta_min <= after_min
                    and holding_until >= e.scheduled_at - timedelta(minutes=flatten_before_min)):
                flatten = True
                titles.append(e.title)
        return EventStatus(True, blackout, flatten, tuple(sorted(set(titles))),
                           "EVENT_BLACKOUT" if blackout else None, detail)


def _snapshots_from_doc(doc: dict) -> list[CalendarSnapshot]:
    start, end = date.fromisoformat(doc["coverage"][0]), date.fromisoformat(doc["coverage"][1])
    if end < start or (end - start).days > 6:
        raise ValueError(f"coverage {start}..{end} is not a single week")
    entries = doc.get("snapshots") or [doc]
    out = []
    for entry in entries:
        retrieved = entry.get("retrieved_at")
        out.append(CalendarSnapshot(start, end, _parse_ts(retrieved) if retrieved else None,
                                    str(entry.get("source_sha256", "")), _events(entry["events"])))
    return out


def normalize_forex_factory(raw_rows: list[dict], *, retrieved_at: datetime, source_sha256: str) -> dict:
    """Convert one Forex Factory weekly JSON list into the pilot calendar schema.

    The week (Sunday..Saturday) is derived from the events' America/New_York
    dates. A list spanning more than one such week is rejected: it is not a
    weekly snapshot and cannot vouch for complete coverage of any week.
    """
    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    if not isinstance(raw_rows, list):
        raise ValueError("calendar list required")
    events = []
    weeks = set()
    for row in raw_rows:
        if not isinstance(row, dict) or not {"title", "country", "date", "impact"} <= set(row):
            raise ValueError("calendar event schema rejected")
        when = _parse_ts(row["date"])
        weeks.add(week_bounds(when.astimezone(ET).date()))
        events.append({"title": str(row["title"]).strip(), "currency": str(row["country"]).strip().upper(),
                       "impact": str(row["impact"]).strip(), "scheduled_at": when.isoformat(),
                       "scheduled_at_et": when.astimezone(ET).isoformat(),
                       "forecast": str(row.get("forecast", "")), "previous": str(row.get("previous", ""))})
    if not events:
        raise ValueError("empty calendar")
    if len(weeks) != 1:
        raise ValueError(f"calendar spans {len(weeks)} weeks; expected one Sunday..Saturday ET week")
    (week_start, week_end), = weeks
    unique = {(e["title"], e["currency"], e["impact"], e["scheduled_at"]): e for e in events}
    ordered = sorted(unique.values(), key=lambda e: (e["scheduled_at"], e["currency"], e["title"]))
    return {"schema_version": SCHEMA_VERSION, "source": "FOREX_FACTORY_WEEKLY",
            "source_sha256": source_sha256, "retrieved_at": retrieved_at.astimezone(UTC).isoformat(),
            "coverage": [week_start.isoformat(), week_end.isoformat()], "events": ordered}
