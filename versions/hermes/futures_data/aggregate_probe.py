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
from dataclasses import dataclass
from datetime import date, datetime, time as day_time, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from .contracts import identity
from .massive import MONTH_CODES, parse_outright_ticker

BASE_URL="https://api.massive.com"; ALLOWED_HOST="api.massive.com"
ROOTS=("ES","NQ"); VENUE="XCME"; MAX_BARS=20_000; MAX_BYTES=25*1024*1024
MIN_CALL_INTERVAL_SECONDS=15.0; MAX_PAGES_PER_MARKET=2
CHICAGO=ZoneInfo("America/Chicago")
LOCKED_PROBE_TARGETS={"ES":("ESM6",date(2026,6,18)),"NQ":("NQM6",date(2026,6,18))}


class ProbeError(RuntimeError):
    def __init__(self,message,*,stage="VALIDATION",category="VALIDATION",endpoint=None,status=None,
                 request_id=None,count=None,root=None,ticker=None,returned_contracts=None):
        super().__init__(message); self.safe={"lifecycle_stage":stage,"http_status":status,
            "endpoint":endpoint,"provider_request_id":request_id,"returned_record_count":count,
            "rejection_category":category,"root":root,"ticker":ticker,
            "returned_contracts":returned_contracts}


@dataclass(frozen=True)
class SelectedContract:
    root:str; ticker:str; first_trade_date:date; last_trade_date:date; settlement_date:date
    tick_size:Decimal; venue:str; provider_request_id:str


def previous_quarter_ticker(root:str, active_tickers:tuple[str,...], *, as_of_year:int)->str:
    parsed=[]
    for ticker in active_tickers:
        try: parsed.append(parse_outright_ticker(ticker,contract_year_hint=as_of_year))
        except ValueError: continue
    candidates=[x for x in parsed if x[0].value==root]
    if not candidates: raise ProbeError("validated metadata has no usable active root",category="NO_ACTIVE_LINEAGE",root=root)
    _,month,year=min(candidates,key=lambda x:(x[2],x[1]))
    quarters=(3,6,9,12); earlier=[m for m in quarters if m<month]
    previous_month=max(earlier) if earlier else 12; previous_year=year if earlier else year-1
    code=next(code for code,value in MONTH_CODES.items() if value==previous_month)
    return f"{root}{code}{previous_year%10}"


def select_five_sessions(expiration:date)->tuple[date,...]:
    cursor=expiration-timedelta(days=7); selected=[]
    while len(selected)<5:
        if cursor.weekday()<5: selected.append(cursor)
        cursor-=timedelta(days=1)
    result=tuple(sorted(selected))
    if expiration in result or any((expiration-x).days<7 for x in result):
        raise ProbeError("sessions overlap expiration boundary",category="SESSION_SELECTION")
    return result


def session_bounds(sessions:tuple[date,...])->tuple[datetime,datetime]:
    start_local=datetime.combine(sessions[0]-timedelta(days=1),day_time(17),tzinfo=CHICAGO)
    end_local=datetime.combine(sessions[-1],day_time(16),tzinfo=CHICAGO)
    return start_local.astimezone(timezone.utc),end_local.astimezone(timezone.utc)


def _request(path:str,query:dict[str,str],key:str,opener,*,endpoint:str)->tuple[dict,bytes]:
    url=BASE_URL+path+"?"+urllib.parse.urlencode(query); parsed=urllib.parse.urlparse(url)
    if parsed.scheme!="https" or parsed.hostname!=ALLOWED_HOST or "apikey" in parsed.query.lower():
        raise ProbeError("request boundary invalid",category="REQUEST_BOUNDARY",endpoint=endpoint)
    request=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"},method="GET")
    status,raw=opener(request,20.0)
    if status in (401,403): raise ProbeError("authentication or entitlement rejected",category="AUTH_OR_ENTITLEMENT",endpoint=endpoint,status=status)
    if status==429: raise ProbeError("rate limit reached",category="RATE_LIMIT",endpoint=endpoint,status=status)
    if status!=200: raise ProbeError("provider request failed",category="HTTP_ERROR",endpoint=endpoint,status=status)
    if len(raw)>MAX_BYTES: raise ProbeError("raw response size limit exceeded",category="SIZE_LIMIT",endpoint=endpoint,status=status)
    try: payload=json.loads(raw.decode(),parse_float=Decimal)
    except Exception as error: raise ProbeError("malformed provider JSON",category="MALFORMED_RESPONSE",endpoint=endpoint,status=status) from error
    request_id=payload.get("request_id") if isinstance(payload.get("request_id"),str) else None
    if payload.get("status")!="OK" or not isinstance(payload.get("results"),list):
        raise ProbeError("invalid provider response",category="MALFORMED_RESPONSE",endpoint=endpoint,status=status,request_id=request_id)
    return payload,raw


def default_opener(request,timeout):
    context=ssl.create_default_context()
    try:
        with urllib.request.urlopen(request,timeout=timeout,context=context) as response:return response.status,response.read(MAX_BYTES+1)
    except urllib.error.HTTPError as error:return error.code,error.read(65536)


def _safe_contract_tuples(rows:list[dict])->list[dict]:
    return [{"ticker":str(x.get("ticker")),"product_code":str(x.get("product_code")),
             "type":str(x.get("type")),"trading_venue":str(x.get("trading_venue"))}
            for x in rows[:16]]


def validate_contract(root:str,ticker:str,payload:dict,*,now:datetime,
                      selected:SelectedContract|None=None)->SelectedContract:
    rows=payload["results"]; request_id=str(payload.get("request_id") or "")
    tuples=_safe_contract_tuples(rows)
    if selected is None:
        for item in rows:
            if item.get("product_code")!=root or item.get("type")!="single" or item.get("trading_venue")!=VENUE:
                raise ProbeError("provider ignored exact discovery filters",category="PROVIDER_CONTRACT_MISMATCH",endpoint="contracts",status=200,request_id=request_id,count=len(rows),root=root,ticker=ticker,returned_contracts=tuples)
            try:
                settlement_year=date.fromisoformat(str(item.get("settlement_date"))).year
                parsed_root,_,_=parse_outright_ticker(str(item.get("ticker")),contract_year_hint=settlement_year)
                if parsed_root.value!=root:raise ValueError("wrong root")
            except Exception as error:
                raise ProbeError("discovery returned a prohibited instrument",category="PROVIDER_CONTRACT_MISMATCH",endpoint="contracts",status=200,request_id=request_id,count=len(rows),root=root,ticker=ticker,returned_contracts=tuples) from error
        matches=[item for item in rows if item.get("ticker")==ticker]
        if len(matches)!=1: raise ProbeError("discovery did not contain exactly one locked ticker",category="DISCOVERY_SELECTION_MISMATCH",endpoint="contracts",status=200,request_id=request_id,count=len(rows),root=root,ticker=ticker,returned_contracts=tuples)
        row=matches[0]
    else:
        if len(rows)!=1: raise ProbeError("exact ticker lookup returned zero or multiple records",category="PROVIDER_CONTRACT_MISMATCH",endpoint="contracts",status=200,request_id=request_id,count=len(rows),root=root,ticker=ticker,returned_contracts=tuples)
        row=rows[0]
    if row.get("ticker")!=ticker or row.get("product_code")!=root or row.get("type")!="single" or row.get("trading_venue")!=VENUE:
        raise ProbeError("contract identity mismatch",category="PROVIDER_CONTRACT_MISMATCH",endpoint="contracts",status=200,request_id=request_id,count=len(rows),root=str(row.get("product_code")),ticker=str(row.get("ticker")),returned_contracts=tuples)
    try:
        last=date.fromisoformat(row["last_trade_date"]); settlement=date.fromisoformat(row["settlement_date"])
        first=date.fromisoformat(row["first_trade_date"]); tick=Decimal(str(row["trade_tick_size"]))
        parse_outright_ticker(ticker,contract_year_hint=settlement.year)
    except Exception as error: raise ProbeError("contract fields malformed",category="MALFORMED_CONTRACT",endpoint="contracts",request_id=request_id,count=1,root=root,ticker=ticker) from error
    if last>=now.date() or settlement>=now.date() or tick<=0:
        raise ProbeError("contract is not fully expired",category="NOT_EXPIRED",endpoint="contracts",request_id=request_id,count=1,root=root,ticker=ticker)
    result=SelectedContract(root,ticker,first,last,settlement,tick,VENUE,request_id)
    if selected is not None and (result.ticker,result.root,result.first_trade_date,result.last_trade_date,
            result.settlement_date,result.tick_size,result.venue)!=(selected.ticker,selected.root,
            selected.first_trade_date,selected.last_trade_date,selected.settlement_date,selected.tick_size,selected.venue):
        raise ProbeError("exact lookup conflicts with selected discovery metadata",category="PROVIDER_CONTRACT_MISMATCH",endpoint="contracts",status=200,request_id=request_id,count=1,root=root,ticker=ticker,returned_contracts=tuples)
    return result


def normalize_bars(contract:SelectedContract,payloads:tuple[dict,...],sessions:tuple[date,...])->tuple[tuple[dict,...],tuple[dict,...]]:
    rows=[row for payload in payloads for row in payload["results"]]
    if len(rows)>MAX_BARS: raise ProbeError("bar limit exceeded",category="BAR_LIMIT",endpoint="aggregates",count=len(rows),root=contract.root,ticker=contract.ticker)
    normalized=[]; seen=set()
    for row in rows:
        if row.get("ticker")!=contract.ticker: raise ProbeError("cross-contract contamination",category="CONTRACT_CONTAMINATION",endpoint="aggregates",count=len(rows),root=contract.root,ticker=str(row.get("ticker")))
        ns=row.get("window_start")
        if isinstance(ns,bool) or not isinstance(ns,int) or ns in seen: raise ProbeError("duplicate or malformed timestamp",category="DUPLICATE_OR_TIMESTAMP",endpoint="aggregates",count=len(rows),root=contract.root,ticker=contract.ticker)
        seen.add(ns); seconds,remainder=divmod(ns,1_000_000_000); stamp=datetime.fromtimestamp(seconds,tz=timezone.utc).replace(microsecond=remainder//1000)
        session=date.fromisoformat(str(row.get("session_end_date")))
        if session not in sessions: raise ProbeError("bar outside selected sessions",category="SESSION_CONTAMINATION",endpoint="aggregates",count=len(rows),root=contract.root,ticker=contract.ticker)
        values={name:Decimal(str(row[name])) for name in ("open","high","low","close","volume")}
        if any(not x.is_finite() for x in values.values()) or values["volume"]<0 or min(values[n] for n in ("open","high","low","close"))<=0 or values["high"]<max(values["open"],values["close"]) or values["low"]>min(values["open"],values["close"]):
            raise ProbeError("invalid aggregate geometry",category="OHLC_OR_VOLUME",endpoint="aggregates",count=len(rows),root=contract.root,ticker=contract.ticker)
        normalized.append({"id":identity("futures-probe-bar-v1",contract.ticker,ns),"ticker":contract.ticker,"root":contract.root,
            "window_start_ns":ns,"timestamp_utc":stamp.isoformat().replace("+00:00","Z"),"session_end_date":session.isoformat(),
            **{k:format(v,"f") for k,v in values.items()}})
    normalized.sort(key=lambda x:x["window_start_ns"])
    if [x["window_start_ns"] for x in normalized]!=sorted(seen): raise ProbeError("timestamps not monotonic",category="ORDERING",endpoint="aggregates",root=contract.root,ticker=contract.ticker)
    start,end=session_bounds(sessions); expected=[]; cursor=start
    observed={x["timestamp_utc"] for x in normalized}
    while cursor<end:
        local=cursor.astimezone(CHICAGO)
        trading_date=(local.date()+timedelta(days=1)) if local.time()>=day_time(17) else local.date()
        if trading_date in sessions and not (day_time(16)<=local.time()<day_time(17)):
            key=cursor.isoformat().replace("+00:00","Z")
            if key not in observed: expected.append({"timestamp_utc":key,"classification":"UNEXPLAINED_MISSING"})
        cursor+=timedelta(minutes=1)
    if expected: raise ProbeError("scheduled-session gaps detected",category="GAPPED",endpoint="aggregates",count=len(expected),root=contract.root,ticker=contract.ticker)
    return tuple(normalized),tuple(expected)


def _bytes(rows:tuple[dict,...])->bytes:
    return ("\n".join(json.dumps(x,sort_keys=True,separators=(",",":")) for x in rows)+"\n").encode()


def _atomic_write(path:Path,payload:bytes)->None:
    temporary=path.with_suffix(path.suffix+".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload);handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)


def run_probe(*,key:str,metadata_report:Path,repository:Path,now:datetime,opener=default_opener,sleep=time.sleep)->dict:
    metadata=json.loads(metadata_report.read_text(encoding="utf-8")); as_of_year=datetime.fromisoformat(metadata["as_of_utc"].replace("Z","+00:00")).year
    derived={root:previous_quarter_ticker(root,tuple(x["ticker"] for x in metadata["contracts"][root]),as_of_year=as_of_year) for root in ROOTS}
    tickers={root:LOCKED_PROBE_TARGETS[root][0] for root in ROOTS}
    if derived!=tickers:raise ProbeError("locked probe target conflicts with validated metadata lineage",category="LOCKED_TARGET_MISMATCH")
    responses={}; call_count=0; raw_bytes_total=0
    for root in ROOTS:
        if call_count:sleep(MIN_CALL_INTERVAL_SECONDS)
        point_in_time=LOCKED_PROBE_TARGETS[root][1].isoformat()
        discovery,raw=_request("/futures/v1/contracts",{"product_code":root,"date":point_in_time,"active":"true","type":"single","limit":"1000","sort":"ticker.asc"},key,opener,endpoint="contracts");call_count+=1
        raw_bytes_total+=len(raw);selected=validate_contract(root,tickers[root],discovery,now=now)
        sleep(MIN_CALL_INTERVAL_SECONDS)
        exact,raw_exact=_request("/futures/v1/contracts",{"ticker":tickers[root],"date":point_in_time,"type":"single","limit":"2"},key,opener,endpoint="contracts");call_count+=1
        raw_bytes_total+=len(raw_exact);contract=validate_contract(root,tickers[root],exact,now=now,selected=selected); sessions=select_five_sessions(contract.last_trade_date); start,end=session_bounds(sessions)
        sleep(MIN_CALL_INTERVAL_SECONDS)
        query={"resolution":"1min","window_start.gte":str(int(start.timestamp()*1_000_000_000)),"window_start.lt":str(int(end.timestamp()*1_000_000_000)),"limit":"10000","sort":"window_start.asc"}
        agg,raw_agg=_request(f"/futures/v1/aggs/{contract.ticker}",query,key,opener,endpoint="aggregates");call_count+=1
        if agg.get("next_url"): raise ProbeError("aggregate pagination exceeds two-request probe",category="PAGINATION_REQUIRED",endpoint="aggregates",request_id=agg.get("request_id"),count=len(agg["results"]),root=root,ticker=contract.ticker)
        bars,gaps=normalize_bars(contract,(agg,),sessions)
        raw_bytes_total+=len(raw_agg);responses[root]=(contract,sessions,bars,gaps,agg.get("request_id"),sha256(raw_agg).hexdigest())
    total=sum(len(x[2]) for x in responses.values()); payloads={root:_bytes(responses[root][2]) for root in ROOTS}
    if total>MAX_BARS or sum(len(x) for x in payloads.values())+raw_bytes_total>MAX_BYTES: raise ProbeError("combined probe scope exceeded",category="COMBINED_LIMIT")
    transaction=repository/"data/backtests/.es_nq_probe_transaction"
    if transaction.exists(): shutil.rmtree(transaction)
    transaction.mkdir(parents=True)
    try:
        summaries={}
        for root in ROOTS:
            contract,sessions,bars,gaps,request_id,raw_hash=responses[root]; folder=transaction/root;folder.mkdir()
            data=payloads[root]; _atomic_write(folder/"bars.jsonl",data)
            summary={"status":"VALIDATED_STAGING","root":root,"contract":contract.ticker,"sessions":[x.isoformat() for x in sessions],
                "row_count":len(bars),"earliest":bars[0]["timestamp_utc"],"latest":bars[-1]["timestamp_utc"],
                "provider_request_id":request_id,"raw_response_sha256":raw_hash,"normalized_sha256":sha256(data).hexdigest(),
                "raw_retained":False,"gap_count":len(gaps),"retrieved_at":now.isoformat().replace("+00:00","Z")}
            _atomic_write(folder/"manifest.json",(json.dumps(summary,sort_keys=True,indent=2)+"\n").encode());
            if sha256((folder/"bars.jsonl").read_bytes()).hexdigest()!=summary["normalized_sha256"]:raise ProbeError("staging checksum verification failed",category="CHECKSUM",root=root)
            summaries[root]=summary
        for root,name in (("ES","es_probe_staging_1"),("NQ","nq_probe_staging_1")):
            target=repository/"data/backtests"/name
            if target.exists(): raise ProbeError("probe staging output already exists",category="OUTPUT_EXISTS",root=root)
        for root,name in (("ES","es_probe_staging_1"),("NQ","nq_probe_staging_1")): os.replace(transaction/root,repository/"data/backtests"/name)
        transaction.rmdir()
        return {"status":"ES_NQ_PROBE_VALIDATED","request_count":call_count,"aggregate_request_count":2,"total_rows":total,"markets":summaries}
    finally:
        if transaction.exists(): shutil.rmtree(transaction)


def credential_free_mock_opener(request,timeout):
    parsed=urllib.parse.urlparse(request.full_url); query=urllib.parse.parse_qs(parsed.query)
    if request.get_header("Authorization")!="Bearer synthetic-offline-only":return 403,b'{}'
    if parsed.path.endswith("/contracts"):
        root=query.get("product_code",[""])[0];ticker=query.get("ticker",[""])[0]
        if root:ticker=LOCKED_PROBE_TARGETS[root][0]
        else:root=ticker[:2]
        row={"ticker":ticker,"product_code":root,"type":"single","trading_venue":"XCME","first_trade_date":"2024-01-01","last_trade_date":"2026-06-19","settlement_date":"2026-06-19","trade_tick_size":"0.25"};payload={"status":"OK","request_id":"mock-contract-"+root,"results":[row]}
    else:
        ticker=parsed.path.rsplit("/",1)[-1];root=ticker[:2];start_ns=int(query["window_start.gte"][0]);end_ns=int(query["window_start.lt"][0]);rows=[]
        for ns in range(start_ns,end_ns,60_000_000_000):
            stamp=datetime.fromtimestamp(ns/1_000_000_000,tz=timezone.utc);local=stamp.astimezone(CHICAGO);session=(local.date()+timedelta(days=1)) if local.time()>=day_time(17) else local.date()
            if session.weekday()<5 and not(day_time(16)<=local.time()<day_time(17)):
                rows.append({"ticker":ticker,"window_start":ns,"session_end_date":session.isoformat(),"open":"100","high":"101","low":"99","close":"100.5","volume":10})
        payload={"status":"OK","request_id":"mock-aggs-"+root,"results":rows}
    return 200,json.dumps(payload,separators=(",",":")).encode()


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("--repository",type=Path,required=True);parser.add_argument("--metadata",type=Path,required=True);parser.add_argument("--credential-free-mock",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args(argv);key=sys.stdin.readline().rstrip("\r\n")
    try:
        result=run_probe(key=key,metadata_report=args.metadata,repository=args.repository.resolve(),now=datetime.now(timezone.utc),opener=credential_free_mock_opener if args.credential_free_mock else default_opener,sleep=(lambda _:None) if args.credential_free_mock else time.sleep)
        print(result["status"]);return 0
    except Exception as error:
        safe=getattr(error,"safe",{"lifecycle_stage":"PROBE","rejection_category":"UNCLASSIFIED"});path=args.repository/"data/backtests/es_nq_probe_diagnostic.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(safe,sort_keys=True,indent=2)+"\n",encoding="utf-8");print("BLOCKED: "+str(error),file=sys.stderr);return 1
    finally:key=""

if __name__=="__main__":raise SystemExit(main())
