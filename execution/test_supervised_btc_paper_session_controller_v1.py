from dataclasses import replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path

import pytest

from execution.paper_clock_guard_v1 import PaperClockHealthV1
from execution.supervised_btc_paper_session_controller_v1 import (
    BTCPaperSessionControllerError, PaperCycleOperationalHealthV1,
    SupervisedBTCPaperSessionControllerV1,
)
from execution.test_supervised_btc_paper_session_assembly_v1 import prepared, CHECKPOINT
from execution.test_supervised_btc_paper_runtime_v1 import clocks
from execution.test_supervised_paper_launch_evidence_v1 import document
from execution.test_paper_performance_ledger_v1 import T, H
from execution.btc_archive_snapshot_source_v1 import BTCArchiveSnapshotError


def launch_evidence(path):
    value=document();value.update(collected_at=T.isoformat(),btc_heartbeat_at=T.isoformat(),
        repository_checkpoint=CHECKPOINT)
    body={key:item for key,item in value.items() if key!="evidence_id"}
    value["evidence_id"]=hashlib.sha256(json.dumps(body,sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    path.write_text(json.dumps(value))


def health(**changes):
    clock=PaperClockHealthV1(T,True,0,100_000_000,H("clock"))
    values=dict(observed_at=T,watchdog_report_id=H("watchdog"),btc_heartbeat_at=T,
        clock=clock,watchdog_healthy=True,btc_recorder_healthy=True,unresolved_gap_count=0)
    values.update(changes);return PaperCycleOperationalHealthV1.create(**values)


def test_controller_runs_no_signal_cycle_honors_stop_and_persists_result(tmp_path):
    assembly,_=prepared(tmp_path);launch_evidence(tmp_path/"launch-evidence.json")
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=health,now_reader=lambda:T)
    def wait(_):
        assembly.session.workflow.stop_path.write_text(json.dumps({
            "session_id":assembly.session.workflow.session_id,"stop":True,
            "trading_authority":False}))
    utc,mono=clocks();output=tmp_path/"runtime-result.json"
    result=controller.run(waiter=wait,utc_reader=utc,monotonic_reader=mono,output_path=output)
    assert result.state=="STOPPED" and result.cycles==1 and result.commands==0
    assert result.termination_reason=="SUPERVISOR_STOP"
    assert json.loads(output.read_text())["runtime_id"]==result.runtime_id
    assert not assembly.session.active and result.trading_authority is False


def test_controller_uses_injected_cycle_input_boundary(tmp_path):
    assembly,_=prepared(tmp_path);launch_evidence(tmp_path/"launch-evidence.json")
    calls=[]
    def cycle_input_reader(*,assembly,as_of):
        calls.append((assembly.assembly_id,as_of))
        return assembly.no_signal_input(as_of=as_of)
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=health,now_reader=lambda:T,
        cycle_input_reader=cycle_input_reader)
    def wait(_):
        assembly.session.workflow.stop_path.write_text(json.dumps({
            "session_id":assembly.session.workflow.session_id,"stop":True,
            "trading_authority":False}))
    utc,mono=clocks()
    result=controller.run(waiter=wait,utc_reader=utc,monotonic_reader=mono)
    assert calls==[(assembly.assembly_id,T)]
    assert result.state=="STOPPED" and result.commands==0


def test_controller_bounded_retry_survives_brief_recorder_transaction(tmp_path):
    assembly,_=prepared(tmp_path);launch_evidence(tmp_path/"launch-evidence.json");calls=[];waits=[]
    def cycle_input_reader(*,assembly,as_of):
        calls.append(as_of)
        if len(calls)<3:raise BTCArchiveSnapshotError("recorder transaction is in progress")
        return assembly.no_signal_input(as_of=as_of)
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=health,now_reader=lambda:T,cycle_input_reader=cycle_input_reader)
    def wait(seconds):
        waits.append(seconds)
        if len(calls)>=3:assembly.session.workflow.stop_path.write_text(json.dumps({
            "session_id":assembly.session.workflow.session_id,"stop":True,"trading_authority":False}))
    utc,mono=clocks();result=controller.run(waiter=wait,utc_reader=utc,monotonic_reader=mono)
    assert len(calls)==3 and waits[:2]==[0.1,0.1]
    assert result.state=="STOPPED" and result.commands==0


def test_controller_persistent_recorder_transaction_fails_after_exact_bound(tmp_path):
    assembly,_=prepared(tmp_path);launch_evidence(tmp_path/"launch-evidence.json");calls=[];waits=[]
    def busy(**_):calls.append(1);raise BTCArchiveSnapshotError("recorder transaction is in progress")
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=health,now_reader=lambda:T,cycle_input_reader=busy)
    utc,mono=clocks()
    with pytest.raises(BTCPaperSessionControllerError,match="bounded retry") as caught:
        controller.run(waiter=waits.append,utc_reader=utc,monotonic_reader=mono)
    assert len(calls)==5 and waits==[0.1]*4 and caught.value.failure_code=="RECORDER_FAILURE"


def test_controller_does_not_retry_nontransient_snapshot_failure(tmp_path):
    assembly,_=prepared(tmp_path);launch_evidence(tmp_path/"launch-evidence.json");calls=[]
    def corrupt(**_):calls.append(1);raise BTCArchiveSnapshotError("manifest is invalid")
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=health,now_reader=lambda:T,cycle_input_reader=corrupt)
    utc,mono=clocks()
    with pytest.raises(BTCArchiveSnapshotError,match="manifest is invalid"):
        controller.run(waiter=lambda _:pytest.fail("nontransient failure was retried"),
            utc_reader=utc,monotonic_reader=mono)
    assert len(calls)==1


def test_controller_rejects_invalid_cycle_input_dependency(tmp_path):
    assembly,_=prepared(tmp_path)
    with pytest.raises(BTCPaperSessionControllerError,match="dependencies"):
        SupervisedBTCPaperSessionControllerV1(assembly=assembly,
            operational_reader=health,cycle_input_reader=object())


@pytest.mark.parametrize("change",[
    {"watchdog_healthy":False},{"btc_recorder_healthy":False},
    {"unresolved_gap_count":1},{"observed_at":T-timedelta(seconds=31)},
    {"btc_heartbeat_at":T-timedelta(seconds=91)},
])
def test_controller_blocks_unhealthy_or_stale_operation_before_session_start(tmp_path,change):
    assembly,_=prepared(tmp_path);launch_evidence(tmp_path/"launch-evidence.json")
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=lambda:health(**change),now_reader=lambda:T)
    utc,mono=clocks()
    with pytest.raises(Exception):
        controller.run(waiter=lambda _:None,utc_reader=utc,monotonic_reader=mono)
    assert not assembly.session.active
    assert not assembly.session.workflow.lock_path.exists()


@pytest.mark.parametrize("change,code",[
    ({"watchdog_healthy":False},"WATCHDOG_FAILURE"),
    ({"btc_recorder_healthy":False},"RECORDER_FAILURE"),
    ({"unresolved_gap_count":1},"RECORDER_GAP"),
    ({"observed_at":T-timedelta(seconds=31)},"STALE_OPERATIONAL_HEALTH"),
    ({"btc_heartbeat_at":T-timedelta(seconds=91)},"RECORDER_FAILURE"),
])
def test_operational_health_failure_has_stable_diagnostic_code(tmp_path,change,code):
    assembly,_=prepared(tmp_path)
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=lambda:health(**change),now_reader=lambda:T)
    with pytest.raises(Exception) as caught:
        controller.run(waiter=lambda _:None)
    from execution.paper_attempt_failure_v1 import classify_failure
    assert classify_failure(caught.value)==code


def test_health_identity_and_controller_reuse_fail_closed(tmp_path):
    with pytest.raises(BTCPaperSessionControllerError,match="identity"):
        replace(health(),health_id="f"*64)
    assembly,_=prepared(tmp_path)
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=health,now_reader=lambda:T)
    controller.used=True
    with pytest.raises(BTCPaperSessionControllerError,match="single-use"):
        controller.run(waiter=lambda _:None)


def test_health_is_timestamped_before_controller_samples_now(tmp_path):
    assembly,_=prepared(tmp_path);calls=[]
    def reader():calls.append("health");return health()
    def now():calls.append("now");return T
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=reader,now_reader=now)
    assert controller._health()==health().clock
    assert calls==["health","now"]


def test_controller_uses_live_health_after_immutable_admission(tmp_path):
    assembly,_=prepared(tmp_path);launch_evidence(tmp_path/"launch-evidence.json")
    assembly.session.start(T)
    assembly.session.evidence_path.write_text("corrupt")
    assert assembly.session._decision(T+timedelta(seconds=91)).eligible
    assembly.session.stop(T+timedelta(seconds=92))


def test_controller_core_has_no_platform_or_order_transport():
    source=Path(__file__).with_name("supervised_btc_paper_session_controller_v1.py").read_text("utf-8").lower()
    for prohibited in ("subprocess","powershell","urllib","requests","websocket","place_order","private_key"):
        assert prohibited not in source
    assert "trading_authority: bool=false" in source
