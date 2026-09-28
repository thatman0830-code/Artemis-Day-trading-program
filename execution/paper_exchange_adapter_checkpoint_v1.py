"""Atomic persistence and crash recovery for the offline paper adapter."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1, PaperAdapterPairReceiptV1, PaperAdapterReason, PaperAdapterReceiptV1,
    PaperExchangeAdapterV1,
)
from execution.paper_gateway_checkpoint_v1 import checkpoint_bytes, snapshot_from_bytes

SCHEMA = "paper-exchange-adapter-checkpoint-v1"
MAX_CHECKPOINT_BYTES = 32 * 1024 * 1024


class PaperAdapterCheckpointError(ValueError):
    pass


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _exact(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise PaperAdapterCheckpointError(f"{name} fields do not match schema")
    return value


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PaperAdapterCheckpointError("duplicate JSON field")
        result[key] = value
    return result


def adapter_payload(adapter: PaperExchangeAdapterV1) -> dict:
    adapter.verify_integrity()
    gateway_document = json.loads(checkpoint_bytes(adapter.gateway))
    receipts = [{
        "command_id": item.command_id,
        "command_fingerprint": item.command_fingerprint,
        "accepted": item.accepted,
        "reason": item.reason.value,
        "gateway_reason": item.gateway_reason,
        "before_snapshot_id": item.before_snapshot_id,
        "after_snapshot_id": item.after_snapshot_id,
        **({"pair_id": item.pair_id,"paper_order_ids":list(item.paper_order_ids)}
           if type(item) is PaperAdapterPairReceiptV1 else {"paper_order_id":item.paper_order_id}),
        "trading_authority": False,
    } for item in adapter.receipts]
    return {"schema_version": SCHEMA, "gateway_checkpoint": gateway_document,
            "receipts": receipts, "adapter_id": adapter.adapter_id,
            "trading_authority": False}


def adapter_checkpoint_bytes(adapter: PaperExchangeAdapterV1) -> bytes:
    payload = adapter_payload(adapter)
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    return _canonical({"schema_version": SCHEMA, "payload": payload,
                       "payload_sha256": digest}) + b"\n"


def adapter_from_bytes(raw: bytes) -> PaperExchangeAdapterV1:
    if not raw or len(raw) > MAX_CHECKPOINT_BYTES:
        raise PaperAdapterCheckpointError("checkpoint size is invalid")
    try:
        envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaperAdapterCheckpointError("checkpoint is not canonical UTF-8 JSON") from exc
    _exact(envelope, ("schema_version", "payload", "payload_sha256"), "envelope")
    if envelope["schema_version"] != SCHEMA:
        raise PaperAdapterCheckpointError("checkpoint schema is unsupported")
    payload = envelope["payload"]
    if hashlib.sha256(_canonical(payload)).hexdigest() != envelope["payload_sha256"]:
        raise PaperAdapterCheckpointError("checkpoint checksum mismatch")
    _exact(payload, ("schema_version", "gateway_checkpoint", "receipts", "adapter_id",
                     "trading_authority"), "payload")
    if payload["schema_version"] != SCHEMA or payload["trading_authority"] is not False:
        raise PaperAdapterCheckpointError("checkpoint authority/schema invalid")
    if not isinstance(payload["receipts"], list):
        raise PaperAdapterCheckpointError("receipts must be a list")
    try:
        gateway = snapshot_from_bytes(_canonical(payload["gateway_checkpoint"]) + b"\n")
        single_keys=("command_id","command_fingerprint","accepted","reason","gateway_reason",
            "before_snapshot_id","after_snapshot_id","paper_order_id","trading_authority")
        pair_keys=("command_id","command_fingerprint","accepted","reason","gateway_reason",
            "before_snapshot_id","after_snapshot_id","pair_id","paper_order_ids","trading_authority")
        receipts = []
        for raw_receipt in payload["receipts"]:
            if not isinstance(raw_receipt,dict):raise PaperAdapterCheckpointError("receipt fields do not match schema")
            kind="SINGLE" if set(raw_receipt)==set(single_keys) else "PAIR" if set(raw_receipt)==set(pair_keys) else None
            if kind is None:raise PaperAdapterCheckpointError("receipt fields do not match schema")
            item=raw_receipt
            if not isinstance(item["accepted"], bool) or item["trading_authority"] is not False:
                raise PaperAdapterCheckpointError("receipt authority/type invalid")
            if item["gateway_reason"] is not None and not isinstance(item["gateway_reason"], str):
                raise PaperAdapterCheckpointError("gateway reason is invalid")
            common=(item["command_id"],item["command_fingerprint"],item["accepted"],
                PaperAdapterReason(item["reason"]),item["gateway_reason"],item["before_snapshot_id"],
                item["after_snapshot_id"])
            if kind=="SINGLE":
                receipts.append(PaperAdapterReceiptV1(*common,item["paper_order_id"],False))
            elif isinstance(item["paper_order_ids"],list):
                receipts.append(PaperAdapterPairReceiptV1(*common,item["pair_id"],
                    tuple(item["paper_order_ids"]),False))
            else: raise PaperAdapterCheckpointError("receipt type fields are invalid")
        adapter = PaperExchangeAdapterV1(gateway, tuple(receipts), payload["adapter_id"], False)
        adapter.verify_integrity()
        return adapter
    except PaperAdapterCheckpointError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise PaperAdapterCheckpointError("checkpoint payload is invalid") from exc


class PaperAdapterCheckpointStoreV1:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def _safe(self):
        if not self.path.parent.is_dir() or self.path.is_symlink() or self.lock_path.is_symlink():
            raise PaperAdapterCheckpointError("checkpoint path is unsafe or parent is missing")

    def _acquire(self):
        self._safe()
        try:
            return os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise PaperAdapterCheckpointError("checkpoint writer lock already exists") from exc

    def _replace_locked(self, adapter):
        temp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temp, "xb") as stream:
                stream.write(adapter_checkpoint_bytes(adapter)); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    def initialize(self, adapter: PaperExchangeAdapterV1) -> None:
        descriptor = self._acquire()
        try:
            os.close(descriptor)
            if self.path.exists():
                raise PaperAdapterCheckpointError("checkpoint already exists")
            self._replace_locked(adapter)
        finally:
            self.lock_path.unlink(missing_ok=True)

    def load(self) -> PaperExchangeAdapterV1:
        if self.path.is_symlink() or not self.path.is_file():
            raise PaperAdapterCheckpointError("checkpoint file is missing or unsafe")
        try:
            return adapter_from_bytes(self.path.read_bytes())
        except OSError as exc:
            raise PaperAdapterCheckpointError("checkpoint is unreadable") from exc

    def _transaction(self, operation):
        descriptor = self._acquire()
        try:
            os.close(descriptor)
            current = self.load()
            updated, result = operation(current)
            updated.verify_integrity()
            self._replace_locked(updated)
            return updated, result
        finally:
            self.lock_path.unlink(missing_ok=True)

    def execute(self, command: PaperAdapterCommandV1):
        return self._transaction(lambda adapter: adapter.execute(command))

    def restart(self) -> PaperExchangeAdapterV1:
        updated, _ = self._transaction(lambda adapter: (adapter.disconnect(), None))
        return updated

    def halt(self) -> PaperExchangeAdapterV1:
        updated, _ = self._transaction(lambda adapter: (adapter.halt(), None))
        return updated

    def reconcile(self, expected_gateway_snapshot_id: str, observed):
        return self._transaction(lambda adapter: adapter.reconcile(
            expected_gateway_snapshot_id, observed))
