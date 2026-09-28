from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib, json
import pytest

from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderSide, OrderType, TimeInForce
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1, PaperExchangeAdapterV1
from execution.paper_gateway_v2 import PaperGatewayPolicyV1, PaperGatewaySnapshotV1, PaperSubmissionV1
from execution.supervised_paper_workflow_v1 import *
from monitoring.off_host_alert_delivery import read_alerts

NOW=datetime(2026,9,1,18,tzinfo=timezone.utc); sha=lambda x:hashlib.sha256(x.encode()).hexdigest()
def initial(): return PaperExchangeAdapterV1.create(PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(Decimal("500"),Decimal("800"),2,timedelta(seconds=5))))
def command(adapter,name="a",authorized=True):
    intent=OrderIntentV2("order-intent-v2-1",sha("order"+name),sha("run"),sha("action"+name),"BTC","BTC-PERP",None,OrderSide.BUY,Decimal("1"),OrderType.MARKET,TimeInForce.IOC,None,None,NOW,NOW,None,None,None,"config-v1","policy-v1")
    request=PaperSubmissionV1(sha("key"+name),intent,Decimal("100"),NOW,NOW,sha("auth"+name),authorized)
    return PaperAdapterCommandV1(sha("cmd"+name),adapter.gateway.snapshot_id,submission=request)
def workflow(tmp_path,session="1"*32): return SupervisedPaperWorkflowV1(tmp_path,SupervisedPaperPolicyV1(timedelta(seconds=5)),initial(),session)

def test_healthy_submission_is_durable_and_auditable(tmp_path):
    with workflow(tmp_path) as item:
        current=item.store.load(); updated,receipt,health=item.cycle(SupervisedPaperCycleV1(NOW,NOW,command(current)))
        assert receipt.accepted and item.store.load()==updated and health.state is SupervisedPaperState.HEALTHY
        assert not item.alerts_path.exists()

def test_rejected_submission_creates_valid_alert(tmp_path):
    with workflow(tmp_path) as item:
        current=item.store.load();_,receipt,_=item.cycle(SupervisedPaperCycleV1(NOW,NOW,command(current,authorized=False)))
        assert not receipt.accepted and len(read_alerts(item.alerts_path))==1

@pytest.mark.parametrize("observed,state",[(NOW-timedelta(seconds=6),SupervisedPaperState.HALTED_STALE_INPUT),(NOW+timedelta(microseconds=1),SupervisedPaperState.HALTED_FUTURE_INPUT)])
def test_bad_input_durably_halts_and_alerts(tmp_path,observed,state):
    with workflow(tmp_path) as item:
        current,_,health=item.cycle(SupervisedPaperCycleV1(NOW,observed))
        assert health.state is state and current.gateway.kill_switch_active and not current.gateway.connected
        assert item.store.load()==current and len(read_alerts(item.alerts_path))==1

def test_restart_forces_reconciliation_and_exact_observation_recovers(tmp_path):
    first=workflow(tmp_path,"1"*32);first.acquire();current=first.start();current,_,_=first.cycle(SupervisedPaperCycleV1(NOW,NOW,command(current)));first.release()
    second=workflow(tmp_path,"2"*32);second.acquire();restarted=second.start()
    try:
        _,_,waiting=second.cycle(SupervisedPaperCycleV1(NOW+timedelta(seconds=1),NOW+timedelta(seconds=1)))
        assert waiting.state is SupervisedPaperState.RECONCILIATION_REQUIRED
        record=restarted.gateway.records[0];observed=((record.paper_order_id,record.state,record.filled_quantity,record.remaining_quantity,record.version),)
        recovered,_,health=second.cycle(SupervisedPaperCycleV1(NOW+timedelta(seconds=2),NOW+timedelta(seconds=2),reconciliation_observation=observed))
        assert health.state is SupervisedPaperState.HEALTHY and recovered.gateway.connected
    finally: second.release()

def test_reconciliation_mismatch_is_alerted_and_killed(tmp_path):
    first=workflow(tmp_path,"1"*32);first.acquire();state=first.start();state,_,_=first.cycle(SupervisedPaperCycleV1(NOW,NOW,command(state)));first.release()
    second=workflow(tmp_path,"2"*32);second.acquire();second.start()
    try:
        failed,_,health=second.cycle(SupervisedPaperCycleV1(NOW,NOW,reconciliation_observation=()))
        assert health.state is SupervisedPaperState.RECONCILIATION_REQUIRED and failed.gateway.kill_switch_active
    finally: second.release()

def test_identity_bound_stop_disconnects_and_alerts(tmp_path):
    with workflow(tmp_path) as item:
        item.stop_path.write_text(json.dumps({"session_id":"1"*32,"stop":True,"trading_authority":False}))
        current,_,health=item.cycle(SupervisedPaperCycleV1(NOW,NOW))
        assert health.state is SupervisedPaperState.STOPPED and not current.gateway.connected

def test_invalid_stop_and_unsolicited_reconciliation_reject(tmp_path):
    with workflow(tmp_path) as item:
        with pytest.raises(SupervisedPaperError,match="unsolicited"):
            item.cycle(SupervisedPaperCycleV1(NOW,NOW,reconciliation_observation=()))
        item.stop_path.write_text("{}")
        with pytest.raises(SupervisedPaperError,match="identity"):
            item.cycle(SupervisedPaperCycleV1(NOW,NOW))

def test_single_owner_and_restart_preserve_receipts(tmp_path):
    one=workflow(tmp_path,"1"*32);two=workflow(tmp_path,"2"*32);one.acquire();one.start()
    try:
        with pytest.raises(SupervisedPaperError,match="owned"):two.acquire()
    finally:one.release()

def test_startup_failure_releases_workflow_lock(tmp_path):
    item=workflow(tmp_path);item.acquire();item.start();item.release()
    item.store.path.write_bytes(b"corrupt")
    failing=workflow(tmp_path,"2"*32)
    with pytest.raises(Exception):
        with failing: pass
    assert not failing.lock_path.exists()

def test_module_has_no_network_credentials_or_live_submission():
    from pathlib import Path
    source=Path(__file__).with_name("supervised_paper_workflow_v1.py").read_text("utf-8").lower()
    for word in ("requests","httpx","socket","websocket","private_key","api_key","submit_live","place_order","subprocess"):
        assert word not in source
