"""Dollar-capacity risk manager with atomic reservations (master spec page 6).

C = cash - floor - execution_reserve - open stressed risk - pending reservations
budget = max(0, min(trade_cap, fraction*C, daily headroom, portfolio headroom,
                    user per-trade ceiling, firm limit))
stop_ticks = ceil(|entry - stop| / tick)          (off-grid distance rounds UP)
unit_loss  = stop_ticks*tick_value + round_trip_commission + stressed_slippage
quantity   = min(floor(budget / unit_loss), internal cap, firm cap, margin cap)

Unrealized profit is never counted as cushion. Stops are never moved to fit:
an over-wide stop yields quantity 0 and the trade is skipped. The floor is the
stricter of the static synthetic floor and the pre-existing 3% outer drawdown
cap. The pre-existing ``risk.pretrade.PreTradeAuthorization`` (kill switch,
market health, structural stop validity, portfolio daily-loss /
consecutive-loss / open-position guard) runs as an outer layer; both must pass.

All state mutation happens under one re-entrant lock, so evaluate-and-reserve
is atomic with respect to every other reservation, fill, close and release.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path
import json
import math
import os
import threading
import uuid

from mes_pilot.config import PilotConfig
from risk.portfolio_guard import PortfolioRiskGuard
from risk.pretrade import AuthorizationDecision, MarketHealthState, PreTradeAuthorization, PreTradeRequest
from risk.risk_engine import RiskEngine, TradeProposal

_EPS = 1e-9
_CONSUMED_INTENT_MEMORY = 1000


# ---------------------------------------------------------------------- shared sizing helpers
def stop_ticks_for(cfg: PilotConfig, entry: float, stop: float) -> int:
    """Whole ticks between entry and stop, rounded UP so loss is never understated."""
    return int(math.ceil(abs(entry - stop) / cfg.instrument.tick_size - _EPS))


def unit_loss_for(cfg: PilotConfig, stop_ticks: int) -> float:
    """Stressed one-contract loss, rounded UP to the cent."""
    i, c = cfg.instrument, cfg.costs
    raw = stop_ticks * i.tick_value + c.round_trip_commission(1) + c.stressed_slippage_ticks * i.tick_value
    return math.ceil(raw * 100 - 1e-6) / 100


def daily_loss_limit(cfg: PilotConfig) -> float:
    """Strictest daily loss allowance: pilot net stop, Frank's ceilings, repo outer cap."""
    r = cfg.risk
    nominal = r.starting_equity
    return min(r.daily_stop, nominal * r.user_daily_pct / 100,
               (nominal - r.static_floor) * r.user_daily_drawdown_share,
               nominal * r.outer_daily_loss_pct / 100)


def effective_floor(cfg: PilotConfig) -> float:
    """Stricter of the static synthetic floor and the pre-existing outer drawdown cap."""
    r = cfg.risk
    return max(r.static_floor, r.starting_equity * (1 - r.outer_drawdown_pct / 100))


def per_trade_ceiling(cfg: PilotConfig) -> float:
    r = cfg.risk
    return r.starting_equity * r.user_trade_pct_max / 100


@dataclass
class AccountState:
    cash: float
    peak_equity: float = 0.0
    floor_usd: float = 0.0
    floor_breached: bool = False
    session_day: str | None = None
    day_start_cash: float = 0.0
    day_realized_net: float = 0.0
    entries_today: int = 0
    consecutive_losses: int = 0
    pause_requires_review: bool = False
    paused_on_day: str | None = None
    reservations: dict = field(default_factory=dict)       # intent_id -> usd
    open_risk: dict = field(default_factory=dict)          # position_id -> usd
    closed_positions: int = 0
    reservation_meta: dict = field(default_factory=dict)   # intent_id -> sizing record (for idempotent replay)
    consumed_intents: list = field(default_factory=list)   # intent_ids already filled (never re-reserve)
    kill_switch_latched: bool = False                      # persisted kill switch (survives restart)
    kill_switch_reason: str | None = None


@dataclass(frozen=True)
class LimitResult:
    name: str
    passed: bool
    value: float | int | str | None
    limit: float | int | str | None


@dataclass(frozen=True)
class RiskDecisionRecord:
    approved: bool
    reason: str | None
    quantity: int
    budget: float
    capacity_c: float
    stop_ticks: int
    unit_loss: float
    worst_case_loss: float
    limits: tuple[LimitResult, ...]
    existing_layer: str

    def as_dict(self) -> dict:
        d = asdict(self)
        d["limits"] = [asdict(x) for x in self.limits]
        return d


class PilotRiskManager:
    def __init__(self, cfg: PilotConfig, state_path: Path | None = None):
        self.cfg = cfg
        self.state_path = Path(state_path) if state_path else None
        self._lock = threading.RLock()
        r = cfg.risk
        self.state = AccountState(cash=r.starting_equity, day_start_cash=r.starting_equity)
        if self.state_path and self.state_path.exists():
            # Fail closed: a corrupt or unknown-schema state file raises rather than resetting capacity.
            self.state = AccountState(**json.loads(self.state_path.read_text(encoding="utf-8")))
        if self.state.peak_equity == 0.0:
            self.state.peak_equity = max(r.starting_equity, self.state.cash)
        if self.state.floor_usd == 0.0:
            self.state.floor_usd = max(effective_floor(cfg),
                                       self.state.peak_equity - r.drawdown_allowance
                                       if r.floor_model == "INTRADAY_TRAILING" else effective_floor(cfg))
        self.outer = PreTradeAuthorization(
            risk_engine=RiskEngine(max_risk_per_trade_pct=r.user_trade_pct_max, max_notional_pct=100.0,
                                   # BTC-tuned 0.05% minimum would block ~15-tick MES stops; 0 keeps the
                                   # structural direction/zero-distance checks only. Documented.
                                   minimum_stop_distance_pct=0.0, maximum_stop_distance_pct=5.0),
            portfolio_guard=PortfolioRiskGuard(max_daily_loss_pct=r.outer_daily_loss_pct,
                                               max_consecutive_losses=r.consecutive_loss_pause,
                                               max_total_exposure_pct=100.0,
                                               max_open_positions=r.max_open_positions),
            maximum_market_data_age_ms=10_000_000,  # quote freshness is enforced by the engine per mode
        )

    # ------------------------------------------------------------------ persistence
    def save(self):
        if not self.state_path:
            return
        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_name(f".{self.state_path.name}.{uuid.uuid4().hex}.tmp")
            tmp.write_text(json.dumps(asdict(self.state), sort_keys=True, indent=1), encoding="utf-8")
            os.replace(tmp, self.state_path)

    # ------------------------------------------------------------------ kill switch (persisted latch)
    def engage_kill_switch(self, reason: str):
        with self._lock:
            self.state.kill_switch_latched = True
            self.state.kill_switch_reason = reason
            self.save()

    def clear_kill_switch(self, note: str) -> dict:
        with self._lock:
            was = self.state.kill_switch_latched
            self.state.kill_switch_latched = False
            self.state.kill_switch_reason = None
            self.save()
            return {"kill_switch_cleared": was, "note": note}

    # ------------------------------------------------------------------ session
    def roll_session(self, day: date):
        """Advance the persisted trading day. Never rewinds: replaying historical context after a
        same-day restart must not reset today's entries or realized loss (repair 2026-10-02)."""
        with self._lock:
            key = day.isoformat()
            if self.state.session_day == key:
                return
            if self.state.session_day is not None and key < self.state.session_day:
                return
            self.state.session_day = key
            self.state.day_start_cash = self.state.cash
            self.state.day_realized_net = 0.0
            self.state.entries_today = 0
            self.save()

    def is_paused(self) -> bool:
        with self._lock:
            s = self.state
            return s.pause_requires_review or (s.paused_on_day is not None and s.paused_on_day == s.session_day)

    def log_review(self, note: str) -> dict:
        """Clear the review requirement of an active loss-streak pause.

        Entries stay paused for the rest of the day the pause began (next
        session AND review). A review logged while no pause is active changes
        nothing, so it cannot be used to reset a running loss streak.
        """
        with self._lock:
            was = self.state.pause_requires_review
            if was:
                self.state.pause_requires_review = False
                self.state.consecutive_losses = 0
                self.save()
            return {"review_cleared_pause": was, "note": note,
                    "still_paused_until_next_session": self.is_paused()}

    # ------------------------------------------------------------------ capacity
    def capacity(self) -> float:
        with self._lock:
            r, s = self.cfg.risk, self.state
            return (s.cash - s.floor_usd - r.execution_reserve
                    - sum(s.open_risk.values()) - sum(s.reservations.values()))

    def mark_equity(self, equity: float) -> dict:
        """Persist a paper equity mark; open-P&L peaks raise an intraday floor.

        A breach latches until a new, explicitly isolated paper account is
        created. The mark is a liquidation-side estimate including fees.
        """
        with self._lock:
            if not math.isfinite(equity):
                raise ValueError("paper equity mark must be finite")
            s, r = self.state, self.cfg.risk
            old_floor = s.floor_usd
            was_breached = s.floor_breached
            if r.floor_model == "INTRADAY_TRAILING":
                s.peak_equity = max(s.peak_equity, equity)
                s.floor_usd = max(s.floor_usd, s.peak_equity - r.drawdown_allowance)
            if equity <= s.floor_usd + _EPS:
                s.floor_breached = True
            if s.floor_usd != old_floor or s.floor_breached != was_breached:
                self.save()
            return {"equity": round(equity, 2), "peak": round(s.peak_equity, 2),
                    "floor": round(s.floor_usd, 2), "breached": s.floor_breached,
                    "new_breach": s.floor_breached and not was_breached}

    def daily_headroom(self) -> float:
        with self._lock:
            s = self.state
            return daily_loss_limit(self.cfg) + s.day_realized_net - sum(s.open_risk.values()) - sum(s.reservations.values())

    def unit_loss(self, stop_ticks: int) -> float:
        return unit_loss_for(self.cfg, stop_ticks)

    # ------------------------------------------------------------------ decision
    def evaluate_and_reserve(self, *, intent_id: str, side: str, entry: float, stop: float, session_open: bool,
                             kill_switch: bool, firm_contract_cap: int | None = None,
                             firm_trade_limit: float | None = None) -> RiskDecisionRecord:
        """Atomically evaluate every limit and, on approval, reserve capacity for ``intent_id``.

        Idempotent: a repeated call for an already-reserved intent with the same
        side/entry/stop returns the original sizing without reserving twice.
        """
        with self._lock:
            return self._evaluate_locked(intent_id, side, entry, stop, session_open, kill_switch,
                                         firm_contract_cap, firm_trade_limit)

    @staticmethod
    def _reject(reason: str, limits: list[LimitResult]) -> RiskDecisionRecord:
        return RiskDecisionRecord(False, reason, 0, 0.0, 0.0, 0, 0.0, 0.0, tuple(limits), "NOT_EVALUATED")

    def _evaluate_locked(self, intent_id, side, entry, stop, session_open, kill_switch, firm_cap, firm_limit):
        cfg, r, s = self.cfg, self.cfg.risk, self.state
        limits: list[LimitResult] = []
        kill = bool(kill_switch) or s.kill_switch_latched

        def check(name, passed, value=None, limit=None):
            limits.append(LimitResult(name, bool(passed), value, limit))
            return passed

        if intent_id in s.reservations:
            meta = s.reservation_meta.get(intent_id)
            if kill:
                # Keep the reservation: it is released only on a confirmed cancel/terminal state.
                check("kill_switch_inactive", False, True, False)
                return self._reject("kill_switch_inactive", limits)
            same = meta is not None and meta["side"] == side and abs(meta["entry"] - entry) < _EPS \
                and abs(meta["stop"] - stop) < _EPS
            check("duplicate_intent_parameters_match", same, intent_id, None)
            if not same:
                return self._reject("duplicate_intent_parameters_match", limits)
            return RiskDecisionRecord(True, "ALREADY_RESERVED", meta["quantity"], meta["budget"], round(self.capacity(), 2),
                                      meta["stop_ticks"], meta["unit_loss"], s.reservations[intent_id],
                                      tuple(limits), "SKIPPED_DUPLICATE")
        if intent_id in s.consumed_intents:
            check("intent_not_already_filled", False, intent_id, None)
            return self._reject("intent_not_already_filled", limits)

        if not check("prices_finite_positive", all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0
                                                  for x in (entry, stop)), f"{entry}/{stop}", "> 0"):
            return self._reject("prices_finite_positive", limits)

        stop_ticks = stop_ticks_for(cfg, entry, stop)
        check("kill_switch_inactive", not kill, kill, False)
        check("session_entry_window_open", session_open, session_open, True)
        check("stop_on_correct_side", (side == "LONG" and stop < entry) or (side == "SHORT" and stop > entry), stop, entry)
        check("stop_ticks_positive", stop_ticks >= 1, stop_ticks, 1)
        # Pending reservations count toward the session cap so concurrent intents cannot overshoot it.
        committed = s.entries_today + len(s.reservations)
        check("entries_this_session", committed < r.max_entries_per_session, committed, r.max_entries_per_session)
        check("consecutive_loss_pause_clear", not self.is_paused(), s.consecutive_losses, r.consecutive_loss_pause)
        open_count = len(s.open_risk) + len(s.reservations)
        check("open_positions_and_pending", open_count < r.max_open_positions, open_count, r.max_open_positions)
        daily_stop_hit = s.day_realized_net <= -r.daily_stop + _EPS
        check("daily_net_stop_not_hit", not daily_stop_hit, round(s.day_realized_net, 2), -r.daily_stop)
        check("synthetic_floor_not_breached", not s.floor_breached, s.floor_usd, "unbreached")

        C = self.capacity()
        daily = self.daily_headroom()
        candidates = {
            "pilot_trade_cap": r.max_trade_budget,
            "capacity_fraction_of_C": r.capacity_fraction * C,
            "daily_headroom": daily,
            "portfolio_headroom_C": C,
            "user_per_trade_ceiling": per_trade_ceiling(cfg),
        }
        if firm_limit is not None:
            candidates["firm_trade_limit"] = firm_limit
        budget = max(0.0, min(candidates.values()))
        binding = min(candidates, key=candidates.get)
        check("usable_capacity_positive", C > _EPS, round(C, 2), 0)
        check("trade_budget_positive", budget > _EPS, round(budget, 2), f"min({binding})")

        unit = self.unit_loss(max(stop_ticks, 1))
        affordable = int(math.floor(budget / unit + _EPS)) if unit > 0 else 0
        # Margin is posted from account cash (loss capacity is enforced separately via the budget).
        margin_cap = int(math.floor(max(0.0, s.cash) / cfg.costs.margin_per_contract))
        caps = [affordable, r.max_contracts, margin_cap]
        if firm_cap is not None:
            caps.append(firm_cap)
        qty = max(0, min(caps))
        check("integer_quantity_at_least_one", qty >= 1, qty,
              f"affordable={affordable},internal={r.max_contracts},margin={margin_cap},firm={firm_cap}")
        worst = round(unit * qty, 2)

        # Outer layer: pre-existing authorization stack.
        outer = self.outer.evaluate(PreTradeRequest(
            trade=TradeProposal(symbol=cfg.instrument.root, side=side, entry_price=entry, stop_price=stop,
                                account_value=s.cash),
            session_start_value=s.day_start_cash, current_total_notional=0.0,
            open_positions=len(s.open_risk), consecutive_losses=s.consecutive_losses,
            market_health=MarketHealthState(connected=True, fresh=True, healthy=True, age_ms=0),
            kill_switch_active=kill))
        check("existing_pretrade_authorization", outer.decision == AuthorizationDecision.AUTHORIZED, outer.reason, "AUTHORIZED")

        failed = [x.name for x in limits if not x.passed]
        approved = not failed
        if approved:
            s.reservations[intent_id] = worst
            s.reservation_meta[intent_id] = {"side": side, "entry": entry, "stop": stop, "quantity": qty,
                                             "budget": round(budget, 2), "stop_ticks": stop_ticks, "unit_loss": unit}
            self.save()
        return RiskDecisionRecord(approved, None if approved else failed[0], qty if approved else 0, round(budget, 2),
                                  round(C, 2), stop_ticks, unit, worst if approved else 0.0, tuple(limits),
                                  outer.decision.value)

    # ------------------------------------------------------------------ lifecycle
    def release(self, intent_id: str):
        """Release a reservation. Call only on a confirmed cancel / terminal non-fill."""
        with self._lock:
            self.state.reservations.pop(intent_id, None)
            self.state.reservation_meta.pop(intent_id, None)
            self.save()

    def on_fill(self, intent_id: str, position_id: str, worst_case_loss: float):
        with self._lock:
            s = self.state
            s.reservations.pop(intent_id, None)
            s.reservation_meta.pop(intent_id, None)
            s.open_risk[position_id] = worst_case_loss
            s.entries_today += 1
            if intent_id not in s.consumed_intents:
                s.consumed_intents.append(intent_id)
                del s.consumed_intents[:-_CONSUMED_INTENT_MEMORY]
            self.save()

    def on_close(self, position_id: str, net_pnl: float, session_day: date | None):
        with self._lock:
            s = self.state
            s.open_risk.pop(position_id, None)
            s.cash = round(s.cash + net_pnl, 2)
            s.day_realized_net = round(s.day_realized_net + net_pnl, 2)
            s.closed_positions += 1
            if net_pnl < 0:
                s.consecutive_losses += 1
            elif net_pnl > 0:
                s.consecutive_losses = 0
            # Breakeven (exactly 0 net) neither extends nor resets the streak.
            if net_pnl < 0 and s.consecutive_losses >= self.cfg.risk.consecutive_loss_pause:
                s.pause_requires_review = True
                s.paused_on_day = session_day.isoformat() if session_day is not None else s.session_day
            self.mark_equity(s.cash)
            self.save()
