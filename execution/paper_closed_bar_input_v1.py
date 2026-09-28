"""Validate an immutable CSV byte snapshot for paper valuation, never fills."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import hashlib
import io
import json

from backtesting.execution_accounting_v2.archive_scanner import _rows_csv, _decimal
from backtesting.execution_accounting_v2.accounting import PriceEvidenceV2

VERSION = "paper-closed-btc-mark-v1"
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000
DURATIONS = {"1m": timedelta(minutes=1), "15m": timedelta(minutes=15)}


class ClosedBTCBarError(ValueError):
    pass


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ClosedBTCBarError("explicit UTC timestamp required")


def _sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ClosedBTCBarError("expected source SHA-256 is invalid")


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ClosedBTCMarkV1:
    mark: PriceEvidenceV2
    timeframe: str
    open_time: datetime
    source_sha256: str
    source_byte_count: int
    source_row_count: int
    bar_fingerprint: str
    receipt_id: str
    trading_authority: bool = False

    def __post_init__(self):
        if self.trading_authority is not False:
            raise ClosedBTCBarError("closed bar receipt cannot grant trading authority")


def validate_closed_btc_mark(*, payload: bytes, expected_sha256: str,
        timeframe: str, available_at: datetime, as_of: datetime,
        maximum_bar_age: timedelta, instrument_id: str,
        mark_specification_id: str, source_version: str,
        previous: ClosedBTCMarkV1 | None = None, market: str = "BTC",
        contract_id: str | None = None) -> ClosedBTCMarkV1:
    """Return the latest fully validated close with explicit source lineage.

    The caller supplies the real availability timestamp and expected snapshot
    hash. Neither a hash nor an is_closed flag authenticates the provider. This
    function performs no I/O and never uses file mtime as market availability.
    """
    _utc(available_at); _utc(as_of); _sha(expected_sha256)
    if (market,instrument_id,contract_id) not in (("BTC","BTC",None),
            ("BTC-PERP","BTC","BTC-PERP")):
        raise ClosedBTCBarError("unsupported BTC valuation identity")
    if timeframe not in DURATIONS or not timedelta(0) < maximum_bar_age <= DURATIONS[timeframe] + timedelta(minutes=1):
        raise ClosedBTCBarError("unsupported timeframe or freshness policy")
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
        raise ClosedBTCBarError("snapshot size/type invalid")
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != expected_sha256:
        raise ClosedBTCBarError("source snapshot checksum mismatch")
    if available_at > as_of:
        raise ClosedBTCBarError("source is not yet available")
    try:
        # Reuse the retained-archive validator on these same immutable bytes.
        intervals = _rows_csv(payload, "BTC", timeframe)
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline="")))
    except (ValueError, UnicodeError, csv.Error, KeyError, TypeError) as exc:
        raise ClosedBTCBarError("invalid closed BTC CSV evidence") from exc
    if not 0 < len(rows) <= MAX_ROWS:
        raise ClosedBTCBarError("snapshot row count invalid")
    duration = DURATIONS[timeframe]
    previous_close = None
    for row, (opened, closed) in zip(rows, intervals):
        if closed - opened != duration or opened.second or opened.microsecond or opened.minute % int(duration.total_seconds() // 60):
            raise ClosedBTCBarError("bar duration/alignment invalid")
        if previous_close is not None and opened != previous_close:
            raise ClosedBTCBarError("duplicate, gap, or regressing bar")
        if closed > available_at:
            raise ClosedBTCBarError("bar closes after source availability")
        if any(_decimal(row[key], key) <= 0 for key in ("open", "high", "low", "close")):
            raise ClosedBTCBarError("BTC prices must be positive")
        previous_close = closed
    opened, closed = intervals[-1]
    if as_of - closed > maximum_bar_age:
        raise ClosedBTCBarError("latest closed bar is stale")
    row = rows[-1]
    identity = {"version":VERSION, "row":row, "market":market,
        "instrument_id":instrument_id,"contract_id":contract_id,
        "mark_specification_id":mark_specification_id, "source_version":source_version}
    bar_id = _fingerprint(identity)
    if previous is not None:
        if not isinstance(previous, ClosedBTCMarkV1) or previous.trading_authority is not False:
            raise ClosedBTCBarError("invalid previous mark receipt")
        if (previous.timeframe,previous.mark.market,previous.mark.instrument_id,
                previous.mark.contract_id,previous.mark.specification_id,previous.mark.source_version) != (
                timeframe,market,instrument_id,contract_id,mark_specification_id,source_version):
            raise ClosedBTCBarError("previous mark lineage differs")
        for prior_row, (prior_open, _) in zip(rows, intervals):
            if prior_open == previous.open_time:
                retained_id = _fingerprint({**identity, "row":prior_row})
                if retained_id != previous.bar_fingerprint:
                    raise ClosedBTCBarError("conflicting revision to retained bar")
        if opened == previous.open_time:
            if bar_id != previous.bar_fingerprint:
                raise ClosedBTCBarError("conflicting revision to retained bar")
            if available_at < previous.mark.available_at:
                raise ClosedBTCBarError("source availability regressed")
            # Preserve first-known availability and identity on polling replay.
            return previous
        if opened != previous.mark.observed_at or available_at < previous.mark.available_at:
            raise ClosedBTCBarError("mark sequence gap, regression, or availability regression")
    core = {**identity, "source_sha256":actual_hash, "available_at":available_at.isoformat()}
    receipt_id = _fingerprint(core)
    mark = PriceEvidenceV2("price-evidence-v2-1", receipt_id, market, instrument_id,
        contract_id, closed, available_at, Decimal(row["close"]), "MARK",
        mark_specification_id, source_version)
    return ClosedBTCMarkV1(mark, timeframe, opened, actual_hash, len(payload),
        len(rows), bar_id, receipt_id, False)
