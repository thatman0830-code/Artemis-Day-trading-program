"""In-process MES paper simulator (master spec page 11 fill policy).

- Market entries fill at the ask (long) / bid (short) of the first executable
  quote AFTER the confirming bar closed; never at the already-known close.
- Protective stop (stop-market) and target (limit) are attached as an OCO.
  A target fills only if price trades at least one tick through it.
- Stop exits gap through: fill at the worse of stop and bar open, minus
  configured stop slippage ticks.
- A bar touching both stop and target resolves stop-first (conservative) and
  is flagged AMBIGUOUS_BAR_STOP_FIRST.
- Fault injection (tests): partial entry fill, protection rejection, delayed
  fill. Rejected protection -> EMERGENCY: flatten through the simulator and
  block new entries until reconciliation is cleared.
No network access, broker client or credentials exist in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import uuid

from mes_pilot.bars import Bar
from mes_pilot.config import PilotConfig


@dataclass(frozen=True)
class Quote:
    ts: datetime
    bid: float
    ask: float
    source: str           # MODELED_FROM_BAR_OPEN | LIVE_MBP1 | SYNTHETIC
    receive_ts: datetime | None = None

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass(frozen=True)
class Intent:
    intent_id: str
    signal_id: str
    setup_id: str
    side: str
    quantity: int
    entry_ref: float
    stop: float
    target: float
    created_at: datetime
    expires_at: datetime
    max_drift_ticks: int
    worst_case_loss: float


@dataclass
class Position:
    position_id: str
    intent_id: str
    signal_id: str
    setup_id: str
    side: str
    quantity: int
    entry_price: float
    entry_time: datetime
    stop: float
    target: float
    initial_risk_usd: float
    entry_fees: float
    protection_status: str = "ACTIVE"
    is_open: bool = True
    exit_price: float | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None
    exit_fees: float = 0.0
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    mae_ticks: float = 0.0
    mfe_ticks: float = 0.0
    flags: list = field(default_factory=list)


@dataclass
class SubmitResult:
    status: str          # FILLED | PARTIAL_FILLED | REJECTED | CANCELLED | DUPLICATE | EMERGENCY_FLATTENED
    reason: str | None
    order_id: str | None = None
    fill_id: str | None = None
    position: Position | None = None


class PaperSimulator:
    def __init__(self, cfg: PilotConfig, state_path: Path | None = None, *, faults: dict | None = None):
        self.cfg = cfg
        self.tick = cfg.instrument.tick_size
        self.state_path = Path(state_path) if state_path else None
        self.faults = dict(faults or {})
        self.orders: dict[str, dict] = {}        # intent_id -> order record (terminal status persists)
        self.positions: dict[str, Position] = {}
        self.emergency: str | None = None
        if self.state_path and self.state_path.exists():
            self._load()

    # ------------------------------------------------------------------ persistence
    def _load(self):
        doc = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.orders = doc["orders"]
        self.emergency = doc.get("emergency")
        for pid, p in doc["positions"].items():
            p["entry_time"] = datetime.fromisoformat(p["entry_time"])
            if p.get("exit_time"):
                p["exit_time"] = datetime.fromisoformat(p["exit_time"])
            self.positions[pid] = Position(**p)

    def save(self):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        doc = {"orders": self.orders, "emergency": self.emergency,
               "positions": {k: asdict(v) for k, v in self.positions.items()}}
        tmp = self.state_path.with_name(f".{self.state_path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(doc, default=lambda o: o.isoformat(), indent=1), encoding="utf-8")
        os.replace(tmp, self.state_path)

    # ------------------------------------------------------------------ helpers
    def _fee(self, qty: int) -> float:
        return round(self.cfg.costs.commission_per_side * qty, 2)

    def _pnl(self, side: str, entry: float, exit_: float, qty: int) -> float:
        points = (exit_ - entry) if side == "LONG" else (entry - exit_)
        return round(points * self.cfg.instrument.point_value * qty, 2)

    def open_positions(self) -> list[Position]:
        return [p for p in self.positions.values() if p.is_open]

    @staticmethod
    def order_id_for(intent_id: str) -> str:
        return "ORD-" + intent_id

    # ------------------------------------------------------------------ entry
    def submit(self, intent: Intent, quote: Quote) -> SubmitResult:
        order_id = self.order_id_for(intent.intent_id)
        if intent.intent_id in self.orders:
            prior = self.orders[intent.intent_id]
            return SubmitResult("DUPLICATE", f"intent already {prior['status']}", order_id)
        if self.emergency:
            return self._terminal(intent, "REJECTED", f"EMERGENCY_STATE:{self.emergency}")
        if intent.quantity < 1:
            return self._terminal(intent, "REJECTED", "INVALID_QUANTITY")
        if self.open_positions():
            return self._terminal(intent, "REJECTED", "POSITION_ALREADY_OPEN")
        if quote.ts > intent.expires_at:
            return self._terminal(intent, "CANCELLED", "INTENT_EXPIRED_BEFORE_EXECUTABLE_QUOTE")
        if quote.ts < intent.created_at:
            return self._terminal(intent, "REJECTED", "QUOTE_PRECEDES_DECISION")
        if quote.bid <= 0 or quote.ask < quote.bid:
            return self._terminal(intent, "REJECTED", "INVALID_OR_CROSSED_QUOTE")
        price = quote.ask if intent.side == "LONG" else quote.bid
        drift = (price - intent.entry_ref) / self.tick if intent.side == "LONG" else (intent.entry_ref - price) / self.tick
        if drift > intent.max_drift_ticks + 1e-9:
            return self._terminal(intent, "CANCELLED", f"PRICE_DRIFT_{drift:.0f}_TICKS")
        if (intent.side == "LONG" and price <= intent.stop) or (intent.side == "SHORT" and price >= intent.stop):
            return self._terminal(intent, "CANCELLED", "EXECUTABLE_PRICE_BEYOND_STOP")
        if (intent.side == "LONG" and price >= intent.target) or (intent.side == "SHORT" and price <= intent.target):
            return self._terminal(intent, "CANCELLED", "TARGET_ALREADY_REACHED")

        qty = intent.quantity
        status = "FILLED"
        if self.faults.get("partial_fill_qty") is not None:
            # A partial fill can never exceed the requested quantity.
            qty = min(int(self.faults.pop("partial_fill_qty")), intent.quantity)
            status = "PARTIAL_FILLED" if qty < intent.quantity else "FILLED"
            if qty <= 0:
                return self._terminal(intent, "CANCELLED", "ZERO_FILL")
        fill_id = "FILL-" + intent.intent_id
        stop_ticks = abs(price - intent.stop) / self.tick
        initial_risk = round(stop_ticks * self.cfg.instrument.tick_value * qty, 2)
        pos = Position("POS-" + intent.intent_id, intent.intent_id, intent.signal_id, intent.setup_id, intent.side,
                       qty, price, quote.ts, intent.stop, intent.target, initial_risk, self._fee(qty))
        self.positions[pos.position_id] = pos
        self.orders[intent.intent_id] = {"order_id": order_id, "status": status, "fill_id": fill_id,
                                         "requested_qty": intent.quantity, "filled_qty": qty,
                                         "fill_price": price, "fill_time": quote.ts.isoformat(),
                                         "quote_source": quote.source}
        # Protection must cover the filled quantity.
        if self.faults.pop("reject_protection", False):
            pos.protection_status = "REJECTED"
            self.emergency = "PROTECTION_REJECTED"
            self.close(pos.position_id, quote, "EMERGENCY_PROTECTION_REJECTED")
            self.save()
            return SubmitResult("EMERGENCY_FLATTENED", "PROTECTION_REJECTED", order_id, fill_id, pos)
        self.save()
        return SubmitResult(status, None, order_id, fill_id, pos)

    def _terminal(self, intent: Intent, status: str, reason: str) -> SubmitResult:
        self.orders[intent.intent_id] = {"order_id": self.order_id_for(intent.intent_id), "status": status,
                                         "reason": reason, "filled_qty": 0}
        self.save()
        return SubmitResult(status, reason, self.order_id_for(intent.intent_id))

    def cancel(self, intent_id: str, reason: str) -> bool:
        """Cancel a not-yet-submitted intent so any later (late) fill attempt is refused."""
        if intent_id in self.orders:
            return False
        self.orders[intent_id] = {"order_id": self.order_id_for(intent_id), "status": "CANCELLED",
                                  "reason": reason, "filled_qty": 0}
        self.save()
        return True

    # ------------------------------------------------------------------ management
    def on_bar(self, bar: Bar) -> list[Position]:
        """Apply protective exits for every open position using a completed M1 bar."""
        closed = []
        for pos in self.open_positions():
            if bar.end <= pos.entry_time:
                continue
            self._track_excursion(pos, bar)
            slip = self.cfg.costs.stop_slippage_ticks * self.tick
            if pos.side == "LONG":
                stop_hit = bar.low <= pos.stop
                target_hit = bar.high >= pos.target + self.tick - 1e-9
                stop_fill = min(pos.stop, bar.open) - slip
            else:
                stop_hit = bar.high >= pos.stop
                target_hit = bar.low <= pos.target - self.tick + 1e-9
                stop_fill = max(pos.stop, bar.open) + slip
            if stop_hit:
                if target_hit:
                    pos.flags.append("AMBIGUOUS_BAR_STOP_FIRST")
                self._finalize(pos, stop_fill, bar.end, "STOP")
                closed.append(pos)
            elif target_hit:
                self._finalize(pos, pos.target, bar.end, "TARGET")
                closed.append(pos)
        if closed:
            self.save()
        return closed

    def on_quote(self, quote: Quote) -> list[Position]:
        """Apply protective paper exits on the live quote stream between bars.

        The bid/ask is the executable liquidation side. A target needs the
        executable side at least one tick through its limit; stop markets pay
        the configured adverse slippage from the worse of stop and quote.
        """
        closed = []
        slip = self.cfg.costs.stop_slippage_ticks * self.tick
        for pos in self.open_positions():
            if quote.ts <= pos.entry_time:
                continue
            if pos.side == "LONG":
                stop_hit = quote.bid <= pos.stop
                target_hit = quote.bid >= pos.target + self.tick - 1e-9
                fill = min(pos.stop, quote.bid) - slip if stop_hit else pos.target
            else:
                stop_hit = quote.ask >= pos.stop
                target_hit = quote.ask <= pos.target - self.tick + 1e-9
                fill = max(pos.stop, quote.ask) + slip if stop_hit else pos.target
            if stop_hit or target_hit:
                self._finalize(pos, fill, quote.ts, "STOP" if stop_hit else "TARGET")
                closed.append(pos)
        if closed:
            self.save()
        return closed

    def _track_excursion(self, pos: Position, bar: Bar):
        if pos.side == "LONG":
            adverse, favorable = pos.entry_price - bar.low, bar.high - pos.entry_price
        else:
            adverse, favorable = bar.high - pos.entry_price, pos.entry_price - bar.low
        pos.mae_ticks = max(pos.mae_ticks, adverse / self.tick)
        pos.mfe_ticks = max(pos.mfe_ticks, favorable / self.tick)

    def close(self, position_id: str, quote: Quote, reason: str) -> Position | None:
        pos = self.positions.get(position_id)
        if pos is None or not pos.is_open:
            return None
        price = quote.bid if pos.side == "LONG" else quote.ask
        self._finalize(pos, price, quote.ts, reason)
        self.save()
        return pos

    def _finalize(self, pos: Position, price: float, when: datetime, reason: str):
        pos.exit_price = price
        pos.exit_time = when
        pos.exit_reason = reason
        pos.exit_fees = self._fee(pos.quantity)
        pos.gross_pnl = self._pnl(pos.side, pos.entry_price, price, pos.quantity)
        pos.net_pnl = round(pos.gross_pnl - pos.entry_fees - pos.exit_fees, 2)
        pos.is_open = False

    def clear_emergency(self) -> str | None:
        was, self.emergency = self.emergency, None
        self.save()
        return was


def modeled_quote(bar: Bar, tick: float, spread_ticks: int) -> Quote:
    """Bar-only feeds have no bid/ask: model a quote at the bar open (labeled MODELED).

    ``spread_ticks`` adverse ticks on each side of the open, so a buyer pays
    open + n ticks and a seller receives open - n ticks.
    """
    edge = spread_ticks * tick
    return Quote(bar.start, bar.open - edge, bar.open + edge, "MODELED_FROM_BAR_OPEN")
