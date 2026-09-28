"""Read one transaction-safe BTC recorder snapshot without provider access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

from backtesting.recorder import ARCHIVE_SCHEMA
from execution.paper_file_valuation_v1 import PaperSnapshotReferenceV1


VERSION = "btc-archive-snapshot-source-v1"
MAXIMUM_MANIFEST_BYTES = 64 * 1024
EXPECTED_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h")


class BTCArchiveSnapshotError(RuntimeError):
    pass


def _utc(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise BTCArchiveSnapshotError(f"{name} must be UTC")


def _time(value, name):
    if not isinstance(value, str): raise BTCArchiveSnapshotError(f"{name} is invalid")
    try: result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise BTCArchiveSnapshotError(f"{name} is invalid") from exc
    _utc(result, name); return result


def _plain_file(path):
    try: info = path.lstat()
    except OSError as exc: raise BTCArchiveSnapshotError("archive input is unreadable") from exc
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise BTCArchiveSnapshotError("archive input is not a plain file")
    return info


@dataclass(frozen=True, slots=True)
class BTCArchiveSnapshotV1:
    reference: PaperSnapshotReferenceV1
    manifest_sha256: str
    archive_id: str
    latest_close: datetime
    manifest_updated_at: datetime
    snapshot_id: str
    trading_authority: bool = False

    def __post_init__(self):
        if self.trading_authority is not False:
            raise BTCArchiveSnapshotError("snapshot source cannot grant trading authority")
        body = {"version": VERSION, "reference": {
            "relative_path": self.reference.relative_path, "sha256": self.reference.sha256,
            "available_at": self.reference.available_at.isoformat()},
            "manifest_sha256": self.manifest_sha256, "archive_id": self.archive_id,
            "latest_close": self.latest_close.isoformat(),
            "manifest_updated_at": self.manifest_updated_at.isoformat(),
            "trading_authority": False}
        expected = hashlib.sha256(json.dumps(body, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        if self.snapshot_id != expected:
            raise BTCArchiveSnapshotError("snapshot source identity mismatch")


def read_btc_archive_snapshot(root, *, timeframe, as_of,
        maximum_manifest_age=timedelta(seconds=45),snapshot_root=None):
    _utc(as_of, "as_of")
    if timeframe not in ("1m", "5m", "15m"):
        raise BTCArchiveSnapshotError("unsupported paper timeframe")
    if not timedelta(0) < maximum_manifest_age <= timedelta(seconds=90):
        raise BTCArchiveSnapshotError("manifest age policy is invalid")
    root = Path(root).absolute()
    manifest_path = root / "archive_manifest.json"
    transaction_path = root / "recorder_transaction.json"
    transaction_root = root / ".recorder_transaction"
    if transaction_path.exists() or transaction_root.exists():
        raise BTCArchiveSnapshotError("recorder transaction is in progress")
    before = _plain_file(manifest_path)
    if not 0 < before.st_size <= MAXIMUM_MANIFEST_BYTES:
        raise BTCArchiveSnapshotError("manifest size is invalid")
    manifest_bytes = manifest_path.read_bytes()
    if len(manifest_bytes) != before.st_size:
        raise BTCArchiveSnapshotError("manifest changed during read")
    try: manifest = json.loads(manifest_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BTCArchiveSnapshotError("manifest is invalid") from exc
    expected_keys = {"archive_id","candle_schema_version","checksums","data_network",
        "schema_version","source","state","streams","symbol","timeframes","updated_at"}
    if (not isinstance(manifest, dict) or set(manifest) != expected_keys
            or manifest["schema_version"] != ARCHIVE_SCHEMA
            or manifest["candle_schema_version"] != "historical-candle-v1"
            or manifest["symbol"] != "BTC" or manifest["data_network"] != "mainnet"
            or manifest["source"] != "hyperliquid-public-mainnet"
            or tuple(manifest["timeframes"]) != EXPECTED_TIMEFRAMES
            or manifest["state"] != "RECORDING"):
        raise BTCArchiveSnapshotError("manifest identity or state is ineligible")
    expected_archive_id = hashlib.sha256((ARCHIVE_SCHEMA + "BTC" + "mainnet").encode()).hexdigest()
    if manifest["archive_id"] != expected_archive_id:
        raise BTCArchiveSnapshotError("archive identity is invalid")
    updated = _time(manifest["updated_at"], "updated_at")
    if not timedelta(0) <= as_of - updated <= maximum_manifest_age:
        raise BTCArchiveSnapshotError("manifest is stale or future-dated")
    stream = manifest["streams"].get(timeframe) if isinstance(manifest["streams"], dict) else None
    filename = f"BTC_{timeframe}.csv"
    digest = manifest["checksums"].get(filename) if isinstance(manifest["checksums"], dict) else None
    if (not isinstance(stream, dict) or set(stream) != {"backfill_attempts","count","earliest",
            "gap_count","latest_close","stale"} or stream["stale"] is not False
            or type(stream["gap_count"]) is not int or stream["gap_count"] != 0
            or type(stream["count"]) is not int or stream["count"] <= 0
            or not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        raise BTCArchiveSnapshotError("stream evidence is incomplete or unhealthy")
    latest = _time(stream["latest_close"], "latest_close")
    if latest > updated or latest > as_of:
        raise BTCArchiveSnapshotError("stream chronology is invalid")
    csv_path = root / filename; csv_before = _plain_file(csv_path)
    payload = csv_path.read_bytes(); csv_after = _plain_file(csv_path)
    manifest_after = manifest_path.read_bytes(); after = _plain_file(manifest_path)
    identity = lambda item: (item.st_dev,item.st_ino,item.st_size,item.st_mtime_ns,item.st_ctime_ns)
    if (identity(csv_before) != identity(csv_after) or identity(before) != identity(after)
            or manifest_after != manifest_bytes or transaction_path.exists() or transaction_root.exists()
            or hashlib.sha256(payload).hexdigest() != digest):
        raise BTCArchiveSnapshotError("archive changed or checksum conflicted during read")
    reference = PaperSnapshotReferenceV1(filename, digest, updated)
    if snapshot_root is not None:
        lines=payload.decode("utf-8-sig").splitlines()
        if len(lines)<2:raise BTCArchiveSnapshotError("archive has no snapshot rows")
        bounded=("\n".join((lines[0],*lines[1:][-1000:]))+"\n").encode("utf-8")
        bounded_hash=hashlib.sha256(bounded).hexdigest();snapshot_root=Path(snapshot_root).absolute()
        snapshot_root.mkdir(parents=True,exist_ok=True)
        if snapshot_root.is_symlink()or not snapshot_root.is_dir():raise BTCArchiveSnapshotError("snapshot root is unsafe")
        snapshot_name=f"BTC_{timeframe}.{bounded_hash}.csv";snapshot_path=snapshot_root/snapshot_name
        if snapshot_path.exists():
            if snapshot_path.is_symlink()or snapshot_path.read_bytes()!=bounded:raise BTCArchiveSnapshotError("snapshot retention conflict")
        else:
            temporary=snapshot_path.with_name(f".{snapshot_name}.{uuid.uuid4().hex}.tmp")
            try:
                with open(temporary,"xb")as stream:stream.write(bounded);stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,snapshot_path)
            finally:temporary.unlink(missing_ok=True)
        reference=PaperSnapshotReferenceV1(snapshot_name,bounded_hash,updated)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    body = {"version":VERSION,"reference":{"relative_path":reference.relative_path,
        "sha256":reference.sha256,"available_at":reference.available_at.isoformat()},"manifest_sha256":manifest_hash,
        "archive_id":manifest["archive_id"],"latest_close":latest.isoformat(),
        "manifest_updated_at":updated.isoformat(),"trading_authority":False}
    snapshot_id = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    return BTCArchiveSnapshotV1(reference,manifest_hash,manifest["archive_id"],latest,updated,snapshot_id,False)
