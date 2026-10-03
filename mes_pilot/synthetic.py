"""Deterministic SYNTHETIC_TEST sequences for the end-to-end demonstration.

Nothing here is market data. The history is a smooth multi-day uptrend
(drift + 24 h and 6 h cycles) so that H4/H1 structure is bullish. On the demo
day a hand-built 09:00-10:30 ET segment is placed relative to the liquidity
levels the engine itself has marked by 09:00, producing:

  scenario "qualifying": REVERSAL_R1 long — London/Asia/PD low swept on M5,
     bullish M5 displacement breaks the M5 swing high, M1 retest confirms,
     simulated entry at the next modeled ask, exit at the premarked target.
  scenario "rejected":   identical except the sweep runs 6.5 points deeper, so
     the structural stop is ~53 ticks: unit loss > the $70 capacity budget ->
     zero whole contracts -> REJECT (the stop is never tightened to fit).

The volatility-percentile filter needs 60 prior sessions of real data and is
disabled for this synthetic run (recorded in the config hash and manifest).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import pi, sin

from mes_pilot.bars import Bar, ET, ONE_MIN, UTC

TICK = 0.25
CONTRACT = "SYNTH-MESZ6"


def _q(x: float) -> float:
    return round(x / TICK) * TICK


def path_price(minutes_from_start: float) -> float:
    h = minutes_from_start / 60.0
    return 6500.0 + 2.0 * h + 30.0 * sin(2 * pi * h / 24.0) + 12.0 * sin(2 * pi * h / 6.0)


def session_minutes(day: date) -> list[datetime]:
    """CME-style session: 18:00 ET (previous day) through 16:59 ET."""
    start = datetime.combine(day - timedelta(days=1), time(18, 0), ET)
    end = datetime.combine(day, time(17, 0), ET)
    out, t = [], start
    while t < end:
        out.append(t.astimezone(UTC))
        t += ONE_MIN
    return out


def bar_from(prev_close: float, close: float, start: datetime, wiggle: float = TICK) -> Bar:
    o, c = _q(prev_close), _q(close)
    return Bar(start, start + ONE_MIN, o, max(o, c) + wiggle, min(o, c) - wiggle, c, 100.0, CONTRACT, 1)


def history(days: list[date], until: datetime | None = None) -> list[Bar]:
    t0 = session_minutes(days[0])[0]
    bars, prev = [], None
    for d in days:
        for ts in session_minutes(d):
            if until is not None and ts >= until:
                return bars
            p = path_price((ts - t0).total_seconds() / 60)
            prev = p if prev is None else prev
            bars.append(bar_from(prev, p, ts))
            prev = p
    return bars


def ohlc_bar(start: datetime, o: float, h: float, low: float, c: float) -> Bar:
    return Bar(start, start + ONE_MIN, _q(o), _q(h), _q(low), _q(c), 100.0, CONTRACT, 1)


def m5_as_m1(start: datetime, o: float, h: float, low: float, c: float) -> list[Bar]:
    """Five M1 bars whose aggregate is exactly the requested M5 OHLC (high then low, or low then high)."""
    up = c >= o
    first, second = (low, h) if up else (h, low)
    pts = [o, first, (first + second) / 2, second, (second + c) / 2, c]
    out = []
    for i in range(5):
        a, b = pts[i], pts[i + 1]
        out.append(ohlc_bar(start + i * ONE_MIN, a, max(a, b), min(a, b), b))
    return out


SCENARIO_DEPTH = {"qualifying": 1.0, "rejected": 6.5}


def choose_geometry(engine, as_of: datetime, price: float, max_depth: float) -> tuple[float, float]:
    """Pick the swept level x and target offset from the engine's own premarked levels.

    x: highest SELL_SIDE level below price whose deepest planned sweep stays above
    every other sell-side level (one level swept) and above the latest H1/H4
    swing lows (bias intact). Target: nearest BUY_SIDE level above x + 7.75.
    """
    sells = sorted({lv.price for lv in engine.book.active(as_of, "SELL_SIDE") if lv.price < price - 10}, reverse=True)
    floors = [s.price for s in (engine.tfs[60].latest_swing("LOW", as_of), engine.tfs[240].latest_swing("LOW", as_of)) if s]
    for i, x in enumerate(sells):
        below = sells[i + 1] if i + 1 < len(sells) else float("-inf")
        if x - max_depth - 0.25 <= below or any(x - max_depth - 1 <= f for f in floors if f < x):
            continue
        buys = sorted(lv.price for lv in engine.book.active(as_of, "BUY_SIDE") if lv.price > x + 7.75)
        if buys:
            return x, buys[0] - x
    raise RuntimeError("no usable synthetic geometry; adjust synthetic history")


def demo_segment(day: date, x: float, p_start: float, depth: float, target_rel: float) -> list[Bar]:
    """Bars from 09:00 to 11:35 ET, prices relative to the swept level ``x``.

    depth: sweep excursion below x (points). target_rel: target level minus x.
    """
    at = lambda hh, mm: datetime.combine(day, time(hh, mm), ET).astimezone(UTC)  # noqa: E731
    bars: list[Bar] = []
    # 09:00-09:20 glide from current price to x+4.75, then hold flat to 09:30 so the
    # two M5 bars left of the 09:35 pivot stay below it (strict pivot).
    t = at(9, 0)
    n = 20
    for i in range(n):
        a = p_start + (x + 4.75 - p_start) * i / n
        b = p_start + (x + 4.75 - p_start) * (i + 1) / n
        bars.append(ohlc_bar(t + i * ONE_MIN, a, max(a, b), min(a, b), b))
    for i in range(n, 30):
        bars.append(ohlc_bar(t + i * ONE_MIN, x + 4.75, x + 5.0, x + 4.5, x + 4.75))
    m5 = [
        (9, 30, x + 4.75, x + 5.25, x + 4.5, x + 4.75),
        (9, 35, x + 4.75, x + 6.0, x + 4.25, x + 4.5),     # M5 swing-high pivot at x+6
        (9, 40, x + 4.5, x + 5.0, x + 3.0, x + 3.25),
        (9, 45, x + 3.25, x + 3.5, x + 1.5, x + 1.75),     # confirms the pivot
        (9, 50, x + 1.75, x + 2.0, x - depth, x + 0.75),   # sweep: below x, closes back above
        (9, 55, x + 0.75, x + 7.75, x + 0.5, x + 7.5),     # displacement + BOS above x+6
    ]
    for hh, mm, o, h, low, c in m5:
        bars.extend(m5_as_m1(at(hh, mm), o, h, low, c))
    # M1 retest into the [equilibrium, x+6] zone, bullish close.
    bars.append(ohlc_bar(at(10, 0), x + 7.5, x + 7.75, x + 6.75, x + 7.0))
    bars.append(ohlc_bar(at(10, 1), x + 7.0, x + 7.0, x + 5.75, x + 5.75))
    bars.append(ohlc_bar(at(10, 2), x + 5.75, x + 6.5, x + 5.5, x + 6.25))   # confirming retest
    # 10:03 onward: rally through the target by >= 1 tick, then drift.
    price, t = x + 6.25, at(10, 3)
    goal = x + target_rel + 1.0
    step = (goal - price) / 15
    for i in range(15):
        bars.append(ohlc_bar(t, price, price + step + TICK, price - TICK, price + step))
        price += step
        t += ONE_MIN
    while t < at(11, 35):
        bars.append(ohlc_bar(t, price, price + TICK, price - TICK, price))
        t += ONE_MIN
    return bars
