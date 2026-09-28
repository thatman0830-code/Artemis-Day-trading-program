"""Persist initial protective inputs; reopen offline replay using only its directory."""
from dataclasses import fields
import json
import os
from pathlib import Path

from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderState, OrderType, TimeInForce
from backtesting.execution_accounting_v2.order_ledger import (
    OrderLedgerV2, OrderLedgerEventV2, OrderLedgerSnapshotV2, OrderLedgerTransitionV2, LedgerEventKind,
)
from backtesting.execution_accounting_v2.ohlc_execution import (
    OHLCBarV2, ExecutionPolicyV2, ExecutionInstructionV2, ExecutionSourceLineageV2, ExecutionPriority,
)
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.paper_performance_checkpoint_v1 import _encode, _decode
from execution.paper_oco_checkpoint_v1 import _unique
from execution.paper_oco_evidence_v1 import DurablePaperOCOReplayV1
from execution.paper_oco_execution_v1 import PaperOCOError


MAX_INITIAL_BYTES = 16 * 1024 * 1024
_FIELDS = {"accounting", "ledger", "stop_order_id", "target_order_id", "policy", "instructions", "armed_at"}
_TYPES = {cls.__name__: cls for cls in (OrderIntentV2, OrderLedgerV2, OrderLedgerEventV2,
    OrderLedgerSnapshotV2, OrderLedgerTransitionV2, OHLCBarV2, ExecutionPolicyV2,
    ExecutionInstructionV2, ExecutionSourceLineageV2)}
_ENUMS = {cls.__name__: cls for cls in (OrderState, OrderType, TimeInForce, LedgerEventKind, ExecutionPriority)}


def _pack(value):
    if type(value) in _ENUMS.values():
        return {"oco_enum": type(value).__name__, "member": value.name}
    if type(value) is tuple:
        return {"oco_tuple": [_pack(item) for item in value]}
    if type(value) in _TYPES.values():
        return {"oco_type": type(value).__name__, "fields": {
            field.name: _pack(getattr(value, field.name)) for field in fields(value)}}
    return _encode(value)


def _unpack(value, depth=0):
    if depth > 48:
        raise PaperOCOError("initial configuration nesting limit")
    if type(value) is dict:
        if set(value) == {"oco_enum", "member"}:
            return _ENUMS[value["oco_enum"]][value["member"]]
        if set(value) == {"oco_tuple"}:
            if type(value["oco_tuple"]) is not list:
                raise PaperOCOError("invalid initial tuple")
            return tuple(_unpack(item, depth+1) for item in value["oco_tuple"])
        if set(value) == {"oco_type", "fields"}:
            cls = _TYPES[value["oco_type"]]
            values = value["fields"]
            if type(values) is not dict or set(values) != {f.name for f in fields(cls)}:
                raise PaperOCOError("initial type schema mismatch")
            return cls(**{name: _unpack(item, depth+1) for name, item in values.items()})
    return _decode(value)


def _path(root):
    root = Path(root).absolute()
    path = root / "oco-initial.json"
    for item in (root, *root.parents, path, root / "oco-checkpoint.lock"):
        if item.is_symlink():
            raise PaperOCOError("linked initial configuration path")
        try:
            stat = item.lstat()
        except FileNotFoundError:
            continue
        if getattr(stat, "st_file_attributes", 0) & 0x400:
            raise PaperOCOError("reparse initial configuration path")
    if not root.is_dir():
        raise PaperOCOError("initial configuration directory missing")
    return path


def _read(root):
    path = _path(root)
    with path.open("rb") as stream:
        raw = stream.read(MAX_INITIAL_BYTES+1)
    if not raw or len(raw) > MAX_INITIAL_BYTES:
        raise PaperOCOError("initial configuration size limit")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(PaperOCOError("invalid numeric constant")))
        if (type(doc) is not dict or set(doc) != {"version", "initial_id", "initial", "trading_authority"}
                or doc["version"] != "paper-oco-initial-v1" or doc["trading_authority"] is not False
                or type(doc["initial"]) is not dict or set(doc["initial"]) != _FIELDS):
            raise PaperOCOError("initial envelope schema mismatch")
        initial = {name: _unpack(item) for name, item in doc["initial"].items()}
        if canonical_fingerprint(initial) != doc["initial_id"]:
            raise PaperOCOError("initial configuration checksum mismatch")
        # Constructor verifies ledger integrity and original pair eligibility.
        return DurablePaperOCOReplayV1(root, initial=initial)
    except (ValueError, TypeError, KeyError, RecursionError, AttributeError) as exc:
        raise PaperOCOError("invalid initial protective configuration") from exc


def create_persisted_protective_session(root, *, initial):
    if type(initial) is not dict or set(initial) != _FIELDS:
        raise PaperOCOError("exact initial configuration fields required")
    runner = DurablePaperOCOReplayV1(root, initial=initial)
    normalized = runner.journal.initial
    raw = json.dumps(dict(version="paper-oco-initial-v1", initial_id=runner.journal.initial_id,
        initial={key: _pack(value) for key, value in normalized.items()}, trading_authority=False),
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_INITIAL_BYTES:
        raise PaperOCOError("initial configuration size limit")
    path = _path(root)
    runner.journal._acquire()
    try:
        if path.exists() or runner.journal.path.exists():
            raise PaperOCOError("protective session already exists; no reset allowed")
        # Create-only: a partial file after interruption blocks implicit recovery.
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        decoded = _read(root)
        if decoded.journal.initial != normalized:
            raise PaperOCOError("initial configuration round-trip differs")
        runner.journal._initialize_locked()
    finally:
        runner.journal.lock.unlink()
    return open_persisted_protective_session(root)


def open_persisted_protective_session(root):
    # An abandoned initialization/writer lock needs owner review, never deletion.
    path = _path(root)
    if (path.parent / "oco-checkpoint.lock").exists():
        raise PaperOCOError("protective writer lock present")
    runner = _read(root)
    runner.load()  # Requires committed journal and all referenced action evidence.
    return runner
