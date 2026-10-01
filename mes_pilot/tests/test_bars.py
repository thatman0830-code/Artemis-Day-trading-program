"""bars.py: validation, session dates, ET/DST bucket anchoring, causal aggregation,
CME closure classification and the real archive loader. No network."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from mes_pilot.bars import (Aggregator, Bar, ET, EARLY_HALT, HOLIDAY_CLOSED, MAINTENANCE, UNEXPECTED, WEEKEND,
                            bucket_bounds, classify_gap, is_exchange_holiday, load_archive_sessions, market_state,
                            session_date_for, unexpected_gap_minutes, validate_bar)

UTC = timezone.utc
ONE = timedelta(minutes=1)
REPO = Path(__file__).resolve().parents[2]
ARCHIVE = REPO / "data" / "backtests" / "es_nq_pass_b_archive_3" / "ES"
FORWARD = REPO / "data" / "futures_forward" / "ES"


def et(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(UTC)


def m1(start: datetime, o=100.0, h=101.0, low=99.0, c=100.5, v=10.0, contract="ESZ6") -> Bar:
    return Bar(start, start + ONE, o, h, low, c, v, contract, 1)


# ----------------------------------------------------------------------------- validate_bar
def test_validate_bar_accepts_valid_bar():
    assert validate_bar(m1(et(2026, 9, 15, 10))) is None


@pytest.mark.parametrize("mutate,code", [
    (dict(start=datetime(2026, 9, 15, 14), end=datetime(2026, 9, 15, 14, 1)), "NAIVE_TIMESTAMP"),
    (dict(end=et(2026, 9, 15, 10, 2)), "BAR_DURATION_MISMATCH"),
    (dict(open=math.nan), "NON_POSITIVE_OR_NAN_PRICE"),
    (dict(close=math.inf), "NON_POSITIVE_OR_NAN_PRICE"),
    (dict(low=0.0), "NON_POSITIVE_OR_NAN_PRICE"),
    (dict(high=99.5), "OHLC_INCONSISTENT"),          # high below open/close
    (dict(low=100.75), "OHLC_INCONSISTENT"),         # low above open
    (dict(volume=-1.0), "NEGATIVE_OR_NAN_VOLUME"),
    (dict(volume=math.nan), "NEGATIVE_OR_NAN_VOLUME"),
])
def test_validate_bar_faults(mutate, code):
    base = m1(et(2026, 9, 15, 10))
    fields = {**base.__dict__, **mutate}
    assert validate_bar(Bar(**fields)) == code


def test_validate_bar_rejects_misaligned_m1():
    start = et(2026, 9, 15, 10) + timedelta(seconds=30)
    assert validate_bar(Bar(start, start + ONE, 100, 101, 99, 100, 1, "ESZ6", 1)) == "MISALIGNED_TIMESTAMP"


# ----------------------------------------------------------------------------- session date
@pytest.mark.parametrize("ts,expected", [
    (et(2026, 9, 15, 17, 59), date(2026, 9, 15)),   # EDT, last minute before maintenance
    (et(2026, 9, 15, 18, 0), date(2026, 9, 16)),    # 18:00 ET starts next trade date
    (et(2025, 12, 1, 17, 59), date(2025, 12, 1)),   # EST
    (et(2025, 12, 1, 18, 0), date(2025, 12, 2)),
    (et(2026, 9, 13, 18, 0), date(2026, 9, 14)),    # Sunday open -> Monday session
    (et(2025, 11, 2, 18, 0), date(2025, 11, 3)),    # first Sunday after fall-back
    (et(2026, 3, 8, 18, 0), date(2026, 3, 9)),      # first Sunday after spring-forward
])
def test_session_date_boundary(ts, expected):
    assert session_date_for(ts) == expected


def test_session_date_uses_et_not_utc():
    # 22:30 UTC is 18:30 EDT (next session) but 17:30 EST (same session, maintenance)
    assert session_date_for(datetime(2026, 9, 15, 22, 30, tzinfo=UTC)) == date(2026, 9, 16)
    assert session_date_for(datetime(2025, 12, 1, 22, 30, tzinfo=UTC)) == date(2025, 12, 1)


def test_session_date_rejects_naive():
    with pytest.raises(ValueError):
        session_date_for(datetime(2026, 9, 15, 12))


# ----------------------------------------------------------------------------- bucket anchoring
H4_ANCHORS = {18, 22, 2, 6, 10, 14}


@pytest.mark.parametrize("ts,start_et", [
    (et(2025, 10, 31, 10, 30), (2025, 10, 31, 10)),   # EDT Friday
    (et(2025, 10, 31, 9, 59), (2025, 10, 31, 6)),
    (et(2025, 11, 2, 18, 0), (2025, 11, 2, 18)),      # EST Sunday open after fall-back
    (et(2025, 11, 3, 1, 59), (2025, 11, 2, 22)),
    (et(2025, 11, 3, 2, 0), (2025, 11, 3, 2)),
    (et(2026, 3, 6, 14, 30), (2026, 3, 6, 14)),       # EST Friday before spring-forward
    (et(2026, 3, 8, 18, 0), (2026, 3, 8, 18)),        # EDT Sunday open
    (et(2026, 3, 9, 13, 59), (2026, 3, 9, 10)),
])
def test_h4_anchored_at_18_et_across_dst(ts, start_et):
    start, end = bucket_bounds(ts, 240)
    assert start == et(*start_et)
    assert start.astimezone(ET).hour in H4_ANCHORS
    assert end - start == timedelta(hours=4)
    assert start <= ts < end


def test_h4_buckets_contiguous_through_dst_nights():
    # Minute-by-minute across both DST transition nights (markets are closed then,
    # but the bucketing must still be well-formed: contiguous, no overlaps).
    for day0 in (datetime(2025, 11, 1, 20, tzinfo=UTC), datetime(2026, 3, 7, 20, tzinfo=UTC)):
        seen = []
        ts = day0
        while ts < day0 + timedelta(hours=30):
            b = bucket_bounds(ts, 240)
            if not seen or seen[-1] != b:
                seen.append(b)
            ts += ONE
        for (s1, e1), (s2, e2) in zip(seen, seen[1:]):
            assert e1 == s2 and s1 < e1
        for s, _ in seen:
            assert s.astimezone(ET).hour in H4_ANCHORS | {3}  # 02:00 does not exist on spring-forward day
    # fall-back night: 22:00 EDT -> 02:00 EST bucket is 5 real hours
    s, e = bucket_bounds(datetime(2025, 11, 2, 6, 30, tzinfo=UTC), 240)
    assert (s, e) == (datetime(2025, 11, 2, 2, tzinfo=UTC), datetime(2025, 11, 2, 7, tzinfo=UTC))
    # spring-forward night: 22:00 EST -> 02:00(=03:00 EDT) is 4h, next to 06:00 EDT is 3h
    s, e = bucket_bounds(datetime(2026, 3, 8, 6, 30, tzinfo=UTC), 240)
    assert (s, e) == (datetime(2026, 3, 8, 3, tzinfo=UTC), datetime(2026, 3, 8, 7, tzinfo=UTC))
    s, e = bucket_bounds(datetime(2026, 3, 8, 7, 30, tzinfo=UTC), 240)
    assert (s, e) == (datetime(2026, 3, 8, 7, tzinfo=UTC), datetime(2026, 3, 8, 10, tzinfo=UTC))


@pytest.mark.parametrize("tf", [5, 15, 60])
def test_intraday_buckets_clock_aligned_in_both_dst_regimes(tf):
    for ts in (et(2025, 12, 3, 10, 37), et(2026, 7, 8, 10, 37), datetime(2025, 11, 2, 6, 37, tzinfo=UTC)):
        s, e = bucket_bounds(ts, tf)
        assert e - s == timedelta(minutes=tf)
        assert s.astimezone(ET).minute % tf == 0 and s <= ts < e


# ----------------------------------------------------------------------------- aggregation
def _run(agg: Aggregator, bars):
    emitted = []
    for b in bars:
        for done in agg.push(b):
            emitted.append((b.end, done))  # (availability time, emitted bar)
    return emitted


def test_aggregator_m5_emits_only_complete_buckets_with_exact_ohlcv():
    start = et(2026, 9, 15, 10, 0)
    rows = [(10, 12, 9, 11), (11, 15, 10, 14), (14, 14, 8, 9), (9, 10, 7, 8), (8, 9, 6, 7),
            (7, 20, 7, 19), (19, 19, 18, 18)]
    bars = [Bar(start + i * ONE, start + (i + 1) * ONE, o, h, low, c, 1 + i, "ESZ6", 1)
            for i, (o, h, low, c) in enumerate(rows)]
    agg = Aggregator(5)
    out = []
    for i, b in enumerate(bars):
        done = agg.push(b)
        if i < 4:
            assert done == []  # partial bucket is never emitted early
        out += [(b.end, d) for d in done]
    assert len(out) == 1
    avail, m5 = out[0]
    assert avail == start + 5 * ONE == m5.end  # available exactly at its close, not before
    assert (m5.start, m5.open, m5.high, m5.low, m5.close, m5.volume, m5.tf) == (start, 10, 15, 6, 7, 15, 5)
    # bucket 10:05 has 2 of 5 minutes: nothing until the clock passes 10:10
    assert agg.flush_if_due(start + 9 * ONE) == []
    late = agg.flush_if_due(start + 10 * ONE)
    assert len(late) == 1 and (late[0].open, late[0].high, late[0].close) == (7, 20, 18)


def test_aggregator_never_emits_before_bucket_end_and_no_duplicate_starts():
    # Continuous M1 bars across the fall-back night: emitted bars must be available
    # no earlier than their end and starts must be strictly increasing.
    start = datetime(2025, 11, 1, 20, tzinfo=UTC)
    bars = [m1(start + i * ONE) for i in range(60 * 14)]
    for tf in (5, 15, 60, 240):
        out = _run(Aggregator(tf), bars)
        starts = [d.start for _, d in out]
        assert starts == sorted(set(starts))
        for avail, d in out:
            assert d.end <= avail
            assert d.start < d.end


def test_aggregator_gap_emits_previous_bucket_when_next_bucket_starts():
    start = et(2026, 9, 15, 10, 0)
    agg = Aggregator(5)
    assert agg.push(m1(start)) == []
    assert agg.push(m1(start + ONE)) == []
    done = agg.push(m1(start + 7 * ONE))  # 10:07 bar: the 10:00 bucket ended at 10:05
    assert len(done) == 1 and done[0].start == start and done[0].end == start + 5 * ONE


def test_aggregator_ignores_late_and_out_of_order_bars():
    start = et(2026, 9, 15, 10, 0)
    agg = Aggregator(5)
    out = _run(agg, [m1(start + i * ONE) for i in range(5)])
    assert len(out) == 1
    assert agg.push(m1(start + 2 * ONE)) == []        # bucket already emitted: never re-opened
    agg.push(m1(start + 7 * ONE))
    assert agg.push(m1(start + 6 * ONE)) == []
    assert agg.flush_if_due(start + 10 * ONE)[0].open == 100.0


def test_h4_aggregation_on_session_uses_et_anchors():
    sess_start = et(2026, 9, 14, 18, 0)   # Sunday open (Monday session)
    bars = [m1(sess_start + i * ONE) for i in range(23 * 60)]
    out = _run(Aggregator(240), bars)
    hours = [d.start.astimezone(ET).hour for _, d in out]
    assert hours == [18, 22, 2, 6, 10]   # 14:00 bucket closes at 18:00, after the 17:00 close
    agg = Aggregator(240)
    _run(agg, bars)
    assert agg.flush_if_due(et(2026, 9, 15, 17, 59)) == []
    tail = agg.flush_if_due(et(2026, 9, 15, 18, 0))
    assert tail[0].start == et(2026, 9, 15, 14, 0) and tail[0].end == et(2026, 9, 15, 18, 0)


# ----------------------------------------------------------------------------- CME closures
def test_market_state_and_gap_classification():
    assert market_state(et(2026, 9, 15, 17, 30)) == MAINTENANCE
    assert market_state(et(2026, 9, 18, 17, 30)) == WEEKEND
    assert market_state(et(2026, 9, 19, 12, 0)) == WEEKEND
    assert market_state(et(2026, 9, 20, 17, 59)) == WEEKEND
    assert market_state(et(2026, 9, 20, 18, 0)) == "OPEN"

    def kinds(a, b):
        return [(s.kind, s.minutes) for s in classify_gap(a, b)]

    assert kinds(et(2026, 9, 15, 17), et(2026, 9, 15, 18)) == [(MAINTENANCE, 60)]
    assert kinds(et(2026, 9, 18, 17), et(2026, 9, 20, 18)) == [(WEEKEND, 2940)]
    assert kinds(et(2026, 6, 19, 13), et(2026, 6, 21, 18)) == [(EARLY_HALT, 240), (WEEKEND, 2940)]
    assert kinds(et(2025, 12, 24, 13, 15), et(2025, 12, 25, 18)) == [(EARLY_HALT, 285), (HOLIDAY_CLOSED, 1440)]
    assert kinds(et(2026, 4, 3, 9, 15), et(2026, 4, 5, 18)) == [(EARLY_HALT, 465), (WEEKEND, 2940)]
    assert kinds(et(2026, 9, 15, 10, 0), et(2026, 9, 15, 10, 3)) == [(UNEXPECTED, 3)]
    assert unexpected_gap_minutes(et(2026, 9, 15, 16, 58), et(2026, 9, 15, 18, 2)) == 4
    assert is_exchange_holiday(date(2026, 9, 7)) and not is_exchange_holiday(date(2026, 9, 8))


# ----------------------------------------------------------------------------- archive loader
def _write_rows(tmp_path: Path, rows) -> Path:
    root = tmp_path / "ES"
    (root / "normalized").mkdir(parents=True)
    with (root / "normalized" / "a.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return root


def _row(minute: int, ticker="ESZ6", day="2026-09-15", close="100.25"):
    ns = int((et(2026, 9, 15, 10) + minute * ONE).timestamp()) * 1_000_000_000
    return {"window_start_ns": ns, "open": "100", "high": "101", "low": "99.5", "close": close, "volume": "5",
            "ticker": ticker, "session_date": day, "root": "ES"}


def test_loader_sorts_dedupes_and_rejects_conflicts(tmp_path):
    root = _write_rows(tmp_path, [_row(2), _row(0), _row(1), _row(1), {**_row(0), "root": "NQ"}])
    (sess,) = load_archive_sessions([root])
    assert [b.start for b in sess.bars] == [et(2026, 9, 15, 10) + i * ONE for i in range(3)]
    assert sess.contract == "ESZ6" and sess.session_date == date(2026, 9, 15)
    conflict = _write_rows(tmp_path / "c", [_row(0), _row(0, close="100.5")])
    with pytest.raises(ValueError, match="conflicting duplicate"):
        load_archive_sessions([conflict])
    two = _write_rows(tmp_path / "t", [_row(0), _row(1, ticker="ESU6")])
    with pytest.raises(ValueError, match="one contract per session"):
        load_archive_sessions([two])


@pytest.mark.skipif(not FORWARD.exists(), reason="forward archive not present")
def test_loader_on_real_forward_archive():
    sessions = load_archive_sessions([FORWARD])
    _check_real(sessions)
    # The forward archive is append-only; newer sessions must not break this loader check.
    assert sessions[0].session_date == date(2026, 8, 27)
    assert sessions[-1].session_date >= date(2026, 9, 29)
    assert {s.contract for s in sessions if s.session_date >= date(2026, 9, 21)} == {"ESZ6"}


@pytest.mark.skipif(not ARCHIVE.exists(), reason="historical archive not present")
def test_loader_on_real_historical_archive():
    sessions = load_archive_sessions([ARCHIVE])
    _check_real(sessions)
    assert len(sessions) == 313
    assert (sessions[0].session_date, sessions[-1].session_date) == (date(2025, 6, 2), date(2026, 8, 26))
    # causal pre-declared roll: contract changes only forward, never flips back
    order = []
    for s in sessions:
        if not order or order[-1] != s.contract:
            order.append(s.contract)
    assert order == ["ESM5", "ESU5", "ESZ5", "ESH6", "ESM6", "ESU6"]


def _check_real(sessions):
    days = [s.session_date for s in sessions]
    assert days == sorted(set(days))
    for s in sessions:
        starts = [b.start for b in s.bars]
        assert starts == sorted(set(starts))
        assert all(b.contract == s.contract for b in s.bars)
        assert all(validate_bar(b) is None for b in s.bars)
        # no bar inside a scheduled closure (holiday table consistent with the data)
        assert all(market_state(b.start) == "OPEN" for b in s.bars)
