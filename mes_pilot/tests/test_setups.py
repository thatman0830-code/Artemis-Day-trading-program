"""REVERSAL_R1 / CONTINUATION_C1 state machines on hand-labeled sequences.

Harness note (documented shortcut): H1/H4 bias is PRESET on the timeframe
states and the swept/target levels are PREMARKED directly in the book, because
producing them from raw history needs days of bars. Everything else (M1->M5
aggregation, swings, gaps, ATR, sweep, displacement, retest, CISD) runs through
the production code in the engine's order. Expected values are derived by hand
in tests/helpers.py.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from mes_pilot.bars import Bar
from mes_pilot.levels import Level
from mes_pilot.tests.helpers import (
    ABOVE_ZONE, C1_ABOVE, C1_B_WEAK_M1, C1_C_AFTER_WEAK_M1, C1_GAP, C1_PULLBACK, C1_STOP, DAY, DISPLACEMENT_M1,
    Harness, NO_SWEEP_M1, R1_STOP, R1_ZONE, RETEST, SWEEP_M1, TARGET_LEVEL, WEAK_M1, bar, c1_long_prefix, et,
    flat_m1, preset_levels, r1_long_prefix,
)


def at(hh, mm):
    return et(DAY, hh, mm)


def run(cfg, bars, *, bias="BULLISH", levels=True):
    h = Harness(cfg, bias=bias)
    if levels:
        preset_levels(h.book, at(7, 0))
    h.feed_all(bars)
    return h


def only(h, family):
    found = h.family(family)
    assert len(found) == 1, [(s.family, s.state, s.reason) for s in h.det.setups.values()]
    return found[0]


# =============================================================== REVERSAL_R1
def test_r1_valid_sweep_displacement_bos_then_m1_retest(cfg):
    h = run(cfg, r1_long_prefix())
    st = only(h, "REVERSAL_R1")
    assert [t["state"] for t in st.transitions] == ["OBSERVING", "ARMED"]
    assert st.transitions[0]["at_utc"] == at(9, 35).isoformat()
    assert st.state == "ARMED" and st.armed_at == at(9, 40) and st.expires_at == at(9, 55)
    assert st.zone == R1_ZONE and st.stop == R1_STOP
    assert (st.target, st.target_level_id) == (TARGET_LEVEL, "TEST_HIGH")
    assert st.refs["structure"] == "BOS" and st.refs["broken_level"] == 5001.0
    assert st.refs["swept_level_id"] == "TEST_LOW" and st.refs["sweep_extreme"] == 4998.5
    assert st.refs["displacement_info"]["prior_atr"] == pytest.approx(15.25 / 14)
    # Regression: the retest-shaped last M1 bar of the arming candle (09:39) did not confirm.
    assert h.confirmed == []
    assert h.feed(bar(at(9, 40), *RETEST)) == [st]
    assert st.state == "CONFIRMED" and st.confirmed_at == at(9, 41)


def test_r1_missing_sweep_creates_nothing(cfg):
    h = run(cfg, r1_long_prefix(sweep=NO_SWEEP_M1) + [bar(at(9, 40), *RETEST)])
    assert h.family("REVERSAL_R1") == [] and h.confirmed == []


def test_r1_missing_displacement_expires_after_six_m5_bars(cfg):
    bars = r1_long_prefix(displacement=WEAK_M1)
    h = run(cfg, bars + flat_m1(at(9, 40), 20))          # through 09:59 (M5 ending 10:00)
    st = only(h, "REVERSAL_R1")
    assert st.state == "OBSERVING" and st.confirmations["displacement"] is False
    h.feed_all(flat_m1(at(10, 0), 5))                     # M5 ending 10:05 > sweep end + 25 min
    assert (st.state, st.reason) == ("EXPIRED", "NO_DISPLACEMENT_WITHIN_6_M5_BARS")
    assert h.confirmed == []


def test_r1_stop_traded_before_entry_invalidates(cfg):
    h = run(cfg, r1_long_prefix() + [bar(at(9, 40), 5001.0, 5001.25, 4998.25, 4998.5)])
    st = only(h, "REVERSAL_R1")
    assert (st.state, st.reason) == ("INVALIDATED", "STOP_LEVEL_TRADED_BEFORE_ENTRY")
    assert h.feed(bar(at(9, 41), *RETEST)) == []


def test_r1_target_consumed_before_entry_invalidates(cfg):
    h = run(cfg, r1_long_prefix() + [bar(at(9, 40), 5001.75, 5005.25, 5001.5, 5004.0)])
    st = only(h, "REVERSAL_R1")
    assert (st.state, st.reason) == ("INVALIDATED", "TARGET_CONSUMED_BEFORE_ENTRY")
    assert h.feed(bar(at(9, 41), *RETEST)) == []


def test_r1_armed_setup_expires_15_minutes_after_arming(cfg):
    h = run(cfg, r1_long_prefix() + [bar(at(9, 40) + timedelta(minutes=i), *ABOVE_ZONE) for i in range(15)])
    st = only(h, "REVERSAL_R1")
    assert st.state == "ARMED"                            # last bar ended exactly at 09:55
    h.feed(bar(at(9, 55), *RETEST))                       # valid-looking retest, but too late
    assert (st.state, st.reason) == ("EXPIRED", "SETUP_LIFETIME_ELAPSED")
    assert st not in h.confirmed


def test_r1_bias_flip_invalidates_at_next_m5_close(cfg):
    h = run(cfg, r1_long_prefix())
    st = only(h, "REVERSAL_R1")
    h.tfs[60].bias = "BEARISH"            # simulate an H1 structure break (preset, documented)
    h.feed_all([bar(at(9, 40) + timedelta(minutes=i), *ABOVE_ZONE) for i in range(5)])
    assert (st.state, st.reason) == ("INVALIDATED", "BIAS_NO_LONGER_ALIGNED")
    assert h.feed(bar(at(9, 45), *RETEST)) == []


def test_r1_no_setup_from_premarket_sweep(cfg):
    # Same geometry 5 minutes earlier: the sweep M5 bar starts 09:25 (before the window).
    h = run(cfg, r1_long_prefix(sweep_at=(9, 25)) + [bar(at(9, 35), *RETEST)])
    assert h.family("REVERSAL_R1") == [] and h.confirmed == []


def test_r1_without_aligned_bias_creates_nothing(cfg):
    h = run(cfg, r1_long_prefix() + [bar(at(9, 40), *RETEST)], bias="NEUTRAL")
    assert h.det.setups == {}


def test_r1_one_setup_per_sweep_bar_even_when_levels_stack(cfg):
    """Regression: stacked levels swept by one bar used to create duplicate setups
    that confirmed together and were conflict-rejected by the engine."""
    h = Harness(cfg)
    preset_levels(h.book, at(7, 0))
    for lid, kind, price in [("H1_FVG_BULL:x", "H1_FVG_BULL", 4999.0), ("H4_FVG_BULL:x", "H4_FVG_BULL", 4999.0)]:
        h.book.levels[lid] = Level(lid, kind, "SELL_SIDE", price, at(7, 0))
    h.feed_all(r1_long_prefix())
    st = only(h, "REVERSAL_R1")
    # Equal price -> kind priority H4 > H1 > other.
    assert st.refs["swept_level_id"] == "H4_FVG_BULL:x"
    assert st.refs["swept_level_ids"] == ["H1_FVG_BULL:x", "H4_FVG_BULL:x", "TEST_LOW"]
    assert [x["level_id"] for x in st.refs["swept_levels"]] == ["H4_FVG_BULL:x", "H1_FVG_BULL:x", "TEST_LOW"]
    # Re-delivering the same sweep bar does not create a second setup.
    h.det.on_m5(bar(at(9, 30), 5000.0, 5000.25, 4998.5, 4999.5, tf=5), True)
    assert len(h.family("REVERSAL_R1")) == 1
    assert h.feed(bar(at(9, 40), *RETEST)) == [st]


def test_r1_primary_level_is_the_deepest_swept(cfg):
    h = Harness(cfg)
    preset_levels(h.book, at(7, 0))
    h.book.levels["H1_SWING_LOW:x"] = Level("H1_SWING_LOW:x", "H1_SWING_LOW", "SELL_SIDE", 4998.75, at(7, 0))
    h.feed_all(r1_long_prefix())
    st = only(h, "REVERSAL_R1")
    assert st.refs["swept_level_id"] == "H1_SWING_LOW:x" and st.refs["swept_price"] == 4998.75


def test_detector_leaves_setups_alone_once_engine_owns_them(cfg):
    """Regression: ENTRY_PENDING/RISK_APPROVED setups used to be re-evaluated (bias flip -> INVALIDATED)."""
    h = run(cfg, r1_long_prefix())
    st = only(h, "REVERSAL_R1")
    h.feed(bar(at(9, 40), *RETEST))
    st.move("ENTRY_PENDING", at(9, 41), "INTENT_QUEUED")
    h.tfs[60].bias = "BEARISH"
    h.feed_all([bar(at(9, 41) + timedelta(minutes=i), *ABOVE_ZONE) for i in range(4)])   # M5 closes 09:45
    assert st.state == "ENTRY_PENDING"


def _mirror(b: Bar, m=10000.0) -> Bar:
    return replace(b, open=m - b.open, high=m - b.low, low=m - b.high, close=m - b.close)


def test_r1_short_is_the_exact_mirror(cfg):
    h = Harness(cfg, bias="BEARISH")
    h.book.levels["HI"] = Level("HI", "TEST_HIGH", "BUY_SIDE", 5001.0, at(7, 0))      # mirror of 4999
    h.book.levels["LO"] = Level("LO", "TEST_LOW", "SELL_SIDE", 4995.0, at(7, 0))      # mirror of 5005
    h.feed_all([_mirror(b) for b in r1_long_prefix()])
    st = only(h, "REVERSAL_R1")
    assert st.direction == "SHORT" and st.state == "ARMED"
    assert st.zone == (4999.0, 4999.75) and st.stop == 5001.75 and st.target == 4995.0
    assert h.feed(_mirror(bar(at(9, 40), *RETEST))) == [st]


# =============================================================== CONTINUATION_C1
def test_c1_valid_displacement_fvg_pullback_respect_and_cisd(cfg):
    h = run(cfg, c1_long_prefix())
    st = only(h, "CONTINUATION_C1")
    assert st.state == "ARMED" and st.armed_at == at(9, 45) and st.expires_at == at(10, 0)
    assert st.zone == C1_GAP and st.target == TARGET_LEVEL
    assert st.refs["efficiency_ratio"] == pytest.approx(1.0) and st.refs["prior_atr"] == pytest.approx(1.0)
    # Regression: the touch-shaped last M1 of the C candle (low 5001.25) preceded arming.
    assert st.refs["touched"] is False and st.refs["pullback_extreme"] is None
    out = h.feed_all([bar(at(9, 45) + timedelta(minutes=i), *row) for i, row in enumerate(C1_PULLBACK)])
    assert out == [st]
    assert st.state == "CONFIRMED" and st.confirmed_at == at(9, 48)
    assert st.stop == C1_STOP and st.refs["cisd_level"] == 5002.0
    assert st.refs["cisd_candle_start"] == at(9, 46).isoformat()


def test_c1_missing_displacement_rejected(cfg):
    h = run(cfg, c1_long_prefix(b=C1_B_WEAK_M1, c=C1_C_AFTER_WEAK_M1))
    st = only(h, "CONTINUATION_C1")
    assert (st.state, st.reason) == ("REJECTED", "C1_NO_DISPLACEMENT_FVG")
    assert st.refs["gap_low"] == 5000.5 and st.refs["gap_high"] == 5001.0


def test_c1_m1_close_below_gap_invalidates(cfg):
    h = run(cfg, c1_long_prefix() + [bar(at(9, 45), 5002.75, 5002.75, 5000.0, 5000.25)])
    st = only(h, "CONTINUATION_C1")
    assert (st.state, st.reason) == ("INVALIDATED", "GAP_DISRESPECTED_M1_CLOSE")


def test_c1_target_consumed_before_entry_invalidates(cfg):
    h = run(cfg, c1_long_prefix() + [bar(at(9, 45), 5002.75, 5005.25, 5002.5, 5005.0)])
    st = only(h, "CONTINUATION_C1")
    assert (st.state, st.reason) == ("INVALIDATED", "TARGET_CONSUMED_BEFORE_ENTRY")


def test_c1_expires_15_minutes_after_arming(cfg):
    h = run(cfg, c1_long_prefix() + [bar(at(9, 45) + timedelta(minutes=i), *C1_ABOVE) for i in range(15)])
    st = only(h, "CONTINUATION_C1")
    assert st.state == "ARMED"
    h.feed(bar(at(10, 0), *C1_ABOVE))
    assert (st.state, st.reason) == ("EXPIRED", "SETUP_LIFETIME_ELAPSED")


def test_c1_bias_flip_invalidates(cfg):
    h = run(cfg, c1_long_prefix())
    st = only(h, "CONTINUATION_C1")
    h.tfs[240].bias = "BEARISH"
    h.feed_all([bar(at(9, 45) + timedelta(minutes=i), *C1_ABOVE) for i in range(5)])
    assert (st.state, st.reason) == ("INVALIDATED", "BIAS_NO_LONGER_ALIGNED")


def test_c1_no_setup_before_0930(cfg):
    h = run(cfg, c1_long_prefix(a_at=(9, 15)))           # C bar starts 09:25
    assert h.family("CONTINUATION_C1") == []


def test_c1_no_target_rejected(cfg):
    h = run(cfg, c1_long_prefix(), levels=False)
    st = only(h, "CONTINUATION_C1")
    assert (st.state, st.reason) == ("REJECTED", "NO_UNCONSUMED_TARGET")


def test_reset_cancels_live_setups_with_reset_time_and_keeps_them_for_logging(cfg):
    h = run(cfg, r1_long_prefix())
    st = only(h, "REVERSAL_R1")
    h.det.reset(at=at(9, 41))
    assert (st.state, st.reason) == ("CANCELLED", "STRUCTURE_RESET")
    assert st.transitions[-1]["at_utc"] == at(9, 41).isoformat()
    assert st.setup_id in h.det.setups and h.det.active() == []


def test_identical_inputs_give_identical_setups(cfg):
    a, b = run(cfg, r1_long_prefix()), run(cfg, r1_long_prefix())
    assert list(a.det.setups) == list(b.det.setups)
    assert [s.transitions for s in a.det.setups.values()] == [s.transitions for s in b.det.setups.values()]
