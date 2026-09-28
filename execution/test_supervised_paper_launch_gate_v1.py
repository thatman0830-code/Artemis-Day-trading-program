from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from execution.supervised_paper_launch_gate_v1 import *

NOW=datetime(2026,9,1,22,tzinfo=timezone.utc); H="a"*64
def policy(): return SupervisedPaperLaunchPolicyV1(H,timedelta(seconds=120),timedelta(minutes=5),
    timedelta(minutes=30),10,Decimal("500"),Decimal("800"))
def facts(): return SupervisedPaperLaunchFactsV1(NOW,H,True,"HEALTHY",H,"Running","HEALTHY",
    NOW-timedelta(seconds=10),0,"Ready",0,0,"RECOVERY_VERIFIED",H,
    "STALE_ALERT_AND_RECOVERY_VERIFIED",H,True,True,0,True,True)

def test_complete_fresh_evidence_produces_short_advisory_btc_only_permit():
    result=evaluate_supervised_paper_launch(facts=facts(),policy=policy(),as_of=NOW)
    assert result.eligible and not result.reasons and result.permitted_markets==("BTC",)
    assert result.expires_at==NOW+timedelta(minutes=5) and result.advisory_only
    assert not result.live_trading_permitted and not result.trading_authority
    with pytest.raises(FrozenInstanceError): result.eligible=False

@pytest.mark.parametrize(("change","reason"),[
    ({"repository_clean":False},PaperLaunchReason.REPOSITORY_NOT_CLEAN),
    ({"repository_checkpoint":"b"*64},PaperLaunchReason.CHECKPOINT_MISMATCH),
    ({"observed_at":NOW-timedelta(seconds=121)},PaperLaunchReason.STALE_EVIDENCE),
    ({"watchdog_state":"UNHEALTHY"},PaperLaunchReason.WATCHDOG_NOT_HEALTHY),
    ({"btc_task_state":"Ready"},PaperLaunchReason.BTC_RECORDER_NOT_HEALTHY),
    ({"btc_heartbeat_at":NOW-timedelta(seconds=91)},PaperLaunchReason.BTC_RECORDER_NOT_HEALTHY),
    ({"btc_unresolved_gap_count":1},PaperLaunchReason.BTC_DATA_GAP),
    ({"es_nq_last_result":1},PaperLaunchReason.ES_NQ_NOT_HEALTHY),
    ({"recovery_drill_result":"FAILED"},PaperLaunchReason.RECOVERY_DRILL_UNVERIFIED),
    ({"unhealthy_alert_delivered":False},PaperLaunchReason.STALE_ALERT_DRILL_UNVERIFIED),
    ({"clock_skew_seconds":3},PaperLaunchReason.CLOCK_SKEW),
    ({"owner_supervision_confirmed":False},PaperLaunchReason.OWNER_SUPERVISION_MISSING),
    ({"stop_control_verified":False},PaperLaunchReason.STOP_CONTROL_UNVERIFIED),
])
def test_every_missing_launch_fact_blocks(change,reason):
    result=evaluate_supervised_paper_launch(facts=replace(facts(),**change),policy=policy(),as_of=NOW)
    assert not result.eligible and reason in result.reasons and result.expires_at is None
    assert not result.permitted_markets

def test_multiple_failures_are_unique_sorted_and_deterministic():
    broken=replace(facts(),repository_clean=False,owner_supervision_confirmed=False,stop_control_verified=False)
    first=evaluate_supervised_paper_launch(facts=broken,policy=policy(),as_of=NOW)
    second=evaluate_supervised_paper_launch(facts=broken,policy=policy(),as_of=NOW)
    assert first==second and first.reasons==tuple(sorted(first.reasons,key=lambda x:x.value))
    assert len(first.launch_id)==64

@pytest.mark.parametrize("change",[
    {"maximum_session_duration":timedelta(minutes=31)}, {"maximum_commands":11},
    {"maximum_order_notional":Decimal("501")}, {"maximum_gross_exposure":Decimal("801")},
    {"permit_lifetime":timedelta(minutes=6)}, {"evidence_maximum_age":timedelta(minutes=6)},
    {"allowed_markets":("BTC","ES")}, {"trading_authority":True},
])
def test_hard_ceilings_cannot_be_raised(change):
    with pytest.raises(ValueError): replace(policy(),**change)

def test_future_evidence_and_authority_reject():
    with pytest.raises(ValueError,match="future"):
        evaluate_supervised_paper_launch(facts=replace(facts(),btc_heartbeat_at=NOW+timedelta(seconds=1)),policy=policy(),as_of=NOW)
    with pytest.raises(ValueError,match="authority"): replace(facts(),trading_authority=True)

def test_module_has_no_execution_provider_or_secret_surface():
    from pathlib import Path
    source=Path(__file__).with_name("supervised_paper_launch_gate_v1.py").read_text("utf-8").lower()
    for value in ("requests","httpx","socket","subprocess","scheduledtask","start-process",
                  "private_key","api_key","place_order","submit_live","paperexchangeadapter"):
        assert value not in source
