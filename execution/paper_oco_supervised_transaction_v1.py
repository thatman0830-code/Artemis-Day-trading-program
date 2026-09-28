"""Crash-visible progress journal for one supervised paper OCO resolution.

This module performs no execution. It records which independently atomic
checkpoint boundaries have completed so restart recovery never infers success
from a missing write or silently skips an acknowledgement.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import re
import uuid

from backtesting.execution_accounting_v2.specifications import canonical_fingerprint


VERSION = "paper-oco-supervised-transaction-v1"
MAX_BYTES = 64 * 1024
SHA = re.compile(r"[0-9a-f]{64}")


class PaperOCOSupervisedTransactionError(RuntimeError):
    pass


class PaperOCOSupervisedStage(str, Enum):
    PREPARED = "PREPARED"
    PERFORMANCE_COMMITTED = "PERFORMANCE_COMMITTED"
    ACCOUNTING_ACKNOWLEDGED = "ACCOUNTING_ACKNOWLEDGED"
    COMMITTED = "COMMITTED"


@dataclass(frozen=True, slots=True)
class PaperOCOSupervisedTransactionV1:
    version: str
    transaction_id: str
    bridge_id: str
    oco_before_checkpoint_id: str
    adapter_before_id: str
    performance_before_id: str
    stage: PaperOCOSupervisedStage
    adapter_after_id: str | None = None
    performance_after_id: str | None = None
    oco_accounting_checkpoint_id: str | None = None
    oco_final_checkpoint_id: str | None = None
    trading_authority: bool = False

    def __post_init__(self) -> None:
        if self.version != VERSION or self.trading_authority is not False:
            raise PaperOCOSupervisedTransactionError("invalid transaction version or authority")
        required = (
            self.transaction_id,
            self.bridge_id,
            self.oco_before_checkpoint_id,
            self.adapter_before_id,
            self.performance_before_id,
        )
        optional = (
            self.adapter_after_id,
            self.performance_after_id,
            self.oco_accounting_checkpoint_id,
            self.oco_final_checkpoint_id,
        )
        if any(type(value) is not str or SHA.fullmatch(value) is None for value in required):
            raise PaperOCOSupervisedTransactionError("invalid transaction identity")
        if any(value is not None and (type(value) is not str or SHA.fullmatch(value) is None)
               for value in optional):
            raise PaperOCOSupervisedTransactionError("invalid checkpoint identity")
        expected = canonical_fingerprint(
            VERSION,
            self.bridge_id,
            self.oco_before_checkpoint_id,
            self.adapter_before_id,
            self.performance_before_id,
            False,
        )
        if self.transaction_id != expected:
            raise PaperOCOSupervisedTransactionError("transaction identity mismatch")
        present = tuple(value is not None for value in optional)
        expected_presence = {
            PaperOCOSupervisedStage.PREPARED: (False, False, False, False),
            PaperOCOSupervisedStage.PERFORMANCE_COMMITTED: (True, True, False, False),
            PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED: (True, True, True, False),
            PaperOCOSupervisedStage.COMMITTED: (True, True, True, True),
        }
        if present != expected_presence.get(self.stage):
            raise PaperOCOSupervisedTransactionError("transaction stage evidence is incomplete")

    @classmethod
    def prepare(cls, *, bridge_id, oco_before_checkpoint_id,
                adapter_before_id, performance_before_id):
        identity = canonical_fingerprint(
            VERSION,
            bridge_id,
            oco_before_checkpoint_id,
            adapter_before_id,
            performance_before_id,
            False,
        )
        return cls(VERSION, identity, bridge_id, oco_before_checkpoint_id,
                   adapter_before_id, performance_before_id,
                   PaperOCOSupervisedStage.PREPARED)


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _document(value: PaperOCOSupervisedTransactionV1) -> dict:
    value.__post_init__()
    payload = {
        "version": value.version,
        "transaction_id": value.transaction_id,
        "bridge_id": value.bridge_id,
        "oco_before_checkpoint_id": value.oco_before_checkpoint_id,
        "adapter_before_id": value.adapter_before_id,
        "performance_before_id": value.performance_before_id,
        "stage": value.stage.value,
        "adapter_after_id": value.adapter_after_id,
        "performance_after_id": value.performance_after_id,
        "oco_accounting_checkpoint_id": value.oco_accounting_checkpoint_id,
        "oco_final_checkpoint_id": value.oco_final_checkpoint_id,
        "trading_authority": False,
    }
    return {"payload": payload,
            "payload_sha256": canonical_fingerprint(payload)}


class PaperOCOSupervisedTransactionStoreV1:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        self.path = self.root / "oco-supervised-transaction.json"
        self.lock = self.root / "oco-supervised-transaction.lock"

    def _safe(self) -> None:
        if not self.root.is_dir():
            raise PaperOCOSupervisedTransactionError("transaction root is missing")
        for path in (self.root, *self.root.parents, self.path, self.lock):
            if path.is_symlink():
                raise PaperOCOSupervisedTransactionError("linked transaction path")
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if getattr(info, "st_file_attributes", 0) & 0x400:
                raise PaperOCOSupervisedTransactionError("reparse transaction path")

    def _acquire(self) -> None:
        self._safe()
        try:
            descriptor = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise PaperOCOSupervisedTransactionError("transaction writer lock conflict") from exc
        os.close(descriptor)

    def _write_locked(self, value: PaperOCOSupervisedTransactionV1) -> None:
        raw = _canonical(_document(value)) + b"\n"
        if len(raw) > MAX_BYTES:
            raise PaperOCOSupervisedTransactionError("transaction journal size limit")
        temporary = self.root / (".oco-supervised-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self) -> PaperOCOSupervisedTransactionV1:
        self._safe()
        if not self.path.is_file():
            raise PaperOCOSupervisedTransactionError("transaction journal is missing")
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if not raw or len(raw) > MAX_BYTES:
                raise PaperOCOSupervisedTransactionError("transaction journal size invalid")
            pairs = json.loads(raw.decode("utf-8"), object_pairs_hook=lambda items: items)
            if type(pairs) is not list:
                raise PaperOCOSupervisedTransactionError("transaction envelope is invalid")
            envelope = self._unique(pairs)
            if set(envelope) != {"payload", "payload_sha256"}:
                raise PaperOCOSupervisedTransactionError("transaction envelope fields differ")
            payload_pairs = envelope["payload"]
            if type(payload_pairs) is not list:
                raise PaperOCOSupervisedTransactionError("transaction payload is invalid")
            payload = self._unique(payload_pairs)
            fields = {name for name in PaperOCOSupervisedTransactionV1.__dataclass_fields__}
            if set(payload) != fields or envelope["payload_sha256"] != canonical_fingerprint(payload):
                raise PaperOCOSupervisedTransactionError("transaction checksum or fields differ")
            payload["stage"] = PaperOCOSupervisedStage(payload["stage"])
            return PaperOCOSupervisedTransactionV1(**payload)
        except PaperOCOSupervisedTransactionError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            raise PaperOCOSupervisedTransactionError("transaction journal is unreadable") from exc

    @staticmethod
    def _unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PaperOCOSupervisedTransactionError("duplicate transaction field")
            result[key] = value
        return result

    def initialize(self, value: PaperOCOSupervisedTransactionV1):
        if value.stage is not PaperOCOSupervisedStage.PREPARED:
            raise PaperOCOSupervisedTransactionError("new transaction must be prepared")
        self._acquire()
        try:
            if self.path.exists():
                existing = self.load()
                if existing != value:
                    raise PaperOCOSupervisedTransactionError("conflicting transaction exists")
                return existing
            self._write_locked(value)
            return self.load()
        finally:
            self.lock.unlink(missing_ok=True)

    def advance(self, *, expected_transaction_id: str,
                expected_stage: PaperOCOSupervisedStage,
                stage: PaperOCOSupervisedStage, **evidence):
        sequence = tuple(PaperOCOSupervisedStage)
        if sequence.index(stage) != sequence.index(expected_stage) + 1:
            raise PaperOCOSupervisedTransactionError("transaction stage transition is invalid")
        allowed = {
            PaperOCOSupervisedStage.PERFORMANCE_COMMITTED:
                {"adapter_after_id", "performance_after_id"},
            PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED:
                {"oco_accounting_checkpoint_id"},
            PaperOCOSupervisedStage.COMMITTED: {"oco_final_checkpoint_id"},
        }
        if set(evidence) != allowed[stage]:
            raise PaperOCOSupervisedTransactionError("transaction stage evidence differs")
        self._acquire()
        try:
            current = self.load()
            if (current.transaction_id != expected_transaction_id
                    or current.stage is not expected_stage):
                raise PaperOCOSupervisedTransactionError("stale transaction compare-and-swap")
            updated = PaperOCOSupervisedTransactionV1(
                **{**{name: getattr(current, name)
                      for name in current.__dataclass_fields__},
                   **evidence, "stage": stage}
            )
            self._write_locked(updated)
            return self.load()
        finally:
            self.lock.unlink(missing_ok=True)
