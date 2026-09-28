from dataclasses import FrozenInstanceError,replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import hashlib,json
import pytest
from execution.supervised_paper_launch_evidence_v1 import *
from execution.supervised_paper_launch_gate_v1 import SupervisedPaperLaunchPolicyV1

NOW=datetime(2026,9,1,22,tzinfo=timezone.utc);H="a"*64
G="d671288487dbad42112aa9ea20993ca4baf9de06"
def document():
    value={"schema_version":EVIDENCE_VERSION,"collected_at":NOW.isoformat(),"repository_checkpoint":H,
        "repository_clean":True,"watchdog_state":"HEALTHY","watchdog_report_id":H,
        "btc_task_state":"Running","btc_recorder_health":"HEALTHY","btc_heartbeat_at":NOW.isoformat(),
        "btc_unresolved_gap_count":0,"es_nq_task_state":"Ready","es_nq_last_result":0,"es_nq_missed_runs":0,
        "recovery_drill_result":"RECOVERY_VERIFIED","recovery_drill_report_id":H,
        "stale_alert_drill_result":"STALE_ALERT_AND_RECOVERY_VERIFIED","stale_alert_drill_report_id":H,
        "unhealthy_alert_delivered":True,"healthy_alert_delivered":True,"clock_skew_seconds":0,
        "source_file_sha256":["b"*64],"trading_authority":False}
    value["evidence_id"]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest();return value
def evidence(tmp_path,change=None):
    value=document();
    if change:value.update(change);body={k:v for k,v in value.items() if k!="evidence_id"};value["evidence_id"]=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    path=tmp_path/"evidence.json";path.write_text(json.dumps(value));return read_launch_evidence(path)
def policy():return SupervisedPaperLaunchPolicyV1(H,timedelta(seconds=120),timedelta(minutes=5),timedelta(minutes=30),10,Decimal("500"),Decimal("800"))
def confirmation():return OwnerSupervisionConfirmationV1.create(confirmed_at=NOW,expires_at=NOW+timedelta(minutes=5),repository_checkpoint=H,owner_supervision_confirmed=True,stop_control_verified=True,maximum_session_seconds=1800,maximum_commands=10,maximum_order_notional=Decimal("500"),maximum_gross_exposure=Decimal("800"))

def test_canonical_evidence_and_current_confirmation_produce_eligible_decision(tmp_path):
    result=evaluate_collected_launch_evidence(evidence=evidence(tmp_path),confirmation=confirmation(),policy=policy(),as_of=NOW)
    assert result.eligible and result.permitted_markets==("BTC",) and not result.trading_authority

def test_evidence_is_strict_content_addressed_and_immutable(tmp_path):
    item=evidence(tmp_path);assert len(item.evidence_id)==64 and item.source_file_sha256==("b"*64,)
    with pytest.raises(FrozenInstanceError):item.repository_clean=False
    value=document();value["evidence_id"]="c"*64;(tmp_path/"bad.json").write_text(json.dumps(value))
    with pytest.raises(ValueError,match="identity"):read_launch_evidence(tmp_path/"bad.json")

@pytest.mark.parametrize("change",[{"extra":1},{"trading_authority":True},{"source_file_sha256":[]},
    {"repository_checkpoint":"bad"},{"btc_unresolved_gap_count":-1},{"repository_clean":1}])
def test_malformed_or_authority_evidence_rejects(tmp_path,change):
    value=document();value.update(change);body={k:v for k,v in value.items() if k!="evidence_id"};value["evidence_id"]=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest();(tmp_path/"bad.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):read_launch_evidence(tmp_path/"bad.json")

def test_confirmation_is_short_lived_checkpoint_and_limit_bound(tmp_path):
    with pytest.raises(ValueError,match="current"):evaluate_collected_launch_evidence(evidence=evidence(tmp_path),confirmation=confirmation(),policy=policy(),as_of=NOW+timedelta(minutes=5))
    with pytest.raises(ValueError,match="checkpoint"):evaluate_collected_launch_evidence(evidence=evidence(tmp_path),confirmation=replace(confirmation(),repository_checkpoint="c"*64),policy=policy(),as_of=NOW)
    with pytest.raises(ValueError,match="limits"):evaluate_collected_launch_evidence(evidence=evidence(tmp_path),confirmation=replace(confirmation(),maximum_commands=9),policy=policy(),as_of=NOW)
    with pytest.raises(ValueError,match="five minutes"):OwnerSupervisionConfirmationV1.create(confirmed_at=NOW,expires_at=NOW+timedelta(minutes=6),repository_checkpoint=H,owner_supervision_confirmed=True,stop_control_verified=True,maximum_session_seconds=1800,maximum_commands=10,maximum_order_notional=Decimal("500"),maximum_gross_exposure=Decimal("800"))

def test_missing_owner_assertions_block_through_gate(tmp_path):
    confirm=OwnerSupervisionConfirmationV1.create(confirmed_at=NOW,expires_at=NOW+timedelta(minutes=5),repository_checkpoint=H,owner_supervision_confirmed=False,stop_control_verified=False,maximum_session_seconds=1800,maximum_commands=10,maximum_order_notional=Decimal("500"),maximum_gross_exposure=Decimal("800"))
    result=evaluate_collected_launch_evidence(evidence=evidence(tmp_path),confirmation=confirm,policy=policy(),as_of=NOW)
    assert not result.eligible and len(result.reasons)==2

def test_module_has_no_environment_or_submission_surface():
    from pathlib import Path
    source=Path(__file__).with_name("supervised_paper_launch_evidence_v1.py").read_text("utf-8").lower()
    for value in ("subprocess","socket","requests","httpx","scheduledtask","get-ciminstance","private_key","api_key","place_order","submit_live"):
        assert value not in source

def test_direct_construction_cannot_grant_trading_authority(tmp_path):
    confirm=confirmation();values={field:getattr(confirm,field) for field in confirm.__dataclass_fields__};values["trading_authority"]=True
    with pytest.raises(ValueError,match="cannot grant trading authority"):OwnerSupervisionConfirmationV1(**values)
    item=evidence(tmp_path);values={field:getattr(item,field) for field in item.__dataclass_fields__};values["trading_authority"]=True
    with pytest.raises(ValueError,match="cannot grant trading authority"):SupervisedPaperLaunchEvidenceV1(**values)

def test_standard_sha1_git_checkpoint_is_accepted(tmp_path):
    item=evidence(tmp_path,{"repository_checkpoint":G})
    assert item.repository_checkpoint==G
