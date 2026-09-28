"""Non-blocking single-owner worker for canonical BTC strategy observations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta
from enum import Enum
import hashlib,json,os,time
from pathlib import Path
import multiprocessing,threading,uuid

from execution.btc_canonical_strategy_observation_v1 import (
    ACTIONABLE,BTCCanonicalStrategyObservationV1,BTCCanonicalStrategyObserverV1,
    _observe_snapshots,
)
from execution.btc_archive_snapshot_source_v1 import read_btc_archive_snapshot

VERSION="btc-canonical-strategy-worker-v1"
HISTORY_VERSION="btc-canonical-strategy-status-history-v1"
MAXIMUM_OBSERVATION_AGE=timedelta(seconds=90)
PROBE_INTERVAL=timedelta(seconds=20)


class BTCStrategyWorkerError(RuntimeError):pass
class BTCStrategyWorkerState(str,Enum):
    IDLE="IDLE";EVALUATING="EVALUATING";READY="READY";FAILED="FAILED"


def _utc(value,name):
    if not isinstance(value,datetime)or value.tzinfo is None or value.utcoffset()!=timedelta(0):
        raise BTCStrategyWorkerError(f"{name} must be UTC")


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":")).encode()


def _process_observe(command_connection,result_connection,snapshot_root):
    """Warm isolated replay loop over exact parent-captured snapshot pairs."""
    try:
        while True:
            request=command_connection.recv()
            if request is None:return
            one,five,requested_at=request
            try:
                value=_observe_snapshots(one=one,five=five,snapshot_root=snapshot_root,
                    as_of=requested_at)
                key=(value.one_minute.reference.sha256,value.five_minute.reference.sha256)
                result_connection.send(("READY",value,key))
            except Exception as exc:
                result_connection.send(("FAILED",type(exc).__name__,None))
    except (EOFError,OSError):return
    finally:command_connection.close();result_connection.close()


@dataclass(frozen=True,slots=True)
class BTCStrategyWorkerStatusV1:
    state: BTCStrategyWorkerState
    observed_at: datetime
    observation_id: str|None
    result_id: str|None
    actionable: bool
    failure_code: str|None
    result_outcome: str|None
    qualification_present: bool|None
    entry_zone_present: bool|None
    decision_reason: str|None
    status_id: str
    trading_authority: bool=False

    def __post_init__(self):
        _utc(self.observed_at,"observed_at")
        if (not isinstance(self.state,BTCStrategyWorkerState)
                or self.actionable is not (self.state is BTCStrategyWorkerState.READY
                    and self.observation_id is not None and self.result_id is not None
                    and self.failure_code is None and self.actionable)
                or (self.state is BTCStrategyWorkerState.READY) is not
                    (self.result_outcome is not None and self.qualification_present is not None
                    and self.entry_zone_present is not None and self.decision_reason is not None)
                or self.trading_authority is not False):
            raise BTCStrategyWorkerError("worker status fields are invalid")
        body={"version":VERSION,"state":self.state.value,"observed_at":self.observed_at.isoformat(),
            "observation_id":self.observation_id,"result_id":self.result_id,
            "actionable":self.actionable,"failure_code":self.failure_code,
            "result_outcome":self.result_outcome,
            "qualification_present":self.qualification_present,
            "entry_zone_present":self.entry_zone_present,
            "decision_reason":self.decision_reason,
            "trading_authority":False}
        if self.status_id!=hashlib.sha256(_canonical(body)).hexdigest():
            raise BTCStrategyWorkerError("worker status identity is invalid")


def _status(state,now,observation=None,failure_code=None):
    ready=state is BTCStrategyWorkerState.READY
    actionable=bool(ready and observation is not None and observation.actionable)
    outcome=observation.result.outcome.value if ready and observation is not None else None
    qualification=(observation.result.setup_fact.final_qualification is not None
        if ready and observation is not None else None)
    entry_zone=(observation.result.setup_fact.entry_zone is not None
        if ready and observation is not None else None)
    canonical_reason=(observation.result.setup_fact.canonical_reason
        if ready and observation is not None else None)
    outcome_reason=(f"OUTCOME_{outcome}"+(f":{canonical_reason}" if canonical_reason else "")
        if ready and observation is not None else None)
    reason=(None if not ready else "ACTIONABLE" if actionable else
        outcome_reason if observation.result.outcome not in ACTIONABLE else
        "MISSING_FINAL_QUALIFICATION" if not qualification else "MISSING_ENTRY_ZONE")
    body={"version":VERSION,"state":state.value,"observed_at":now.isoformat(),
        "observation_id":None if observation is None else observation.observation_id,
        "result_id":None if observation is None else observation.result.id,
        "actionable":actionable,"failure_code":failure_code,"result_outcome":outcome,
        "qualification_present":qualification,"entry_zone_present":entry_zone,
        "decision_reason":reason,"trading_authority":False}
    identity=hashlib.sha256(_canonical(body)).hexdigest()
    return BTCStrategyWorkerStatusV1(state,now,body["observation_id"],body["result_id"],
        actionable,failure_code,outcome,qualification,entry_zone,reason,identity,False)


class BTCCanonicalStrategyWorkerV1:
    def __init__(self,*,archive_root,snapshot_root,status_path,status_history_path=None,
            evaluator=None,probe=None):
        self.archive_root=Path(archive_root).absolute();self.snapshot_root=Path(snapshot_root).absolute()
        self.status_path=Path(status_path).absolute()
        self.status_history_path=(None if status_history_path is None else
            Path(status_history_path).absolute())
        self._history_sequence=0;self._history_previous_id=None
        if self.status_history_path is not None and self.status_history_path.exists():
            raise BTCStrategyWorkerError("worker status history already exists")
        observer=BTCCanonicalStrategyObserverV1(archive_root=self.archive_root,
            snapshot_root=self.snapshot_root)
        self._process_mode=evaluator is None and probe is None
        self.evaluator=evaluator or observer.observe
        def default_probe(*,as_of):
            one=read_btc_archive_snapshot(self.archive_root,timeframe="1m",as_of=as_of,
                snapshot_root=self.snapshot_root)
            five=read_btc_archive_snapshot(self.archive_root,timeframe="5m",as_of=as_of,
                snapshot_root=self.snapshot_root)
            if (one.manifest_sha256,one.archive_id,one.manifest_updated_at)!=(
                    five.manifest_sha256,five.archive_id,five.manifest_updated_at):
                raise BTCStrategyWorkerError("strategy probe streams conflict")
            return one.reference.sha256,five.reference.sha256
        self.probe=probe or default_probe
        if not callable(self.evaluator)or not callable(self.probe):
            raise BTCStrategyWorkerError("worker dependencies are invalid")
        self._lock=threading.Lock();self._thread=None;self._process=None;self._pipe=None
        self._receiver=None;self._commands=None;self._evaluating=False
        self._observation=None
        self._failure=None;self._requested_at=None;self._requested_key=None
        self._evaluated_key=None;self._completed_monotonic=None

    def _write(self,status):
        self.status_path.parent.mkdir(parents=True,exist_ok=True)
        if self.status_path.is_symlink()or self.status_path.parent.is_symlink():
            raise BTCStrategyWorkerError("worker status path is unsafe")
        document={"state":status.state.value,"observed_at":status.observed_at.isoformat(),
            "observation_id":status.observation_id,"result_id":status.result_id,
            "actionable":status.actionable,"failure_code":status.failure_code,
            "result_outcome":status.result_outcome,
            "qualification_present":status.qualification_present,
            "entry_zone_present":status.entry_zone_present,
            "decision_reason":status.decision_reason,
            "status_id":status.status_id,"trading_authority":False}
        temporary=self.status_path.with_name(f".{self.status_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary,"xb")as stream:
                stream.write(_canonical(document)+b"\n");stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.status_path)
        finally:temporary.unlink(missing_ok=True)
        if self.status_history_path is not None:
            history=self.status_history_path
            history.parent.mkdir(parents=True,exist_ok=True)
            if history.is_symlink()or history.parent.is_symlink():
                raise BTCStrategyWorkerError("worker status history path is unsafe")
            body={"schema_version":HISTORY_VERSION,"sequence":self._history_sequence,
                "previous_event_id":self._history_previous_id,"status_id":status.status_id,
                "state":status.state.value,"observed_at":status.observed_at.isoformat(),
                "observation_id":status.observation_id,"result_id":status.result_id,
                "actionable":status.actionable,"failure_code":status.failure_code,
                "result_outcome":status.result_outcome,
                "qualification_present":status.qualification_present,
                "entry_zone_present":status.entry_zone_present,
                "decision_reason":status.decision_reason,
                "trading_authority":False}
            event_id=hashlib.sha256(_canonical(body)).hexdigest()
            with open(history,"ab")as stream:
                stream.write(_canonical({**body,"event_id":event_id})+b"\n")
                stream.flush();os.fsync(stream.fileno())
            self._history_sequence+=1;self._history_previous_id=event_id

    def _evaluate(self,requested_at):
        try:
            requested_key=tuple(self.probe(as_of=requested_at))
            if len(requested_key)!=2 or any(not isinstance(item,str)or len(item)!=64 for item in requested_key):
                raise BTCStrategyWorkerError("strategy probe identity is invalid")
            with self._lock:
                existing=self._observation;existing_key=self._evaluated_key
            if existing is not None and requested_key==existing_key:
                with self._lock:
                    self._failure=None;self._requested_key=requested_key
                    self._completed_monotonic=time.monotonic()
                return
            value=self.evaluator(as_of=requested_at)
            if not isinstance(value,BTCCanonicalStrategyObservationV1):
                raise BTCStrategyWorkerError("evaluator returned an invalid observation")
            with self._lock:
                self._observation=value;self._failure=None;self._requested_key=requested_key
                self._evaluated_key=requested_key;self._completed_monotonic=time.monotonic()
        except Exception as exc:
            with self._lock:self._observation=None;self._failure=type(exc).__name__

    def _running(self):
        if self._process_mode:
            return self._evaluating
        return self._thread is not None and self._thread.is_alive()

    def _receive_process(self,connection):
        """Drain the child pipe off-loop so a large typed result cannot deadlock."""
        try:
            while True:
                state,value,key=connection.recv()
                with self._lock:
                    if state=="READY" and isinstance(value,BTCCanonicalStrategyObservationV1):
                        self._observation=value;self._evaluated_key=tuple(key)
                        self._requested_key=tuple(key);self._failure=None
                        self._completed_monotonic=time.monotonic()
                    else:self._observation=None;self._failure=str(value)
                    self._evaluating=False
        except (EOFError,OSError,ValueError,TypeError):
            with self._lock:
                self._observation=None;self._failure="WorkerProcessNoResult"
                self._evaluating=False
        finally:
            connection.close()

    def _start(self,as_of):
        if self._process_mode:
            # Capture one transaction-consistent immutable pair before Windows
            # spawn/import latency can move the live recorder beyond `as_of`.
            one=read_btc_archive_snapshot(self.archive_root,timeframe="1m",as_of=as_of,
                snapshot_root=self.snapshot_root)
            five=read_btc_archive_snapshot(self.archive_root,timeframe="5m",as_of=as_of,
                snapshot_root=self.snapshot_root)
            if (one.manifest_sha256,one.archive_id,one.manifest_updated_at)!=(
                    five.manifest_sha256,five.archive_id,five.manifest_updated_at):
                raise BTCStrategyWorkerError("strategy snapshot streams conflict")
            requested_key=(one.reference.sha256,five.reference.sha256)
            # Reuse the already-published immutable observation when the
            # recorder manifest has not changed.  The process boundary stays
            # intact, while avoiding a full historical replay every probe.
            if self._observation is not None and requested_key==self._evaluated_key:
                self._requested_key=requested_key;self._failure=None
                self._completed_monotonic=time.monotonic()
                return
            if self._process is None:
                context=multiprocessing.get_context("spawn")
                command_child,self._commands=context.Pipe(duplex=False)
                self._pipe,result_child=context.Pipe(duplex=False)
                self._process=context.Process(target=_process_observe,
                    args=(command_child,result_child,self.snapshot_root),daemon=True,
                    name="btc-canonical-strategy-worker")
                self._process.start();command_child.close();result_child.close()
                self._receiver=threading.Thread(target=self._receive_process,args=(self._pipe,),
                    daemon=True,name="btc-canonical-strategy-result-receiver")
                self._receiver.start()
            if not self._process.is_alive():
                raise BTCStrategyWorkerError("strategy worker process stopped")
            self._requested_key=requested_key
            self._commands.send((one,five,as_of));self._evaluating=True
        else:
            self._thread=threading.Thread(target=self._evaluate,args=(as_of,),daemon=True,
                name="btc-canonical-strategy-worker");self._thread.start()

    def poll(self,*,as_of):
        _utc(as_of,"as_of")
        with self._lock:
            running=self._running()
            if running:
                status=_status(BTCStrategyWorkerState.EVALUATING,as_of)
            else:
                if not self._process_mode and self._thread is not None:
                    self._thread.join(timeout=0);self._thread=None
                observation=self._observation;failure=self._failure
                fresh=(observation is not None and timedelta(0)<=
                    as_of-observation.one_minute.manifest_updated_at<=MAXIMUM_OBSERVATION_AGE)
                probe_fresh=(self._completed_monotonic is not None and
                    0<=time.monotonic()-self._completed_monotonic<
                    PROBE_INTERVAL.total_seconds())
                if failure is not None:
                    status=_status(BTCStrategyWorkerState.FAILED,as_of,
                        failure_code=failure)
                elif fresh and probe_fresh:
                    status=_status(BTCStrategyWorkerState.READY,as_of,observation)
                else:
                    status=_status(BTCStrategyWorkerState.IDLE,as_of)
                    self._requested_at=as_of;self._failure=None
                    try:self._start(as_of)
                    except Exception as exc:
                        self._failure=type(exc).__name__
                        status=_status(BTCStrategyWorkerState.FAILED,as_of,
                            failure_code=self._failure)
        self._write(status);return status

    def ready_observation(self,*,as_of):
        status=self.poll(as_of=as_of)
        if status.state is not BTCStrategyWorkerState.READY:return status,None
        with self._lock:
            observation=self._observation
        if observation is None or observation.observation_id!=status.observation_id:
            raise BTCStrategyWorkerError("ready observation changed during read")
        return status,observation

    def close(self):
        """Release the isolated production worker at the session boundary."""
        receiver=None
        with self._lock:
            if self._process is not None:
                if self._process.is_alive() and self._commands is not None:
                    try:self._commands.send(None)
                    except (BrokenPipeError,EOFError,OSError):pass
                self._process.join(timeout=2)
                if self._process.is_alive():self._process.terminate()
                self._process.join(timeout=2);self._process=None
            if self._commands is not None:self._commands.close();self._commands=None
            if self._pipe is not None:self._pipe.close();self._pipe=None
            self._evaluating=False
            receiver=self._receiver;self._receiver=None
        if receiver is not None:receiver.join(timeout=2)
