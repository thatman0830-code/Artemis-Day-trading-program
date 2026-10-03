"""Premarked liquidity levels (master spec page 7) built only from completed data.

Level families: prior completed trading-day high/low; completed Asia
(19:00-00:00 ET) and London (02:00-05:00 ET) window high/low; confirmed H1/H4
swing highs/lows; unfilled H1/H4 fair-value-gap boundaries. A level is
"consumed" once price trades at least one tick through it after it became
known. Setups freeze a snapshot of the book at creation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta

from mes_pilot.bars import Bar, ET, session_date_for
from mes_pilot.structure import Gap, Swing


@dataclass
class Level:
    level_id: str
    kind: str
    side: str            # BUY_SIDE (above: highs) | SELL_SIDE (below: lows)
    price: float
    known_at: datetime
    consumed_at: datetime | None = None

    def snapshot(self) -> dict:
        d = asdict(self)
        d["known_at"] = self.known_at.isoformat()
        d["consumed_at"] = self.consumed_at.isoformat() if self.consumed_at else None
        return d


def _in_window(local_t: time, start: time, end: time) -> bool:
    if start < end:
        return start <= local_t < end
    return local_t >= start or local_t < end  # wraps midnight (end 00:00)


class LiquidityBook:
    def __init__(self, tick: float, asia: tuple[time, time], london: tuple[time, time],
                 equal_tolerance_ticks: int = 2, swing_max_age_days: int = 10):
        self.tick = tick
        self.asia = asia
        self.london = london
        self.tolerance = equal_tolerance_ticks * tick
        self.swing_max_age = timedelta(days=swing_max_age_days)
        self.levels: dict[str, Level] = {}
        self._day: date | None = None
        self._day_hl: list[float] | None = None
        self._asia_hl: list[float] | None = None
        self._london_hl: list[float] | None = None
        self._asia_done = False
        self._london_done = False

    # ------------------------------------------------------------------
    def _add(self, level: Level):
        self.levels.setdefault(level.level_id, level)

    def on_m1(self, bar: Bar):
        """Update session ranges, finalize completed windows, mark consumption."""
        day = session_date_for(bar.start)
        if self._day is not None and day != self._day:
            self._finalize_day(bar.start)
        if self._day != day:
            self._day = day
            self._day_hl = None
            self._asia_hl = None
            self._london_hl = None
            self._asia_done = False
            self._london_done = False
            for lid in [k for k, v in self.levels.items() if v.kind.startswith(("ASIA", "LONDON"))]:
                del self.levels[lid]

        local_t = bar.start.astimezone(ET).time()
        in_asia = _in_window(local_t, *self.asia)
        in_london = _in_window(local_t, *self.london)
        # A window is complete when the first bar outside it starts: publish it
        # BEFORE marking consumption so this very bar can consume it.
        if not in_asia and self._asia_hl is not None and not self._asia_done:
            self._close_window("ASIA", self._asia_hl, bar.start)
            self._asia_done = True
        if not in_london and self._london_hl is not None and not self._london_done:
            self._close_window("LONDON", self._london_hl, bar.start)
            self._london_done = True

        # Consumption: only levels known at/before this bar started.
        for lv in self.levels.values():
            if lv.consumed_at is None and lv.known_at <= bar.start:
                if lv.side == "BUY_SIDE" and bar.high >= lv.price + self.tick - 1e-9:
                    lv.consumed_at = bar.end
                elif lv.side == "SELL_SIDE" and bar.low <= lv.price - self.tick + 1e-9:
                    lv.consumed_at = bar.end

        self._day_hl = self._extend(self._day_hl, bar)
        if in_asia and not self._asia_done:
            self._asia_hl = self._extend(self._asia_hl, bar)
        if in_london and not self._london_done:
            self._london_hl = self._extend(self._london_hl, bar)

        # Expire old swing / gap levels.
        for lid in [k for k, v in self.levels.items()
                    if v.kind.startswith(("H1_", "H4_")) and bar.end - v.known_at > self.swing_max_age]:
            del self.levels[lid]

    @staticmethod
    def _extend(hl, bar):
        if hl is None:
            return [bar.high, bar.low]
        return [max(hl[0], bar.high), min(hl[1], bar.low)]

    def _close_window(self, name: str, hl: list[float], known_at: datetime):
        self._add(Level(f"{name}_H:{self._day}", f"{name}_HIGH", "BUY_SIDE", hl[0], known_at))
        self._add(Level(f"{name}_L:{self._day}", f"{name}_LOW", "SELL_SIDE", hl[1], known_at))

    def _finalize_day(self, known_at: datetime):
        for lid in [k for k, v in self.levels.items() if v.kind in ("PDH", "PDL")]:
            del self.levels[lid]
        if self._day_hl is not None:
            self._add(Level(f"PDH:{self._day}", "PDH", "BUY_SIDE", self._day_hl[0], known_at))
            self._add(Level(f"PDL:{self._day}", "PDL", "SELL_SIDE", self._day_hl[1], known_at))

    def add_swing(self, swing: Swing):
        tag = "H4" if swing.tf == 240 else "H1"
        side = "BUY_SIDE" if swing.kind == "HIGH" else "SELL_SIDE"
        self._add(Level(f"{tag}_SWING_{swing.kind}:{swing.bar_start.isoformat()}", f"{tag}_SWING_{swing.kind}",
                        side, swing.price, swing.confirmed_at))

    def add_gap(self, gap: Gap):
        tag = "H4" if gap.tf == 240 else "H1"
        # A bearish gap above price draws buy-side delivery to its lower bound;
        # a bullish gap below draws sell-side delivery to its upper bound.
        if gap.direction == "BEAR":
            self._add(Level(f"{tag}_FVG_BEAR:{gap.created_at.isoformat()}", f"{tag}_FVG_BEAR", "BUY_SIDE", gap.low, gap.created_at))
        else:
            self._add(Level(f"{tag}_FVG_BULL:{gap.created_at.isoformat()}", f"{tag}_FVG_BULL", "SELL_SIDE", gap.high, gap.created_at))

    def reset(self):
        self.__init__(self.tick, self.asia, self.london, int(round(self.tolerance / self.tick)), self.swing_max_age.days)

    # ------------------------------------------------------------------
    def active(self, as_of: datetime, side: str | None = None) -> list[Level]:
        """Levels known at ``as_of`` and not consumed by a bar that ended at/before it.

        As-of semantics matter for sweeps: by the time an M5 bar is evaluated its
        M1 bars have already consumed the level it swept, but the level was
        still unconsumed when that M5 bar started.
        """
        return [lv for lv in self.levels.values()
                if lv.known_at <= as_of and (lv.consumed_at is None or lv.consumed_at > as_of)
                and (side is None or lv.side == side)]

    def cluster_count(self, level: Level, as_of: datetime) -> int:
        return sum(1 for other in self.active(as_of, level.side)
                   if other.level_id != level.level_id and abs(other.price - level.price) <= self.tolerance + 1e-9)

    def nearest_target(self, direction: str, entry: float, as_of: datetime) -> Level | None:
        """Nearest level beyond ``entry``; never a level already consumed (as of now, not ``as_of``)."""
        if direction == "LONG":
            above = [lv for lv in self.active(as_of, "BUY_SIDE")
                     if lv.consumed_at is None and lv.price >= entry + self.tick - 1e-9]
            return min(above, key=lambda lv: (lv.price, lv.level_id)) if above else None
        below = [lv for lv in self.active(as_of, "SELL_SIDE")
                 if lv.consumed_at is None and lv.price <= entry - self.tick + 1e-9]
        return max(below, key=lambda lv: (lv.price, lv.level_id)) if below else None

    def snapshot(self, as_of: datetime) -> list[dict]:
        return [lv.snapshot() for lv in sorted(self.active(as_of), key=lambda x: (x.price, x.level_id))]
