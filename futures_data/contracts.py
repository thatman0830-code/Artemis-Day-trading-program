from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Mapping, Protocol


SCHEMA_VERSION = "futures-data-v1"


def utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC timezone-aware")
    return value.astimezone(timezone.utc)


def decimal(value: object, field: str, *, positive: bool = False, nonnegative: bool = False) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field} must be Decimal; float conversion is forbidden")
    if not value.is_finite():
        raise ValueError(f"{field} must be finite")
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValueError(f"{field} has invalid sign")
    return value


def identity(*parts: object) -> str:
    return sha256("\x1f".join(str(x) for x in parts).encode()).hexdigest()


class FuturesRoot(str, Enum):
    ES = "ES"
    NQ = "NQ"


class InstrumentKind(str, Enum):
    OUTRIGHT_FUTURE = "OUTRIGHT_FUTURE"


@dataclass(frozen=True)
class ContractSpec:
    id: str
    provider: str
    provider_ticker: str
    root: FuturesRoot
    contract_month: int
    contract_year: int
    exchange: str
    first_trade_date: date
    last_trade_date: date
    expiration_date: date
    settlement_date: date
    tick_size: Decimal
    tick_value: Decimal
    multiplier: Decimal
    source_version: str
    retrieved_at: datetime
    kind: InstrumentKind = InstrumentKind.OUTRIGHT_FUTURE

    def __post_init__(self) -> None:
        if not all(isinstance(x, str) and x.strip() for x in (self.provider, self.provider_ticker, self.exchange, self.source_version)):
            raise ValueError("contract text lineage is required")
        if not isinstance(self.root, FuturesRoot) or self.kind is not InstrumentKind.OUTRIGHT_FUTURE:
            raise ValueError("only ES/NQ outright futures are supported")
        if not 1 <= self.contract_month <= 12 or self.contract_year < 2000:
            raise ValueError("invalid contract month/year")
        if not self.first_trade_date <= self.last_trade_date <= self.expiration_date:
            raise ValueError("contract lifecycle dates are inconsistent")
        decimal(self.tick_size, "tick_size", positive=True); decimal(self.tick_value, "tick_value", positive=True)
        decimal(self.multiplier, "multiplier", positive=True); utc(self.retrieved_at, "retrieved_at")
        expected = identity(SCHEMA_VERSION, self.provider, self.provider_ticker, self.root.value,
                            self.contract_month, self.contract_year, self.exchange, self.source_version)
        if self.id != expected:
            raise ValueError("contract identity mismatch")


@dataclass(frozen=True)
class FuturesBar:
    id: str
    contract_id: str
    provider_ticker: str
    root: FuturesRoot
    open_time: datetime
    close_time: datetime
    provider_timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    finalized: bool
    source_version: str

    def __post_init__(self) -> None:
        opened, closed = utc(self.open_time, "open_time"), utc(self.close_time, "close_time")
        utc(self.provider_timestamp, "provider_timestamp")
        if closed - opened != timedelta(minutes=1) or opened.second or opened.microsecond:
            raise ValueError("bar must be an aligned one-minute interval")
        if not self.finalized:
            raise ValueError("forming bars are forbidden")
        values = [decimal(getattr(self, n), n, positive=n != "volume", nonnegative=n == "volume")
                  for n in ("open", "high", "low", "close", "volume")]
        o, h, l, c, _ = values
        if h < max(o, c) or l > min(o, c) or h < l:
            raise ValueError("invalid OHLC geometry")
        if self.id != identity(SCHEMA_VERSION, self.contract_id, opened.isoformat(), closed.isoformat()):
            raise ValueError("bar identity mismatch")


@dataclass(frozen=True)
class RequestManifest:
    id: str
    provider: str
    operation: str
    parameters: tuple[tuple[str, str], ...]
    requested_at: datetime
    raw_sha256: str
    cursor_in: str | None
    cursor_out: str | None
    status_code: int
    rate_limit_remaining: int | None
    retry_after_seconds: Decimal | None

    def __post_init__(self) -> None:
        utc(self.requested_at, "requested_at")
        if tuple(sorted(self.parameters)) != self.parameters or any("key" in k.lower() or "token" in k.lower() for k, _ in self.parameters):
            raise ValueError("request parameters must be sorted and credential-free")
        if len(self.raw_sha256) != 64 or not 100 <= self.status_code <= 599:
            raise ValueError("invalid request audit facts")
        if self.retry_after_seconds is not None:
            decimal(self.retry_after_seconds, "retry_after_seconds", nonnegative=True)


@dataclass(frozen=True)
class Page:
    records: tuple[Mapping[str, object], ...]
    raw_bytes: bytes
    next_cursor: str | None
    status_code: int = 200
    rate_limit_remaining: int | None = None
    retry_after_seconds: Decimal | None = None


class FuturesDataProvider(Protocol):
    provider_id: str
    supports_trades: bool
    supports_quotes: bool
    def discover_contracts(self, root: FuturesRoot, *, as_of: datetime) -> tuple[ContractSpec, ...]: ...
    def get_contract(self, ticker: str, *, as_of: datetime) -> ContractSpec: ...
    def get_schedule(self, contract: ContractSpec, *, start: date, end: date) -> object: ...
    def get_minute_bars(self, contract: ContractSpec, *, start: datetime, end: datetime,
                        cursor: str | None = None) -> tuple[tuple[FuturesBar, ...], RequestManifest]: ...

