"""REVERSAL_R1 and CONTINUATION_C1 setup state machines (master spec pages 7-8).

Pilot interpretations (proposed paper defaults, NOT source-engine settings):

REVERSAL_R1 (long shown; short mirrors)
  1. H4 and H1 bias both BULLISH.
  2. A completed M5 bar sweeps a premarked SELL_SIDE level known before the bar
     started: low <= level - 1 tick and close > level.          -> OBSERVING
  3. Within 6 M5 bars (sweep bar included) a bullish M5 displacement candle
     (body >= 1.0 x prior ATR(14), close in top 25%) that either closes >= 1 tick
     above the latest confirmed M5 swing high (BOS) or closes above the top of
     an active bearish M5/M15 gap (inverse FVG).                -> ARMED
     Retest zone = [equilibrium of sweep-extreme -> displacement high, broken level].
     Stop = sweep extreme - 1 tick. Target = nearest unconsumed BUY_SIDE level
     above the broken level, frozen now.
  4. A completed bullish M1 bar trades into the zone without breaching the stop
     and closes back above the zone low.                        -> CONFIRMED
  Price at/below stop, target consumed, bias flip or 15 min elapsed -> terminal.

CONTINUATION_C1 (long shown)
  1. H4/H1 bias BULLISH; M5 efficiency ratio(20) >= 0.35.
  2. A completed M5 bullish FVG whose middle bar is a bullish displacement
     candle; an unconsumed BUY_SIDE target exists above it (frozen).  -> ARMED
  3. M1 pullback trades into the gap (low <= gap high) while no M1 closes
     below the gap low (gap respect).
  4. CISD: a bullish M1 bar closes above the open of the most recent bearish M1
     candle formed during the pullback.                         -> CONFIRMED
     Stop = lowest low of the pullback - 1 tick (wick respecting the gap).
  No reversal-style sweep is required for C1.

Setups are created only from bars that start at/after the session entry-window
open, so no premarket structure arms an entry.

Causality rules enforced here (regression-tested in tests/test_setups.py):
- An M1 bar that started before a setup was ARMED (e.g. the last M1 bar of the
  arming M5 candle) never confirms it or counts as its pullback touch.
- One REVERSAL_R1 setup per sweep bar and direction; every level that bar
  swept is recorded, the most extreme one is the reference level.
- Only OBSERVING/ARMED setups are updated; once the engine takes over a
  CONFIRMED setup (RISK_APPROVED, ENTRY_PENDING, ...) the detector leaves it alone.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
import json

from mes_pilot.bars import ET, Bar
from mes_pilot.structure import TimeframeState, aligned_bias, cisd_level, ote_zone, sweep

TERMINAL = {"EXPIRED", "INVALIDATED", "REJECTED", "CANCELLED", "CLOSED"}
LIVE_STATES = {"OBSERVING", "ARMED"}
# Tie-break among equally priced swept levels (lower = more significant).
_KIND_PRIORITY = (("PDL", "PDH"), ("LONDON_",), ("ASIA_",), ("H4_",), ("H1_",))


def _kind_rank(kind: str) -> int:
    for rank, prefixes in enumerate(_KIND_PRIORITY):
        if kind.startswith(prefixes):
            return rank
    return len(_KIND_PRIORITY)


@dataclass
class Setup:
    setup_id: str
    family: str
    direction: str
    created_at: datetime
    expires_at: datetime
    state: str = "OBSERVING"
    transitions: list = field(default_factory=list)
    confirmations: dict = field(default_factory=dict)
    refs: dict = field(default_factory=dict)
    frozen_levels: list = field(default_factory=list)
    target_level_id: str | None = None
    target: float | None = None
    stop: float | None = None
    zone: tuple[float, float] | None = None
    confirmed_at: datetime | None = None
    armed_at: datetime | None = None
    entry_ref: float | None = None
    reason: str | None = None

    def move(self, state: str, at: datetime, reason: str, data_ts: datetime | None = None):
        self.state = state
        self.reason = reason
        self.transitions.append({"state": state, "at_utc": at.isoformat(), "reason": reason,
                                 "market_data_ts": (data_ts or at).isoformat()})

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL


def _sid(*parts) -> str:
    return sha256(json.dumps(parts, default=str).encode()).hexdigest()[:24]


class SetupDetector:
    def __init__(self, cfg, tfs: dict[int, TimeframeState], book):
        self.cfg = cfg
        self.s = cfg.strategy
        self.tick = cfg.instrument.tick_size
        self.tfs = tfs
        self.book = book
        self.setups: dict[str, Setup] = {}
        self.events: list[dict] = []   # rejections/skips for the ledger
        # Pure diagnostics (never read by any decision): per-completed-M5 funnel counts.
        self.counters: Counter = Counter()

    def reset_counters(self):
        """Clear the diagnostic funnel counters (e.g. at a session boundary)."""
        self.counters = Counter()

    # ------------------------------------------------------------------ helpers
    def _bias(self) -> str:
        return aligned_bias(self.tfs[240], self.tfs[60])

    def _expiry(self, at: datetime) -> datetime:
        return at + timedelta(minutes=self.s.setup_expiry_min)

    def _reject(self, family, direction, at, reason, **data):
        self.events.append({"family": family, "direction": direction, "at": at, "reason": reason, **data})

    def active(self) -> list[Setup]:
        return [x for x in self.setups.values() if x.state in LIVE_STATES]

    # ------------------------------------------------------------------ M5 events
    def on_m5(self, bar: Bar, window_open: bool):
        bias = self._bias()
        m5 = self.tfs[5]
        c = self.counters
        c["m5_bars"] += 1
        if window_open:
            # Funnel counts are scoped to entry-window M5 bars (where setups can be created):
            # bias_aligned_long + bias_aligned_short + bias_neutral == m5_window_bars.
            c["m5_window_bars"] += 1
            c["bias_aligned_long" if bias == "BULLISH" else "bias_aligned_short" if bias == "BEARISH"
              else "bias_neutral"] += 1
            c["m5_gaps_formed"] += sum(1 for g in m5.gaps if g.created_at == bar.end and g.tf == m5.tf)
        for st in self.active():
            self._m5_update(st, bar, bias)
        if not window_open:
            return
        if bias not in ("BULLISH", "BEARISH"):
            return
        direction = "LONG" if bias == "BULLISH" else "SHORT"
        self._r1_detect_sweep(bar, direction)
        self._c1_detect(bar, direction, m5)

    def _r1_detect_sweep(self, bar: Bar, direction: str):
        side = "SELL_SIDE" if direction == "LONG" else "BUY_SIDE"
        # Levels known and unconsumed when the sweep bar STARTED (its own M1 bars consume them).
        swept = [lv for lv in self.book.active(bar.start, side)
                 if sweep(bar, lv.price, side, self.tick, self.s.sweep_min_ticks)]
        if not swept:
            return
        self.counters["sweeps_detected"] += 1
        # One setup per sweep bar: several levels swept by one candle share the same
        # extreme, stop, zone and target, so separate setups would only duplicate (and
        # then conflict-reject) each other. Primary = deepest swept level (long: lowest
        # sell-side price; short: highest buy-side price); ties by kind priority, then id.
        sign = 1 if direction == "LONG" else -1
        lv = min(swept, key=lambda x: (sign * x.price, _kind_rank(x.kind), x.level_id))
        sid = _sid("REVERSAL_R1", direction, bar.start)
        if sid in self.setups:
            return
        # Sweep bar + 5 more M5 bars may supply the displacement/structure break.
        st = Setup(sid, "REVERSAL_R1", direction, bar.end, bar.end + timedelta(minutes=25))
        st.frozen_levels = self.book.snapshot(bar.start)
        st.refs = {"swept_level_id": lv.level_id, "swept_level_kind": lv.kind, "swept_price": lv.price,
                   "swept_level_ids": sorted(x.level_id for x in swept),
                   "swept_levels": [{"level_id": x.level_id, "kind": x.kind, "price": x.price}
                                    for x in sorted(swept, key=lambda x: (sign * x.price, _kind_rank(x.kind), x.level_id))],
                   "sweep_extreme": bar.low if direction == "LONG" else bar.high,
                   "sweep_bar_start": bar.start.isoformat(), "level_cluster": self.book.cluster_count(lv, bar.start)}
        st.confirmations = {"aligned_bias": True, "sweep_rejection": True}
        st.move("OBSERVING", bar.end, "SWEEP_AND_REJECTION_M5")
        self.setups[sid] = st
        self.counters["setups_created_REVERSAL_R1"] += 1
        self._r1_try_arm(st, bar)   # the sweep bar itself may displace

    def _r1_try_arm(self, st: Setup, bar: Bar):
        m5, m15 = self.tfs[5], self.tfs[15]
        ok_disp, info = m5.is_displacement(bar, st.direction, self.s.displacement_body_atr, self.s.displacement_close_outer)
        st.confirmations["displacement"] = ok_disp
        st.refs["displacement_info"] = info      # original key, kept for compatibility
        st.refs["displacement"] = info           # same detail under the shared diagnostics key
        if not ok_disp:
            return
        broken = None
        how = None
        if st.direction == "LONG":
            sw = m5.latest_swing("HIGH", bar.start, before_bar_start=bar.start)
            if sw and bar.close >= sw.price + self.s.bos_min_ticks * self.tick - 1e-9:
                broken, how = sw.price, "BOS"
            else:
                for g in m5.active_gaps("BEAR", bar.start) + m15.active_gaps("BEAR", bar.start):
                    if bar.close > g.high:
                        broken, how = g.high, f"IFVG_M{g.tf}"
                        break
        else:
            sw = m5.latest_swing("LOW", bar.start, before_bar_start=bar.start)
            if sw and bar.close <= sw.price - self.s.bos_min_ticks * self.tick + 1e-9:
                broken, how = sw.price, "BOS"
            else:
                for g in m5.active_gaps("BULL", bar.start) + m15.active_gaps("BULL", bar.start):
                    if bar.close < g.low:
                        broken, how = g.low, f"IFVG_M{g.tf}"
                        break
        st.confirmations["structure_break"] = broken is not None
        if broken is None:
            return
        extreme = st.refs["sweep_extreme"]
        leg_end = bar.high if st.direction == "LONG" else bar.low
        eq = (extreme + leg_end) / 2
        zone = (min(eq, broken), max(eq, broken))
        st.zone = zone
        st.stop = (extreme - self.s.stop_buffer_ticks * self.tick) if st.direction == "LONG" \
            else (extreme + self.s.stop_buffer_ticks * self.tick)
        st.refs.update({"structure": how, "broken_level": broken, "displacement_bar_start": bar.start.isoformat(),
                        "equilibrium": eq})
        target = self.book.nearest_target(st.direction, broken, bar.end)
        if target is None:
            st.move("REJECTED", bar.end, "NO_UNCONSUMED_TARGET")
            return
        st.target_level_id, st.target = target.level_id, target.price
        st.refs["target_kind"] = target.kind
        st.expires_at = self._expiry(bar.end)
        st.armed_at = bar.end
        st.move("ARMED", bar.end, f"M5_DISPLACEMENT_{how}")

    def _c1_detect(self, bar: Bar, direction: str, m5: TimeframeState):
        want = "BULL" if direction == "LONG" else "BEAR"
        new = [g for g in m5.gaps if g.created_at == bar.end and g.direction == want]
        if not new:
            return
        gap = new[0]
        sid = _sid("CONTINUATION_C1", direction, gap.created_at)
        if sid in self.setups:
            return
        bars = list(m5.bars)
        a, b = bars[-3], bars[-2]
        er = m5.efficiency_ratio()
        # Displacement of the middle bar B uses the ATR completed before B.
        before_b = TimeframeState(5, self.tick, atr_period=self.s.atr_period)
        before_b.bars.extend(bars[:-2])
        prior_atr = before_b.atr()
        ok_disp, disp_info = before_b.is_displacement(b, direction, self.s.displacement_body_atr,
                                                      self.s.displacement_close_outer)
        st = Setup(sid, "CONTINUATION_C1", direction, bar.end, self._expiry(bar.end))
        st.frozen_levels = self.book.snapshot(bar.end)
        st.refs = {"gap_low": gap.low, "gap_high": gap.high, "gap_created_at": gap.created_at.isoformat(),
                   "middle_bar_start": b.start.isoformat(), "efficiency_ratio": er, "prior_atr": prior_atr,
                   "impulse_start": a.low if direction == "LONG" else a.high,
                   "impulse_end": bar.high if direction == "LONG" else bar.low,
                   "displacement": disp_info}
        st.confirmations = {"aligned_bias": True, "displacement_fvg": bool(ok_disp),
                            "efficiency_ok": er is not None and er >= self.s.continuation_min_er}
        self.setups[sid] = st
        self.counters["setups_created_CONTINUATION_C1"] += 1
        # Pilot policy (coordinator decision): the displacement candle itself must start
        # inside the entry window, so no premarket structure arms a continuation.
        if b.start.astimezone(ET).time() < self.cfg.session.entry_start:
            st.move("REJECTED", bar.end, "C1_DISPLACEMENT_BEFORE_ENTRY_WINDOW")
            return
        if not ok_disp:
            st.move("REJECTED", bar.end, "C1_NO_DISPLACEMENT_FVG")
            return
        if er is None:
            st.move("REJECTED", bar.end, "C1_EFFICIENCY_UNKNOWN")
            return
        if er < self.s.continuation_min_er:
            st.move("REJECTED", bar.end, "C1_EFFICIENCY_BELOW_MIN")
            return
        target = self.book.nearest_target(direction, bar.close, bar.end)
        if target is None:
            st.move("REJECTED", bar.end, "NO_UNCONSUMED_TARGET")
            return
        st.target_level_id, st.target = target.level_id, target.price
        st.refs["target_kind"] = target.kind
        st.zone = (gap.low, gap.high)
        st.refs["touched"] = False
        st.refs["pullback_extreme"] = None
        st.armed_at = bar.end
        st.move("ARMED", bar.end, "M5_DISPLACEMENT_FVG")

    def _m5_update(self, st: Setup, bar: Bar, bias: str):
        want = "BULLISH" if st.direction == "LONG" else "BEARISH"
        if bias != want:
            st.move("INVALIDATED", bar.end, "BIAS_NO_LONGER_ALIGNED")
            return
        if st.family == "REVERSAL_R1" and st.state == "OBSERVING":
            if bar.end > st.expires_at:
                st.move("EXPIRED", bar.end, "NO_DISPLACEMENT_WITHIN_6_M5_BARS")
                return
            beyond = bar.low < st.refs["sweep_extreme"] if st.direction == "LONG" else bar.high > st.refs["sweep_extreme"]
            if beyond and bar.start.isoformat() != st.refs["sweep_bar_start"]:
                st.move("INVALIDATED", bar.end, "SWEEP_EXTREME_EXCEEDED")
                return
            if bar.start.isoformat() != st.refs["sweep_bar_start"]:
                self._r1_try_arm(st, bar)

    # ------------------------------------------------------------------ M1 events
    def on_m1(self, bar: Bar) -> list[Setup]:
        """Update ARMED setups with a completed M1 bar; return those CONFIRMED by it."""
        confirmed = []
        for st in self.active():
            if st.state != "ARMED":
                continue
            if st.armed_at is not None and bar.start < st.armed_at:
                continue  # bar (partly) precedes the arming close: not evidence after arming
            if bar.end > st.expires_at:
                st.move("EXPIRED", bar.end, "SETUP_LIFETIME_ELAPSED")
                continue
            lv = self.book.levels.get(st.target_level_id)
            if lv is None:
                st.move("INVALIDATED", bar.end, "TARGET_LEVEL_NO_LONGER_TRACKED")
                continue
            if lv.consumed_at is not None:
                st.move("INVALIDATED", bar.end, "TARGET_CONSUMED_BEFORE_ENTRY")
                continue
            if st.family == "REVERSAL_R1":
                self._r1_m1(st, bar, confirmed)
            else:
                self._c1_m1(st, bar, confirmed)
        for st in confirmed:
            self.counters[f"setups_confirmed_{st.family}"] += 1
        return confirmed

    def _r1_m1(self, st: Setup, bar: Bar, confirmed: list):
        lo, hi = st.zone
        if st.direction == "LONG":
            if bar.low <= st.stop:
                st.move("INVALIDATED", bar.end, "STOP_LEVEL_TRADED_BEFORE_ENTRY")
                return
            if bar.low <= hi and bar.bullish and bar.close >= lo:
                st.confirmations["m1_retest"] = True
                st.confirmed_at = bar.end
                st.move("CONFIRMED", bar.end, "M1_RETEST_CONFIRMED")
                confirmed.append(st)
        else:
            if bar.high >= st.stop:
                st.move("INVALIDATED", bar.end, "STOP_LEVEL_TRADED_BEFORE_ENTRY")
                return
            if bar.high >= lo and bar.bearish and bar.close <= hi:
                st.confirmations["m1_retest"] = True
                st.confirmed_at = bar.end
                st.move("CONFIRMED", bar.end, "M1_RETEST_CONFIRMED")
                confirmed.append(st)

    def _c1_m1(self, st: Setup, bar: Bar, confirmed: list):
        lo, hi = st.zone
        m1 = self.tfs[1]
        if st.direction == "LONG":
            if bar.close < lo:
                st.move("INVALIDATED", bar.end, "GAP_DISRESPECTED_M1_CLOSE")
                return
            if bar.low <= hi:
                st.refs["touched"] = True
                prev = st.refs["pullback_extreme"]
                st.refs["pullback_extreme"] = bar.low if prev is None else min(prev, bar.low)
                return  # the touching bar itself cannot also be the CISD confirmation
            if st.refs["touched"]:
                lvl = cisd_level([b for b in m1.bars if b.end > st.created_at], "LONG", bar.start)
                if lvl and bar.bullish and bar.close > lvl[0]:
                    self._c1_confirm(st, bar, lvl, confirmed)
        else:
            if bar.close > hi:
                st.move("INVALIDATED", bar.end, "GAP_DISRESPECTED_M1_CLOSE")
                return
            if bar.high >= lo:
                st.refs["touched"] = True
                prev = st.refs["pullback_extreme"]
                st.refs["pullback_extreme"] = bar.high if prev is None else max(prev, bar.high)
                return
            if st.refs["touched"]:
                lvl = cisd_level([b for b in m1.bars if b.end > st.created_at], "SHORT", bar.start)
                if lvl and bar.bearish and bar.close < lvl[0]:
                    self._c1_confirm(st, bar, lvl, confirmed)

    def _c1_confirm(self, st: Setup, bar: Bar, lvl, confirmed: list):
        ext = st.refs["pullback_extreme"]
        buf = self.s.stop_buffer_ticks * self.tick
        st.stop = ext - buf if st.direction == "LONG" else ext + buf
        lo, hi = ote_zone(st.refs["impulse_start"], st.refs["impulse_end"], *self.s.ote)
        in_ote = lo <= ext <= hi
        st.refs.update({"cisd_level": lvl[0], "cisd_candle_start": lvl[1].isoformat(), "ote_zone": [lo, hi],
                        "pullback_in_ote": in_ote})
        st.confirmations.update({"gap_respect": True, "m1_cisd": True, "ote": in_ote})
        if self.s.ote_required and not in_ote:
            st.move("REJECTED", bar.end, "OTE_REQUIRED_NOT_MET")
            return
        st.confirmed_at = bar.end
        st.move("CONFIRMED", bar.end, "M1_GAP_RESPECT_CISD")
        confirmed.append(st)

    def reset(self, at: datetime | None = None):
        """Cancel live setups (kept, so the engine still logs them as terminal)."""
        for st in self.active():
            st.move("CANCELLED", at or st.created_at, "STRUCTURE_RESET")
