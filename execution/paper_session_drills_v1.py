"""Deterministic, bounded offline runner and recovery drills."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib, json
from pathlib import Path
from execution.paper_gateway_v2 import PaperGatewaySnapshotV1
from execution.paper_session_supervisor_v1 import PaperSessionPolicyV1, PaperSessionState, PaperSessionSupervisorV1

@dataclass(frozen=True,slots=True)
class DrillObservationV1:
    name:str;passed:bool;reason:str

@dataclass(frozen=True,slots=True)
class DrillReportV1:
    observations:tuple[DrillObservationV1,...];report_id:str;trading_authority:bool=False

def run_bounded(root:Path,initial:PaperGatewaySnapshotV1,policy:PaperSessionPolicyV1,
                cycles:tuple[tuple[datetime,datetime],...],session_id:str="0"*32):
    if not cycles: raise ValueError("bounded runner requires at least one cycle")
    health=[]
    with PaperSessionSupervisorV1(root,policy,session_id) as supervisor:
        state=supervisor.load_or_initialize(initial)
        for now,observed in cycles:
            state,item=supervisor.cycle(state,now,observed);health.append(item)
            if item.state is not PaperSessionState.HEALTHY: break
    return state,tuple(health)

def run_recovery_drills(root:Path,initial:PaperGatewaySnapshotV1,now:datetime):
    root=Path(root);root.mkdir();policy=PaperSessionPolicyV1(timedelta(seconds=5),timedelta(seconds=1));items=[]
    healthy_root=root/"healthy";healthy_root.mkdir()
    state,health=run_bounded(healthy_root,initial,policy,((now,now),))
    items.append(DrillObservationV1("healthy-cycle",health[-1].state is PaperSessionState.HEALTHY,"bounded healthy cycle"))
    stale_root=root/"stale";stale_root.mkdir()
    state,health=run_bounded(stale_root,initial,policy,((now,now-timedelta(seconds=6)),))
    items.append(DrillObservationV1("stale-input-halt",state.kill_switch_active and not state.connected,"stale input halted"))
    future_root=root/"future";future_root.mkdir()
    state,health=run_bounded(future_root,initial,policy,((now,now+timedelta(microseconds=1)),))
    items.append(DrillObservationV1("future-input-halt",state.kill_switch_active and not state.connected,"future input halted"))
    restart_root=root/"restart";restart_root.mkdir();run_bounded(restart_root,initial,policy,((now,now),),"1"*32)
    with PaperSessionSupervisorV1(restart_root,policy,"2"*32) as supervisor: restarted=supervisor.load_or_initialize()
    items.append(DrillObservationV1("restart-reconciliation",not restarted.connected and restarted.reconciliation_required,"restart forced reconciliation"))
    lock_root=root/"contention";lock_root.mkdir();one=PaperSessionSupervisorV1(lock_root,policy,"3"*32);two=PaperSessionSupervisorV1(lock_root,policy,"4"*32);one.acquire()
    try:
        try: two.acquire();blocked=False
        except Exception: blocked=True
    finally: one.release()
    items.append(DrillObservationV1("single-owner",blocked,"second owner rejected"))
    stop_root=root/"stop";stop_root.mkdir()
    with PaperSessionSupervisorV1(stop_root,policy,"5"*32) as supervisor:
        stopped=supervisor.load_or_initialize(initial);supervisor.stop_path.write_text(json.dumps({"session_id":"5"*32,"stop":True,"trading_authority":False}))
        stopped,stop_health=supervisor.cycle(stopped,now,now)
    items.append(DrillObservationV1("controlled-stop",stop_health.state is PaperSessionState.STOPPED,"identity-bound stop"))
    corrupt_root=root/"corrupt";corrupt_root.mkdir();run_bounded(corrupt_root,initial,policy,((now,now),),"6"*32)
    (corrupt_root/"gateway-checkpoint.json").write_bytes(b"corrupt")
    try:
        with PaperSessionSupervisorV1(corrupt_root,policy,"7"*32) as supervisor: supervisor.load_or_initialize()
        rejected=False
    except Exception: rejected=True
    items.append(DrillObservationV1("corrupt-checkpoint",rejected,"corruption rejected"))
    payload=[(x.name,x.passed,x.reason) for x in items];report_id=hashlib.sha256(json.dumps(payload,separators=(",",":" )).encode()).hexdigest()
    return DrillReportV1(tuple(items),report_id,False)
