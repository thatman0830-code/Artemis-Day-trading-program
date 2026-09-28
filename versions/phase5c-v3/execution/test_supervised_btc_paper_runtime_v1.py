from dataclasses import replace
from datetime import timedelta
import hashlib
import json

import pytest

from execution.paper_file_valuation_v1 import PaperFileValuationV1, PaperSnapshotReferenceV1
from execution.strategy_paper_intent_v1 import compile_strategy_paper_intent
from execution.supervised_btc_paper_runtime_v1 import (
    SupervisedBTCPaperRuntimeV1, SupervisedPaperRuntimeError,
    SupervisedPaperRuntimeInputV1,prepare_btc_perpetual_runtime_input,
)
from execution.test_bounded_paper_session_v1 import driver, submit
from execution.test_paper_closed_bar_input_v1 import HEADER, row
from execution.test_paper_clock_guard_v1 import health
from execution.test_paper_performance_ledger_v1 import T, H
from execution.test_strategy_paper_intent_v1 import arguments


def runtime(tmp_path):
    root = tmp_path / "snapshots"; root.mkdir()
    payload = (HEADER + row(-1)).encode()
    (root / "btc.csv").write_bytes(payload)
    reference = PaperSnapshotReferenceV1("btc.csv", hashlib.sha256(payload).hexdigest(), T)
    session = driver(tmp_path)
    valuation = PaperFileValuationV1(session=session, snapshot_root=root, timeframe="1m",
        maximum_bar_age=timedelta(minutes=1), instrument_id="BTC",
        mark_specification_id=H("mark-spec"), source_version="synthetic-file-v1")
    return SupervisedBTCPaperRuntimeV1(valuation, poll_interval=timedelta(seconds=1)), session, reference


def clocks():
    state = {"capture": 0, "calls": 0}
    def mono():
        value = state["capture"] * 1_000_000_000
        state["calls"] += 1
        if state["calls"] % 2 == 0: state["capture"] += 1
        return value
    def utc(): return T + timedelta(seconds=state["capture"])
    return utc, mono


def test_runtime_polls_verified_snapshot_honors_stop_and_writes_summary(tmp_path):
    item, session, reference = runtime(tmp_path)
    def wait(_):
        session.workflow.stop_path.write_text(json.dumps({"session_id":session.workflow.session_id,
            "stop":True,"trading_authority":False}))
    utc, mono = clocks(); output = tmp_path / "result.json"
    result = item.run(input_reader=lambda:SupervisedPaperRuntimeInputV1(reference),
        health_reader=lambda:health(), waiter=wait, utc_reader=utc,
        monotonic_reader=mono, output_path=output)
    assert result.state == "STOPPED" and result.cycles == 1 and result.commands == 0
    assert result.termination_reason == "SUPERVISOR_STOP"
    assert result.trading_authority is False and len(result.runtime_id) == 64
    assert json.loads(output.read_text())["runtime_id"] == result.runtime_id
    assert not session.active and not session.workflow.lock_path.exists()
    with pytest.raises(SupervisedPaperRuntimeError, match="identity"):
        replace(result, runtime_id=H("tampered"))


def test_slow_input_crossing_deadline_stops_cleanly_before_valuation(tmp_path):
    item, session, reference = runtime(tmp_path)
    clock={"seconds":0}
    def utc():return T+timedelta(seconds=clock["seconds"])
    def mono():return clock["seconds"]*1_000_000_000
    def input_reader():
        clock["seconds"]=301
        return SupervisedPaperRuntimeInputV1(reference)
    output=tmp_path/"deadline-result.json"
    result=item.run(input_reader=input_reader,health_reader=lambda:health(),
        waiter=lambda _:None,utc_reader=utc,monotonic_reader=mono,output_path=output)
    assert result.state=="STOPPED" and result.cycles==0 and result.commands==0
    assert result.termination_reason=="SESSION_DEADLINE"
    assert json.loads(output.read_text())["runtime_id"]==result.runtime_id
    assert not session.active and not session.workflow.lock_path.exists()
    assert json.loads((session.workflow.root/"latest-health.json").read_text())["state"]=="STOPPED"


def test_runtime_reserves_poll_interval_for_clean_deadline_stop(tmp_path):
    item,session,reference=runtime(tmp_path);clock={"milliseconds":0};health_calls=[]
    def utc():return T+timedelta(milliseconds=clock["milliseconds"])
    def mono():return clock["milliseconds"]*1_000_000
    def input_reader():
        clock["milliseconds"]=299_500
        return SupervisedPaperRuntimeInputV1(reference)
    result=item.run(input_reader=input_reader,
        health_reader=lambda:(health_calls.append(1)or health()),waiter=lambda _:None,
        utc_reader=utc,monotonic_reader=mono)
    assert result.state=="STOPPED" and result.cycles==0 and result.commands==0
    assert result.termination_reason=="SESSION_DEADLINE"
    assert len(health_calls)==1  # start only; valuation was never entered
    assert result.stopped_at==(T+timedelta(milliseconds=299_500)).isoformat()
    assert not session.active and not session.workflow.lock_path.exists()


def test_entry_command_requires_exact_snapshot_bound_strategy_receipt(tmp_path):
    _, session, reference = runtime(tmp_path)
    session.start(T)
    args = arguments(); args["source_sha256"] = reference.sha256
    receipt = compile_strategy_paper_intent(**args)
    command = submit(session)
    command = command.__class__(command.command_id, command.expected_gateway_snapshot_id,
        submission=command.submission.__class__(command.submission.idempotency_key,
            receipt.intent, command.submission.reference_price, command.submission.requested_at,
            command.submission.market_data_at, command.submission.authorization_id, True, False))
    value = SupervisedPaperRuntimeInputV1(reference, command, receipt)
    assert value.strategy_intent is receipt
    with pytest.raises(SupervisedPaperRuntimeError, match="bound"):
        SupervisedPaperRuntimeInputV1(
            PaperSnapshotReferenceV1(reference.relative_path, H("other"), reference.available_at),
            command, receipt)
    session.stop(T)


def test_runtime_input_accepts_only_snapshot_bound_btc_perpetual_receipt(tmp_path):
    from execution.test_btc_perpetual_paper_gateway_bridge_v1 import perpetual_components,launch
    from execution.btc_perpetual_paper_gateway_bridge_v1 import prepare_btc_perpetual_paper_command
    plan,gateway,now,_=perpetual_components(tmp_path)
    receipt=plan.strategy_intent
    reference=PaperSnapshotReferenceV1("btc.csv",receipt.source_sha256,now)
    value=prepare_btc_perpetual_runtime_input(plan=plan,launch=launch(now),reference=reference,
        expected_gateway_snapshot_id=gateway.snapshot_id,requested_at=now,market_data_at=now)
    command=value.command
    assert value.strategy_intent is receipt and not value.trading_authority
    with pytest.raises(SupervisedPaperRuntimeError,match="bound"):
        SupervisedPaperRuntimeInputV1(
            PaperSnapshotReferenceV1("btc.csv",H("other-perpetual-snapshot"),now),command,receipt)


def test_runtime_rejects_invalid_dependencies_and_reuse(tmp_path):
    item, session, reference = runtime(tmp_path); utc, mono = clocks()
    with pytest.raises(SupervisedPaperRuntimeError, match="dependencies"):
        item.run(input_reader=None, health_reader=lambda:health(), waiter=lambda _:None)
    # Dependency validation consumes nothing and does not start a session.
    assert not session.active


@pytest.mark.parametrize("seconds", [0, -1, 5])
def test_poll_interval_hard_ceiling(tmp_path, seconds):
    item, _, _ = runtime(tmp_path)
    if seconds == 0:
        with pytest.raises(SupervisedPaperRuntimeError):
            SupervisedBTCPaperRuntimeV1(item.valuation, poll_interval=timedelta(0))
    elif seconds < 0 or seconds > 4:
        with pytest.raises(SupervisedPaperRuntimeError):
            SupervisedBTCPaperRuntimeV1(item.valuation, poll_interval=timedelta(seconds=seconds))
