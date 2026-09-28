"""Canonical, atomic persistence for the paper-performance ledger."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import uuid

from backtesting.execution_accounting_v2.accounting import (
    AccountingEventKind, AccountingEventV2, AccountingPolicyV2,
    AccountingSnapshotPhase4V2, FillEconomicsV2, FundingFactV2,
    InstrumentAccountingLedgerV2, MarginBasis, MarginSpecificationV2,
    PositionStateV2, PriceEvidenceV2, SettlementFactV2,
)
from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2, OrderSide
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from execution.paper_performance_ledger_v1 import PaperFillBindingV1, PaperPerformanceLedgerV1


SCHEMA_VERSION = "paper-performance-checkpoint-v1"
MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024


class PaperPerformanceCheckpointError(ValueError):
    pass


_DATACLASSES = {item.__name__: item for item in (
    PaperPerformanceLedgerV1, PaperFillBindingV1, InstrumentAccountingLedgerV2,
    InstrumentSpecificationV2, AccountingPolicyV2, MarginSpecificationV2,
    AccountingEventV2, ExecutionFillV2, FillEconomicsV2, PriceEvidenceV2,
    SettlementFactV2, FundingFactV2, AccountingSnapshotPhase4V2, PositionStateV2,
)}
_ENUMS = {item.__name__: item for item in (
    AccountingEventKind, MarginBasis, InstrumentProfile, OrderSide,
)}


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _encode(value):
    # String-backed enums must be handled before primitive strings.
    if isinstance(value, Enum):
        return {"$enum": f"{type(value).__name__}.{value.name}"}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise PaperPerformanceCheckpointError("non-finite Decimal is forbidden")
        return {"$decimal": str(value)}
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise PaperPerformanceCheckpointError("datetime must be UTC")
        return {"$datetime": value.isoformat().replace("+00:00", "Z")}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise PaperPerformanceCheckpointError("float values are forbidden")
    if isinstance(value, tuple):
        return {"$tuple": [_encode(item) for item in value]}
    if is_dataclass(value) and type(value).__name__ in _DATACLASSES:
        return {"$type": type(value).__name__, "fields": {
            item.name: _encode(getattr(value, item.name)) for item in fields(value)}}
    raise PaperPerformanceCheckpointError(f"unsupported checkpoint type: {type(value).__name__}")


def _exact(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise PaperPerformanceCheckpointError(f"{name} fields do not match schema")
    return value


def _decode(value, depth=0):
    if depth > 64:
        raise PaperPerformanceCheckpointError("checkpoint nesting is excessive")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (float, list)) or not isinstance(value, dict):
        raise PaperPerformanceCheckpointError("checkpoint value type is unsupported")
    if set(value) == {"$decimal"}:
        if not isinstance(value["$decimal"], str):
            raise PaperPerformanceCheckpointError("Decimal value must be a canonical string")
        try:
            result = Decimal(value["$decimal"])
        except (InvalidOperation, TypeError) as exc:
            raise PaperPerformanceCheckpointError("Decimal value is invalid") from exc
        if not result.is_finite():
            raise PaperPerformanceCheckpointError("Decimal value is non-finite")
        return result
    if set(value) == {"$datetime"}:
        raw = value["$datetime"]
        if not isinstance(raw, str) or not raw.endswith("Z"):
            raise PaperPerformanceCheckpointError("datetime is not canonical UTC")
        try:
            result = datetime.fromisoformat(raw[:-1] + "+00:00")
        except ValueError as exc:
            raise PaperPerformanceCheckpointError("datetime is invalid") from exc
        if result.tzinfo != timezone.utc:
            raise PaperPerformanceCheckpointError("datetime is not UTC")
        return result
    if set(value) == {"$enum"}:
        raw = value["$enum"]
        if not isinstance(raw, str) or raw.count(".") != 1:
            raise PaperPerformanceCheckpointError("enum identity is invalid")
        type_name, member = raw.split(".")
        try:
            return _ENUMS[type_name][member]
        except (KeyError, TypeError) as exc:
            raise PaperPerformanceCheckpointError("enum is unsupported") from exc
    if set(value) == {"$tuple"}:
        if not isinstance(value["$tuple"], list):
            raise PaperPerformanceCheckpointError("tuple payload is invalid")
        return tuple(_decode(item, depth + 1) for item in value["$tuple"])
    _exact(value, ("$type", "fields"), "typed value")
    type_name, raw_fields = value["$type"], value["fields"]
    cls = _DATACLASSES.get(type_name)
    if cls is None or not isinstance(raw_fields, dict):
        raise PaperPerformanceCheckpointError("dataclass type is unsupported")
    expected = tuple(item.name for item in fields(cls))
    _exact(raw_fields, expected, type_name)
    try:
        return cls(**{name: _decode(raw_fields[name], depth + 1) for name in expected})
    except PaperPerformanceCheckpointError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise PaperPerformanceCheckpointError(f"{type_name} failed validation") from exc


def checkpoint_bytes(ledger: PaperPerformanceLedgerV1) -> bytes:
    ledger.accounting.verify_integrity()
    payload = {"schema_version": SCHEMA_VERSION, "ledger": _encode(ledger),
               "advisory_only": True, "live_trading_permitted": False,
               "trading_authority": False}
    return _canonical({"schema_version": SCHEMA_VERSION, "payload": payload,
        "payload_sha256": hashlib.sha256(_canonical(payload)).hexdigest()}) + b"\n"


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PaperPerformanceCheckpointError("duplicate JSON field")
        result[key] = value
    return result


def ledger_from_bytes(raw: bytes) -> PaperPerformanceLedgerV1:
    if not raw or len(raw) > MAX_CHECKPOINT_BYTES:
        raise PaperPerformanceCheckpointError("checkpoint size is invalid")
    try:
        envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except PaperPerformanceCheckpointError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaperPerformanceCheckpointError("checkpoint is not valid UTF-8 JSON") from exc
    _exact(envelope, ("schema_version", "payload", "payload_sha256"), "envelope")
    if envelope["schema_version"] != SCHEMA_VERSION:
        raise PaperPerformanceCheckpointError("checkpoint schema is unsupported")
    payload = _exact(envelope["payload"], ("schema_version", "ledger",
        "advisory_only", "live_trading_permitted", "trading_authority"), "payload")
    if payload["schema_version"] != SCHEMA_VERSION or payload["advisory_only"] is not True or payload["live_trading_permitted"] is not False or payload["trading_authority"] is not False:
        raise PaperPerformanceCheckpointError("checkpoint authority or schema is invalid")
    if hashlib.sha256(_canonical(payload)).hexdigest() != envelope["payload_sha256"]:
        raise PaperPerformanceCheckpointError("checkpoint checksum mismatch")
    ledger = _decode(payload["ledger"])
    if not isinstance(ledger, PaperPerformanceLedgerV1):
        raise PaperPerformanceCheckpointError("checkpoint does not contain a paper ledger")
    ledger.accounting.verify_integrity()
    return ledger


class PaperPerformanceCheckpointStoreV1:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def _safe(self):
        if not self.path.parent.is_dir() or self.path.is_symlink() or self.lock_path.is_symlink():
            raise PaperPerformanceCheckpointError("checkpoint path is unsafe or parent is missing")

    def _acquire(self):
        self._safe()
        try:
            return os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise PaperPerformanceCheckpointError("checkpoint writer lock already exists") from exc

    def _replace_locked(self, ledger):
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary, "xb") as stream:
                stream.write(checkpoint_bytes(ledger)); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def initialize(self, ledger: PaperPerformanceLedgerV1):
        descriptor = self._acquire()
        try:
            os.close(descriptor)
            if self.path.exists():
                raise PaperPerformanceCheckpointError("checkpoint already exists")
            self._replace_locked(ledger)
        finally:
            self.lock_path.unlink(missing_ok=True)

    def load(self) -> PaperPerformanceLedgerV1:
        if self.path.is_symlink() or not self.path.is_file():
            raise PaperPerformanceCheckpointError("checkpoint file is missing or unsafe")
        try:
            return ledger_from_bytes(self.path.read_bytes())
        except OSError as exc:
            raise PaperPerformanceCheckpointError("checkpoint is unreadable") from exc

    def save(self, ledger: PaperPerformanceLedgerV1, *, expected_ledger_id: str):
        descriptor = self._acquire()
        try:
            os.close(descriptor)
            current = self.load()
            if current.ledger_id != expected_ledger_id:
                raise PaperPerformanceCheckpointError("checkpoint compare-and-swap conflict")
            self._replace_locked(ledger)
        finally:
            self.lock_path.unlink(missing_ok=True)
