"""Fail-closed, offline paper gateway.  This module has no live-order capability."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json

from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderSide, OrderType, TimeInForce


class PaperGatewayReason(str, Enum):
    ACCEPTED = "ACCEPTED"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    DUPLICATE_CONFLICT = "DUPLICATE_CONFLICT"
    DISCONNECTED = "DISCONNECTED"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"
    FUTURE_MARKET_DATA = "FUTURE_MARKET_DATA"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    AUTHORIZATION_REJECTED = "AUTHORIZATION_REJECTED"
    EXPOSURE_LIMIT = "EXPOSURE_LIMIT"
    OPEN_ORDER_LIMIT = "OPEN_ORDER_LIMIT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    EVENT_APPLIED = "EVENT_APPLIED"
    EVENT_REPLAY = "EVENT_REPLAY"
    EVENT_CONFLICT = "EVENT_CONFLICT"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    TERMINAL_ORDER = "TERMINAL_ORDER"
    STALE_ORDER_VERSION = "STALE_ORDER_VERSION"
    EVENT_TIME_REGRESSION = "EVENT_TIME_REGRESSION"
    INVALID_FILL_QUANTITY = "INVALID_FILL_QUANTITY"


class PaperOrderState(str, Enum):
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    FILLED = "FILLED"


class PaperEventKind(str, Enum):
    FILL = "FILL"
    CANCEL = "CANCEL"


def _utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC")


def _positive(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError(f"{name} must be a positive finite Decimal")


def _fingerprint(*values: object) -> str:
    def default(value: object):
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, (Decimal, datetime, Enum)):
            return str(value.value if isinstance(value, Enum) else value)
        if hasattr(value, "__dataclass_fields__"):
            return {name: getattr(value, name) for name in value.__dataclass_fields__}
        raise TypeError(type(value).__name__)
    raw = json.dumps(values, default=default, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperGatewayPolicyV1:
    max_order_notional: Decimal
    max_total_notional: Decimal
    max_open_orders: int
    maximum_market_data_age: timedelta

    def __post_init__(self) -> None:
        _positive(self.max_order_notional, "max_order_notional")
        _positive(self.max_total_notional, "max_total_notional")
        if self.max_order_notional > self.max_total_notional:
            raise ValueError("per-order limit cannot exceed total limit")
        if not isinstance(self.max_open_orders, int) or isinstance(self.max_open_orders, bool) or self.max_open_orders < 1:
            raise ValueError("max_open_orders must be positive")
        if self.maximum_market_data_age <= timedelta(0):
            raise ValueError("maximum_market_data_age must be positive")


@dataclass(frozen=True, slots=True)
class PaperSubmissionV1:
    idempotency_key: str
    intent: OrderIntentV2
    reference_price: Decimal
    requested_at: datetime
    market_data_at: datetime
    authorization_id: str
    authorized: bool
    trading_authority: bool = False

    def __post_init__(self) -> None:
        for value, name in ((self.idempotency_key, "idempotency_key"),
                            (self.authorization_id, "authorization_id")):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be lowercase SHA-256")
        _positive(self.reference_price, "reference_price")
        _utc(self.requested_at, "requested_at"); _utc(self.market_data_at, "market_data_at")
        if self.trading_authority:
            raise ValueError("paper submission cannot carry trading authority")

    @property
    def fingerprint(self) -> str:
        return _fingerprint("paper-submission-v1", self)


@dataclass(frozen=True, slots=True)
class PaperContingentPairV1:
    """Atomic paper-only stop/target admission sharing one exposure quantity."""
    pair_id: str
    adverse: PaperSubmissionV1
    favorable: PaperSubmissionV1
    shared_exposure: bool = True
    trading_authority: bool = False

    def __post_init__(self) -> None:
        if len(self.pair_id)!=64 or any(c not in "0123456789abcdef" for c in self.pair_id):
            raise ValueError("pair_id must be lowercase SHA-256")
        if type(self.adverse) is not PaperSubmissionV1 or type(self.favorable) is not PaperSubmissionV1:
            raise ValueError("typed paper submissions required")
        if self.shared_exposure is not True or self.trading_authority is not False:
            raise ValueError("contingent pair authority or ownership invalid")
        expected=_fingerprint("paper-contingent-pair-identity-v1",
            self.adverse.fingerprint,self.favorable.fingerprint)
        if self.pair_id!=expected:
            raise ValueError("contingent pair identity mismatch")

    @classmethod
    def create(cls,adverse: PaperSubmissionV1,favorable: PaperSubmissionV1):
        identity=_fingerprint("paper-contingent-pair-identity-v1",
            adverse.fingerprint,favorable.fingerprint)
        return cls(identity,adverse,favorable,True,False)

    @property
    def fingerprint(self) -> str:
        return _fingerprint("paper-contingent-pair-v1",self)


@dataclass(frozen=True, slots=True)
class PaperOrderRecordV1:
    paper_order_id: str
    idempotency_key: str
    request_fingerprint: str
    order_id: str
    market: str
    notional: Decimal
    state: PaperOrderState
    accepted_at: datetime
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    version: int
    last_event_at: datetime | None
    event_fingerprints: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        for value, name in ((self.paper_order_id, "paper_order_id"),
                            (self.idempotency_key, "idempotency_key"),
                            (self.request_fingerprint, "request_fingerprint"),
                            (self.order_id, "order_id")):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be lowercase SHA-256")
        _positive(self.notional, "notional"); _positive(self.quantity, "quantity")
        for value, name in ((self.filled_quantity, "filled_quantity"),
                            (self.remaining_quantity, "remaining_quantity")):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError(f"{name} must be nonnegative finite Decimal")
        if self.filled_quantity + self.remaining_quantity != self.quantity:
            raise ValueError("paper order quantity conservation failure")
        if self.state is PaperOrderState.FILLED and self.remaining_quantity != 0:
            raise ValueError("filled paper order must have zero remaining quantity")
        if self.state is PaperOrderState.PARTIALLY_FILLED and not (0 < self.filled_quantity < self.quantity):
            raise ValueError("partial paper order requires a strict partial quantity")
        _utc(self.accepted_at, "accepted_at")
        if self.last_event_at is not None:
            _utc(self.last_event_at, "last_event_at")
            if self.last_event_at < self.accepted_at:
                raise ValueError("last event precedes acceptance")
        if self.version != len(self.event_fingerprints) or self.version < 0:
            raise ValueError("paper order version/event history mismatch")
        event_ids = tuple(item[0] for item in self.event_fingerprints)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("paper event identities must be unique")
        for event_id, fingerprint in self.event_fingerprints:
            for value in (event_id, fingerprint):
                if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                    raise ValueError("paper event identity must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class PaperOrderEventV1:
    event_id: str
    paper_order_id: str
    kind: PaperEventKind
    occurred_at: datetime
    expected_version: int
    fill_quantity: Decimal | None = None
    trading_authority: bool = False

    def __post_init__(self) -> None:
        for value, name in ((self.event_id, "event_id"), (self.paper_order_id, "paper_order_id")):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be lowercase SHA-256")
        if not isinstance(self.kind, PaperEventKind):
            raise ValueError("kind must be PaperEventKind")
        _utc(self.occurred_at, "occurred_at")
        if not isinstance(self.expected_version, int) or self.expected_version < 0:
            raise ValueError("expected_version must be nonnegative")
        if self.kind is PaperEventKind.FILL:
            _positive(self.fill_quantity, "fill_quantity")
        elif self.fill_quantity is not None:
            raise ValueError("cancel event cannot carry fill quantity")
        if self.trading_authority:
            raise ValueError("paper event cannot carry trading authority")

    @property
    def fingerprint(self) -> str:
        return _fingerprint("paper-order-event-v1", self)


@dataclass(frozen=True,slots=True)
class PaperContingentResolutionV1:
    resolution_id: str
    pair_id: str
    paper_order_ids: tuple[str,str]
    fill: PaperOrderEventV1
    cancellations: tuple[PaperOrderEventV1,...]
    trading_authority: bool=False

    def __post_init__(self):
        for value,name in ((self.resolution_id,"resolution_id"),(self.pair_id,"pair_id")):
            if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be lowercase SHA-256")
        if (type(self.paper_order_ids) is not tuple or len(self.paper_order_ids)!=2
                or len(set(self.paper_order_ids))!=2 or type(self.fill) is not PaperOrderEventV1
                or type(self.cancellations) is not tuple or not 1<=len(self.cancellations)<=2
                or self.fill.kind is not PaperEventKind.FILL
                or any(type(item) is not PaperOrderEventV1 or item.kind is not PaperEventKind.CANCEL
                    for item in self.cancellations) or self.trading_authority is not False):
            raise ValueError("invalid contingent resolution")
        expected=_fingerprint("paper-contingent-resolution-v1",self.pair_id,
            self.paper_order_ids,self.fill,self.cancellations)
        if self.resolution_id!=expected:
            raise ValueError("contingent resolution identity mismatch")

    @classmethod
    def create(cls,*,pair_id,paper_order_ids,fill,cancellations):
        paper_order_ids=tuple(paper_order_ids);cancellations=tuple(cancellations)
        identity=_fingerprint("paper-contingent-resolution-v1",pair_id,paper_order_ids,fill,cancellations)
        return cls(identity,pair_id,paper_order_ids,fill,cancellations,False)


@dataclass(frozen=True, slots=True)
class PaperGatewayDecisionV1:
    accepted: bool
    reason: PaperGatewayReason
    record: PaperOrderRecordV1 | None
    trading_authority: bool = False


@dataclass(frozen=True, slots=True)
class PaperGatewaySnapshotV1:
    policy: PaperGatewayPolicyV1
    connected: bool
    kill_switch_active: bool
    reconciliation_required: bool
    records: tuple[PaperOrderRecordV1, ...]
    snapshot_id: str
    trading_authority: bool = False

    def __post_init__(self) -> None:
        for value, name in ((self.connected, "connected"),
                            (self.kill_switch_active, "kill_switch_active"),
                            (self.reconciliation_required, "reconciliation_required"),
                            (self.trading_authority, "trading_authority")):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be bool")
        if self.trading_authority:
            raise ValueError("paper gateway integrity failure: trading authority")
        if not isinstance(self.records, tuple):
            raise ValueError("records must be immutable tuple")
        if self.snapshot_id and (len(self.snapshot_id) != 64 or any(c not in "0123456789abcdef" for c in self.snapshot_id)):
            raise ValueError("snapshot_id must be lowercase SHA-256")

    @classmethod
    def create(cls, policy: PaperGatewayPolicyV1) -> "PaperGatewaySnapshotV1":
        return cls._build(policy, True, False, False, ())

    @classmethod
    def _build(cls, policy, connected, kill_switch, reconciliation, records):
        identity = _fingerprint("paper-gateway-snapshot-v1", policy, connected, kill_switch,
                                reconciliation, records, False)
        return cls(policy, connected, kill_switch, reconciliation, records, identity, False)

    def _decision(self, reason, record=None):
        return PaperGatewayDecisionV1(reason in (PaperGatewayReason.ACCEPTED,
            PaperGatewayReason.IDEMPOTENT_REPLAY, PaperGatewayReason.EVENT_APPLIED,
            PaperGatewayReason.EVENT_REPLAY), reason, record, False)

    def submit(self, request: PaperSubmissionV1) -> tuple["PaperGatewaySnapshotV1", PaperGatewayDecisionV1]:
        existing = next((x for x in self.records if x.idempotency_key == request.idempotency_key), None)
        if existing:
            reason = (PaperGatewayReason.IDEMPOTENT_REPLAY if existing.request_fingerprint == request.fingerprint
                      else PaperGatewayReason.DUPLICATE_CONFLICT)
            return self, self._decision(reason, existing if reason is PaperGatewayReason.IDEMPOTENT_REPLAY else None)
        if any(x.order_id == request.intent.order_id for x in self.records):
            return self, self._decision(PaperGatewayReason.DUPLICATE_CONFLICT)
        for blocked, reason in ((self.kill_switch_active, PaperGatewayReason.KILL_SWITCH_ACTIVE),
                                (not self.connected, PaperGatewayReason.DISCONNECTED),
                                (self.reconciliation_required, PaperGatewayReason.RECONCILIATION_REQUIRED),
                                (not request.authorized, PaperGatewayReason.AUTHORIZATION_REJECTED),
                                (request.market_data_at > request.requested_at,
                                 PaperGatewayReason.FUTURE_MARKET_DATA),
                                (request.requested_at - request.market_data_at > self.policy.maximum_market_data_age,
                                 PaperGatewayReason.STALE_MARKET_DATA)):
            if blocked:
                return self, self._decision(reason)
        notional = request.intent.quantity * request.reference_price
        open_records = tuple(x for x in self.records if x.state in
            (PaperOrderState.ACCEPTED,PaperOrderState.PARTIALLY_FILLED))
        if notional > self.policy.max_order_notional or sum((x.notional for x in open_records), Decimal(0)) + notional > self.policy.max_total_notional:
            return self, self._decision(PaperGatewayReason.EXPOSURE_LIMIT)
        if len(open_records) >= self.policy.max_open_orders:
            return self, self._decision(PaperGatewayReason.OPEN_ORDER_LIMIT)
        record = PaperOrderRecordV1(_fingerprint("paper-order-v1", request.fingerprint), request.idempotency_key,
            request.fingerprint, request.intent.order_id, request.intent.market, notional,
            PaperOrderState.ACCEPTED, request.requested_at, request.intent.quantity, Decimal(0),
            request.intent.quantity, 0, None, ())
        updated = self._build(self.policy, self.connected, self.kill_switch_active,
                              self.reconciliation_required, self.records + (record,))
        return updated, updated._decision(PaperGatewayReason.ACCEPTED, record)

    def submit_contingent_pair(self, pair: PaperContingentPairV1):
        """Admit both exits or neither; never submit to an external venue."""
        if type(pair) is not PaperContingentPairV1:
            raise ValueError("typed contingent pair required")
        pair.__post_init__()
        submissions=(pair.adverse,pair.favorable)
        found=tuple(next((x for x in self.records if x.idempotency_key==r.idempotency_key),None)
            for r in submissions)
        if any(found):
            if all(found) and all(record.request_fingerprint==request.fingerprint
                    for record,request in zip(found,submissions)):
                return self,tuple(self._decision(PaperGatewayReason.IDEMPOTENT_REPLAY,item) for item in found)
            return self,(self._decision(PaperGatewayReason.DUPLICATE_CONFLICT),)*2
        if any(any(x.order_id==request.intent.order_id for x in self.records) for request in submissions):
            return self,(self._decision(PaperGatewayReason.DUPLICATE_CONFLICT),)*2
        adverse,favorable=(item.intent for item in submissions)
        common=("run_id","market","instrument_id","contract_id","side","quantity",
            "time_in_force","parent_order_id","configuration_version","execution_policy_version")
        invalid=(adverse.order_id==favorable.order_id
            or adverse.action_id==favorable.action_id
            or any(getattr(adverse,name)!=getattr(favorable,name) for name in common)
            or adverse.market!="BTC" or adverse.side is not OrderSide.SELL
            or adverse.quantity<=0 or adverse.time_in_force is not TimeInForce.GTC
            or adverse.parent_order_id is None
            or adverse.order_type is not OrderType.STOP_MARKET
            or favorable.order_type is not OrderType.LIMIT
            or adverse.stop_price is None or favorable.limit_price is None
            or not adverse.stop_price<submissions[0].reference_price<favorable.limit_price
            or submissions[0].reference_price!=submissions[1].reference_price
            or submissions[0].requested_at!=submissions[1].requested_at
            or submissions[0].market_data_at!=submissions[1].market_data_at
            or submissions[0].authorization_id!=submissions[1].authorization_id)
        invalid = invalid or any(item.intent.submitted_at!=item.requested_at
            or item.intent.activation_at!=item.requested_at for item in submissions)
        if invalid:
            return self,(self._decision(PaperGatewayReason.AUTHORIZATION_REJECTED),)*2
        for blocked,reason in ((self.kill_switch_active,PaperGatewayReason.KILL_SWITCH_ACTIVE),
                (not self.connected,PaperGatewayReason.DISCONNECTED),
                (self.reconciliation_required,PaperGatewayReason.RECONCILIATION_REQUIRED),
                (not all(r.authorized for r in submissions),PaperGatewayReason.AUTHORIZATION_REJECTED),
                (any(r.market_data_at>r.requested_at for r in submissions),PaperGatewayReason.FUTURE_MARKET_DATA),
                (any(r.requested_at-r.market_data_at>self.policy.maximum_market_data_age for r in submissions),
                    PaperGatewayReason.STALE_MARKET_DATA)):
            if blocked:return self,(self._decision(reason),)*2
        open_records=tuple(x for x in self.records if x.state in
            (PaperOrderState.ACCEPTED,PaperOrderState.PARTIALLY_FILLED))
        notionals=tuple(r.intent.quantity*r.reference_price for r in submissions)
        if (any(value>self.policy.max_order_notional for value in notionals)
                or sum((x.notional for x in open_records),Decimal(0))+max(notionals)>self.policy.max_total_notional):
            return self,(self._decision(PaperGatewayReason.EXPOSURE_LIMIT),)*2
        if len(open_records)+2>self.policy.max_open_orders:
            return self,(self._decision(PaperGatewayReason.OPEN_ORDER_LIMIT),)*2
        records=[]
        for request,notional in zip(submissions,notionals):
            records.append(PaperOrderRecordV1(_fingerprint("paper-order-v1",request.fingerprint),
                request.idempotency_key,request.fingerprint,request.intent.order_id,request.intent.market,
                notional,PaperOrderState.ACCEPTED,request.requested_at,request.intent.quantity,
                Decimal(0),request.intent.quantity,0,None,()))
        updated=self._build(self.policy,self.connected,self.kill_switch_active,
            self.reconciliation_required,self.records+tuple(records))
        return updated,tuple(updated._decision(PaperGatewayReason.ACCEPTED,item) for item in records)

    def apply_event(self, event: PaperOrderEventV1) -> tuple["PaperGatewaySnapshotV1", PaperGatewayDecisionV1]:
        index = next((i for i, item in enumerate(self.records)
                      if item.paper_order_id == event.paper_order_id), None)
        if index is None:
            return self, self._decision(PaperGatewayReason.ORDER_NOT_FOUND)
        record = self.records[index]
        previous = dict(record.event_fingerprints).get(event.event_id)
        if previous is not None:
            reason = PaperGatewayReason.EVENT_REPLAY if previous == event.fingerprint else PaperGatewayReason.EVENT_CONFLICT
            return self, self._decision(reason, record if reason is PaperGatewayReason.EVENT_REPLAY else None)
        if record.state in (PaperOrderState.CANCELLED, PaperOrderState.FILLED):
            return self, self._decision(PaperGatewayReason.TERMINAL_ORDER)
        if event.expected_version != record.version:
            return self, self._decision(PaperGatewayReason.STALE_ORDER_VERSION)
        if event.occurred_at < record.accepted_at or (record.last_event_at and event.occurred_at < record.last_event_at):
            return self, self._decision(PaperGatewayReason.EVENT_TIME_REGRESSION)
        filled = record.filled_quantity
        state = record.state
        if event.kind is PaperEventKind.FILL:
            filled += event.fill_quantity
            if filled > record.quantity:
                return self, self._decision(PaperGatewayReason.INVALID_FILL_QUANTITY)
            state = PaperOrderState.FILLED if filled == record.quantity else PaperOrderState.PARTIALLY_FILLED
        else:
            state = PaperOrderState.CANCELLED
        updated_record = PaperOrderRecordV1(record.paper_order_id, record.idempotency_key,
            record.request_fingerprint, record.order_id, record.market, record.notional, state,
            record.accepted_at, record.quantity, filled, record.quantity - filled, record.version + 1,
            event.occurred_at, record.event_fingerprints + ((event.event_id, event.fingerprint),))
        records = self.records[:index] + (updated_record,) + self.records[index + 1:]
        updated = self._build(self.policy, self.connected, self.kill_switch_active,
                              self.reconciliation_required, records)
        return updated, updated._decision(PaperGatewayReason.EVENT_APPLIED, updated_record)

    def resolve_contingent_pair(self,resolution: PaperContingentResolutionV1):
        """Apply one fill and all required cancellations, or preserve the input snapshot."""
        if type(resolution) is not PaperContingentResolutionV1:
            raise ValueError("typed contingent resolution required")
        resolution.__post_init__()
        if self.kill_switch_active:return self,(self._decision(PaperGatewayReason.KILL_SWITCH_ACTIVE),)
        if not self.connected:return self,(self._decision(PaperGatewayReason.DISCONNECTED),)
        if self.reconciliation_required:return self,(self._decision(PaperGatewayReason.RECONCILIATION_REQUIRED),)
        records=[]
        try:
            for identity in resolution.paper_order_ids:
                found=tuple(item for item in self.records if item.paper_order_id==identity)
                if len(found)!=1:raise ValueError("pair record missing")
                records.append(found[0])
            events=(resolution.fill,)+resolution.cancellations
            if any(event.paper_order_id not in resolution.paper_order_ids for event in events):
                raise ValueError("resolution event references foreign order")
            retained=[]
            for event in events:
                record=next(item for item in records if item.paper_order_id==event.paper_order_id)
                retained.append(dict(record.event_fingerprints).get(event.event_id)==event.fingerprint)
            if all(retained):
                return self,tuple(self._decision(PaperGatewayReason.EVENT_REPLAY,
                    next(item for item in records if item.paper_order_id==event.paper_order_id)) for event in events)
            if any(retained):raise ValueError("partial resolution replay")
            if (resolution.fill.paper_order_id not in resolution.paper_order_ids
                    or any(item.state is not PaperOrderState.ACCEPTED for item in records)):
                raise ValueError("pair is not unresolved")
            winner=next(item for item in records if item.paper_order_id==resolution.fill.paper_order_id)
            full=resolution.fill.fill_quantity==winner.remaining_quantity
            expected_cancel=set(resolution.paper_order_ids)-({winner.paper_order_id} if full else set())
            if ({item.paper_order_id for item in resolution.cancellations}!=expected_cancel
                    or len({item.event_id for item in resolution.cancellations})!=len(resolution.cancellations)
                    or any(item.occurred_at<=resolution.fill.occurred_at for item in resolution.cancellations)):
                raise ValueError("resolution cancellation coverage invalid")
            current=self;decisions=[]
            current,decision=current.apply_event(resolution.fill);decisions.append(decision)
            if not decision.accepted:raise ValueError("fill rejected")
            for event in sorted(resolution.cancellations,key=lambda item:(item.occurred_at,item.event_id)):
                current,decision=current.apply_event(event);decisions.append(decision)
                if not decision.accepted:raise ValueError("cancellation rejected")
            return current,tuple(decisions)
        except ValueError:
            return self,(self._decision(PaperGatewayReason.EVENT_CONFLICT),)

    def disconnect(self) -> "PaperGatewaySnapshotV1":
        return self._build(self.policy, False, self.kill_switch_active, True, self.records)

    def reconcile(self, observed: tuple[tuple[str, PaperOrderState, Decimal, Decimal, int], ...]) -> "PaperGatewaySnapshotV1":
        expected = tuple(sorted((x.paper_order_id, x.state, x.filled_quantity,
                                 x.remaining_quantity, x.version) for x in self.records))
        if tuple(sorted(observed)) != expected:
            return self._build(self.policy, False, True, True, self.records)
        return self._build(self.policy, True, self.kill_switch_active, False, self.records)

    def activate_kill_switch(self) -> "PaperGatewaySnapshotV1":
        return self._build(self.policy, self.connected, True, self.reconciliation_required, self.records)

    @classmethod
    def resume(cls, snapshot: "PaperGatewaySnapshotV1") -> "PaperGatewaySnapshotV1":
        expected = cls._build(snapshot.policy, snapshot.connected, snapshot.kill_switch_active,
                              snapshot.reconciliation_required, snapshot.records)
        if expected.snapshot_id != snapshot.snapshot_id or snapshot.trading_authority:
            raise ValueError("paper gateway snapshot integrity failure")
        return snapshot
