from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from execution.supervised_paper_launch_evidence_collector_v1 import collect_launch_evidence, write_launch_evidence
from execution.supervised_paper_launch_evidence_v1 import read_launch_evidence

NOW=datetime(2026,9,1,23,tzinfo=timezone.utc);H="a"*64
G="d671288487dbad42112aa9ea20993ca4baf9de06"


def _files(tmp_path:Path):
    docs={
        "watchdog.json":{"adapter_version":"OWNER_CONTEXT_HEALTH_ADAPTER_V1","report_id":H,
            "readiness":{"state":"HEALTHY"},"observations":[
                {"component":"btc-recorder","task_running":True,"latest_heartbeat_at":NOW.isoformat(),"unresolved_gap_count":0,"clock_skew_seconds":1,"trading_authority":False},
                {"component":"es-nq-recorder","task_running":True,"latest_heartbeat_at":NOW.isoformat(),"unresolved_gap_count":0,"clock_skew_seconds":1,"trading_authority":False}],"trading_authority":False},
        "recovery.json":{"schema_version":"controlled-btc-recorder-recovery-drill-v1","result":"RECOVERY_VERIFIED","report_id":"b"*64,"trading_authority":False},
        "stale.json":{"schema_version":"controlled-stale-alert-drill-v1","result":"STALE_ALERT_AND_RECOVERY_VERIFIED","report_id":"c"*64,
            "stale_observed":True,"unhealthy_alert_delivered":True,"recovery_observed":True,"healthy_alert_delivered":True,"trading_authority":False}}
    paths={}
    for name,value in docs.items():
        paths[name]=tmp_path/name;paths[name].write_text(json.dumps(value),encoding="utf-8")
    return paths,docs


def _collect(tmp_path,**changes):
    paths,_=_files(tmp_path);args={"watchdog_path":paths["watchdog.json"],"recovery_drill_path":paths["recovery.json"],
        "stale_drill_path":paths["stale.json"],"repository_checkpoint":H,"repository_clean":True,
        "btc_task_state":"Running","es_nq_task_state":"Ready","es_nq_last_result":0,"es_nq_missed_runs":0,"collected_at":NOW}
    args.update(changes);return collect_launch_evidence(**args)


def test_collects_content_addressed_read_only_evidence(tmp_path):
    value=_collect(tmp_path);assert value["trading_authority"] is False and value["repository_clean"] is True
    assert value["btc_task_state"]=="Running" and value["es_nq_task_state"]=="Ready"
    assert len(value["source_file_sha256"])==3 and value["source_file_sha256"]==sorted(value["source_file_sha256"])
    output=tmp_path/"out"/"evidence.json";write_launch_evidence(output,value)
    assert read_launch_evidence(output).evidence_id==value["evidence_id"]


@pytest.mark.parametrize("change,match",[
    ({"repository_clean":False},"clean"),({"repository_checkpoint":"bad"},"SHA-256"),
    ({"es_nq_missed_runs":-1},"nonnegative"),({"es_nq_last_result":True},"integer")])
def test_repository_and_task_facts_fail_closed(tmp_path,change,match):
    with pytest.raises(ValueError,match=match):_collect(tmp_path,**change)


@pytest.mark.parametrize("file_name,key,value,match",[
    ("watchdog.json","trading_authority",True,"authority"),
    ("watchdog.json","adapter_version","wrong","version"),
    ("recovery.json","result","FAILED","recovery"),
    ("stale.json","result","FAILED","stale"),
    ("stale.json","healthy_alert_delivered",False,"healthy_alert_delivered")])
def test_tampered_sources_fail_closed(tmp_path,file_name,key,value,match):
    paths,docs=_files(tmp_path);docs[file_name][key]=value;paths[file_name].write_text(json.dumps(docs[file_name]))
    with pytest.raises(ValueError,match=match):collect_launch_evidence(watchdog_path=paths["watchdog.json"],recovery_drill_path=paths["recovery.json"],stale_drill_path=paths["stale.json"],repository_checkpoint=H,repository_clean=True,btc_task_state="Running",es_nq_task_state="Ready",es_nq_last_result=0,es_nq_missed_runs=0,collected_at=NOW)


def test_windows_wrapper_is_read_only_and_has_no_submission_surface():
    source=Path(__file__).parents[1].joinpath("scripts","collect_supervised_paper_launch_evidence.ps1").read_text("utf-8").lower()
    assert "get-scheduledtask" in source and source.count("safe.directory=")==2
    for forbidden in ("start-scheduledtask","enable-scheduledtask","set-scheduledtask","register-scheduledtask","place_order","submit_order","api_key","private_key"):
        assert forbidden not in source

def test_sha1_git_checkpoint_is_preserved(tmp_path):
    value=_collect(tmp_path,repository_checkpoint=G)
    assert value["repository_checkpoint"]==G
