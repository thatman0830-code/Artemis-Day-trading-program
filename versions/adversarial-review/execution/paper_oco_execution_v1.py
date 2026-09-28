"""Single-use offline shared-position stop/target execution coordinator.

Uses V2 OHLC fills. Every proposed exit blocks further evaluation until accounting
is acknowledged; partial exits then require a new, externally verified protection
generation. No gateway transport, cancellation, cost invention, or persistence.
"""
from dataclasses import dataclass
from decimal import Decimal

from backtesting.execution_accounting_v2.accounting import AccountingEventKind
from backtesting.execution_accounting_v2.contracts import OrderSide, OrderType, TimeInForce, OrderState
from backtesting.execution_accounting_v2.order_ledger import LedgerEventKind, OrderLedgerEventV2
from backtesting.execution_accounting_v2.ohlc_execution import CollisionGroupV2, evaluate_bar
from backtesting.execution_accounting_v2.specifications import InstrumentProfile, canonical_fingerprint, _utc


class PaperOCOError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PaperOCOResultV1:
    result_id: str
    evaluation: object
    position_snapshot_id: str
    projected_remaining_quantity: Decimal
    state: str
    trading_authority: bool = False

    def __post_init__(self):
        if self.trading_authority is not False:
            raise PaperOCOError("protective evaluation grants no trading authority")


class PaperOCOCoordinatorV1:
    def __init__(self, *, accounting, ledger, stop_order_id, target_order_id,
                 policy, instructions, armed_at):
        accounting.verify_integrity(); ledger.verify_integrity(); _utc(armed_at,"armed_at")
        self.accounting=accounting; self.ledger=ledger; self.policy=policy
        self.instructions=tuple(instructions); self.armed_at=armed_at
        self.last_close=None; self.state="ARMED"; self.pending=None
        self.acknowledged_accounting=None
        self.quantity=accounting.snapshot.position.signed_quantity
        if accounting.profile is not InstrumentProfile.BTC_SPOT or accounting.market!="BTC" or self.quantity<=0:
            raise PaperOCOError("verified long BTC spot position required")
        if (armed_at < accounting.snapshot.as_of or stop_order_id==target_order_id
                or armed_at.second or armed_at.microsecond
                or any(event.event_time>armed_at for event in ledger.events)):
            raise PaperOCOError("invalid arming chronology or pair identity")
        stop=ledger.order(stop_order_id); target=ledger.order(target_order_id)
        ids={stop_order_id,target_order_id}
        if len(ledger.orders)!=2 or {i.order_id for i in self.instructions}!=ids or len(self.instructions)!=2:
            raise PaperOCOError("exactly one stop/target pair required")
        for order in (stop,target):
            intent=order.intent
            if (intent.side is not OrderSide.SELL or intent.run_id!=accounting.run_id
                    or (intent.market,intent.instrument_id,intent.contract_id)!=(accounting.market,accounting.instrument_id,accounting.contract_id)
                    or intent.quantity!=self.quantity or order.remaining_quantity!=self.quantity
                    or order.filled_quantity!=0 or intent.time_in_force is not TimeInForce.GTC
                    or intent.activation_at>armed_at or order.state.value!="ACTIVE"):
                raise PaperOCOError("pair must be active, unfilled, and match held units")
        entries={e.fill.order_id for e in accounting.events if e.kind is AccountingEventKind.FILL and e.fill.side is OrderSide.BUY}
        if stop.intent.parent_order_id!=target.intent.parent_order_id or entries!={stop.intent.parent_order_id}:
            raise PaperOCOError("pair must bind an accounted entry order")
        average=accounting.snapshot.position.average_entry_price
        if (stop.intent.order_type is not OrderType.STOP_MARKET or target.intent.order_type is not OrderType.LIMIT
                or not stop.intent.stop_price < average < target.intent.limit_price):
            raise PaperOCOError("long stop/target geometry invalid")
        self.group=CollisionGroupV2("collision-group-v2-1",canonical_fingerprint("paper-oco-v1",accounting.ledger_fingerprint,ledger.ledger_fingerprint),
            stop_order_id,target_order_id,True)

    def evaluate(self, *, bar, evaluated_at, accounting):
        if self.state!="ARMED":
            raise PaperOCOError("protective coordinator blocked: "+self.state)
        try:
            accounting.verify_integrity()
            if accounting!=self.accounting:
                raise PaperOCOError("position evidence changed; rearm required")
            expected_open=self.armed_at if self.last_close is None else self.last_close
            if bar.open_time!=expected_open:
                raise PaperOCOError("protection bar replay, gap or pre-arming chronology")
            result=evaluate_bar(ledger=self.ledger,bar=bar,evaluated_at=evaluated_at,
                instrument=accounting.instrument,policy=self.policy,instructions=self.instructions,
                collision_groups=(self.group,))
            consumed=sum((f.quantity for f in result.fills),Decimal(0))
            if len(result.fills)>1 or consumed>self.quantity:
                raise PaperOCOError("protective fill exceeds shared position ownership")
            state="AWAITING_ACCOUNTING" if result.fills else "ARMED"
            receipt=PaperOCOResultV1(canonical_fingerprint("paper-oco-result-v1",self.group,result.evaluation_id,accounting.ledger_fingerprint),
                result,accounting.snapshot.snapshot_id,self.quantity-consumed,state)
            self.ledger=result.output_ledger; self.last_close=bar.close_time; self.state=state
            if result.fills: self.pending=receipt
            return receipt
        except Exception:
            self.state="HALTED"
            raise

    def acknowledge_accounting(self, accounting):
        if self.state!="AWAITING_ACCOUNTING":
            raise PaperOCOError("no pending protective accounting")
        try:
            accounting.verify_integrity()
            original=self.accounting
            if (accounting.instrument!=original.instrument or accounting.run_id!=original.run_id
                    or accounting.policy!=original.policy or accounting.margin_specification!=original.margin_specification
                    or accounting.starting_cash!=original.starting_cash
                    or accounting.events[:len(original.events)]!=original.events):
                raise PaperOCOError("accounting ancestry or identity differs")
            appended=accounting.events[len(original.events):]
            fills=tuple(e.fill for e in appended if e.kind is AccountingEventKind.FILL)
            if (fills!=self.pending.evaluation.fills
                    or any(e.kind not in (AccountingEventKind.FILL,AccountingEventKind.MARK) for e in appended)
                    or accounting.snapshot.position.signed_quantity!=self.pending.projected_remaining_quantity):
                raise PaperOCOError("protective execution and accounting do not reconcile")
            self.state="FLAT_REQUIRES_SIBLING_CANCELLATION" if accounting.snapshot.position.signed_quantity==0 else "PARTIAL_REQUIRES_REARM"
            self.acknowledged_accounting=accounting
            return self.state
        except Exception:
            self.state="HALTED"
            raise

    def acknowledge_cancellation(self, *, accounting, cancellations):
        """Verify supplied V2 lifecycle facts; never issue cancellations or rearm."""
        if self.state not in ("FLAT_REQUIRES_SIBLING_CANCELLATION", "PARTIAL_REQUIRES_REARM"):
            raise PaperOCOError("cancellation acknowledgement blocked: " + self.state)
        try:
            accounting.verify_integrity()
            if accounting != self.acknowledged_accounting:
                raise PaperOCOError("cancellation accounting evidence changed")
            if type(cancellations) is not tuple or not 1 <= len(cancellations) <= 4:
                raise PaperOCOError("bounded explicit cancellation events required")
            ledger = self.ledger
            existing_ids = {event.event_id for event in ledger.events}
            seen = set()
            for event in cancellations:
                if (type(event) is not OrderLedgerEventV2
                        or event.kind not in (LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL)
                        or event.source_event_id != self.pending.result_id
                        or event.event_time <= max(fill.fill_time for fill in self.pending.evaluation.fills)
                        or event.event_time < accounting.snapshot.as_of
                        or event.event_id in existing_ids or event.event_id in seen
                        or event.fill_quantity is not None or event.replacement_intent is not None):
                    raise PaperOCOError("invalid or unrelated cancellation evidence")
                seen.add(event.event_id)
                ledger = ledger.apply(event)
            if any(order.state not in (OrderState.FILLED, OrderState.CANCELLED) for order in ledger.orders):
                raise PaperOCOError("old protective orders remain executable")
            self.ledger = ledger
            self.state = "CLOSED_FLAT" if accounting.snapshot.position.signed_quantity == 0 else "CANCELLED_REQUIRES_REARM"
            return self.state
        except Exception:
            self.state = "HALTED"
            raise
