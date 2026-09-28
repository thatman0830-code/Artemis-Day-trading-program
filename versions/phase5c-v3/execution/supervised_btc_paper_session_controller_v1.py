"""Fail-closed controller for an assembled supervised BTC paper session."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json

from execution.paper_clock_guard_v1 import PaperClockHealthV1
from execution.btc_archive_snapshot_source_v1 import BTCArchiveSnapshotError
from execution.supervised_btc_paper_session_assembly_v1 import (
    SupervisedBTCPaperSessionAssemblyV1,
)

VERSION="supervised-btc-paper-session-controller-v1"
TRANSIENT_SNAPSHOT_MESSAGES=frozenset(("recorder transaction is in progress",
    "archive changed or checksum conflicted during read"))
SNAPSHOT_RETRY_ATTEMPTS=5
SNAPSHOT_RETRY_SECONDS=0.1


class BTCPaperSessionControllerError(RuntimeError):
    def __init__(self,message,failure_code="CONTROLLER_FAILURE"):
        super().__init__(message);self.failure_code=failure_code


def _id(*values):
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(",",":"),
        default=str).encode()).hexdigest()


@dataclass(frozen=True,slots=True)
class PaperCycleOperationalHealthV1:
    observed_at: datetime
    watchdog_report_id: str
    btc_heartbeat_at: datetime
    clock: PaperClockHealthV1
    watchdog_healthy: bool
    btc_recorder_healthy: bool
    unresolved_gap_count: int
    health_id: str
    trading_authority: bool=False

    def __post_init__(self):
        for value in (self.observed_at,self.btc_heartbeat_at):
            if value.tzinfo is None or value.utcoffset()!=timedelta(0):
                raise BTCPaperSessionControllerError("operational health times must be UTC")
        if (not isinstance(self.clock,PaperClockHealthV1)
                or not isinstance(self.unresolved_gap_count,int)
                or isinstance(self.unresolved_gap_count,bool) or self.unresolved_gap_count<0
                or self.trading_authority is not False):
            raise BTCPaperSessionControllerError("operational health fields are invalid")
        expected=_id(VERSION,self.observed_at,self.watchdog_report_id,self.btc_heartbeat_at,
            self.clock,self.watchdog_healthy,self.btc_recorder_healthy,
            self.unresolved_gap_count,False)
        if self.health_id!=expected:
            raise BTCPaperSessionControllerError("operational health identity mismatch")

    @classmethod
    def create(cls,*,observed_at,watchdog_report_id,btc_heartbeat_at,clock,
            watchdog_healthy,btc_recorder_healthy,unresolved_gap_count):
        identity=_id(VERSION,observed_at,watchdog_report_id,btc_heartbeat_at,clock,
            watchdog_healthy,btc_recorder_healthy,unresolved_gap_count,False)
        return cls(observed_at,watchdog_report_id,btc_heartbeat_at,clock,
            watchdog_healthy,btc_recorder_healthy,unresolved_gap_count,identity,False)


class SupervisedBTCPaperSessionControllerV1:
    def __init__(self,*,assembly,operational_reader,now_reader=None,cycle_input_reader=None):
        if (not isinstance(assembly,SupervisedBTCPaperSessionAssemblyV1)
                or not callable(operational_reader)
                or (now_reader is not None and not callable(now_reader))
                or (cycle_input_reader is not None and not callable(cycle_input_reader))):
            raise BTCPaperSessionControllerError("controller dependencies are invalid")
        self.assembly=assembly;self.operational_reader=operational_reader
        self.now_reader=now_reader or (lambda:datetime.now(timezone.utc))
        self.cycle_input_reader=cycle_input_reader;self.used=False

    def _health(self,now=None):
        value=self.operational_reader()
        if now is None:now=self.now_reader()
        if not isinstance(value,PaperCycleOperationalHealthV1):
            raise BTCPaperSessionControllerError("typed operational health is required")
        if not timedelta(0)<=now-value.observed_at<=timedelta(seconds=30):
            raise BTCPaperSessionControllerError("operational health blocked the paper session","STALE_OPERATIONAL_HEALTH")
        if not timedelta(0)<=now-value.btc_heartbeat_at<=timedelta(seconds=90):
            raise BTCPaperSessionControllerError("operational health blocked the paper session","RECORDER_FAILURE")
        if value.clock.observed_at>now or value.clock.synchronized is not True:
            raise BTCPaperSessionControllerError("operational health blocked the paper session","CLOCK_FAILURE")
        if value.watchdog_healthy is not True:
            raise BTCPaperSessionControllerError("operational health blocked the paper session","WATCHDOG_FAILURE")
        if value.btc_recorder_healthy is not True:
            raise BTCPaperSessionControllerError("operational health blocked the paper session","RECORDER_FAILURE")
        if value.unresolved_gap_count!=0:
            raise BTCPaperSessionControllerError("operational health blocked the paper session","RECORDER_GAP")
        return value.clock

    def run(self,*,waiter,utc_reader=None,monotonic_reader=None,output_path=None):
        if self.used: raise BTCPaperSessionControllerError("controller is single-use")
        if not callable(waiter): raise BTCPaperSessionControllerError("waiter is required")
        self.used=True
        def health_reader(): return self._health()
        def input_reader():
            self._health();now=self.now_reader()
            if self.cycle_input_reader is None:
                return self.assembly.no_signal_input(as_of=now)
            for attempt in range(SNAPSHOT_RETRY_ATTEMPTS):
                try:return self.cycle_input_reader(assembly=self.assembly,as_of=now)
                except BTCArchiveSnapshotError as exc:
                    if str(exc) not in TRANSIENT_SNAPSHOT_MESSAGES:raise
                    if attempt+1==SNAPSHOT_RETRY_ATTEMPTS:
                        raise BTCPaperSessionControllerError(
                            "recorder transaction remained busy after bounded retry",
                            "RECORDER_FAILURE") from exc
                    waiter(SNAPSHOT_RETRY_SECONDS)
                    self._health();now=self.now_reader()
        try:
            return self.assembly.runtime.run(input_reader=input_reader,
                health_reader=health_reader,waiter=waiter,utc_reader=utc_reader,
                monotonic_reader=monotonic_reader,output_path=output_path)
        finally:
            if self.cycle_input_reader is not None and hasattr(self.cycle_input_reader,"close"):
                self.cycle_input_reader.close()
