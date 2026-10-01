"""Pilot engine: completed bars -> features -> setups -> decision -> risk -> route -> ledger.

Execution sequence per completed M1 bar (master spec execution_sequence):
  1. validate bar; roll session/contract; execute pending simulated orders at
     the first quote after their decision (this bar's open, or a live quote)
  2. update levels, timeframes, regimes, setups (completed bars only)
  3. protective management first: OCO stop/target, then time/session/event/
     kill-switch exits (queued to the next executable quote)
  4. evaluate newly CONFIRMED setups: ABSTAIN (envelope) / REJECT (rule) /
     ACCEPT -> reserve capacity -> PAPER intent or PROP advisory alert
Every decision and transition is appended to the evidence ledger with UTC
decision time, market-data time, strategy version and config hash.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import json
import os
import uuid

from mes_pilot.alerts import AlertOutbox, EntryAlert, ManagementAlert
from mes_pilot.account_rules import TrailingFloor, check_trade
from mes_pilot.bars import Aggregator, Bar, ET, is_exchange_holiday, session_date_for, validate_bar
from mes_pilot.config import PilotConfig
from mes_pilot.events import EventCalendar
from mes_pilot.ledger import EvidenceLedger
from mes_pilot.levels import LiquidityBook
from mes_pilot.modes import OperatingMode, build_route
from mes_pilot.regime import AccumulationTracker, VolatilityBand
from mes_pilot.risk import PilotRiskManager, effective_floor, stop_ticks_for
from mes_pilot.setups import Setup, SetupDetector
from mes_pilot.simulator import Intent, PaperSimulator, Quote, modeled_quote
from mes_pilot.structure import TimeframeState

UTC = timezone.utc
TFS = (1, 5, 15, 60, 240)


def git_commit(root: Path) -> str:
    """Read HEAD without spawning processes (keeps this package free of subprocess use)."""
    try:
        gitdir = root / ".git"
        if gitdir.is_file():
            location = gitdir.read_text(encoding="utf-8").strip()
            if not location.startswith("gitdir: "):
                return "UNKNOWN"
            gitdir = (root / location[8:]).resolve()
        common = gitdir
        if (gitdir / "commondir").exists():
            common = (gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()).resolve()
        head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref = head[5:]
            loose = common / ref
            if loose.exists():
                return f"{loose.read_text(encoding='utf-8').strip()} ({ref})"
            packed = common / "packed-refs"
            if packed.exists():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        return f"{line.split()[0]} ({ref})"
        return head
    except OSError:
        return "UNKNOWN"


class PilotEngine:
    def __init__(self, cfg: PilotConfig, *, out_dir: Path, evidence_label: str, data_source: str,
                 calendar: EventCalendar, mode: str | None = None, quote_mode: str = "MODELED",
                 faults: dict | None = None, sqlite_mirror=None, account_profile=None,
                 allow_unconfigured_prop_dry_run: bool = False, run_id: str | None = None,
                 calendar_policy_label: str = "REQUIRED", clock=None):
        self.cfg = cfg
        self.clock = clock or (lambda: datetime.now(UTC))   # injectable for deterministic tests
        self.mode = OperatingMode(mode or cfg.mode)
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.quote_mode = quote_mode
        self.calendar = calendar
        self.account_profile = account_profile
        self.account_floor = TrailingFloor(account_profile, account_profile.account_size) if account_profile else None
        self.allow_prop_dry_run = allow_unconfigured_prop_dry_run
        self.run_id = run_id or uuid.uuid4().hex
        tick = cfg.instrument.tick_size
        s = cfg.strategy
        self.tfs = {tf: TimeframeState(tf, tick, s.swing_side_bars, s.atr_period, s.er_period) for tf in TFS}
        self.aggs = {tf: Aggregator(tf) for tf in TFS if tf != 1}
        self.book = LiquidityBook(tick, cfg.session.asia, cfg.session.london, s.equal_tolerance_ticks)
        self.detector = SetupDetector(cfg, self.tfs, self.book)
        self.vol = VolatilityBand(s.volatility_sessions, s.volatility_band)
        a = cfg.accumulation
        self.accum = AccumulationTracker(a.lookback_closes, a.max_range_atr, a.max_er, a.stale_after_bars)
        self.risk = PilotRiskManager(cfg, self.out_dir / "risk-state.json")
        self.ledger = EvidenceLedger(self.out_dir, evidence_label, self.run_id, sqlite_mirror=sqlite_mirror)
        self.kill_path = self.out_dir / "kill-switch.json"

        self.simulator = None
        self.outbox = None
        if self.mode is OperatingMode.PAPER_AUTO:
            self.simulator = PaperSimulator(cfg, self.out_dir / "simulator-state.json", faults=faults)
            self.route = build_route(self.mode, simulator=self.simulator)
        else:
            self.outbox = AlertOutbox(self.out_dir / "prop-alerts.jsonl")
            self.route = build_route(self.mode, outbox=self.outbox, live_auto_enabled=cfg.live_auto_enabled)

        self.warmup = False   # True: build structure/regime history only; no decisions or session records
        self.pending: list[tuple[Intent, dict]] = []
        self.pending_exits: dict[str, str] = {}
        self.session: date | None = None
        self.contract: str | None = None
        self.last_bar: Bar | None = None
        self.last_m5 = None
        self.vol_state = ("UNAVAILABLE", None)
        self.blocked: str | None = None
        self.last_quote: Quote | None = None
        self._session_stats = self._new_stats()
        self.session_summaries: list[dict] = []

        self.ledger.append("RUN_MANIFEST", run_id=self.run_id, mode=self.mode.value, code_commit=git_commit(Path(__file__).parents[1]),
                           strategy_version=cfg.strategy_version, config_hash=cfg.config_hash, data_source=data_source,
                           quote_mode=quote_mode, calendar_source=calendar.source, calendar_policy=calendar_policy_label,
                           instrument={"root": cfg.instrument.root, "tick_size": tick, "tick_value": cfg.instrument.tick_value,
                                       "price_proxy": cfg.raw["instrument"]["price_proxy_root"]},
                           account_profile=getattr(account_profile, "profile_id", "UNCONFIGURED"),
                           paper_portfolio=cfg.raw.get("paper_portfolio"),
                           cost_model=cfg.raw["costs"], clock_policy="UTC internal; America/New_York session labels")
        self._reconcile_on_start()

    # ------------------------------------------------------------------ kill switch
    def kill_switch_active(self) -> bool:
        if self.risk.state.kill_switch_latched:
            return True
        if self.cfg.raw.get("paper_portfolio"):
            group_kill = self.out_dir.parent / "group-kill-switch.json"
            if group_kill.exists() and bool(json.loads(group_kill.read_text(encoding="utf-8")).get("active")):
                return True
        if not self.kill_path.exists():
            return False
        return bool(json.loads(self.kill_path.read_text(encoding="utf-8")).get("active"))

    def set_kill_switch(self, active: bool, reason: str):
        tmp = self.kill_path.with_name(f".kill.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps({"active": active, "reason": reason, "at": datetime.now(UTC).isoformat()}), encoding="utf-8")
        os.replace(tmp, self.kill_path)
        if active:
            self.risk.engage_kill_switch(reason)
        else:
            self.risk.clear_kill_switch(reason)
        self.ledger.append("KILL_SWITCH", active=active, reason=reason)

    # ------------------------------------------------------------------ restart reconciliation
    def _reconcile_on_start(self):
        if self.simulator is None:
            return
        sim_open = {p.position_id for p in self.simulator.open_positions()}
        risk_open = set(self.risk.state.open_risk)
        issues = []
        for intent_id in list(self.risk.state.reservations):
            # Pending intents are not persisted (lifetime 60 s); cancel so a late fill is refused.
            self.simulator.cancel(intent_id, "RESTART_PENDING_INTENT_CANCELLED")
            self.risk.release(intent_id)
            issues.append(f"STALE_RESERVATION_RELEASED:{intent_id}")
        if sim_open != risk_open:
            self.blocked = "RECONCILIATION_MISMATCH"
            issues.append(f"MISMATCH sim={sorted(sim_open)} risk={sorted(risk_open)}")
        if self.simulator.emergency:
            self.blocked = f"EMERGENCY:{self.simulator.emergency}"
        self.ledger.append("RECONCILIATION", at="startup", simulator_open=sorted(sim_open), risk_open=sorted(risk_open),
                           issues=issues, entries_blocked=self.blocked)

    def clear_block(self, note: str):
        was = self.blocked
        if self.simulator and self.simulator.emergency:
            self.simulator.clear_emergency()
        sim_open = {p.position_id for p in self.simulator.open_positions()} if self.simulator else set()
        if sim_open == set(self.risk.state.open_risk):
            self.blocked = None
        self.ledger.append("RECONCILIATION", at="operator_clear", previous_block=was, now_blocked=self.blocked, note=note)

    # ------------------------------------------------------------------ session handling
    @staticmethod
    def _new_stats() -> dict:
        return {"bars": 0, "window_bars": 0, "faults": [], "setups_created": Counter(), "confirmed": 0,
                "decisions": Counter(), "reasons": Counter(), "entries": 0, "positions": 0, "net_pnl": 0.0,
                "calendar_available": None, "max_gap_min": 0.0}

    def _local(self, ts: datetime) -> time:
        return ts.astimezone(ET).time()

    def _window_open(self, ts: datetime) -> bool:
        t = self._local(ts)
        return self.cfg.session.entry_start <= t < self.cfg.session.entry_end

    def _roll(self, bar: Bar):
        self._roll_session(session_date_for(bar.start))
        if self.contract is not None and _series(bar.contract) != _series(self.contract):
            self._structure_reset(bar, f"CONTRACT_ROLL {self.contract}->{bar.contract}")
        self.contract = bar.contract

    def _roll_session(self, day: date):
        if self.session is not None and day != self.session:
            self._close_session()
        if day != self.session:
            self.session = day
            self.risk.roll_session(day)
            self.vol.roll(day)
            self._session_stats = self._new_stats()
            # Point-in-time: availability as of the entry-window open (when decisions start).
            cal = self.calendar.status(datetime.combine(day, self.cfg.session.entry_start, ET).astimezone(UTC), day, currencies=(), impacts=(),
                                       before_min=0, after_min=0, flatten_before_min=0, required=self.cfg.events.required)
            self._session_stats["calendar_available"] = cal.calendar_available

    def _structure_reset(self, bar: Bar, reason: str):
        for tf in self.tfs.values():
            tf.reset()
        for agg in self.aggs.values():
            agg.reset()
        self.book.reset()
        self.detector.reset(at=bar.start)
        self.ledger.append("STRUCTURE_RESET", at=bar.start, reason=reason)

    def _close_session(self):
        st = self._session_stats
        if self.session is None or self.warmup:
            return
        if is_exchange_holiday(self.session):
            cls = "EXCHANGE_HOLIDAY_NO_ENTRIES"
        elif st["window_bars"] == 0:
            cls = "NO_SESSION_DATA_IN_WINDOW"
        elif st["faults"]:
            cls = "OPERATIONAL_FAULT"
        elif st["positions"] > 0 or st["entries"] > 0:
            cls = "TRADED"
        elif st["calendar_available"] is False and self.cfg.events.required:
            cls = "CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION"
        elif st["confirmed"] == 0:
            cls = "NO_VALID_SETUP"
        else:
            cls = "SETUPS_CONFIRMED_BUT_NOT_TAKEN"
        summary = {"session_date": self.session.isoformat(), "classification": cls,
                   "calendar_available": st["calendar_available"], "window_bars": st["window_bars"],
                   "setups_created": dict(st["setups_created"]), "setups_confirmed": st["confirmed"],
                   "decisions": dict(st["decisions"]), "skip_reasons": dict(st["reasons"]),
                   "entries": st["entries"], "positions": st["positions"], "net_pnl": round(st["net_pnl"], 2),
                   "faults": st["faults"][:20], "max_m1_gap_minutes_in_window": st["max_gap_min"],
                   "equity_after": self.risk.state.cash,
                   "paper_floor": self.risk.state.floor_usd,
                   "paper_peak_equity": self.risk.state.peak_equity,
                   "paper_floor_breached": self.risk.state.floor_breached}
        self.session_summaries.append(summary)
        self.ledger.append("SESSION_SUMMARY", dedupe_key=f"SESSION:{self.session}:{self.run_id}", **summary)

    def end_warmup(self):
        """Leave warmup: discard the warmup session's stats so it never produces a SESSION_SUMMARY."""
        self.session = None
        self._session_stats = self._new_stats()
        self.warmup = False
        self.ledger.append("WARMUP_COMPLETE", last_bar=self.last_bar.end if self.last_bar else None)

    def finish(self):
        if self.simulator is not None and not self.warmup:
            still_open = self.simulator.open_positions()
            if still_open:
                # Not flattened here: protective orders persist and the next run reconciles and manages them.
                self.ledger.append("OPEN_POSITIONS_AT_FINISH", positions=[p.position_id for p in still_open],
                                   note="protective stop/target remain active in persisted simulator state")
        self._close_session()
        self.session = None

    # ------------------------------------------------------------------ main entry
    def process_bar(self, bar: Bar, live_quote: Quote | None = None):
        fault = validate_bar(bar)
        if fault:
            if bar.start.tzinfo is not None:
                # Attribute the fault to the session it belongs to (may be a session's first bar).
                self._roll_session(session_date_for(bar.start))
            self._session_stats["faults"].append({"at": bar.start.isoformat(), "fault": fault})
            self.ledger.append("MARKET_FAULT", at=bar.start, fault=fault, contract=bar.contract)
            return
        if self.last_bar is not None and bar.start <= self.last_bar.start:
            self.ledger.append("MARKET_FAULT", at=bar.start, fault="DUPLICATE_OR_OUT_OF_ORDER_BAR")
            return
        self._roll(bar)
        st = self._session_stats
        st["bars"] += 1
        gap_min = (bar.start - self.last_bar.end).total_seconds() / 60 if self.last_bar else 0.0
        if self._window_open(bar.start):
            st["window_bars"] += 1
            st["max_gap_min"] = max(st["max_gap_min"], gap_min)

        # 1. executable quote for anything queued at the previous decision
        quote = live_quote or (modeled_quote(bar, self.cfg.instrument.tick_size, self.cfg.costs.spread_ticks)
                               if self.quote_mode == "MODELED" else None)
        if quote is not None:
            self.last_quote = quote
            self._execute_pending(quote, bar)

        # 2. structure (completed bars only)
        self.book.on_m1(bar)
        self.tfs[1].push(bar)
        m5_closed = []
        for tf, agg in self.aggs.items():
            for done in agg.push(bar):
                ev = self.tfs[tf].push(done)
                if tf in (60, 240):
                    for sw in ev["new_swings"]:
                        self.book.add_swing(sw)
                    for g in ev["new_gaps"]:
                        self.book.add_gap(g)
                if tf == 5:
                    m5_closed.append(done)
        for m5 in m5_closed:
            atr = self.tfs[5].atr()
            self.vol.observe(m5.end, atr)
            self.vol_state = self.vol.classify(m5.end, atr)
            self.accum.on_m5(list(self.tfs[5].bars), self.tfs[5].atr(exclude_last=1))
            before = set(self.detector.setups)
            self.detector.on_m5(m5, self._window_open(m5.start))
            for sid in set(self.detector.setups) - before:
                st["setups_created"][self.detector.setups[sid].family] += 1

        # 3. protective management
        if self.simulator is not None:
            for pos in self.simulator.on_bar(bar):
                self._record_close(pos)
            self._time_exits(bar)
            if self.quote_mode == "MODELED":
                edge = self.cfg.costs.spread_ticks * self.cfg.instrument.tick_size
                mark = Quote(bar.end, bar.close - edge, bar.close + edge, "MODELED_BAR_CLOSE")
            else:
                mark = live_quote
            if mark is not None:
                self._mark_paper_equity(mark)
        # 4. setups confirmed by this M1 close
        confirmed = self.detector.on_m1(bar)
        self._log_terminal_setups(bar)
        if confirmed and self.warmup:
            for c in confirmed:
                c.move("CANCELLED", bar.end, "WARMUP_NO_DECISIONS")
        elif confirmed:
            st["confirmed"] += len(confirmed)
            self._decide(confirmed, bar, gap_min, live_quote)
        self.last_bar = bar

    # ------------------------------------------------------------------ execution
    def process_quote(self, quote: Quote):
        """Live quotes between bars: fill queued intents/exits at the first quote after their decision."""
        self.last_quote = quote
        if self.simulator is not None:
            for pos in self.simulator.on_quote(quote):
                self._record_close(pos)
            open_positions = self.simulator.open_positions()
            if open_positions and self.kill_switch_active():
                for pos in open_positions:
                    closed = self.simulator.close(pos.position_id, quote, "KILL_SWITCH_FLATTEN")
                    if closed:
                        self._record_close(closed)
        if self.simulator is not None and (self.pending or self.pending_exits):
            self._execute_pending(quote, None)
        if self.simulator is not None:
            self._mark_paper_equity(quote)

    def _mark_paper_equity(self, quote: Quote):
        """Track liquidation-side equity, including open P&L and both sides' fees."""
        equity = self.risk.state.cash
        for pos in self.simulator.open_positions():
            exit_px = quote.bid if pos.side == "LONG" else quote.ask
            points = (exit_px - pos.entry_price) if pos.side == "LONG" else (pos.entry_price - exit_px)
            equity += points * self.cfg.instrument.point_value * pos.quantity
            equity -= pos.entry_fees + self.cfg.costs.commission_per_side * pos.quantity
        mark = self.risk.mark_equity(round(equity, 2))
        if not mark["new_breach"]:
            return
        self.blocked = "PAPER_TRAILING_FLOOR_BREACH"
        self.risk.engage_kill_switch(self.blocked)
        for intent, _ in self.pending:
            self.simulator.cancel(intent.intent_id, self.blocked)
            self.risk.release(intent.intent_id)
        self.pending.clear()
        self.ledger.append("PAPER_FLOOR_BREACH", at=quote.ts, quote_source=quote.source, **mark)
        for pos in list(self.simulator.open_positions()):
            closed = self.simulator.close(pos.position_id, quote, self.blocked)
            if closed:
                self._record_close(closed)

    def _execute_pending(self, quote: Quote, bar: Bar | None):
        for pos_id, reason in list(self.pending_exits.items()):
            pos = self.simulator.close(pos_id, quote, reason)
            if pos:
                self._record_close(pos)
            self.pending_exits.pop(pos_id, None)
        still = []
        for intent, ctx in self.pending:
            if quote.ts < intent.created_at:
                still.append((intent, ctx))
                continue
            if self.kill_switch_active():
                self.simulator.cancel(intent.intent_id, "KILL_SWITCH")
                self.risk.release(intent.intent_id)
                self.ledger.append("ORDER", dedupe_key=f"ORDER:{intent.intent_id}", intent_id=intent.intent_id,
                                   status="CANCELLED", reason="KILL_SWITCH")
                continue
            res = self.route.submit(intent, quote)
            self.ledger.append("ORDER", dedupe_key=f"ORDER:{intent.intent_id}", intent_id=intent.intent_id,
                               order_id=res.order_id, signal_id=intent.signal_id, status=res.status, reason=res.reason,
                               quote={"ts": quote.ts, "bid": quote.bid, "ask": quote.ask, "source": quote.source},
                               sent_at=quote.ts, requested_qty=intent.quantity)
            if res.position is not None:
                pos = res.position
                filled = self.simulator.orders[intent.intent_id]["filled_qty"]
                self.ledger.append("FILL", dedupe_key=f"FILL:{res.fill_id}", fill_id=res.fill_id, order_id=res.order_id,
                                   intent_id=intent.intent_id, signal_id=intent.signal_id, fill_time=pos.entry_time,
                                   requested_price=intent.entry_ref, fill_price=pos.entry_price, requested_qty=intent.quantity,
                                   filled_qty=filled, fees=pos.entry_fees,
                                   slippage_ticks=round((pos.entry_price - intent.entry_ref) / self.cfg.instrument.tick_size
                                                        * (1 if pos.side == "LONG" else -1), 2),
                                   latency_s=(pos.entry_time - intent.created_at).total_seconds(),
                                   protection_status=pos.protection_status, quote_source=quote.source)
                worst = self.risk.unit_loss(stop_ticks_for(self.cfg, pos.entry_price, pos.stop)) * filled
                self.risk.on_fill(intent.intent_id, pos.position_id, round(worst, 2))
                mirror_id = self.ledger.mirror_open(pos.position_id, symbol=self.cfg.instrument.root, side=pos.side,
                                                    quantity=filled, requested_entry=intent.entry_ref,
                                                    filled_entry=pos.entry_price, stop_price=pos.stop,
                                                    target_price=pos.target, entry_fee=pos.entry_fees)
                self.ledger.append("POSITION_OPENED", dedupe_key=f"OPEN:{pos.position_id}", position_id=pos.position_id,
                                   signal_id=pos.signal_id, setup_family=ctx["family"], side=pos.side, quantity=filled,
                                   entry_price=pos.entry_price, stop=pos.stop, target=pos.target,
                                   initial_risk_usd=pos.initial_risk_usd, protection_status=pos.protection_status,
                                   **({"mirror_id": mirror_id} if mirror_id else {}))
                self._session_stats["entries"] += 1
                if res.status == "EMERGENCY_FLATTENED":
                    self.blocked = "EMERGENCY:PROTECTION_REJECTED"
                    self.ledger.append("EMERGENCY", reason="PROTECTION_REJECTED", position_id=pos.position_id,
                                       action="FLATTENED_VIA_SIMULATOR", entries_blocked=True)
                    self._record_close(pos)
            else:
                self.risk.release(intent.intent_id)
        self.pending = still

    def _time_exits(self, bar: Bar):
        sess = self.cfg.session
        for pos in self.simulator.open_positions():
            if pos.position_id in self.pending_exits:
                continue
            reason = None
            cutoff = datetime.combine(bar.end.astimezone(ET).date(), sess.flat_by, ET) - timedelta(minutes=1)
            if self.kill_switch_active():
                reason = "KILL_SWITCH_FLATTEN"
            elif bar.end >= cutoff and self._local(bar.end) < time(17, 0):
                reason = "SESSION_CUTOFF"
            elif bar.end - pos.entry_time >= timedelta(minutes=self.cfg.strategy.max_hold_min - 1):
                reason = "MAX_HOLD_TIME"
            else:
                ev = self.calendar.status(bar.end, self.session, currencies=self.cfg.events.currencies,
                                          impacts=self.cfg.events.impacts, before_min=self.cfg.events.before_min,
                                          after_min=self.cfg.events.after_min,
                                          flatten_before_min=self.cfg.events.flatten_before_min,
                                          required=self.cfg.events.required,
                                          holding_until=pos.entry_time + timedelta(minutes=self.cfg.strategy.max_hold_min))
                if ev.flatten_required:
                    reason = "EVENT_FLATTEN"
            if reason:
                self.pending_exits[pos.position_id] = reason
                self.ledger.append("EXIT_PENDING", position_id=pos.position_id, reason=reason, decided_at=bar.end)

    def _record_close(self, pos):
        r = pos.initial_risk_usd or None
        net_r = round(pos.net_pnl / r, 4) if r else None
        hold = (pos.exit_time - pos.entry_time).total_seconds() / 60
        rec = self.ledger.append("POSITION_CLOSED", dedupe_key=f"CLOSE:{pos.position_id}", position_id=pos.position_id,
                                 signal_id=pos.signal_id, setup_id=pos.setup_id, side=pos.side, quantity=pos.quantity,
                                 entry_price=pos.entry_price, exit_price=pos.exit_price, entry_time=pos.entry_time,
                                 exit_time=pos.exit_time, exit_reason=pos.exit_reason, gross_pnl=pos.gross_pnl,
                                 fees=round(pos.entry_fees + pos.exit_fees, 2), net_pnl=pos.net_pnl,
                                 initial_r_usd=pos.initial_risk_usd, net_r=net_r,
                                 outcome="WIN" if pos.net_pnl > 0 else ("LOSS" if pos.net_pnl < 0 else "BREAKEVEN"),
                                 mae_ticks=pos.mae_ticks, mfe_ticks=pos.mfe_ticks, hold_minutes=round(hold, 2),
                                 flags=pos.flags, protection_status=pos.protection_status)
        if rec is None:
            return
        self.ledger.mirror_close(pos.position_id, requested_exit=pos.exit_price, filled_exit=pos.exit_price,
                                 exit_fee=pos.exit_fees, gross_pnl=pos.gross_pnl, net_pnl=pos.net_pnl,
                                 exit_reason=pos.exit_reason)
        self.risk.on_close(pos.position_id, pos.net_pnl, self.session)
        self._session_stats["positions"] += 1
        self._session_stats["net_pnl"] += pos.net_pnl

    # ------------------------------------------------------------------ decisions
    def _log_terminal_setups(self, bar: Bar):
        if self.warmup:
            return
        stale_before = bar.end - timedelta(days=1)
        for sid in [k for k, v in self.detector.setups.items()
                    if v.terminal and v.created_at < stale_before and self.ledger.has(f"SETUP:{k}")]:
            del self.detector.setups[sid]   # keep the scan bounded on long replays (already logged)
        for st in self.detector.setups.values():
            if st.terminal and not self.ledger.has(f"SETUP:{st.setup_id}"):
                self.ledger.append("SETUP_TERMINAL", dedupe_key=f"SETUP:{st.setup_id}", setup_id=st.setup_id,
                                   family=st.family, direction=st.direction, state=st.state, reason=st.reason,
                                   transitions=st.transitions, confirmations=st.confirmations,
                                   refs=_jsonable(st.refs), strategy_version=self.cfg.strategy_version,
                                   config_hash=self.cfg.config_hash)
                if st.state in ("REJECTED", "INVALIDATED", "EXPIRED"):
                    self._session_stats["reasons"][f"{st.family}:{st.reason}"] += 1

    def _features(self, bar: Bar) -> dict:
        return {"h4_bias": self.tfs[240].bias, "h1_bias": self.tfs[60].bias, "m15_bias": self.tfs[15].bias,
                "m5_atr14": self.tfs[5].atr(), "m5_efficiency_ratio20": self.tfs[5].efficiency_ratio(),
                "m5_atr_percentile_state": self.vol_state[0], "m5_atr_percentile": self.vol_state[1],
                "accumulation_state": self.accum.s.state, "accumulation_false_breaks": self.accum.s.false_breaks,
                "range_location": self.accum.location(bar.close, self.cfg.instrument.tick_size),
                "range_bounds": [self.accum.s.low, self.accum.s.high]}

    def _decide(self, confirmed: list[Setup], bar: Bar, gap_min: float, live_quote: Quote | None):
        cfg, tick = self.cfg, self.cfg.instrument.tick_size
        conflict = len(confirmed) > 1
        for st in confirmed:
            decision, reason, risk_rec, extra = self._evaluate(st, bar, gap_min, live_quote, conflict)
            self._session_stats["decisions"][decision] += 1
            if decision != "ACCEPT":
                self._session_stats["reasons"][reason] += 1
                st.move("REJECTED" if decision == "REJECT" else "CANCELLED", bar.end, reason)
            self.ledger.append("CANDIDATE", dedupe_key=f"CANDIDATE:{st.setup_id}", signal_id=st.setup_id,
                               setup_family=st.family, setup_version=cfg.strategy_version, config_hash=cfg.config_hash,
                               direction=st.direction, decision_ts=bar.end, market_data_ts=bar.start,
                               session_date=self.session, contract=bar.contract, features=_jsonable(self._features(bar)),
                               confirmations=st.confirmations, refs=_jsonable(st.refs), transitions=st.transitions,
                               level_count_frozen=len(st.frozen_levels), entry_zone=st.zone, stop=st.stop,
                               target=st.target, target_level_id=st.target_level_id, decision_state=decision,
                               reason=reason, risk=risk_rec, **extra)
            if decision == "ACCEPT":
                self._accept(st, bar, risk_rec, extra)
            if not st.terminal:
                continue   # ENTRY_PENDING: lifecycle continues in INTENT/ORDER/FILL/POSITION records
            self.ledger.append("SETUP_TERMINAL", dedupe_key=f"SETUP:{st.setup_id}", setup_id=st.setup_id,
                               family=st.family, direction=st.direction, state=st.state, reason=st.reason,
                               transitions=st.transitions, confirmations=st.confirmations, refs=_jsonable(st.refs),
                               strategy_version=cfg.strategy_version, config_hash=cfg.config_hash)

    def _evaluate(self, st: Setup, bar: Bar, gap_min: float, live_quote: Quote | None, conflict: bool):
        cfg, tick, s = self.cfg, self.cfg.instrument.tick_size, self.cfg.strategy
        edge = cfg.costs.spread_ticks * tick
        entry_ref = bar.close + edge if st.direction == "LONG" else bar.close - edge
        risk_pts = abs(entry_ref - st.stop)
        reward_pts = (st.target - entry_ref) if st.direction == "LONG" else (entry_ref - st.target)
        rr = round(reward_pts / risk_pts, 4) if risk_pts > 0 else None
        stop_ticks = int(round(risk_pts / tick))
        cost_r = (cfg.costs.round_trip_commission(1) / (stop_ticks * cfg.instrument.tick_value)) if stop_ticks else None
        p = s.planning_p
        exp_r = round(p * rr - (1 - p) * 1 - cost_r, 4) if (rr is not None and cost_r is not None) else None
        extra = {"entry_ref": entry_ref, "gross_reward_risk": rr, "stop_ticks_est": stop_ticks,
                 "probability": {"p_win": p, "status": "ASSUMPTION_NOT_MEASURED", "calibrated": "NOT_ESTIMATED"},
                 "assumed_expectancy_r": exp_r, "quote_mode": self.quote_mode}
        st.entry_ref = entry_ref

        def out(decision, reason, risk=None):
            return decision, reason, risk, extra

        # ---- ABSTAIN: outside the approved operating envelope
        if conflict:
            return out("REJECT", "CONCURRENT_SETUP_CONFLICT")
        if self.blocked:
            return out("ABSTAIN", f"ENTRIES_BLOCKED:{self.blocked}")
        if self.kill_switch_active():
            return out("ABSTAIN", "KILL_SWITCH_ACTIVE")
        cutoff = (datetime.combine(bar.end.astimezone(ET).date(), cfg.session.flat_by, ET) - timedelta(minutes=1))
        if not self._window_open(bar.end) or bar.end >= cutoff:
            return out("ABSTAIN", "OUTSIDE_ENTRY_WINDOW")
        if is_exchange_holiday(self.session):
            return out("ABSTAIN", "EXCHANGE_HOLIDAY_SESSION")
        ev = self.calendar.status(bar.end, self.session, currencies=cfg.events.currencies, impacts=cfg.events.impacts,
                                  before_min=cfg.events.before_min, after_min=cfg.events.after_min,
                                  flatten_before_min=cfg.events.flatten_before_min, required=cfg.events.required)
        extra["event_status"] = {"calendar_available": ev.calendar_available, "blackout": ev.in_blackout,
                                 "events": list(ev.event_titles), "reason": ev.reason}
        if ev.reason in ("CALENDAR_UNAVAILABLE", "EVENT_BLACKOUT"):
            return out("ABSTAIN", ev.reason)
        if gap_min > 1.0 + 1e-9:
            return out("ABSTAIN", "STALE_DATA_M1_GAP")
        if self.quote_mode == "LIVE":
            q = live_quote or self.last_quote
            if q is None:
                return out("ABSTAIN", "NO_EXECUTABLE_QUOTE")
            age = (bar.end - q.ts).total_seconds() if q.receive_ts is None else (self.clock() - q.receive_ts).total_seconds()
            extra["quote_status"] = {"age_s": age, "spread_ticks": q.spread / tick, "source": q.source}
            if age > cfg.max_quote_age_s:
                return out("ABSTAIN", "STALE_QUOTE")
            if q.bid <= 0 or q.ask < q.bid:
                return out("ABSTAIN", "INVALID_OR_CROSSED_QUOTE")
            if q.spread / tick > cfg.max_spread_ticks + 1e-9:
                return out("ABSTAIN", "SPREAD_TOO_WIDE")
        else:
            extra["quote_status"] = {"source": "MODELED_FROM_BAR_OPEN", "spread_ticks_modeled": 2 * cfg.costs.spread_ticks,
                                     "validated_spread": False}
        if s.volatility_filter and self.vol_state[0] != "IN_BAND":
            return out("ABSTAIN", f"VOLATILITY_{self.vol_state[0]}")
        if cfg.accumulation.gate and st.family == "CONTINUATION_C1" and \
                self.accum.location(bar.close, tick) in ("INTERIOR",):
            return out("ABSTAIN", "ACCUMULATION_INTERIOR")
        if self.simulator is not None and self.simulator.open_positions():
            return out("REJECT", "POSITION_ALREADY_OPEN")
        if self.pending:
            return out("REJECT", "ENTRY_ALREADY_PENDING")
        # ---- REJECT: a defined rule failed
        if rr is None or rr < s.min_rr - 1e-9:
            return out("REJECT", "INVALID_PAYOFF_BELOW_MIN_RR")
        if exp_r is None or exp_r <= 0:
            return out("REJECT", "NON_POSITIVE_ASSUMED_EXPECTANCY")
        intent_id = "INT-" + st.setup_id
        risk = self.risk.evaluate_and_reserve(intent_id=intent_id, side=st.direction, entry=entry_ref, stop=st.stop,
                                              session_open=True, kill_switch=self.kill_switch_active())
        rd = risk.as_dict()
        if not risk.approved:
            return out("REJECT", f"RISK:{risk.reason}", rd)
        if self.mode is OperatingMode.PROP_MANUAL_ALERTS:
            floor = self.account_floor.floor if self.account_floor is not None else effective_floor(cfg)
            acct = check_trade(self.account_profile, contracts_micro=risk.quantity,
                               day_loss_after_worst=max(0.0, -self.risk.state.day_realized_net) + risk.worst_case_loss,
                               equity_after_worst=self.risk.state.cash - risk.worst_case_loss, floor=floor)
            extra["account_rule_status"] = acct
            if not acct["allowed_for_prop_alert"] and not self.allow_prop_dry_run:
                self.risk.release(intent_id)
                return out("ABSTAIN", "PROP_PROFILE_UNCONFIGURED", rd)
        return out("ACCEPT", None, rd)

    def _accept(self, st: Setup, bar: Bar, risk_rec: dict, extra: dict):
        intent_id = "INT-" + st.setup_id
        st.move("RISK_APPROVED", bar.end, "ALL_CHECKS_PASSED")
        if self.mode is OperatingMode.PAPER_AUTO:
            intent = Intent(intent_id, st.setup_id, st.setup_id, st.direction, risk_rec["quantity"], st.entry_ref,
                            st.stop, st.target, bar.end, bar.end + timedelta(seconds=self.cfg.strategy.intent_lifetime_s),
                            self.cfg.strategy.intent_max_drift_ticks, risk_rec["worst_case_loss"])
            self.pending.append((intent, {"family": st.family}))
            st.move("ENTRY_PENDING", bar.end, "INTENT_QUEUED_FOR_NEXT_EXECUTABLE_QUOTE")
            self.ledger.append("INTENT", dedupe_key=f"INTENT:{intent_id}", intent_id=intent_id, signal_id=st.setup_id,
                               side=st.direction, quantity=intent.quantity, entry_ref=intent.entry_ref, stop=st.stop,
                               target=st.target, created_at=intent.created_at, expires_at=intent.expires_at,
                               worst_case_loss=intent.worst_case_loss)
        else:
            acct = extra.get("account_rule_status", {})
            alert = EntryAlert(alert_id="ALR-" + st.setup_id, signal_id=st.setup_id,
                               strategy_version=self.cfg.strategy_version, config_hash=self.cfg.config_hash,
                               contract=f"MES (price ref {bar.contract})", side=st.direction, setup=st.family,
                               detected_at=bar.end.isoformat(),
                               expires_at=(bar.end + timedelta(seconds=self.cfg.strategy.intent_lifetime_s)).isoformat(),
                               entry_zone=st.zone, current_price=bar.close, stop=st.stop, target=st.target,
                               suggested_quantity=risk_rec["quantity"], worst_case_risk_usd=risk_rec["worst_case_loss"],
                               gross_reward_risk=extra["gross_reward_risk"],
                               account_rule_status=acct.get("status", "UNCONFIGURED") + (" (DRY RUN - DO NOT TRADE ON PROP)" if self.allow_prop_dry_run and not acct.get("allowed_for_prop_alert") else ""),
                               invalidation=f"Price trades {'below' if st.direction == 'LONG' else 'above'} {st.stop} or target {st.target} reached before entry, or alert expired")
            res = self.route.emit(alert)
            # Advisory alerts never reserve paper capacity or create fills.
            self.risk.release(intent_id)
            st.move("CLOSED", bar.end, "ALERT_EMITTED" if res["emitted"] else res["reason"])
            self.ledger.append("ALERT", dedupe_key=f"ALERT:{alert.alert_id}", alert=asdict(alert),
                               emitted=res["emitted"], reason=res.get("reason"))


def _jsonable(obj):
    return json.loads(json.dumps(obj, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)))


def _series(contract: str) -> str:
    """ES and MES of the same expiry are one price series (e.g. ESZ6 / MESZ6 -> 'Z6')."""
    tail = contract[-2:]
    if len(contract) >= 3 and tail[0] in "FGHJKMNQUVXZ" and tail[1].isdigit():
        return tail
    return contract
