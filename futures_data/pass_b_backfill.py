from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

SCHEMA_VERSION = "es-nq-pass-b-backfill-v3"
CALENDAR_VERSION = "MASSIVE_SCHEDULE_EVENTS_20260826_V2"
ROLLOVER_VERSION = "OWNER_TWO_SESSION_VOLUME_CROSSOVER_SPARSE_V2"
PLAN_DIR = "es_nq_pass_b_plan_3"
STAGING_DIR = "es_nq_pass_b_staging_3"
ARCHIVE_DIR = "es_nq_pass_b_archive_3"
ROOTS = ("ES", "NQ")
CHICAGO = ZoneInfo("America/Chicago")
OUTRIGHT_NAMES = {
    "ES": ("E-mini S&P 500 Futures", "E-mini Standard and Poor's 500 Stock Price Index Futures"),
    "NQ": ("E-mini Nasdaq-100 Futures", "E-mini Nasdaq-100 Index Futures"),
}
MAX_REQUESTS = 130
MAX_ROWS = 1_000_000
MAX_RAW_BYTES = 300 * 1024 * 1024
MAX_NORMALIZED_BYTES = 300 * 1024 * 1024
MAX_COMBINED_BYTES = 650 * 1024 * 1024
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
MIN_CALL_INTERVAL_SECONDS = 15.0
SECRET = re.compile(r"(?i)(authorization|bearer\s+|api[_-]?key|credential|secret)")
BASE_URL = "https://api.massive.com"
ALLOWED_HOST = "api.massive.com"


class PassBError(RuntimeError):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, default=str) + "\n").encode("utf-8")


def _identity(*parts: object) -> str:
    return sha256("|".join(str(x) for x in parts).encode()).hexdigest()


def _atomic_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() or partial.exists():
        raise PassBError("existing path rejected")
    with partial.open("xb") as handle:
        handle.write(payload); handle.flush(); os.fsync(handle.fileno())
    os.rename(partial, path)


def _schedule_evidence(repository: Path) -> tuple[dict, list[str]]:
    base = repository / "data/backtests/es_nq_schedule_verification_2"
    streams, hashes = {}, []
    for root in ROOTS:
        records = []
        for manifest_path in sorted((base / root / "manifests").glob("*.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw_path = base / root / manifest["raw_relative_path"]
            raw = raw_path.read_bytes(); digest = sha256(raw).hexdigest()
            if digest != manifest["raw_sha256"] or manifest.get("http_status") != 200:
                raise PassBError("schedule evidence checksum or status conflict")
            hashes.extend((digest, sha256(manifest_path.read_bytes()).hexdigest()))
            payload = json.loads(raw.decode("utf-8"))
            for item in payload.get("results", []):
                if item.get("product_code") == root and item.get("product_name") in OUTRIGHT_NAMES[root]:
                    stamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)
                    records.append({"session_date": item["session_end_date"], "event": item["event"],
                                    "timestamp": stamp.isoformat().replace("+00:00", "Z"),
                                    "venue": item["trading_venue"], "product_name": item["product_name"]})
        key = lambda x: (x["session_date"], x["timestamp"], x["event"])
        if not records or len({key(x) for x in records}) != len(records) or any(x["venue"] != "XCME" for x in records):
            raise PassBError("outright schedule identity conflict")
        streams[root] = sorted(records, key=key)
    canonical = lambda rows: [(x["session_date"], x["event"], x["timestamp"], x["venue"]) for x in rows]
    if canonical(streams["ES"]) != canonical(streams["NQ"]):
        raise PassBError("ES and NQ schedule conflict")
    return streams, sorted(set(hashes))


def _build_calendar(streams: dict) -> dict:
    sessions = []
    by_date = {}
    for event in streams["ES"]:
        by_date.setdefault(event["session_date"], []).append(event)
    for session_date, events in sorted(by_date.items()):
        active_start = None; intervals = []
        for event in sorted(events, key=lambda x: x["timestamp"]):
            stamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            if event["event"] == "open":
                if active_start is not None: raise PassBError("schedule opens while active")
                active_start = stamp
            elif event["event"] in ("pre_open", "close"):
                if active_start is not None:
                    if stamp <= active_start: raise PassBError("schedule interval geometry invalid")
                    intervals.append((active_start, stamp)); active_start = None
            else:
                raise PassBError("unknown schedule event")
        if active_start is not None or not intervals:
            raise PassBError("schedule session incomplete")
        ordinary_close = datetime.fromisoformat(session_date).replace(tzinfo=CHICAGO, hour=16)
        final_close = intervals[-1][1].astimezone(CHICAGO)
        sessions.append({"session_date": session_date,
            "events": [{"event": x["event"], "timestamp_utc": x["timestamp"],
                        "timestamp_chicago": datetime.fromisoformat(x["timestamp"].replace("Z", "+00:00")).astimezone(CHICAGO).isoformat()}
                       for x in sorted(events, key=lambda x: x["timestamp"])],
            "active_intervals": [{"start_utc": a.isoformat().replace("+00:00", "Z"),
                                  "end_exclusive_utc": b.isoformat().replace("+00:00", "Z"),
                                  "start_chicago": a.astimezone(CHICAGO).isoformat(),
                                  "end_exclusive_chicago": b.astimezone(CHICAGO).isoformat()}
                                 for a, b in intervals],
            "early_or_special": final_close.time() != ordinary_close.time() or len(intervals) != 1})
    represented = {date.fromisoformat(x["session_date"]) for x in sessions}
    cursor, excluded = date(2025, 6, 1), []
    while cursor <= date(2026, 8, 26):
        if cursor not in represented:
            excluded.append({"date": cursor.isoformat(), "reason": "WEEKEND" if cursor.weekday() >= 5 else "PROVIDER_VERIFIED_NO_SESSION_EVENTS"})
        cursor += timedelta(days=1)
    return {"schema_version": SCHEMA_VERSION, "calendar_version": CALENDAR_VERSION,
            "timezone": "America/Chicago", "utc_required": True, "sessions": sessions,
            "represented_session_dates": len(sessions), "excluded_dates": excluded}


def _active_minutes(session: dict) -> set[int]:
    values = set()
    for interval in session["active_intervals"]:
        start = datetime.fromisoformat(interval["start_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(interval["end_exclusive_utc"].replace("Z", "+00:00"))
        cursor = int(start.timestamp() // 60)
        while cursor < int(end.timestamp() // 60): values.add(cursor); cursor += 1
    return values


def _revalidate_rollovers(repository: Path, calendar: dict) -> dict:
    old_plan = json.loads((repository / "data/backtests/es_nq_rollover_discovery_plan_3/plan.json").read_text())
    old_result = repository / "data/backtests/es_nq_rollover_discovery_1"
    session_map = {x["session_date"]: x for x in calendar["sessions"]}
    markets = {}
    for root in ROOTS:
        facts = []
        for manifest_path in sorted((old_result / root / "manifests").glob("*.json")):
            manifest = json.loads(manifest_path.read_text()); raw_path = old_result / root / manifest["raw_relative_path"]
            raw = raw_path.read_bytes()
            if sha256(raw).hexdigest() != manifest["raw_sha256"]: raise PassBError("Pass A raw checksum conflict")
            payload = json.loads(raw.decode())
            by_session = {}
            for row in payload.get("results", []):
                by_session.setdefault(row["session_end_date"], []).append(row)
            pair = next(x for x in old_plan["markets"][root]["pairs"] if manifest["request_id"] in x["request_ids"])
            contract_id = pair["outgoing_id"] if manifest["ticker"] == pair["outgoing_ticker"] else pair["incoming_id"]
            for session_date in pair["sessions"]:
                if session_date not in session_map: raise PassBError("rollover session absent from verified calendar")
                expected = _active_minutes(session_map[session_date]); rows = by_session.get(session_date, [])
                observed = {int(Decimal(str(x["window_start"])) // Decimal(60_000_000_000)) for x in rows}
                if not observed <= expected: raise PassBError("Pass A bar outside verified session")
                missing = expected - observed
                volume = sum((Decimal(str(x["volume"])) for x in rows), Decimal(0))
                fact_id = _identity(ROLLOVER_VERSION, pair["id"], contract_id, session_date, volume, len(missing))
                facts.append({"id": fact_id, "pair_id": pair["id"], "contract_id": contract_id,
                              "ticker": manifest["ticker"], "session": session_date, "volume": str(volume),
                              "missing_aggregate_minutes": len(missing), "missing_semantics": "ZERO_OBSERVED_ELIGIBLE_TRADE_VOLUME_NO_OHLC",
                              "source_request_id": manifest["request_id"]})
        decisions = []
        for pair in old_plan["markets"][root]["pairs"]:
            relevant = [x for x in facts if x["pair_id"] == pair["id"]]
            by = {(x["session"], x["contract_id"]): x for x in relevant}; streak = 0; decision = None
            for index, session_date in enumerate(pair["sessions"]):
                outgoing, incoming = by.get((session_date, pair["outgoing_id"])), by.get((session_date, pair["incoming_id"]))
                if outgoing is None or incoming is None: raise PassBError("rollover daily evidence incomplete")
                streak = streak + 1 if Decimal(incoming["volume"]) > Decimal(outgoing["volume"]) else 0
                if streak == 2:
                    effective = pair["sessions"][index + 1] if index + 1 < len(pair["sessions"]) else None
                    if effective is None: raise PassBError("crossover lacks next session")
                    evidence = [by[(pair["sessions"][index-1], pair["outgoing_id"])], by[(pair["sessions"][index-1], pair["incoming_id"])], outgoing, incoming]
                    decision = {"id": _identity(ROLLOVER_VERSION, pair["id"], session_date, effective, *(x["id"] for x in evidence)),
                                "pair_id": pair["id"], "root": root, "outgoing_id": pair["outgoing_id"],
                                "incoming_id": pair["incoming_id"], "decision_session": session_date,
                                "decision_time": session_map[session_date]["active_intervals"][-1]["end_exclusive_utc"],
                                "effective_session": effective, "method": "TWO_CONSECUTIVE_FINALIZED_VOLUME_CROSSOVER_SPARSE_ZERO",
                                "evidence": evidence, "no_lookahead": True}; break
            if decision is None:
                fallback_session = pair["sessions"][-2]; effective = pair["sessions"][-1]
                decision = {"id": _identity(ROLLOVER_VERSION, pair["id"], fallback_session, effective, "fallback"),
                            "pair_id": pair["id"], "root": root, "outgoing_id": pair["outgoing_id"],
                            "incoming_id": pair["incoming_id"], "decision_session": fallback_session,
                            "decision_time": session_map[fallback_session]["active_intervals"][-1]["end_exclusive_utc"],
                            "effective_session": effective, "method": "FROZEN_CALENDAR_FALLBACK", "evidence": [], "no_lookahead": True}
            decisions.append(decision)
        contracts = old_plan["markets"][root]["contracts"]; windows=[]; cursor="2025-06-01"
        for index, contract in enumerate(contracts):
            end = decisions[index]["effective_session"] if index < len(decisions) else "2026-08-27"
            windows.append({"contract_id": contract["id"], "ticker": contract["ticker"], "start": cursor, "end_exclusive": end,
                            "roll_decision_id": decisions[index]["id"] if index < len(decisions) else None}); cursor=end
        markets[root] = {"facts": facts, "decisions": decisions, "active_windows": windows}
    return {"schema_version": SCHEMA_VERSION, "rollover_version": ROLLOVER_VERSION, "markets": markets}


def build_plan(repository: Path) -> dict:
    streams, schedule_hashes = _schedule_evidence(repository); calendar = _build_calendar(streams)
    rollovers = _revalidate_rollovers(repository, calendar); session_map = {x["session_date"]: x for x in calendar["sessions"]}
    markets={}; total_requests=total_rows=0
    for root in ROOTS:
        requests=[]
        for window in rollovers["markets"][root]["active_windows"]:
            eligible=[x for x in calendar["sessions"] if window["start"] <= x["session_date"] < window["end_exclusive"]]
            for offset in range(0,len(eligible),5):
                chunk=eligible[offset:offset+5]; rows=sum(len(_active_minutes(x)) for x in chunk)
                request_id=_identity(SCHEMA_VERSION,root,window["contract_id"],*(x["session_date"] for x in chunk))
                requests.append({"id":request_id,"root":root,"contract_id":window["contract_id"],"ticker":window["ticker"],
                    "sessions":[x["session_date"] for x in chunk],"start_utc":chunk[0]["active_intervals"][0]["start_utc"],
                    "end_utc":chunk[-1]["active_intervals"][-1]["end_exclusive_utc"],"maximum_rows":rows})
        markets[root]={"requests":requests,"request_count":len(requests),"estimated_rows":sum(x["maximum_rows"] for x in requests)}
        total_requests+=len(requests);total_rows+=markets[root]["estimated_rows"]
    if total_requests>MAX_REQUESTS or total_rows>MAX_ROWS: raise PassBError("frozen plan exceeds owner cap")
    body={"schema_version":SCHEMA_VERSION,"calendar_version":CALENDAR_VERSION,"rollover_version":ROLLOVER_VERSION,
          "source_schedule_sha256":schedule_hashes,"source_pass_a_plan_id":json.loads((repository/"data/backtests/es_nq_rollover_discovery_plan_3/plan.json").read_text())["id"],
          "calendar":calendar,"rollovers":rollovers,"markets":markets,"caps":{"requests":MAX_REQUESTS,"rows":MAX_ROWS,
          "raw_bytes":MAX_RAW_BYTES,"normalized_bytes":MAX_NORMALIZED_BYTES,"combined_bytes":MAX_COMBINED_BYTES,
          "response_bytes":MAX_RESPONSE_BYTES},
          "estimated":{"requests":total_requests,"rows":total_rows,"minimum_runtime_minutes":(total_requests+3)//4},
          "unsupported_interval":{"start":"2024-08-25","end_exclusive":"2025-06-01"},"execution_authorized":False}
    body["id"]=_identity(_json_bytes(body)); target=repository/"data/backtests"/PLAN_DIR
    if target.exists(): raise PassBError("versioned plan already exists")
    _atomic_new(target/"calendar.json",_json_bytes(calendar));_atomic_new(target/"rollovers.json",_json_bytes(rollovers))
    _atomic_new(target/"plan.json",_json_bytes(body))
    hashes={name:sha256((target/name).read_bytes()).hexdigest() for name in ("calendar.json","rollovers.json","plan.json")}
    _atomic_new(target/"artifact_manifest.json",_json_bytes({"schema_version":SCHEMA_VERSION,"plan_id":body["id"],"sha256":hashes}))
    return body


class PassBStore:
    def __init__(self, repository: Path, plan: dict):
        self.stage=repository/"data/backtests"/STAGING_DIR;self.archive=repository/"data/backtests"/ARCHIVE_DIR;self.plan=plan
        self.stop=repository/"data/backtests/es_nq_pass_b.stop"
    def totals(self)->dict:
        pending=[json.loads(x.read_text()) for x in self.stage.glob("*/pending/*.json")]
        manifests=[json.loads(x.read_text()) for x in self.stage.glob("*/manifests/*.json")]
        return {"requests":len(pending),"rows":sum(x["normalized_rows"] for x in manifests),
                "raw":sum(x["raw_bytes"] for x in pending),"normalized":sum(x["normalized_bytes"] for x in manifests)}
    def complete(self,root:str,request:dict)->bool:
        path=self.stage/root/"manifests"/(request["id"]+".json")
        if not path.exists():return False
        m=json.loads(path.read_text());
        if m["plan_id"]!=self.plan["id"] or m["request_id"]!=request["id"]:raise PassBError("plan-ID mismatch")
        for field,hash_field in (("raw_relative_path","raw_sha256"),("normalized_relative_path","normalized_sha256")):
            p=self.stage/root/m[field]
            if not p.exists() or sha256(p.read_bytes()).hexdigest()!=m[hash_field]:raise PassBError("checkpoint checksum conflict")
        checkpoint=self.stage/root/"checkpoints"/(request["id"]+".json")
        if not checkpoint.exists():raise PassBError("checkpoint missing")
        value=json.loads(checkpoint.read_text())
        if value.get("plan_id")!=self.plan["id"] or value.get("request_id")!=request["id"] or value.get("manifest_sha256")!=sha256(path.read_bytes()).hexdigest():raise PassBError("checkpoint checksum conflict")
        return True
    def retained(self,root:str,request:dict):
        raw=self.stage/root/"raw"/(request["id"]+".json");pending=self.stage/root/"pending"/(request["id"]+".json")
        if not raw.exists() and not pending.exists():return None
        if not raw.exists() or not pending.exists():raise PassBError("incomplete raw-first transaction")
        p=json.loads(pending.read_text());data=raw.read_bytes()
        if p["plan_id"]!=self.plan["id"] or sha256(data).hexdigest()!=p["raw_sha256"]:raise PassBError("raw-first conflict")
        return data,p
    def retain(self,root:str,request:dict,raw:bytes,status:int,request_id:str|None):
        if self.stop.exists():raise PassBError("owner stop requested")
        if len(raw)>MAX_RESPONSE_BYTES:raise PassBError("response cap exceeded")
        projected=self.totals();projected["raw"]+=len(raw)
        if (projected["requests"]+1>MAX_REQUESTS or projected["raw"]>MAX_RAW_BYTES or
                projected["raw"]+projected["normalized"]>MAX_COMBINED_BYTES):
            raise PassBError("cumulative cap exceeded")
        path=self.stage/root/"raw"/(request["id"]+".json");_atomic_new(path,raw)
        _atomic_new(self.stage/root/"pending"/(request["id"]+".json"),_json_bytes({"schema_version":SCHEMA_VERSION,"plan_id":self.plan["id"],
            "request_id":request["id"],"root":root,"http_status":status,"provider_request_id":request_id,
            "raw_sha256":sha256(raw).hexdigest(),"raw_bytes":len(raw),"automatic_retry":False,"aggregate_endpoint":True}))
    def commit(self,root:str,request:dict,normalized:bytes,rows:int,reconciliation:dict|None=None):
        retained=self.retained(root,request)
        if retained is None:raise PassBError("raw-first transaction missing")
        raw,pending=retained; totals=self.totals();combined=totals["raw"]+totals["normalized"]+len(normalized)
        if totals["rows"]+rows>MAX_ROWS or totals["normalized"]+len(normalized)>MAX_NORMALIZED_BYTES or combined>MAX_COMBINED_BYTES:raise PassBError("cumulative cap exceeded")
        norm=self.stage/root/"normalized"/(request["id"]+".jsonl");_atomic_new(norm,normalized)
        manifest={**pending,"normalized_rows":rows,"normalized_bytes":len(normalized),"normalized_sha256":sha256(normalized).hexdigest(),
                  "expected_maximum_rows":request["maximum_rows"],"missing_aggregate_minutes":request["maximum_rows"]-rows,
                  "raw_relative_path":"raw/"+request["id"]+".json","normalized_relative_path":"normalized/"+request["id"]+".jsonl",
                  "ticker":request["ticker"],"contract_id":request["contract_id"],
                  "session_reconciliation":reconciliation or {"policy":"STRICT_SESSION_TIMESTAMP_PAIR_V1","excluded_provider_duplicates":0}}
        mp=self.stage/root/"manifests"/(request["id"]+".json");_atomic_new(mp,_json_bytes(manifest))
        _atomic_new(self.stage/root/"checkpoints"/(request["id"]+".json"),_json_bytes({"plan_id":self.plan["id"],"request_id":request["id"],"manifest_sha256":sha256(mp.read_bytes()).hexdigest()}))
    def promote(self):
        if self.archive.exists() or not self.stage.exists():raise PassBError("promotion boundary invalid")
        os.rename(self.stage,self.archive)


def _normalize(raw:bytes,request:dict,calendar:dict)->tuple[bytes,int,dict]:
    payload=json.loads(raw.decode("utf-8"),parse_float=Decimal)
    if not isinstance(payload,dict) or not isinstance(payload.get("results"),list) or payload.get("next_url") is not None:raise PassBError("schema or pagination anomaly")
    sessions={x["session_date"]:x for x in calendar["sessions"] if x["session_date"] in request["sessions"]}
    minutes_by_session={name:_active_minutes(value) for name,value in sessions.items()}
    canonical_by_minute={}
    for name,minutes in minutes_by_session.items():
        for minute in minutes:
            if minute in canonical_by_minute:raise PassBError("verified calendar session overlap")
            canonical_by_minute[minute]=name
    grouped={}
    for row in payload["results"]:
        if row.get("ticker")!=request["ticker"] or row.get("session_end_date") not in sessions:raise PassBError("wrong-contract or session row")
        stamp=int(Decimal(str(row["window_start"]))//Decimal(60_000_000_000))
        if stamp not in canonical_by_minute:raise PassBError("unexpected boundary row")
        grouped.setdefault(stamp,[]).append(row)
    output=[];excluded=0
    for stamp,rows in sorted(grouped.items()):
        canonical_session=canonical_by_minute[stamp]
        matching=[row for row in rows if row["session_end_date"]==canonical_session]
        if len(matching)!=1:raise PassBError("session-boundary mismatch")
        row=matching[0]
        economic={key:value for key,value in row.items() if key!="session_end_date"}
        for duplicate in rows:
            if duplicate is row:continue
            if {key:value for key,value in duplicate.items() if key!="session_end_date"}!=economic:
                raise PassBError("conflicting duplicate row")
            excluded+=1
        try:
            values={name:Decimal(str(row[name])) for name in ("open","high","low","close","volume")}
        except (KeyError,InvalidOperation) as exc:raise PassBError("economic schema invalid") from exc
        if values["high"]<max(values["open"],values["close"]) or values["low"]>min(values["open"],values["close"]) or values["volume"]<0:raise PassBError("OHLCV invalid")
        output.append({"schema_version":SCHEMA_VERSION,"plan_id":request.get("plan_id"),"root":request["root"],"contract_id":request["contract_id"],
                       "ticker":request["ticker"],"session_date":row["session_end_date"],"window_start_ns":int(row["window_start"]),
                       **{k:str(v) for k,v in values.items()}})
    output.sort(key=lambda x:x["window_start_ns"])
    return (("\n".join(json.dumps(x,sort_keys=True,separators=(",",":")) for x in output)+("\n" if output else "")).encode(),len(output),
            {"policy":"STRICT_SESSION_TIMESTAMP_PAIR_V1","excluded_provider_duplicates":excluded})


def _fetch(request:dict,key:str):
    query={"resolution":"1min","window_start.gte":str(int(datetime.fromisoformat(request["start_utc"].replace("Z","+00:00")).timestamp()*1_000_000_000)),
           "window_start.lt":str(int(datetime.fromisoformat(request["end_utc"].replace("Z","+00:00")).timestamp()*1_000_000_000)),"limit":"10000","sort":"window_start.asc"}
    url=BASE_URL+"/futures/v1/aggs/"+urllib.parse.quote(request["ticker"],safe="")+"?"+urllib.parse.urlencode(query)
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!="https" or parsed.hostname!=ALLOWED_HOST or SECRET.search(parsed.query):raise PassBError("request boundary invalid")
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=30,context=ssl.create_default_context()) as response:
            return response.status,response.read(MAX_RESPONSE_BYTES+1),response.headers.get("X-Request-Id")
    except urllib.error.HTTPError as error:
        return error.code,error.read(MAX_RESPONSE_BYTES+1),error.headers.get("X-Request-Id")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise PassBError(f"provider transport failed ({type(error).__name__})") from None


def execute(repository:Path,key:str,*,fetch:Callable=_fetch,sleep:Callable=time.sleep)->dict:
    plan=json.loads((repository/"data/backtests"/PLAN_DIR/"plan.json").read_text());store=PassBStore(repository,plan);calls=0
    started=datetime.now(timezone.utc).isoformat();attempt_id=_identity("PASS_B_EXECUTION_ATTEMPT",plan["id"],started)
    ordinal=0
    for root in ROOTS:
        for original in plan["markets"][root]["requests"]:
            ordinal+=1
            request={**original,"plan_id":plan["id"]}
            if store.complete(root,request):continue
            current=store.totals()
            if current["requests"]>=MAX_REQUESTS or current["rows"]>MAX_ROWS or current["raw"]>MAX_RAW_BYTES or current["normalized"]>MAX_NORMALIZED_BYTES or current["raw"]+current["normalized"]>MAX_COMBINED_BYTES:
                raise PassBError("cumulative cap reached before request")
            retained=store.retained(root,request)
            if retained is None:
                if calls:sleep(MIN_CALL_INTERVAL_SECONDS)
                try:
                    status,raw,provider_id=fetch(request,key)
                except PassBError:
                    raise
                except Exception as error:
                    raise PassBError(f"provider request failed ({type(error).__name__})") from None
                calls+=1;store.retain(root,request,raw,status,provider_id)
            else:raw,pending=retained;status=pending["http_status"]
            if status!=200:raise PassBError("provider response rejected")
            try:
                normalized,rows,reconciliation=_normalize(raw,request,plan["calendar"])
                store.commit(root,request,normalized,rows,reconciliation)
            except PassBError as error:
                raise PassBError(str(error),details={"attempt_id":attempt_id,"request_ordinal":ordinal,"root":root,
                    "request_id":request["id"],"ticker":request["ticker"],"sessions":request["sessions"],
                    "network_calls_this_process":calls}) from None
            except Exception as error:
                raise PassBError(f"local validation failed ({type(error).__name__})",details={"attempt_id":attempt_id,
                    "request_ordinal":ordinal,"root":root,"request_id":request["id"],"ticker":request["ticker"],
                    "sessions":request["sessions"],"network_calls_this_process":calls}) from None
    store.promote();return {"state":"PASS_B_VALIDATED_ARCHIVE","plan_id":plan["id"],"attempt_id":attempt_id,"network_calls":calls,"automatic_retry":False,"recorder_started":False}


def main(argv=None)->int:
    parser=argparse.ArgumentParser();parser.add_argument("--repository",type=Path,required=True);parser.add_argument("--build-plan",action="store_true");parser.add_argument("--execute",action="store_true");args=parser.parse_args(argv)
    try:
        if args.build_plan:print(json.dumps(build_plan(args.repository.resolve()),sort_keys=True));return 0
        if args.execute:
            key=sys.stdin.readline().rstrip("\r\n")
            try:print(json.dumps(execute(args.repository.resolve(),key),sort_keys=True));return 0
            finally:key=""
        raise PassBError("explicit mode required")
    except PassBError as exc:
        directory=args.repository.resolve()/"data/backtests/pass_b_diagnostics";name="diagnostic-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json"
        _atomic_new(directory/name,_json_bytes({"schema_version":SCHEMA_VERSION,"failure_phase":"PASS_B","exception_class":type(exc).__name__,"sanitized_message":str(exc)[:200],**exc.details}))
        print("BLOCKED: Pass B failed closed; see local sanitized diagnostic",file=sys.stderr);return 2
    except Exception as exc:
        directory=args.repository.resolve()/"data/backtests/pass_b_diagnostics";name="diagnostic-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json"
        _atomic_new(directory/name,_json_bytes({"schema_version":SCHEMA_VERSION,"failure_phase":"PASS_B",
            "exception_class":type(exc).__name__,"sanitized_message":"unexpected local failure"}))
        print("BLOCKED: Pass B failed closed; see local sanitized diagnostic",file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
