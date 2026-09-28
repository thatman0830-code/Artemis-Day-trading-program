"""Deterministic, offline adapter around the fail-closed paper gateway.

This module deliberately exposes no provider or live-execution transport.  It
binds paper commands to immutable gateway snapshots and records their outcomes
so retries cannot create duplicate paper exposure.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json

from execution.paper_gateway_v2 import (
    PaperGatewayDecisionV1,
    PaperGatewaySnapshotV1,
    PaperOrderEventV1,
    PaperOrderState,
    PaperSubmissionV1,
)


class PaperAdapterReason(str, Enum):
    SUBMISSION_APPLIED = "SUBMISSION_APPLIED"
    EVENT_APPLIED = "EVENT_APPLIED"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    COMMAND_CONFLICT = "COMMAND_CONFLICT"
    STALE_GATEWAY_SNAPSHOT = "STALE_GATEWAY_SNAPSHOT"
    GATEWAY_REJECTED = "GATEWAY_REJECTED"
    RECONCILED = "RECONCILED"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"


def _sha(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _canonical(*values: object) -> str:
    def encode(value: object):
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, Decimal):
            return str(value)
        if hasattr(value, "__dataclass_fields__"):
            return {name: getattr(value, name) for name in value.__dataclass_fields__}
        raise TypeError(type(value).__name__)
    raw = json.dumps(values, default=encode, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperAdapterCommandV1:
    command_id: str
    expected_gateway_snapshot_id: str
    submission: PaperSubmissionV1 | None = None
    event: PaperOrderEventV1 | None = None
    trading_authority: bool = False

    def __post_init__(self) -> None:
        _sha(self.command_id, "command_id")
        _sha(self.expected_gateway_snapshot_id, "expected_gateway_snapshot_id")
        if (self.submission is None) == (self.event is None):
            raise ValueError("command must contain exactly one paper action")
        if self.trading_authority:
            raise ValueError("paper adapter command cannot carry trading authority")

    @property
    def fingerprint(self) -> str:
        return _canonical("paper-adapter-command-v1", self)


@dataclass(frozen=True, slots=True)
class PaperAdapterReceiptV1:
    command_id: str
    command_fingerprint: str
    accepted: bool
    reason: PaperAdapterReason
    gateway_reason: str | None
    before_snapshot_id: str
    after_snapshot_id: str
    paper_order_id: str | None
    trading_authority: bool = False

    def __post_init__(self) -> None:
        for value, name in ((self.command_id, "command_id"),
                            (self.command_fingerprint, "command_fingerprint"),
                            (self.before_snapshot_id, "before_snapshot_id"),
                            (self.after_snapshot_id, "after_snapshot_id")):
            _sha(value, name)
        if self.paper_order_id is not None:
            _sha(self.paper_order_id, "paper_order_id")
        if self.trading_authority:
            raise ValueError("paper adapter receipt cannot carry trading authority")


@dataclass(frozen=True, slots=True)
class PaperExchangeAdapterV1:
    gateway: PaperGatewaySnapshotV1
    receipts: tuple[PaperAdapterReceiptV1, ...]
    adapter_id: str
    trading_authority: bool = False

    def __post_init__(self) -> None:
        _sha(self.adapter_id, "adapter_id")
        if not isinstance(self.receipts, tuple):
            raise ValueError("receipts must be immutable")
        if len({item.command_id for item in self.receipts}) != len(self.receipts):
            raise ValueError("adapter command identities must be unique")
        if self.trading_authority or self.gateway.trading_authority:
            raise ValueError("paper adapter cannot carry trading authority")

    @classmethod
    def create(cls, gateway: PaperGatewaySnapshotV1) -> "PaperExchangeAdapterV1":
        PaperGatewaySnapshotV1.resume(gateway)
        return cls._build(gateway, ())

    @classmethod
    def _build(cls, gateway, receipts):
        identity = _canonical("paper-exchange-adapter-v1", gateway.snapshot_id, receipts, False)
        return cls(gateway, receipts, identity, False)

    def verify_integrity(self) -> None:
        PaperGatewaySnapshotV1.resume(self.gateway)
        expected = self._build(self.gateway, self.receipts)
        if expected.adapter_id != self.adapter_id:
            raise ValueError("paper adapter integrity failure")

    def _transient(self, command, reason, gateway_reason=None):
        return PaperAdapterReceiptV1(command.command_id, command.fingerprint, False, reason,
            gateway_reason, self.gateway.snapshot_id, self.gateway.snapshot_id, None, False)

    def execute(self, command: PaperAdapterCommandV1):
        self.verify_integrity()
        existing = next((item for item in self.receipts if item.command_id == command.command_id), None)
        if existing is not None:
            if existing.command_fingerprint == command.fingerprint:
                replay = PaperAdapterReceiptV1(existing.command_id, existing.command_fingerprint,
                    existing.accepted, PaperAdapterReason.IDEMPOTENT_REPLAY, existing.gateway_reason,
                    existing.before_snapshot_id, existing.after_snapshot_id, existing.paper_order_id, False)
                return self, replay
            return self, self._transient(command, PaperAdapterReason.COMMAND_CONFLICT)
        if command.expected_gateway_snapshot_id != self.gateway.snapshot_id:
            return self, self._transient(command, PaperAdapterReason.STALE_GATEWAY_SNAPSHOT)
        before = self.gateway.snapshot_id
        gateway, decision = (self.gateway.submit(command.submission) if command.submission is not None
                             else self.gateway.apply_event(command.event))
        applied = decision.accepted
        reason = (PaperAdapterReason.SUBMISSION_APPLIED if command.submission is not None
                  else PaperAdapterReason.EVENT_APPLIED) if applied else PaperAdapterReason.GATEWAY_REJECTED
        receipt = self._receipt(command, decision, reason, before, gateway.snapshot_id)
        return self._build(gateway, self.receipts + (receipt,)), receipt

    @staticmethod
    def _receipt(command, decision: PaperGatewayDecisionV1, reason, before, after):
        return PaperAdapterReceiptV1(command.command_id, command.fingerprint, decision.accepted,
            reason, decision.reason.value, before, after,
            None if decision.record is None else decision.record.paper_order_id, False)

    def disconnect(self) -> "PaperExchangeAdapterV1":
        self.verify_integrity()
        return self._build(self.gateway.disconnect(), self.receipts)

    def halt(self) -> "PaperExchangeAdapterV1":
        """Fail closed without discarding gateway records or adapter receipts."""
        self.verify_integrity()
        return self._build(self.gateway.activate_kill_switch().disconnect(), self.receipts)

    def reconcile(self, expected_gateway_snapshot_id: str,
                  observed: tuple[tuple[str, PaperOrderState, object, object, int], ...]):
        self.verify_integrity(); _sha(expected_gateway_snapshot_id, "expected_gateway_snapshot_id")
        if expected_gateway_snapshot_id != self.gateway.snapshot_id:
            return self, PaperAdapterReason.STALE_GATEWAY_SNAPSHOT
        gateway = self.gateway.reconcile(observed)
        adapter = self._build(gateway, self.receipts)
        reason = (PaperAdapterReason.RECONCILED if gateway.connected and not gateway.reconciliation_required
                  else PaperAdapterReason.RECONCILIATION_MISMATCH)
        return adapter, reason
