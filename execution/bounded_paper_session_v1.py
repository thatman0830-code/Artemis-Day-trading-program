"""Caller-driven offline session boundary; not an autonomous trading runner.

Every step requires explicit UTC time and evidence. No data collection, strategy,
fill generation, timer thread, or automatic recovery is performed here.
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from backtesting.execution_accounting_v2.contracts import OrderSide

from execution.supervised_paper_launch_decision_v1 import (
    SESSION_DURATION, MAXIMUM_COMMANDS, MAXIMUM_ORDER_NOTIONAL, MAXIMUM_GROSS_EXPOSURE,
)
from execution.supervised_paper_launch_evidence_v1 import (
    OwnerSupervisionConfirmationV1, evaluate_collected_launch_evidence, read_launch_evidence,
)
from execution.supervised_paper_launch_gate_v1 import SupervisedPaperLaunchPolicyV1
from execution.paper_reservation_checkpoint_v1 import PaperReservationCheckpointV1
from execution.supervised_paper_performance_v1 import SupervisedPaperPerformanceV1
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperWorkflowV1, SupervisedPaperPolicyV1, SupervisedPaperCycleV1,
    SupervisedPaperState,
)


class BoundedPaperSessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundedPaperSessionResultV1:
    session_id: str
    commands: int
    reserved_notional: Decimal
    ledger_id: str
    state: str
    trading_authority: bool = False


class BoundedPaperSessionV1:
    def __init__(self, *, root, initial_adapter, initial_accounting, evidence_path,
                 confirmation, expected_checkpoint, session_id,
                 refresh_launch_evidence_each_step=True):
        self.workflow = SupervisedPaperWorkflowV1(Path(root),
            SupervisedPaperPolicyV1(timedelta(seconds=5)), initial_adapter, session_id)
        self.bridge = SupervisedPaperPerformanceV1(self.workflow, initial_accounting)
        self.reservation = PaperReservationCheckpointV1(Path(root), session_id)
        self.evidence_path = Path(evidence_path)
        self.confirmation = confirmation
        if type(refresh_launch_evidence_each_step)is not bool:
            raise BoundedPaperSessionError("launch-evidence refresh policy must be boolean")
        self.refresh_launch_evidence_each_step=refresh_launch_evidence_each_step
        self.launch_decision=None
        identity = (initial_accounting.market, initial_accounting.instrument_id,
                    initial_accounting.contract_id, initial_accounting.profile)
        supported = {
            ("BTC", "BTC", None, InstrumentProfile.BTC_SPOT),
            ("BTC-PERP", "BTC", "BTC-PERP", InstrumentProfile.BTC_LINEAR_PERPETUAL),
        }
        if identity not in supported:
            raise BoundedPaperSessionError("bounded session requires an explicit supported BTC instrument")
        self.policy = SupervisedPaperLaunchPolicyV1(expected_checkpoint,
            timedelta(minutes=5), timedelta(minutes=5), SESSION_DURATION,
            MAXIMUM_COMMANDS, MAXIMUM_ORDER_NOTIONAL, MAXIMUM_GROSS_EXPOSURE,
            allowed_markets=(initial_accounting.market,))
        self.active = False
        self.commands = 0
        self.reserved = Decimal(0)
        self.filled_notional = Decimal(0)
        self.order_fill_notional = {}
        self.order_intents = {}
        self.contingent_pairs = {}
        self.seen_commands = set()
        self.seen_events = set()
        self.last_time = None
        self.deadline = None

    def _decision(self, now):
        # Rebuild the content-addressed owner confirmation, rather than accepting
        # a directly constructed or replaced record with a stale identity.
        c = self.confirmation
        rebuilt = OwnerSupervisionConfirmationV1.create(confirmed_at=c.confirmed_at,
            expires_at=c.expires_at, repository_checkpoint=c.repository_checkpoint,
            owner_supervision_confirmed=c.owner_supervision_confirmed,
            stop_control_verified=c.stop_control_verified,
            maximum_session_seconds=c.maximum_session_seconds,
            maximum_commands=c.maximum_commands,
            maximum_order_notional=c.maximum_order_notional,
            maximum_gross_exposure=c.maximum_gross_exposure)
        if rebuilt != c or c.owner_supervision_confirmed is not True or c.stop_control_verified is not True:
            raise BoundedPaperSessionError("owner confirmation invalid")
        if self.launch_decision is not None and not self.refresh_launch_evidence_each_step:
            if not c.confirmed_at<=now<c.expires_at:
                raise BoundedPaperSessionError("owner confirmation expired")
            return self.launch_decision
        decision = evaluate_collected_launch_evidence(evidence=read_launch_evidence(self.evidence_path),
            confirmation=c, policy=self.policy, as_of=now)
        if not decision.eligible:
            raise BoundedPaperSessionError("launch evidence blocked: " + ",".join(r.value for r in decision.reasons))
        self.launch_decision=decision
        return decision

    def start(self, now):
        if self.last_time is not None or self.active:
            raise BoundedPaperSessionError("session objects are single-use")
        decision = self._decision(now)
        self.last_time = now
        adapter = self.workflow.initial
        adapter.verify_integrity()
        if adapter.gateway.records or adapter.receipts or not adapter.gateway.connected or adapter.gateway.kill_switch_active or adapter.gateway.reconciliation_required:
            raise BoundedPaperSessionError("fresh healthy adapter required")
        book = self.bridge.initial_accounting
        identity=(book.market,book.instrument_id,book.contract_id,book.profile)
        if book.events or identity not in {
                ("BTC","BTC",None,InstrumentProfile.BTC_SPOT),
                ("BTC-PERP","BTC","BTC-PERP",InstrumentProfile.BTC_LINEAR_PERPETUAL)}:
            raise BoundedPaperSessionError("fresh supported BTC accounting required")
        # Never reuse a previous session or silently reset its counters.
        if self.workflow.root.is_symlink() or not self.workflow.root.is_dir() or any(self.workflow.root.iterdir()):
            raise BoundedPaperSessionError("fresh empty session directory required")
        self.workflow.acquire()
        try:
            result = self.bridge.start()
            # The prepared-only reservation is part of the durable session
            # boundary. Never begin an active session without it, and never
            # replace or reset a pre-existing reservation.
            self.reservation.initialize()
            self.deadline = min(now + decision.maximum_session_duration,
                decision.expires_at, self.confirmation.expires_at)
            self.active = True
            return result
        except Exception:
            self.workflow.release()
            raise

    def _long_exit_capacity(self):
        """Check held units and outstanding sells before any gateway mutation.

        No OCO credit is inferred: independent sell orders reserve independently.
        """
        adapter = self.workflow.store.load()
        ledger = self.bridge.store.load()
        if ledger.reconcile_gateway(adapter.gateway) != ledger:
            raise BoundedPaperSessionError("exit capacity requires reconciled current checkpoints")
        quantity = ledger.snapshot.position.signed_quantity
        if quantity < 0:
            raise BoundedPaperSessionError("negative position cannot provide long-exit capacity")
        reserved = Decimal(0); grouped = {}
        for record in adapter.gateway.records:
            if record.state.value not in ("ACCEPTED", "PARTIALLY_FILLED"):
                continue
            intent = self.order_intents.get(record.order_id)
            if intent is None:
                raise BoundedPaperSessionError("exit capacity has unknown outstanding order")
            if intent.side is OrderSide.SELL:
                group=self.contingent_pairs.get(intent.order_id)
                if group is None:reserved+=record.remaining_quantity
                else:grouped[group]=max(grouped.get(group,Decimal(0)),record.remaining_quantity)
        reserved+=sum(grouped.values(),Decimal(0))
        if reserved > quantity:
            raise BoundedPaperSessionError("outstanding sells exceed long-exit capacity")
        return quantity, reserved

    # Preserve the established internal name for retained spot-session tooling.
    def _spot_exit_capacity(self):
        return self._long_exit_capacity()

    def step(self, cycle, *, verified_fill=None, closed_mark=None):
        if not self.active:
            raise BoundedPaperSessionError("session is not active")
        try:
            if cycle.now < self.last_time or cycle.now >= self.deadline:
                raise BoundedPaperSessionError("session deadline or chronology violation")
            self._decision(cycle.now)
            if cycle.reconciliation_observation is not None:
                raise BoundedPaperSessionError("automatic recovery is unsupported")
            cmd = cycle.command
            if cmd is not None:
                if self.commands >= self.policy.maximum_commands or cmd.command_id in self.seen_commands:
                    raise BoundedPaperSessionError("command budget or replay violation")
                if cmd.contingent_pair is not None:
                    pair=cmd.contingent_pair; submissions=(pair.adverse,pair.favorable)
                    book=self.bridge.initial_accounting
                    if any((item.intent.market,item.intent.instrument_id,item.intent.contract_id)!=
                            (book.market,book.instrument_id,book.contract_id) for item in submissions):
                        raise BoundedPaperSessionError("contingent pair instrument mismatch")
                    if any(item.requested_at!=cycle.now or item.intent.submitted_at!=cycle.now
                            or item.intent.activation_at!=cycle.now for item in submissions):
                        raise BoundedPaperSessionError("contingent pair time mismatch")
                    held,exit_reserved=self._long_exit_capacity()
                    if pair.adverse.intent.quantity>held-exit_reserved:
                        raise BoundedPaperSessionError("contingent pair exceeds unreserved long-exit capacity")
                    notionals=tuple(item.reference_price*item.intent.quantity for item in submissions)
                    shared=max(notionals)
                    if (any(value>self.policy.maximum_order_notional for value in notionals)):
                        raise BoundedPaperSessionError("session contingent notional limit")
                    for item in submissions:
                        self.order_intents[item.intent.order_id]=item.intent
                        self.contingent_pairs[item.intent.order_id]=pair.pair_id
                elif cmd.submission is not None:
                    req = cmd.submission
                    intent = req.intent
                    book = self.bridge.initial_accounting
                    if (intent.market, intent.instrument_id, intent.contract_id) != (book.market, book.instrument_id, book.contract_id):
                        raise BoundedPaperSessionError("submission instrument mismatch")
                    if req.requested_at != cycle.now or intent.submitted_at > cycle.now or intent.activation_at > cycle.now:
                        raise BoundedPaperSessionError("submission time mismatch")
                    if intent.side is OrderSide.SELL:
                        held, exit_reserved = self._long_exit_capacity()
                        if intent.quantity > held - exit_reserved:
                            raise BoundedPaperSessionError("submission exceeds unreserved long-exit capacity")
                    notional = req.reference_price * intent.quantity
                    increases_exposure = intent.side is OrderSide.BUY
                    if (notional > self.policy.maximum_order_notional
                            or (increases_exposure and self.reserved + notional > self.policy.maximum_gross_exposure)):
                        raise BoundedPaperSessionError("session notional limit")
                    if increases_exposure:
                        self.reserved += notional  # Entry exposure budget is never recycled.
                    self.order_intents[intent.order_id] = intent
                else:
                    if cmd.event.event_id in self.seen_events or cmd.event.occurred_at > cycle.now:
                        raise BoundedPaperSessionError("event replay or future timestamp")
                    self.seen_events.add(cmd.event.event_id)
                self.commands += 1
                self.seen_commands.add(cmd.command_id)
            if verified_fill is not None:
                fill = verified_fill.fill
                intent = self.order_intents.get(fill.order_id)
                if intent is None or fill.side != intent.side or fill.fill_time > cycle.now:
                    raise BoundedPaperSessionError("fill order/side/time mismatch")
                if fill.side is OrderSide.SELL:
                    held, _ = self._long_exit_capacity()
                    if fill.quantity > held:
                        raise BoundedPaperSessionError("exit fill exceeds held long quantity")
                notional = abs(fill.quantity * fill.economic_price)
                order_total = self.order_fill_notional.get(fill.order_id, Decimal(0)) + notional
                increases_exposure = fill.side is OrderSide.BUY
                if (order_total > self.policy.maximum_order_notional
                        or (increases_exposure and self.filled_notional + notional > self.policy.maximum_gross_exposure)):
                    raise BoundedPaperSessionError("fill notional limit")
                if increases_exposure:self.filled_notional += notional
                self.order_fill_notional[fill.order_id] = order_total
            result = self.bridge.cycle(cycle, verified_fill=verified_fill, closed_mark=closed_mark)
            self.last_time = cycle.now
            adapter, receipt, health, ledger = result
            reservation=self.reservation.load()
            if cmd is not None and cmd.submission is not None and reservation["body"]["state"]!="EMPTY":
                self.reservation.commit(expected_checkpoint_id=reservation["checkpoint_id"])
            position = ledger.snapshot.position
            valuation = position.mark_price if position.mark_price is not None else position.average_entry_price
            position_notional = abs(position.signed_quantity * valuation) if valuation is not None else Decimal(0)
            outstanding=Decimal(0);grouped={}
            for record in adapter.gateway.records:
                if record.state.value not in ("ACCEPTED","PARTIALLY_FILLED"):continue
                intent=self.order_intents.get(record.order_id)
                if intent is None:raise BoundedPaperSessionError("gross exposure has unknown outstanding order")
                if intent.side is OrderSide.SELL:continue
                remaining=record.notional*record.remaining_quantity/record.quantity
                group=self.contingent_pairs.get(record.order_id)
                if group is None:outstanding+=remaining
                else:grouped[group]=max(grouped.get(group,Decimal(0)),remaining)
            outstanding+=sum(grouped.values(),Decimal(0))
            if position_notional + outstanding > self.policy.maximum_gross_exposure:
                raise BoundedPaperSessionError("marked gross exposure limit")
            if health.state is SupervisedPaperState.STOPPED:
                self.active = False
                self.workflow.release()
            elif health.state is not SupervisedPaperState.HEALTHY or (receipt is not None and not receipt.accepted):
                raise BoundedPaperSessionError("cycle rejected or unhealthy")
            return result
        except Exception:
            self.active = False
            try:
                # Use the last validated UTC clock if the failing input was bad.
                self.workflow.halt_performance_persistence(
                    SupervisedPaperCycleV1(self.last_time, self.last_time))
            except Exception as halt_error:
                raise BoundedPaperSessionError("session halt persistence unconfirmed") from halt_error
            finally:
                self.workflow.release()
            raise

    def stop(self, now):
        if not self.active:
            raise BoundedPaperSessionError("session is not active")
        try:
            if now < self.last_time:
                raise BoundedPaperSessionError("stop clock regression")
            document = {"session_id": self.workflow.session_id, "stop": True, "trading_authority": False}
            if not self.workflow.stop_path.exists():
                with open(self.workflow.stop_path, "x", encoding="utf-8") as stream:
                    json.dump(document, stream); stream.flush(); os.fsync(stream.fileno())
            adapter, _, health, ledger = self.bridge.cycle(SupervisedPaperCycleV1(now, now))
            if health.state is not SupervisedPaperState.STOPPED or adapter.gateway.connected:
                raise BoundedPaperSessionError("stop was not confirmed")
            return BoundedPaperSessionResultV1(self.workflow.session_id, self.commands,
                self.reserved, ledger.ledger_id, health.state.value)
        except Exception:
            try:
                self.workflow.halt_performance_persistence(
                    SupervisedPaperCycleV1(self.last_time, self.last_time))
            except Exception as halt_error:
                raise BoundedPaperSessionError("session stop/halt persistence unconfirmed") from halt_error
            raise
        finally:
            self.active = False
            self.workflow.release()
