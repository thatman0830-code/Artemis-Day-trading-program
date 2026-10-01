"""Hand-built bar sequences and a detector harness for the MES pilot tests.

Every price below is chosen by hand; expectations in the tests are computed
by hand from these numbers (see the comments next to each scenario), never by
calling the production code under test.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from mes_pilot.bars import Aggregator, Bar, ET
from mes_pilot.levels import Level, LiquidityBook
from mes_pilot.setups import SetupDetector
from mes_pilot.structure import TimeframeState

UTC = timezone.utc
TICK = 0.25
CONTRACT = "TEST-MESZ6"
ONE = timedelta(minutes=1)
DAY = date(2026, 9, 15)  # an ordinary Tuesday (EDT)


def et(day: date, hh: int, mm: int) -> datetime:
    """ET wall-clock time -> aware UTC datetime."""
    return datetime.combine(day, time(hh, mm), ET).astimezone(UTC)


def bar(start: datetime, o: float, h: float, low: float, c: float, tf: int = 1, contract: str = CONTRACT,
        volume: float = 10.0) -> Bar:
    return Bar(start, start + timedelta(minutes=tf), o, h, low, c, volume, contract, tf)


def bars_tf(start: datetime, tf: int, rows: list[tuple]) -> list[Bar]:
    """Consecutive tf-minute bars from (o, h, l, c) rows."""
    return [bar(start + i * timedelta(minutes=tf), *row, tf=tf) for i, row in enumerate(rows)]


# Flat filler: every M1 and every M5 bar of it is O 5000 H 5000.5 L 4999.5 C 5000
# (true range exactly 1.0, no strict pivots, no gaps, efficiency ratio undefined).
FLAT = (5000.0, 5000.5, 4999.5, 5000.0)


def flat_m1(start: datetime, minutes: int, row: tuple = FLAT) -> list[Bar]:
    return [bar(start + i * ONE, *row) for i in range(minutes)]


# ---------------------------------------------------------------------------
# REVERSAL_R1 long scenario, relative to the sweep M5 bar start S.
#
# Premarked (preset) levels: TEST_LOW SELL_SIDE 4999.00, TEST_HIGH BUY_SIDE 5005.00.
#   S-90 .. S-25 : 14 flat M5 bars (as M1)
#   S-20         : M5 pivot bar, high 5001.00 (one M1 bar reaches it)
#   S-15 .. S-5  : 3 flat M5 bars -> pivot S-20, right-hand bars S-15 and S-10, so the
#                  swing high 5001 is confirmed only at S-5 (end of the S-10 bar)
#   S            : sweep M5 bar O 5000 H 5000.25 L 4998.50 C 4999.50
#                  (low 2 ticks through 4999, close back above) -> OBSERVING at S+5
#   S+5          : displacement M5 O 4999.50 H 5002.00 L 4999.25 C 5001.75
#                  prior ATR(14) = (9*1.0 + 1.5 + 3*1.0 + 1.75)/14 = 1.0893; body 2.25 >= 1.0893;
#                  close 0.25 below high <= 25% of range 2.75; close 5001.75 >= swing 5001 + 1 tick (BOS)
#                  -> ARMED at S+10. zone = [ (4998.5+5002)/2, 5001 ] = [5000.25, 5001.00],
#                  stop = 4998.50 - 0.25 = 4998.25, target = 5005.00, expires S+25.
#                  Its last M1 bar (S+9) is shaped like a valid retest (bullish, low 5000.75 in
#                  zone): it started before the setup armed, so it must NOT confirm.
#   S+10 (M1)    : retest O 5001.00 H 5001.50 L 5000.50 C 5001.25 -> CONFIRMED at S+11
# ---------------------------------------------------------------------------
LOW_LEVEL = 4999.0
TARGET_LEVEL = 5005.0
R1_ZONE = (5000.25, 5001.0)
R1_STOP = 4998.25

SWEEP_M1 = [  # aggregate O 5000 H 5000.25 L 4998.5 C 4999.5
    (5000.0, 5000.25, 4999.75, 4999.75),
    (4999.75, 4999.75, 4998.5, 4998.75),
    (4998.75, 4999.25, 4998.75, 4999.0),
    (4999.0, 4999.5, 4999.0, 4999.25),
    (4999.25, 4999.5, 4999.25, 4999.5),
]
NO_SWEEP_M1 = [  # low stops exactly AT 4999.00: touch, no 1-tick trade-through
    (5000.0, 5000.25, 4999.75, 4999.75),
    (4999.75, 4999.75, 4999.0, 4999.25),
    (4999.25, 4999.5, 4999.25, 4999.25),
    (4999.25, 4999.5, 4999.25, 4999.5),
    (4999.5, 4999.5, 4999.25, 4999.5),
]
DISPLACEMENT_M1 = [  # aggregate O 4999.5 H 5002 L 4999.25 C 5001.75
    (4999.5, 5000.0, 4999.25, 5000.0),
    (5000.0, 5000.75, 4999.75, 5000.5),
    (5000.5, 5001.25, 5000.25, 5001.0),
    (5001.0, 5001.75, 5000.75, 5001.5),
    (5001.0, 5002.0, 5000.75, 5001.75),   # retest-shaped, but before arming
]
WEAK_M1 = [  # aggregate O 4999.5 H 5000.5 L 4999.25 C 5000.25: body 0.75 < ATR 1.09
    (4999.5, 5000.0, 4999.25, 5000.0),
    (5000.0, 5000.5, 4999.75, 5000.25),
    (5000.25, 5000.5, 5000.0, 5000.25),
    (5000.25, 5000.5, 5000.0, 5000.25),
    (5000.25, 5000.5, 5000.0, 5000.25),
]
RETEST = (5001.0, 5001.5, 5000.5, 5001.25)
ABOVE_ZONE = (5002.0, 5002.5, 5001.5, 5002.25)   # never trades into the zone, no stop/target
HOLD = (5001.25, 5001.75, 5000.75, 5001.5)       # after an entry at 5001.50: no stop, no target


def r1_long_prefix(day: date = DAY, sweep_at: tuple[int, int] = (9, 30), *, sweep=SWEEP_M1,
                   displacement=DISPLACEMENT_M1) -> list[Bar]:
    """M1 bars from S-90 through the end of the displacement M5 bar (S+9)."""
    s = et(day, *sweep_at)
    out = flat_m1(s - timedelta(minutes=90), 70)                      # S-90 .. S-21
    out += [bar(s - timedelta(minutes=20), 5000.0, 5001.0, 4999.5, 5000.0)]  # pivot high 5001
    out += flat_m1(s - timedelta(minutes=19), 19)                     # S-19 .. S-1
    out += [bar(s + i * ONE, *row) for i, row in enumerate(sweep)]
    out += [bar(s + (5 + i) * ONE, *row) for i, row in enumerate(displacement)]
    return out


def preset_levels(book: LiquidityBook, known_at: datetime) -> None:
    """Directly premark the two scenario levels (focused-unit-test shortcut, documented)."""
    book.levels["TEST_LOW"] = Level("TEST_LOW", "TEST_LOW", "SELL_SIDE", LOW_LEVEL, known_at)
    book.levels["TEST_HIGH"] = Level("TEST_HIGH", "TEST_HIGH", "BUY_SIDE", TARGET_LEVEL, known_at)


# ---------------------------------------------------------------------------
# CONTINUATION_C1 long scenario, relative to the gap's A bar start A (default 09:30).
#   A-90 .. A-5 : flat M5 bars (as M1); prior ATR before B = 1.0
#   A    (M5)   : flat O 5000 H 5000.5 L 4999.5 C 5000
#   A+5  (M5) B : displacement O 5000 H 5002.5 L 4999.75 C 5002.25 (body 2.25 >= 1.0, close 1 tick off high)
#   A+10 (M5) C : O 5002.25 H 5003 L 5001.25 C 5002.75 -> BULL FVG [5000.50, 5001.25] created A+15
#                 ER(20) = |5002.75-5000| / (2.25+0.5) = 1.0 >= 0.35; target TEST_HIGH 5005
#                 -> ARMED at A+15, expires A+30. Its last M1 bar (A+14) has low 5001.25 = gap top:
#                 shaped like a touch, but it precedes arming and must not count.
#   A+15 M1     : O 5002.75 H 5002.75 L 5001.75 C 5002.00 (bearish, no touch)
#   A+16 M1     : O 5002.00 H 5002.00 L 5001.00 C 5001.25 (bearish, touch; pullback low 5001.00)
#   A+17 M1     : O 5001.50 H 5002.50 L 5001.50 C 5002.25 (bullish, no touch, close > 5002.00 = open
#                 of the latest bearish pullback candle) -> CONFIRMED at A+18, stop 5000.75
# ---------------------------------------------------------------------------
C1_GAP = (5000.5, 5001.25)
C1_STOP = 5000.75
C1_B_M1 = [  # aggregate O 5000 H 5002.5 L 4999.75 C 5002.25
    (5000.0, 5000.5, 4999.75, 5000.25),
    (5000.25, 5001.0, 5000.25, 5001.0),
    (5001.0, 5001.75, 5001.0, 5001.5),
    (5001.5, 5002.25, 5001.5, 5002.0),
    (5002.0, 5002.5, 5002.0, 5002.25),
]
C1_B_WEAK_M1 = [  # aggregate O 5000 H 5001.5 L 4999.75 C 5000.75: body 0.75 < ATR 1.0
    (5000.0, 5000.5, 4999.75, 5000.25),
    (5000.25, 5001.0, 5000.25, 5000.75),
    (5000.75, 5001.5, 5000.5, 5000.75),
    (5000.75, 5001.0, 5000.5, 5000.75),
    (5000.75, 5001.0, 5000.5, 5000.75),
]
C1_C_M1 = [  # aggregate O 5002.25 H 5003 L 5001.25 C 5002.75
    (5002.25, 5003.0, 5002.0, 5002.5),
    (5002.5, 5002.75, 5002.0, 5002.25),
    (5002.25, 5002.5, 5001.75, 5002.0),
    (5002.0, 5002.5, 5001.75, 5002.25),
    (5002.25, 5002.75, 5001.25, 5002.75),   # touch-shaped, before arming
]
C1_C_AFTER_WEAK_M1 = [  # aggregate O 5000.75 H 5002 L 5001 C 5001.75 -> gap [5000.5, 5001.0]
    (5000.75, 5001.5, 5001.0, 5001.25),
    (5001.25, 5002.0, 5001.25, 5001.75),
    (5001.75, 5002.0, 5001.5, 5001.75),
    (5001.75, 5002.0, 5001.5, 5001.75),
    (5001.75, 5002.0, 5001.5, 5001.75),
]
C1_PULLBACK = [
    (5002.75, 5002.75, 5001.75, 5002.0),
    (5002.0, 5002.0, 5001.0, 5001.25),
    (5001.5, 5002.5, 5001.5, 5002.25),
]
C1_ABOVE = (5003.0, 5003.5, 5002.5, 5003.25)


def c1_long_prefix(day: date = DAY, a_at: tuple[int, int] = (9, 30), *, b=C1_B_M1, c=C1_C_M1) -> list[Bar]:
    """M1 bars from A-90 through the end of the C bar (A+14)."""
    a = et(day, *a_at)
    out = flat_m1(a - timedelta(minutes=90), 95)                      # A-90 .. A+4 (A is flat)
    out += [bar(a + (5 + i) * ONE, *row) for i, row in enumerate(b)]
    out += [bar(a + (10 + i) * ONE, *row) for i, row in enumerate(c)]
    return out


# ---------------------------------------------------------------------------
class Harness:
    """TimeframeStates + LiquidityBook + SetupDetector wired in the engine's order.

    Per completed M1 bar: book.on_m1 -> M1 state -> aggregated M5/M15/H1/H4
    pushes (H1/H4 swings and gaps premarked) -> detector.on_m5 for any M5 bar
    completed by this M1 -> detector.on_m1. Bias is preset on H1/H4 (documented
    focused-test shortcut: a real bias needs days of H1/H4 history).
    """

    def __init__(self, cfg, bias: str = "BULLISH", entry_window=(time(9, 30), time(11, 30))):
        s = cfg.strategy
        self.cfg = cfg
        self.tfs = {tf: TimeframeState(tf, TICK, s.swing_side_bars, s.atr_period, s.er_period)
                    for tf in (1, 5, 15, 60, 240)}
        self.aggs = {tf: Aggregator(tf) for tf in (5, 15, 60, 240)}
        self.book = LiquidityBook(TICK, cfg.session.asia, cfg.session.london, s.equal_tolerance_ticks)
        self.det = SetupDetector(cfg, self.tfs, self.book)
        self.tfs[60].bias = self.tfs[240].bias = bias
        self.window = entry_window
        self.confirmed: list = []
        self.confirmed_at: dict = {}

    def window_open(self, ts: datetime) -> bool:
        t = ts.astimezone(ET).time()
        return self.window[0] <= t < self.window[1]

    def feed(self, m1: Bar) -> list:
        self.book.on_m1(m1)
        self.tfs[1].push(m1)
        closed_m5 = []
        for tf, agg in self.aggs.items():
            for done in agg.push(m1):
                ev = self.tfs[tf].push(done)
                if tf in (60, 240):
                    for sw in ev["new_swings"]:
                        self.book.add_swing(sw)
                    for g in ev["new_gaps"]:
                        self.book.add_gap(g)
                if tf == 5:
                    closed_m5.append(done)
        for m5 in closed_m5:
            self.det.on_m5(m5, self.window_open(m5.start))
        out = self.det.on_m1(m1)
        for st in out:
            self.confirmed.append(st)
            self.confirmed_at[st.setup_id] = m1.end
        return out

    def feed_all(self, bars: list[Bar]) -> list:
        out = []
        for b in bars:
            out += self.feed(b)
        return out

    def family(self, name: str) -> list:
        return [s for s in self.det.setups.values() if s.family == name]
