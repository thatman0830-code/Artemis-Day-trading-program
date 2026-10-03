"""Causal market-structure primitives (master spec page 7, pilot interpretation).

Repository comparison (documented discrepancies, see docs/MES_PAPER_PILOT_V1.md):
- strategy/market_structure.py uses the same 2-bar strict pivot but scans a
  whole frame and records no confirmation time; here a swing is usable only
  after its second right-hand bar closes.
- strategy/liquidity.py measures sweeps in percent (BTC-oriented); here sweeps,
  BOS and gaps are measured in whole ticks.

Every feature is computed from bars whose ``end`` <= decision time.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from mes_pilot.bars import Bar


@dataclass(frozen=True)
class Swing:
    kind: str          # "HIGH" | "LOW"
    price: float
    bar_start: datetime
    confirmed_at: datetime  # end of the 2nd right-hand bar
    tf: int


@dataclass
class Gap:
    direction: str      # "BULL" | "BEAR"
    low: float
    high: float
    created_at: datetime  # end of bar C
    tf: int
    middle_bar_start: datetime
    touches: int = 0
    filled_at: datetime | None = None
    invalidated_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.filled_at is None and self.invalidated_at is None

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2

    def active_at(self, as_of: datetime) -> bool:
        """Gap known at ``as_of`` and neither filled nor invalidated by a bar that ended at/before it."""
        return (self.created_at <= as_of
                and (self.filled_at is None or self.filled_at > as_of)
                and (self.invalidated_at is None or self.invalidated_at > as_of))


@dataclass
class TimeframeState:
    tf: int
    tick: float
    swing_side: int = 2
    atr_period: int = 14
    er_period: int = 20
    bars: deque = field(default_factory=lambda: deque(maxlen=600))
    swings_high: list = field(default_factory=list)
    swings_low: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    bias: str = "NEUTRAL"           # BULLISH | BEARISH | NEUTRAL
    bias_event_at: datetime | None = None
    bias_level: float | None = None

    # ------------------------------------------------------------------
    def push(self, bar: Bar) -> dict:
        """Append a completed bar; return events confirmed by this close."""
        events: dict = {"new_swings": [], "new_gaps": [], "bias_change": None}
        self.bars.append(bar)
        events["new_swings"] = self._confirm_swing()
        self._update_gaps(bar)
        gap = self._detect_gap()
        if gap is not None:
            self.gaps.append(gap)
            events["new_gaps"].append(gap)
        events["bias_change"] = self._update_bias(bar)
        if len(self.gaps) > 200:
            self.gaps = [g for g in self.gaps if g.active][-200:]
        return events

    # ------------------------------------------------------------------
    def _confirm_swing(self) -> list[Swing]:
        n = self.swing_side
        if len(self.bars) < 2 * n + 1:
            return []
        window = list(self.bars)[-(2 * n + 1):]
        pivot = window[n]
        left, right = window[:n], window[n + 1:]
        confirmed_at = window[-1].end
        out = []
        if all(pivot.high > b.high for b in left + right):
            s = Swing("HIGH", pivot.high, pivot.start, confirmed_at, self.tf)
            self.swings_high.append(s)
            out.append(s)
        if all(pivot.low < b.low for b in left + right):
            s = Swing("LOW", pivot.low, pivot.start, confirmed_at, self.tf)
            self.swings_low.append(s)
            out.append(s)
        return out

    def _detect_gap(self) -> Gap | None:
        if len(self.bars) < 3:
            return None
        a, b, c = list(self.bars)[-3:]
        if c.low - a.high >= self.tick - 1e-9:
            return Gap("BULL", a.high, c.low, c.end, self.tf, b.start)
        if a.low - c.high >= self.tick - 1e-9:
            return Gap("BEAR", c.high, a.low, c.end, self.tf, b.start)
        return None

    def _update_gaps(self, bar: Bar):
        for g in self.gaps:
            if not g.active or g.created_at >= bar.end:
                continue
            if g.direction == "BULL":
                if bar.low <= g.high:
                    g.touches += 1
                if bar.close < g.low:
                    g.invalidated_at = bar.end
                elif bar.low <= g.low:
                    g.filled_at = bar.end
            else:
                if bar.high >= g.low:
                    g.touches += 1
                if bar.close > g.high:
                    g.invalidated_at = bar.end
                elif bar.high >= g.high:
                    g.filled_at = bar.end

    def _update_bias(self, bar: Bar) -> str | None:
        """Close beyond the most recent confirmed swing sets structure; persists until opposite break.

        The reference swing must have been confirmed before this bar started: a
        swing confirmed by this same close (its 2nd right-hand bar) cannot be the
        level this close breaks, and must not shadow an older swing that it does.
        """
        hi = self.latest_swing("HIGH", bar.start)
        lo = self.latest_swing("LOW", bar.start)
        new = None
        if hi is not None and bar.close >= hi.price + self.tick - 1e-9 and self.bias != "BULLISH":
            new, level = "BULLISH", hi.price
        elif lo is not None and bar.close <= lo.price - self.tick + 1e-9 and self.bias != "BEARISH":
            new, level = "BEARISH", lo.price
        if new:
            self.bias, self.bias_event_at, self.bias_level = new, bar.end, level
        return new

    # ------------------------------------------------------------------
    def latest_swing(self, kind: str, as_of: datetime, before_bar_start: datetime | None = None) -> Swing | None:
        seq = self.swings_high if kind == "HIGH" else self.swings_low
        for s in reversed(seq):
            if s.confirmed_at <= as_of and (before_bar_start is None or s.bar_start < before_bar_start):
                return s
        return None

    def atr_before(self, ts: datetime) -> float | None:
        """ATR over the ``atr_period`` completed bars that ended at/before ``ts`` (causal)."""
        bars = [b for b in self.bars if b.end <= ts]
        return self._atr_of(bars)

    def atr(self, exclude_last: int = 0) -> float | None:
        """Simple mean true range over ``atr_period`` completed bars, optionally excluding the newest bars."""
        bars = list(self.bars)
        if exclude_last:
            bars = bars[:-exclude_last]
        return self._atr_of(bars)

    def _atr_of(self, bars: list) -> float | None:
        if len(bars) < self.atr_period + 1:
            return None
        window = bars[-(self.atr_period + 1):]
        trs = []
        for prev, cur in zip(window, window[1:]):
            trs.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
        value = sum(trs) / len(trs)
        return value if value > 0 else None

    def efficiency_ratio(self, period: int | None = None, exclude_last: int = 0) -> float | None:
        period = period or self.er_period
        closes = [b.close for b in self.bars]
        if exclude_last:
            closes = closes[:-exclude_last]
        if len(closes) < period + 1:
            return None
        window = closes[-(period + 1):]
        path = sum(abs(b - a) for a, b in zip(window, window[1:]))
        if path == 0:
            return None
        return abs(window[-1] - window[0]) / path

    def is_displacement(self, bar: Bar, direction: str, body_mult: float, outer: float) -> tuple[bool, dict]:
        """Body >= mult x prior completed ATR(14); close in the outer fraction toward direction.

        "Prior" = bars that ended at/before this candle started, so the candle's
        own range (and anything after it) never enters its threshold, whether or
        not the candle has already been pushed into this state.

        The returned boolean is unchanged from the original predicate; ``info`` is a
        pure diagnostic: every subcondition is evaluated and recorded (even after an
        earlier one fails) and ``reason`` names the FIRST failing one in the order
        NO_PRIOR_ATR, ZERO_RANGE, WRONG_DIRECTION, CLOSE_NOT_IN_OUTER_FRACTION,
        BODY_BELOW_ATR_MULT (else PASS). ``close_location`` is the distance of the
        close from the favourable extreme as a fraction of the range (0 = at the
        high for LONG / at the low for SHORT).
        """
        prior_atr = self.atr_before(bar.start)
        rng = bar.high - bar.low
        long_side = direction == "LONG"
        direction_ok = bool(bar.bullish if long_side else bar.bearish)
        off_extreme = (bar.high - bar.close) if long_side else (bar.close - bar.low)
        close_location_ok = bool(off_extreme <= outer * rng + 1e-9)
        required_body = body_mult * prior_atr if prior_atr is not None else None
        body_ok = bool(bar.body >= body_mult * prior_atr - 1e-9) if prior_atr is not None else None
        data_available = prior_atr is not None and rng > 0
        if prior_atr is None:
            reason = "NO_PRIOR_ATR"
        elif rng <= 0:
            reason = "ZERO_RANGE"
        elif not direction_ok:
            reason = "WRONG_DIRECTION"
        elif not close_location_ok:
            reason = "CLOSE_NOT_IN_OUTER_FRACTION"
        elif not body_ok:
            reason = "BODY_BELOW_ATR_MULT"
        else:
            reason = "PASS"
        ok = reason == "PASS"
        info = {
            "candle": {"start": bar.start.isoformat(), "end": bar.end.isoformat(),
                       "o": bar.open, "h": bar.high, "l": bar.low, "c": bar.close},
            "direction": direction,
            "prior_atr": prior_atr,
            "body": bar.body,
            "range": rng,
            "body_atr_ratio": (bar.body / prior_atr) if prior_atr else None,
            "required_body": required_body,
            "body_mult": body_mult,
            "outer_fraction": outer,
            "close_location": (off_extreme / rng) if rng > 0 else None,
            "direction_ok": direction_ok,
            "close_location_ok": close_location_ok,
            "body_ok": body_ok,
            "data_available": data_available,
            "reason": reason,
            "status": "UNKNOWN" if not data_available else ("PASS" if ok else "FAIL"),
        }
        return ok, info

    def active_gaps(self, direction: str, as_of: datetime) -> list[Gap]:
        """Gaps active AS OF ``as_of`` (a gap a later bar filled/invalidated is still active before that bar)."""
        return [g for g in self.gaps if g.direction == direction and g.active_at(as_of)]

    def reset(self):
        self.bars.clear()
        self.swings_high.clear()
        self.swings_low.clear()
        self.gaps.clear()
        self.bias, self.bias_event_at, self.bias_level = "NEUTRAL", None, None


def aligned_bias(h4: TimeframeState, h1: TimeframeState) -> str:
    if h4.bias == h1.bias and h4.bias in ("BULLISH", "BEARISH"):
        return h4.bias
    return "NEUTRAL"


def sweep(bar: Bar, level: float, side: str, tick: float, min_ticks: int) -> bool:
    """Excursion >= min_ticks beyond level then close back through it.

    side="SELL_SIDE" (a low/level below price) -> bar.low <= level - n*tick and close > level.
    side="BUY_SIDE"  (a high/level above price) -> bar.high >= level + n*tick and close < level.
    """
    reach = min_ticks * tick - 1e-9
    if side == "SELL_SIDE":
        return level - bar.low >= reach and bar.close > level
    return bar.high - level >= reach and bar.close < level


def cisd_level(bars: list[Bar], direction: str, before: datetime) -> tuple[float, datetime] | None:
    """Open of the most recent opposite-direction candle that closed at or before ``before``."""
    for b in reversed(bars):
        if b.end > before:
            continue
        if direction == "LONG" and b.bearish:
            return b.open, b.start
        if direction == "SHORT" and b.bullish:
            return b.open, b.start
    return None


def ote_zone(impulse_start: float, impulse_end: float, lo: float, hi: float) -> tuple[float, float]:
    """62-79% retracement band of a frozen impulse (start -> end)."""
    span = impulse_end - impulse_start
    a = impulse_end - lo * span
    b = impulse_end - hi * span
    return (min(a, b), max(a, b))
