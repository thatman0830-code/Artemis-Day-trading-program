"""Phase 6 deterministic futures-rollover and perpetual-funding coordination.

The module emits immutable instructions and accounting-event inputs.  It never
creates a fill, submits an order, fetches data, or mutates an upstream ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from enum import Enum, IntEnum

from .accounting import (ACCOUNTING_VERSION, AccountingEventKind, AccountingEventV2,
                         AccountingSnapshotPhase4V2, FundingFactV2)
from .contracts import InstrumentSpecificationV2, OrderSide
from .ohlc_execution import ExecutionFillV2, OHLCBarV2
from .risk_sessions import RISK_POLICY_VERSION, VerifiedSessionV2
from .specifications import InstrumentProfile, _finite_decimal, _text, _utc, canonical_fingerprint
from .validation import is_on_grid


PHASE6_VERSION = "ROLLOVER_FUNDING_V2_PHASE6_1"


class Phase6Reason(str, Enum):
    OK = "OK"
    INVALID_ROLL_SPECIFICATION = "INVALID_ROLL_SPECIFICATION"
    STALE_ROLL_SPECIFICATION = "STALE_ROLL_SPECIFICATION"
    OVERLAPPING_ROLL_SPECIFICATION = "OVERLAPPING_ROLL_SPECIFICATION"
    AMBIGUOUS_ROLL_SPECIFICATION = "AMBIGUOUS_ROLL_SPECIFICATION"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    OUTGOING_NOT_CLOSED = "OUTGOING_NOT_CLOSED"
    OUTGOING_CLOSE_FAILED = "OUTGOING_CLOSE_FAILED"
    MISSING_OUTGOING_BAR = "MISSING_OUTGOING_BAR"
    MISSING_INCOMING_BAR = "MISSING_INCOMING_BAR"
    INCOMING_INCOMPLETE = "INCOMING_INCOMPLETE"
    PARTICIPATION_UNAVAILABLE = "PARTICIPATION_UNAVAILABLE"
    SAME_BAR_REJECTED = "SAME_BAR_REJECTED"
    LOOKAHEAD_REJECTED = "LOOKAHEAD_REJECTED"
    BAR_INELIGIBLE = "BAR_INELIGIBLE"
    FUNDING_NOT_SUPPORTED = "FUNDING_NOT_SUPPORTED"
    MISSING_FUNDING_FACT = "MISSING_FUNDING_FACT"
    LATE_FUNDING_FACT = "LATE_FUNDING_FACT"
    STALE_FUNDING_FACT = "STALE_FUNDING_FACT"
    FUNDING_BOUNDARY_MISSED = "FUNDING_BOUNDARY_MISSED"
    DUPLICATE_EVENT_CONFLICT = "DUPLICATE_EVENT_CONFLICT"
    DUPLICATE_ECONOMIC_EVENT = "DUPLICATE_ECONOMIC_EVENT"
    EVENT_TIME_REGRESSION = "EVENT_TIME_REGRESSION"
    PRIORITY_AMBIGUITY = "PRIORITY_AMBIGUITY"
    CHECKPOINT_TAMPERED = "CHECKPOINT_TAMPERED"
    INCOMPLETE_ROLL = "INCOMPLETE_ROLL"
    INCOMPLETE_FUNDING = "INCOMPLETE_FUNDING"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"


class Phase6Error(ValueError):
    def __init__(self, reason: Phase6Reason, detail: str):
        self.reason, self.detail = reason, detail
        super().__init__(f"{reason.value}: {detail}")


class RollLeg(str, Enum):
    OUTGOING_CLOSE = "OUTGOING_CLOSE"
    INCOMING_OPEN = "INCOMING_OPEN"


class RollStatus(str, Enum):
    PENDING_OUTGOING = "PENDING_OUTGOING"
    OUTGOING_PARTIAL = "OUTGOING_PARTIAL"
    FLAT_AWAITING_INCOMING = "FLAT_AWAITING_INCOMING"
    INCOMING_PARTIAL = "INCOMING_PARTIAL"
    COMPLETE = "COMPLETE"
    FAILED_OUTGOING = "FAILED_OUTGOING"


class Phase6EventKind(str, Enum):
    SETTLEMENT = "SETTLEMENT"
    FUNDING = "FUNDING"
    ROLLOVER_OUTGOING = "ROLLOVER_OUTGOING"
    ROLLOVER_INCOMING = "ROLLOVER_INCOMING"


class Phase6Priority(IntEnum):
    DATA_SESSION = 10
    SETTLEMENT = 20
    FUNDING = 21
    ROLLOVER_OUTGOING = 22
    ROLLOVER_INCOMING = 23
    MARKET_DATA = 30
    STRATEGY = 40
    PRE_TRADE_RISK = 50
    FILLS = 60
    ACCOUNTING = 70
    POST_ACCOUNTING_RISK = 80
    REPORTING = 90


_KIND_PRIORITY = {Phase6EventKind.SETTLEMENT: Phase6Priority.SETTLEMENT,
                  Phase6EventKind.FUNDING: Phase6Priority.FUNDING,
                  Phase6EventKind.ROLLOVER_OUTGOING: Phase6Priority.ROLLOVER_OUTGOING,
                  Phase6EventKind.ROLLOVER_INCOMING: Phase6Priority.ROLLOVER_INCOMING}


def _sha(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{field} must be lowercase SHA-256")


def _positive(value: Decimal, field: str) -> None:
    _finite_decimal(value, field)
    if value <= 0: raise ValueError(f"{field} must be positive")


def _identity(record) -> tuple[str, str, str | None]:
    return record.market, record.instrument_id, record.contract_id


@dataclass(frozen=True, slots=True)
class RollSpecificationV2:
    schema_version: str
    roll_specification_id: str
    run_id: str
    market: str
    instrument_id: str
    outgoing_contract_id: str
    incoming_contract_id: str
    opening_side: OrderSide
    outgoing_quantity: Decimal
    incoming_quantity: Decimal
    roll_time: datetime
    effective_from: datetime
    effective_to: datetime
    outgoing_session_id: str
    incoming_session_id: str
    outgoing_instrument_specification_id: str
    incoming_instrument_specification_id: str
    participation_limit: Decimal
    quantity_step: Decimal
    roll_version: str
    source_ids: tuple[str, ...]

    @classmethod
    def create(cls, **v) -> "RollSpecificationV2":
        names = ("run_id", "market", "instrument_id", "outgoing_contract_id", "incoming_contract_id",
            "opening_side", "outgoing_quantity", "incoming_quantity", "roll_time", "effective_from",
            "effective_to", "outgoing_session_id", "incoming_session_id",
            "outgoing_instrument_specification_id", "incoming_instrument_specification_id",
            "participation_limit", "quantity_step", "roll_version", "source_ids")
        rid = canonical_fingerprint("roll-specification-v2-1", *(v[n] for n in names))
        return cls("roll-specification-v2-1", rid, **v)

    def __post_init__(self) -> None:
        if self.schema_version != "roll-specification-v2-1" or self.roll_version != PHASE6_VERSION:
            raise ValueError("unsupported roll specification version")
        for n in ("roll_specification_id", "run_id", "outgoing_session_id", "incoming_session_id",
                  "outgoing_instrument_specification_id", "incoming_instrument_specification_id"):
            _sha(getattr(self, n), n)
        for n in ("market", "instrument_id", "outgoing_contract_id", "incoming_contract_id", "roll_version"):
            _text(getattr(self, n), n)
        if self.outgoing_contract_id == self.incoming_contract_id: raise ValueError("roll contracts must differ")
        for n in ("outgoing_quantity", "incoming_quantity", "quantity_step"): _positive(getattr(self, n), n)
        _positive(self.participation_limit, "participation_limit")
        if self.participation_limit > 1: raise ValueError("participation limit cannot exceed one")
        if not is_on_grid(self.outgoing_quantity, self.quantity_step) or not is_on_grid(self.incoming_quantity, self.quantity_step):
            raise ValueError("roll quantities must be on grid")
        for n in ("roll_time", "effective_from", "effective_to"): _utc(getattr(self, n), n)
        if not self.effective_from <= self.roll_time < self.effective_to: raise ValueError("roll time outside effective interval")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)): raise ValueError("roll sources invalid")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.market, self.instrument_id,
            self.outgoing_contract_id, self.incoming_contract_id, self.opening_side,
            self.outgoing_quantity, self.incoming_quantity, self.roll_time, self.effective_from,
            self.effective_to, self.outgoing_session_id, self.incoming_session_id,
            self.outgoing_instrument_specification_id, self.incoming_instrument_specification_id,
            self.participation_limit, self.quantity_step, self.roll_version, self.source_ids)
        if expected != self.roll_specification_id: raise ValueError("roll specification identity mismatch")


def validate_roll_specifications(specifications: tuple[RollSpecificationV2, ...]) -> None:
    seen: dict[tuple[str, str, datetime], RollSpecificationV2] = {}
    ordered = sorted(specifications, key=lambda x: (x.market, x.instrument_id, x.effective_from, x.roll_specification_id))
    for spec in ordered:
        key = (spec.market, spec.instrument_id, spec.roll_time)
        if key in seen and seen[key] != spec: raise Phase6Error(Phase6Reason.AMBIGUOUS_ROLL_SPECIFICATION, "multiple rolls share identity/time")
        seen[key] = spec
    for left, right in zip(ordered, ordered[1:]):
        if (left.market, left.instrument_id) == (right.market, right.instrument_id) and right.effective_from < left.effective_to:
            raise Phase6Error(Phase6Reason.OVERLAPPING_ROLL_SPECIFICATION, "roll specification intervals overlap")


@dataclass(frozen=True, slots=True)
class RolloverInstructionV2:
    schema_version: str
    instruction_id: str
    roll_specification_id: str
    leg: RollLeg
    market: str
    instrument_id: str
    contract_id: str
    side: OrderSide
    remaining_quantity: Decimal
    authorized_quantity: Decimal
    triggered_at: datetime
    trigger_bar_id: str
    eligible_bar_id: str
    session_id: str
    roll_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "rollover-instruction-v2-1" or self.roll_version != PHASE6_VERSION: raise ValueError("unsupported rollover instruction")
        for n in ("instruction_id", "roll_specification_id", "trigger_bar_id", "eligible_bar_id", "session_id"): _sha(getattr(self, n), n)
        _positive(self.remaining_quantity, "remaining_quantity"); _positive(self.authorized_quantity, "authorized_quantity")
        if self.authorized_quantity > self.remaining_quantity: raise ValueError("authorized quantity exceeds remaining")
        _utc(self.triggered_at, "triggered_at")
        expected = canonical_fingerprint(self.schema_version, self.roll_specification_id, self.leg,
            self.market, self.instrument_id, self.contract_id, self.side, self.remaining_quantity,
            self.authorized_quantity, self.triggered_at, self.trigger_bar_id, self.eligible_bar_id,
            self.session_id, self.roll_version)
        if expected != self.instruction_id: raise ValueError("rollover instruction identity mismatch")


@dataclass(frozen=True, slots=True)
class RolloverEventV2:
    schema_version: str
    event_id: str
    roll_specification_id: str
    leg: RollLeg
    fill_id: str
    bar_id: str
    event_time: datetime
    quantity: Decimal
    contract_id: str
    source_instruction_id: str

    def __post_init__(self) -> None:
        if self.schema_version != "rollover-event-v2-1": raise ValueError("unsupported rollover event")
        for n in ("event_id", "roll_specification_id", "fill_id", "bar_id", "source_instruction_id"): _sha(getattr(self, n), n)
        _utc(self.event_time, "event_time"); _positive(self.quantity, "quantity")
        expected = canonical_fingerprint(self.schema_version, self.roll_specification_id, self.leg,
            self.fill_id, self.bar_id, self.event_time, self.quantity, self.contract_id,
            self.source_instruction_id)
        if expected != self.event_id: raise ValueError("rollover event identity mismatch")


@dataclass(frozen=True, slots=True)
class RolloverStateV2:
    schema_version: str
    state_id: str
    specification: RollSpecificationV2
    status: RollStatus
    outgoing_filled: Decimal
    incoming_filled: Decimal
    temporarily_flat: bool
    events: tuple[RolloverEventV2, ...]
    failure_reason: Phase6Reason | None

    @classmethod
    def create(cls, specification: RollSpecificationV2, signed_outgoing_quantity: Decimal) -> "RolloverStateV2":
        _finite_decimal(signed_outgoing_quantity, "signed_outgoing_quantity")
        expected_sign = Decimal("1") if specification.opening_side == OrderSide.BUY else Decimal("-1")
        if signed_outgoing_quantity != expected_sign * specification.outgoing_quantity:
            raise Phase6Error(Phase6Reason.IDENTITY_MISMATCH, "outgoing position differs from roll specification")
        sid = canonical_fingerprint("rollover-state-v2-1", specification, RollStatus.PENDING_OUTGOING,
                                    Decimal("0"), Decimal("0"), False, (), None)
        return cls("rollover-state-v2-1", sid, specification, RollStatus.PENDING_OUTGOING,
                   Decimal("0"), Decimal("0"), False, (), None)

    def __post_init__(self) -> None:
        if self.schema_version != "rollover-state-v2-1": raise ValueError("unsupported rollover state")
        _sha(self.state_id, "state_id")
        for n in ("outgoing_filled", "incoming_filled"):
            _finite_decimal(getattr(self, n), n)
            if getattr(self, n) < 0: raise ValueError("roll filled quantity cannot be negative")
        expected = canonical_fingerprint(self.schema_version, self.specification, self.status,
            self.outgoing_filled, self.incoming_filled, self.temporarily_flat, self.events, self.failure_reason)
        if expected != self.state_id: raise ValueError("rollover state identity mismatch")


def eligible_roll_quantity(bar: OHLCBarV2, specification: RollSpecificationV2,
                           remaining: Decimal) -> Decimal:
    if bar.volume is None or bar.volume <= 0: raise Phase6Error(Phase6Reason.PARTICIPATION_UNAVAILABLE, "verified positive volume required")
    raw = min(remaining, bar.volume * specification.participation_limit)
    units = (raw / specification.quantity_step).to_integral_value(rounding=ROUND_FLOOR)
    result = units * specification.quantity_step
    if result <= 0: raise Phase6Error(Phase6Reason.PARTICIPATION_UNAVAILABLE, "participation floors to zero")
    return result


def create_roll_instruction(*, state: RolloverStateV2, bar: OHLCBarV2,
                            session: VerifiedSessionV2, trigger_bar_id: str,
                            outgoing_instrument: InstrumentSpecificationV2,
                            incoming_instrument: InstrumentSpecificationV2) -> RolloverInstructionV2:
    spec = state.specification; _sha(trigger_bar_id, "trigger_bar_id")
    if bar.bar_id == trigger_bar_id: raise Phase6Error(Phase6Reason.SAME_BAR_REJECTED, "roll action requires later bar")
    if bar.open_time <= spec.roll_time or bar.available_at < bar.close_time: raise Phase6Error(Phase6Reason.LOOKAHEAD_REJECTED, "roll bar not available after decision")
    if not (bar.finalized and bar.session_eligible and bar.data_quality_valid and bar.contract_eligible): raise Phase6Error(Phase6Reason.BAR_INELIGIBLE, "roll bar ineligible")
    if not spec.effective_from <= bar.open_time < spec.effective_to: raise Phase6Error(Phase6Reason.STALE_ROLL_SPECIFICATION, "roll spec not effective")
    if state.status in (RollStatus.PENDING_OUTGOING, RollStatus.OUTGOING_PARTIAL):
        leg, contract, side = RollLeg.OUTGOING_CLOSE, spec.outgoing_contract_id, (OrderSide.SELL if spec.opening_side == OrderSide.BUY else OrderSide.BUY)
        remaining = spec.outgoing_quantity - state.outgoing_filled; expected_session = spec.outgoing_session_id
        expected_instrument = outgoing_instrument
    elif state.status in (RollStatus.FLAT_AWAITING_INCOMING, RollStatus.INCOMING_PARTIAL):
        leg, contract, side = RollLeg.INCOMING_OPEN, spec.incoming_contract_id, spec.opening_side
        remaining = spec.incoming_quantity - state.incoming_filled; expected_session = spec.incoming_session_id
        expected_instrument = incoming_instrument
    else:
        raise Phase6Error(Phase6Reason.OUTGOING_CLOSE_FAILED if state.status == RollStatus.FAILED_OUTGOING else Phase6Reason.INCOMPLETE_ROLL, "roll has no eligible next leg")
    if (_identity(bar) != (spec.market, spec.instrument_id, contract) or session.session_id != expected_session or
            _identity(expected_instrument) != (spec.market, spec.instrument_id, contract)):
        raise Phase6Error(Phase6Reason.IDENTITY_MISMATCH, "bar/session/instrument differs from roll leg")
    if expected_instrument.specification_id != (spec.outgoing_instrument_specification_id if leg == RollLeg.OUTGOING_CLOSE else spec.incoming_instrument_specification_id):
        raise Phase6Error(Phase6Reason.VERSION_MISMATCH, "instrument specification lineage differs")
    if not session.open_time <= bar.open_time and bar.close_time <= session.close_time: raise Phase6Error(Phase6Reason.IDENTITY_MISMATCH, "bar outside verified session")
    authorized = eligible_roll_quantity(bar, spec, remaining)
    iid = canonical_fingerprint("rollover-instruction-v2-1", spec.roll_specification_id, leg,
        spec.market, spec.instrument_id, contract, side, remaining, authorized, bar.open_time,
        trigger_bar_id, bar.bar_id, session.session_id, spec.roll_version)
    return RolloverInstructionV2("rollover-instruction-v2-1", iid, spec.roll_specification_id,
        leg, spec.market, spec.instrument_id, contract, side, remaining, authorized,
        bar.open_time, trigger_bar_id, bar.bar_id, session.session_id, spec.roll_version)


def apply_roll_fill(state: RolloverStateV2, instruction: RolloverInstructionV2,
                    fill: ExecutionFillV2) -> RolloverStateV2:
    spec = state.specification
    if instruction.roll_specification_id != spec.roll_specification_id or fill.market_event_id != instruction.eligible_bar_id:
        raise Phase6Error(Phase6Reason.IDENTITY_MISMATCH, "fill lineage differs from instruction")
    if (fill.market, fill.instrument_id, fill.contract_id, fill.side) != (instruction.market,
            instruction.instrument_id, instruction.contract_id, instruction.side):
        raise Phase6Error(Phase6Reason.IDENTITY_MISMATCH, "fill identity differs from roll instruction")
    if fill.quantity > instruction.authorized_quantity: raise Phase6Error(Phase6Reason.PARTICIPATION_UNAVAILABLE, "fill exceeds authorized participation")
    event_id = canonical_fingerprint("rollover-event-v2-1", spec.roll_specification_id,
        instruction.leg, fill.fill_id, fill.market_event_id, fill.fill_time, fill.quantity,
        fill.contract_id, instruction.instruction_id)
    event = RolloverEventV2("rollover-event-v2-1", event_id, spec.roll_specification_id,
        instruction.leg, fill.fill_id, fill.market_event_id, fill.fill_time, fill.quantity,
        fill.contract_id, instruction.instruction_id)
    existing = {item.fill_id: item for item in state.events}
    if fill.fill_id in existing:
        if existing[fill.fill_id] == event: return state
        raise Phase6Error(Phase6Reason.DUPLICATE_EVENT_CONFLICT, "roll fill identity reused with conflicting facts")
    outgoing, incoming = state.outgoing_filled, state.incoming_filled
    if instruction.leg == RollLeg.OUTGOING_CLOSE:
        if state.status not in (RollStatus.PENDING_OUTGOING, RollStatus.OUTGOING_PARTIAL): raise Phase6Error(Phase6Reason.OUTGOING_NOT_CLOSED, "outgoing leg no longer active")
        outgoing += fill.quantity
        status = RollStatus.FLAT_AWAITING_INCOMING if outgoing == spec.outgoing_quantity else RollStatus.OUTGOING_PARTIAL
        flat = status == RollStatus.FLAT_AWAITING_INCOMING
    else:
        if state.status not in (RollStatus.FLAT_AWAITING_INCOMING, RollStatus.INCOMING_PARTIAL): raise Phase6Error(Phase6Reason.OUTGOING_NOT_CLOSED, "incoming blocked until outgoing closed")
        incoming += fill.quantity
        status = RollStatus.COMPLETE if incoming == spec.incoming_quantity else RollStatus.INCOMING_PARTIAL
        flat = incoming == 0
    if outgoing > spec.outgoing_quantity or incoming > spec.incoming_quantity: raise Phase6Error(Phase6Reason.PARTICIPATION_UNAVAILABLE, "roll overfilled")
    if not is_on_grid(fill.quantity, spec.quantity_step): raise Phase6Error(Phase6Reason.PARTICIPATION_UNAVAILABLE, "roll fill is off quantity grid")
    if state.events and event.event_time < state.events[-1].event_time:
        raise Phase6Error(Phase6Reason.EVENT_TIME_REGRESSION, "roll fill chronology regressed")
    events = state.events + (event,)
    sid = canonical_fingerprint(state.schema_version, spec, status, outgoing, incoming, flat, events, None)
    return RolloverStateV2(state.schema_version, sid, spec, status, outgoing, incoming, flat, events, None)


def record_missing_roll_bar(state: RolloverStateV2, leg: RollLeg) -> RolloverStateV2:
    if leg == RollLeg.INCOMING_OPEN and state.status == RollStatus.FLAT_AWAITING_INCOMING: return state
    if leg != RollLeg.OUTGOING_CLOSE or state.status not in (RollStatus.PENDING_OUTGOING, RollStatus.OUTGOING_PARTIAL):
        raise Phase6Error(Phase6Reason.INCOMPLETE_ROLL, "missing bar does not match active leg")
    sid = canonical_fingerprint(state.schema_version, state.specification, RollStatus.FAILED_OUTGOING,
        state.outgoing_filled, state.incoming_filled, False, state.events, Phase6Reason.MISSING_OUTGOING_BAR)
    return RolloverStateV2(state.schema_version, sid, state.specification, RollStatus.FAILED_OUTGOING,
        state.outgoing_filled, state.incoming_filled, False, state.events, Phase6Reason.MISSING_OUTGOING_BAR)


@dataclass(frozen=True, slots=True)
class FundingRequirementV2:
    schema_version: str
    requirement_id: str
    run_id: str
    market: str
    instrument_id: str
    contract_id: str
    funding_time: datetime
    latest_available_at: datetime
    contract_basis: str
    contract_multiplier: Decimal
    instrument_specification_id: str
    funding_version: str
    fact_source_version: str
    source_ids: tuple[str, ...]

    @classmethod
    def create(cls, **v) -> "FundingRequirementV2":
        names = ("run_id", "market", "instrument_id", "contract_id", "funding_time",
                 "latest_available_at", "contract_basis", "contract_multiplier",
                 "instrument_specification_id", "funding_version", "fact_source_version", "source_ids")
        rid = canonical_fingerprint("funding-requirement-v2-1", *(v[n] for n in names))
        return cls("funding-requirement-v2-1", rid, **v)

    def __post_init__(self) -> None:
        if self.schema_version != "funding-requirement-v2-1" or self.funding_version != PHASE6_VERSION: raise ValueError("unsupported funding requirement")
        for n in ("requirement_id", "run_id", "instrument_specification_id"): _sha(getattr(self, n), n)
        for n in ("market", "instrument_id", "contract_id", "contract_basis", "funding_version", "fact_source_version"): _text(getattr(self, n), n)
        _utc(self.funding_time, "funding_time"); _utc(self.latest_available_at, "latest_available_at")
        if self.latest_available_at < self.funding_time: raise ValueError("funding availability boundary invalid")
        _positive(self.contract_multiplier, "contract_multiplier")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)): raise ValueError("funding requirement needs unique sources")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.market, self.instrument_id,
            self.contract_id, self.funding_time, self.latest_available_at, self.contract_basis,
            self.contract_multiplier, self.instrument_specification_id, self.funding_version,
            self.fact_source_version, self.source_ids)
        if expected != self.requirement_id: raise ValueError("funding requirement identity mismatch")


@dataclass(frozen=True, slots=True)
class FundingApplicationV2:
    schema_version: str
    application_id: str
    requirement_id: str
    funding_id: str
    accounting_event: AccountingEventV2
    signed_quantity: Decimal
    expected_payment: Decimal
    accounting_snapshot_id: str
    funding_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "funding-application-v2-1" or self.funding_version != PHASE6_VERSION: raise ValueError("unsupported funding application")
        for n in ("application_id", "requirement_id", "funding_id", "accounting_snapshot_id"): _sha(getattr(self, n), n)
        _finite_decimal(self.signed_quantity, "signed_quantity"); _finite_decimal(self.expected_payment, "expected_payment")
        expected = canonical_fingerprint(self.schema_version, self.requirement_id, self.funding_id,
            self.accounting_event, self.signed_quantity, self.expected_payment,
            self.accounting_snapshot_id, self.funding_version)
        if expected != self.application_id: raise ValueError("funding application identity mismatch")


def prepare_funding_application(*, requirement: FundingRequirementV2, fact: FundingFactV2 | None,
                                snapshot: AccountingSnapshotPhase4V2,
                                instrument: InstrumentSpecificationV2,
                                perpetual_capability_enabled: bool) -> FundingApplicationV2:
    if fact is None: raise Phase6Error(Phase6Reason.MISSING_FUNDING_FACT, "authoritative funding fact required")
    if instrument.profile != InstrumentProfile.BTC_LINEAR_PERPETUAL or not perpetual_capability_enabled:
        raise Phase6Error(Phase6Reason.FUNDING_NOT_SUPPORTED, "funding is capability-gated perpetual only")
    if snapshot.accounting_version != ACCOUNTING_VERSION: raise Phase6Error(Phase6Reason.VERSION_MISMATCH, "accounting version differs")
    identity = (requirement.market, requirement.instrument_id, requirement.contract_id)
    if _identity(instrument) != identity or _identity(snapshot) != identity or _identity(fact) != identity:
        raise Phase6Error(Phase6Reason.IDENTITY_MISMATCH, "funding identities differ")
    if requirement.instrument_specification_id != instrument.specification_id or requirement.contract_multiplier != instrument.contract_multiplier:
        raise Phase6Error(Phase6Reason.VERSION_MISMATCH, "funding contract basis/multiplier lineage differs")
    if fact.funding_time != requirement.funding_time: raise Phase6Error(Phase6Reason.STALE_FUNDING_FACT, "funding timestamp differs")
    if fact.source_version != requirement.fact_source_version: raise Phase6Error(Phase6Reason.VERSION_MISMATCH, "funding source version differs")
    if fact.available_at > requirement.latest_available_at: raise Phase6Error(Phase6Reason.LATE_FUNDING_FACT, "funding fact arrived after boundary")
    if snapshot.as_of > requirement.funding_time: raise Phase6Error(Phase6Reason.EVENT_TIME_REGRESSION, "snapshot already crossed funding boundary")
    expected_payment = -snapshot.position.signed_quantity * fact.mark_price * requirement.contract_multiplier * fact.rate
    event_id = canonical_fingerprint("accounting-event-v2-1", requirement.requirement_id,
                                     fact.funding_id, fact.funding_time, fact.available_at)
    event = AccountingEventV2("accounting-event-v2-1", event_id, AccountingEventKind.FUNDING,
                              fact.funding_time, fact.available_at, funding=fact)
    aid = canonical_fingerprint("funding-application-v2-1", requirement.requirement_id,
        fact.funding_id, event, snapshot.position.signed_quantity, expected_payment,
        snapshot.snapshot_id, requirement.funding_version)
    return FundingApplicationV2("funding-application-v2-1", aid, requirement.requirement_id,
        fact.funding_id, event, snapshot.position.signed_quantity, expected_payment,
        snapshot.snapshot_id, requirement.funding_version)


@dataclass(frozen=True, slots=True)
class Phase6EventV2:
    schema_version: str
    event_id: str
    economic_id: str
    kind: Phase6EventKind
    event_time: datetime
    payload_id: str

    @classmethod
    def create(cls, *, economic_id: str, kind: Phase6EventKind, event_time: datetime,
               payload_id: str) -> "Phase6EventV2":
        eid = canonical_fingerprint("phase6-event-v2-1", economic_id, kind, event_time, payload_id)
        return cls("phase6-event-v2-1", eid, economic_id, kind, event_time, payload_id)

    def __post_init__(self) -> None:
        if self.schema_version != "phase6-event-v2-1": raise ValueError("unsupported phase6 event")
        for n in ("event_id", "economic_id", "payload_id"): _sha(getattr(self, n), n)
        _utc(self.event_time, "event_time")
        expected = canonical_fingerprint(self.schema_version, self.economic_id,
                                         self.kind, self.event_time, self.payload_id)
        if expected != self.event_id: raise ValueError("phase6 event identity mismatch")


@dataclass(frozen=True, slots=True)
class Phase6LedgerV2:
    schema_version: str
    run_id: str
    events: tuple[Phase6EventV2, ...]
    ledger_fingerprint: str

    @classmethod
    def create(cls, run_id: str) -> "Phase6LedgerV2":
        _sha(run_id, "run_id"); fp = canonical_fingerprint("phase6-ledger-v2-1", run_id, ())
        return cls("phase6-ledger-v2-1", run_id, (), fp)

    def verify_integrity(self) -> None:
        if self.ledger_fingerprint != canonical_fingerprint(self.schema_version, self.run_id, self.events):
            raise Phase6Error(Phase6Reason.CHECKPOINT_TAMPERED, "phase6 ledger fingerprint differs")

    def apply(self, event: Phase6EventV2) -> "Phase6LedgerV2":
        self.verify_integrity(); by_id = {x.event_id: x for x in self.events}
        if event.event_id in by_id:
            if by_id[event.event_id] == event: return self
            raise Phase6Error(Phase6Reason.DUPLICATE_EVENT_CONFLICT, "event identity reused")
        if event.economic_id in {x.economic_id for x in self.events}: raise Phase6Error(Phase6Reason.DUPLICATE_ECONOMIC_EVENT, "economic identity reused")
        if self.events:
            previous = self.events[-1]
            if event.event_time == previous.event_time and _KIND_PRIORITY[event.kind] == _KIND_PRIORITY[previous.kind]:
                raise Phase6Error(Phase6Reason.PRIORITY_AMBIGUITY, "same-time same-priority events require upstream resolution")
            current_key = (event.event_time, int(_KIND_PRIORITY[event.kind]), event.event_id)
            prior_key = (previous.event_time, int(_KIND_PRIORITY[previous.kind]), previous.event_id)
            if current_key < prior_key: raise Phase6Error(Phase6Reason.EVENT_TIME_REGRESSION, "phase6 event order regressed")
        events = self.events + (event,); fp = canonical_fingerprint(self.schema_version, self.run_id, events)
        return replace(self, events=events, ledger_fingerprint=fp)


@dataclass(frozen=True, slots=True)
class Phase6CheckpointV2:
    schema_version: str
    checkpoint_id: str
    ledger_fingerprint: str
    ledger: Phase6LedgerV2

    @classmethod
    def create(cls, ledger: Phase6LedgerV2) -> "Phase6CheckpointV2":
        ledger.verify_integrity(); cid = canonical_fingerprint("phase6-checkpoint-v2-1", ledger.ledger_fingerprint)
        return cls("phase6-checkpoint-v2-1", cid, ledger.ledger_fingerprint, ledger)

    def __post_init__(self) -> None:
        if self.schema_version != "phase6-checkpoint-v2-1": raise ValueError("unsupported checkpoint")
        _sha(self.checkpoint_id, "checkpoint_id"); _sha(self.ledger_fingerprint, "ledger_fingerprint")
        if self.ledger.ledger_fingerprint != self.ledger_fingerprint: raise Phase6Error(Phase6Reason.CHECKPOINT_TAMPERED, "checkpoint differs")
        if self.checkpoint_id != canonical_fingerprint(self.schema_version, self.ledger_fingerprint):
            raise Phase6Error(Phase6Reason.CHECKPOINT_TAMPERED, "checkpoint identity differs")


def funding_boundary_gate(*, snapshot: AccountingSnapshotPhase4V2,
                          requirements: tuple[FundingRequirementV2, ...],
                          applications: tuple[FundingApplicationV2, ...], through: datetime) -> None:
    _utc(through, "through"); applied = {x.requirement_id for x in applications}
    if snapshot.position.signed_quantity:
        missing = [r for r in requirements if snapshot.as_of <= r.funding_time <= through and r.requirement_id not in applied]
        if missing: raise Phase6Error(Phase6Reason.FUNDING_BOUNDARY_MISSED, "held position crossed unapplied funding boundary")


def completed_phase6_gate(*, rolls: tuple[RolloverStateV2, ...],
                          requirements: tuple[FundingRequirementV2, ...],
                          applications: tuple[FundingApplicationV2, ...],
                          snapshot: AccountingSnapshotPhase4V2, through: datetime) -> None:
    if any(r.status != RollStatus.COMPLETE for r in rolls): raise Phase6Error(Phase6Reason.INCOMPLETE_ROLL, "roll remains incomplete")
    try: funding_boundary_gate(snapshot=snapshot, requirements=requirements, applications=applications, through=through)
    except Phase6Error as exc:
        raise Phase6Error(Phase6Reason.INCOMPLETE_FUNDING, exc.detail) from exc


@dataclass(frozen=True, slots=True)
class Phase6ReconciliationV2:
    schema_version: str
    reconciliation_id: str
    run_id: str
    order_ledger_fingerprint: str
    execution_ids: tuple[str, ...]
    accounting_ledger_fingerprint: str
    accounting_snapshot_id: str
    risk_ledger_fingerprint: str
    session_ids: tuple[str, ...]
    roll_state_ids: tuple[str, ...]
    funding_application_ids: tuple[str, ...]
    phase6_ledger_fingerprint: str

    @classmethod
    def create(cls, **v) -> "Phase6ReconciliationV2":
        names = ("run_id", "order_ledger_fingerprint", "execution_ids",
            "accounting_ledger_fingerprint", "accounting_snapshot_id", "risk_ledger_fingerprint",
            "session_ids", "roll_state_ids", "funding_application_ids", "phase6_ledger_fingerprint")
        rid = canonical_fingerprint("phase6-reconciliation-v2-1", *(v[n] for n in names))
        return cls("phase6-reconciliation-v2-1", rid, **v)

    def __post_init__(self) -> None:
        if self.schema_version != "phase6-reconciliation-v2-1": raise ValueError("unsupported reconciliation")
        for n in ("reconciliation_id", "run_id", "order_ledger_fingerprint",
                  "accounting_ledger_fingerprint", "accounting_snapshot_id",
                  "risk_ledger_fingerprint", "phase6_ledger_fingerprint"):
            _sha(getattr(self, n), n)
        for collection in (self.execution_ids, self.session_ids, self.roll_state_ids, self.funding_application_ids):
            if len(collection) != len(set(collection)): raise Phase6Error(Phase6Reason.RECONCILIATION_MISMATCH, "duplicate reconciliation lineage")
        expected = canonical_fingerprint(self.schema_version, self.run_id, self.order_ledger_fingerprint,
            self.execution_ids, self.accounting_ledger_fingerprint, self.accounting_snapshot_id,
            self.risk_ledger_fingerprint, self.session_ids, self.roll_state_ids,
            self.funding_application_ids, self.phase6_ledger_fingerprint)
        if expected != self.reconciliation_id: raise Phase6Error(Phase6Reason.RECONCILIATION_MISMATCH, "reconciliation identity differs")
