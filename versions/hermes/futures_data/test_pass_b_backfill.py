from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest

import futures_data.pass_b_backfill as pb


def calendar():
    events=[]
    for root in pb.ROOTS:
        events.extend([])
    stream=[{"session_date":"2025-06-02","event":"pre_open","timestamp":"2025-06-01T21:00:00Z","venue":"XCME","product_name":"x"},
            {"session_date":"2025-06-02","event":"open","timestamp":"2025-06-01T22:00:00Z","venue":"XCME","product_name":"x"},
            {"session_date":"2025-06-02","event":"pre_open","timestamp":"2025-06-02T17:00:00Z","venue":"XCME","product_name":"x"},
            {"session_date":"2025-06-02","event":"open","timestamp":"2025-06-02T18:00:00Z","venue":"XCME","product_name":"x"},
            {"session_date":"2025-06-02","event":"close","timestamp":"2025-06-02T21:00:00Z","venue":"XCME","product_name":"x"}]
    return pb._build_calendar({"ES":stream,"NQ":stream})


def test_calendar_models_break_special_session_and_timezone():
    value=calendar();session=value["sessions"][0]
    assert len(session["active_intervals"])==2 and session["early_or_special"] is True
    assert all("-05:00" in x["start_chicago"] for x in session["active_intervals"])
    assert value["represented_session_dates"]==1


def test_frozen_calendar_and_plan_are_complete_unique_and_bounded():
    repository_root=Path(__file__).resolve().parents[1]
    plan=json.loads((repository_root/"data/backtests"/pb.PLAN_DIR/"plan.json").read_text())
    assert plan["calendar"]["represented_session_dates"]==313
    assert plan["estimated"]["requests"]==130 and plan["estimated"]["rows"]==882180
    assert plan["estimated"]["requests"]<=pb.MAX_REQUESTS and plan["estimated"]["rows"]<=pb.MAX_ROWS
    for root in pb.ROOTS:
        requests=plan["markets"][root]["requests"]
        sessions=[x for request in requests for x in request["sessions"]]
        assert len(sessions)==313 and len(set(sessions))==313
        assert all(request["root"]==root and request["ticker"].startswith(root) for request in requests)
    assert plan["rollovers"]["markets"]["ES"]["active_windows"][-1]["end_exclusive"]=="2026-08-27"


def test_rollovers_are_sparse_explicit_no_lookahead_and_no_fallback():
    repository_root=Path(__file__).resolve().parents[1]
    value=json.loads((repository_root/"data/backtests"/pb.PLAN_DIR/"rollovers.json").read_text())
    for root in pb.ROOTS:
        decisions=value["markets"][root]["decisions"]
        assert len(decisions)==5
        assert all(x["method"]=="TWO_CONSECUTIVE_FINALIZED_VOLUME_CROSSOVER_SPARSE_ZERO" for x in decisions)
        assert all(x["no_lookahead"] and x["decision_session"]<x["effective_session"] for x in decisions)
        assert all("missing_aggregate_minutes" in fact for x in decisions for fact in x["evidence"])


def test_calendar_holidays_early_closes_and_dst_are_source_exact():
    root=Path(__file__).resolve().parents[1]
    calendar=json.loads((root/"data/backtests"/pb.PLAN_DIR/"calendar.json").read_text())
    sessions={x["session_date"]:x for x in calendar["sessions"]}
    excluded={x["date"]:x["reason"] for x in calendar["excluded_dates"]}
    assert excluded["2025-11-27"]=="PROVIDER_VERIFIED_NO_SESSION_EVENTS"
    assert excluded["2025-12-25"]=="PROVIDER_VERIFIED_NO_SESSION_EVENTS"
    assert sessions["2025-11-28"]["early_or_special"] is True
    assert sessions["2025-12-24"]["active_intervals"][-1]["end_exclusive_chicago"].endswith("12:15:00-06:00")
    assert sessions["2026-03-06"]["active_intervals"][0]["start_utc"].endswith("23:00:00Z")
    assert sessions["2026-03-09"]["active_intervals"][0]["start_utc"].endswith("22:00:00Z")


def sample_request():
    return {"id":"request","root":"ES","contract_id":"contract","ticker":"ESM6","sessions":["2025-06-02"],
            "start_utc":"2025-06-01T22:00:00Z","end_utc":"2025-06-02T21:00:00Z","maximum_rows":1380,"plan_id":"plan"}


def ordinary_calendar():
    return {"sessions":[{"session_date":"2025-06-02","active_intervals":[{"start_utc":"2025-06-01T22:00:00Z","end_exclusive_utc":"2025-06-02T21:00:00Z"}]}]}


def raw_row(ticker="ESM6",stamp="2025-06-01T22:00:00+00:00"):
    ns=int(datetime.fromisoformat(stamp).timestamp()*1_000_000_000)
    return {"ticker":ticker,"session_end_date":"2025-06-02","window_start":ns,"open":"1","high":"2","low":"1","close":"2","volume":"3"}


def test_normalization_preserves_exact_contract_and_never_synthesizes():
    request=sample_request();data,rows,reconciliation=pb._normalize(json.dumps({"results":[raw_row()]}).encode(),request,ordinary_calendar())
    record=json.loads(data);assert rows==1 and record["contract_id"]=="contract" and record["ticker"]=="ESM6"
    assert reconciliation["excluded_provider_duplicates"]==0
    assert len(data.splitlines())==1
    with pytest.raises(pb.PassBError,match="wrong-contract"):
        pb._normalize(json.dumps({"results":[raw_row("NQM6")]}).encode(),request,ordinary_calendar())
    with pytest.raises(pb.PassBError,match="pagination"):
        pb._normalize(json.dumps({"results":[],"next_url":"x"}).encode(),request,ordinary_calendar())


def test_raw_first_checkpoint_resume_checksum_and_path_isolation(tmp_path):
    plan={"id":"plan"};store=pb.PassBStore(tmp_path,plan);request=sample_request();raw=b'{"results":[]}'
    store.retain("ES",request,raw,200,"safe-id")
    assert store.retained("ES",request)[0]==raw
    store.commit("ES",request,b"",0);assert store.complete("ES",request)
    assert (store.stage/"ES/raw/request.json").exists() and not (store.stage/"NQ/raw/request.json").exists()
    with pytest.raises(pb.PassBError,match="existing"):
        store.retain("ES",{**request,"id":"other"},raw,200,None) if False else pb._atomic_new(store.stage/"ES/raw/request.json",raw)
    (store.stage/"ES/raw/request.json").write_bytes(b"corrupt")
    with pytest.raises(pb.PassBError,match="checksum"):
        store.complete("ES",request)


def test_wrong_plan_id_and_stop_fail_closed(tmp_path):
    request=sample_request();store=pb.PassBStore(tmp_path,{"id":"plan"});store.retain("ES",request,b"{}",200,None)
    pending=store.stage/"ES/pending/request.json";value=json.loads(pending.read_text());value["plan_id"]="wrong";pending.write_text(json.dumps(value))
    with pytest.raises(pb.PassBError,match="raw-first conflict"):store.retained("ES",request)
    stopped=pb.PassBStore(tmp_path/"stopped",{"id":"plan"});stopped.stop.parent.mkdir(parents=True);stopped.stop.write_text("stop")
    with pytest.raises(pb.PassBError,match="stop"):stopped.retain("ES",request,b"{}",200,None)


@pytest.mark.parametrize("field,limit",[("MAX_RAW_BYTES",1),("MAX_ROWS",0),("MAX_NORMALIZED_BYTES",0),("MAX_COMBINED_BYTES",1)])
def test_every_cumulative_cap_fails_closed(tmp_path,monkeypatch,field,limit):
    monkeypatch.setattr(pb,field,limit);store=pb.PassBStore(tmp_path,{"id":"plan"});request=sample_request()
    if field in ("MAX_RAW_BYTES", "MAX_COMBINED_BYTES"):
        with pytest.raises(pb.PassBError,match="cap"):store.retain("ES",request,b"{}",200,None)
    else:
        store.retain("ES",request,b"{}",200,None)
        with pytest.raises(pb.PassBError,match="cap"):store.commit("ES",request,b"x",1)


def test_request_cap_and_recorder_prohibition():
    repository_root=Path(__file__).resolve().parents[1]
    source=(repository_root/"futures_data/pass_b_backfill.py").read_text().lower()
    assert "start_recorder" not in source and "continuous" not in source
    assert pb.MAX_REQUESTS==130 and pb.MIN_CALL_INTERVAL_SECONDS==15


def test_executor_resumes_retained_raw_without_redownload_and_never_retries(tmp_path):
    cal=ordinary_calendar();requests={}
    for root,ticker in (("ES","ESM6"),("NQ","NQM6")):
        requests[root]={"requests":[{**sample_request(),"id":root.lower(),"root":root,"ticker":ticker,"contract_id":root+"-contract"}]}
    plan={"id":"plan","calendar":cal,"markets":requests}
    plan_path=tmp_path/"data/backtests"/pb.PLAN_DIR/"plan.json";plan_path.parent.mkdir(parents=True);plan_path.write_text(json.dumps(plan))
    es_request={**requests["ES"]["requests"][0],"plan_id":"plan"}
    es_raw=json.dumps({"results":[raw_row("ESM6")]}).encode()
    pb.PassBStore(tmp_path,plan).retain("ES",es_request,es_raw,200,"safe-es")
    calls=[];sleeps=[]
    def fetch(request,key):
        calls.append(request["root"])
        return 200,json.dumps({"results":[raw_row(request["ticker"])]}).encode(),"safe-nq"
    result=pb.execute(tmp_path,"synthetic-canary",fetch=fetch,sleep=sleeps.append)
    assert calls==["NQ"] and sleeps==[]
    assert result["network_calls"]==1 and result["automatic_retry"] is False and result["recorder_started"] is False
    archive=tmp_path/"data/backtests"/pb.ARCHIVE_DIR
    assert (archive/"ES/raw/es.json").read_bytes()==es_raw
    assert "synthetic-canary" not in "".join(p.read_text(errors="ignore") for p in archive.rglob("*") if p.is_file())


def test_schema_failure_retains_raw_before_parsing(tmp_path):
    cal=ordinary_calendar();requests={root:{"requests":[{**sample_request(),"id":root.lower(),"root":root,"ticker":root+"M6","contract_id":root+"-contract"}]} for root in pb.ROOTS}
    plan={"id":"plan","calendar":cal,"markets":requests};path=tmp_path/"data/backtests"/pb.PLAN_DIR/"plan.json";path.parent.mkdir(parents=True);path.write_text(json.dumps(plan))
    with pytest.raises(pb.PassBError,match="schema"):
        pb.execute(tmp_path,"synthetic-canary",fetch=lambda *_:(200,b'{"unexpected":true}',None),sleep=lambda _:None)
    assert (tmp_path/"data/backtests"/pb.STAGING_DIR/"ES/raw/es.json").read_bytes()==b'{"unexpected":true}'


def test_provider_exception_is_sanitized_and_not_retried(tmp_path):
    requests={root:{"requests":[{**sample_request(),"id":root.lower(),"root":root,"ticker":root+"M6","contract_id":root+"-contract"}]} for root in pb.ROOTS}
    plan={"id":"plan","calendar":ordinary_calendar(),"markets":requests}
    path=tmp_path/"data/backtests"/pb.PLAN_DIR/"plan.json";path.parent.mkdir(parents=True);path.write_text(json.dumps(plan))
    calls=[]
    def failed(*_):
        calls.append(1)
        raise RuntimeError("synthetic-canary-sensitive-body")
    with pytest.raises(pb.PassBError,match=r"provider request failed \(RuntimeError\)") as caught:
        pb.execute(tmp_path,"synthetic-canary-key",fetch=failed,sleep=lambda _:None)
    assert len(calls)==1
    assert "canary" not in str(caught.value)


def test_provider_duplicate_with_wrong_session_label_is_audited_not_double_counted():
    request=sample_request();correct=raw_row();wrong={**correct,"session_end_date":"2025-06-01"}
    calendar={"sessions":[
        {"session_date":"2025-06-01","active_intervals":[{"start_utc":"2025-05-31T22:00:00Z","end_exclusive_utc":"2025-06-01T21:00:00Z"}]},
        *ordinary_calendar()["sessions"]]}
    request={**request,"sessions":["2025-06-01","2025-06-02"]}
    data,rows,reconciliation=pb._normalize(json.dumps({"results":[wrong,correct]}).encode(),request,calendar)
    assert rows==1 and len(data.splitlines())==1
    assert reconciliation=={"policy":"STRICT_SESSION_TIMESTAMP_PAIR_V1","excluded_provider_duplicates":1}


def test_provider_duplicate_conflict_or_missing_canonical_label_fails_closed():
    request=sample_request();correct=raw_row();conflict={**correct,"session_end_date":"2025-06-01","volume":"4"}
    calendar={"sessions":[
        {"session_date":"2025-06-01","active_intervals":[{"start_utc":"2025-05-31T22:00:00Z","end_exclusive_utc":"2025-06-01T21:00:00Z"}]},
        *ordinary_calendar()["sessions"]]}; request={**request,"sessions":["2025-06-01","2025-06-02"]}
    with pytest.raises(pb.PassBError,match="conflicting duplicate"):
        pb._normalize(json.dumps({"results":[conflict,correct]}).encode(),request,calendar)
    with pytest.raises(pb.PassBError,match="session-boundary mismatch"):
        pb._normalize(json.dumps({"results":[{**correct,"session_end_date":"2025-06-01"}]}).encode(),request,calendar)


def test_resume_reconciles_retained_request_then_fetches_first_uncommitted(tmp_path):
    cal={"sessions":[
        {"session_date":"2025-06-01","active_intervals":[{"start_utc":"2025-05-31T22:00:00Z","end_exclusive_utc":"2025-06-01T21:00:00Z"}]},
        *ordinary_calendar()["sessions"]]}
    requests=[]
    for index in range(3):
        requests.append({**sample_request(),"id":f"request-{index}","sessions":["2025-06-01","2025-06-02"],"maximum_rows":2760})
    plan={"id":"plan","calendar":cal,"markets":{"ES":{"requests":requests},"NQ":{"requests":[]}}}
    path=tmp_path/"data/backtests"/pb.PLAN_DIR/"plan.json";path.parent.mkdir(parents=True);path.write_text(json.dumps(plan))
    store=pb.PassBStore(tmp_path,plan);correct=raw_row();wrong={**correct,"session_end_date":"2025-06-01"}
    first={**requests[0],"plan_id":"plan"};raw=json.dumps({"results":[correct]}).encode();store.retain("ES",first,raw,200,None)
    normalized,rows,reconciliation=pb._normalize(raw,first,cal);store.commit("ES",first,normalized,rows,reconciliation)
    second={**requests[1],"plan_id":"plan"};store.retain("ES",second,json.dumps({"results":[wrong,correct]}).encode(),200,None)
    calls=[]
    def fail_on_third(request,_key):
        calls.append(request["id"])
        raise RuntimeError("bounded stop")
    with pytest.raises(pb.PassBError,match="provider request failed"):
        pb.execute(tmp_path,"synthetic",fetch=fail_on_third,sleep=lambda _:None)
    assert calls==["request-2"]
    assert store.complete("ES",second)
    manifest=json.loads((store.stage/"ES/manifests/request-1.json").read_text())
    assert manifest["session_reconciliation"]["excluded_provider_duplicates"]==1


def test_powershell_helper_keeps_key_out_of_arguments_and_has_no_recorder_path():
    root=Path(__file__).resolve().parents[1]
    text=(root/"scripts/enter_massive_es_nq_pass_b_key.ps1").read_text()
    assert "Read-Host" in text and "-AsSecureString" in text
    assert "Get-Content $secretPath -Raw|& $python" in text
    assert "--execute" in text and "--api-key" not in text.lower()
    assert "record" not in text.lower() and "recorder" not in text.lower()
    assert "2>$null" in text and "[Console]::Error.WriteLine($failureMessage)" in text
    assert "throw 'Pass B execution failed closed.'" not in text


def test_malformed_retained_response_is_bounded_and_contextual(tmp_path):
    request=sample_request();plan={"id":"plan","calendar":ordinary_calendar(),"markets":{"ES":{"requests":[request]},"NQ":{"requests":[]}}}
    path=tmp_path/"data/backtests"/pb.PLAN_DIR/"plan.json";path.parent.mkdir(parents=True);path.write_text(json.dumps(plan))
    store=pb.PassBStore(tmp_path,plan);store.retain("ES",{**request,"plan_id":"plan"},b"not-json",200,None)
    with pytest.raises(pb.PassBError,match=r"local validation failed \(JSONDecodeError\)") as caught:
        pb.execute(tmp_path,"synthetic",fetch=lambda *_:pytest.fail("retained raw must not be fetched"),sleep=lambda _:None)
    assert caught.value.details["request_ordinal"]==1
    assert caught.value.details["request_id"]=="request"
