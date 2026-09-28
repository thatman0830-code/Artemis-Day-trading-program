from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Mapping


class CanonicalTimeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"

    @property
    def duration(self) -> timedelta:
        return {
            self.M1: timedelta(minutes=1), self.M5: timedelta(minutes=5),
            self.M15: timedelta(minutes=15), self.H1: timedelta(hours=1),
            self.H4: timedelta(hours=4),
        }[self]


class GapPolicy(str, Enum):
    REJECT = "REJECT"
    RECORD = "RECORD"


class ValidationStatus(str, Enum):
    VALID = "VALID"
    VALID_WITH_GAPS = "VALID_WITH_GAPS"


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    return value.strip()


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a UTC timezone-aware datetime.")
    return value.astimezone(timezone.utc)


def _decimal(value: object, field: str, *, optional: bool = False) -> Decimal | None:
    if value is None and optional:
        return None
    if not isinstance(value, Decimal):
        raise TypeError(f"{field} must be Decimal; implicit conversion is forbidden.")
    if not value.is_finite():
        raise ValueError(f"{field} must be finite.")
    return value


def _canonical_decimal(value: Decimal | None) -> str:
    if value is None:
        return "NULL"
    normalized = value.normalize()
    return format(normalized, "f") if normalized else "0"


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identity(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HistoricalCandle:
    id: str
    dataset_id: str
    schema_version: str
    source: str
    exchange: str
    symbol: str
    timeframe: CanonicalTimeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    is_closed: bool

    def __post_init__(self) -> None:
        for name in ("id", "dataset_id", "schema_version", "source", "exchange", "symbol"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.timeframe, CanonicalTimeframe):
            raise TypeError("timeframe must be CanonicalTimeframe.")
        opened, closed = _utc(self.open_time, "open_time"), _utc(self.close_time, "close_time")
        if opened >= closed:
            raise ValueError("open_time must be before close_time.")
        if closed - opened != self.timeframe.duration:
            raise ValueError("Candle duration does not match its canonical timeframe.")
        interval_seconds = int(self.timeframe.duration.total_seconds())
        if int(opened.timestamp()) % interval_seconds != 0 or opened.microsecond != 0:
            raise ValueError("Candle open_time is not canonically interval-aligned.")
        if not isinstance(self.is_closed, bool) or not self.is_closed:
            raise ValueError("Historical datasets accept completed candles only.")
        prices = {name: _decimal(getattr(self, name), name) for name in ("open", "high", "low", "close")}
        if any(value <= 0 for value in prices.values()):
            raise ValueError("Candle prices must be positive.")
        if prices["high"] < max(prices["open"], prices["close"]) or prices["low"] > min(prices["open"], prices["close"]):
            raise ValueError("Invalid OHLC geometry.")
        if prices["high"] < prices["low"]:
            raise ValueError("high cannot be below low.")
        volume = _decimal(self.volume, "volume", optional=True)
        if volume is not None and volume < 0:
            raise ValueError("volume must be nonnegative.")
        expected = candle_identity(
            dataset_id=self.dataset_id, schema_version=self.schema_version,
            source=self.source, exchange=self.exchange, symbol=self.symbol,
            timeframe=self.timeframe, open_time=opened, close_time=closed,
        )
        if self.id != expected:
            raise ValueError("Candle identity does not match its immutable coordinates.")


def candle_identity(*, dataset_id: str, schema_version: str, source: str, exchange: str,
                    symbol: str, timeframe: CanonicalTimeframe, open_time: datetime,
                    close_time: datetime) -> str:
    return _identity(("historical-candle-v1", dataset_id, schema_version, source,
                      exchange, symbol, timeframe.value, _timestamp(open_time),
                      _timestamp(close_time)))


def normalize_historical_candle(raw: Mapping[str, object], *, dataset_id: str,
                                schema_version: str, source: str, exchange: str) -> HistoricalCandle:
    """Normalize an already-exact mapping. Floats are deliberately rejected."""
    required = {"symbol", "timeframe", "open_time", "close_time", "open", "high", "low", "close", "is_closed"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"Missing historical candle fields: {sorted(missing)}")
    try:
        timeframe = CanonicalTimeframe(raw["timeframe"])
    except (ValueError, TypeError) as error:
        raise ValueError("Unsupported canonical timeframe.") from error
    open_time = _utc(raw["open_time"], "open_time")
    close_time = _utc(raw["close_time"], "close_time")
    identity = candle_identity(
        dataset_id=dataset_id, schema_version=schema_version, source=source,
        exchange=exchange, symbol=_required_text(raw["symbol"], "symbol"),
        timeframe=timeframe, open_time=open_time, close_time=close_time,
    )
    return HistoricalCandle(
        id=identity, dataset_id=dataset_id, schema_version=schema_version,
        source=source, exchange=exchange, symbol=str(raw["symbol"]).strip(),
        timeframe=timeframe, open_time=open_time, close_time=close_time,
        open=_decimal(raw["open"], "open"), high=_decimal(raw["high"], "high"),
        low=_decimal(raw["low"], "low"), close=_decimal(raw["close"], "close"),
        volume=_decimal(raw.get("volume"), "volume", optional=True),
        is_closed=raw["is_closed"],
    )


def normalize_hyperliquid_candle(raw: Mapping[str, object], *, dataset_id: str,
                                 schema_version: str, source: str = "hyperliquid-archive",
                                 exchange: str = "hyperliquid") -> HistoricalCandle:
    """Normalize exact Hyperliquid `t/T/o/h/l/c/v` history without float coercion."""
    required = {"s", "i", "t", "T", "o", "h", "l", "c", "is_closed"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"Missing Hyperliquid candle fields: {sorted(missing)}")
    for name in ("t", "T"):
        if isinstance(raw[name], bool) or not isinstance(raw[name], int):
            raise TypeError(f"{name} must be an exact integer epoch millisecond value.")

    def exact_number(value: object, field: str, *, optional: bool = False) -> Decimal | None:
        if value is None and optional:
            return None
        if isinstance(value, float):
            raise TypeError(f"{field} cannot be a binary float.")
        if isinstance(value, Decimal):
            result = value
        elif isinstance(value, str):
            try:
                result = Decimal(value)
            except Exception as error:
                raise ValueError(f"{field} must be an exact decimal string.") from error
        else:
            raise TypeError(f"{field} must be Decimal or an exact decimal string.")
        if not result.is_finite():
            raise ValueError(f"{field} must be finite.")
        return result

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    canonical = {
        "symbol": raw["s"], "timeframe": raw["i"],
        "open_time": epoch + timedelta(milliseconds=raw["t"]),
        "close_time": epoch + timedelta(milliseconds=raw["T"]),
        "open": exact_number(raw["o"], "o"), "high": exact_number(raw["h"], "h"),
        "low": exact_number(raw["l"], "l"), "close": exact_number(raw["c"], "c"),
        "volume": exact_number(raw.get("v"), "v", optional=True),
        "is_closed": raw["is_closed"],
    }
    return normalize_historical_candle(
        canonical, dataset_id=dataset_id, schema_version=schema_version,
        source=source, exchange=exchange,
    )
@dataclass(frozen=True)
class Gap:
    symbol: str
    timeframe: CanonicalTimeframe
    previous_candle_id: str
    next_candle_id: str
    expected_open_time: datetime
    actual_open_time: datetime
    missing_count: int


@dataclass(frozen=True)
class HistoricalDataset:
    dataset_id: str
    schema_version: str
    source: str
    exchange: str
    symbol: str
    candles: tuple[HistoricalCandle, ...]
    gap_policy: GapPolicy
    gaps: tuple[Gap, ...]
    validation_status: ValidationStatus
    fingerprint: str

    def __post_init__(self) -> None:
        for name in ("dataset_id", "schema_version", "source", "exchange", "symbol", "fingerprint"):
            _required_text(getattr(self, name), name)
        if not isinstance(self.candles, tuple) or not self.candles:
            raise ValueError("A validated dataset requires an immutable nonempty candle sequence.")
        if any((c.dataset_id, c.schema_version, c.source, c.exchange, c.symbol) !=
               (self.dataset_id, self.schema_version, self.source, self.exchange, self.symbol)
               for c in self.candles):
            raise ValueError("Validated dataset candle lineage mismatch.")
        expected = tuple(sorted(self.candles, key=lambda c: (c.open_time, c.symbol, c.timeframe.value, c.id)))
        if self.candles != expected or len({c.id for c in self.candles}) != len(self.candles):
            raise ValueError("Validated dataset ordering or identity is invalid.")
        if self.fingerprint != dataset_fingerprint(self.candles):
            raise ValueError("Validated dataset fingerprint mismatch.")
        if self.validation_status is ValidationStatus.VALID and self.gaps:
            raise ValueError("A gap-free validation status cannot contain gaps.")
        if self.validation_status is ValidationStatus.VALID_WITH_GAPS and not self.gaps:
            raise ValueError("Gap validation status requires recorded gaps.")

    def candles_for(self, timeframe: CanonicalTimeframe) -> tuple[HistoricalCandle, ...]:
        return tuple(candle for candle in self.candles if candle.timeframe is timeframe)


def dataset_fingerprint(candles: tuple[HistoricalCandle, ...]) -> str:
    rows = []
    for candle in candles:
        rows.append("\x1e".join((
            candle.id, candle.symbol, candle.timeframe.value, _timestamp(candle.open_time),
            _timestamp(candle.close_time), _canonical_decimal(candle.open),
            _canonical_decimal(candle.high), _canonical_decimal(candle.low),
            _canonical_decimal(candle.close), _canonical_decimal(candle.volume), "1",
        )))
    return sha256("\n".join(rows).encode("utf-8")).hexdigest()


def validate_dataset(candles: tuple[HistoricalCandle, ...], *, dataset_id: str,
                     schema_version: str, source: str, exchange: str,
                     gap_policy: GapPolicy = GapPolicy.REJECT,
                     validation_time: datetime) -> HistoricalDataset:
    _required_text(dataset_id, "dataset_id"); _required_text(schema_version, "schema_version")
    _required_text(source, "source"); _required_text(exchange, "exchange")
    if not isinstance(candles, tuple):
        raise TypeError("candles must be an immutable tuple.")
    if not candles:
        raise ValueError("A historical dataset requires at least one candle.")
    if not isinstance(gap_policy, GapPolicy):
        raise TypeError("gap_policy must be GapPolicy.")
    cutoff = _utc(validation_time, "validation_time")
    ids = [candle.id for candle in candles]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate candle identity.")
    coordinates = [(c.symbol, c.timeframe, c.open_time) for c in candles]
    if len(coordinates) != len(set(coordinates)):
        raise ValueError("Duplicate candle interval.")
    expected_order = sorted(candles, key=lambda c: (c.open_time, c.symbol, c.timeframe.value, c.id))
    if list(candles) != expected_order:
        raise ValueError("Candles must use strict canonical chronological ordering.")
    symbols = {candle.symbol for candle in candles}
    if len(symbols) != 1:
        raise ValueError("A dataset is isolated to one symbol.")
    symbol = next(iter(symbols))
    for candle in candles:
        if (candle.dataset_id, candle.schema_version, candle.source, candle.exchange) != (dataset_id, schema_version, source, exchange):
            raise ValueError("Candle dataset identity/version/source mismatch.")
        if candle.close_time > cutoff:
            raise ValueError("Future or currently incomplete candle is ineligible.")
    grouped: dict[tuple[str, CanonicalTimeframe], list[HistoricalCandle]] = {}
    for candle in candles:
        grouped.setdefault((candle.symbol, candle.timeframe), []).append(candle)
    gaps: list[Gap] = []
    for (symbol, timeframe), group in grouped.items():
        for previous, current in zip(group, group[1:]):
            if current.open_time < previous.close_time:
                raise ValueError("Overlapping candle intervals are forbidden.")
            if current.open_time > previous.close_time:
                seconds = int((current.open_time - previous.close_time).total_seconds())
                duration = int(timeframe.duration.total_seconds())
                if seconds % duration:
                    raise ValueError("Gap boundary is not aligned to the timeframe.")
                gaps.append(Gap(symbol, timeframe, previous.id, current.id,
                                previous.close_time, current.open_time, seconds // duration))
    if gaps and gap_policy is GapPolicy.REJECT:
        raise ValueError("Dataset contains gaps under REJECT policy.")
    frozen_gaps = tuple(gaps)
    return HistoricalDataset(
        dataset_id, schema_version, source, exchange, symbol, candles, gap_policy,
        frozen_gaps, ValidationStatus.VALID_WITH_GAPS if gaps else ValidationStatus.VALID,
        dataset_fingerprint(candles),
    )


@dataclass(frozen=True)
class MultiTimeframeView:
    dataset: HistoricalDataset

    def visible(self, *, timeframe: CanonicalTimeframe, as_of: datetime) -> tuple[HistoricalCandle, ...]:
        boundary = _utc(as_of, "as_of")
        return tuple(c for c in self.dataset.candles_for(timeframe) if c.close_time <= boundary)

    def latest(self, *, timeframe: CanonicalTimeframe, as_of: datetime) -> HistoricalCandle | None:
        visible = self.visible(timeframe=timeframe, as_of=as_of)
        return visible[-1] if visible else None
