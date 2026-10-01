"""Causal regime measurements (master spec pages 9-10).

VolatilityBand: M5 ATR(14) versus the trailing N-session distribution at the
same ET time of day. Insufficient history -> UNAVAILABLE (an enabled filter
then blocks the entry; it never silently passes).

AccumulationTracker: RANGE_COMPRESSION_CANDIDATE from a frozen prior M5 range
(21 closes / 20 intervals), width/ATR and efficiency ratio. A completed close
beyond a frozen boundary starts TRANSITION; a close back inside is a recorded
FALSE_BREAK. Price compression is not evidence of institutional buying; the
ACCUMULATION label is never assigned from price alone.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime

from mes_pilot.bars import Bar, ET


class VolatilityBand:
    def __init__(self, lookback_sessions: int, band: tuple[float, float]):
        self.lookback = lookback_sessions
        self.band = band
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=lookback_sessions))
        self._session: date | None = None
        self._today: dict[str, float] = {}

    @staticmethod
    def _bucket(ts: datetime) -> str:
        local = ts.astimezone(ET)
        return f"{local.hour:02d}:{local.minute:02d}"

    def roll(self, session: date):
        if self._session is not None and session != self._session:
            for key, value in self._today.items():
                self.history[key].append(value)
            self._today = {}
        self._session = session

    def observe(self, m5_end: datetime, atr: float | None):
        if atr is not None:
            self._today[self._bucket(m5_end)] = atr

    def classify(self, m5_end: datetime, atr: float | None) -> tuple[str, float | None]:
        if atr is None:
            return "UNAVAILABLE", None
        hist = self.history.get(self._bucket(m5_end))
        if not hist or len(hist) < self.lookback:
            return "UNAVAILABLE", None
        below = sum(1 for v in hist if v < atr)
        equal = sum(1 for v in hist if v == atr)
        pct = 100.0 * (below + 0.5 * equal) / len(hist)
        lo, hi = self.band
        return ("IN_BAND" if lo <= pct <= hi else "OUT_OF_BAND"), round(pct, 2)


@dataclass
class RangeState:
    state: str = "UNKNOWN"          # UNKNOWN | NONE | RANGE_COMPRESSION_CANDIDATE | TRANSITION_UP | TRANSITION_DOWN
    high: float | None = None
    low: float | None = None
    formed_at: datetime | None = None
    age_bars: int = 0
    false_breaks: int = 0
    last_event: str | None = None


class AccumulationTracker:
    def __init__(self, lookback_closes: int, max_range_atr: float, max_er: float, stale_after_bars: int):
        self.n = lookback_closes
        self.max_range_atr = max_range_atr
        self.max_er = max_er
        self.stale = stale_after_bars
        self.s = RangeState()

    def on_m5(self, bars: list[Bar], prior_atr: float | None) -> RangeState:
        s = self.s
        s.last_event = None
        if len(bars) < self.n + 1:
            s.state = "UNKNOWN"
            return s
        current = bars[-1]
        prior = bars[-(self.n + 1):-1]   # prior 21 completed bars, excluding current
        if s.state in ("RANGE_COMPRESSION_CANDIDATE", "TRANSITION_UP", "TRANSITION_DOWN"):
            s.age_bars += 1
            if s.state == "RANGE_COMPRESSION_CANDIDATE":
                if current.close > s.high:
                    s.state, s.last_event = "TRANSITION_UP", "BREAK_UP_CLOSE"
                elif current.close < s.low:
                    s.state, s.last_event = "TRANSITION_DOWN", "BREAK_DOWN_CLOSE"
            elif s.low <= current.close <= s.high:
                s.false_breaks += 1
                s.state, s.last_event = "RANGE_COMPRESSION_CANDIDATE", "FALSE_BREAK_REENTERED"
            if s.age_bars > self.stale:
                self.s = RangeState(state="NONE", last_event="RANGE_EXPIRED")
            return self.s
        # Detect a new frozen range from prior completed bars.
        closes = [b.close for b in prior]
        path = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
        if prior_atr is None or prior_atr <= 0 or path == 0:
            s.state = "UNKNOWN"
            return s
        er = abs(closes[-1] - closes[0]) / path
        hi, lo = max(b.high for b in prior), min(b.low for b in prior)
        if (hi - lo) / prior_atr <= self.max_range_atr and er <= self.max_er:
            self.s = RangeState("RANGE_COMPRESSION_CANDIDATE", hi, lo, current.end, 0, 0, "RANGE_FORMED")
        else:
            s.state = "NONE"
        return self.s

    def location(self, price: float, tick: float, edge_ticks: int = 4) -> str:
        s = self.s
        if s.high is None or s.state not in ("RANGE_COMPRESSION_CANDIDATE",):
            return "NO_RANGE"
        if price > s.high or price < s.low:
            return "OUTSIDE"
        if price >= s.high - edge_ticks * tick or price <= s.low + edge_ticks * tick:
            return "RANGE_EDGE"
        return "INTERIOR"
