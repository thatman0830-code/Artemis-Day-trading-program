"""Atomic, content-verified persistence for the offline paper gateway."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import uuid

from backtesting.execution_accounting_v2.contracts import (
    OrderIntentV2, OrderSide, OrderType, TimeInForce,
)
from execution.paper_gateway_v2 import (
    PaperGatewayPolicyV1, PaperGatewaySnapshotV1, PaperOrderRecordV1, PaperOrderState,
)

SCHEMA = "paper-gateway-checkpoint-v1"
MAX_CHECKPOINT_BYTES = 16 * 1024 * 1024


class PaperCheckpointError(ValueError):
    pass


def _dt(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def _parse_dt(value, name, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PaperCheckpointError(f"{name} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise PaperCheckpointError(f"{name} is invalid") from exc
    if parsed.tzinfo != timezone.utc:
        raise PaperCheckpointError(f"{name} must be UTC")
    return parsed


def _exact(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise PaperCheckpointError(f"{name} fields do not match schema")
    return value


def _intent_to_dict(value: OrderIntentV2):
    return {name: (getattr(value, name).value if name in ("side", "order_type", "time_in_force")
                   else str(getattr(value, name)) if name == "quantity"
                   else _dt(getattr(value, name)) if name in ("submitted_at", "activation_at", "expires_at")
                   else getattr(value, name)) for name in value.__dataclass_fields__}


def _intent_from_dict(value):
    keys = tuple(OrderIntentV2.__dataclass_fields__)
    value = _exact(value, keys, "intent")
    try:
        return OrderIntentV2(**{**value, "quantity": Decimal(value["quantity"]),
            "side": OrderSide(value["side"]), "order_type": OrderType(value["order_type"]),
            "time_in_force": TimeInForce(value["time_in_force"]),
            "submitted_at": _parse_dt(value["submitted_at"], "submitted_at"),
            "activation_at": _parse_dt(value["activation_at"], "activation_at"),
            "expires_at": _parse_dt(value["expires_at"], "expires_at", True)})
    except (ValueError, TypeError, KeyError) as exc:
        raise PaperCheckpointError("intent is invalid") from exc


def snapshot_payload(snapshot: PaperGatewaySnapshotV1) -> dict:
    PaperGatewaySnapshotV1.resume(snapshot)
    records = []
    for record in snapshot.records:
        records.append({
            "paper_order_id": record.paper_order_id, "idempotency_key": record.idempotency_key,
            "request_fingerprint": record.request_fingerprint, "order_id": record.order_id,
            "market": record.market, "notional": str(record.notional), "state": record.state.value,
            "accepted_at": _dt(record.accepted_at), "quantity": str(record.quantity),
            "filled_quantity": str(record.filled_quantity), "remaining_quantity": str(record.remaining_quantity),
            "version": record.version, "last_event_at": _dt(record.last_event_at),
            "event_fingerprints": [list(item) for item in record.event_fingerprints],
        })
    return {"schema_version": SCHEMA, "policy": {
        "max_order_notional": str(snapshot.policy.max_order_notional),
        "max_total_notional": str(snapshot.policy.max_total_notional),
        "max_open_orders": snapshot.policy.max_open_orders,
        "maximum_market_data_age_microseconds": snapshot.policy.maximum_market_data_age // timedelta(microseconds=1),
    }, "connected": snapshot.connected, "kill_switch_active": snapshot.kill_switch_active,
        "reconciliation_required": snapshot.reconciliation_required, "records": records,
        "snapshot_id": snapshot.snapshot_id, "trading_authority": False}


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def checkpoint_bytes(snapshot: PaperGatewaySnapshotV1) -> bytes:
    payload = snapshot_payload(snapshot)
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    return _canonical({"schema_version": SCHEMA, "payload": payload, "payload_sha256": digest}) + b"\n"


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PaperCheckpointError("duplicate JSON field")
        result[key] = value
    return result


def snapshot_from_bytes(raw: bytes) -> PaperGatewaySnapshotV1:
    if not raw or len(raw) > MAX_CHECKPOINT_BYTES:
        raise PaperCheckpointError("checkpoint size is invalid")
    try:
        envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaperCheckpointError("checkpoint is not canonical UTF-8 JSON") from exc
    _exact(envelope, ("schema_version", "payload", "payload_sha256"), "envelope")
    if envelope["schema_version"] != SCHEMA:
        raise PaperCheckpointError("checkpoint schema is unsupported")
    payload = envelope["payload"]
    if hashlib.sha256(_canonical(payload)).hexdigest() != envelope["payload_sha256"]:
        raise PaperCheckpointError("checkpoint checksum mismatch")
    _exact(payload, ("schema_version", "policy", "connected", "kill_switch_active",
        "reconciliation_required", "records", "snapshot_id", "trading_authority"), "payload")
    if payload["schema_version"] != SCHEMA or payload["trading_authority"] is not False:
        raise PaperCheckpointError("checkpoint authority/schema invalid")
    policy_data = _exact(payload["policy"], ("max_order_notional", "max_total_notional",
        "max_open_orders", "maximum_market_data_age_microseconds"), "policy")
    try:
        policy = PaperGatewayPolicyV1(Decimal(policy_data["max_order_notional"]),
            Decimal(policy_data["max_total_notional"]), policy_data["max_open_orders"],
            timedelta(microseconds=policy_data["maximum_market_data_age_microseconds"]))
        record_keys = ("paper_order_id", "idempotency_key", "request_fingerprint", "order_id",
            "market", "notional", "state", "accepted_at", "quantity", "filled_quantity",
            "remaining_quantity", "version", "last_event_at", "event_fingerprints")
        records = tuple(PaperOrderRecordV1(_exact(item, record_keys, "record")["paper_order_id"], item["idempotency_key"],
            item["request_fingerprint"], item["order_id"], item["market"], Decimal(item["notional"]),
            PaperOrderState(item["state"]), _parse_dt(item["accepted_at"], "accepted_at"),
            Decimal(item["quantity"]), Decimal(item["filled_quantity"]), Decimal(item["remaining_quantity"]),
            item["version"], _parse_dt(item["last_event_at"], "last_event_at", True),
            tuple(tuple(pair) for pair in item["event_fingerprints"])) for item in payload["records"])
        snapshot = PaperGatewaySnapshotV1(policy, payload["connected"], payload["kill_switch_active"],
            payload["reconciliation_required"], records, payload["snapshot_id"], False)
        return PaperGatewaySnapshotV1.resume(snapshot)
    except PaperCheckpointError:
        raise
    except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
        raise PaperCheckpointError("checkpoint payload is invalid") from exc


class PaperGatewayCheckpointStoreV1:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def save(self, snapshot: PaperGatewaySnapshotV1) -> None:
        if not self.path.parent.is_dir() or self.path.is_symlink() or self.lock_path.is_symlink():
            raise PaperCheckpointError("checkpoint path is unsafe or parent is missing")
        try:
            lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise PaperCheckpointError("checkpoint writer lock already exists") from exc
        temp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            os.close(lock_fd)
            with open(temp, "xb") as stream:
                stream.write(checkpoint_bytes(snapshot)); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, self.path)
        finally:
            if temp.exists(): temp.unlink()
            if self.lock_path.exists(): self.lock_path.unlink()

    def load(self) -> PaperGatewaySnapshotV1:
        if self.path.is_symlink() or not self.path.is_file():
            raise PaperCheckpointError("checkpoint file is missing or unsafe")
        return snapshot_from_bytes(self.path.read_bytes())
