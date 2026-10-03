"""M1 data-coverage bookkeeping and fail-closed strategy readiness (repair 2026-10-02).

``CoverageTracker`` records, for M1 bars delivered in order, which
scheduled-open minutes are known and which are UNEXPECTED gaps.

* Scheduled closures (maintenance, weekend, early halts, holiday closures per
  ``bars.market_state``) are never gaps and never need data.
* A missing scheduled-open minute is known ONLY when it has documented
  evidence of zero trades, registered with ``attest_zero_trade`` BEFORE the bar
  that follows it is observed:
    - ``LIVE_END_OF_INTERVAL``: the Databento live gateway sent
      ``end_of_interval`` system messages bracketing that minute in the same
      uninterrupted connection with no OHLCV record for it;
    - ``ARCHIVE_MANIFEST_ZERO_VOLUME``: the archive manifest's declared
      zero-volume minute count exactly equals the minutes missing from its file.
  A bare continuity label, an empty provider response or "same stream" alone
  certifies nothing (acceptance review 2026-10-02).
* Watermark: nothing at or after the last known minute (last bar end or a
  contiguous attested minute) is known; nothing before the first bar is known.

Gaps persist for the life of the tracker. The engine resets market structure
on every new unexpected gap, so stale bias/levels/ATR never bridge a hole.

Every CME equity closure boundary sits on an ET quarter hour and ET offsets
are whole hours, so ``market_state`` is constant inside each UTC quarter hour;
open-minute counting walks quarter hours instead of single minutes.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Iterable, Mapping

from mes_pilot.bars import ET, OPEN, UTC, Bar, CME_EQUITY_FULL_CLOSURES, market_state

EVIDENCE_KINDS = ("LIVE_END_OF_INTERVAL", "ARCHIVE_MANIFEST_ZERO_VOLUME")
QUARTER = timedelta(minutes=15)
ONE_MIN = timedelta(minutes=1)
DEFAULT_TIMEFRAMES = (1, 5, 15, 60, 240)


def _utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("naive timestamp")
    return ts.astimezone(UTC)


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def open_runs(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Maximal [run_start, run_end) intervals of OPEN minutes inside [start, end)."""
    cursor, stop = _utc(start), _utc(end)
    runs: list[tuple[datetime, datetime]] = []
    while cursor < stop:
        floor = cursor.replace(second=0, microsecond=0)
        nxt = floor - timedelta(minutes=floor.minute % 15) + QUARTER
        chunk_end = min(nxt, stop)
        if market_state(cursor) == OPEN:
            if runs and runs[-1][1] == cursor:
                runs[-1] = (runs[-1][0], chunk_end)
            else:
                runs.append((cursor, chunk_end))
        cursor = chunk_end
    return runs


def open_minutes(start: datetime, end: datetime) -> int:
    """Number of scheduled-open minutes in [start, end)."""
    return sum(_minutes(b - a) for a, b in open_runs(start, end))


def open_minute_starts(start: datetime, end: datetime) -> list[datetime]:
    out = []
    for a, b in open_runs(start, end):
        t = a
        while t < b:
            out.append(t)
            t += ONE_MIN
    return out


@dataclass(frozen=True)
class GapRecord:
    start: datetime          # previous known minute end (watermark)
    end: datetime            # next bar start
    open_minutes: int        # unexpected (scheduled-open, un-evidenced) minutes inside [start, end)
    prev_source: str | None
    next_source: str | None
    continuity: str | None   # label claimed by the next bar (informational only)
    attested_minutes: int = 0
    reason: str = "UNEVIDENCED_MISSING_OPEN_MINUTES"

    def to_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "open_minutes": self.open_minutes,
                "attested_minutes": self.attested_minutes, "prev_source": self.prev_source,
                "next_source": self.next_source, "continuity": self.continuity, "reason": self.reason}


class CoverageTracker:
    """Known/unknown scheduled-open minutes of an in-order M1 bar stream."""

    def __init__(self):
        self._first: datetime | None = None
        self._frontier: datetime | None = None
        self._last_source: str | None = None
        self._gaps: list[GapRecord] = []
        self._seg_starts: list[datetime] = []   # unexpected open segments, sorted, disjoint
        self._seg_ends: list[datetime] = []
        self._attested: dict[datetime, str] = {}  # minute start -> evidence kind (pending + applied)
        self._bars = 0
        self._late_or_duplicate = 0
        self._sources: Counter = Counter()
        self._continuity: Counter = Counter()
        self._attested_applied = Counter()

    # ------------------------------------------------------------------ evidence
    def attest_zero_trade(self, minute_start: datetime, evidence: str):
        """Register documented evidence that the open minute starting at ``minute_start`` had no trades."""
        if evidence not in EVIDENCE_KINDS:
            raise ValueError(f"unsupported zero-trade evidence {evidence!r}")
        m = _utc(minute_start).replace(second=0, microsecond=0)
        if market_state(m) != OPEN:
            return
        if self._frontier is not None and m < self._frontier:
            return  # already decided; evidence cannot retroactively clear a recorded gap
        self._attested[m] = evidence
        # A contiguous attested minute right at the watermark advances it.
        while self._frontier is not None and self._attested.get(self._frontier) is not None:
            self._attested_applied[self._attested[self._frontier]] += 1
            self._frontier += ONE_MIN

    # ------------------------------------------------------------------ ingest
    def observe(self, bar: Bar, continuity: str | None = None, source: str | None = None) -> list[GapRecord]:
        """Record an M1 bar; return the NEW unexpected gaps it reveals."""
        start, end = _utc(bar.start), _utc(bar.end)
        if self._frontier is not None and start < self._frontier:
            self._late_or_duplicate += 1
            return []
        self._bars += 1
        self._sources[source or "UNSPECIFIED"] += 1
        self._continuity[continuity or "NONE"] += 1
        new: list[GapRecord] = []
        if self._first is None:
            self._first = start
        elif start > self._frontier:
            missing = open_minute_starts(self._frontier, start)
            unknown = [m for m in missing if m not in self._attested]
            attested = len(missing) - len(unknown)
            for m in missing:
                if m in self._attested:
                    self._attested_applied[self._attested[m]] += 1
            if unknown:
                rec = GapRecord(self._frontier, start, len(unknown), self._last_source, source, continuity, attested)
                self._gaps.append(rec)
                for m in unknown:  # merge consecutive unknown minutes into segments
                    if self._seg_ends and self._seg_ends[-1] == m:
                        self._seg_ends[-1] = m + ONE_MIN
                    else:
                        self._seg_starts.append(m)
                        self._seg_ends.append(m + ONE_MIN)
                new.append(rec)
        self._frontier = end
        self._last_source = source
        # forget evidence that can no longer matter
        if len(self._attested) > 5000:
            self._attested = {k: v for k, v in self._attested.items() if k >= self._frontier}
        return new

    # ------------------------------------------------------------------ queries
    @property
    def first_bar_start(self) -> datetime | None:
        return self._first

    @property
    def last_bar_end(self) -> datetime | None:
        """Coverage watermark: end of the last known minute."""
        return self._frontier

    def gaps(self) -> list[GapRecord]:
        return list(self._gaps)

    def gaps_overlapping(self, start: datetime, end: datetime) -> list[GapRecord]:
        s, e = _utc(start), _utc(end)
        return [g for g in self._gaps if g.start < e and g.end > s]

    def _overlapping(self, start: datetime, end: datetime) -> Iterable[tuple[datetime, datetime]]:
        i = bisect_right(self._seg_ends, start)
        while i < len(self._seg_starts) and self._seg_starts[i] < end:
            yield self._seg_starts[i], self._seg_ends[i]
            i += 1

    def unexpected_minutes(self, start: datetime, end: datetime) -> int:
        """Recorded unexpected-missing open minutes overlapping [start, end)."""
        s, e = _utc(start), _utc(end)
        return sum(_minutes(min(b, e) - max(a, s)) for a, b in self._overlapping(s, e))

    def is_complete(self, start: datetime, end: datetime) -> bool:
        """True when every scheduled-open minute of [start, end) is known (bars or evidence).

        Rejects any interval whose open minutes start before the first bar or end
        after the coverage watermark, and any interval overlapping a recorded gap.
        """
        s, e = _utc(start), _utc(end)
        runs = open_runs(s, e)
        if not runs:
            return True
        if self._first is None or runs[0][0] < self._first or self._frontier < runs[-1][1]:
            return False
        return next(iter(self._overlapping(s, e)), None) is None

    def to_dict(self) -> dict:
        return {
            "first_bar_start": self._first.isoformat() if self._first else None,
            "last_bar_end": self._frontier.isoformat() if self._frontier else None,
            "bars_observed": self._bars,
            "late_or_duplicate_bars_ignored": self._late_or_duplicate,
            "sources": dict(self._sources),
            "continuity_labels": dict(self._continuity),
            "zero_trade_minutes_evidenced": dict(self._attested_applied),
            "unexpected_gap_count": len(self._gaps),
            "unexpected_minutes_total": sum(g.open_minutes for g in self._gaps),
            "gaps": [g.to_dict() for g in self._gaps[-50:]],
        }


def bar_completeness(tracker: CoverageTracker, bar: Bar) -> dict:
    """Coverage of one (usually aggregated) bar's scheduled-open minutes."""
    s, e = _utc(bar.start), _utc(bar.end)
    expected = open_minutes(s, e)
    unexpected = tracker.unexpected_minutes(s, e)
    first, frontier = tracker.first_bar_start, tracker.last_bar_end
    if first is None:
        unknown = expected
    else:
        unknown = (open_minutes(s, min(e, first)) if first > s else 0) + \
                  (open_minutes(max(s, frontier), e) if frontier < e else 0)
    observed = max(0, expected - unexpected - unknown)
    return {"complete": tracker.is_complete(s, e), "expected_open_minutes": expected,
            "unexpected_minutes": unexpected, "unknown_minutes": unknown, "known_minutes": observed}


# --------------------------------------------------------------------- readiness
@dataclass
class ReadinessResult:
    ready: bool
    reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def _at(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, ET).astimezone(UTC)


def previous_trading_date(day: date) -> date:
    """Previous CME equity trade date, skipping weekends and full closures (Monday -> Friday)."""
    d = day - timedelta(days=1)
    while d.weekday() >= 5 or d in CME_EQUITY_FULL_CLOSURES:
        d -= timedelta(days=1)
    return d


def session_bounds(day: date, rollover: time = time(18), close: time = time(17)) -> tuple[datetime, datetime]:
    """UTC [start, end) of trade date ``day``: rollover ET on the previous calendar day to close ET on day.

    For a Monday trade date the session opens Sunday 18:00 ET (weekend minutes are closures).
    """
    return _at(day - timedelta(days=1), rollover), _at(day, close)


def window_bounds(day: date, window: tuple[time, time], rollover: time = time(18)) -> tuple[datetime, datetime]:
    """UTC bounds of a configured ET window belonging to trade date ``day``.

    Clock times at/after the rollover fall on the previous calendar day, so
    Asia 19:00-00:00 for trade date D runs 19:00 ET D-1 -> 00:00 ET D.
    """
    def place(clock: time) -> datetime:
        return _at(day - timedelta(days=1) if clock >= rollover else day, clock)
    start, end = place(window[0]), place(window[1])
    if end <= start:
        end = _at(day, window[1]) if window[0] >= rollover else end + timedelta(days=1)
    return start, end


def _window_check(tracker: CoverageTracker, start: datetime, end: datetime, now: datetime) -> dict:
    stop = min(end, now)
    info = {"start": start.isoformat(), "end": end.isoformat(), "evaluated_to": stop.isoformat(),
            "ended": end <= now}
    if stop <= start or open_minutes(start, stop) == 0:
        info.update(required=False, ok=True, unexpected_minutes=0, complete=None)
        return info
    unexpected = tracker.unexpected_minutes(start, stop)
    complete = tracker.is_complete(start, stop)
    info.update(required=True, unexpected_minutes=unexpected, complete=complete,
                expected_open_minutes=open_minutes(start, stop), ok=unexpected == 0 and complete)
    return info


def evaluate_readiness(*, now: datetime, tracker: CoverageTracker, tfs: Mapping, session_day: date | None, cfg,
                       vol_state: tuple, required_bars: int = 21,
                       incomplete_bar_starts: Mapping[int, set] | None = None,
                       timeframes: tuple[int, ...] = DEFAULT_TIMEFRAMES) -> ReadinessResult:
    """Fail-closed strategy readiness from data coverage.

    Required: every timeframe has ``required_bars`` complete bars whose lookback
    has no unexpected gap; the previous actual trading session and the elapsed
    overnight part of the current session are complete; the configured Asia and
    London windows (once ended) are complete; and, when the volatility filter is
    enabled, the volatility percentile is available (``OUT_OF_BAND`` stays a
    normal strategy rejection, not a readiness fault).
    """
    now = _utc(now)
    reasons: list[str] = []
    details: dict = {"now": now.isoformat(), "session_day": session_day.isoformat() if session_day else None,
                     "required_bars": required_bars, "coverage": {
                         "first_bar_start": tracker.first_bar_start.isoformat() if tracker.first_bar_start else None,
                         "last_bar_end": tracker.last_bar_end.isoformat() if tracker.last_bar_end else None,
                         "unexpected_gap_count": len(tracker.gaps())}}
    if tracker.first_bar_start is None or session_day is None:
        reasons.append("NO_CONTEXT")
        return ReadinessResult(False, reasons, details)
    incomplete_bar_starts = incomplete_bar_starts or {}

    tf_details = {}
    for tf in timeframes:
        state = tfs.get(tf) if hasattr(tfs, "get") else tfs[tf]
        bars = list(state.bars) if state is not None else []
        info: dict = {"bars": len(bars)}
        if len(bars) < required_bars:
            reasons.append(f"TF_{tf}_INSUFFICIENT_BARS")
            info["ok"] = False
            tf_details[tf] = info
            continue
        window = bars[-required_bars:]
        lb_start = _utc(window[0].start)
        gap_minutes = tracker.unexpected_minutes(lb_start, now) if lb_start < now else 0
        flagged = incomplete_bar_starts.get(tf) or set()
        partial = [b.start.isoformat() for b in window
                   if b.start in flagged or (tf > 1 and not tracker.is_complete(b.start, b.end))]
        info.update(lookback_start=lb_start.isoformat(), unexpected_minutes=gap_minutes, partial_bars=partial)
        if gap_minutes:
            reasons.append(f"TF_{tf}_GAP_IN_LOOKBACK")
        if partial:
            reasons.append(f"TF_{tf}_PARTIAL_BAR_IN_LOOKBACK")
        info["ok"] = not gap_minutes and not partial
        tf_details[tf] = info
    details["timeframes"] = tf_details

    rollover = getattr(cfg.session, "day_rollover", time(18))
    prior_day = previous_trading_date(session_day)
    ps, pe = session_bounds(prior_day, rollover)
    prior = _window_check(tracker, ps, pe, now)
    prior["trade_date"] = prior_day.isoformat()
    cs = _at(session_day - timedelta(days=1), rollover)
    ce = _at(session_day, cfg.session.entry_start)
    overnight = _window_check(tracker, cs, ce, now)
    details["prior_session"] = prior
    details["current_overnight"] = overnight
    if not prior["ok"]:
        reasons.append("PRIOR_SESSION_GAP")
    if not overnight["ok"]:
        reasons.append("CURRENT_OVERNIGHT_GAP")

    for name, code in (("asia", "ASIA_WINDOW_GAP"), ("london", "LONDON_WINDOW_GAP")):
        ws, we = window_bounds(session_day, getattr(cfg.session, name), rollover)
        info = {"start": ws.isoformat(), "end": we.isoformat(), "ended": we <= now}
        if we <= now and open_minutes(ws, we) > 0:
            unexpected = tracker.unexpected_minutes(ws, we)
            complete = tracker.is_complete(ws, we)
            info.update(required=True, unexpected_minutes=unexpected, complete=complete,
                        expected_open_minutes=open_minutes(ws, we), ok=unexpected == 0 and complete)
            if not info["ok"]:
                reasons.append(code)
        else:
            info.update(required=False, ok=True)
        details[name] = info

    vol_enabled = bool(getattr(cfg.strategy, "volatility_filter", False))
    vstate = vol_state[0] if vol_state else None
    details["volatility"] = {"state": vstate, "filter_enabled": vol_enabled}
    if vol_enabled and vstate in (None, "UNAVAILABLE"):
        reasons.append("VOLATILITY_UNAVAILABLE")
    return ReadinessResult(ready=not reasons, reasons=reasons, details=details)
