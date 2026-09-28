"""BOT 2.0 Phase 1 contracts.  These are data-only and have no execution authority."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

RAW_EVENT_SCHEMA_V1 = "bot2-raw-market-event-v1"
RAW_EVENT_SCHEMA = "bot2-raw-market-event-v2"
DATA_QUALITY_SCHEMA = "bot2-data-quality-report-v1"
DATASET_MANIFEST_SCHEMA = "bot2-dataset-manifest-v2"
TIMESTAMP_SOURCES = frozenset({"HISTORICAL_EXCHANGE_EVENT", "LIVE_PROVIDER_CAPTURE", "TEST_FIXTURE", "UNSPECIFIED"})


class QualityReason(str, Enum):
    INVALID_SCHEMA = "INVALID_SCHEMA"
    INVALID_INSTRUMENT = "INVALID_INSTRUMENT"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_VOLUME = "INVALID_VOLUME"
    MISSING_TIMESTAMP = "MISSING_TIMESTAMP"
    TIMESTAMP_REGRESSION = "TIMESTAMP_REGRESSION"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    SEQUENCE_REGRESSION = "SEQUENCE_REGRESSION"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    STALE_EVENT = "STALE_EVENT"
    INTERVAL_GAP = "INTERVAL_GAP"
    CROSS_MARKET_SKEW = "CROSS_MARKET_SKEW"
    FUTURE_EVENT = "FUTURE_EVENT"
    EMPTY_DATASET = "EMPTY_DATASET"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamps must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """Immutable normalized event retaining exchange and local receipt clocks."""

    instrument: str
    venue: str
    event_type: str
    exchange_time: datetime
    receipt_time: datetime | None
    price: float
    volume: float
    sequence: int | None = None
    event_id: str | None = None
    session_id: str | None = None
    contract_id: str | None = None
    schema_version: str = RAW_EVENT_SCHEMA
    receive_timestamp_available: bool | None = None
    timestamp_source: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        if self.schema_version not in (RAW_EVENT_SCHEMA, RAW_EVENT_SCHEMA_V1):
            raise ValueError("unsupported raw event schema")
        object.__setattr__(self, "exchange_time", _utc(self.exchange_time))
        if self.receipt_time is not None:
            object.__setattr__(self, "receipt_time", _utc(self.receipt_time))
        available = self.receipt_time is not None if self.receive_timestamp_available is None else self.receive_timestamp_available
        if available != (self.receipt_time is not None):
            raise ValueError("receive timestamp availability must match timestamp presence")
        if self.schema_version == RAW_EVENT_SCHEMA_V1 and not available:
            raise ValueError("v1 raw events require a receive timestamp; use v2 for historical exchange-only data")
        if self.timestamp_source not in TIMESTAMP_SOURCES:
            raise ValueError("unsupported timestamp provenance")
        if self.timestamp_source == "HISTORICAL_EXCHANGE_EVENT" and available:
            raise ValueError("historical exchange-only events cannot claim a receive timestamp")
        object.__setattr__(self, "receive_timestamp_available", available)
        if not self.instrument or not self.venue or not self.event_type:
            raise ValueError("instrument, venue, and event_type are required")

    @property
    def identity(self) -> tuple[Any, ...]:
        return (self.instrument, self.event_type, self.exchange_time.isoformat(),
                self.price, self.volume, self.sequence, self.event_id)

    @property
    def event_timestamp(self) -> datetime:
        return self.exchange_time

    @property
    def receive_timestamp(self) -> datetime | None:
        return self.receipt_time

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["exchange_time"] = self.exchange_time.isoformat().replace("+00:00", "Z")
        result["receipt_time"] = self.receipt_time.isoformat().replace("+00:00", "Z") if self.receipt_time else None
        result["event_timestamp"] = result["exchange_time"]
        result["receive_timestamp"] = result["receipt_time"]
        return result


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    state: str
    schema_version: str = DATA_QUALITY_SCHEMA
    checked_events: int = 0
    accepted_events: int = 0
    reason_counts: Mapping[str, int] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    first_exchange_time: str | None = None
    last_exchange_time: str | None = None
    max_latency_seconds: float | None = None
    event_hash: str | None = None
    trading_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"reason_counts": dict(self.reason_counts),
                               "reasons": list(self.reasons)}


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    dataset_id: str
    source: str
    instruments: tuple[str, ...]
    start_exchange_time: str
    end_exchange_time: str
    schema_version: str
    validation_status: str
    source_sha256: str
    normalized_sha256: str
    code_commit: str
    configuration_sha256: str
    event_count: int
    quality_report: DataQualityReport
    created_at: str
    manifest_schema_version: str = DATASET_MANIFEST_SCHEMA
    timestamp_provenance: Mapping[str, int] = field(default_factory=dict)
    trading_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"instruments": list(self.instruments),
                               "timestamp_provenance": dict(self.timestamp_provenance),
                               "quality_report": self.quality_report.to_dict()}
