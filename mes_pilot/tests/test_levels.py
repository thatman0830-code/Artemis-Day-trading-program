"""Premarked liquidity levels: windows, rollover, consumption, target selection."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from mes_pilot.levels import Level, LiquidityBook
from mes_pilot.structure import Swing, sweep
from mes_pilot.tests.helpers import TICK, bar, et

MON = date(2026, 9, 14)
TUE = date(2026, 9, 15)   # session TUE starts MON 18:00 ET


def book():
    return LiquidityBook(TICK, (time(19, 0), time(0, 0)), (time(2, 0), time(5, 0)))


def kinds(b: LiquidityBook, as_of):
    return sorted(lv.kind for lv in b.active(as_of))


def test_pdh_pdl_appear_only_at_the_1800_et_rollover():
    b = book()
    b.on_m1(bar(et(MON, 17, 57), 5000, 5010, 4995, 5005))
    b.on_m1(bar(et(MON, 17, 58), 5005, 5006, 4990, 5000))
    b.on_m1(bar(et(MON, 17, 59), 5000, 5001, 4999, 5000))
    assert kinds(b, et(MON, 18, 0)) == []          # the MON session is not complete yet
    b.on_m1(bar(et(MON, 18, 0), 5000, 5001, 4999, 5000))
    pdh, pdl = b.levels[f"PDH:{MON}"], b.levels[f"PDL:{MON}"]
    assert (pdh.price, pdl.price) == (5010, 4990)
    assert pdh.known_at == pdl.known_at == et(MON, 18, 0)
    assert kinds(b, et(MON, 17, 59)) == []          # not knowable before the rollover
    assert kinds(b, et(MON, 18, 1)) == ["PDH", "PDL"]


def _asia_bars(b, last_hl=(5004, 5001)):
    b.on_m1(bar(et(MON, 18, 0), 5000, 5001, 4999, 5000))
    b.on_m1(bar(et(MON, 19, 0), 5002, 5005, 5000, 5003))   # Asia high 5005 so far
    b.on_m1(bar(et(MON, 23, 59), 5003, last_hl[0], last_hl[1], 5002))


def test_asia_window_levels_publish_only_after_the_window_completes():
    b = book()
    _asia_bars(b, last_hl=(5004, 4998))                       # Asia: H 5005, L 4998
    assert not any(k.startswith("ASIA") for k in kinds(b, et(TUE, 0, 0)))
    b.on_m1(bar(et(TUE, 0, 0), 5002, 5003, 5001, 5002))       # first bar outside the window
    hi, lo = b.levels[f"ASIA_H:{TUE}"], b.levels[f"ASIA_L:{TUE}"]
    assert (hi.price, lo.price, hi.known_at) == (5005, 4998, et(TUE, 0, 0))
    assert hi.consumed_at is None and lo.consumed_at is None


def test_bar_that_completes_a_window_can_consume_it():
    """Regression: the window must be published before consumption is evaluated for that bar."""
    b = book()
    _asia_bars(b)
    b.on_m1(bar(et(TUE, 0, 0), 5004, 5005.25, 5003, 5005))  # 1 tick through the Asia high 5005
    assert b.levels[f"ASIA_H:{TUE}"].consumed_at == et(TUE, 0, 1)


def test_london_window_and_previous_day_windows_are_dropped_on_rollover():
    b = book()
    b.on_m1(bar(et(TUE, 1, 59), 5000, 5001, 4999, 5000))
    b.on_m1(bar(et(TUE, 2, 0), 5000, 5003, 4997, 5001))
    b.on_m1(bar(et(TUE, 4, 59), 5001, 5002, 4998, 5001))
    assert not any(k.startswith("LONDON") for k in kinds(b, et(TUE, 5, 0)))
    b.on_m1(bar(et(TUE, 5, 0), 5001, 5002, 5000, 5001))
    assert (b.levels[f"LONDON_H:{TUE}"].price, b.levels[f"LONDON_L:{TUE}"].price) == (5003, 4997)
    b.on_m1(bar(et(TUE, 18, 0), 5001, 5002, 5000, 5001))     # next session
    assert not any(k.startswith("LONDON") for k in (lv.kind for lv in b.levels.values()))
    assert {lv.kind for lv in b.levels.values()} == {"PDH", "PDL"}


def test_consumption_requires_one_tick_trade_through_after_known():
    b = book()
    t = et(TUE, 10, 0)
    b.levels["H"] = Level("H", "TEST", "BUY_SIDE", 5010, t)
    b.levels["L"] = Level("L", "TEST", "SELL_SIDE", 4990, t)
    b.on_m1(bar(t - timedelta(minutes=1), 5000, 5015, 4985, 5000))  # before known: ignored
    assert b.levels["H"].consumed_at is None and b.levels["L"].consumed_at is None
    b.on_m1(bar(t, 5005, 5010, 4990, 5000))                         # exact touches only
    assert b.levels["H"].consumed_at is None and b.levels["L"].consumed_at is None
    b.on_m1(bar(t + timedelta(minutes=1), 5005, 5010.25, 4990, 5000))
    assert b.levels["H"].consumed_at == t + timedelta(minutes=2)
    b.on_m1(bar(t + timedelta(minutes=2), 4995, 4996, 4989.75, 4995))
    assert b.levels["L"].consumed_at == t + timedelta(minutes=3)


def test_swing_level_known_at_confirmation_not_at_pivot():
    b = book()
    pivot, confirmed = et(TUE, 8, 0), et(TUE, 11, 0)
    b.add_swing(Swing("HIGH", 5020, pivot, confirmed, 60))
    lid = f"H1_SWING_HIGH:{pivot.isoformat()}"
    assert b.active(confirmed - timedelta(minutes=1)) == []
    b.on_m1(bar(confirmed - timedelta(minutes=1), 5019, 5021, 5018, 5019))   # before confirmation
    assert b.levels[lid].consumed_at is None
    b.on_m1(bar(confirmed, 5019, 5020.25, 5018, 5019))
    assert b.levels[lid].consumed_at == confirmed + timedelta(minutes=1)


def test_active_is_as_of_so_a_completed_m5_sweep_sees_the_level_it_swept():
    """Regression (coordinator repro): M1 bars inside the M5 sweep consume the level first."""
    b = book()
    b.levels["X"] = Level("X", "TEST", "SELL_SIDE", 100.0, et(TUE, 9, 0))
    rows = [(101, 101.5, 100.5, 101), (101, 101, 100.25, 100.5), (100.5, 100.5, 99.0, 99.5),
            (99.5, 100.5, 99.25, 100.25), (100.25, 101.25, 100, 101)]
    for i, row in enumerate(rows):
        b.on_m1(bar(et(TUE, 9, 50 + i), *row))
    assert b.levels["X"].consumed_at == et(TUE, 9, 53)
    m5 = bar(et(TUE, 9, 50), 101, 101.5, 99.0, 101, tf=5)
    assert [lv.level_id for lv in b.active(m5.start, "SELL_SIDE")] == ["X"]
    assert sweep(m5, 100.0, "SELL_SIDE", TICK, 1)
    assert b.active(m5.end, "SELL_SIDE") == []
    assert b.active(et(TUE, 9, 53), "SELL_SIDE") == []          # consumed exactly at as_of


def test_nearest_target_skips_consumed_unknown_and_too_close_levels():
    b = book()
    t = et(TUE, 10, 0)
    later = t + timedelta(minutes=30)
    b.levels["consumed"] = Level("consumed", "TEST", "BUY_SIDE", 5003, t, consumed_at=t + timedelta(minutes=5))
    b.levels["too_close"] = Level("too_close", "TEST", "BUY_SIDE", 5000, t)        # not >= entry + 1 tick
    b.levels["future"] = Level("future", "TEST", "BUY_SIDE", 5004, later)          # not yet known
    b.levels["good"] = Level("good", "TEST", "BUY_SIDE", 5008, t)
    b.levels["far"] = Level("far", "TEST", "BUY_SIDE", 5012, t)
    b.levels["sell_consumed"] = Level("sell_consumed", "TEST", "SELL_SIDE", 4996, t, consumed_at=t + timedelta(minutes=5))
    b.levels["sell_good"] = Level("sell_good", "TEST", "SELL_SIDE", 4994, t)
    now = t + timedelta(minutes=10)
    assert b.nearest_target("LONG", 5000, now).level_id == "good"
    assert b.nearest_target("SHORT", 5000, now).level_id == "sell_good"
    # Even with an as_of BEFORE the consumption, a consumed level is never a target.
    assert b.nearest_target("LONG", 5000, t + timedelta(minutes=1)).level_id == "good"
    assert b.nearest_target("LONG", 5013, now) is None
