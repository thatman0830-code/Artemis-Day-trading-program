"""Read-only, fail-closed scanner for retained OHLC evidence archives."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
import io
import json
from pathlib import Path

from .oos_evidence import EvidenceFileV1, MissingIntervalV1
from .specifications import canonical_fingerprint

ARCHIVE_SCAN_VERSION = "ARCHIVE_EVIDENCE_SCAN_V1"
_DURATIONS = {"1m": timedelta(minutes=1), "5m": timedelta(minutes=5),
              "15m": timedelta(minutes=15), "1h": timedelta(hours=1),
              "4h": timedelta(hours=4)}


class ArchiveFormat(str, Enum):
    CLOSED_CANDLE_CSV = "CLOSED_CANDLE_CSV"
    FUTURES_NORMALIZED_JSONL = "FUTURES_NORMALIZED_JSONL"


class ArchiveScanError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ArchiveScanV1:
    scan_id: str
    market: str
    archive_format: ArchiveFormat
    evidence_file: EvidenceFileV1
    missing_intervals: tuple[MissingIntervalV1, ...]
    version: str = ARCHIVE_SCAN_VERSION
    trading_authority: bool = False


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ArchiveScanError(f"{field} must be an ISO UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArchiveScanError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ArchiveScanError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ArchiveScanError(f"{field} must be an exact decimal string")
    try: result = Decimal(str(value))
    except InvalidOperation as exc: raise ArchiveScanError(f"{field} is malformed") from exc
    if not result.is_finite(): raise ArchiveScanError(f"{field} must be finite")
    return result


def _validate_ohlcv(row: dict, market: str, timeframe: str) -> None:
    if row.get("market") != market or row.get("timeframe") != timeframe:
        raise ArchiveScanError("market or timeframe contamination")
    opened, high, low, closed = (_decimal(row[key], key) for key in ("open", "high", "low", "close"))
    volume = _decimal(row["volume"], "volume")
    if high < max(opened, closed) or low > min(opened, closed) or high < low or volume < 0:
        raise ArchiveScanError("OHLCV invariant violation")


def _resolve(repository: Path, relative_path: str) -> tuple[Path, str]:
    normalized = relative_path.replace("\\", "/")
    if not normalized or normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise ArchiveScanError("archive path must be repository-relative")
    root = repository.resolve(strict=True); path = (root / normalized).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ArchiveScanError("archive path escapes repository or is not a file")
    return path, normalized


def _rows_csv(payload: bytes, market: str, timeframe: str) -> list[tuple[datetime, datetime]]:
    try: text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise ArchiveScanError("CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    expected = ["symbol","timeframe","open_time","close_time","open","high","low","close","volume","is_closed"]
    if reader.fieldnames != expected: raise ArchiveScanError("CSV header mismatch")
    result = []
    for item in reader:
        if (set(item) != set(expected) or any(value is None for value in item.values())
                or item["is_closed"].lower() != "true"):
            raise ArchiveScanError("CSV row shape or finalization mismatch")
        row = dict(item); row["market"] = row.pop("symbol")
        _validate_ohlcv(row, market, timeframe)
        result.append((_utc(row["open_time"], "open_time"), _utc(row["close_time"], "close_time")))
    return result


def _rows_jsonl(payload: bytes, market: str, timeframe: str) -> list[tuple[datetime, datetime]]:
    if timeframe != "1m": raise ArchiveScanError("normalized futures JSONL must be 1m")
    try: lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc: raise ArchiveScanError("JSONL is not UTF-8") from exc
    result = []
    for line in lines:
        try: item = json.loads(line)
        except json.JSONDecodeError as exc: raise ArchiveScanError("JSONL row is malformed") from exc
        required = {"root","window_start_ns","open","high","low","close","volume"}
        if not isinstance(item, dict) or not required <= set(item): raise ArchiveScanError("JSONL row shape mismatch")
        ns = item["window_start_ns"]
        if isinstance(ns, bool) or not isinstance(ns, int) or ns < 0 or ns % 1_000_000_000:
            raise ArchiveScanError("window_start_ns is invalid")
        row = {**item, "market": item["root"], "timeframe": "1m"}; _validate_ohlcv(row, market, timeframe)
        opened = datetime.fromtimestamp(ns / 1_000_000_000, timezone.utc)
        result.append((opened, opened + timedelta(minutes=1)))
    return result


def scan_archive(*, repository: Path, relative_path: str, market: str,
                 timeframe: str, archive_format: ArchiveFormat) -> ArchiveScanV1:
    if (market not in {"BTC", "ES", "NQ"} or timeframe not in _DURATIONS
            or not isinstance(archive_format, ArchiveFormat)):
        raise ArchiveScanError("unsupported market or timeframe")
    path, normalized = _resolve(repository, relative_path); payload = path.read_bytes()
    if not payload: raise ArchiveScanError("archive is empty")
    rows = (_rows_csv(payload, market, timeframe) if archive_format is ArchiveFormat.CLOSED_CANDLE_CSV
            else _rows_jsonl(payload, market, timeframe))
    if not rows: raise ArchiveScanError("archive contains no records")
    duration = _DURATIONS[timeframe]; previous_open = None; gaps = []
    for opened, closed in rows:
        if closed - opened != duration: raise ArchiveScanError("bar duration mismatch")
        if previous_open is not None:
            if opened <= previous_open: raise ArchiveScanError("duplicate or regressing timestamp")
            expected = previous_open + duration
            if opened > expected:
                gaps.append(MissingIntervalV1(timeframe, expected, opened,
                                              "UNCLASSIFIED_ARCHIVE_DISCONTINUITY"))
        previous_open = opened
    evidence = EvidenceFileV1(normalized, sha256(payload).hexdigest(), len(payload), len(rows),
                              timeframe, rows[0][0], rows[-1][1])
    scan_id = canonical_fingerprint(ARCHIVE_SCAN_VERSION, market, archive_format.value,
                                    evidence, tuple(gaps), False)
    return ArchiveScanV1(scan_id, market, archive_format, evidence, tuple(gaps))
