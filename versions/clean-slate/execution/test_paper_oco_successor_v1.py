from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
import json

import pytest

from backtesting.execution_accounting_v2.contracts import OrderState
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.paper_oco_handoff_v1 import PaperOCOHandoffStoreV1
from execution.paper_oco_successor_v1 import PaperOCOSuccessorV1
from execution.supervised_paper_launch_evidence_v1 import OwnerSupervisionConfirmationV1
from execution.supervised_paper_launch_gate_v1 import SupervisedPaperLaunchPolicyV1
from execution.test_supervised_paper_launch_evidence_v1 import document
from execution.test_paper_oco_handoff_v1 import setup
from execution.test_paper_oco_execution_v1 import H


def ready(tmp_path):
    handoff,args=setup(tmp_path)
    prepared=handoff.prepare(**args)
    now=args["reviewed_at"]
    value=document();value.update(collected_at=now.isoformat(),btc_heartbeat_at=now.isoformat())
    value.pop("evidence_id");value["evidence_id"]=hashlib.sha256(json.dumps(value,
        sort_keys=True,separators=(",",":")).encode()).hexdigest()
    evidence_path=tmp_path/"launch-evidence.json";evidence_path.write_text(json.dumps(value))
    confirmation=OwnerSupervisionConfirmationV1.create(confirmed_at=now,
        expires_at=now+timedelta(minutes=5),repository_checkpoint="a"*64,
        owner_supervision_confirmed=True,stop_control_verified=True,maximum_session_seconds=1800,
        maximum_commands=10,maximum_order_notional=Decimal(500),maximum_gross_exposure=Decimal(800))
    policy=SupervisedPaperLaunchPolicyV1("a"*64,timedelta(minutes=5),timedelta(minutes=5),
        timedelta(minutes=30),10,Decimal(500),Decimal(800))
    auth=dict(evidence_path=evidence_path,confirmation=confirmation,policy=policy,activated_at=now)
    return PaperOCOSuccessorV1(handoff),prepared,auth,now


def test_single_successor_is_durable_active_paper_protection(tmp_path):
    binding,prepared,auth,now=ready(tmp_path)
    doc,runner=binding.create(expected_handoff_id=prepared["handoff_id"],**auth)
    assert doc["state"]=="COMMITTED" and doc["paper_only"] is True
    assert doc["live_trading_permitted"] is False and doc["trading_authority"] is False
    _,coordinator=runner.load()
    assert coordinator.state=="ARMED" and len(coordinator.ledger.orders)==2
    assert all(order.state is OrderState.ACTIVE for order in coordinator.ledger.orders)
    assert all(item.source_lineage is not None for item in coordinator.instructions)
    assert binding.load()[0]==doc


def test_successor_evaluates_exact_next_bar_after_reopen(tmp_path):
    binding,prepared,auth,now=ready(tmp_path)
    _,runner=binding.create(expected_handoff_id=prepared["handoff_id"],**auth)
    _,coordinator=runner.load()
    source=coordinator.instructions[0].source_lineage.source_bar
    following=replace(source,bar_id=H("successor-next-bar"),open_time=now,
        close_time=now+timedelta(minutes=1),available_at=now+timedelta(minutes=1))
    doc,_=runner.load()
    updated=runner.advance(kind="EVALUATE",payload=dict(bar=following,
        evaluated_at=following.available_at,accounting=coordinator.accounting),
        expected_checkpoint_id=doc["checkpoint_id"])
    assert updated["body"]["state"]=="ARMED"


def test_exact_retry_returns_same_generation_and_conflict_rejects(tmp_path):
    binding,prepared,auth,now=ready(tmp_path)
    first,runner=binding.create(expected_handoff_id=prepared["handoff_id"],**auth)
    second,reloaded=binding.create(expected_handoff_id=prepared["handoff_id"],**auth)
    assert second==first and reloaded.journal.initial_id==runner.journal.initial_id
    changed={**auth,"policy":replace(auth["policy"],permit_lifetime=timedelta(minutes=4))}
    with pytest.raises(PaperOCOError,match="conflicting"):
        binding.create(expected_handoff_id=prepared["handoff_id"],**changed)


@pytest.mark.parametrize("fault",["stale","unhealthy","expired","future","confirmation_identity","checkpoint"])
def test_invalid_authority_or_identity_rejects_before_successor(tmp_path,fault):
    binding,prepared,auth,now=ready(tmp_path)
    expected=prepared["handoff_id"]
    if fault=="stale": expected="0"*64
    elif fault=="unhealthy":
        value=json.loads(auth["evidence_path"].read_text());value["watchdog_state"]="UNHEALTHY"
        value.pop("evidence_id");value["evidence_id"]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest();auth["evidence_path"].write_text(json.dumps(value))
    elif fault=="expired": auth["activated_at"]+=timedelta(minutes=5)
    elif fault=="future":
        value=json.loads(auth["evidence_path"].read_text());value["collected_at"]=(now+timedelta(seconds=1)).isoformat()
        value.pop("evidence_id");value["evidence_id"]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest();auth["evidence_path"].write_text(json.dumps(value))
    elif fault=="confirmation_identity": auth["confirmation"]=replace(auth["confirmation"],confirmation_id=H("tampered"))
    else: auth["policy"]=replace(auth["policy"],expected_checkpoint="c"*64)
    with pytest.raises(PaperOCOError):
        binding.create(expected_handoff_id=expected,**auth)
    assert not binding.path.exists()


@pytest.mark.parametrize("limit",["order","gross"])
def test_risk_limit_rejects_before_successor(tmp_path,limit):
    binding,prepared,auth,now=ready(tmp_path)
    changes={"maximum_order_notional":Decimal(1)} if limit=="order" else {"maximum_gross_exposure":Decimal(1)}
    auth["confirmation"]=OwnerSupervisionConfirmationV1.create(confirmed_at=now,
        expires_at=now+timedelta(minutes=5),repository_checkpoint="a"*64,
        owner_supervision_confirmed=True,stop_control_verified=True,maximum_session_seconds=1800,
        maximum_commands=10,maximum_order_notional=changes.get("maximum_order_notional",Decimal(500)),
        maximum_gross_exposure=changes.get("maximum_gross_exposure",Decimal(800)))
    auth["policy"]=replace(auth["policy"],**changes)
    with pytest.raises(PaperOCOError,match="risk limits"):
        binding.create(expected_handoff_id=prepared["handoff_id"],**auth)
    assert not binding.path.exists()


def test_crash_after_inflight_marker_blocks_automatic_retry(tmp_path,monkeypatch):
    binding,prepared,auth,now=ready(tmp_path)
    import execution.paper_oco_successor_v1 as module
    monkeypatch.setattr(module,"create_persisted_protective_session",
        lambda *args,**kwargs: (_ for _ in ()).throw(OSError("disk stopped")))
    with pytest.raises(OSError,match="disk stopped"):
        binding.create(expected_handoff_id=prepared["handoff_id"],**auth)
    assert binding._read()["state"]=="IN_FLIGHT"
    with pytest.raises(PaperOCOError,match="incomplete"):
        binding.create(expected_handoff_id=prepared["handoff_id"],**auth)


def test_tampered_binding_and_successor_both_fail_closed(tmp_path):
    binding,prepared,auth,now=ready(tmp_path)
    binding.create(expected_handoff_id=prepared["handoff_id"],**auth)
    raw=binding.path.read_bytes()
    binding.path.write_bytes(raw.replace(b'"trading_authority":false',b'"trading_authority":true '))
    with pytest.raises(PaperOCOError): binding.load()
    binding.path.write_bytes(raw)
    successor=binding._successor(prepared["handoff_id"])/"oco-initial.json"
    successor.write_bytes(b"{")
    with pytest.raises(PaperOCOError): binding.load()
