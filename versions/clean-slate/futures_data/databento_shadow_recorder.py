"""Read-only Databento MES/MNQ shadow-recorder boundary.

The module is deliberately SDK- and credential-agnostic.  A separately owned
transport supplies already decoded OHLCV-1m records.  This boundary validates
those records, computes bounded restart-replay windows, and writes immutable
hash chains.  It has no account, order, signing, or execution surface.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping, Protocol


SCHEMA_VERSION = "databento-micro-futures-shadow-v1"
DATASET = "GLBX.MDP3"
SOURCE_SCHEMA = "ohlcv-1m"
FINALITY_LAG = timedelta(minutes=2)
MAX_INTRADAY_REPLAY = timedelta(hours=24)
DEFAULT_BOOTSTRAP = timedelta(hours=1)
LANES = {"ES": "MES.FUT", "NQ": "MNQ.FUT"}
ZERO_HASH = "0" * 64


class DatabentoShadowError(ValueError):
    """Fail-closed validation error for the shadow data boundary."""


class MinuteSource(Protocol):
    source_id: str

    def fetch(self, *, dataset: str, schema: str, parent_symbol: str,
              start: datetime, end: datetime) -> Iterable[Mapping[str, object]]: ...


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise DatabentoShadowError(f"{field} must be timezone-aware")
    converted = value.astimezone(timezone.utc)
    if converted.second or converted.microsecond:
        raise DatabentoShadowError(f"{field} must be minute-aligned")
    return converted


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _decimal(value: object, field: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, float):
        raise DatabentoShadowError(f"binary float forbidden for {field}")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DatabentoShadowError(f"invalid {field}") from exc
    if not result.is_finite() or (result < 0 if nonnegative else result <= 0):
        raise DatabentoShadowError(f"invalid {field}")
    return result


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _atomic(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(_canonical(document) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _read_manifest(path: Path, *, lane: str) -> dict:
    try:
        document = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatabentoShadowError("manifest unreadable") from exc
    if not isinstance(document, dict):
        raise DatabentoShadowError("manifest schema invalid")
    digest = document.pop("manifest_sha256", None)
    if digest != sha256(_canonical(document)).hexdigest():
        raise DatabentoShadowError("manifest digest invalid")
    if (document.get("schema_version") != SCHEMA_VERSION
            or document.get("source") != "databento-live"
            or document.get("lane") != lane
            or document.get("parent_symbol") != LANES.get(lane)
            or document.get("trading_authority") is not False
            or document.get("order_endpoints_present") is not False):
        raise DatabentoShadowError("manifest boundary invalid")
    return {**document, "manifest_sha256": digest}


@dataclass(frozen=True)
class ReplayWindow:
    start: datetime
    end: datetime
    reason: str

    def __post_init__(self) -> None:
        start, end = _utc(self.start, "start"), _utc(self.end, "end")
        if start >= end or end - start > MAX_INTRADAY_REPLAY:
            raise DatabentoShadowError("invalid replay window")
        if self.reason not in {"BOOTSTRAP", "RESTART_CONTINUATION"}:
            raise DatabentoShadowError("invalid replay reason")


def replay_window(*, observed_at: datetime, latest_close: datetime | None,
                  bootstrap: timedelta = DEFAULT_BOOTSTRAP) -> ReplayWindow:
    now = observed_at.astimezone(timezone.utc)
    end = (now - FINALITY_LAG).replace(second=0, microsecond=0)
    floor = end - MAX_INTRADAY_REPLAY
    if latest_close is None:
        if bootstrap <= timedelta(0) or bootstrap > MAX_INTRADAY_REPLAY:
            raise DatabentoShadowError("invalid bootstrap duration")
        return ReplayWindow(max(floor, end - bootstrap), end, "BOOTSTRAP")
    latest = _utc(latest_close, "latest_close")
    if latest > end:
        raise DatabentoShadowError("archive head is later than finality horizon")
    if latest < floor:
        raise DatabentoShadowError("restart exceeds 24-hour replay boundary")
    return ReplayWindow(latest, end, "RESTART_CONTINUATION")


@dataclass(frozen=True)
class ShadowMinute:
    lane: str
    parent_symbol: str
    instrument_id: int
    raw_symbol: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if self.lane not in LANES or self.parent_symbol != LANES[self.lane]:
            raise DatabentoShadowError("lane or parent-symbol mismatch")
        opened, closed = _utc(self.open_time, "open_time"), _utc(self.close_time, "close_time")
        if closed - opened != timedelta(minutes=1):
            raise DatabentoShadowError("bar must cover exactly one minute")
        if not isinstance(self.instrument_id, int) or self.instrument_id <= 0 or not self.raw_symbol:
            raise DatabentoShadowError("instrument lineage required")
        o, h, l, c = self.open, self.high, self.low, self.close
        if h < max(o, c) or l > min(o, c) or h < l:
            raise DatabentoShadowError("invalid OHLC geometry")

    def document(self) -> dict:
        return {
            "close": format(self.close, "f"), "close_time_utc": _iso(self.close_time),
            "dataset": DATASET, "finalized": True, "high": format(self.high, "f"),
            "instrument_id": self.instrument_id, "lane": self.lane,
            "low": format(self.low, "f"), "open": format(self.open, "f"),
            "open_time_utc": _iso(self.open_time), "parent_symbol": self.parent_symbol,
            "paper_only": True, "raw_symbol": self.raw_symbol,
            "schema_version": SCHEMA_VERSION, "source_schema": SOURCE_SCHEMA,
            "trading_authority": False, "volume": format(self.volume, "f"),
        }


def normalize_record(record: Mapping[str, object], *, lane: str,
                     finality_horizon: datetime) -> ShadowMinute:
    required = {"ts_event", "instrument_id", "raw_symbol", "open", "high", "low", "close", "volume"}
    if not isinstance(record, Mapping) or not required <= set(record):
        raise DatabentoShadowError("decoded OHLCV-1m schema incomplete")
    timestamp = record["ts_event"]
    if isinstance(timestamp, int):
        opened = datetime.fromtimestamp(timestamp / 1_000_000_000, timezone.utc)
    elif isinstance(timestamp, str):
        opened = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    elif isinstance(timestamp, datetime):
        opened = timestamp
    else:
        raise DatabentoShadowError("unsupported event timestamp")
    opened = _utc(opened, "ts_event")
    closed = opened + timedelta(minutes=1)
    if closed > _utc(finality_horizon, "finality_horizon"):
        raise DatabentoShadowError("forming minute rejected")
    values = {name: _decimal(record[name], name, nonnegative=name == "volume")
              for name in ("open", "high", "low", "close", "volume")}
    return ShadowMinute(lane, LANES.get(lane, ""), int(record["instrument_id"]),
                        str(record["raw_symbol"]), opened, closed, **values)


def _read_chain(path: Path, *, initial_hash: str = ZERO_HASH) -> tuple[list[dict], str, datetime | None]:
    rows: list[dict] = []
    previous = initial_hash
    latest = None
    if not path.exists():
        return rows, previous, latest
    for raw in path.read_bytes().splitlines():
        row = json.loads(raw)
        digest = row.pop("record_sha256", None)
        if row.get("schema_version") != SCHEMA_VERSION or row.get("previous_record_sha256") != previous:
            raise DatabentoShadowError("archive hash chain invalid")
        if digest != sha256(_canonical(row)).hexdigest():
            raise DatabentoShadowError("archive record digest invalid")
        opened = datetime.fromisoformat(str(row["open_time_utc"]).replace("Z", "+00:00"))
        if latest is not None and opened <= latest:
            raise DatabentoShadowError("archive chronology invalid")
        rows.append({**row, "record_sha256": digest})
        previous, latest = digest, opened
    return rows, previous, latest


def append_minutes(*, archive_root: Path, lane: str, minutes: Iterable[ShadowMinute],
                   observed_at: datetime, replay: ReplayWindow, source_id: str) -> dict:
    if lane not in LANES or source_id != "databento-live":
        raise DatabentoShadowError("source boundary rejected")
    ordered = tuple(sorted(minutes, key=lambda item: item.open_time))
    if any(item.lane != lane for item in ordered):
        raise DatabentoShadowError("cross-lane contamination")
    if len({item.open_time for item in ordered}) != len(ordered):
        raise DatabentoShadowError("duplicate input minute")
    lane_root = Path(archive_root) / lane
    lane_root.mkdir(parents=True, exist_ok=True)
    lock_path = lane_root / ".writer.lock"
    try:
        lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise DatabentoShadowError("single-writer lock active") from exc
    try:
        os.write(lock, str(os.getpid()).encode("ascii")); os.close(lock)
        existing_by_time: dict[datetime, dict] = {}
        files = sorted(lane_root.glob("????-??-??.jsonl"))
        head = ZERO_HASH
        last_open = None
        count = 0
        for path in files:
            rows, file_head, file_last = _read_chain(path, initial_hash=head)
            for row in rows:
                stamp = datetime.fromisoformat(row["open_time_utc"].replace("Z", "+00:00"))
                existing_by_time[stamp] = row
            if rows:
                head, last_open = file_head, file_last
            count += len(rows)
        accepted = 0
        for minute in ordered:
            document = minute.document()
            current = existing_by_time.get(minute.open_time)
            if current is not None:
                comparable = {key: value for key, value in current.items()
                              if key not in {"previous_record_sha256", "record_sha256"}}
                if comparable != document:
                    raise DatabentoShadowError("provider revision conflicts with immutable minute")
                continue
            if last_open is not None and minute.open_time <= last_open:
                raise DatabentoShadowError("late insertion into immutable chain rejected")
            body = {**document, "previous_record_sha256": head}
            digest = sha256(_canonical(body)).hexdigest()
            path = lane_root / f"{minute.open_time.date().isoformat()}.jsonl"
            with path.open("ab") as stream:
                stream.write(_canonical({**body, "record_sha256": digest}) + b"\n")
                stream.flush(); os.fsync(stream.fileno())
            head, last_open, count, accepted = digest, minute.open_time, count + 1, accepted + 1
        manifest = {
            "account_access": False, "archive_integrity_verified": True,
            "dataset": DATASET, "head_record_sha256": head,
            "last_open_time_utc": _iso(last_open) if last_open else None,
            "lane": lane, "order_endpoints_present": False, "parent_symbol": LANES[lane],
            "paper_only": True, "record_count": count,
            "replay_end_utc": _iso(replay.end), "replay_reason": replay.reason,
            "replay_start_utc": _iso(replay.start), "schema_version": SCHEMA_VERSION,
            "source": source_id, "source_schema": SOURCE_SCHEMA, "state": "SHADOW_RECORDING",
            "trading_authority": False, "updated_at": _iso(observed_at.astimezone(timezone.utc)),
        }
        manifest["manifest_sha256"] = sha256(_canonical(manifest)).hexdigest()
        _atomic(lane_root / "manifest.json", manifest)
        return {**manifest, "accepted_record_count": accepted}
    finally:
        lock_path.unlink(missing_ok=True)


def record_once(*, source: MinuteSource, archive_root: Path,
                observed_at: datetime | None = None) -> dict:
    if source.source_id != "databento-live":
        raise DatabentoShadowError("unexpected transport source")
    now = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    result = {}
    for lane, parent in LANES.items():
        manifest_path = Path(archive_root) / lane / "manifest.json"
        latest_close = None
        if manifest_path.exists():
            manifest = _read_manifest(manifest_path, lane=lane)
            latest_open = manifest.get("last_open_time_utc")
            if latest_open:
                latest_close = datetime.fromisoformat(latest_open.replace("Z", "+00:00")) + timedelta(minutes=1)
        window = replay_window(observed_at=now, latest_close=latest_close)
        decoded = tuple(source.fetch(dataset=DATASET, schema=SOURCE_SCHEMA,
                                     parent_symbol=parent, start=window.start, end=window.end))
        minutes = tuple(normalize_record(row, lane=lane, finality_horizon=window.end) for row in decoded)
        result[lane] = append_minutes(archive_root=archive_root, lane=lane, minutes=minutes,
                                      observed_at=now, replay=window, source_id=source.source_id)
    return {"schema_version": SCHEMA_VERSION, "state": "SHADOW_COMPLETE",
            "lanes": result, "paper_only": True, "trading_authority": False}
