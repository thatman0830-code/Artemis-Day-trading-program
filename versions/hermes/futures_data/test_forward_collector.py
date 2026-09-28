from __future__ import annotations

import json
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path

import pytest
import subprocess
from hashlib import sha256

from futures_data import forward_collector as fc


def session(root="ES",day="2026-08-27",ticker="ESU6",close=datetime(2026,8,27,21,tzinfo=timezone.utc)):
    return fc.ForwardSession(root,day,ticker,root+"-contract",((close-timedelta(hours=23),close),),"schedule-source","schedule-v1")


def response(value,*,wrong=False):
    start=value.active_intervals[0][0];stamp=int(start.timestamp()*1_000_000_000)
    return json.dumps({"results":[{"ticker":"NQU6" if wrong else value.ticker,"session_end_date":value.session_date,"window_start":stamp,
        "open":"1","high":"2","low":"1","close":"2","volume":"3"}]}).encode()


def test_delayed_eligibility_is_close_plus_eight_hours_and_buffer():
    value=session();assert value.eligible_at()==datetime(2026,8,28,6,tzinfo=timezone.utc)
    assert value.eligible_at(safety_buffer=timedelta(minutes=30))==datetime(2026,8,28,5,30,tzinfo=timezone.utc)


def test_holiday_early_close_and_dst_use_explicit_utc_events():
    early=session(close=datetime(2026,11,27,18,tzinfo=timezone.utc));assert early.eligible_at()==datetime(2026,11,28,3,tzinfo=timezone.utc)
    dst=session(day="2026-03-09",close=datetime(2026,3,9,21,tzinfo=timezone.utc));assert dst.eligible_at()==datetime(2026,3,10,6,tzinfo=timezone.utc)


def test_downtime_catchup_raw_first_checkpoint_and_no_duplicate(tmp_path):
    values=(session(),session("NQ","2026-08-27","NQU6"));calls=[]
    def transport(value,key):calls.append(value.root);return 200,response(value),"safe-id"
    clock=lambda:datetime(2026,8,29,tzinfo=timezone.utc)
    result=fc.DelayedDailyCollector(tmp_path,values,transport,sleep=lambda _:None,clock=clock).run("synthetic")
    assert calls==["ES","NQ"] and result["network_calls"]==2 and result["automatic_retry"] is False
    assert (tmp_path/"data/futures_forward/ES/raw/2026-08-27-ESU6.json").exists()
    assert (tmp_path/"data/futures_forward/NQ/checkpoints/2026-08-27-NQU6.json").exists()
    calls.clear();again=fc.DelayedDailyCollector(tmp_path,values,transport,sleep=lambda _:None,clock=lambda:datetime(2026,8,30,tzinfo=timezone.utc)).run("synthetic")
    assert calls==[] and again["network_calls"]==0


def test_raw_is_retained_before_schema_or_wrong_contract_failure(tmp_path):
    value=session();collector=fc.DelayedDailyCollector(tmp_path,(value,),lambda *_:(200,response(value,wrong=True),None),clock=lambda:datetime(2026,8,29,tzinfo=timezone.utc))
    with pytest.raises(Exception,match="wrong-contract"):collector.run("synthetic")
    assert (tmp_path/"data/futures_forward/ES/raw/2026-08-27-ESU6.json").exists()
    assert not (tmp_path/"data/futures_forward/ES/manifests/2026-08-27-ESU6.json").exists()


def test_overlap_lock_stop_and_caps_fail_closed(tmp_path,monkeypatch):
    store=fc.ForwardStore(tmp_path,"one");store.acquire()
    with pytest.raises(fc.ForwardCollectorError,match="overlap"):fc.ForwardStore(tmp_path,"two").acquire()
    store.release();value=session();monkeypatch.setattr(fc,"RUN_RAW_CAP",1)
    with pytest.raises(fc.ForwardCollectorError,match="cap"):fc.DelayedDailyCollector(tmp_path,(value,),lambda *_:(200,response(value),None),clock=lambda:datetime(2026,8,29,tzinfo=timezone.utc)).run("x")


def test_rollover_requires_two_finalized_sessions_and_next_session():
    facts=tuple(fc.RolloverVolumeFact("ES","pair",f"2026-09-{day:02d}","ESU6","ESZ6",Decimal(out),Decimal(inc),datetime(2026,9,day,22,tzinfo=timezone.utc))
        for day,out,inc in ((1,10,9),(2,10,11),(3,10,12)))
    decision=fc.rollover_decision(facts,lambda _day:"2026-09-04")
    assert decision["decision_session"]=="2026-09-03" and decision["effective_session"]=="2026-09-04" and decision["no_lookahead"]


def test_collector_keeps_rollover_legs_separate_and_freezes_decision(tmp_path):
    close1=datetime(2026,9,1,21,tzinfo=timezone.utc);close2=datetime(2026,9,2,21,tzinfo=timezone.utc);close3=datetime(2026,9,3,21,tzinfo=timezone.utc)
    values=(
        fc.ForwardSession("ES","2026-09-01","ESU6","out",((close1-timedelta(hours=23),close1),),"s","v","pair","OUTGOING"),
        fc.ForwardSession("ES","2026-09-01","ESZ6","in",((close1-timedelta(hours=23),close1),),"s","v","pair","INCOMING"),
        fc.ForwardSession("ES","2026-09-02","ESU6","out",((close2-timedelta(hours=23),close2),),"s","v","pair","OUTGOING"),
        fc.ForwardSession("ES","2026-09-02","ESZ6","in",((close2-timedelta(hours=23),close2),),"s","v","pair","INCOMING"),
        fc.ForwardSession("ES","2026-09-03","ESZ6","in",((close3-timedelta(hours=23),close3),),"s","v"))
    def transport(value,_key):
        raw=json.loads(response(value));raw["results"][0]["volume"]="20" if value.rollover_leg=="INCOMING" else "10"
        return 200,json.dumps(raw).encode(),None
    fc.DelayedDailyCollector(tmp_path,values,transport,sleep=lambda _:None,clock=lambda:datetime(2026,9,5,tzinfo=timezone.utc)).run("x")
    decisions=list((tmp_path/"data/futures_forward/ES/rollovers").glob("*.json"));assert len(decisions)==1
    value=json.loads(decisions[0].read_text());assert value["effective_session"]=="2026-09-03" and value["incoming_ticker"]=="ESZ6"


def test_no_forming_session_is_requested(tmp_path):
    value=session();calls=[]
    result=fc.DelayedDailyCollector(tmp_path,(value,),lambda *_:calls.append(1),clock=lambda:datetime(2026,8,27,22,tzinfo=timezone.utc)).run("x")
    assert calls==[] and result["network_calls"]==0


def test_scripts_are_owner_dpapi_redacted_nonoverlap_and_preserve_data():
    root=Path(__file__).resolve().parents[1];scripts=root/"scripts"
    enrollment=(scripts/"enroll_massive_es_nq_forward_credential.ps1").read_text();runner=(scripts/"run_es_nq_delayed_forward_collector.ps1").read_text()
    install=(scripts/"install_es_nq_delayed_forward_task.ps1").read_text();uninstall=(scripts/"uninstall_es_nq_delayed_forward_task.ps1").read_text()
    assert "Read-Host" in enrollment and "-AsSecureString" in enrollment and "ConvertFrom-SecureString" in enrollment
    assert "ConvertTo-SecureString" in runner and "Get-Content $credential" in runner and "--api-key" not in runner.lower()
    assert "RedirectStandardInput=$true" in runner and "StandardInput.WriteLine($plain)" in runner and "2>$null" not in runner
    assert "MultipleInstances IgnoreNew" in install and "RunLevel Limited" in install and "RestartCount 0" in install
    assert "Remove-Item" not in uninstall and "DATA_AND_AUDIT_EVIDENCE_PRESERVED" in uninstall


def test_no_trading_btc_or_backtest_control_capability():
    source=Path(fc.__file__).read_text().lower()
    for prohibited in ("place_order","private_key","wallet","signing","start_recorder","pass_b_backfill --execute"):
        assert prohibited not in source
    assert "btc_forward_archive_2" in source # explicit rejection boundary only


def test_configuration_helper_runs_from_outside_repository(tmp_path):
    root=Path(__file__).resolve().parents[1]
    configuration=tmp_path/"verified sessions.json"
    material={
        "schema_version":"es-nq-verified-forward-sessions-v1","finalized":True,
        "source_id":"fixture-source","schedule_version":"fixture-v1",
        "verified_coverage":{"start_inclusive":"2026-08-26","end_exclusive":"2026-08-27","last_session":"2026-08-26"},
        "evidence":[],"history":[],"pending_session_count":1,
        "sessions":[{"root":"ES","session_date":"2026-08-27","ticker":"ESU6","contract_id":"es-u6",
            "active_intervals":[{"start_utc":"2026-08-26T22:00:00Z","end_exclusive_utc":"2026-08-27T21:00:00Z"}]}]
    }
    canonical=(json.dumps(material,sort_keys=True,indent=2)+"\n").encode();payload={**material,"configuration_id":sha256(canonical).hexdigest()}
    data=(json.dumps(payload,sort_keys=True,indent=2)+"\n").encode();configuration.write_bytes(data)
    configuration.with_name("es_nq_forward_sessions.manifest.json").write_text(json.dumps({
        "configuration_id":payload["configuration_id"],"configuration_sha256":sha256(data).hexdigest()}),encoding="utf-8")
    powershell=Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    result=subprocess.run([str(powershell),"-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",
        str(root/"scripts/validate_es_nq_forward_configuration.ps1"),"-ConfigurationPath",str(configuration)],
        cwd=Path.home(),text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=="FORWARD_CONFIGURATION_VALIDATED_OFFLINE"
    assert "traceback" not in (result.stdout+result.stderr).lower()


def test_configuration_helper_missing_manifest_is_one_sanitized_line():
    root=Path(__file__).resolve().parents[1]
    powershell=Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    missing=Path.home()/"definitely-absent-forward-configuration.json"
    result=subprocess.run([str(powershell),"-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",
        str(root/"scripts/validate_es_nq_forward_configuration.ps1"),"-ConfigurationPath",str(missing)],
        cwd=Path.home(),text=True,capture_output=True,timeout=30)
    assert result.returncode==2
    assert result.stdout==""
    assert result.stderr.strip()=="BLOCKED: Finalized forward-session configuration is unavailable."
