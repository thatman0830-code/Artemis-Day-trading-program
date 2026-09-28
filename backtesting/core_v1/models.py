from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum
from hashlib import sha256
import json
from typing import Any


CORE_V1_VERSION = "backtest-engine-core-v1"


def require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC timezone-aware")


def require_decimal(value: Decimal, name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError(f"{name} must be a finite Decimal")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")


def canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        require_utc(value)
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, timedelta):
        return format(Decimal(str(value.total_seconds())), "f")
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {k: canonical(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [canonical(v) for v in value]
    return value


def fingerprint(value: Any) -> str:
    raw = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(raw.encode("utf-8")).hexdigest()


class EventType(str, Enum):
    DATA_QUALITY_HALT = "DATA_QUALITY_HALT"
    SESSION_OPEN = "SESSION_OPEN"
    SESSION_CLOSE = "SESSION_CLOSE"
    MAINTENANCE_BREAK = "MAINTENANCE_BREAK"
    EXCHANGE_CLOSURE = "EXCHANGE_CLOSURE"
    EARLY_CLOSE = "EARLY_CLOSE"
    ROLLOVER_DECISION = "ROLLOVER_DECISION"
    ROLLOVER_EFFECTIVE = "ROLLOVER_EFFECTIVE"
    FINALIZED_MARKET_BAR = "FINALIZED_MARKET_BAR"
    FUNDING = "FUNDING"
    SIGNAL_EVALUATION = "SIGNAL_EVALUATION"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    FILL = "FILL"
    PARTIAL_FILL = "PARTIAL_FILL"
    CANCEL = "CANCEL"
    EXPIRY = "EXPIRY"
    POSITION_UPDATE = "POSITION_UPDATE"
    CASH_FEE_MARGIN_UPDATE = "CASH_FEE_MARGIN_UPDATE"
    MARK_TO_MARKET = "MARK_TO_MARKET"
    RISK = "RISK"
    END_OF_RUN = "END_OF_RUN"


EVENT_PRIORITY = {kind: index for index, kind in enumerate(EventType)}


class TriggerKind(str, Enum):
    PERIODIC = "PERIODIC"
    SESSION = "SESSION"
    MARKET = "MARKET"
    RISK = "RISK"
    ROLLOVER = "ROLLOVER"
    DATA_QUALITY = "DATA_QUALITY"


class ActionKind(str, Enum):
    ENTER = "ENTER"
    EXIT = "EXIT"
    REDUCE = "REDUCE"
    CANCEL = "CANCEL"
    FLATTEN = "FLATTEN"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class EndPolicy(str, Enum):
    FLATTEN = "FLATTEN"
    REJECT_OPEN = "REJECT_OPEN"


@dataclass(frozen=True)
class CoreBar:
    id: str
    market: str
    instrument_id: str
    contract_id: str | None
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    session_id: str
    source_id: str
    source_version: str
    source_checksum: str
    sequence: int
    tradable: bool = True
    missing_before: int = 0
    rollover_decision_id: str | None = None
    dataset_lineage: str = ""

    def __post_init__(self) -> None:
        require_utc(self.open_time); require_utc(self.close_time)
        if self.open_time >= self.close_time:
            raise ValueError("bar interval is invalid")
        for name in ("open", "high", "low", "close"):
            require_decimal(getattr(self, name), name, positive=True)
        require_decimal(self.volume, "volume")
        if self.volume < 0 or self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("bar geometry is invalid")
        if self.sequence < 0 or self.missing_before < 0:
            raise ValueError("bar sequence/gap metadata is invalid")


@dataclass(frozen=True)
class CoreEvent:
    id: str
    event_type: EventType
    event_time: datetime
    market: str
    instrument_id: str
    contract_id: str | None
    session_id: str | None
    source_id: str
    source_checksum: str
    sequence: int
    schema_version: str = CORE_V1_VERSION

    def __post_init__(self) -> None:
        require_utc(self.event_time)

    @property
    def ordering_key(self) -> tuple:
        return (self.event_time, EVENT_PRIORITY[self.event_type], self.market,
                self.instrument_id, self.sequence, self.id)


@dataclass(frozen=True)
class Trigger:
    id: str
    kind: TriggerKind
    event: CoreEvent


@dataclass(frozen=True)
class Action:
    id: str
    kind: ActionKind
    instrument_id: str
    side: Side | None = None
    quantity: Decimal | None = None
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    reason: str = ""


@dataclass(frozen=True)
class StrategyRequirements:
    strategy_id: str
    strategy_version: str
    markets: tuple[str, ...]
    required_fields: tuple[str, ...]
    trigger_kinds: tuple[TriggerKind, ...]
    order_types: tuple[OrderType, ...]
    requires_volume_for_partial_fills: bool = False
    requires_funding: bool = False
    requires_rollover: bool = False


@dataclass(frozen=True)
class ReadOnlyState:
    event_time: datetime
    bars: tuple[CoreBar, ...]
    positions: tuple["PositionSnapshot", ...]
    equity: Decimal
    source_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class InstrumentSpec:
    id: str
    instrument_id: str
    market: str
    tick_size: Decimal
    quantity_step: Decimal
    contract_multiplier: Decimal
    margin_rate: Decimal
    commission_rate: Decimal
    slippage_ticks: Decimal
    effective_from: datetime
    effective_to: datetime | None
    source_id: str
    version: str

    def __post_init__(self) -> None:
        require_utc(self.effective_from)
        if self.effective_to: require_utc(self.effective_to)
        for name in ("tick_size", "quantity_step", "contract_multiplier"):
            require_decimal(getattr(self, name), name, positive=True)
        for name in ("margin_rate", "commission_rate", "slippage_ticks"):
            require_decimal(getattr(self, name), name)
            if getattr(self, name) < 0: raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True)
class ExecutionConfig:
    version: str
    volume_participation: Decimal | None
    end_policy: EndPolicy
    reject_ambiguous_intrabar: bool = True


@dataclass(frozen=True)
class RiskConfig:
    version: str
    max_gross_exposure: Decimal
    max_margin: Decimal
    minimum_planned_rr: Decimal

    def __post_init__(self) -> None:
        for name in ("max_gross_exposure", "max_margin", "minimum_planned_rr"):
            require_decimal(getattr(self, name), name, positive=True)


@dataclass(frozen=True)
class OrderRecord:
    id: str
    action_id: str
    instrument_id: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    submitted_at: datetime
    eligible_after: datetime
    state: str
    reason: str | None


@dataclass(frozen=True)
class FillRecord:
    id: str
    order_id: str
    bar_id: str
    event_time: datetime
    price: Decimal
    quantity: Decimal
    commission: Decimal
    slippage: Decimal
    partial: bool


@dataclass(frozen=True)
class PositionSnapshot:
    id: str
    instrument_id: str
    quantity: Decimal
    average_price: Decimal
    event_time: datetime
    source_fill_id: str


@dataclass(frozen=True)
class AccountingSnapshot:
    id: str
    event_time: datetime
    cash: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    funding: Decimal
    margin: Decimal
    gross_exposure: Decimal
    equity: Decimal
    drawdown: Decimal
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class BacktestResult:
    id: str
    result_version: str
    run_id: str
    dataset_fingerprints: tuple[str, ...]
    strategy_identity: str
    configuration_identity: str
    capability_report_id: str
    events: tuple[CoreEvent, ...]
    orders: tuple[OrderRecord, ...]
    fills: tuple[FillRecord, ...]
    positions: tuple[PositionSnapshot, ...]
    accounting: tuple[AccountingSnapshot, ...]
    rejections: tuple[str, ...]
    finalized_trade_count: int
    oos_trade_count_by_market: tuple[tuple[str, int], ...]
    advisory_acceptance: str
    runtime_facts: tuple[tuple[str, str], ...] = ()

    def machine_json(self) -> str:
        payload = canonical(self)
        payload.pop("runtime_facts", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
