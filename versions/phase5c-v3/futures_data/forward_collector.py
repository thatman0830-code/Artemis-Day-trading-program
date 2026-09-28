from __future__ import annotations

import json
import os
import sys
import time
import argparse
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Callable

from futures_data import pass_b_backfill as canonical

SCHEMA_VERSION="es-nq-delayed-forward-v1"
ROOTS=("ES","NQ")
RECENCY_DELAY=timedelta(hours=8)
DEFAULT_SAFETY_BUFFER=timedelta(hours=1)
MIN_REQUEST_INTERVAL=15.0
RUN_REQUEST_CAP=20
RUN_ROW_CAP=100_000
RUN_RAW_CAP=50*1024*1024
RUN_NORMALIZED_CAP=100*1024*1024
RUN_COMBINED_CAP=150*1024*1024
CUMULATIVE_RAW_CAP=1024*1024*1024
CUMULATIVE_NORMALIZED_CAP=2*1024*1024*1024
CUMULATIVE_COMBINED_CAP=3*1024*1024*1024


class ForwardCollectorError(RuntimeError):
    pass


def _bytes(value:object)->bytes:
    return (json.dumps(value,sort_keys=True,indent=2,default=str)+"\n").encode()


def _hash(path:Path)->str:
    return sha256(path.read_bytes()).hexdigest()


def _atomic(path:Path,payload:bytes)->None:
    path.parent.mkdir(parents=True,exist_ok=True);partial=path.with_suffix(path.suffix+".partial")
    if path.exists() or partial.exists():raise ForwardCollectorError("existing artifact rejected")
    with partial.open("xb") as handle:handle.write(payload);handle.flush();os.fsync(handle.fileno())
    os.rename(partial,path)


@dataclass(frozen=True)
class ForwardSession:
    root:str
    session_date:str
    ticker:str
    contract_id:str
    active_intervals:tuple[tuple[datetime,datetime],...]
    schedule_source_id:str
    schedule_version:str
    rollover_pair_id:str|None=None
    rollover_leg:str="ACTIVE"

    def __post_init__(self):
        if self.root not in ROOTS or not self.ticker.startswith(self.root):raise ForwardCollectorError("root or ticker rejected")
        if self.rollover_leg not in ("ACTIVE","OUTGOING","INCOMING"):raise ForwardCollectorError("rollover leg rejected")
        if (self.rollover_leg=="ACTIVE")!=(self.rollover_pair_id is None):raise ForwardCollectorError("rollover pair boundary rejected")
        if any(not start.tzinfo or not end.tzinfo or start>=end for start,end in self.active_intervals):raise ForwardCollectorError("schedule interval rejected")
        for (_,end),(next_start,_) in zip(self.active_intervals,self.active_intervals[1:]):
            if end>next_start:raise ForwardCollectorError("schedule overlap rejected")

    @property
    def close(self)->datetime:return self.active_intervals[-1][1].astimezone(timezone.utc)

    def eligible_at(self,*,safety_buffer:timedelta=DEFAULT_SAFETY_BUFFER)->datetime:
        if safety_buffer<timedelta(0):raise ForwardCollectorError("negative safety buffer")
        return self.close+RECENCY_DELAY+safety_buffer


@dataclass(frozen=True)
class RolloverVolumeFact:
    root:str;pair_id:str;session_date:str;outgoing_ticker:str;incoming_ticker:str
    outgoing_volume:Decimal;incoming_volume:Decimal;finalized_at:datetime


def rollover_decision(facts:tuple[RolloverVolumeFact,...],next_session:Callable[[str],str])->dict|None:
    ordered=sorted(facts,key=lambda x:x.session_date);streak=0
    for fact in ordered:
        if not fact.finalized_at.tzinfo:raise ForwardCollectorError("rollover fact timestamp is naive")
        streak=streak+1 if fact.incoming_volume>fact.outgoing_volume else 0
        if streak==2:
            effective=next_session(fact.session_date)
            if not effective or effective<=fact.session_date:raise ForwardCollectorError("rollover next session invalid")
            evidence=ordered[ordered.index(fact)-1:ordered.index(fact)+1]
            return {"id":sha256("|".join(["FORWARD_TWO_SESSION_V1",fact.pair_id,effective,*[x.session_date for x in evidence]]).encode()).hexdigest(),
                "root":fact.root,"pair_id":fact.pair_id,"decision_session":fact.session_date,"effective_session":effective,
                "outgoing_ticker":fact.outgoing_ticker,"incoming_ticker":fact.incoming_ticker,
                "method":"TWO_CONSECUTIVE_FINALIZED_VOLUME_CROSSOVER_SPARSE_ZERO","no_lookahead":True}
    return None


class ForwardStore:
    def __init__(self,repository:Path,run_id:str):
        self.repository=repository.resolve();self.root=self.repository/"data/futures_forward";self.reports=self.repository/"outputs/futures_forward"
        self.stop=self.repository/"data/futures_forward.stop";self.lock=self.repository/"data/futures_forward.lock";self.run_id=run_id
        forbidden=(self.repository/"data/backtests/btc_forward_archive_2").resolve()
        if self.root==forbidden or forbidden in self.root.parents:raise ForwardCollectorError("BTC path boundary conflict")

    def acquire(self):
        self.lock.parent.mkdir(parents=True,exist_ok=True)
        try:
            with self.lock.open("x") as handle:handle.write(self.run_id)
        except FileExistsError:raise ForwardCollectorError("collector overlap rejected") from None

    def release(self):
        if self.lock.exists() and self.lock.read_text()==self.run_id:self.lock.unlink()

    def complete(self,session:ForwardSession)->bool:
        checkpoint=self.root/session.root/"checkpoints"/(session.session_date+"-"+session.ticker+".json")
        if not checkpoint.exists():return False
        value=json.loads(checkpoint.read_text());manifest=self.root/session.root/value["manifest_relative_path"]
        if value["root"]!=session.root or value["ticker"]!=session.ticker or not manifest.exists() or _hash(manifest)!=value["manifest_sha256"]:raise ForwardCollectorError("checkpoint conflict")
        item=json.loads(manifest.read_text())
        for field,hash_field in (("raw_relative_path","raw_sha256"),("normalized_relative_path","normalized_sha256")):
            path=self.root/session.root/item[field]
            if not path.exists() or _hash(path)!=item[hash_field]:raise ForwardCollectorError("verified session checksum conflict")
        return True

    def totals(self)->dict:
        raw=sum(x.stat().st_size for x in self.root.glob("*/raw/*.json"));normalized=sum(x.stat().st_size for x in self.root.glob("*/normalized/*.jsonl"))
        return {"raw":raw,"normalized":normalized,"combined":raw+normalized}

    def retain(self,session:ForwardSession,raw:bytes,status:int,provider_request_id:str|None):
        if self.complete(session):raise ForwardCollectorError("verified session overwrite rejected")
        base=self.root/session.root;name=f"{session.session_date}-{session.ticker}"
        raw_path=base/"raw"/(name+".json")
        _atomic(raw_path,raw)
        _atomic(base/"pending"/(name+".json"),_bytes({"schema_version":SCHEMA_VERSION,"run_id":self.run_id,"root":session.root,
            "session_date":session.session_date,"ticker":session.ticker,"contract_id":session.contract_id,"http_status":status,
            "provider_request_id":provider_request_id,"raw_relative_path":"raw/"+raw_path.name,"raw_sha256":sha256(raw).hexdigest(),"raw_bytes":len(raw),"automatic_retry":False}))

    def commit(self,session:ForwardSession,normalized:bytes,rows:int,maximum_rows:int):
        base=self.root/session.root;name=f"{session.session_date}-{session.ticker}";pending_path=base/"pending"/(name+".json")
        raw_path=base/"raw"/(name+".json")
        if not pending_path.exists() or not raw_path.exists():raise ForwardCollectorError("raw-first transaction missing")
        pending=json.loads(pending_path.read_text());raw=raw_path.read_bytes()
        if pending["ticker"]!=session.ticker or pending["contract_id"]!=session.contract_id or _hash(raw_path)!=pending["raw_sha256"]:raise ForwardCollectorError("raw-first transaction conflict")
        normalized_path=base/"normalized"/(name+".jsonl")
        _atomic(normalized_path,normalized)
        manifest={**pending,"schedule_source_id":session.schedule_source_id,"schedule_version":session.schedule_version,
            "normalized_relative_path":"normalized/"+normalized_path.name,"normalized_sha256":sha256(normalized).hexdigest(),
            "normalized_bytes":len(normalized),"normalized_rows":rows,"missing_aggregate_minutes":maximum_rows-rows,
            "missing_semantics":"ZERO_OBSERVED_ELIGIBLE_TRADE_VOLUME_NO_OHLC","automatic_retry":False,
            "rollover_pair_id":session.rollover_pair_id,"rollover_leg":session.rollover_leg,
            "observed_volume":str(sum((Decimal(json.loads(line)["volume"]) for line in normalized.decode().splitlines()),Decimal(0)))}
        manifest_path=base/"manifests"/(name+".json");_atomic(manifest_path,_bytes(manifest))
        _atomic(base/"checkpoints"/(session.session_date+"-"+session.ticker+".json"),_bytes({"schema_version":SCHEMA_VERSION,"root":session.root,
            "ticker":session.ticker,"session_date":session.session_date,"manifest_relative_path":"manifests/"+manifest_path.name,
            "manifest_sha256":_hash(manifest_path)}))


class DelayedDailyCollector:
    def __init__(self,repository:Path,sessions:tuple[ForwardSession,...],transport:Callable,*,safety_buffer:timedelta=DEFAULT_SAFETY_BUFFER,
                 sleep:Callable=time.sleep,clock:Callable=lambda:datetime.now(timezone.utc)):
        self.repository=repository.resolve();self.sessions=sessions;self.transport=transport;self.safety_buffer=safety_buffer;self.sleep=sleep;self.clock=clock

    def run(self,key:str,*,configuration:dict|None=None,reference_refresher=None,configuration_path:Path|None=None,configuration_manifest_path:Path|None=None)->dict:
        started=self.clock().astimezone(timezone.utc);run_id=sha256((SCHEMA_VERSION+"|"+started.isoformat()).encode()).hexdigest();store=ForwardStore(self.repository,run_id);store.acquire()
        calls=rows=raw_bytes=normalized_bytes=0
        try:
            if not key: raise ForwardCollectorError("credential presence rejected")
            if configuration is not None:
                from futures_data.validate_forward_configuration import validate_configuration
                configuration_path=configuration_path or self.repository/"config/es_nq_forward_sessions.json"
                validated=validate_configuration(configuration_path,repository=self.repository,manifest_path=configuration_manifest_path)
                if tuple(validated)!=tuple(self.sessions): raise ForwardCollectorError("configuration/session handoff rejected")
            run_sessions=tuple(self.sessions)
            if reference_refresher is not None and configuration is not None:
                refreshed=reference_refresher.run(configuration,key,started)
                if refreshed["state"]=="REFRESH_VALIDATED":
                    from futures_data.forward_reference_refresh import publish_successor
                    path,manifest=publish_successor(self.repository,refreshed["configuration"])
                    run_sessions=validate_configuration(path,repository=self.repository,manifest_path=manifest)
            eligible=sorted((x for x in run_sessions if x.eligible_at(safety_buffer=self.safety_buffer)<=started),key=lambda x:(x.session_date,x.root,x.ticker))
            for session in eligible:
                if store.stop.exists():raise ForwardCollectorError("owner stop requested")
                if store.complete(session):continue
                if calls>=RUN_REQUEST_CAP:raise ForwardCollectorError("per-run request cap exceeded")
                if calls:self.sleep(MIN_REQUEST_INTERVAL)
                status,raw,provider_id=self.transport(session,key);calls+=1
                if status!=200:raise ForwardCollectorError("provider response rejected")
                cumulative=store.totals()
                if (raw_bytes+len(raw)>RUN_RAW_CAP or raw_bytes+normalized_bytes+len(raw)>RUN_COMBINED_CAP or
                    cumulative["raw"]+len(raw)>CUMULATIVE_RAW_CAP or cumulative["combined"]+len(raw)>CUMULATIVE_COMBINED_CAP):raise ForwardCollectorError("collector cap exceeded")
                store.retain(session,raw,status,provider_id)
                maximum=sum(int((end-start).total_seconds()/60) for start,end in session.active_intervals)
                request={"id":run_id,"root":session.root,"contract_id":session.contract_id,"ticker":session.ticker,"sessions":[session.session_date],
                    "maximum_rows":maximum,"plan_id":run_id}
                calendar={"sessions":[{"session_date":session.session_date,"active_intervals":[{"start_utc":start.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),
                    "end_exclusive_utc":end.astimezone(timezone.utc).isoformat().replace("+00:00","Z")} for start,end in session.active_intervals]}]}
                normalized,count,_=canonical._normalize(raw,request,calendar)
                projected_rows=rows+count;projected_raw=raw_bytes+len(raw);projected_norm=normalized_bytes+len(normalized)
                cumulative=store.totals()
                if (projected_rows>RUN_ROW_CAP or projected_norm>RUN_NORMALIZED_CAP or projected_raw+projected_norm>RUN_COMBINED_CAP or
                    cumulative["normalized"]+len(normalized)>CUMULATIVE_NORMALIZED_CAP or cumulative["combined"]+len(normalized)>CUMULATIVE_COMBINED_CAP):raise ForwardCollectorError("collector cap exceeded")
                store.commit(session,normalized,count,maximum);rows=projected_rows;raw_bytes=projected_raw;normalized_bytes=projected_norm
            self._update_rollovers(store,eligible)
            horizon=max((x.eligible_at(safety_buffer=self.safety_buffer) for x in self.sessions),default=None)
            state="STALE_SCHEDULE" if horizon is None or started>horizon else "HEALTHY"
            report={"schema_version":SCHEMA_VERSION,"run_id":run_id,"state":state,"schedule_horizon":horizon.isoformat() if horizon else None,
                "alert_required":state!="HEALTHY","eligible_sessions":len(eligible),"network_calls":calls,
                "rows":rows,"raw_bytes":raw_bytes,"normalized_bytes":normalized_bytes,"automatic_retry":False,"trading":False,"recorder_control":False}
            _atomic(store.reports/("run-"+started.strftime("%Y%m%dT%H%M%SZ")+".json"),_bytes(report));return report
        finally:store.release()

    def _update_rollovers(self,store:ForwardStore,sessions:list[ForwardSession]):
        pairs=sorted({x.rollover_pair_id for x in sessions if x.rollover_pair_id})
        dates=sorted({x.session_date for x in sessions})
        for pair_id in pairs:
            relevant=[x for x in sessions if x.rollover_pair_id==pair_id];facts=[]
            for day in sorted({x.session_date for x in relevant}):
                legs={x.rollover_leg:x for x in relevant if x.session_date==day}
                if set(legs)!={"OUTGOING","INCOMING"}:raise ForwardCollectorError("rollover legs incomplete")
                manifests={leg:json.loads((store.root/item.root/"manifests"/(item.session_date+"-"+item.ticker+".json")).read_text()) for leg,item in legs.items()}
                facts.append(RolloverVolumeFact(legs["OUTGOING"].root,pair_id,day,legs["OUTGOING"].ticker,legs["INCOMING"].ticker,
                    Decimal(manifests["OUTGOING"]["observed_volume"]),Decimal(manifests["INCOMING"]["observed_volume"]),legs["OUTGOING"].close))
            decision=rollover_decision(tuple(facts),lambda day:next((value for value in dates if value>day),""))
            if decision:
                path=store.root/decision["root"]/"rollovers"/(decision["id"]+".json")
                if path.exists() and json.loads(path.read_text())!=decision:raise ForwardCollectorError("rollover decision conflict")
                if not path.exists():_atomic(path,_bytes(decision))


def main(argv=None)->int:
    # When executed with ``python -m``, the package-qualified refresh module
    # imports its own collector module identity.  Catch that exact typed error
    # as well as the ``__main__`` identity so failures remain sanitized.
    from futures_data.forward_reference_refresh import ForwardCollectorError as ReferenceRefreshError
    parser=argparse.ArgumentParser(description="Delayed ES/NQ public research-data collector; trading disabled")
    parser.add_argument("--repository",type=Path,required=True);parser.add_argument("--sessions",type=Path,required=True);parser.add_argument("--run",action="store_true")
    args=parser.parse_args(argv);key=sys.stdin.readline().rstrip("\r\n")
    try:
        if not args.run:raise ForwardCollectorError("explicit run mode required")
        from futures_data.validate_forward_configuration import validate_configuration
        from futures_data.forward_reference_refresh import resolve_current
        configuration_path,configuration_manifest=resolve_current(args.repository.resolve(),args.sessions.resolve())
        payload=json.loads(configuration_path.read_text(encoding="utf-8"));sessions=list(validate_configuration(configuration_path,repository=args.repository.resolve(),manifest_path=configuration_manifest))
        def transport(session:ForwardSession,credential:str):
            request={"ticker":session.ticker,"start_utc":session.active_intervals[0][0].astimezone(timezone.utc).isoformat().replace("+00:00","Z"),
                "end_utc":session.active_intervals[-1][1].astimezone(timezone.utc).isoformat().replace("+00:00","Z")}
            return canonical._fetch(request,credential)
        from futures_data.forward_reference_refresh import ReferenceRefresher,default_fetcher
        refresher=ReferenceRefresher(args.repository.resolve(),default_fetcher(payload))
        result=DelayedDailyCollector(args.repository.resolve(),tuple(sessions),transport).run(key,configuration=payload,reference_refresher=refresher,
            configuration_path=configuration_path,configuration_manifest_path=configuration_manifest);print(json.dumps(result,sort_keys=True));return 0
    except (ForwardCollectorError,ReferenceRefreshError,canonical.PassBError,
            ValueError,KeyError,json.JSONDecodeError,urllib.error.URLError) as error:
        directory=args.repository.resolve()/"outputs/futures_forward/diagnostics";name="diagnostic-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json"
        _atomic(directory/name,_bytes({"schema_version":SCHEMA_VERSION,"failure_phase":"DELAYED_FORWARD","exception_class":type(error).__name__,"sanitized_message":str(error)[:160]}))
        print("BLOCKED: delayed ES/NQ collector failed closed; see local sanitized diagnostic",file=sys.stderr);return 2
    finally:key=""


if __name__=="__main__":raise SystemExit(main())
