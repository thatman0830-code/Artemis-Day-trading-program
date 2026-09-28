"""Single-owner, bounded, offline workflow for supervised paper execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import os
from pathlib import Path

from execution.paper_exchange_adapter_checkpoint_v1 import PaperAdapterCheckpointStoreV1
from execution.paper_exchange_adapter_v1 import (
    PaperAdapterCommandV1, PaperAdapterReason, PaperAdapterReceiptV1,
    PaperExchangeAdapterV1,
)


class SupervisedPaperError(RuntimeError):
    pass


class SupervisedPaperState(str, Enum):
    HEALTHY = "HEALTHY"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    HALTED_STALE_INPUT = "HALTED_STALE_INPUT"
    HALTED_FUTURE_INPUT = "HALTED_FUTURE_INPUT"
    HALTED_PERFORMANCE_PERSISTENCE = "HALTED_PERFORMANCE_PERSISTENCE"
    STOPPED = "STOPPED"


def _utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise SupervisedPaperError(f"{name} must be UTC")


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class SupervisedPaperPolicyV1:
    maximum_input_age: timedelta

    def __post_init__(self):
        if self.maximum_input_age <= timedelta(0):
            raise ValueError("maximum_input_age must be positive")


@dataclass(frozen=True, slots=True)
class SupervisedPaperCycleV1:
    now: datetime
    input_observed_at: datetime
    command: PaperAdapterCommandV1 | None = None
    reconciliation_observation: tuple | None = None


@dataclass(frozen=True, slots=True)
class SupervisedPaperHealthV1:
    session_id: str
    state: SupervisedPaperState
    observed_at: datetime
    input_observed_at: datetime
    adapter_id: str
    gateway_snapshot_id: str
    receipt_reason: str | None
    kill_switch_active: bool
    reconciliation_required: bool
    heartbeat_id: str
    trading_authority: bool = False


class SupervisedPaperWorkflowV1:
    def __init__(self, root: Path, policy: SupervisedPaperPolicyV1,
                 initial: PaperExchangeAdapterV1, session_id: str):
        self.root = Path(root); self.policy = policy; self.initial = initial
        self.session_id = session_id
        if len(session_id) != 32 or any(c not in "0123456789abcdef" for c in session_id):
            raise ValueError("session_id must be lowercase UUID hex")
        self.lock_path = self.root / "supervised-paper.lock"
        self.stop_path = self.root / "stop-request.json"
        self.health_path = self.root / "latest-health.json"
        self.alerts_path = self.root / "alerts.jsonl"
        self.store = PaperAdapterCheckpointStoreV1(self.root / "adapter-checkpoint.json")
        self._owned = False

    def acquire(self):
        if not self.root.is_dir() or self.lock_path.is_symlink():
            raise SupervisedPaperError("workflow root is missing or unsafe")
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise SupervisedPaperError("supervised workflow already owned") from exc
        try:
            os.write(descriptor, _canonical({"session_id": self.session_id,
                                             "trading_authority": False})); os.fsync(descriptor)
        except Exception:
            os.close(descriptor); self.lock_path.unlink(missing_ok=True); raise
        os.close(descriptor); self._owned = True

    def _assert_owner(self):
        if not self._owned or not self.lock_path.is_file() or self.lock_path.is_symlink():
            raise SupervisedPaperError("workflow ownership lost")
        try:
            owner = json.loads(self.lock_path.read_text("utf-8"))
        except Exception as exc:
            raise SupervisedPaperError("workflow lock is unreadable") from exc
        if owner != {"session_id": self.session_id, "trading_authority": False}:
            raise SupervisedPaperError("workflow ownership mismatch")

    def start(self):
        self._assert_owner()
        if self.store.path.exists():
            return self.store.restart()
        self.store.initialize(self.initial)
        return self.initial

    def _stop_requested(self):
        if not self.stop_path.exists(): return False
        try: value = json.loads(self.stop_path.read_text("utf-8"))
        except Exception as exc: raise SupervisedPaperError("stop request is unreadable") from exc
        if value != {"session_id": self.session_id, "stop": True, "trading_authority": False}:
            raise SupervisedPaperError("stop request identity mismatch")
        return True

    def cycle(self, cycle: SupervisedPaperCycleV1):
        self._assert_owner(); _utc(cycle.now, "now"); _utc(cycle.input_observed_at, "input_observed_at")
        current = self.store.load(); receipt = None
        if self._stop_requested():
            current = self.store.restart(); state = SupervisedPaperState.STOPPED
        elif cycle.input_observed_at > cycle.now:
            current = self.store.halt(); state = SupervisedPaperState.HALTED_FUTURE_INPUT
        elif cycle.now - cycle.input_observed_at > self.policy.maximum_input_age:
            current = self.store.halt(); state = SupervisedPaperState.HALTED_STALE_INPUT
        elif current.gateway.reconciliation_required:
            state = SupervisedPaperState.RECONCILIATION_REQUIRED
            if cycle.reconciliation_observation is not None:
                current, reason = self.store.reconcile(current.gateway.snapshot_id,
                                                       cycle.reconciliation_observation)
                if reason is PaperAdapterReason.RECONCILED and not current.gateway.kill_switch_active:
                    state = SupervisedPaperState.HEALTHY
        elif cycle.reconciliation_observation is not None:
            raise SupervisedPaperError("unsolicited reconciliation observation")
        elif cycle.command is not None:
            current, receipt = self.store.execute(cycle.command)
            state = SupervisedPaperState.HEALTHY
        else:
            state = SupervisedPaperState.HEALTHY
        health = self._write_health(current, cycle, state, receipt)
        if state is not SupervisedPaperState.HEALTHY or (receipt is not None and not receipt.accepted):
            self._append_alert(health)
        return current, receipt, health

    def halt_performance_persistence(self, cycle: SupervisedPaperCycleV1):
        """Durably halt and publish health when accounting persistence fails."""
        self._assert_owner(); _utc(cycle.now, "now"); _utc(cycle.input_observed_at, "input_observed_at")
        current = self.store.halt()
        state = SupervisedPaperState.HALTED_PERFORMANCE_PERSISTENCE
        health = self._write_health(current, cycle, state, None)
        self._append_alert(health)
        return current, health

    def _write_health(self, adapter, cycle, state, receipt):
        core = {"session_id": self.session_id, "state": state.value,
            "observed_at": cycle.now.isoformat(), "input_observed_at": cycle.input_observed_at.isoformat(),
            "adapter_id": adapter.adapter_id, "gateway_snapshot_id": adapter.gateway.snapshot_id,
            "receipt_reason": None if receipt is None else receipt.reason.value,
            "kill_switch_active": adapter.gateway.kill_switch_active,
            "reconciliation_required": adapter.gateway.reconciliation_required,
            "trading_authority": False}
        heartbeat = hashlib.sha256(_canonical(core)).hexdigest(); document = {**core, "heartbeat_id": heartbeat}
        temporary = self.health_path.with_name(".latest-health.tmp")
        try:
            with open(temporary, "xb") as stream:
                stream.write(_canonical(document) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.health_path)
        finally: temporary.unlink(missing_ok=True)
        return SupervisedPaperHealthV1(self.session_id, state, cycle.now, cycle.input_observed_at,
            adapter.adapter_id, adapter.gateway.snapshot_id, core["receipt_reason"],
            adapter.gateway.kill_switch_active, adapter.gateway.reconciliation_required,
            heartbeat, False)

    def _append_alert(self, health):
        body = {"schema_version": "supervised-paper-alert-v1", "observed_at": health.observed_at.isoformat(),
            "session_id": health.session_id, "state": health.state.value,
            "adapter_id": health.adapter_id, "gateway_snapshot_id": health.gateway_snapshot_id,
            "receipt_reason": health.receipt_reason, "kill_switch_active": health.kill_switch_active,
            "reconciliation_required": health.reconciliation_required, "trading_authority": False}
        event_id = hashlib.sha256(_canonical(body)).hexdigest(); line = _canonical({"event_id": event_id, **body}) + b"\n"
        existing = self.alerts_path.read_bytes().splitlines() if self.alerts_path.exists() else []
        if line.rstrip() not in existing:
            with open(self.alerts_path, "ab") as stream:
                stream.write(line); stream.flush(); os.fsync(stream.fileno())

    def release(self):
        self._assert_owner(); self.lock_path.unlink(); self._owned = False

    def __enter__(self):
        self.acquire()
        try:
            self.start()
        except Exception:
            if self._owned: self.release()
            raise
        return self
    def __exit__(self, *_):
        if self._owned: self.release()
