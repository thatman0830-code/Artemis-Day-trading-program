"""Deterministic Phase 4 instrument accounting.

The ledger consumes accepted Phase 3 fills and explicit economic facts.  It
does not create orders, fills, risk decisions, liquidation, or provider data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum, IntEnum

from .contracts import InstrumentSpecificationV2, OrderSide
from .ohlc_execution import ExecutionFillV2
from .specifications import InstrumentProfile, _finite_decimal, _text, _utc, canonical_fingerprint
from .validation import is_on_grid


ACCOUNTING_VERSION = "INSTRUMENT_ACCOUNTING_V2_PHASE4_1"


class AccountingEventKind(str, Enum):
    FILL = "FILL"
    MARK = "MARK"
    SETTLEMENT = "SETTLEMENT"
    FUNDING = "FUNDING"


class MarginBasis(str, Enum):
    NOTIONAL_RATE = "NOTIONAL_RATE"
    PER_CONTRACT = "PER_CONTRACT"


class AccountingReason(str, Enum):
    MIXED_LEDGER_VERSION = "MIXED_LEDGER_VERSION"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    EVENT_TIME_REGRESSION = "EVENT_TIME_REGRESSION"
    DUPLICATE_EVENT_CONFLICT = "DUPLICATE_EVENT_CONFLICT"
    DUPLICATE_ECONOMIC_EVENT = "DUPLICATE_ECONOMIC_EVENT"
    INVALID_ECONOMIC_FACT = "INVALID_ECONOMIC_FACT"
    OFF_GRID_ECONOMICS = "OFF_GRID_ECONOMICS"
    MISSING_FILL_COST = "MISSING_FILL_COST"
    MISSING_MARK_EVIDENCE = "MISSING_MARK_EVIDENCE"
    MISSING_SETTLEMENT_FACT = "MISSING_SETTLEMENT_FACT"
    SETTLEMENT_NOT_SUPPORTED = "SETTLEMENT_NOT_SUPPORTED"
    FUNDING_NOT_SUPPORTED = "FUNDING_NOT_SUPPORTED"
    MISSING_PERPETUAL_CAPABILITY = "MISSING_PERPETUAL_CAPABILITY"
    STALE_SPECIFICATION = "STALE_SPECIFICATION"
    CHECKPOINT_TAMPERED = "CHECKPOINT_TAMPERED"
    END_OF_DATA_RESIDUAL = "END_OF_DATA_RESIDUAL"


class AccountingError(ValueError):
    def __init__(self, reason: AccountingReason, detail: str):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}")


def _sha(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{field} must be lowercase SHA-256")


def _nonnegative(value: Decimal, field: str) -> None:
    _finite_decimal(value, field)
    if value < 0:
        raise ValueError(f"{field} must be nonnegative")


@dataclass(frozen=True, slots=True)
class FillEconomicsV2:
    schema_version: str
    economics_id: str
    fill_id: str
    commission: Decimal
    exchange_fee: Decimal
    slippage_cost: Decimal
    currency: str
    specification_ids: tuple[str, ...]
    cost_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "fill-economics-v2-1":
            raise ValueError("unsupported fill economics schema_version")
        _sha(self.economics_id, "economics_id"); _sha(self.fill_id, "fill_id")
        for name in ("commission", "exchange_fee", "slippage_cost"):
            _nonnegative(getattr(self, name), name)
        _text(self.currency, "currency"); _text(self.cost_version, "cost_version")
        if not self.specification_ids or len(self.specification_ids) != len(set(self.specification_ids)):
            raise ValueError("specification_ids must be non-empty and unique")

    @property
    def total(self) -> Decimal:
        return self.commission + self.exchange_fee + self.slippage_cost


@dataclass(frozen=True, slots=True)
class PriceEvidenceV2:
    schema_version: str
    price_event_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    observed_at: datetime
    available_at: datetime
    price: Decimal
    price_type: str
    specification_id: str
    source_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "price-evidence-v2-1":
            raise ValueError("unsupported price evidence schema_version")
        _sha(self.price_event_id, "price_event_id")
        for name in ("market", "instrument_id", "price_type", "specification_id", "source_version"):
            _text(getattr(self, name), name)
        _utc(self.observed_at, "observed_at"); _utc(self.available_at, "available_at")
        if self.available_at < self.observed_at:
            raise ValueError("price cannot be available before observation")
        _finite_decimal(self.price, "price")
        if self.price <= 0:
            raise ValueError("price must be positive")


@dataclass(frozen=True, slots=True)
class SettlementFactV2:
    schema_version: str
    settlement_id: str
    market: str
    instrument_id: str
    contract_id: str
    settlement_time: datetime
    available_at: datetime
    settlement_price: Decimal
    specification_id: str
    source_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "settlement-fact-v2-1":
            raise ValueError("unsupported settlement schema_version")
        _sha(self.settlement_id, "settlement_id")
        for name in ("market", "instrument_id", "contract_id", "specification_id", "source_version"):
            _text(getattr(self, name), name)
        _utc(self.settlement_time, "settlement_time"); _utc(self.available_at, "available_at")
        if self.available_at < self.settlement_time:
            raise ValueError("settlement cannot be available before its event")
        _finite_decimal(self.settlement_price, "settlement_price")
        if self.settlement_price <= 0:
            raise ValueError("settlement_price must be positive")


@dataclass(frozen=True, slots=True)
class FundingFactV2:
    schema_version: str
    funding_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    funding_time: datetime
    available_at: datetime
    rate: Decimal
    mark_price: Decimal
    oracle_price: Decimal
    specification_ids: tuple[str, ...]
    source_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "funding-fact-v2-1":
            raise ValueError("unsupported funding schema_version")
        _sha(self.funding_id, "funding_id")
        for name in ("market", "instrument_id", "source_version"):
            _text(getattr(self, name), name)
        _utc(self.funding_time, "funding_time"); _utc(self.available_at, "available_at")
        if self.available_at < self.funding_time:
            raise ValueError("funding cannot be available before its event")
        _finite_decimal(self.rate, "rate")
        for name in ("mark_price", "oracle_price"):
            _finite_decimal(getattr(self, name), name)
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if len(self.specification_ids) < 3 or len(self.specification_ids) != len(set(self.specification_ids)):
            raise ValueError("funding requires unique funding, mark, and oracle specifications")


@dataclass(frozen=True, slots=True)
class MarginSpecificationV2:
    schema_version: str
    margin_specification_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    effective_from: datetime
    effective_to: datetime | None
    basis: MarginBasis
    clearing_initial: Decimal
    clearing_maintenance: Decimal
    customer_initial: Decimal
    customer_maintenance: Decimal
    source_version: str

    def __post_init__(self) -> None:
        if self.schema_version != "margin-specification-v2-1":
            raise ValueError("unsupported margin schema_version")
        _sha(self.margin_specification_id, "margin_specification_id")
        for name in ("market", "instrument_id", "source_version"):
            _text(getattr(self, name), name)
        _utc(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _utc(self.effective_to, "effective_to")
            if self.effective_to <= self.effective_from:
                raise ValueError("margin interval must be non-empty")
        if not isinstance(self.basis, MarginBasis):
            raise ValueError("basis must be MarginBasis")
        for name in ("clearing_initial", "clearing_maintenance", "customer_initial", "customer_maintenance"):
            _nonnegative(getattr(self, name), name)
        if self.basis == MarginBasis.NOTIONAL_RATE and any(
                getattr(self, name) > 1 for name in ("clearing_initial", "clearing_maintenance", "customer_initial", "customer_maintenance")):
            raise ValueError("notional margin rates cannot exceed one")


@dataclass(frozen=True, slots=True)
class AccountingPolicyV2:
    schema_version: str
    accounting_version: str
    cost_version: str
    authoritative_price_type: str
    perpetual_capability_enabled: bool
    specification_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "accounting-policy-v2-1" or self.accounting_version != ACCOUNTING_VERSION:
            raise ValueError("unsupported accounting policy version")
        _text(self.cost_version, "cost_version"); _text(self.authoritative_price_type, "authoritative_price_type")
        if not self.specification_ids or len(self.specification_ids) != len(set(self.specification_ids)):
            raise ValueError("policy specification_ids must be non-empty and unique")
        if not isinstance(self.perpetual_capability_enabled, bool):
            raise ValueError("perpetual_capability_enabled must be bool")


@dataclass(frozen=True, slots=True)
class AccountingEventV2:
    schema_version: str
    event_id: str
    kind: AccountingEventKind
    event_time: datetime
    available_at: datetime
    fill: ExecutionFillV2 | None = None
    fill_economics: FillEconomicsV2 | None = None
    price: PriceEvidenceV2 | None = None
    settlement: SettlementFactV2 | None = None
    funding: FundingFactV2 | None = None

    def __post_init__(self) -> None:
        if self.schema_version != "accounting-event-v2-1":
            raise ValueError("unsupported accounting event schema_version")
        _sha(self.event_id, "event_id")
        if not isinstance(self.kind, AccountingEventKind):
            raise ValueError("kind must be AccountingEventKind")
        _utc(self.event_time, "event_time"); _utc(self.available_at, "available_at")
        if self.available_at < self.event_time:
            raise ValueError("event cannot be available before occurrence")
        payloads = (self.fill is not None, self.price is not None,
                    self.settlement is not None, self.funding is not None)
        if sum(payloads) != 1:
            raise ValueError("accounting event requires exactly one payload")
        if self.kind == AccountingEventKind.FILL and (self.fill is None or self.fill_economics is None):
            raise ValueError("fill event requires fill economics")
        if self.kind != AccountingEventKind.FILL and self.fill_economics is not None:
            raise ValueError("only fill events may contain fill economics")
        expected_type = {AccountingEventKind.FILL: ExecutionFillV2,
                         AccountingEventKind.MARK: PriceEvidenceV2,
                         AccountingEventKind.SETTLEMENT: SettlementFactV2,
                         AccountingEventKind.FUNDING: FundingFactV2}[self.kind]
        payload = {AccountingEventKind.FILL: self.fill, AccountingEventKind.MARK: self.price,
                   AccountingEventKind.SETTLEMENT: self.settlement,
                   AccountingEventKind.FUNDING: self.funding}[self.kind]
        if not isinstance(payload, expected_type):
            raise ValueError("accounting payload type does not match event kind")
        payload_time, payload_available = {
            AccountingEventKind.FILL: (self.fill.fill_time, self.fill.fill_time) if self.fill else (None, None),
            AccountingEventKind.MARK: (self.price.observed_at, self.price.available_at) if self.price else (None, None),
            AccountingEventKind.SETTLEMENT: (self.settlement.settlement_time, self.settlement.available_at) if self.settlement else (None, None),
            AccountingEventKind.FUNDING: (self.funding.funding_time, self.funding.available_at) if self.funding else (None, None),
        }[self.kind]
        if (self.event_time, self.available_at) != (payload_time, payload_available):
            raise ValueError("event chronology must equal immutable payload chronology")


@dataclass(frozen=True, slots=True)
class PositionStateV2:
    signed_quantity: Decimal
    average_entry_price: Decimal | None
    mark_price: Decimal | None
    last_settlement_price: Decimal | None

    def __post_init__(self) -> None:
        _finite_decimal(self.signed_quantity, "signed_quantity")
        for name in ("average_entry_price", "mark_price", "last_settlement_price"):
            value = getattr(self, name)
            if value is not None:
                _finite_decimal(value, name)
                if value <= 0:
                    raise ValueError(f"{name} must be positive")
        if self.signed_quantity == 0 and self.average_entry_price is not None:
            raise ValueError("flat position cannot retain average entry")
        if self.signed_quantity != 0 and self.average_entry_price is None:
            raise ValueError("open position requires average entry")


@dataclass(frozen=True, slots=True)
class AccountingSnapshotPhase4V2:
    schema_version: str
    snapshot_id: str
    run_id: str
    as_of: datetime
    market: str
    instrument_id: str
    contract_id: str | None
    profile: InstrumentProfile
    currency: str
    position: PositionStateV2
    starting_cash: Decimal
    cash: Decimal
    gross_realized_pnl: Decimal
    unrealized_pnl: Decimal
    settlement_transfers: Decimal
    commissions: Decimal
    exchange_fees: Decimal
    slippage_costs: Decimal
    funding: Decimal
    total_costs: Decimal
    net_result: Decimal
    equity: Decimal
    clearing_initial_margin: Decimal
    clearing_maintenance_margin: Decimal
    customer_initial_margin: Decimal
    customer_maintenance_margin: Decimal
    margin_breach: bool
    source_event_ids: tuple[str, ...]
    accounting_version: str
    snapshot_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != "instrument-accounting-snapshot-v2-1":
            raise ValueError("unsupported accounting snapshot schema_version")
        _sha(self.snapshot_id, "snapshot_id"); _sha(self.run_id, "run_id")
        _sha(self.snapshot_fingerprint, "snapshot_fingerprint")
        _utc(self.as_of, "as_of")
        for name in ("market", "instrument_id", "currency", "accounting_version"):
            _text(getattr(self, name), name)
        for name in ("starting_cash", "cash", "gross_realized_pnl", "unrealized_pnl",
                     "settlement_transfers", "commissions", "exchange_fees", "slippage_costs",
                     "funding", "total_costs", "net_result", "equity",
                     "clearing_initial_margin", "clearing_maintenance_margin",
                     "customer_initial_margin", "customer_maintenance_margin"):
            _finite_decimal(getattr(self, name), name)
        if len(self.source_event_ids) != len(set(self.source_event_ids)):
            raise ValueError("source event identities must be unique")
        if self.total_costs != self.commissions + self.exchange_fees + self.slippage_costs:
            raise ValueError("cost attribution does not sum exactly")
        if self.net_result != self.gross_result - self.total_costs:
            raise ValueError("gross minus costs does not equal net result")
        expected_equity = (self.cash + self.position.signed_quantity *
                           (self.position.mark_price or Decimal("0"))) if self.profile == InstrumentProfile.BTC_SPOT else (
                           self.cash + self.unrealized_pnl)
        if self.equity != expected_equity:
            raise ValueError("cash and equity do not reconcile")
        for name in ("clearing_initial_margin", "clearing_maintenance_margin",
                     "customer_initial_margin", "customer_maintenance_margin"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")

    @property
    def gross_result(self) -> Decimal:
        return self.gross_realized_pnl + self.settlement_transfers + self.funding


class _Priority(IntEnum):
    SETTLEMENT = 10
    FUNDING = 20
    FILL = 30
    MARK = 40


_PRIORITY = {AccountingEventKind.SETTLEMENT: _Priority.SETTLEMENT,
             AccountingEventKind.FUNDING: _Priority.FUNDING,
             AccountingEventKind.FILL: _Priority.FILL,
             AccountingEventKind.MARK: _Priority.MARK}


def _identity(record, market: str, instrument_id: str, contract_id: str | None) -> bool:
    return (record.market, record.instrument_id, record.contract_id) == (market, instrument_id, contract_id)


def _pnl(profile: InstrumentProfile, signed_quantity: Decimal, entry: Decimal,
         price: Decimal, multiplier: Decimal) -> Decimal:
    return signed_quantity * (price - entry) * multiplier


def _margin(spec: MarginSpecificationV2, quantity: Decimal, price: Decimal,
            multiplier: Decimal, value: Decimal) -> Decimal:
    if spec.basis == MarginBasis.PER_CONTRACT:
        return abs(quantity) * value
    return abs(quantity) * price * multiplier * value


@dataclass(frozen=True, slots=True)
class AccountingCheckpointV2:
    schema_version: str
    checkpoint_id: str
    ledger_fingerprint: str
    ledger: "InstrumentAccountingLedgerV2"

    def __post_init__(self) -> None:
        if self.schema_version != "accounting-checkpoint-v2-1":
            raise ValueError("unsupported checkpoint schema_version")
        _sha(self.checkpoint_id, "checkpoint_id"); _sha(self.ledger_fingerprint, "ledger_fingerprint")
        if self.ledger.ledger_fingerprint != self.ledger_fingerprint:
            raise AccountingError(AccountingReason.CHECKPOINT_TAMPERED, "checkpoint fingerprint differs")


@dataclass(frozen=True, slots=True)
class InstrumentAccountingLedgerV2:
    schema_version: str
    run_id: str
    market: str
    instrument_id: str
    contract_id: str | None
    profile: InstrumentProfile
    currency: str
    starting_cash: Decimal
    instrument: InstrumentSpecificationV2
    policy: AccountingPolicyV2
    margin_specification: MarginSpecificationV2
    events: tuple[AccountingEventV2, ...]
    snapshots: tuple[AccountingSnapshotPhase4V2, ...]
    ledger_fingerprint: str

    @classmethod
    def create(cls, *, run_id: str, starting_cash: Decimal, instrument: InstrumentSpecificationV2,
               policy: AccountingPolicyV2, margin_specification: MarginSpecificationV2) -> "InstrumentAccountingLedgerV2":
        _sha(run_id, "run_id"); _finite_decimal(starting_cash, "starting_cash")
        if instrument.profile == InstrumentProfile.BTC_UNKNOWN_UNSUPPORTED:
            raise AccountingError(AccountingReason.INVALID_ECONOMIC_FACT, "unsupported instrument profile")
        if instrument.profile == InstrumentProfile.BTC_LINEAR_PERPETUAL and not policy.perpetual_capability_enabled:
            raise AccountingError(AccountingReason.MISSING_PERPETUAL_CAPABILITY, "perpetual capability is disabled")
        if (margin_specification.market, margin_specification.instrument_id, margin_specification.contract_id) != (
                instrument.market, instrument.instrument_id, instrument.contract_id):
            raise AccountingError(AccountingReason.IDENTITY_MISMATCH, "margin and instrument identities differ")
        if instrument.profile == InstrumentProfile.BTC_SPOT and any((margin_specification.clearing_initial,
                margin_specification.clearing_maintenance, margin_specification.customer_initial,
                margin_specification.customer_maintenance)):
            raise AccountingError(AccountingReason.INVALID_ECONOMIC_FACT,
                                  "unlevered BTC spot requires zero margin facts")
        zero_position = PositionStateV2(Decimal("0"), None, None, None)
        provisional = cls("instrument-accounting-ledger-v2-1", run_id, instrument.market,
            instrument.instrument_id, instrument.contract_id, instrument.profile, instrument.currency,
            starting_cash, instrument, policy, margin_specification, (), (), "0" * 64)
        snap = provisional._snapshot(zero_position, starting_cash, Decimal("0"), Decimal("0"),
                                    Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), ())
        return replace(provisional, snapshots=(snap,), ledger_fingerprint=provisional._fingerprint((), (snap,)))

    def __post_init__(self) -> None:
        if self.schema_version != "instrument-accounting-ledger-v2-1":
            raise ValueError("unsupported accounting ledger schema_version")
        _sha(self.run_id, "run_id"); _sha(self.ledger_fingerprint, "ledger_fingerprint")

    def _fingerprint(self, events, snapshots) -> str:
        return canonical_fingerprint(self.schema_version, self.run_id, self.market, self.instrument_id,
            self.contract_id, self.profile, self.currency, self.starting_cash,
            self.instrument.specification_id, self.policy, self.margin_specification,
            events, tuple(replace(s, snapshot_fingerprint="0" * 64) for s in snapshots))

    def verify_integrity(self) -> None:
        if self.ledger_fingerprint != self._fingerprint(self.events, self.snapshots):
            raise AccountingError(AccountingReason.CHECKPOINT_TAMPERED, "ledger fingerprint differs")

    @property
    def snapshot(self) -> AccountingSnapshotPhase4V2:
        return self.snapshots[-1]

    def _snapshot(self, position: PositionStateV2, cash: Decimal, gross: Decimal,
                  settlement: Decimal, commissions: Decimal, exchange_fees: Decimal,
                  slippage: Decimal, funding: Decimal, source_ids: tuple[str, ...],
                  as_of: datetime | None = None) -> AccountingSnapshotPhase4V2:
        mark = position.mark_price or position.average_entry_price
        unrealized = Decimal("0") if position.signed_quantity == 0 or mark is None else _pnl(
            self.profile, position.signed_quantity, position.average_entry_price, mark,
            self.instrument.contract_multiplier)
        costs = commissions + exchange_fees + slippage
        net = gross + settlement + funding - costs
        if self.profile == InstrumentProfile.BTC_SPOT:
            equity = cash + position.signed_quantity * (mark or Decimal("0"))
        else:
            equity = cash + unrealized
        m = self.margin_specification
        margin_price = mark or position.average_entry_price or Decimal("0")
        ci = _margin(m, position.signed_quantity, margin_price, self.instrument.contract_multiplier, m.clearing_initial)
        cm = _margin(m, position.signed_quantity, margin_price, self.instrument.contract_multiplier, m.clearing_maintenance)
        ui = _margin(m, position.signed_quantity, margin_price, self.instrument.contract_multiplier, m.customer_initial)
        um = _margin(m, position.signed_quantity, margin_price, self.instrument.contract_multiplier, m.customer_maintenance)
        breach = bool(position.signed_quantity and equity < um)
        stamp = as_of or self.instrument.effective_from
        values = (self.run_id, stamp, self.market, self.instrument_id, self.contract_id, position,
                  self.starting_cash, cash, gross, unrealized, settlement, commissions,
                  exchange_fees, slippage, funding, costs, net, equity, ci, cm, ui, um,
                  breach, source_ids, self.policy.accounting_version)
        fingerprint = canonical_fingerprint("instrument-accounting-snapshot-v2-1", *values)
        return AccountingSnapshotPhase4V2("instrument-accounting-snapshot-v2-1", fingerprint,
            self.run_id, stamp, self.market, self.instrument_id, self.contract_id, self.profile,
            self.currency, position, self.starting_cash, cash, gross, unrealized, settlement,
            commissions, exchange_fees, slippage, funding, costs, net, equity, ci, cm, ui, um,
            breach, source_ids, self.policy.accounting_version, fingerprint)

    def apply(self, event: AccountingEventV2) -> "InstrumentAccountingLedgerV2":
        self.verify_integrity()
        existing = {item.event_id: item for item in self.events}
        if event.event_id in existing:
            if existing[event.event_id] == event:
                return self
            raise AccountingError(AccountingReason.DUPLICATE_EVENT_CONFLICT, "event identity reused")
        def economic_identity(item: AccountingEventV2) -> str:
            if item.kind == AccountingEventKind.FILL:
                return item.fill_economics.economics_id
            if item.kind == AccountingEventKind.MARK:
                return item.price.price_event_id
            if item.kind == AccountingEventKind.SETTLEMENT:
                return item.settlement.settlement_id
            return item.funding.funding_id
        if economic_identity(event) in {economic_identity(item) for item in self.events}:
            raise AccountingError(AccountingReason.DUPLICATE_ECONOMIC_EVENT,
                                  "economic identity was already applied under another event")
        if self.events:
            previous = self.events[-1]
            if (event.available_at, int(_PRIORITY[event.kind]), event.event_id) < (
                    previous.available_at, int(_PRIORITY[previous.kind]), previous.event_id):
                raise AccountingError(AccountingReason.EVENT_TIME_REGRESSION, "canonical event order regressed")
        snap = self.snapshot
        position = snap.position
        cash, gross, settlement = snap.cash, snap.gross_realized_pnl, snap.settlement_transfers
        commissions, exchange_fees = snap.commissions, snap.exchange_fees
        slippage, funding_total = snap.slippage_costs, snap.funding
        if not (self.margin_specification.effective_from <= event.event_time and
                (self.margin_specification.effective_to is None or event.event_time < self.margin_specification.effective_to)):
            raise AccountingError(AccountingReason.STALE_SPECIFICATION, "margin specification not effective")
        if not (self.instrument.effective_from <= event.event_time and
                (self.instrument.effective_to is None or event.event_time < self.instrument.effective_to)):
            raise AccountingError(AccountingReason.STALE_SPECIFICATION, "instrument specification not effective")

        if event.kind == AccountingEventKind.FILL:
            fill, economics = event.fill, event.fill_economics
            if not _identity(fill, self.market, self.instrument_id, self.contract_id):
                raise AccountingError(AccountingReason.IDENTITY_MISMATCH, "fill identity differs")
            if economics.fill_id != fill.fill_id or economics.currency != self.currency:
                raise AccountingError(AccountingReason.MISSING_FILL_COST, "fill cost lineage differs")
            if economics.cost_version != self.policy.cost_version:
                raise AccountingError(AccountingReason.VERSION_MISMATCH, "cost version differs")
            if not set(economics.specification_ids).issubset(set(self.policy.specification_ids)):
                raise AccountingError(AccountingReason.INVALID_ECONOMIC_FACT, "cost specifications are unverified")
            if fill.execution_policy_version.startswith("v1"):
                raise AccountingError(AccountingReason.MIXED_LEDGER_VERSION, "v1 fill is ineligible")
            if not is_on_grid(fill.quantity, self.instrument.quantity_step) or not is_on_grid(fill.economic_price, self.instrument.tick_size):
                raise AccountingError(AccountingReason.OFF_GRID_ECONOMICS, "fill is off instrument grid")
            expected_slippage = fill.adverse_friction * fill.quantity * self.instrument.contract_multiplier
            if economics.slippage_cost != expected_slippage:
                raise AccountingError(AccountingReason.INVALID_ECONOMIC_FACT, "slippage attribution differs from accepted fill")
            direction = Decimal("1") if fill.side == OrderSide.BUY else Decimal("-1")
            delta = direction * fill.quantity
            old_q, old_avg = position.signed_quantity, position.average_entry_price
            close_qty = min(abs(old_q), abs(delta)) if old_q and old_q * delta < 0 else Decimal("0")
            realized = Decimal("0") if close_qty == 0 else close_qty * (fill.reference_price - old_avg) * (
                Decimal("1") if old_q > 0 else Decimal("-1")) * self.instrument.contract_multiplier
            new_q = old_q + delta
            if old_q == 0 or old_q * delta > 0:
                new_avg = ((abs(old_q) * (old_avg or Decimal("0"))) + abs(delta) * fill.reference_price) / abs(new_q)
            elif new_q == 0:
                new_avg = None
            elif old_q * new_q > 0:
                new_avg = old_avg
            else:
                new_avg = fill.reference_price
            gross += realized
            commissions += economics.commission; exchange_fees += economics.exchange_fee
            slippage += economics.slippage_cost
            if self.profile == InstrumentProfile.BTC_SPOT:
                cash -= delta * fill.reference_price
                cash -= economics.total
            else:
                cash += realized - economics.total
            position = PositionStateV2(new_q, new_avg, fill.reference_price, position.last_settlement_price)

        elif event.kind == AccountingEventKind.MARK:
            price = event.price
            if not _identity(price, self.market, self.instrument_id, self.contract_id):
                raise AccountingError(AccountingReason.IDENTITY_MISMATCH, "mark identity differs")
            if price.price_type != self.policy.authoritative_price_type:
                raise AccountingError(AccountingReason.MISSING_MARK_EVIDENCE, "wrong authoritative price type")
            if price.specification_id not in self.policy.specification_ids:
                raise AccountingError(AccountingReason.MISSING_MARK_EVIDENCE, "mark specification is unverified")
            if not is_on_grid(price.price, self.instrument.tick_size):
                raise AccountingError(AccountingReason.OFF_GRID_ECONOMICS, "mark is off tick grid")
            position = replace(position, mark_price=price.price)

        elif event.kind == AccountingEventKind.SETTLEMENT:
            fact = event.settlement
            if self.profile not in (InstrumentProfile.ES_FUTURE, InstrumentProfile.NQ_FUTURE):
                raise AccountingError(AccountingReason.SETTLEMENT_NOT_SUPPORTED, "profile has no variation settlement")
            if not _identity(fact, self.market, self.instrument_id, self.contract_id):
                raise AccountingError(AccountingReason.IDENTITY_MISMATCH, "settlement identity differs")
            if fact.specification_id not in self.policy.specification_ids:
                raise AccountingError(AccountingReason.MISSING_SETTLEMENT_FACT, "settlement specification is unverified")
            if not is_on_grid(fact.settlement_price, self.instrument.tick_size):
                raise AccountingError(AccountingReason.OFF_GRID_ECONOMICS, "settlement is off tick grid")
            transfer = Decimal("0") if position.signed_quantity == 0 else _pnl(self.profile,
                position.signed_quantity, position.average_entry_price, fact.settlement_price,
                self.instrument.contract_multiplier)
            cash += transfer; settlement += transfer
            position = PositionStateV2(position.signed_quantity,
                fact.settlement_price if position.signed_quantity else None,
                fact.settlement_price, fact.settlement_price)

        elif event.kind == AccountingEventKind.FUNDING:
            fact = event.funding
            if self.profile != InstrumentProfile.BTC_LINEAR_PERPETUAL:
                raise AccountingError(AccountingReason.FUNDING_NOT_SUPPORTED, "funding is perpetual-only")
            if not self.policy.perpetual_capability_enabled:
                raise AccountingError(AccountingReason.MISSING_PERPETUAL_CAPABILITY, "perpetual capability is disabled")
            if not _identity(fact, self.market, self.instrument_id, self.contract_id):
                raise AccountingError(AccountingReason.IDENTITY_MISMATCH, "funding identity differs")
            if not set(fact.specification_ids).issubset(set(self.policy.specification_ids)):
                raise AccountingError(AccountingReason.INVALID_ECONOMIC_FACT, "funding lineage is unverified")
            if not is_on_grid(fact.mark_price, self.instrument.tick_size) or not is_on_grid(
                    fact.oracle_price, self.instrument.tick_size):
                raise AccountingError(AccountingReason.OFF_GRID_ECONOMICS,
                                      "funding mark/oracle evidence is off tick grid")
            payment = -position.signed_quantity * fact.mark_price * self.instrument.contract_multiplier * fact.rate
            cash += payment; funding_total += payment
            position = replace(position, mark_price=fact.mark_price)

        source_ids = snap.source_event_ids + (event.event_id,)
        new_snap = self._snapshot(position, cash, gross, settlement, commissions, exchange_fees,
                                  slippage, funding_total, source_ids, event.available_at)
        events = self.events + (event,); snapshots = self.snapshots + (new_snap,)
        return replace(self, events=events, snapshots=snapshots,
                       ledger_fingerprint=self._fingerprint(events, snapshots))

    @classmethod
    def replay(cls, base: "InstrumentAccountingLedgerV2", events: tuple[AccountingEventV2, ...]) -> "InstrumentAccountingLedgerV2":
        if base.events:
            raise AccountingError(AccountingReason.CHECKPOINT_TAMPERED, "replay base must be empty")
        ledger = base
        for event in events:
            ledger = ledger.apply(event)
        return ledger

    def checkpoint(self) -> AccountingCheckpointV2:
        return AccountingCheckpointV2("accounting-checkpoint-v2-1",
            canonical_fingerprint("accounting-checkpoint-v2-1", self.ledger_fingerprint),
            self.ledger_fingerprint, self)

    @classmethod
    def resume(cls, checkpoint: AccountingCheckpointV2) -> "InstrumentAccountingLedgerV2":
        checkpoint.ledger.verify_integrity()
        expected = canonical_fingerprint("accounting-checkpoint-v2-1", checkpoint.ledger_fingerprint)
        if checkpoint.checkpoint_id != expected:
            raise AccountingError(AccountingReason.CHECKPOINT_TAMPERED, "checkpoint identity differs")
        return checkpoint.ledger

    def validate_end_of_data(self) -> tuple[AccountingReason, ...]:
        return (AccountingReason.END_OF_DATA_RESIDUAL,) if self.snapshot.position.signed_quantity else ()
