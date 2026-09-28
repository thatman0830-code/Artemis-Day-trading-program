"""Single-owner, offline supervision for durable paper-gateway sessions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import uuid

from execution.paper_gateway_checkpoint_v1 import PaperCheckpointError, PaperGatewayCheckpointStoreV1
from execution.paper_gateway_v2 import PaperGatewaySnapshotV1


class PaperSessionError(RuntimeError): pass


class PaperSessionState(str, Enum):
    HEALTHY = "HEALTHY"
    HALTED_STALE_INPUT = "HALTED_STALE_INPUT"
    HALTED_FUTURE_INPUT = "HALTED_FUTURE_INPUT"
    STOPPED = "STOPPED"


def _utc(value: datetime, name: str):
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise PaperSessionError(f"{name} must be UTC")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class PaperSessionPolicyV1:
    maximum_input_age: timedelta
    heartbeat_interval: timedelta

    def __post_init__(self):
        if self.maximum_input_age <= timedelta(0) or self.heartbeat_interval <= timedelta(0):
            raise ValueError("session durations must be positive")


@dataclass(frozen=True, slots=True)
class PaperSessionHealthV1:
    session_id: str
    state: PaperSessionState
    observed_at: datetime
    input_observed_at: datetime | None
    gateway_snapshot_id: str
    kill_switch_active: bool
    reconciliation_required: bool
    stop_requested: bool
    heartbeat_id: str
    trading_authority: bool = False


class PaperSessionSupervisorV1:
    def __init__(self, root: Path, policy: PaperSessionPolicyV1, session_id: str | None = None):
        self.root=Path(root);self.policy=policy;self.session_id=session_id or uuid.uuid4().hex
        if len(self.session_id)!=32 or any(c not in "0123456789abcdef" for c in self.session_id):
            raise ValueError("session_id must be lowercase UUID hex")
        self.lock_path=self.root/"paper-session.lock";self.stop_path=self.root/"stop-request.json"
        self.health_path=self.root/"latest-health.json";self.store=PaperGatewayCheckpointStoreV1(self.root/"gateway-checkpoint.json")
        self._owned=False

    def acquire(self):
        if not self.root.is_dir() or self.lock_path.is_symlink():
            raise PaperSessionError("session root is missing or unsafe")
        payload=_canonical({"session_id":self.session_id,"trading_authority":False})
        try: fd=os.open(self.lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as exc: raise PaperSessionError("paper session already owned") from exc
        try:
            os.write(fd,payload);os.fsync(fd)
        except Exception:
            os.close(fd);self.lock_path.unlink(missing_ok=True);raise
        os.close(fd);self._owned=True

    def _assert_owner(self):
        if not self._owned or not self.lock_path.is_file() or self.lock_path.is_symlink():
            raise PaperSessionError("paper session ownership lost")
        try: owner=json.loads(self.lock_path.read_text("utf-8"))
        except Exception as exc: raise PaperSessionError("paper session lock unreadable") from exc
        if owner != {"session_id":self.session_id,"trading_authority":False}:
            raise PaperSessionError("paper session ownership mismatch")

    def load_or_initialize(self, initial: PaperGatewaySnapshotV1 | None = None):
        self._assert_owner()
        if self.store.path.exists():
            restarted=self.store.load().disconnect()
            self.store.save(restarted)
            return restarted
        if initial is None: raise PaperSessionError("verified checkpoint or explicit initial state required")
        self.store.save(initial);return initial

    def _stop_requested(self):
        if not self.stop_path.exists(): return False
        try: value=json.loads(self.stop_path.read_text("utf-8"))
        except Exception as exc: raise PaperSessionError("stop request is unreadable") from exc
        if value != {"session_id":self.session_id,"stop":True,"trading_authority":False}:
            raise PaperSessionError("stop request identity mismatch")
        return True

    def cycle(self, snapshot: PaperGatewaySnapshotV1, now: datetime, input_observed_at: datetime):
        self._assert_owner();_utc(now,"now");_utc(input_observed_at,"input_observed_at")
        stop=self._stop_requested();state=PaperSessionState.HEALTHY
        if stop: state=PaperSessionState.STOPPED
        elif input_observed_at>now:
            snapshot=snapshot.activate_kill_switch().disconnect();state=PaperSessionState.HALTED_FUTURE_INPUT
        elif now-input_observed_at>self.policy.maximum_input_age:
            snapshot=snapshot.activate_kill_switch().disconnect();state=PaperSessionState.HALTED_STALE_INPUT
        self.store.save(snapshot)
        core={"session_id":self.session_id,"state":state.value,"observed_at":now.isoformat(),
            "input_observed_at":input_observed_at.isoformat(),"gateway_snapshot_id":snapshot.snapshot_id,
            "kill_switch_active":snapshot.kill_switch_active,"reconciliation_required":snapshot.reconciliation_required,
            "stop_requested":stop,"trading_authority":False}
        heartbeat=hashlib.sha256(_canonical(core)).hexdigest();document={**core,"heartbeat_id":heartbeat}
        temp=self.health_path.with_name(f".{self.health_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temp,"xb") as stream: stream.write(_canonical(document)+b"\n");stream.flush();os.fsync(stream.fileno())
            os.replace(temp,self.health_path)
        finally: temp.unlink(missing_ok=True)
        return snapshot,PaperSessionHealthV1(self.session_id,state,now,input_observed_at,snapshot.snapshot_id,
            snapshot.kill_switch_active,snapshot.reconciliation_required,stop,heartbeat,False)

    def release(self):
        self._assert_owner();self.lock_path.unlink();self._owned=False

    def __enter__(self): self.acquire();return self
    def __exit__(self,*_):
        if self._owned: self.release()
