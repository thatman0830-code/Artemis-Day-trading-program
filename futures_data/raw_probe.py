from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .aggregate_probe import (ALLOWED_HOST, BASE_URL, LOCKED_PROBE_TARGETS, MAX_BARS,
    MAX_BYTES, MIN_CALL_INTERVAL_SECONDS, ProbeError, credential_free_mock_opener,
    default_opener, normalize_bars, previous_quarter_ticker, select_five_sessions,
    session_bounds, validate_contract)

PROBE_SCHEMA="massive-es-nq-raw-probe-v2"
DESTINATIONS={"ES":"es_probe_staging_2","NQ":"nq_probe_staging_2"}


def _atomic_new(path:Path,payload:bytes)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".partial")
    if path.exists() or temporary.exists():raise ProbeError("destination path already exists",category="OUTPUT_EXISTS")
    with temporary.open("xb") as handle:
        handle.write(payload);handle.flush();os.fsync(handle.fileno())
    os.rename(temporary,path)


def _safe_parameters(query:dict[str,str])->dict[str,str]:
    if any("key" in x.lower() or "token" in x.lower() for x in query):raise ProbeError("credential entered query parameters",category="CREDENTIAL_BOUNDARY")
    return dict(sorted((str(k),str(v)) for k,v in query.items()))


def request_and_retain(*,path:str,query:dict[str,str],key:str,opener,raw_path:Path,
                       endpoint:str,root:str,ticker:str,retrieved_at:datetime)->tuple[dict,dict]:
    safe_query=_safe_parameters(query);url=BASE_URL+path+"?"+urllib.parse.urlencode(safe_query);parsed=urllib.parse.urlparse(url)
    if parsed.scheme!="https" or parsed.hostname!=ALLOWED_HOST or "apikey" in parsed.query.lower():raise ProbeError("request boundary invalid",category="REQUEST_BOUNDARY",endpoint=endpoint,root=root,ticker=ticker)
    request=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"},method="GET")
    status,raw=opener(request,20.0)
    if len(raw)>MAX_BYTES:raise ProbeError("raw response size limit exceeded",category="SIZE_LIMIT",endpoint=endpoint,status=status,root=root,ticker=ticker)
    _atomic_new(raw_path,raw)
    raw_hash=sha256(raw).hexdigest()
    if sha256(raw_path.read_bytes()).hexdigest()!=raw_hash:raise ProbeError("raw checksum verification failed",category="CHECKSUM",endpoint=endpoint,status=status,root=root,ticker=ticker)
    if status in (401,403):raise ProbeError("authentication or entitlement rejected",category="AUTH_OR_ENTITLEMENT",endpoint=endpoint,status=status,root=root,ticker=ticker)
    if status==429:raise ProbeError("rate limit anomaly",category="RATE_LIMIT",endpoint=endpoint,status=status,root=root,ticker=ticker)
    if status!=200:raise ProbeError("provider request failed",category="HTTP_ERROR",endpoint=endpoint,status=status,root=root,ticker=ticker)
    try:payload=json.loads(raw.decode("utf-8"),parse_float=__import__("decimal").Decimal)
    except Exception as error:raise ProbeError("unexpected provider schema",category="SCHEMA",endpoint=endpoint,status=status,root=root,ticker=ticker) from error
    request_id=payload.get("request_id") if isinstance(payload.get("request_id"),str) else None;results=payload.get("results")
    if payload.get("status")!="OK" or not isinstance(results,list):raise ProbeError("unexpected provider schema",category="SCHEMA",endpoint=endpoint,status=status,request_id=request_id,root=root,ticker=ticker)
    audit={"provider":"massive-futures","endpoint":endpoint,"endpoint_path":path,"parameters":safe_query,
        "ticker":ticker,"retrieved_at":retrieved_at.isoformat().replace("+00:00","Z"),"http_status":status,
        "provider_request_id":request_id,"response_byte_count":len(raw),"raw_response_sha256":raw_hash,
        "raw_relative_path":str(raw_path.relative_to(raw_path.parents[1])).replace("\\","/"),
        "schema_version":PROBE_SCHEMA,"provider_status":payload.get("status"),"returned_record_count":len(results),
        "raw_retained":True,"normalized_output_sha256":None,"normalized_row_count":0}
    return payload,audit


def _json_bytes(value)->bytes:return (json.dumps(value,sort_keys=True,indent=2,default=str)+"\n").encode()
def _rows_bytes(rows)->bytes:return ("\n".join(json.dumps(x,sort_keys=True,separators=(",",":")) for x in rows)+"\n").encode()


def run_raw_probe(*,key:str,metadata_report:Path,repository:Path,now:datetime,opener=default_opener,sleep=time.sleep)->dict:
    metadata=json.loads(metadata_report.read_text(encoding="utf-8"));as_of_year=datetime.fromisoformat(metadata["as_of_utc"].replace("Z","+00:00")).year
    derived={root:previous_quarter_ticker(root,tuple(x["ticker"] for x in metadata["contracts"][root]),as_of_year=as_of_year) for root in ("ES","NQ")}
    targets={root:LOCKED_PROBE_TARGETS[root][0] for root in ("ES","NQ")}
    if derived!=targets:raise ProbeError("locked targets conflict with metadata lineage",category="LOCKED_TARGET_MISMATCH")
    base=repository/"data/backtests";transaction=base/".es_nq_raw_probe_transaction"
    for name in DESTINATIONS.values():
        if (base/name).exists():raise ProbeError("corrected staging destination already exists",category="OUTPUT_EXISTS")
    if transaction.exists():raise ProbeError("probe transaction already exists",category="OUTPUT_EXISTS")
    transaction.mkdir(parents=True);total_raw=0;total_rows=0;call_count=0;summaries={}
    try:
        for root in ("ES","NQ"):
            market=transaction/root
            for part in ("raw","normalized","manifests","reports"):(market/part).mkdir(parents=True)
            ticker=targets[root];point=LOCKED_PROBE_TARGETS[root][1].isoformat();audits=[]
            if call_count:sleep(MIN_CALL_INTERVAL_SECONDS)
            discovery,audit=request_and_retain(path="/futures/v1/contracts",query={"product_code":root,"date":point,"active":"true","type":"single","limit":"1000","sort":"ticker.asc"},key=key,opener=opener,raw_path=market/"raw/001_contract_discovery.json",endpoint="contracts-discovery",root=root,ticker=ticker,retrieved_at=now);call_count+=1;audits.append(audit);total_raw+=audit["response_byte_count"]
            selected=validate_contract(root,ticker,discovery,now=now)
            sleep(MIN_CALL_INTERVAL_SECONDS)
            exact,audit=request_and_retain(path="/futures/v1/contracts",query={"ticker":ticker,"date":point,"type":"single","limit":"2"},key=key,opener=opener,raw_path=market/"raw/002_contract_exact.json",endpoint="contracts-exact",root=root,ticker=ticker,retrieved_at=now);call_count+=1;audits.append(audit);total_raw+=audit["response_byte_count"]
            contract=validate_contract(root,ticker,exact,now=now,selected=selected);sessions=select_five_sessions(contract.last_trade_date);start,end=session_bounds(sessions)
            sleep(MIN_CALL_INTERVAL_SECONDS)
            aggregate,audit=request_and_retain(path=f"/futures/v1/aggs/{ticker}",query={"resolution":"1min","window_start.gte":str(int(start.timestamp()*1_000_000_000)),"window_start.lt":str(int(end.timestamp()*1_000_000_000)),"limit":"10000","sort":"window_start.asc"},key=key,opener=opener,raw_path=market/"raw/003_aggregates.json",endpoint="aggregates",root=root,ticker=ticker,retrieved_at=now);call_count+=1;audits.append(audit);total_raw+=audit["response_byte_count"]
            if aggregate.get("next_url"):raise ProbeError("partial aggregate response requires pagination",category="PARTIAL_RESPONSE",endpoint="aggregates",request_id=aggregate.get("request_id"),count=len(aggregate["results"]),root=root,ticker=ticker)
            bars,gaps=normalize_bars(contract,(aggregate,),sessions);data=_rows_bytes(bars);total_rows+=len(bars)
            if total_rows>MAX_BARS or total_raw+len(data)>MAX_BYTES:raise ProbeError("combined probe cap exceeded",category="COMBINED_LIMIT")
            _atomic_new(market/"normalized/bars.jsonl",data);normal_hash=sha256(data).hexdigest()
            contract_bytes=_json_bytes({"root":root,"ticker":ticker,"first_trade_date":contract.first_trade_date,"last_trade_date":contract.last_trade_date,"settlement_date":contract.settlement_date,"tick_size":contract.tick_size,"venue":contract.venue})
            _atomic_new(market/"normalized/contract.json",contract_bytes);contract_hash=sha256(contract_bytes).hexdigest()
            for index,item in enumerate(audits,1):
                item["normalized_output_sha256"]=normal_hash if index==3 else contract_hash;item["normalized_row_count"]=len(bars) if index==3 else 1
                _atomic_new(market/f"manifests/{index:03d}_request.json",_json_bytes(item))
            report={"status":"VALIDATED_STAGING","schema_version":PROBE_SCHEMA,"root":root,"ticker":ticker,
                "sessions":[x.isoformat() for x in sessions],"row_count":len(bars),"gap_count":len(gaps),
                "earliest":bars[0]["timestamp_utc"],"latest":bars[-1]["timestamp_utc"],"normalized_sha256":normal_hash,
                "raw_retained":True,"raw_files":[x["raw_relative_path"] for x in audits],"request_manifest_count":len(audits)}
            _atomic_new(market/"reports/validation.json",_json_bytes(report));summaries[root]=report
        # Recompute every retained checksum before promotion.
        for root in ("ES","NQ"):
            market=transaction/root
            for manifest_path in sorted((market/"manifests").glob("*.json")):
                item=json.loads(manifest_path.read_text());raw_path=market/item["raw_relative_path"]
                if sha256(raw_path.read_bytes()).hexdigest()!=item["raw_response_sha256"]:raise ProbeError("retained raw checksum conflict",category="CHECKSUM",root=root)
        for root in ("ES","NQ"):os.rename(transaction/root,base/DESTINATIONS[root])
        transaction.rmdir()
        return {"status":"ES_NQ_PROBE_VALIDATED","schema_version":PROBE_SCHEMA,"request_count":call_count,"aggregate_request_count":2,"total_rows":total_rows,"raw_retained":True,"markets":summaries}
    except Exception as error:
        rejected=base/"rejected_probes"/("raw_probe_"+now.strftime("%Y%m%dT%H%M%SZ"))
        if transaction.exists() and not rejected.exists():
            rejected.parent.mkdir(parents=True,exist_ok=True);os.rename(transaction,rejected)
            safe=getattr(error,"safe",{"lifecycle_stage":"RAW_PROBE","rejection_category":"UNCLASSIFIED"})
            _atomic_new(rejected/"sanitized_failure.json",_json_bytes(safe))
        raise
    finally:
        if transaction.exists():shutil.rmtree(transaction)


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("--repository",type=Path,required=True);parser.add_argument("--metadata",type=Path,required=True);parser.add_argument("--credential-free-mock",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args(argv);key=sys.stdin.readline().rstrip("\r\n")
    try:
        result=run_raw_probe(key=key,metadata_report=args.metadata,repository=args.repository.resolve(),now=datetime.now(timezone.utc),opener=credential_free_mock_opener if args.credential_free_mock else default_opener,sleep=(lambda _:None) if args.credential_free_mock else time.sleep)
        print(result["status"]);return 0
    except Exception as error:print("BLOCKED: "+str(error),file=sys.stderr);return 1
    finally:key=""
if __name__=="__main__":raise SystemExit(main())
