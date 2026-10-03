"""Causal structure primitives: delayed pivots, no look-ahead, determinism, FVGs, bias, displacement."""
from __future__ import annotations

from datetime import timedelta

import pytest

from mes_pilot.structure import TimeframeState, cisd_level, sweep
from mes_pilot.tests.helpers import DAY, TICK, bar, bars_tf, et

T0 = et(DAY, 8, 0)


def state(tf=5, atr_period=14):
    return TimeframeState(tf, TICK, swing_side=2, atr_period=atr_period, er_period=20)


# ---------------------------------------------------------------- pivots
def test_swing_high_usable_only_after_second_right_hand_bar_closes():
    rows = [  # pivot = bar 2 (high 103); lows rise so no swing low forms
        (100, 101, 99, 100.5),
        (100.5, 102, 99.5, 101.5),
        (101.5, 103, 100, 102),
        (102, 102.5, 100.5, 101),
        (101, 101.5, 100.75, 101.25),
    ]
    bars = bars_tf(T0, 5, rows)
    st = state()
    for b in bars[:4]:
        assert st.push(b)["new_swings"] == []
    # After the first right-hand bar the pivot is still not usable.
    assert st.latest_swing("HIGH", bars[3].end) is None
    ev = st.push(bars[4])
    assert [(s.kind, s.price) for s in ev["new_swings"]] == [("HIGH", 103)]
    sw = ev["new_swings"][0]
    assert sw.bar_start == bars[2].start
    assert sw.confirmed_at == bars[4].end
    assert st.latest_swing("HIGH", bars[4].end - timedelta(seconds=1)) is None
    assert st.latest_swing("HIGH", bars[4].end) == sw


def test_equal_highs_and_lows_are_not_strict_pivots():
    rows = [
        (100, 101, 99, 100),
        (100, 102, 98, 101),
        (101, 102, 98, 100),     # equal high 102 / equal low 98 with its left neighbour
        (100, 101, 99, 100),
        (100, 100.5, 99.5, 100),
        (100, 100.5, 99.5, 100),
    ]
    st = state()
    for b in bars_tf(T0, 5, rows):
        st.push(b)
    assert st.swings_high == [] and st.swings_low == []


# ---------------------------------------------------------------- leakage / determinism
def _zigzag(n=60):
    """Deterministic input path (not production code): 5-bar up/down legs with varied size."""
    rows, price = [], 5000.0
    for i in range(n):
        leg = (i // 5) % 2
        step = (0.75 + 0.25 * (i % 3)) * (1 if leg == 0 else -1)
        o = price
        c = price + step
        h = max(o, c) + 0.25 * (1 + i % 2)
        lo = min(o, c) - 0.25 * (1 + (i + 1) % 2)
        if i in (17, 33):            # two jump bars that leave fair-value gaps
            c, h = o + 4.0, o + 4.25
        rows.append((o, h, lo, c))
        price = c
    return bars_tf(T0, 5, rows)


def _features_now(st: TimeframeState, t):
    return {
        "bias": st.bias,
        "bias_event_at": st.bias_event_at,
        "bias_level": st.bias_level,
        **_features_as_of(st, t),
    }


def _features_as_of(st: TimeframeState, t):
    return {
        "swings_high": [(s.price, s.bar_start) for s in st.swings_high if s.confirmed_at <= t],
        "swings_low": [(s.price, s.bar_start) for s in st.swings_low if s.confirmed_at <= t],
        "latest_high": st.latest_swing("HIGH", t),
        "latest_low": st.latest_swing("LOW", t),
        "gaps": [(g.direction, g.low, g.high, g.created_at) for g in st.gaps if g.created_at <= t],
        "active_bull": [(g.low, g.high) for g in st.active_gaps("BULL", t)],
        "active_bear": [(g.low, g.high) for g in st.active_gaps("BEAR", t)],
        "atr": st.atr_before(t),
    }


def test_incremental_features_equal_prefix_recomputation_and_never_change_later():
    bars = _zigzag()
    live = state()
    recorded = []
    for b in bars:
        live.push(b)
        recorded.append(_features_now(live, b.end))
    assert any(r["gaps"] for r in recorded), "fixture must exercise gaps"
    assert any(r["swings_high"] for r in recorded) and any(r["swings_low"] for r in recorded)
    assert any(r["bias"] != "NEUTRAL" for r in recorded)

    for k, b in enumerate(bars):
        fresh = state()
        for x in bars[: k + 1]:
            fresh.push(x)
        # 1) feeding one at a time == recomputing from the same prefix
        assert _features_now(fresh, b.end) == recorded[k], f"prefix mismatch at bar {k}"
        # 2) appending later bars never changes what was knowable at time t
        assert _features_as_of(live, b.end) == {key: recorded[k][key] for key in _features_as_of(live, b.end)}, \
            f"look-ahead at bar {k}"


def test_identical_inputs_identical_outputs():
    a, b = state(), state()
    ev_a = [a.push(x) for x in _zigzag()]
    ev_b = [b.push(x) for x in _zigzag()]
    assert ev_a == ev_b
    assert (a.swings_high, a.swings_low, a.gaps, a.bias, a.bias_event_at) == \
        (b.swings_high, b.swings_low, b.gaps, b.bias, b.bias_event_at)


# ---------------------------------------------------------------- FVG lifecycle
FVG_ROWS = [
    (100, 101, 99.5, 100.75),        # A: high 101
    (100.75, 103.5, 100.5, 103.25),  # B
    (103.25, 104, 102, 103.75),      # C: low 102 -> BULL gap [101, 102] at C.end
]


def test_bull_fvg_created_only_at_c_close_then_touched_then_filled():
    st = state()
    bars = bars_tf(T0, 5, FVG_ROWS + [
        (103.75, 104, 101.75, 103),      # D: low 101.75 <= 102 -> touch, not filled
        (103, 103.25, 100.75, 101.5),    # E: low 100.75 <= 101, close 101.5 >= 101 -> filled
    ])
    st.push(bars[0]); st.push(bars[1])
    assert st.gaps == []
    ev = st.push(bars[2])
    (g,) = ev["new_gaps"]
    assert (g.direction, g.low, g.high, g.created_at, g.middle_bar_start) == ("BULL", 101, 102, bars[2].end, bars[1].start)
    st.push(bars[3])
    assert g.touches == 1 and g.active
    st.push(bars[4])
    assert g.touches == 2 and g.filled_at == bars[4].end and g.invalidated_at is None
    # As-of view: still active before E closed.
    assert st.active_gaps("BULL", bars[3].end) == [g]
    assert st.active_gaps("BULL", bars[4].end) == []


def test_bull_fvg_invalidated_by_close_below_gap():
    st = state()
    for b in bars_tf(T0, 5, FVG_ROWS + [(103, 103, 100.5, 100.75)]):   # close 100.75 < 101
        st.push(b)
    (g,) = st.gaps
    assert g.invalidated_at is not None and g.filled_at is None and not g.active


def test_bear_fvg_and_one_tick_minimum():
    st = state()
    for b in bars_tf(T0, 5, [(100, 100.5, 99, 99.25), (99.25, 99.5, 96.5, 96.75), (96.75, 98.75, 96, 97)]):
        st.push(b)
    (g,) = st.gaps   # A.low 99 - C.high 98.75 = 1 tick
    assert (g.direction, g.low, g.high) == ("BEAR", 98.75, 99)
    st2 = state()
    for b in bars_tf(T0, 5, [(100, 100.5, 99, 99.25), (99.25, 99.5, 96.5, 96.75), (96.75, 99, 96, 97)]):
        st2.push(b)
    assert st2.gaps == []   # C.high == A.low: zero-width, no gap


def test_gap_invalidated_by_the_bar_that_breaks_it_is_still_active_as_of_that_bar_start():
    """Regression: active_gaps(as_of) must reflect the gap state at as_of, not 'now'.

    Before the fix, an M5 displacement candle that closed through a bearish gap
    had already invalidated it when R1 asked for active gaps 'as of bar.start',
    so the inverse-FVG structure break could never be detected.
    """
    st = state()
    bars = bars_tf(T0, 5, [(100, 100.5, 99, 99.25), (99.25, 99.5, 96.5, 96.75), (96.75, 98.75, 96, 97),
                           (97, 99.5, 96.75, 99.25)])   # closes 99.25 > gap high 99 -> invalidates
    for b in bars:
        st.push(b)
    (g,) = st.gaps
    assert g.invalidated_at == bars[3].end
    assert st.active_gaps("BEAR", bars[3].start) == [g]
    assert st.active_gaps("BEAR", bars[3].end) == []


# ---------------------------------------------------------------- bias
BIAS_ROWS = [
    (99, 100, 98, 99),
    (99, 101, 98.5, 100),
    (100, 103, 99, 101),        # 2: pivot high 103
    (101, 102, 97, 97.5),       # 3: pivot low 97
    (97.5, 101.5, 97.5, 100),   # 4: confirms swing high 103
    (100, 101, 98, 100.5),      # 5: confirms swing low 97
    (100.5, 103.75, 100, 103.5),  # 6: close 103.5 >= 103 + 1 tick -> BULLISH
    (103.5, 104, 101, 101.5),   # 7: back below 103, bias persists
    (101.5, 102, 96.5, 96.75),  # 8: close 96.75 <= 97 - 1 tick -> BEARISH
]


def test_bias_set_by_close_beyond_swing_and_persists_until_opposite_break():
    st = state(tf=60)
    bars = bars_tf(T0, 60, BIAS_ROWS)
    seen = []
    for b in bars:
        st.push(b)
        seen.append(st.bias)
    assert seen == ["NEUTRAL"] * 6 + ["BULLISH", "BULLISH", "BEARISH"]
    assert st.bias_level == 97 and st.bias_event_at == bars[8].end


def test_bias_reference_swing_must_be_known_before_the_breaking_bar():
    """A swing confirmed by the same close must not shadow the older swing that close breaks."""
    rows = [
        (98, 99, 97, 98.5),
        (98.5, 99.5, 97.5, 99),
        (99, 100, 98, 99.5),          # pivot high 100 (confirmed at bar 4)
        (99.5, 99.5, 97.25, 97.5),
        (97.5, 99, 97.5, 98),
        (98, 99.75, 97.75, 99.5),
        (99.5, 104, 99.25, 99.75),    # pivot high 104 (confirmed at bar 8)
        (99.75, 101, 99.5, 100),
        (100, 100.75, 99.75, 100.5),  # close 100.5 >= 100 + 1 tick; same close confirms 104
    ]
    st = state(tf=60)
    bars = bars_tf(T0, 60, rows)
    for b in bars:
        st.push(b)
    assert [s.price for s in st.swings_high] == [100, 104]
    assert st.bias == "BULLISH" and st.bias_level == 100 and st.bias_event_at == bars[8].end


# ---------------------------------------------------------------- displacement
DISP_PRIOR = [(100, 101, 99, 100), (100, 101, 99, 100.5), (100.5, 101.5, 99.5, 100), (100, 101, 99, 100.5)]
# ATR(3) over the prior bars: TRs 2, 2, 2 -> 2.0. Candidate: body 2.0, range 2.5, close 0.25 off the high.
# Including the candidate itself would give (2 + 2 + 2.5)/3 = 2.1667 > body -> wrongly FAIL.
CANDIDATE = (100.75, 103, 100.5, 102.75)


@pytest.mark.parametrize("pushed", ["not_pushed", "pushed_last", "pushed_then_later_bar"])
def test_displacement_uses_atr_completed_before_the_candle(pushed):
    st = TimeframeState(5, TICK, atr_period=3)
    bars = bars_tf(T0, 5, DISP_PRIOR + [CANDIDATE, (102.75, 110, 102, 109)])
    for b in bars[:4]:
        st.push(b)
    cand = bars[4]
    if pushed != "not_pushed":
        st.push(cand)
    if pushed == "pushed_then_later_bar":
        st.push(bars[5])
    ok, info = st.is_displacement(cand, "LONG", 1.0, 0.25)
    assert info["prior_atr"] == pytest.approx(2.0)
    assert ok and info["status"] == "PASS"


def test_displacement_rejects_close_outside_outer_quarter_and_wrong_direction():
    st = TimeframeState(5, TICK, atr_period=3)
    for b in bars_tf(T0, 5, DISP_PRIOR):
        st.push(b)
    t = T0 + timedelta(minutes=20)
    weak_close = bar(t, 100.75, 104, 100.5, 102.75, tf=5)   # range 3.5; 1.25 off high > 0.875
    assert st.is_displacement(weak_close, "LONG", 1.0, 0.25)[0] is False
    assert st.is_displacement(bar(t, *CANDIDATE, tf=5), "SHORT", 1.0, 0.25)[0] is False
    unknown = TimeframeState(5, TICK, atr_period=3)
    ok, info = unknown.is_displacement(bar(t, *CANDIDATE, tf=5), "LONG", 1.0, 0.25)
    assert not ok and info["status"] == "UNKNOWN"


# ---------------------------------------------------------------- sweep / CISD primitives
def test_sweep_needs_one_tick_excursion_and_close_back_through():
    t = T0
    assert sweep(bar(t, 100, 101, 98.75, 99.5), 99.0, "SELL_SIDE", TICK, 1) is True
    assert sweep(bar(t, 100, 101, 99.0, 99.5), 99.0, "SELL_SIDE", TICK, 1) is False     # touch only
    assert sweep(bar(t, 100, 101, 98.5, 98.75), 99.0, "SELL_SIDE", TICK, 1) is False    # closed below
    assert sweep(bar(t, 100, 101.25, 99, 100.5), 101.0, "BUY_SIDE", TICK, 1) is True


def test_cisd_level_ignores_candles_closing_after_the_reference_time():
    bars = bars_tf(T0, 1, [(10, 10.5, 9, 9.5), (9.5, 10, 9.25, 9.75), (9.75, 9.75, 9, 9.25)])
    assert cisd_level(bars, "LONG", bars[1].end) == (10, bars[0].start)
    assert cisd_level(bars, "LONG", bars[2].end) == (9.75, bars[2].start)
