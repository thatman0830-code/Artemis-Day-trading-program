"""Deterministic conservative one-minute OHLC execution facts.

Phase 3 consumes immutable Phase 1 instrument facts and a Phase 2 order
ledger.  It owns trigger/touch, adverse price selection and bar-volume
allocation only.  It deliberately does not calculate fees, PnL, margin,
risk decisions, strategy actions, or provider data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from enum import Enum, IntEnum

from .contracts import InstrumentSpecificationV2, OrderSide, OrderState, OrderType, TimeInForce
from .order_ledger import LedgerEventKind, OrderLedgerEventV2, OrderLedgerV2
from .specifications import _finite_decimal, _text, _utc, canonical_fingerprint
from .validation import is_on_grid, validate_order_against_instrument


EXECUTION_POLICY_VERSION = "CONSERVATIVE_OHLC_1M_V1"
LIQUIDITY_POLICY_VERSION = "BAR_VOLUME_PARTICIPATION_V1"


class ExecutionPriority(IntEnum):
    RISK_SESSION_END_LIQUIDATION = 10
    ROLLOVER_OUTGOING_CLOSE = 20
    ORDINARY_POSITION_REDUCING = 30
    STRATEGY_EXIT = 40
    ENTRY_OR_ROLLOVER_INCOMING = 50


class CollisionRole(str, Enum):
    ADVERSE = "ADVERSE"
    FAVORABLE = "FAVORABLE"


class ExecutionReason(str, Enum):
    INVALID_POLICY = "INVALID_POLICY"
    INVALID_BAR = "INVALID_BAR"
    BAR_NOT_FINAL = "BAR_NOT_FINAL"
    BAR_NOT_AVAILABLE = "BAR_NOT_AVAILABLE"
    BAR_INELIGIBLE = "BAR_INELIGIBLE"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    ORDER_NOT_EXECUTABLE = "ORDER_NOT_EXECUTABLE"
    SAME_SOURCE_BAR_INELIGIBLE = "SAME_SOURCE_BAR_INELIGIBLE"
    SOURCE_LINEAGE_UNPROVEN = "SOURCE_LINEAGE_UNPROVEN"
    MISSING_VOLUME = "MISSING_VOLUME"
    AMBIGUOUS_INTRABAR_REJECTED = "AMBIGUOUS_INTRABAR_REJECTED"
    INVALID_COLLISION_GROUP = "INVALID_COLLISION_GROUP"
    DUPLICATE_IDENTITY_CONFLICT = "DUPLICATE_IDENTITY_CONFLICT"


class OHLCExecutionError(ValueError):
    def __init__(self, reason: ExecutionReason, detail: str):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}")


def _sha(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{field} must be lowercase SHA-256")


def _positive(value: Decimal, field: str) -> None:
    _finite_decimal(value, field)
    if value <= 0:
        raise ValueError(f"{field} must be positive")


def _nonnegative(value: Decimal, field: str) -> None:
    _finite_decimal(value, field)
    if value < 0:
        raise ValueError(f"{field} must be nonnegative")


@dataclass(frozen=True, slots=True)
class OHLCBarV2:
    schema_version: str
    bar_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    open_time: datetime
    close_time: datetime
    available_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    finalized: bool
    session_eligible: bool
    data_quality_valid: bool
    contract_eligible: bool
    source_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "ohlc-bar-v2-1":
            raise ValueError("unsupported OHLC bar schema_version")
        _sha(self.bar_id, "bar_id")
        for name in ("market", "instrument_id", "source_version"):
            _text(getattr(self, name), name)
        if self.contract_id is not None:
            _text(self.contract_id, "contract_id")
        for name in ("open_time", "close_time", "available_at"):
            _utc(getattr(self, name), name)
        if self.open_time >= self.close_time or self.available_at < self.close_time:
            raise ValueError("bar chronology is invalid")
        if self.close_time - self.open_time != timedelta(minutes=1) or any(
                value.second != 0 or value.microsecond != 0
                for value in (self.open_time, self.close_time)):
            raise ValueError("execution bars must use aligned one-minute intervals")
        for name in ("open", "high", "low", "close"):
            _positive(getattr(self, name), name)
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.high < self.low:
            raise ValueError("OHLC geometry is invalid")
        if self.volume is not None:
            _nonnegative(self.volume, "volume")


@dataclass(frozen=True, slots=True)
class ExecutionPolicyV2:
    schema_version: str
    policy_id: str
    execution_policy_version: str
    liquidity_policy_version: str
    maximum_participation_rate: Decimal
    assumption_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "ohlc-execution-policy-v2-1":
            raise ValueError("unsupported execution policy schema_version")
        _sha(self.policy_id, "policy_id")
        if self.execution_policy_version != EXECUTION_POLICY_VERSION:
            raise ValueError("unsupported execution policy")
        if self.liquidity_policy_version != LIQUIDITY_POLICY_VERSION:
            raise ValueError("unsupported liquidity policy")
        _text(self.assumption_version, "assumption_version")
        _positive(self.maximum_participation_rate, "maximum_participation_rate")
        if self.maximum_participation_rate > 1:
            raise ValueError("maximum_participation_rate cannot exceed one")


@dataclass(frozen=True, slots=True)
class ExecutionSourceLineageV2:
    """Cryptographic binding from a finalized source bar to ledger activation."""

    schema_version: str
    lineage_id: str
    source_bar: OHLCBarV2
    action_id: str
    order_id: str
    activation_event_id: str
    activation_event_time: datetime

    @classmethod
    def create(cls, *, source_bar: OHLCBarV2, action_id: str, order_id: str,
               activation_event_id: str, activation_event_time: datetime) -> "ExecutionSourceLineageV2":
        lineage_id = canonical_fingerprint("execution-source-lineage-v2-1", source_bar,
            action_id, order_id, activation_event_id, activation_event_time)
        return cls("execution-source-lineage-v2-1", lineage_id, source_bar, action_id,
                   order_id, activation_event_id, activation_event_time)

    def __post_init__(self) -> None:
        if self.schema_version != "execution-source-lineage-v2-1":
            raise ValueError("unsupported execution source lineage schema_version")
        for name in ("lineage_id", "action_id", "order_id", "activation_event_id"):
            _sha(getattr(self, name), name)
        _utc(self.activation_event_time, "activation_event_time")
        if not self.source_bar.finalized:
            raise ValueError("execution source bar must be finalized")
        expected = canonical_fingerprint(self.schema_version, self.source_bar, self.action_id,
            self.order_id, self.activation_event_id, self.activation_event_time)
        if self.lineage_id != expected:
            raise ValueError("execution source lineage fingerprint mismatch")


@dataclass(frozen=True, slots=True)
class ExecutionInstructionV2:
    schema_version: str
    instruction_id: str
    order_id: str
    priority: ExecutionPriority
    participation_rate: Decimal
    slippage_ticks: Decimal
    assumption_version: str
    source_lineage: ExecutionSourceLineageV2 | None = None

    def __post_init__(self) -> None:
        if self.schema_version != "execution-instruction-v2-1":
            raise ValueError("unsupported execution instruction schema_version")
        _sha(self.instruction_id, "instruction_id")
        _sha(self.order_id, "order_id")
        if not isinstance(self.priority, ExecutionPriority):
            raise ValueError("priority must be ExecutionPriority")
        _positive(self.participation_rate, "participation_rate")
        if self.participation_rate > 1:
            raise ValueError("participation_rate cannot exceed one")
        _nonnegative(self.slippage_ticks, "slippage_ticks")
        _text(self.assumption_version, "assumption_version")
        if self.source_lineage is not None and not isinstance(self.source_lineage, ExecutionSourceLineageV2):
            raise ValueError("source_lineage must be ExecutionSourceLineageV2")


@dataclass(frozen=True, slots=True)
class CollisionGroupV2:
    schema_version: str
    collision_group_id: str
    adverse_order_id: str
    favorable_order_id: str
    ownership_declared: bool = True

    def __post_init__(self) -> None:
        if self.schema_version != "collision-group-v2-1":
            raise ValueError("unsupported collision group schema_version")
        for name in ("collision_group_id", "adverse_order_id", "favorable_order_id"):
            _sha(getattr(self, name), name)
        if self.adverse_order_id == self.favorable_order_id:
            raise ValueError("collision orders must be distinct")
        if not isinstance(self.ownership_declared, bool):
            raise ValueError("ownership_declared must be bool")


@dataclass(frozen=True, slots=True)
class ExecutionFillV2:
    schema_version: str
    fill_id: str
    order_id: str
    market_event_id: str
    trigger_market_event_id: str | None
    market: str
    instrument_id: str
    contract_id: str | None
    fill_time: datetime
    side: OrderSide
    quantity: Decimal
    reference_price: Decimal
    unrounded_economic_price: Decimal
    economic_price: Decimal
    adverse_friction: Decimal
    bar_volume: Decimal
    bar_available_quantity: Decimal
    order_participation_cap: Decimal
    execution_rule_code: str
    execution_policy_version: str
    liquidity_policy_version: str
    assumption_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "execution-fill-v2-1":
            raise ValueError("unsupported execution fill schema_version")
        for name in ("fill_id", "order_id", "market_event_id"):
            _sha(getattr(self, name), name)
        if self.trigger_market_event_id is not None:
            _sha(self.trigger_market_event_id, "trigger_market_event_id")
        for name in ("market", "instrument_id", "execution_rule_code",
                     "execution_policy_version", "liquidity_policy_version", "assumption_version"):
            _text(getattr(self, name), name)
        _utc(self.fill_time, "fill_time")
        if not isinstance(self.side, OrderSide):
            raise ValueError("side must be OrderSide")
        for name in ("quantity", "reference_price", "unrounded_economic_price", "economic_price"):
            _positive(getattr(self, name), name)
        for name in ("adverse_friction", "bar_volume", "bar_available_quantity", "order_participation_cap"):
            _nonnegative(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class ExecutionEvaluationV2:
    schema_version: str
    evaluation_id: str
    evaluated_at: datetime
    input_ledger_fingerprint: str
    output_ledger_fingerprint: str
    bar_id: str
    policy_id: str
    trigger_event_ids: tuple[str, ...]
    fill_event_ids: tuple[str, ...]
    evaluation_event_ids: tuple[str, ...]
    fills: tuple[ExecutionFillV2, ...]
    suppressed_favorable_order_ids: tuple[str, ...]
    initial_bar_budget: Decimal
    consumed_bar_budget: Decimal
    remaining_bar_budget: Decimal
    output_ledger: OrderLedgerV2

    def __post_init__(self) -> None:
        if self.schema_version != "ohlc-execution-evaluation-v2-1":
            raise ValueError("unsupported evaluation schema_version")
        for name in ("evaluation_id", "input_ledger_fingerprint", "output_ledger_fingerprint",
                     "bar_id", "policy_id"):
            _sha(getattr(self, name), name)
        _utc(self.evaluated_at, "evaluated_at")
        for values in (self.trigger_event_ids, self.fill_event_ids, self.evaluation_event_ids,
                       self.suppressed_favorable_order_ids):
            if len(values) != len(set(values)):
                raise ValueError("evaluation identities must be unique")
        for name in ("initial_bar_budget", "consumed_bar_budget", "remaining_bar_budget"):
            _nonnegative(getattr(self, name), name)
        if self.initial_bar_budget != self.consumed_bar_budget + self.remaining_bar_budget:
            raise ValueError("bar budget does not reconcile")
        if self.output_ledger.ledger_fingerprint != self.output_ledger_fingerprint:
            raise ValueError("output ledger fingerprint mismatch")


def _floor_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def _adverse_round(value: Decimal, tick: Decimal, side: OrderSide) -> Decimal:
    rounding = ROUND_CEILING if side == OrderSide.BUY else ROUND_FLOOR
    return (value / tick).to_integral_value(rounding=rounding) * tick


def _event_id(kind: LedgerEventKind, order_id: str, bar_id: str, rule: str) -> str:
    return canonical_fingerprint("phase3-ledger-event-v2-1", kind, order_id, bar_id, rule)


def _event(ledger: OrderLedgerV2, *, snapshot, kind: LedgerEventKind, bar: OHLCBarV2,
           rule: str, fill_quantity: Decimal | None = None) -> OrderLedgerEventV2:
    return OrderLedgerEventV2("order-ledger-event-v2-1",
        _event_id(kind, snapshot.intent.order_id, bar.bar_id, rule), snapshot.intent.order_id,
        kind, bar.available_at, len(ledger.events) + 1, snapshot.order_version,
        snapshot.intent.market, snapshot.intent.instrument_id, snapshot.intent.contract_id,
        bar.bar_id, rule, fill_quantity=fill_quantity,
        contract_eligibility_verified=bar.contract_eligible)


def _trigger_market_event_id(ledger: OrderLedgerV2, order_id: str) -> str | None:
    triggers = tuple(event.source_event_id for event in ledger.events
                     if event.order_id == order_id and event.kind == LedgerEventKind.TRIGGER)
    if len(triggers) > 1:
        raise OHLCExecutionError(ExecutionReason.DUPLICATE_IDENTITY_CONFLICT,
                                 "order has conflicting trigger lineage")
    return triggers[0] if triggers else None


def _touch(snapshot, bar: OHLCBarV2) -> tuple[bool, bool, Decimal | None, str | None]:
    """Return trigger, fill candidate, reference price and rule."""
    intent = snapshot.intent
    buy = intent.side == OrderSide.BUY
    if intent.order_type == OrderType.MARKET:
        return False, True, bar.open, "MARKET_NEXT_ELIGIBLE_OPEN"
    if intent.order_type == OrderType.LIMIT:
        touched = bar.low <= intent.limit_price if buy else bar.high >= intent.limit_price
        return False, touched, intent.limit_price if touched else None, "LIMIT_AT_FROZEN_PRICE" if touched else None
    if intent.order_type == OrderType.STOP_MARKET:
        if snapshot.triggered:
            return False, True, bar.open, "STOP_MARKET_TRIGGERED_NEXT_OPEN"
        gap = bar.open >= intent.stop_price if buy else bar.open <= intent.stop_price
        touched = bar.high >= intent.stop_price if buy else bar.low <= intent.stop_price
        if not touched:
            return False, False, None, None
        return True, True, bar.open if gap else intent.stop_price, (
            "STOP_MARKET_GAP_OPEN" if gap else "STOP_MARKET_THRESHOLD")
    if intent.order_type == OrderType.STOP_LIMIT:
        if not snapshot.triggered:
            touched = bar.high >= intent.stop_price if buy else bar.low <= intent.stop_price
            return touched, False, None, "STOP_LIMIT_TRIGGER" if touched else None
        touched = bar.low <= intent.limit_price if buy else bar.high >= intent.limit_price
        return False, touched, intent.limit_price if touched else None, (
            "STOP_LIMIT_LATER_BAR_LIMIT" if touched else None)
    raise OHLCExecutionError(ExecutionReason.ORDER_NOT_EXECUTABLE, "unsupported order type")


def evaluate_bar(*, ledger: OrderLedgerV2, bar: OHLCBarV2, evaluated_at: datetime,
                 instrument: InstrumentSpecificationV2, policy: ExecutionPolicyV2,
                 instructions: tuple[ExecutionInstructionV2, ...],
                 collision_groups: tuple[CollisionGroupV2, ...] = ()) -> ExecutionEvaluationV2:
    """Evaluate one finalized bar and return immutable execution facts and a new ledger."""
    _utc(evaluated_at, "evaluated_at")
    ledger.verify_integrity()
    if evaluated_at < bar.available_at:
        raise OHLCExecutionError(ExecutionReason.BAR_NOT_AVAILABLE, "bar is not yet visible")
    if not bar.finalized:
        raise OHLCExecutionError(ExecutionReason.BAR_NOT_FINAL, "forming bar is ineligible")
    if not (bar.session_eligible and bar.data_quality_valid and bar.contract_eligible):
        raise OHLCExecutionError(ExecutionReason.BAR_INELIGIBLE, "session, data, or contract is ineligible")
    if (bar.market, bar.instrument_id, bar.contract_id) != (
            instrument.market, instrument.instrument_id, instrument.contract_id):
        raise OHLCExecutionError(ExecutionReason.IDENTITY_MISMATCH, "bar and instrument identity differ")
    if not (instrument.effective_from <= bar.open_time and
            (instrument.effective_to is None or bar.close_time <= instrument.effective_to)):
        raise OHLCExecutionError(ExecutionReason.IDENTITY_MISMATCH, "bar is outside instrument validity")
    if policy.execution_policy_version != EXECUTION_POLICY_VERSION:
        raise OHLCExecutionError(ExecutionReason.VERSION_MISMATCH, "execution policy version mismatch")
    if bar.volume is None:
        raise OHLCExecutionError(ExecutionReason.MISSING_VOLUME, "participation requires exact bar volume")
    if any(not is_on_grid(value, instrument.tick_size) for value in (bar.open, bar.high, bar.low, bar.close)):
        raise OHLCExecutionError(ExecutionReason.INVALID_BAR, "bar prices are off tick grid")

    instruction_by_order = {item.order_id: item for item in instructions}
    if len(instruction_by_order) != len(instructions):
        raise OHLCExecutionError(ExecutionReason.DUPLICATE_IDENTITY_CONFLICT, "duplicate instruction order")
    if any(item.participation_rate > policy.maximum_participation_rate for item in instructions):
        raise OHLCExecutionError(ExecutionReason.INVALID_POLICY, "instruction exceeds global participation")
    candidates = []
    for instruction in instructions:
        snapshot = ledger.order(instruction.order_id)
        intent = snapshot.intent
        if intent.execution_policy_version != policy.execution_policy_version or instruction.assumption_version != policy.assumption_version:
            raise OHLCExecutionError(ExecutionReason.VERSION_MISMATCH, "order/instruction policy lineage differs")
        if (intent.market, intent.instrument_id, intent.contract_id) != (
                bar.market, bar.instrument_id, bar.contract_id):
            raise OHLCExecutionError(ExecutionReason.IDENTITY_MISMATCH, "order and bar identity differ")
        lineage = instruction.source_lineage
        if lineage is None:
            raise OHLCExecutionError(ExecutionReason.SOURCE_LINEAGE_UNPROVEN,
                                     "execution instruction lacks source-bar lineage")
        source = lineage.source_bar
        if (lineage.order_id, lineage.action_id) != (intent.order_id, intent.action_id):
            raise OHLCExecutionError(ExecutionReason.SOURCE_LINEAGE_UNPROVEN,
                                     "source lineage order/action identity differs")
        if (source.market, source.instrument_id, source.contract_id, source.source_version) != (
                bar.market, bar.instrument_id, bar.contract_id, bar.source_version):
            raise OHLCExecutionError(ExecutionReason.SOURCE_LINEAGE_UNPROVEN,
                                     "source and evaluated bar lineage differs")
        activations = tuple(event for event in ledger.events if event.order_id == intent.order_id and
                            event.kind == LedgerEventKind.ACTIVATE)
        if len(activations) != 1 or (activations[0].event_id, activations[0].event_time) != (
                lineage.activation_event_id, lineage.activation_event_time):
            raise OHLCExecutionError(ExecutionReason.SOURCE_LINEAGE_UNPROVEN,
                                     "ledger activation is not bound to source lineage")
        if source.bar_id == bar.bar_id:
            raise OHLCExecutionError(ExecutionReason.SAME_SOURCE_BAR_INELIGIBLE,
                                     "source bar cannot execute its derived order")
        if lineage.activation_event_time < intent.activation_at or intent.submitted_at < source.available_at:
            raise OHLCExecutionError(ExecutionReason.SOURCE_LINEAGE_UNPROVEN,
                                     "order chronology precedes its source availability")
        if source.available_at > bar.open_time or source.close_time > bar.open_time:
            raise OHLCExecutionError(ExecutionReason.SOURCE_LINEAGE_UNPROVEN,
                                     "source information was unavailable before evaluated bar")
        report = validate_order_against_instrument(intent, instrument)
        if not report.valid:
            raise OHLCExecutionError(ExecutionReason.IDENTITY_MISMATCH, report.issues[0].detail)
        if snapshot.state not in (OrderState.ACTIVE, OrderState.TRIGGERED, OrderState.PARTIALLY_FILLED):
            raise OHLCExecutionError(ExecutionReason.ORDER_NOT_EXECUTABLE, "instruction order is not executable")
        if intent.activation_at > bar.open_time:
            raise OHLCExecutionError(ExecutionReason.SAME_SOURCE_BAR_INELIGIBLE,
                                     "order is not active at the bar open")
        trigger, fillable, reference, rule = _touch(snapshot, bar)
        candidates.append((instruction, snapshot, trigger, fillable, reference, rule))

    suppressed: set[str] = set()
    candidate_ids = {snapshot.intent.order_id for _, snapshot, _, fillable, _, _ in candidates if fillable}
    seen_collision_orders: set[str] = set()
    for group in collision_groups:
        if group.adverse_order_id in seen_collision_orders or group.favorable_order_id in seen_collision_orders:
            raise OHLCExecutionError(ExecutionReason.INVALID_COLLISION_GROUP, "order belongs to multiple collision groups")
        seen_collision_orders.update((group.adverse_order_id, group.favorable_order_id))
        if group.adverse_order_id not in instruction_by_order or group.favorable_order_id not in instruction_by_order:
            raise OHLCExecutionError(ExecutionReason.INVALID_COLLISION_GROUP, "collision order instruction is missing")
        adverse = ledger.order(group.adverse_order_id).intent
        favorable = ledger.order(group.favorable_order_id).intent
        if (adverse.market, adverse.instrument_id, adverse.contract_id) != (
                favorable.market, favorable.instrument_id, favorable.contract_id):
            raise OHLCExecutionError(ExecutionReason.INVALID_COLLISION_GROUP, "collision identities differ")
        if group.adverse_order_id in candidate_ids and group.favorable_order_id in candidate_ids:
            if not group.ownership_declared:
                raise OHLCExecutionError(ExecutionReason.AMBIGUOUS_INTRABAR_REJECTED,
                                         "collision has no declared adverse owner")
            suppressed.add(group.favorable_order_id)

    working = ledger
    trigger_events = []
    trigger_candidates = sorted((item for item in candidates if item[2]),
                                key=lambda item: _event_id(LedgerEventKind.TRIGGER,
                                    item[1].intent.order_id, bar.bar_id, item[5]))
    for instruction, old_snapshot, _, _, _, rule in trigger_candidates:
        snapshot = working.order(old_snapshot.intent.order_id)
        event = _event(working, snapshot=snapshot, kind=LedgerEventKind.TRIGGER, bar=bar, rule=rule)
        working = working.apply(event)
        trigger_events.append(event.event_id)

    initial_budget = _floor_step(bar.volume * policy.maximum_participation_rate,
                                 instrument.quantity_step)
    remaining_budget = initial_budget
    fills: list[ExecutionFillV2] = []
    fill_events = []
    evaluation_events = []
    pending_events: list[tuple[str, LedgerEventKind, str, str, Decimal | None]] = []
    fill_candidates = sorted((item for item in candidates if item[3] and
                              item[1].intent.order_id not in suppressed and
                              not (item[1].intent.order_type == OrderType.STOP_LIMIT and item[2])),
                             key=lambda item: (int(item[0].priority),
                                               item[1].intent.activation_at,
                                               item[1].intent.submitted_at,
                                               item[1].intent.order_id))
    for instruction, old_snapshot, _, _, reference, rule in fill_candidates:
        snapshot = working.order(old_snapshot.intent.order_id)
        order_cap = _floor_step(bar.volume * instruction.participation_rate,
                                instrument.quantity_step)
        quantity = min(snapshot.remaining_quantity, order_cap, remaining_budget)
        quantity = _floor_step(quantity, instrument.quantity_step)
        if quantity <= 0:
            continue
        slip = instruction.slippage_ticks * instrument.tick_size
        if snapshot.intent.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
            unrounded = reference
            economic = reference
        else:
            unrounded = reference + slip if snapshot.intent.side == OrderSide.BUY else reference - slip
            economic = _adverse_round(unrounded, instrument.tick_size, snapshot.intent.side)
        friction = economic - reference if snapshot.intent.side == OrderSide.BUY else reference - economic
        fill_id = canonical_fingerprint("execution-fill-v2-1", snapshot.intent.order_id, bar.bar_id,
            quantity, reference, unrounded, economic, rule, policy.policy_id, instruction.instruction_id)
        fill = ExecutionFillV2("execution-fill-v2-1", fill_id, snapshot.intent.order_id,
            bar.bar_id, _trigger_market_event_id(working, snapshot.intent.order_id),
            bar.market, bar.instrument_id,
            bar.contract_id, bar.available_at, snapshot.intent.side, quantity, reference,
            unrounded, economic, friction, bar.volume, initial_budget, order_cap, rule,
            policy.execution_policy_version, policy.liquidity_policy_version,
            policy.assumption_version)
        event_id = _event_id(LedgerEventKind.FILL, snapshot.intent.order_id, bar.bar_id, rule)
        pending_events.append((event_id, LedgerEventKind.FILL, snapshot.intent.order_id, rule, quantity))
        fills.append(fill); remaining_budget -= quantity

    allocated_order_ids = {fill.order_id for fill in fills}
    for instruction, old_snapshot, _, _, _, _ in candidates:
        current = working.order(old_snapshot.intent.order_id)
        if (current.intent.time_in_force == TimeInForce.IOC and not current.ioc_evaluated and
                current.state in (OrderState.ACTIVE, OrderState.TRIGGERED) and
                current.intent.order_id not in allocated_order_ids):
            rule = "IOC_FIRST_ELIGIBLE_BAR_NO_FILL"
            event_id = _event_id(LedgerEventKind.EXECUTION_EVALUATED,
                                 current.intent.order_id, bar.bar_id, rule)
            pending_events.append((event_id, LedgerEventKind.EXECUTION_EVALUATED,
                                   current.intent.order_id, rule, None))

    # Phase 2 freezes equal-time ledger ordering by kind priority then event ID.
    # Allocation occurred above in execution priority order; ingestion is lexical
    # and cannot change the already-frozen quantities.
    for _, kind, order_id, rule, quantity in sorted(pending_events, key=lambda item: item[0]):
        snapshot = working.order(order_id)
        event = _event(working, snapshot=snapshot, kind=kind, bar=bar,
                       rule=rule, fill_quantity=quantity)
        working = working.apply(event)
        if kind == LedgerEventKind.FILL:
            fill_events.append(event.event_id)
        else:
            evaluation_events.append(event.event_id)

    consumed = initial_budget - remaining_budget
    evaluation_id = canonical_fingerprint("ohlc-execution-evaluation-v2-1", ledger.ledger_fingerprint,
        working.ledger_fingerprint, bar, policy, instructions, collision_groups, tuple(fills),
        tuple(sorted(suppressed)), initial_budget, consumed)
    return ExecutionEvaluationV2("ohlc-execution-evaluation-v2-1", evaluation_id, evaluated_at,
        ledger.ledger_fingerprint, working.ledger_fingerprint, bar.bar_id, policy.policy_id,
        tuple(trigger_events), tuple(fill_events), tuple(evaluation_events), tuple(fills),
        tuple(sorted(suppressed)), initial_budget, consumed, remaining_budget, working)
