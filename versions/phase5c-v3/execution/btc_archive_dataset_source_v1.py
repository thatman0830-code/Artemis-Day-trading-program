"""Build one canonical dataset from an unchanged five-timeframe BTC archive."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path

from backtesting.downloader import CANDLE_SCHEMA, CSV_FIELDS, _ms
from backtesting.market_data import (
    CanonicalTimeframe, GapPolicy, HistoricalDataset, normalize_hyperliquid_candle,
    validate_dataset,
)
from backtesting.recorder import ARCHIVE_SCHEMA
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from execution.btc_archive_snapshot_source_v1 import (
    EXPECTED_TIMEFRAMES, MAXIMUM_MANIFEST_BYTES, BTCArchiveSnapshotError,
    _plain_file, _time, _utc,
)


VERSION = "btc-archive-dataset-source-v1"
MAXIMUM_CSV_BYTES = 256 * 1024 * 1024


class BTCArchiveDatasetError(RuntimeError):
    pass


def _fail(message: str, error: Exception | None = None):
    if error is None:
        raise BTCArchiveDatasetError(message)
    raise BTCArchiveDatasetError(message) from error


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _dataset_id(manifest_sha256: str, checksums: dict[str, str]) -> str:
    body = {"version": VERSION, "manifest_sha256": manifest_sha256,
            "checksums": checksums}
    return hashlib.sha256(json.dumps(body, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()


def _parse(payload: bytes, *, timeframe: CanonicalTimeframe, dataset_id: str,
           source: str):
    try:
        text = payload.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            _fail("archive CSV schema is invalid")
        result = []
        for row in reader:
            if row["symbol"] != "BTC" or row["timeframe"] != timeframe.value:
                _fail("archive CSV lineage is invalid")
            if row["is_closed"] != "true":
                _fail("archive contains an incomplete candle")
            opened = datetime.fromisoformat(row["open_time"].replace("Z", "+00:00"))
            closed = datetime.fromisoformat(row["close_time"].replace("Z", "+00:00"))
            result.append(normalize_hyperliquid_candle({
                "s": row["symbol"], "i": row["timeframe"], "t": _ms(opened),
                "T": _ms(closed), "o": row["open"], "h": row["high"],
                "l": row["low"], "c": row["close"], "v": row["volume"] or None,
                "is_closed": True,
            }, dataset_id=dataset_id, schema_version=CANDLE_SCHEMA,
                source=source, exchange="hyperliquid"))
    except BTCArchiveDatasetError:
        raise
    except (UnicodeError, ValueError, TypeError, KeyError) as exc:
        _fail("archive CSV content is invalid", exc)
    if not result:
        _fail("archive CSV is empty")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class BTCArchiveDatasetV1:
    dataset: HistoricalDataset
    archive_id: str
    manifest_sha256: str
    file_sha256: tuple[tuple[str, str], ...]
    manifest_updated_at: datetime
    bundle_id: str
    instrument_profile: InstrumentProfile = InstrumentProfile.BTC_LINEAR_PERPETUAL
    trading_authority: bool = False

    def __post_init__(self):
        if (self.instrument_profile is not InstrumentProfile.BTC_LINEAR_PERPETUAL
                or self.trading_authority is not False):
            _fail("dataset source cannot grant trading authority")
        body = {"version": VERSION, "dataset_fingerprint": self.dataset.fingerprint,
            "archive_id": self.archive_id, "manifest_sha256": self.manifest_sha256,
            "file_sha256": dict(self.file_sha256),
            "manifest_updated_at": self.manifest_updated_at.isoformat(),
            "instrument_profile": self.instrument_profile.value,
            "trading_authority": False}
        expected = hashlib.sha256(json.dumps(body, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        if self.bundle_id != expected:
            _fail("dataset bundle identity mismatch")


def read_btc_archive_dataset(root, *, as_of: datetime,
        maximum_manifest_age: timedelta = timedelta(seconds=45)) -> BTCArchiveDatasetV1:
    try:
        _utc(as_of, "as_of")
    except BTCArchiveSnapshotError as exc:
        _fail("as_of must be UTC", exc)
    if not timedelta(0) < maximum_manifest_age <= timedelta(seconds=90):
        _fail("manifest age policy is invalid")
    root = Path(root).absolute()
    manifest_path = root / "archive_manifest.json"
    transaction_path = root / "recorder_transaction.json"
    transaction_root = root / ".recorder_transaction"
    if transaction_path.exists() or transaction_root.exists():
        _fail("recorder transaction is in progress")
    try:
        before = _plain_file(manifest_path)
    except BTCArchiveSnapshotError as exc:
        _fail("archive manifest is unreadable", exc)
    if not 0 < before.st_size <= MAXIMUM_MANIFEST_BYTES:
        _fail("manifest size is invalid")
    manifest_bytes = manifest_path.read_bytes()
    if len(manifest_bytes) != before.st_size:
        _fail("manifest changed during read")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("manifest is invalid", exc)
    expected_keys = {"archive_id", "candle_schema_version", "checksums", "data_network",
        "schema_version", "source", "state", "streams", "symbol", "timeframes", "updated_at"}
    expected_archive_id = hashlib.sha256((ARCHIVE_SCHEMA + "BTC" + "mainnet").encode()).hexdigest()
    if (not isinstance(manifest, dict) or set(manifest) != expected_keys
            or manifest["schema_version"] != ARCHIVE_SCHEMA
            or manifest["candle_schema_version"] != CANDLE_SCHEMA
            or manifest["archive_id"] != expected_archive_id
            or manifest["symbol"] != "BTC" or manifest["data_network"] != "mainnet"
            or manifest["source"] != "hyperliquid-public-mainnet"
            or tuple(manifest["timeframes"]) != EXPECTED_TIMEFRAMES
            or manifest["state"] != "RECORDING"
            or not isinstance(manifest["checksums"], dict)
            or not isinstance(manifest["streams"], dict)):
        _fail("manifest identity or state is ineligible")
    try:
        updated = _time(manifest["updated_at"], "updated_at")
    except BTCArchiveSnapshotError as exc:
        _fail("manifest chronology is invalid", exc)
    if not timedelta(0) <= as_of - updated <= maximum_manifest_age:
        _fail("manifest is stale or future-dated")

    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    names = tuple(f"BTC_{value}.csv" for value in EXPECTED_TIMEFRAMES)
    if set(manifest["checksums"]) != set(names) or set(manifest["streams"]) != set(EXPECTED_TIMEFRAMES):
        _fail("manifest stream inventory is invalid")
    checksums = {name: manifest["checksums"].get(name) for name in names}
    if any(not isinstance(value, str) or len(value) != 64
           or any(char not in "0123456789abcdef" for char in value)
           for value in checksums.values()):
        _fail("manifest checksum inventory is invalid")
    dataset_id = _dataset_id(manifest_hash, checksums)
    payloads = {}
    file_info = {}
    for name in names:
        path = root / name
        try:
            info = _plain_file(path)
        except BTCArchiveSnapshotError as exc:
            _fail("archive CSV is unreadable", exc)
        if not 0 < info.st_size <= MAXIMUM_CSV_BYTES:
            _fail("archive CSV size is invalid")
        payload = path.read_bytes()
        after = _plain_file(path)
        if _identity(info) != _identity(after) or len(payload) != info.st_size:
            _fail("archive changed during read")
        if hashlib.sha256(payload).hexdigest() != checksums[name]:
            _fail("archive checksum conflicted during read")
        payloads[name] = payload
        file_info[name] = info

    manifest_after = manifest_path.read_bytes()
    after = _plain_file(manifest_path)
    if (_identity(before) != _identity(after) or manifest_after != manifest_bytes
            or transaction_path.exists() or transaction_root.exists()
            or any(_identity(file_info[name]) != _identity(_plain_file(root / name)) for name in names)):
        _fail("archive changed during read")

    candles = []
    for value, name in zip(EXPECTED_TIMEFRAMES, names):
        timeframe = CanonicalTimeframe(value)
        parsed = _parse(payloads[name], timeframe=timeframe, dataset_id=dataset_id,
                        source=manifest["source"])
        stream = manifest["streams"][value]
        if (not isinstance(stream, dict)
                or set(stream) != {"backfill_attempts", "count", "earliest", "gap_count", "latest_close", "stale"}):
            _fail("stream evidence is invalid")
        try:
            earliest = _time(stream["earliest"], "earliest")
            latest = _time(stream["latest_close"], "latest_close")
        except (BTCArchiveSnapshotError, KeyError) as exc:
            _fail("stream evidence is invalid", exc)
        if (type(stream["count"]) is not int or stream["count"] != len(parsed)
                or type(stream["gap_count"]) is not int or stream["gap_count"] != 0
                or stream["stale"] is not False or parsed[0].open_time != earliest
                or parsed[-1].close_time != latest or latest > updated or latest > as_of):
            _fail("stream evidence conflicts with archive bytes")
        candles.extend(parsed)
    ordered = tuple(sorted(candles, key=lambda item: (
        item.open_time, item.symbol, item.timeframe.value, item.id)))
    try:
        dataset = validate_dataset(ordered, dataset_id=dataset_id,
            schema_version=CANDLE_SCHEMA, source=manifest["source"], exchange="hyperliquid",
            gap_policy=GapPolicy.REJECT, validation_time=as_of)
    except (ValueError, TypeError) as exc:
        _fail("canonical dataset validation failed", exc)
    frozen_checksums = tuple((name, checksums[name]) for name in names)
    body = {"version": VERSION, "dataset_fingerprint": dataset.fingerprint,
        "archive_id": manifest["archive_id"], "manifest_sha256": manifest_hash,
        "file_sha256": dict(frozen_checksums), "manifest_updated_at": updated.isoformat(),
        "instrument_profile": InstrumentProfile.BTC_LINEAR_PERPETUAL.value,
        "trading_authority": False}
    bundle_id = hashlib.sha256(json.dumps(body, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    return BTCArchiveDatasetV1(dataset, manifest["archive_id"], manifest_hash,
        frozen_checksums, updated, bundle_id, InstrumentProfile.BTC_LINEAR_PERPETUAL, False)
