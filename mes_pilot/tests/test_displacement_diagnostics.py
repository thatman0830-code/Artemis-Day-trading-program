"""Displacement diagnostics and SetupDetector funnel counters are PURE additions.

- ``TimeframeState.is_displacement`` returns exactly the boolean of the original
  predicate (copied verbatim below as the reference) over a grid of candles.
- Every documented ``reason`` code is reachable and is the FIRST failing subcondition.
- A C1 rejection records the displacement detail in ``refs["displacement"]``.
- ``SetupDetector.counters`` counts the per-M5 funnel without changing decisions.
"""
from __future__ import annotations

import itertools
from datetime import timedelta

import pytest

from mes_pilot.bars import Bar
from mes_pilot.structure import TimeframeState
from mes_pilot.tests.helpers import (
    C1_B_WEAK_M1, C1_C_AFTER_WEAK_M1, C1_PULLBACK, DAY, RETEST, TICK, Harness, bar, bars_tf, c1_long_prefix, et,
    preset_levels, r1_long_prefix,
)

T0 = et(DAY, 9, 0)
PRIOR = [(100, 101, 99, 100), (100, 101, 99, 100.5), (100.5, 101.5, 99.5, 100), (100, 101, 99, 100.5)]  # ATR(3)=2.0


def _original(st: TimeframeState, bar: Bar, direction: str, body_mult: float, outer: float) -> bool:
    """The pre-diagnostics predicate, verbatim (reference for equivalence)."""
    prior_atr = st.atr_before(bar.start)
    rng = bar.high - bar.low
    if prior_atr is None or rng <= 0:
        return False
    if direction == "LONG":
        ok_dir = bar.bullish and (bar.high - bar.close) <= outer * rng + 1e-9
    else:
        ok_dir = bar.bearish and (bar.close - bar.low) <= outer * rng + 1e-9
    return ok_dir and bar.body >= body_mult * prior_atr - 1e-9


def _state(prior=PRIOR) -> TimeframeState:
    st = TimeframeState(5, TICK, atr_period=3)
    for b in bars_tf(T0, 5, prior):
        st.push(b)
    return st


def _candle(o, h, low, c) -> Bar:
    return bar(T0 + timedelta(minutes=20), o, h, low, c, tf=5)


def test_boolean_identical_to_original_predicate_over_a_grid():
    with_atr, without_atr = _state(), TimeframeState(5, TICK, atr_period=3)
    prices = [99.0 + 0.25 * i for i in range(17)]          # 99.00 .. 103.00 in ticks
    n = 0
    for o, c in itertools.product(prices, prices):
        for low in (min(o, c) - x for x in (0.0, 0.25, 1.0)):
            for high in (max(o, c) + x for x in (0.0, 0.25, 1.0)):
                cand = _candle(o, high, low, c)
                for st, direction, mult, outer in itertools.product(
                        (with_atr, without_atr), ("LONG", "SHORT"), (0.5, 1.0, 1.5), (0.1, 0.25, 0.5)):
                    ok, info = st.is_displacement(cand, direction, mult, outer)
                    assert ok is _original(st, cand, direction, mult, outer), (o, high, low, c, direction, mult, outer)
                    assert (info["reason"] == "PASS") is ok
                    assert info["status"] == ("UNKNOWN" if not info["data_available"] else "PASS" if ok else "FAIL")
                    n += 1
    assert n > 50000


@pytest.mark.parametrize("st_kind,ohlc,direction,reason", [
    ("empty", (100.75, 103, 100.5, 102.75), "LONG", "NO_PRIOR_ATR"),
    ("atr", (101, 101, 101, 101), "LONG", "ZERO_RANGE"),
    ("atr", (100.75, 103, 100.5, 102.75), "SHORT", "WRONG_DIRECTION"),
    ("atr", (100.75, 104, 100.5, 102.75), "LONG", "CLOSE_NOT_IN_OUTER_FRACTION"),
    ("atr", (101.0, 102.0, 100.75, 101.75), "LONG", "BODY_BELOW_ATR_MULT"),
    ("atr", (100.75, 103, 100.5, 102.75), "LONG", "PASS"),
])
def test_each_reason_code_is_reachable(st_kind, ohlc, direction, reason):
    st = TimeframeState(5, TICK, atr_period=3) if st_kind == "empty" else _state()
    ok, info = st.is_displacement(_candle(*ohlc), direction, 1.0, 0.25)
    assert info["reason"] == reason and ok is (reason == "PASS")
    assert set(info) >= {"candle", "prior_atr", "body", "range", "body_atr_ratio", "required_body", "body_mult",
                         "outer_fraction", "close_location", "direction_ok", "close_location_ok", "body_ok",
                         "data_available", "reason"}
    assert info["candle"] == {"start": (T0 + timedelta(minutes=20)).isoformat(),
                              "end": (T0 + timedelta(minutes=25)).isoformat(),
                              "o": ohlc[0], "h": ohlc[1], "l": ohlc[2], "c": ohlc[3]}


def test_all_subconditions_recorded_even_after_first_failure():
    # Bearish candle for LONG with weak body and close off the high: every check fails.
    ok, info = _state().is_displacement(_candle(101.5, 102, 100, 101), "LONG", 1.0, 0.25)
    assert not ok and info["reason"] == "WRONG_DIRECTION"
    assert (info["direction_ok"], info["close_location_ok"], info["body_ok"]) == (False, False, False)
    assert info["prior_atr"] == pytest.approx(2.0) and info["required_body"] == pytest.approx(2.0)
    assert info["body_atr_ratio"] == pytest.approx(0.25) and info["close_location"] == pytest.approx(0.5)
    assert info["data_available"] is True


def test_c1_rejection_records_the_failing_displacement_subcondition(cfg):
    h = Harness(cfg)
    preset_levels(h.book, et(DAY, 7, 0))
    h.feed_all(c1_long_prefix(b=C1_B_WEAK_M1, c=C1_C_AFTER_WEAK_M1))
    (st,) = [s for s in h.det.setups.values() if s.family == "CONTINUATION_C1"]
    assert (st.state, st.reason) == ("REJECTED", "C1_NO_DISPLACEMENT_FVG")
    d = st.refs["displacement"]
    # B = O 5000 H 5001.5 L 4999.75 C 5000.75: range 1.75, close 0.75 off the high (0.4286 > 0.25),
    # body 0.75 < 1.0 x ATR 1.0 -> first failing subcondition is the close location.
    assert d["reason"] == "CLOSE_NOT_IN_OUTER_FRACTION"
    assert (d["direction_ok"], d["close_location_ok"], d["body_ok"]) == (True, False, False)
    assert d["prior_atr"] == pytest.approx(1.0) and d["body"] == pytest.approx(0.75)
    assert d["close_location"] == pytest.approx(0.75 / 1.75)
    assert d["candle"]["start"] == st.refs["middle_bar_start"]


def test_r1_keeps_displacement_info_and_gains_shared_key(cfg):
    h = Harness(cfg)
    preset_levels(h.book, et(DAY, 7, 0))
    h.feed_all(r1_long_prefix())
    (st,) = [s for s in h.det.setups.values() if s.family == "REVERSAL_R1"]
    assert st.refs["displacement"] is st.refs["displacement_info"]
    assert st.refs["displacement"]["reason"] == "PASS"


def test_counters_on_c1_sequence(cfg):
    h = Harness(cfg)
    preset_levels(h.book, et(DAY, 7, 0))
    h.feed_all(c1_long_prefix())                       # 105 M1 bars -> 21 M5 bars, 3 in the window
    h.feed_all([bar(et(DAY, 9, 45) + timedelta(minutes=i), *row) for i, row in enumerate(C1_PULLBACK)])
    assert len(h.confirmed) == 1
    c = h.det.counters
    assert c["m5_bars"] == 21 and c["m5_window_bars"] == 3
    assert c["bias_aligned_long"] == 3 and c["bias_aligned_short"] == 0 and c["bias_neutral"] == 0
    assert c["m5_gaps_formed"] == 1 and c["sweeps_detected"] == 0
    assert c["setups_created_CONTINUATION_C1"] == 1 and c["setups_confirmed_CONTINUATION_C1"] == 1
    assert c["setups_created_REVERSAL_R1"] == 0
    h.det.reset_counters()
    assert sum(h.det.counters.values()) == 0


def test_counters_on_r1_sequence_and_neutral_bias(cfg):
    h = Harness(cfg)
    preset_levels(h.book, et(DAY, 7, 0))
    h.feed_all(r1_long_prefix())                       # 100 M1 -> 20 M5 bars, 2 in the window
    h.feed(bar(et(DAY, 9, 40), *RETEST))
    c = h.det.counters
    assert (c["m5_bars"], c["m5_window_bars"], c["bias_aligned_long"]) == (20, 2, 2)
    assert c["sweeps_detected"] == 1 and c["setups_created_REVERSAL_R1"] == 1
    assert c["setups_confirmed_REVERSAL_R1"] == 1 and c["m5_gaps_formed"] == 0

    n = Harness(cfg, bias="NEUTRAL")
    preset_levels(n.book, et(DAY, 7, 0))
    n.feed_all(r1_long_prefix())
    assert n.det.setups == {}
    assert (n.det.counters["bias_neutral"], n.det.counters["sweeps_detected"]) == (2, 0)


def test_counting_does_not_change_decisions(cfg):
    """Same input, counters cleared midway in one run: identical setups and transitions."""
    a, b = Harness(cfg), Harness(cfg)
    for h in (a, b):
        preset_levels(h.book, et(DAY, 7, 0))
    seq = c1_long_prefix() + [bar(et(DAY, 9, 45) + timedelta(minutes=i), *row) for i, row in enumerate(C1_PULLBACK)]
    a.feed_all(seq)
    for i, x in enumerate(seq):
        if i % 7 == 0:
            b.det.reset_counters()
        b.feed(x)
    assert [(s.setup_id, s.transitions, s.refs) for s in a.det.setups.values()] == \
           [(s.setup_id, s.transitions, s.refs) for s in b.det.setups.values()]
