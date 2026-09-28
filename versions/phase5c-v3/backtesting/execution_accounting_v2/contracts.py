"""Immutable v2 Phase 1 ledger contracts.

These records describe facts.  They do not perform lifecycle transitions,
matching, fills, accounting, risk actions, or liquidation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .specifications import InstrumentProfile, _finite_decimal, _text, _utc


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


def _enum(value, expected, field: str) -> None:
    if not isinstance(value, expected):
        raise ValueError(f"{field} must be {expected.__name__}")


class EvidenceClass(str, Enum):
    AUTHORITATIVE_FACT = "AUTHORITATIVE_FACT"
    OWNER_ASSUMPTION = "OWNER_ASSUMPTION"
    HISTORICAL_OBSERVATION = "HISTORICAL_OBSERVATION"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"


class OrderState(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REPLACED = "REPLACED"


class RiskPhase(str, Enum):
    PRE_TRADE = "PRE_TRADE"
    POST_EVENT = "POST_EVENT"
    SESSION = "SESSION"
    DATA_QUALITY = "DATA_QUALITY"
    ROLLOVER = "ROLLOVER"


class RiskDecision(str, Enum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    HALT = "HALT"
    FORCE_REDUCE = "FORCE_REDUCE"
    FORCE_FLATTEN = "FORCE_FLATTEN"


@dataclass(frozen=True, slots=True)
class InstrumentSpecificationV2:
    schema_version: str
    specification_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    profile: InstrumentProfile
    currency: str
    tick_size: Decimal
    quantity_step: Decimal
    contract_multiplier: Decimal
    point_value: Decimal | None
    effective_from: datetime
    effective_to: datetime | None
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "instrument-spec-v2-1":
            raise ValueError("unsupported instrument schema_version")
        _sha(self.specification_id, "specification_id")
        for name in ("market", "instrument_id", "currency"):
            _text(getattr(self, name), name)
        if self.contract_id is not None:
            _text(self.contract_id, "contract_id")
        _enum(self.profile, InstrumentProfile, "profile")
        for name in ("tick_size", "quantity_step", "contract_multiplier"):
            _positive(getattr(self, name), name)
        if self.point_value is not None:
            _positive(self.point_value, "point_value")
        _utc(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _utc(self.effective_to, "effective_to")
            if self.effective_to <= self.effective_from:
                raise ValueError("instrument effective interval must be non-empty")
        if not self.evidence_ids or len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("instrument evidence_ids must be non-empty and unique")


@dataclass(frozen=True, slots=True)
class OwnerAssumptionV2:
    schema_version: str
    assumption_id: str
    assumption_type: str
    market: str
    instrument_id: str
    effective_from: datetime
    effective_to: datetime | None
    decimal_values: tuple[tuple[str, Decimal], ...]
    owner_approved: bool
    synthetic_test_only: bool
    decision_reference: str

    def __post_init__(self) -> None:
        if self.schema_version != "owner-assumption-v2-1":
            raise ValueError("unsupported owner assumption schema_version")
        _sha(self.assumption_id, "assumption_id")
        for name in ("assumption_type", "market", "instrument_id", "decision_reference"):
            _text(getattr(self, name), name)
        _utc(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _utc(self.effective_to, "effective_to")
            if self.effective_to <= self.effective_from:
                raise ValueError("assumption effective interval must be non-empty")
        names = tuple(name for name, _ in self.decimal_values)
        if not names or names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("decimal_values must be uniquely and lexically ordered")
        for name, value in self.decimal_values:
            _text(name, "decimal value name")
            _finite_decimal(value, name)
        if self.synthetic_test_only and self.owner_approved:
            raise ValueError("synthetic assumption cannot be production approved")


@dataclass(frozen=True, slots=True)
class CapabilityDeclarationV2:
    schema_version: str
    declaration_id: str
    profile: InstrumentProfile
    market: str
    instrument_id: str
    supported_order_types: tuple[OrderType, ...]
    required_data_fields: tuple[str, ...]
    specification_ids: tuple[str, ...]
    production_eligible: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "capability-declaration-v2-1":
            raise ValueError("unsupported capability schema_version")
        _sha(self.declaration_id, "declaration_id")
        _text(self.market, "market")
        _text(self.instrument_id, "instrument_id")
        for values, name in ((self.supported_order_types, "supported_order_types"),
                             (self.required_data_fields, "required_data_fields"),
                             (self.specification_ids, "specification_ids"),
                             (self.reason_codes, "reason_codes")):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        _enum(self.profile, InstrumentProfile, "profile")
        if any(not isinstance(item, OrderType) for item in self.supported_order_types):
            raise ValueError("supported_order_types must contain OrderType values")
        if self.production_eligible and self.reason_codes:
            raise ValueError("eligible capability cannot contain blocking reasons")


@dataclass(frozen=True, slots=True)
class OrderIntentV2:
    schema_version: str
    order_id: str
    run_id: str
    action_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    side: OrderSide
    quantity: Decimal
    order_type: OrderType
    time_in_force: TimeInForce
    limit_price: Decimal | None
    stop_price: Decimal | None
    submitted_at: datetime
    activation_at: datetime
    expires_at: datetime | None
    parent_order_id: str | None
    replaces_order_id: str | None
    configuration_version: str
    execution_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "order-intent-v2-1":
            raise ValueError("unsupported order schema_version")
        for name in ("order_id", "run_id", "action_id"):
            _sha(getattr(self, name), name)
        for name in ("market", "instrument_id", "configuration_version", "execution_policy_version"):
            _text(getattr(self, name), name)
        if self.contract_id is not None:
            _text(self.contract_id, "contract_id")
        _positive(self.quantity, "quantity")
        _enum(self.side, OrderSide, "side")
        _enum(self.order_type, OrderType, "order_type")
        _enum(self.time_in_force, TimeInForce, "time_in_force")
        for value, name in ((self.limit_price, "limit_price"), (self.stop_price, "stop_price")):
            if value is not None:
                _positive(value, name)
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.limit_price is None:
            raise ValueError("limit order requires limit_price")
        if self.order_type in (OrderType.STOP_MARKET, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError("stop order requires stop_price")
        if self.order_type == OrderType.MARKET and (self.limit_price is not None or self.stop_price is not None):
            raise ValueError("market order cannot contain limit/stop prices")
        _utc(self.submitted_at, "submitted_at")
        _utc(self.activation_at, "activation_at")
        if self.activation_at < self.submitted_at:
            raise ValueError("activation cannot precede submission")
        if self.expires_at is not None:
            _utc(self.expires_at, "expires_at")
            if self.expires_at <= self.activation_at:
                raise ValueError("expiry must follow activation")
        for name in ("parent_order_id", "replaces_order_id"):
            value = getattr(self, name)
            if value is not None:
                _sha(value, name)
                if value == self.order_id:
                    raise ValueError(f"{name} cannot self-reference")


@dataclass(frozen=True, slots=True)
class OrderTransitionV2:
    schema_version: str
    transition_id: str
    order_id: str
    event_time: datetime
    from_state: OrderState
    to_state: OrderState
    reason_code: str
    source_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "order-transition-v2-1":
            raise ValueError("unsupported transition schema_version")
        _sha(self.transition_id, "transition_id")
        _sha(self.order_id, "order_id")
        _utc(self.event_time, "event_time")
        _enum(self.from_state, OrderState, "from_state")
        _enum(self.to_state, OrderState, "to_state")
        _text(self.reason_code, "reason_code")
        if self.from_state == self.to_state:
            raise ValueError("transition must change state")
        if len(self.source_event_ids) != len(set(self.source_event_ids)):
            raise ValueError("source_event_ids must be unique")


@dataclass(frozen=True, slots=True)
class FillV2:
    schema_version: str
    fill_id: str
    order_id: str
    market_event_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    fill_time: datetime
    side: OrderSide
    quantity: Decimal
    economic_price: Decimal
    reference_price: Decimal
    friction: Decimal
    fee_total: Decimal
    currency: str
    execution_rule_code: str
    execution_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "fill-v2-1":
            raise ValueError("unsupported fill schema_version")
        for name in ("fill_id", "order_id", "market_event_id"):
            _sha(getattr(self, name), name)
        for name in ("market", "instrument_id", "currency", "execution_rule_code",
                     "execution_policy_version"):
            _text(getattr(self, name), name)
        if self.contract_id is not None:
            _text(self.contract_id, "contract_id")
        _utc(self.fill_time, "fill_time")
        _enum(self.side, OrderSide, "side")
        for name in ("quantity", "economic_price", "reference_price"):
            _positive(getattr(self, name), name)
        _finite_decimal(self.friction, "friction")
        _nonnegative(self.fee_total, "fee_total")


@dataclass(frozen=True, slots=True)
class AccountingSnapshotV2:
    schema_version: str
    snapshot_id: str
    run_id: str
    as_of: datetime
    currency: str
    cash: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    funding: Decimal
    equity: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal
    available_funds: Decimal
    source_event_ids: tuple[str, ...]
    accounting_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "accounting-snapshot-v2-1":
            raise ValueError("unsupported accounting schema_version")
        _sha(self.snapshot_id, "snapshot_id")
        _sha(self.run_id, "run_id")
        _utc(self.as_of, "as_of")
        _text(self.currency, "currency")
        _text(self.accounting_version, "accounting_version")
        for name in ("cash", "realized_pnl", "unrealized_pnl", "fees", "funding", "equity",
                     "initial_margin", "maintenance_margin", "available_funds"):
            _finite_decimal(getattr(self, name), name)
        for name in ("fees", "initial_margin", "maintenance_margin"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if len(self.source_event_ids) != len(set(self.source_event_ids)):
            raise ValueError("source_event_ids must be unique")


@dataclass(frozen=True, slots=True)
class RiskEventV2:
    schema_version: str
    risk_event_id: str
    run_id: str
    event_time: datetime
    market: str
    instrument_id: str
    phase: RiskPhase
    decision: RiskDecision
    reason_codes: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    risk_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "risk-event-v2-1":
            raise ValueError("unsupported risk schema_version")
        _sha(self.risk_event_id, "risk_event_id")
        _sha(self.run_id, "run_id")
        _utc(self.event_time, "event_time")
        _enum(self.phase, RiskPhase, "phase")
        _enum(self.decision, RiskDecision, "decision")
        for name in ("market", "instrument_id", "risk_policy_version"):
            _text(getattr(self, name), name)
        if not self.reason_codes or len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason_codes must be non-empty and unique")
        if len(self.source_event_ids) != len(set(self.source_event_ids)):
            raise ValueError("source_event_ids must be unique")


@dataclass(frozen=True, slots=True)
class BacktestResultIdentityV2:
    schema_version: str
    result_id: str
    run_id: str
    configuration_fingerprint: str
    dataset_fingerprint: str
    economic_fingerprint: str
    strategy_version: str
    execution_policy_version: str
    accounting_version: str
    risk_policy_version: str
    started_at: datetime
    ended_at: datetime
    source_record_ids: tuple[str, ...]
    simulation_only: bool

    def __post_init__(self) -> None:
        if self.schema_version != "backtest-result-v2-1":
            raise ValueError("unsupported result schema_version")
        for name in ("result_id", "run_id", "configuration_fingerprint", "dataset_fingerprint",
                     "economic_fingerprint"):
            _sha(getattr(self, name), name)
        for name in ("strategy_version", "execution_policy_version", "accounting_version",
                     "risk_policy_version"):
            _text(getattr(self, name), name)
        _utc(self.started_at, "started_at")
        _utc(self.ended_at, "ended_at")
        if self.ended_at < self.started_at:
            raise ValueError("result ended_at cannot precede started_at")
        if not self.simulation_only:
            raise ValueError("v2 Phase 1 results must be simulation_only")
        if len(self.source_record_ids) != len(set(self.source_record_ids)):
            raise ValueError("source_record_ids must be unique")
