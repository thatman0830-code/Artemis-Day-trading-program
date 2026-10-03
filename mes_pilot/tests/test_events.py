"""events.py: weekly coverage, point-in-time snapshots, live staleness, blackout and
flatten boundaries, High-impact USD filter, missing calendar. No network."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from mes_pilot.events import (ET, Event, EventCalendar, LIVE_MAX_SNAPSHOT_AGE, normalize_forex_factory,
                              week_bounds)

UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]
CAL_DIR = REPO / "data" / "mes_pilot" / "calendar"
KW = dict(currencies=("USD",), impacts=("High",), before_min=10, after_min=15, flatten_before_min=5, required=True)


def et(y, m, d, hh, mm=0, ss=0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET).astimezone(UTC)


DAY = date(2026, 10, 2)                     # Friday
NFP = et(2026, 10, 2, 8, 30)


def cal(events, days=(DAY,)) -> EventCalendar:
    return EventCalendar(list(events), set(days), "TEST")


def ff_row(title, when_et: datetime, currency="USD", impact="High"):
    return {"title": title, "country": currency, "date": when_et.astimezone(ET).isoformat(), "impact": impact,
            "forecast": "", "previous": ""}


# ----------------------------------------------------------------------------- week coverage
@pytest.mark.parametrize("day", [date(2026, 9, 27), date(2026, 9, 28), date(2026, 10, 2), date(2026, 10, 3)])
def test_week_bounds_sunday_to_saturday(day):
    assert week_bounds(day) == (date(2026, 9, 27), date(2026, 10, 3))


def test_normalize_uses_et_week_and_rejects_multi_week():
    # Sunday 21:30 ET is already Monday in UTC; the week must still start that Sunday.
    rows = [ff_row("Early", et(2026, 9, 6, 21, 30), "JPY", "Low"), ff_row("CPI m/m", et(2026, 9, 11, 8, 30))]
    doc = normalize_forex_factory(rows, retrieved_at=datetime(2026, 9, 8, tzinfo=UTC), source_sha256="x")
    assert doc["coverage"] == ["2026-09-06", "2026-09-12"]
    assert doc["schema_version"] == "mes-pilot-calendar-v1"
    with pytest.raises(ValueError, match="weeks"):
        normalize_forex_factory(rows + [ff_row("Next", et(2026, 9, 14, 8, 30))],
                                retrieved_at=datetime(2026, 9, 8, tzinfo=UTC), source_sha256="x")
    with pytest.raises(ValueError):
        normalize_forex_factory(rows, retrieved_at=datetime(2026, 9, 8), source_sha256="x")
    with pytest.raises(ValueError):
        normalize_forex_factory([], retrieved_at=datetime(2026, 9, 8, tzinfo=UTC), source_sha256="x")


# ----------------------------------------------------------------------------- blackout / flatten
@pytest.mark.parametrize("now,blackout", [
    (NFP - timedelta(minutes=10, seconds=1), False),
    (NFP - timedelta(minutes=10), True),        # -10 inclusive
    (NFP, True),
    (NFP + timedelta(minutes=15), True),        # +15 inclusive
    (NFP + timedelta(minutes=15, seconds=1), False),
])
def test_blackout_boundaries(now, blackout):
    st = cal([Event("Non-Farm Employment Change", "USD", "High", NFP)]).status(now, DAY, **KW)
    assert st.calendar_available and st.in_blackout is blackout
    assert st.reason == ("EVENT_BLACKOUT" if blackout else None)
    assert not st.flatten_required  # no position -> nothing to flatten


@pytest.mark.parametrize("now,flatten", [
    (NFP - timedelta(minutes=5, seconds=1), False),
    (NFP - timedelta(minutes=5), True),         # flatten 5 min before
    (NFP + timedelta(minutes=15), True),
    (NFP + timedelta(minutes=15, seconds=1), False),
])
def test_flatten_boundaries_for_open_position(now, flatten):
    st = cal([Event("NFP", "USD", "High", NFP)]).status(now, DAY, holding_until=now + timedelta(minutes=30), **KW)
    assert st.flatten_required is flatten


def test_only_high_impact_usd_counts():
    events = [Event("ECB", "EUR", "High", NFP), Event("ISM", "USD", "Medium", NFP), Event("Bank Holiday", "USD", "Holiday", NFP)]
    st = cal(events).status(NFP, DAY, holding_until=NFP + timedelta(minutes=30), **KW)
    assert not st.in_blackout and not st.flatten_required and st.reason is None


def test_missing_calendar_blocks_when_required():
    st = EventCalendar.empty().status(NFP, DAY, **KW)
    assert (st.calendar_available, st.reason, st.detail) == (False, "CALENDAR_UNAVAILABLE", "NO_COVERAGE")
    st = cal([], days=()).status(NFP, DAY, **{**KW, "required": False})
    assert (st.calendar_available, st.reason, st.in_blackout) == (False, "CALENDAR_NOT_REQUIRED_DIAGNOSTIC", False)


# ----------------------------------------------------------------------------- files: point-in-time / staleness
def _write_week(directory: Path, snapshots: list[tuple[datetime, list[dict]]], name="ff-week-2026-09-27.json"):
    entries = []
    for retrieved, rows in snapshots:
        doc = normalize_forex_factory(rows, retrieved_at=retrieved, source_sha256=f"sha-{retrieved.isoformat()}")
        entries.append(doc)
    latest = entries[-1]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps({**latest, "snapshots": [
        {"source_sha256": e["source_sha256"], "retrieved_at": e["retrieved_at"], "events": e["events"]}
        for e in entries]}), encoding="utf-8")


def test_point_in_time_snapshot_selection(tmp_path):
    first = et(2026, 9, 28, 21, 29)        # Monday evening
    second = et(2026, 10, 1, 12, 0)        # Thursday noon: adds an event
    base = [ff_row("Non-Farm Employment Change", NFP), ff_row("Low thing", et(2026, 9, 28, 6), "GBP", "Low")]
    added = base + [ff_row("Fed Chair Speaks", et(2026, 10, 1, 12, 5))]
    _write_week(tmp_path, [(first, base), (second, added)])
    c = EventCalendar.load_dir(tmp_path)
    # Monday's session was decided before any snapshot existed -> unavailable
    st = c.status(et(2026, 9, 28, 10), date(2026, 9, 28), **KW)
    assert (st.reason, st.detail) == ("CALENDAR_UNAVAILABLE", "NOT_YET_RETRIEVED")
    # 11:59 decision: inside the added event's -10 window, but only the Monday snapshot was known
    st = c.status(et(2026, 10, 1, 11, 59), date(2026, 10, 1), **KW)
    assert st.calendar_available and not st.in_blackout and st.detail == f"sha-{first.isoformat()}"
    st = c.status(et(2026, 10, 1, 12, 1), date(2026, 10, 1), **KW)
    assert st.in_blackout and st.event_titles == ("Fed Chair Speaks",) and st.detail == f"sha-{second.isoformat()}"
    # without point-in-time the latest snapshot covers the whole week (replay diagnostics only)
    loose = EventCalendar.load_dir(tmp_path, point_in_time=False)
    assert loose.status(et(2026, 9, 28, 10), date(2026, 9, 28), **KW).calendar_available
    # outside the week
    assert c.status(et(2026, 10, 5, 10), date(2026, 10, 5), **KW).detail == "NO_COVERAGE"


def test_live_staleness_requires_snapshot_within_7_days(tmp_path):
    retrieved = et(2026, 9, 25, 9, 0)       # retrieved before the week (e.g. a next-week feed)
    _write_week(tmp_path, [(retrieved, [ff_row("NFP", NFP)])])
    live = EventCalendar.load_for_live(tmp_path)
    assert live.max_snapshot_age == LIVE_MAX_SNAPSHOT_AGE == timedelta(days=7)
    ok = live.status(retrieved + timedelta(days=7), date(2026, 10, 2), **KW)
    assert ok.calendar_available
    stale = live.status(retrieved + timedelta(days=7, seconds=1), date(2026, 10, 2), **KW)
    assert (stale.reason, stale.detail) == ("CALENDAR_UNAVAILABLE", "STALE_SNAPSHOT")
    # replay mode (no live age rule) still uses it
    assert EventCalendar.load_dir(tmp_path).status(retrieved + timedelta(days=8), date(2026, 10, 2), **KW).calendar_available


def test_corrupt_or_foreign_files_give_no_coverage(tmp_path):
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "other.json").write_text(json.dumps({"schema_version": "something-else"}), encoding="utf-8")
    (tmp_path / "two-weeks.json").write_text(json.dumps({"schema_version": "mes-pilot-calendar-v1",
                                                         "coverage": ["2026-09-27", "2026-10-10"], "events": []}),
                                             encoding="utf-8")
    c = EventCalendar.load_dir(tmp_path)
    assert len(c.load_errors) == 2 and not c.covered_days
    assert c.status(NFP, DAY, **KW).reason == "CALENDAR_UNAVAILABLE"


def test_naive_decision_time_rejected():
    with pytest.raises(ValueError):
        cal([]).status(datetime(2026, 10, 2, 12), DAY, **KW)


# ----------------------------------------------------------------------------- generated calendar
@pytest.mark.skipif(not (CAL_DIR / "ff-week-2026-09-27.json").exists(), reason="imported calendar not present")
def test_imported_calendar_point_in_time_and_live():
    c = EventCalendar.load_dir(CAL_DIR)
    assert {d for d in c.covered_days} >= {date(2026, 9, 6) + timedelta(days=i) for i in range(28)}
    # week of 27 Sep: first snapshot 2026-09-29 01:29 UTC (Mon 21:29 ET)
    assert c.status(et(2026, 9, 28, 10), date(2026, 9, 28), **KW).detail == "NOT_YET_RETRIEVED"
    assert c.status(et(2026, 9, 29, 10), date(2026, 9, 29), **KW).calendar_available
    st = c.status(et(2026, 10, 2, 8, 25), date(2026, 10, 2), **KW)
    assert st.in_blackout and "Non-Farm Employment Change" in st.event_titles
    live = EventCalendar.load_for_live(CAL_DIR)
    assert live.status(et(2026, 10, 2, 10), date(2026, 10, 2), **KW).calendar_available
    assert live.status(et(2026, 10, 5, 10), date(2026, 10, 5), **KW).detail == "NO_COVERAGE"
