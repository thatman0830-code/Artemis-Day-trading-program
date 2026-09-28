from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from futures_data.forward_bootstrap import build_bootstrap
from futures_data.forward_collector import ForwardCollectorError
from futures_data.forward_reference_refresh import ReferenceRefresher, build_successor, default_fetcher, refresh_required, publish_successor, resolve_current, _events_to_schedules
from futures_data.validate_forward_configuration import validate_configuration


REPOSITORY=Path(__file__).resolve().parents[1]


def test_retained_evidence_builds_zero_pending_immutable_bootstrap():
    configuration,manifest,audit=build_bootstrap(REPOSITORY)
    assert configuration["sessions"]==[] and configuration["pending_session_count"]==0
    assert len(configuration["history"])==626
    assert {x["root"] for x in configuration["history"]}=={"ES","NQ"}
    assert configuration["verified_coverage"]["last_session"]=="2026-08-26"
    assert audit["result"]=="VALID_ZERO_PENDING_BOOTSTRAP" and manifest["configuration_sha256"]


def test_installed_bootstrap_and_manifest_validate():
    sessions=validate_configuration(REPOSITORY/"config/es_nq_forward_sessions.json",repository=REPOSITORY)
    assert sessions==()


def future_payload(root):
    ticker=root+"U6"
    schedule={"product_code":root,"trading_venue":"XCME","session_date":"2026-08-27",
        "active_intervals":[{"start_utc":"2026-08-26T22:00:00Z","end_exclusive_utc":"2026-08-27T21:00:00Z"}]}
    contract={"ticker":ticker,"product_code":root,"type":"single","trading_venue":"XCME",
        "first_trade_date":"2023-08-21","last_trade_date":"2026-09-18","settlement_date":"2026-09-18"}
    return schedule,contract


def test_reference_refresh_raw_first_exact_contract_and_atomic_successor(tmp_path):
    config,_,_=build_bootstrap(REPOSITORY); calls=[]
    def fetch(endpoint,root,key,page_url=None,contract_ticker=None):
        calls.append((endpoint,root,key)); schedule,contract=future_payload(root)
        if contract_ticker:contract["ticker"]=contract_ticker
        return 200,json.dumps({"status":"OK","results":[schedule if endpoint=="schedules" else contract]}).encode(),"safe"
    result=ReferenceRefresher(tmp_path,fetch,sleep=lambda _:None).run(config,"synthetic",datetime(2026,8,27,tzinfo=timezone.utc))
    assert result["network_calls"]==6 and result["automatic_retry"] is False
    assert len(result["configuration"]["sessions"])==2
    assert all((tmp_path/"data/futures_forward/references"/result["refresh_id"]/root/"raw/schedules.json").exists() for root in ("ES","NQ"))


def test_contract_refresh_queries_bounded_lifecycle_index_not_weekend_point_in_time(monkeypatch):
    config,_,_=build_bootstrap(REPOSITORY);seen=[]
    class Response:
        status=200;headers={}
        def __enter__(self):return self
        def __exit__(self,*_):return False
        def read(self,_):return b'{"status":"OK","results":[]}'
    def urlopen(request,**_):seen.append(request.full_url);return Response()
    monkeypatch.setattr("urllib.request.urlopen",urlopen)
    default_fetcher(config)("contracts","ES","secret",contract_ticker="ESU6")
    query=seen[0].split("?",1)[1]
    assert "product_code=ES" in query and "ticker=ESU6" in query and "date.lt=2026-08-27" in urllib.parse.unquote(query)
    assert "type=single" in query and "limit=1" in query and "sort=date.desc" in query and "active=" not in query


def test_reference_refresh_accepts_only_newest_exact_contract_version(tmp_path):
    config,_,_=build_bootstrap(REPOSITORY); seen=[]
    def fetch(endpoint,root,key,page_url=None,contract_ticker=None):
        seen.append((endpoint,root,page_url,contract_ticker));schedule,contract=future_payload(root)
        if contract_ticker:contract["ticker"]=contract_ticker
        payload={"status":"OK","results":[schedule if endpoint=="schedules" else contract]}
        if endpoint=="contracts" and contract_ticker.endswith("U6") and page_url is None:
            payload["next_url"]="https://api.massive.com/futures/v1/contracts?cursor=safe"
        return 200,json.dumps(payload).encode(),"safe"
    result=ReferenceRefresher(tmp_path,fetch,sleep=lambda _:None).run(config,"synthetic",datetime(2026,8,27,tzinfo=timezone.utc))
    assert result["network_calls"]==6
    assert not any(endpoint=="contracts" and page_url for endpoint,_,page_url,_ in seen)


def test_exact_contract_response_rejects_mislabeled_calendar_spread(tmp_path):
    config,_,_=build_bootstrap(REPOSITORY)
    def fetch(endpoint,root,key,page_url=None,contract_ticker=None):
        schedule,contract=future_payload(root)
        if contract_ticker:contract["ticker"]=contract_ticker
        rows=[schedule] if endpoint=="schedules" else [{**contract,"ticker":contract["ticker"]+"-"+root+"Z6"},contract]
        return 200,json.dumps({"results":rows}).encode(),None
    with pytest.raises(ForwardCollectorError,match="exact contract response"):
        ReferenceRefresher(tmp_path,fetch,sleep=lambda _:None).run(config,"synthetic",datetime(2026,8,27,tzinfo=timezone.utc))


@pytest.mark.parametrize("next_url",[
    "http://api.massive.com/futures/v1/schedules?cursor=x",
    "https://evil.example/futures/v1/schedules?cursor=x",
    "https://api.massive.com/futures/v1/contracts?cursor=x",
])
def test_reference_refresh_rejects_untrusted_pagination_target(tmp_path,next_url):
    config,_,_=build_bootstrap(REPOSITORY)
    def fetch(endpoint,root,key,page_url=None,contract_ticker=None):
        schedule,contract=future_payload(root)
        if contract_ticker:contract["ticker"]=contract_ticker
        payload={"results":[schedule if endpoint=="schedules" else contract]}
        if endpoint=="schedules":payload["next_url"]=next_url
        return 200,json.dumps(payload).encode(),None
    with pytest.raises(ForwardCollectorError,match="pagination target"):
        ReferenceRefresher(tmp_path,fetch,sleep=lambda _:None).run(config,"synthetic",datetime(2026,8,27,tzinfo=timezone.utc))


@pytest.mark.parametrize("mutation",["micro","venue","combo"])
def test_reference_refresh_rejects_prohibited_contracts(tmp_path,mutation):
    config,_,_=build_bootstrap(REPOSITORY)
    def fetch(endpoint,root,key,page_url=None,contract_ticker=None):
        schedule,contract=future_payload(root)
        if contract_ticker:contract["ticker"]=contract_ticker
        if endpoint=="contracts":
            if mutation=="micro":contract["ticker"]="MESU6" if root=="ES" else "MNQU6"
            if mutation=="venue":contract["trading_venue"]="OTHER"
            if mutation=="combo":contract["type"]="combo"
        return 200,json.dumps({"results":[schedule if endpoint=="schedules" else contract]}).encode(),None
    with pytest.raises(ForwardCollectorError,match="contract"):
        ReferenceRefresher(tmp_path,fetch,sleep=lambda _:None).run(config,"synthetic",datetime(2026,8,27,tzinfo=timezone.utc))


def test_refresh_does_not_fabricate_non_contiguous_future_date():
    config,_,_=build_bootstrap(REPOSITORY); schedules=[];contracts=[]
    for root in ("ES","NQ"):
        schedule,contract=future_payload(root);schedule["session_date"]="2026-08-28";schedules.append(schedule);contracts.append(contract)
    with pytest.raises(ForwardCollectorError,match="non-contiguous"):build_successor(config,schedules,contracts)


def test_refresh_accepts_weekend_between_exclusive_boundary_and_next_session():
    config,_,_=build_bootstrap(REPOSITORY);schedules=[];contracts=[]
    config["verified_coverage"]={**config["verified_coverage"],
        "end_exclusive":"2026-08-29","last_session":"2026-08-28"}
    for root in ("ES","NQ"):
        schedule,contract=future_payload(root);schedule["root"]=root
        schedule["session_date"]="2026-08-31"
        schedules.append(schedule);contracts.append(contract)
    successor=build_successor(config,schedules,contracts)
    assert successor["verified_coverage"]["last_session"]=="2026-08-31"


def test_refresh_horizon_boundary():
    config,_,_=build_bootstrap(REPOSITORY)
    assert refresh_required(config,datetime(2026,8,27,tzinfo=timezone.utc))


def test_future_rollover_is_prepared_but_not_decided():
    config,_,_=build_bootstrap(REPOSITORY);schedules=[];contracts=[]
    for root in ("ES","NQ"):
        for day in range(14,19):
            schedule,current=future_payload(root);schedule["root"]=root;schedule["session_date"]=f"2026-09-{day:02d}";schedules.append(schedule)
        contracts.append(current)
        contracts.append({**current,"ticker":root+"Z6","last_trade_date":"2026-12-18","settlement_date":"2026-12-18"})
    config["verified_coverage"]={**config["verified_coverage"],"end_exclusive":"2026-09-14","last_session":"2026-09-11"}
    successor=build_successor(config,schedules,contracts)
    assert len(successor["rollover_preparations"])==2
    assert all(x["state"]=="AWAITING_FINALIZED_VOLUME" and x["rollover_decision"] is None for x in successor["rollover_preparations"])
    assert {x["rollover_leg"] for x in successor["sessions"]}=={"OUTGOING","INCOMING"}


def test_expired_contract_advances_to_verified_successor():
    config,_,_=build_bootstrap(REPOSITORY);schedules=[];contracts=[]
    config["verified_coverage"]={**config["verified_coverage"],"end_exclusive":"2026-09-19","last_session":"2026-09-18"}
    for root in ("ES","NQ"):
        schedule,current=future_payload(root);schedule["root"]=root;schedule["session_date"]="2026-09-21";schedules.append(schedule)
        contracts.extend([current,{**current,"ticker":root+"Z6","first_trade_date":"2021-09-17","last_trade_date":"2026-12-18","settlement_date":"2026-12-18"}])
    successor=build_successor(config,schedules,contracts)
    assert {x["ticker"] for x in successor["sessions"]}=={"ESZ6","NQZ6"}
    assert {x["rollover_leg"] for x in successor["sessions"]}=={"ACTIVE"}


def test_successor_publication_is_versioned_and_pointer_is_checksum_verified(tmp_path):
    config,_,_=build_bootstrap(REPOSITORY);schedule_es,contract_es=future_payload("ES");schedule_nq,contract_nq=future_payload("NQ");schedule_es["root"]="ES";schedule_nq["root"]="NQ"
    successor=build_successor(config,[schedule_es,schedule_nq],[contract_es,contract_nq])
    path,manifest=publish_successor(tmp_path,successor)
    current,current_manifest=resolve_current(tmp_path,tmp_path/"bootstrap.json")
    assert current==path and current_manifest==manifest
    assert not (tmp_path/"config/es_nq_forward_current.json.partial").exists()


def test_exact_failed_attempt_mixed_outright_and_spread_schedule_is_filtered():
    rows=[]
    for name in ("E-mini Standard and Poor's 500 Stock Price Index Futures","ES Equity Calendar Spread"):
        for event,stamp in (("pre_open","2026-08-26T21:00:00Z"),("open","2026-08-26T22:00:00Z"),("close","2026-08-27T21:00:00Z")):
            rows.append({"product_code":"ES","product_name":name,"trading_venue":"XCME","session_end_date":"2026-08-27","event":event,"timestamp":stamp})
    result=_events_to_schedules("ES",rows,"2026-08-27")
    assert len(result)==1 and result[0]["session_date"]=="2026-08-27"


def test_reconciled_current_configuration_avoids_duplicate_reference_request():
    path,manifest=resolve_current(REPOSITORY,REPOSITORY/"config/es_nq_forward_sessions.json")
    configuration=json.loads(path.read_text())
    validate_configuration(path,repository=REPOSITORY,manifest_path=manifest)
    bootstrap_id=json.loads((REPOSITORY/"config/es_nq_forward_sessions.json").read_text())["configuration_id"]
    cursor=configuration;seen=set()
    while cursor["configuration_id"]!=bootstrap_id:
        assert cursor["configuration_id"] not in seen and len(seen)<10
        seen.add(cursor["configuration_id"])
        parent_id=cursor["parent_configuration_id"]
        if parent_id==bootstrap_id:break
        cursor=json.loads((REPOSITORY/"config/es_nq_forward_versions"/(parent_id+".json")).read_text())
    assert seen
    assert not refresh_required(configuration,datetime(2026,8,27,tzinfo=timezone.utc))


def test_wrapper_uses_private_stdin_and_is_location_independent():
    source=(REPOSITORY/"scripts/run_es_nq_delayed_forward_collector.ps1").read_text()
    assert "$PSScriptRoot" in source and "WorkingDirectory=$repository" in source
    assert "RedirectStandardInput=$true" in source and "StandardInput.WriteLine($plain)" in source
    assert "--api-key" not in source.lower() and "2>$null" not in source
