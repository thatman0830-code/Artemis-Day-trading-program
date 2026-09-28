from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import pytest

from execution.supervised_paper_launch_decision_v1 import *
from execution.supervised_paper_launch_evidence_v1 import EVIDENCE_VERSION

NOW=datetime(2026,9,1,23,tzinfo=timezone.utc);G="d"*40;H="a"*64


def evidence(tmp_path):
    body={"schema_version":EVIDENCE_VERSION,"collected_at":NOW.isoformat(),"repository_checkpoint":G,
        "repository_clean":True,"watchdog_state":"HEALTHY","watchdog_report_id":H,
        "btc_task_state":"Running","btc_recorder_health":"HEALTHY","btc_heartbeat_at":NOW.isoformat(),
        "btc_unresolved_gap_count":0,"es_nq_task_state":"Ready","es_nq_last_result":0,"es_nq_missed_runs":0,
        "recovery_drill_result":"RECOVERY_VERIFIED","recovery_drill_report_id":H,
        "stale_alert_drill_result":"STALE_ALERT_AND_RECOVERY_VERIFIED","stale_alert_drill_report_id":H,
        "unhealthy_alert_delivered":True,"healthy_alert_delivered":True,"clock_skew_seconds":0,
        "source_file_sha256":["b"*64],"trading_authority":False}
    value={**body,"evidence_id":hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
    path=tmp_path/"evidence.json";path.write_text(json.dumps(value));return path


def test_explicit_acknowledgements_create_bounded_advisory_decision(tmp_path):
    value=create_launch_decision(evidence_path=evidence(tmp_path),as_of=NOW,
        owner_supervision_confirmed=True,stop_control_verified=True)
    assert value["eligible"] and value["permitted_markets"]==["BTC-PERP"]
    assert value["maximum_session_seconds"]==300 and value["maximum_commands"]==5
    assert value["maximum_order_notional"]=="100" and value["maximum_gross_exposure"]=="100"
    assert value["advisory_only"] is True and value["live_trading_permitted"] is False and value["trading_authority"] is False


@pytest.mark.parametrize("supervision,stop",[(False,True),(True,False),(False,False)])
def test_missing_owner_acknowledgement_rejects(tmp_path,supervision,stop):
    with pytest.raises(ValueError,match="explicit owner"):
        create_launch_decision(evidence_path=evidence(tmp_path),as_of=NOW,
            owner_supervision_confirmed=supervision,stop_control_verified=stop)


def test_stale_evidence_produces_ineligible_decision(tmp_path):
    value=create_launch_decision(evidence_path=evidence(tmp_path),as_of=NOW.replace(minute=6),
        owner_supervision_confirmed=True,stop_control_verified=True)
    assert not value["eligible"] and value["reasons"]==["BTC_RECORDER_NOT_HEALTHY","STALE_EVIDENCE"]


def test_output_is_atomic_and_content_addressed(tmp_path):
    value=create_launch_decision(evidence_path=evidence(tmp_path),as_of=NOW,
        owner_supervision_confirmed=True,stop_control_verified=True)
    output=tmp_path/"out"/"decision.json";write_launch_decision(output,value)
    loaded=json.loads(output.read_text());identity=loaded.pop("decision_envelope_id")
    assert identity==hashlib.sha256(json.dumps(loaded,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    assert not list(output.parent.glob("*.tmp-*"))


def test_module_has_no_session_start_or_submission_surface():
    source=Path(__file__).with_name("supervised_paper_launch_decision_v1.py").read_text("utf-8").lower()
    for forbidden in ("start-scheduledtask","place_order","submit_order","paperexchangeadapter","supervisedpaperworkflow","requests","socket","api_key","private_key"):
        assert forbidden not in source
