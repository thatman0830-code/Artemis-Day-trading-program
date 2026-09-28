"""Deterministic append-only v2 order ledger.

Phase 2 owns lifecycle facts only.  It never decides whether market data earns a
fill and never computes economic accounting.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .contracts import OrderIntentV2, OrderState, OrderType, TimeInForce, _sha
from .specifications import _finite_decimal, _text, _utc, canonical_fingerprint, canonical_json_bytes


class LedgerEventKind(str, Enum):
    SUBMIT = "SUBMIT"
    FORCED_CLOSE_INTENT = "FORCED_CLOSE_INTENT"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    ACTIVATE = "ACTIVATE"
    TRIGGER = "TRIGGER"
    FILL = "FILL"
    EXECUTION_EVALUATED = "EXECUTION_EVALUATED"
    CANCEL_REQUEST = "CANCEL_REQUEST"
    CANCEL = "CANCEL"
    EXPIRE = "EXPIRE"
    REPLACE = "REPLACE"


EVENT_PRIORITY = {
    LedgerEventKind.SUBMIT: 10,
    LedgerEventKind.FORCED_CLOSE_INTENT: 10,
    LedgerEventKind.ACCEPT: 20,
    LedgerEventKind.REJECT: 25,
    LedgerEventKind.ACTIVATE: 30,
    LedgerEventKind.CANCEL_REQUEST: 40,
    LedgerEventKind.CANCEL: 41,
    LedgerEventKind.REPLACE: 42,
    LedgerEventKind.EXPIRE: 43,
    LedgerEventKind.TRIGGER: 50,
    LedgerEventKind.FILL: 60,
    LedgerEventKind.EXECUTION_EVALUATED: 60,
}


class OrderLedgerReason(str, Enum):
    INVALID_ORDER_TRANSITION = "INVALID_ORDER_TRANSITION"
    TERMINAL_ORDER_MUTATION = "TERMINAL_ORDER_MUTATION"
    ORDER_NOT_ACTIVE = "ORDER_NOT_ACTIVE"
    STOP_NOT_TRIGGERED = "STOP_NOT_TRIGGERED"
    ZERO_FILL_QUANTITY = "ZERO_FILL_QUANTITY"
    ORDER_OVERFILL = "ORDER_OVERFILL"
    QUANTITY_CONSERVATION_FAILURE = "QUANTITY_CONSERVATION_FAILURE"
    EVENT_SEQUENCE_REGRESSION = "EVENT_SEQUENCE_REGRESSION"
    EVENT_TIME_REGRESSION = "EVENT_TIME_REGRESSION"
    DUPLICATE_EVENT_CONFLICT = "DUPLICATE_EVENT_CONFLICT"
    STALE_ORDER_VERSION = "STALE_ORDER_VERSION"
    ORDER_IDENTITY_MISMATCH = "ORDER_IDENTITY_MISMATCH"
    CONTRACT_ELIGIBILITY_UNPROVEN = "CONTRACT_ELIGIBILITY_UNPROVEN"
    SESSION_BOUNDARY_UNPROVEN = "SESSION_BOUNDARY_UNPROVEN"
    IOC_ALREADY_EVALUATED = "IOC_ALREADY_EVALUATED"
    CANCELLED_ORDER_FILL = "CANCELLED_ORDER_FILL"
    REPLACED_ORDER_FILL = "REPLACED_ORDER_FILL"
    INVALID_REPLACEMENT = "INVALID_REPLACEMENT"
    AMBIGUOUS_INTRABAR_REJECTED = "AMBIGUOUS_INTRABAR_REJECTED"
    END_OF_DATA_RESIDUAL = "END_OF_DATA_RESIDUAL"
    MIXED_LEDGER_VERSION = "MIXED_LEDGER_VERSION"
    DUPLICATE_ORDER_CONFLICT = "DUPLICATE_ORDER_CONFLICT"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"


class OrderLedgerError(ValueError):
    def __init__(self, reason: OrderLedgerReason, detail: str):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}")


@dataclass(frozen=True, slots=True)
class OrderLedgerEventV2:
    schema_version: str
    event_id: str
    order_id: str
    kind: LedgerEventKind
    event_time: datetime
    sequence_number: int
    expected_order_version: int
    market: str
    instrument_id: str
    contract_id: str | None
    source_event_id: str
    reason_code: str
    fill_quantity: Decimal | None = None
    session_boundary_verified: bool = False
    contract_eligibility_verified: bool = False
    replacement_intent: OrderIntentV2 | None = None
    intrabar_owner: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != "order-ledger-event-v2-1":
            raise ValueError("unsupported ledger event schema_version")
        for name in ("event_id", "order_id", "source_event_id"):
            _sha(getattr(self, name), name)
        if not isinstance(self.kind, LedgerEventKind):
            raise ValueError("kind must be LedgerEventKind")
        _utc(self.event_time, "event_time")
        if not isinstance(self.sequence_number, int) or isinstance(self.sequence_number, bool) or self.sequence_number < 1:
            raise ValueError("sequence_number must be a positive integer")
        if not isinstance(self.expected_order_version, int) or isinstance(self.expected_order_version, bool) or self.expected_order_version < 0:
            raise ValueError("expected_order_version must be a nonnegative integer")
        for name in ("market", "instrument_id", "reason_code"):
            _text(getattr(self, name), name)
        if self.contract_id is not None:
            _text(self.contract_id, "contract_id")
        if self.fill_quantity is not None:
            _finite_decimal(self.fill_quantity, "fill_quantity")


@dataclass(frozen=True, slots=True)
class OrderLedgerTransitionV2:
    schema_version: str
    transition_id: str
    ledger_version: str
    order_id: str
    parent_order_id: str | None
    child_order_id: str | None
    market: str
    instrument_id: str
    contract_id: str | None
    event_time: datetime
    sequence_number: int
    transition_ordinal: int
    previous_state: OrderState
    resulting_state: OrderState
    accepted_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    reason_code: str
    source_event_id: str
    event_id: str
    event_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != "order-ledger-transition-v2-1" or self.ledger_version != "order-ledger-v2-1":
            raise ValueError("unsupported ledger transition version")
        for name in ("transition_id", "order_id", "source_event_id", "event_id", "event_fingerprint"):
            _sha(getattr(self, name), name)
        for name in ("parent_order_id", "child_order_id"):
            if getattr(self, name) is not None:
                _sha(getattr(self, name), name)
        for name in ("market", "instrument_id", "reason_code"):
            _text(getattr(self, name), name)
        _utc(self.event_time, "event_time")
        if not isinstance(self.sequence_number, int) or self.sequence_number < 1:
            raise ValueError("sequence_number must be positive integer")
        if not isinstance(self.transition_ordinal, int) or self.transition_ordinal < 1:
            raise ValueError("transition_ordinal must be positive integer")
        if not isinstance(self.previous_state, OrderState) or not isinstance(self.resulting_state, OrderState):
            raise ValueError("transition states must be OrderState")
        for name in ("accepted_quantity", "filled_quantity", "remaining_quantity"):
            value = getattr(self, name); _finite_decimal(value, name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.accepted_quantity != self.filled_quantity + self.remaining_quantity:
            raise ValueError("transition quantity conservation failure")


@dataclass(frozen=True, slots=True)
class OrderLedgerSnapshotV2:
    schema_version: str
    intent: OrderIntentV2
    state: OrderState
    order_version: int
    last_sequence_number: int
    last_event_time: datetime | None
    accepted_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    triggered: bool
    ioc_evaluated: bool
    transition_ids: tuple[str, ...]
    replacement_child_order_id: str | None
    forced_close_intent: bool

    def __post_init__(self) -> None:
        if self.schema_version != "order-ledger-snapshot-v2-1":
            raise ValueError("unsupported ledger snapshot version")
        if not isinstance(self.intent, OrderIntentV2) or not isinstance(self.state, OrderState):
            raise ValueError("snapshot intent/state types are invalid")
        for value, name in ((self.order_version, "order_version"),
                            (self.last_sequence_number, "last_sequence_number")):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be nonnegative integer")
        if self.last_event_time is not None:
            _utc(self.last_event_time, "last_event_time")
        for name in ("accepted_quantity", "filled_quantity", "remaining_quantity"):
            value = getattr(self, name); _finite_decimal(value, name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.accepted_quantity != self.filled_quantity + self.remaining_quantity:
            raise ValueError("snapshot quantity conservation failure")
        for transition_id in self.transition_ids:
            _sha(transition_id, "transition_id")
        if self.replacement_child_order_id is not None:
            _sha(self.replacement_child_order_id, "replacement_child_order_id")


@dataclass(frozen=True, slots=True)
class LedgerCheckpointV2:
    schema_version: str
    ledger: "OrderLedgerV2"
    ledger_fingerprint: str

    def verify(self) -> None:
        if self.schema_version != "order-ledger-checkpoint-v2-1":
            raise OrderLedgerError(OrderLedgerReason.MIXED_LEDGER_VERSION, "checkpoint schema mismatch")
        self.ledger.verify_integrity()
        if self.ledger_fingerprint != self.ledger.ledger_fingerprint:
            raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT, "checkpoint fingerprint mismatch")


TERMINAL_STATES = frozenset({OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED,
                             OrderState.EXPIRED, OrderState.REPLACED})

ALLOWED_TRANSITIONS = {
    OrderState.CREATED: frozenset({LedgerEventKind.SUBMIT, LedgerEventKind.FORCED_CLOSE_INTENT}),
    OrderState.SUBMITTED: frozenset({LedgerEventKind.ACCEPT, LedgerEventKind.REJECT}),
    OrderState.ACCEPTED: frozenset({LedgerEventKind.ACTIVATE, LedgerEventKind.REJECT,
                                    LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL}),
    OrderState.ACTIVE: frozenset({LedgerEventKind.TRIGGER, LedgerEventKind.FILL,
                                  LedgerEventKind.EXECUTION_EVALUATED,
                                  LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL,
                                  LedgerEventKind.EXPIRE, LedgerEventKind.REPLACE}),
    OrderState.TRIGGERED: frozenset({LedgerEventKind.FILL, LedgerEventKind.EXECUTION_EVALUATED,
                                     LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL,
                                     LedgerEventKind.EXPIRE, LedgerEventKind.REPLACE}),
    OrderState.PARTIALLY_FILLED: frozenset({LedgerEventKind.FILL, LedgerEventKind.CANCEL_REQUEST,
                                           LedgerEventKind.CANCEL, LedgerEventKind.EXPIRE,
                                           LedgerEventKind.REPLACE}),
    OrderState.CANCEL_REQUESTED: frozenset({LedgerEventKind.FILL, LedgerEventKind.CANCEL,
                                            LedgerEventKind.EXPIRE}),
}


def _transition_identity(*, ledger_version, event_id, event_fingerprint, ordinal, order_id,
                         parent_order_id, child_order_id, market, instrument_id, contract_id,
                         event_time, sequence_number, previous_state, resulting_state,
                         accepted_quantity, filled_quantity, remaining_quantity, reason_code,
                         source_event_id):
    return canonical_fingerprint("order-ledger-transition-v2-1", ledger_version, event_id,
        event_fingerprint, ordinal, order_id, parent_order_id, child_order_id, market,
        instrument_id, contract_id, event_time, sequence_number, previous_state, resulting_state,
        accepted_quantity, filled_quantity, remaining_quantity, reason_code, source_event_id)


@dataclass(frozen=True, slots=True)
class OrderLedgerV2:
    schema_version: str
    ledger_version: str
    orders: tuple[OrderLedgerSnapshotV2, ...]
    events: tuple[OrderLedgerEventV2, ...]
    event_fingerprints: tuple[tuple[str, str], ...]
    transitions: tuple[OrderLedgerTransitionV2, ...]
    ledger_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != "order-ledger-v2-1" or self.ledger_version != "order-ledger-v2-1":
            raise ValueError("unsupported order ledger version")
        if self.ledger_fingerprint:
            _sha(self.ledger_fingerprint, "ledger_fingerprint")
        order_ids = tuple(item.intent.order_id for item in self.orders)
        event_ids = tuple(item.event_id for item in self.events)
        if len(order_ids) != len(set(order_ids)) or len(event_ids) != len(set(event_ids)):
            raise ValueError("ledger identities must be unique")

    @classmethod
    def create(cls, intents: tuple[OrderIntentV2, ...], ledger_version: str = "order-ledger-v2-1") -> "OrderLedgerV2":
        if ledger_version != "order-ledger-v2-1":
            raise OrderLedgerError(OrderLedgerReason.MIXED_LEDGER_VERSION, "ledger version mismatch")
        ordered = tuple(sorted(intents, key=lambda item: item.order_id))
        if len({item.order_id for item in ordered}) != len(ordered):
            raise OrderLedgerError(OrderLedgerReason.DUPLICATE_ORDER_CONFLICT, "duplicate root order identity")
        zero = Decimal("0")
        snapshots = tuple(OrderLedgerSnapshotV2("order-ledger-snapshot-v2-1", item,
            OrderState.CREATED, 0, 0, None, zero, zero, zero, False, False, (), None, False)
            for item in ordered)
        ledger = cls("order-ledger-v2-1", ledger_version, snapshots, (), (), (), "")
        return replace(ledger, ledger_fingerprint=ledger._compute_fingerprint())

    def _compute_fingerprint(self) -> str:
        return canonical_fingerprint(self.schema_version, self.ledger_version, self.orders,
                                     self.events, self.event_fingerprints, self.transitions)

    def serialize(self) -> bytes:
        return canonical_json_bytes(self.schema_version, self.ledger_version, self.orders,
                                    self.events, self.event_fingerprints, self.transitions,
                                    self.ledger_fingerprint)

    def verify_integrity(self) -> None:
        if self.schema_version != "order-ledger-v2-1" or self.ledger_version != "order-ledger-v2-1":
            raise OrderLedgerError(OrderLedgerReason.MIXED_LEDGER_VERSION, "ledger schema mismatch")
        if self._compute_fingerprint() != self.ledger_fingerprint:
            raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT, "ledger fingerprint mismatch")
        if tuple(event.event_id for event in self.events) != tuple(event_id for event_id, _ in self.event_fingerprints):
            raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT, "event index mismatch")
        for event, (_, fingerprint) in zip(self.events, self.event_fingerprints):
            if canonical_fingerprint(event) != fingerprint:
                raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT, "event content tampered")
        for snapshot in self.orders:
            if snapshot.accepted_quantity != snapshot.filled_quantity + snapshot.remaining_quantity:
                raise OrderLedgerError(OrderLedgerReason.QUANTITY_CONSERVATION_FAILURE,
                                       "snapshot quantity does not reconcile")
        transition_ids = tuple(item.transition_id for item in self.transitions)
        if len(transition_ids) != len(set(transition_ids)):
            raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT,
                                   "duplicate transition identity")
        known_transitions = set(transition_ids)
        for snapshot in self.orders:
            if len(snapshot.transition_ids) != len(set(snapshot.transition_ids)) or not set(snapshot.transition_ids).issubset(known_transitions):
                raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT,
                                       "snapshot transition lineage is invalid")
        for item in self.transitions:
            expected = _transition_identity(ledger_version=item.ledger_version,
                event_id=item.event_id, event_fingerprint=item.event_fingerprint,
                ordinal=item.transition_ordinal, order_id=item.order_id,
                parent_order_id=item.parent_order_id, child_order_id=item.child_order_id,
                market=item.market, instrument_id=item.instrument_id, contract_id=item.contract_id,
                event_time=item.event_time, sequence_number=item.sequence_number,
                previous_state=item.previous_state, resulting_state=item.resulting_state,
                accepted_quantity=item.accepted_quantity, filled_quantity=item.filled_quantity,
                remaining_quantity=item.remaining_quantity, reason_code=item.reason_code,
                source_event_id=item.source_event_id)
            if item.transition_id != expected:
                raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT,
                                       "transition identity does not match content")

    def checkpoint(self) -> LedgerCheckpointV2:
        self.verify_integrity()
        return LedgerCheckpointV2("order-ledger-checkpoint-v2-1", self, self.ledger_fingerprint)

    @classmethod
    def resume(cls, checkpoint: LedgerCheckpointV2,
               events: tuple[OrderLedgerEventV2, ...]) -> "OrderLedgerV2":
        checkpoint.verify()
        ledger = checkpoint.ledger
        for event in events:
            ledger = ledger.apply(event)
        return ledger

    @classmethod
    def replay(cls, intents: tuple[OrderIntentV2, ...],
               events: tuple[OrderLedgerEventV2, ...]) -> "OrderLedgerV2":
        ledger = cls.create(intents)
        for event in events:
            ledger = ledger.apply(event)
        return ledger

    def order(self, order_id: str) -> OrderLedgerSnapshotV2:
        found = tuple(item for item in self.orders if item.intent.order_id == order_id)
        if len(found) != 1:
            raise OrderLedgerError(OrderLedgerReason.ORDER_NOT_FOUND, "order identity not present")
        return found[0]

    def validate_end_of_data(self) -> None:
        residual = tuple(item.intent.order_id for item in self.orders if item.state not in TERMINAL_STATES)
        if residual:
            raise OrderLedgerError(OrderLedgerReason.END_OF_DATA_RESIDUAL,
                                   f"{len(residual)} order(s) remain non-terminal")

    def apply(self, event: OrderLedgerEventV2) -> "OrderLedgerV2":
        if event.schema_version != "order-ledger-event-v2-1":
            raise OrderLedgerError(OrderLedgerReason.MIXED_LEDGER_VERSION, "event schema mismatch")
        fingerprint = canonical_fingerprint(event)
        existing = {event_id: value for event_id, value in self.event_fingerprints}
        if event.event_id in existing:
            if existing[event.event_id] == fingerprint:
                return self
            raise OrderLedgerError(OrderLedgerReason.DUPLICATE_EVENT_CONFLICT,
                                   "event identity reused with different content")
        expected_sequence = len(self.events) + 1
        if event.sequence_number != expected_sequence:
            raise OrderLedgerError(OrderLedgerReason.EVENT_SEQUENCE_REGRESSION,
                                   f"expected sequence {expected_sequence}")
        if self.events:
            previous = self.events[-1]
            if event.event_time < previous.event_time:
                raise OrderLedgerError(OrderLedgerReason.EVENT_TIME_REGRESSION, "event time moved backward")
            if event.event_time == previous.event_time:
                previous_key = (EVENT_PRIORITY[previous.kind], previous.event_id)
                current_key = (EVENT_PRIORITY[event.kind], event.event_id)
                if current_key <= previous_key:
                    raise OrderLedgerError(OrderLedgerReason.EVENT_SEQUENCE_REGRESSION,
                                           "equal-time events are not in canonical priority/identity order")
        snapshot = self.order(event.order_id)
        if (event.market, event.instrument_id, event.contract_id) != (
                snapshot.intent.market, snapshot.intent.instrument_id, snapshot.intent.contract_id):
            raise OrderLedgerError(OrderLedgerReason.ORDER_IDENTITY_MISMATCH,
                                   "event market/instrument/contract differs from order")
        if event.expected_order_version != snapshot.order_version:
            raise OrderLedgerError(OrderLedgerReason.STALE_ORDER_VERSION, "expected order version is stale")
        if event.kind == LedgerEventKind.EXECUTION_EVALUATED and snapshot.ioc_evaluated:
            raise OrderLedgerError(OrderLedgerReason.IOC_ALREADY_EVALUATED, "IOC already evaluated")
        if snapshot.state in TERMINAL_STATES:
            if event.kind == LedgerEventKind.FILL and snapshot.state == OrderState.CANCELLED:
                reason = OrderLedgerReason.CANCELLED_ORDER_FILL
            elif event.kind == LedgerEventKind.FILL and snapshot.state == OrderState.REPLACED:
                reason = OrderLedgerReason.REPLACED_ORDER_FILL
            else:
                reason = OrderLedgerReason.TERMINAL_ORDER_MUTATION
            raise OrderLedgerError(reason, "terminal order cannot transition")
        if event.kind not in ALLOWED_TRANSITIONS.get(snapshot.state, frozenset()):
            if event.kind == LedgerEventKind.FILL:
                reason = (OrderLedgerReason.STOP_NOT_TRIGGERED if snapshot.intent.order_type in
                          (OrderType.STOP_MARKET, OrderType.STOP_LIMIT) and not snapshot.triggered
                          else OrderLedgerReason.ORDER_NOT_ACTIVE)
            else:
                reason = OrderLedgerReason.INVALID_ORDER_TRANSITION
            raise OrderLedgerError(reason, f"{snapshot.state.value} cannot accept {event.kind.value}")
        if (snapshot.intent.time_in_force == TimeInForce.GTC and event.kind in
                (LedgerEventKind.TRIGGER, LedgerEventKind.FILL, LedgerEventKind.EXECUTION_EVALUATED)
                and not event.contract_eligibility_verified):
            raise OrderLedgerError(OrderLedgerReason.CONTRACT_ELIGIBILITY_UNPROVEN,
                                   "GTC execution event requires current contract-policy eligibility")
        updated, transitions, child = self._transition(snapshot, event, fingerprint)
        orders = tuple(item for item in self.orders if item.intent.order_id != snapshot.intent.order_id) + (updated,)
        if child is not None:
            if any(item.intent.order_id == child.intent.order_id for item in orders):
                raise OrderLedgerError(OrderLedgerReason.INVALID_REPLACEMENT,
                                       "replacement child identity already exists")
            orders += (child,)
        orders = tuple(sorted(orders, key=lambda item: item.intent.order_id))
        ledger = replace(self, orders=orders, events=self.events + (event,),
                         event_fingerprints=self.event_fingerprints + ((event.event_id, fingerprint),),
                         transitions=self.transitions + transitions, ledger_fingerprint="")
        ledger = replace(ledger, ledger_fingerprint=ledger._compute_fingerprint())
        ledger.verify_integrity()
        return ledger

    def _transition(self, snapshot, event, event_fingerprint):
        kind = event.kind
        state = snapshot.state
        accepted, filled, remaining = snapshot.accepted_quantity, snapshot.filled_quantity, snapshot.remaining_quantity
        triggered, ioc = snapshot.triggered, snapshot.ioc_evaluated
        child = None
        states: list[tuple[OrderState, str, Decimal, Decimal, Decimal]] = []
        if kind in (LedgerEventKind.SUBMIT, LedgerEventKind.FORCED_CLOSE_INTENT):
            next_state = OrderState.SUBMITTED
            forced = kind == LedgerEventKind.FORCED_CLOSE_INTENT
        elif kind == LedgerEventKind.ACCEPT:
            accepted = snapshot.intent.quantity; remaining = accepted
            next_state = OrderState.ACCEPTED; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.REJECT:
            next_state = OrderState.REJECTED; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.ACTIVATE:
            if not event.contract_eligibility_verified:
                raise OrderLedgerError(OrderLedgerReason.CONTRACT_ELIGIBILITY_UNPROVEN,
                                       "activation requires exact contract eligibility")
            next_state = OrderState.ACTIVE; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.TRIGGER:
            if snapshot.intent.order_type not in (OrderType.STOP_MARKET, OrderType.STOP_LIMIT):
                raise OrderLedgerError(OrderLedgerReason.INVALID_ORDER_TRANSITION,
                                       "only stop orders may trigger")
            triggered = True; next_state = OrderState.TRIGGERED; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.FILL:
            if state not in (OrderState.ACTIVE, OrderState.TRIGGERED, OrderState.PARTIALLY_FILLED,
                             OrderState.CANCEL_REQUESTED):
                raise OrderLedgerError(OrderLedgerReason.ORDER_NOT_ACTIVE, "fill requires active order")
            if snapshot.intent.order_type in (OrderType.STOP_MARKET, OrderType.STOP_LIMIT) and not triggered:
                raise OrderLedgerError(OrderLedgerReason.STOP_NOT_TRIGGERED, "stop must trigger before fill")
            if (snapshot.intent.order_type == OrderType.STOP_LIMIT and snapshot.last_event_time is not None
                    and event.event_time <= snapshot.last_event_time):
                raise OrderLedgerError(OrderLedgerReason.INVALID_ORDER_TRANSITION,
                                       "stop-limit fill must follow its trigger event")
            quantity = event.fill_quantity
            if quantity is None or quantity <= 0:
                raise OrderLedgerError(OrderLedgerReason.ZERO_FILL_QUANTITY, "fill quantity must be positive")
            if quantity > remaining:
                raise OrderLedgerError(OrderLedgerReason.ORDER_OVERFILL, "fill exceeds remaining quantity")
            filled += quantity; remaining -= quantity
            next_state = OrderState.FILLED if remaining == 0 else OrderState.PARTIALLY_FILLED
            forced = snapshot.forced_close_intent
            if snapshot.intent.time_in_force == TimeInForce.IOC:
                if ioc:
                    raise OrderLedgerError(OrderLedgerReason.IOC_ALREADY_EVALUATED, "IOC already evaluated")
                ioc = True
                if remaining > 0:
                    states.append((next_state, event.reason_code, accepted, filled, remaining))
                    next_state = OrderState.CANCELLED
        elif kind == LedgerEventKind.EXECUTION_EVALUATED:
            if snapshot.intent.time_in_force != TimeInForce.IOC or ioc:
                raise OrderLedgerError(OrderLedgerReason.IOC_ALREADY_EVALUATED, "not a first IOC evaluation")
            ioc = True; next_state = OrderState.CANCELLED; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.CANCEL_REQUEST:
            next_state = OrderState.CANCEL_REQUESTED; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.CANCEL:
            next_state = OrderState.CANCELLED; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.EXPIRE:
            if snapshot.intent.time_in_force == TimeInForce.DAY and not event.session_boundary_verified:
                raise OrderLedgerError(OrderLedgerReason.SESSION_BOUNDARY_UNPROVEN,
                                       "DAY expiry requires verified session boundary")
            if snapshot.intent.time_in_force == TimeInForce.GTC and not event.contract_eligibility_verified:
                raise OrderLedgerError(OrderLedgerReason.CONTRACT_ELIGIBILITY_UNPROVEN,
                                       "GTC expiry requires contract-policy evidence")
            next_state = OrderState.EXPIRED; forced = snapshot.forced_close_intent
        elif kind == LedgerEventKind.REPLACE:
            replacement = event.replacement_intent
            if replacement is None or replacement.parent_order_id != snapshot.intent.order_id or \
                    replacement.replaces_order_id != snapshot.intent.order_id or (
                replacement.market, replacement.instrument_id, replacement.contract_id) != (
                    snapshot.intent.market, snapshot.intent.instrument_id, snapshot.intent.contract_id):
                raise OrderLedgerError(OrderLedgerReason.INVALID_REPLACEMENT,
                                       "replacement child and identity linkage required")
            if replacement.quantity > remaining:
                raise OrderLedgerError(OrderLedgerReason.INVALID_REPLACEMENT,
                                       "replacement quantity exceeds parent residual")
            zero = Decimal("0")
            child = OrderLedgerSnapshotV2("order-ledger-snapshot-v2-1", replacement,
                OrderState.CREATED, 0, 0, None, zero, zero, zero, False, False, (), None, False)
            next_state = OrderState.REPLACED; forced = snapshot.forced_close_intent
        else:
            raise OrderLedgerError(OrderLedgerReason.INVALID_ORDER_TRANSITION, "undeclared event")
        states.append((next_state, event.reason_code, accepted, filled, remaining))
        transitions = []
        previous_state = state
        ids = list(snapshot.transition_ids)
        for ordinal, (resulting, reason, accepted_q, filled_q, remaining_q) in enumerate(states, 1):
            if accepted_q != filled_q + remaining_q or remaining_q < 0:
                raise OrderLedgerError(OrderLedgerReason.QUANTITY_CONSERVATION_FAILURE,
                                       "accepted != filled + remaining")
            transition_id = _transition_identity(ledger_version=self.ledger_version,
                event_id=event.event_id, event_fingerprint=event_fingerprint, ordinal=ordinal,
                order_id=snapshot.intent.order_id, parent_order_id=snapshot.intent.parent_order_id,
                child_order_id=child.intent.order_id if child is not None else None,
                market=snapshot.intent.market, instrument_id=snapshot.intent.instrument_id,
                contract_id=snapshot.intent.contract_id, event_time=event.event_time,
                sequence_number=event.sequence_number, previous_state=previous_state,
                resulting_state=resulting, accepted_quantity=accepted_q, filled_quantity=filled_q,
                remaining_quantity=remaining_q, reason_code=reason,
                source_event_id=event.source_event_id)
            transition = OrderLedgerTransitionV2("order-ledger-transition-v2-1", transition_id,
                self.ledger_version, snapshot.intent.order_id, snapshot.intent.parent_order_id,
                child.intent.order_id if child is not None else None, snapshot.intent.market,
                snapshot.intent.instrument_id, snapshot.intent.contract_id, event.event_time,
                event.sequence_number, ordinal, previous_state, resulting, accepted_q, filled_q,
                remaining_q, reason, event.source_event_id, event.event_id, event_fingerprint)
            transitions.append(transition); ids.append(transition_id); previous_state = resulting
        updated = OrderLedgerSnapshotV2("order-ledger-snapshot-v2-1", snapshot.intent, next_state,
            snapshot.order_version + 1, event.sequence_number, event.event_time, accepted, filled,
            remaining, triggered, ioc, tuple(ids), child.intent.order_id if child else snapshot.replacement_child_order_id,
            forced)
        return updated, tuple(transitions), child
