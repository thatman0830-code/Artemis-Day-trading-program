from __future__ import annotations

import json
import os
import re
import time
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable

from futures_data.forward_collector import ForwardCollectorError

REFRESH_SCHEMA = "es-nq-forward-reference-refresh-v1"
MAX_REQUESTS = 8
MAX_RAW_BYTES = 8 * 1024 * 1024
MIN_REQUEST_INTERVAL = 15.0
REFRESH_THRESHOLD = timedelta(days=14)
TICKER = re.compile(r"^(ES|NQ)[HMUZ][0-9]{1,2}$")
BASE_URL="https://api.massive.com"
OUTRIGHT_PRODUCT_NAMES={
    "ES":{"E-mini Standard and Poor's 500 Stock Price Index Futures","E-mini S&P 500 Futures"},
    "NQ":{"E-mini Nasdaq-100 Index Futures","E-mini Nasdaq-100 Futures"},
}


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() or partial.exists():
        raise ForwardCollectorError("reference artifact conflict")
    with partial.open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.rename(partial, path)


def refresh_required(configuration: dict, now: datetime, threshold: timedelta = REFRESH_THRESHOLD) -> bool:
    boundary = datetime.fromisoformat(configuration["verified_coverage"]["end_exclusive"] + "T00:00:00+00:00")
    return boundary - now.astimezone(timezone.utc) <= threshold


def _validate_contract(root: str, row: dict) -> dict:
    ticker = row.get("ticker")
    if (row.get("product_code") != root or row.get("type") != "single" or
            row.get("trading_venue") != "XCME" or not isinstance(ticker, str) or
            not TICKER.fullmatch(ticker) or not ticker.startswith(root)):
        raise ForwardCollectorError("reference contract rejected")
    required = ("first_trade_date", "last_trade_date", "settlement_date")
    if any(not isinstance(row.get(x), str) for x in required):
        raise ForwardCollectorError("reference contract lifecycle rejected")
    for value in required: date.fromisoformat(row[value])
    return {name: row[name] for name in ("ticker", "product_code", "type", "trading_venue", *required)}


def _validate_schedule(root: str, row: dict, after: str) -> dict:
    if row.get("product_code") != root or row.get("trading_venue") != "XCME":
        raise ForwardCollectorError("reference schedule product rejected")
    day = row.get("session_date")
    intervals = row.get("active_intervals")
    if not isinstance(day, str) or day < after or not isinstance(intervals, list) or not intervals:
        raise ForwardCollectorError("reference schedule boundary rejected")
    normalized = []
    for interval in intervals:
        start = datetime.fromisoformat(interval["start_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(interval["end_exclusive_utc"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ForwardCollectorError("reference schedule interval rejected")
        normalized.append({"start_utc": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                           "end_exclusive_utc": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")})
    return {"root": root, "session_date": day, "active_intervals": normalized}


def _events_to_schedules(root:str, rows:list[dict], after:str)->list[dict]:
    by_day={}
    for row in rows:
        if row.get("product_name") not in OUTRIGHT_PRODUCT_NAMES[root]:
            continue
        if row.get("product_code")!=root or row.get("trading_venue")!="XCME" or row.get("event") not in ("pre_open","open","close"):
            raise ForwardCollectorError("reference schedule event rejected")
        day=row.get("session_end_date");stamp=row.get("timestamp")
        if not isinstance(day,str) or day<after or not isinstance(stamp,str):raise ForwardCollectorError("reference schedule event boundary rejected")
        moment=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if moment.tzinfo is None:raise ForwardCollectorError("reference schedule timestamp rejected")
        by_day.setdefault(day,[]).append((moment.astimezone(timezone.utc),row["event"]))
    if not by_day:raise ForwardCollectorError("reference outright schedule absent")
    result=[]
    for day,events in sorted(by_day.items()):
        active=None;intervals=[]
        for stamp,event in sorted(events):
            if event=="open":
                if active is not None:raise ForwardCollectorError("reference schedule duplicate open")
                active=stamp
            elif active is not None:
                if stamp<=active:raise ForwardCollectorError("reference schedule interval rejected")
                intervals.append({"start_utc":active.isoformat().replace("+00:00","Z"),"end_exclusive_utc":stamp.isoformat().replace("+00:00","Z")});active=None
        if active is not None or not intervals:raise ForwardCollectorError("reference schedule incomplete")
        result.append({"root":root,"session_date":day,"active_intervals":intervals})
    return result


def default_fetcher(configuration:dict):
    boundary=configuration["verified_coverage"]["end_exclusive"]
    end=(date.fromisoformat(boundary)+timedelta(days=45)).isoformat()
    def fetch(endpoint:str,root:str,key:str):
        query=({"product_code":root,"session_end_date.gte":boundary,"session_end_date.lt":end,"limit":"1000","sort":"session_end_date.asc"}
            if endpoint=="schedules" else {"product_code":root,"date":boundary,"active":"true","type":"single","limit":"1000","sort":"ticker.asc"})
        url=BASE_URL+"/futures/v1/"+endpoint+"?"+urllib.parse.urlencode(query)
        request=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"},method="GET")
        with urllib.request.urlopen(request,timeout=30,context=ssl.create_default_context()) as response:
            return response.status,response.read(MAX_RAW_BYTES+1),response.headers.get("X-Request-Id") or response.headers.get("Request-Id")
    return fetch


@dataclass
class ReferenceRefresher:
    repository: Path
    fetch: Callable[[str, str, str], tuple[int, bytes, str | None]]
    sleep: Callable[[float], None] = time.sleep

    def run(self, configuration: dict, credential: str, now: datetime) -> dict:
        if not credential:
            raise ForwardCollectorError("credential presence rejected")
        if not refresh_required(configuration, now):
            return {"state": "NOT_REQUIRED", "network_calls": 0, "configuration": configuration}
        refresh_id = sha256((configuration["configuration_id"] + "|" + now.astimezone(timezone.utc).isoformat()).encode()).hexdigest()
        base = self.repository.resolve() / "data/futures_forward/references" / refresh_id
        calls = total = 0; schedules = []; contracts = []; refresh_evidence=[]; schedule_events={"ES":[],"NQ":[]}
        for root in ("ES", "NQ"):
            for endpoint in ("schedules", "contracts"):
                if calls >= MAX_REQUESTS: raise ForwardCollectorError("reference request cap exceeded")
                if calls: self.sleep(MIN_REQUEST_INTERVAL)
                status, raw, request_id = self.fetch(endpoint, root, credential); calls += 1; total += len(raw)
                if total > MAX_RAW_BYTES: raise ForwardCollectorError("reference byte cap exceeded")
                raw_path = base/root/"raw"/(endpoint+".json")
                _atomic(raw_path, raw)
                _atomic(base/root/"manifests"/(endpoint+".json"), _bytes({"schema_version": REFRESH_SCHEMA,
                    "endpoint_class": "futures_"+endpoint, "root": root, "http_status": status,
                    "provider_request_id": request_id, "raw_relative_path": raw_path.relative_to(base).as_posix(),
                    "raw_sha256": sha256(raw).hexdigest(), "raw_bytes": len(raw), "automatic_retry": False}))
                refresh_evidence.append({"path":raw_path.relative_to(self.repository.resolve()).as_posix(),"sha256":sha256(raw).hexdigest()})
                if status != 200: raise ForwardCollectorError("reference provider response rejected")
                try: payload = json.loads(raw)
                except (ValueError, TypeError) as error: raise ForwardCollectorError("reference schema rejected") from error
                rows = payload.get("results")
                if not isinstance(rows, list) or payload.get("next_url"):
                    raise ForwardCollectorError("reference pagination or schema rejected")
                if endpoint == "schedules":
                    if rows and "event" in rows[0]: schedule_events[root].extend(rows)
                    else: schedules.extend(_validate_schedule(root, x, configuration["verified_coverage"]["end_exclusive"]) for x in rows)
                else: contracts.extend(_validate_contract(root, x) for x in rows)
        if schedule_events["ES"] or schedule_events["NQ"]:
            parsed={root:_events_to_schedules(root,schedule_events[root],configuration["verified_coverage"]["end_exclusive"]) for root in ("ES","NQ")}
            canonical=lambda xs:[(x["session_date"],x["active_intervals"]) for x in xs]
            if canonical(parsed["ES"])!=canonical(parsed["NQ"]):raise ForwardCollectorError("ES/NQ reference schedule conflict")
            schedules=[*parsed["ES"],*parsed["NQ"]]
        successor = build_successor(configuration, schedules, contracts)
        material={k:v for k,v in successor.items() if k!="configuration_id"}
        material["evidence"]=[*material.get("evidence",[]),*refresh_evidence]
        successor={**material,"configuration_id":sha256(_bytes(material)).hexdigest()}
        return {"state": "REFRESH_VALIDATED", "network_calls": calls, "refresh_id": refresh_id,
                "raw_bytes": total, "configuration": successor, "automatic_retry": False}


def build_successor(configuration: dict, schedules: list[dict], contracts: list[dict]) -> dict:
    if not schedules:
        raise ForwardCollectorError("reference refresh returned no future sessions")
    days = sorted({x["session_date"] for x in schedules})
    if days[0] != configuration["verified_coverage"]["end_exclusive"]:
        raise ForwardCollectorError("reference refresh is non-contiguous")
    by_root = {root: sorted((x for x in contracts if x["product_code"] == root), key=lambda x:(x["settlement_date"],x["ticker"])) for root in ("ES","NQ")}
    if any(not by_root[root] for root in by_root): raise ForwardCollectorError("reference exact contracts missing")
    pending = []; preparations=[]
    for root in ("ES","NQ"):
        root_schedules=sorted((x for x in schedules if x["root"]==root),key=lambda x:x["session_date"])
        current_ticker=next((x["ticker"] for x in reversed(configuration["history"]) if x["root"]==root),None)
        current=next((x for x in by_root[root] if x["ticker"]==current_ticker),None)
        if current is None: raise ForwardCollectorError("current exact contract absent from refresh")
        following=next((x for x in by_root[root] if x["settlement_date"]>current["settlement_date"]),None)
        overlap_days=[]
        if following:
            eligible_days=[x["session_date"] for x in root_schedules if x["session_date"]<=current["last_trade_date"]]
            overlap_days=eligible_days[-5:]
            if overlap_days:
                pair_id=sha256((root+"|"+current["ticker"]+"|"+following["ticker"]+"|"+overlap_days[0]).encode()).hexdigest()
                preparations.append({"root":root,"pair_id":pair_id,"outgoing_ticker":current["ticker"],
                    "incoming_ticker":following["ticker"],"sessions":overlap_days,"state":"AWAITING_FINALIZED_VOLUME",
                    "rollover_decision":None})
        for schedule in root_schedules:
            if schedule["session_date"]>current["last_trade_date"]:
                continue
            if schedule["session_date"] in overlap_days:
                prep=preparations[-1]
                for contract,leg in ((current,"OUTGOING"),(following,"INCOMING")):
                    pending.append({**schedule,"ticker":contract["ticker"],"contract_id":sha256(_bytes(contract)).hexdigest(),
                        "rollover_pair_id":prep["pair_id"],"rollover_leg":leg})
            else:
                if not (current["first_trade_date"]<=schedule["session_date"]<=current["last_trade_date"]):
                    raise ForwardCollectorError("future active contract requires finalized rollover")
                pending.append({**schedule,"ticker":current["ticker"],"contract_id":sha256(_bytes(current)).hexdigest(),"rollover_leg":"ACTIVE"})
    material = {k:v for k,v in configuration.items() if k != "configuration_id"}
    material["sessions"] = pending; material["pending_session_count"] = len(pending)
    covered_days=sorted({x["session_date"] for x in pending})
    if not covered_days:raise ForwardCollectorError("reference refresh produced no bounded sessions")
    material["verified_coverage"] = {**material["verified_coverage"], "end_exclusive":(date.fromisoformat(covered_days[-1])+timedelta(days=1)).isoformat(), "last_session":covered_days[-1]}
    material["refresh_required"] = False; material["refresh_reason"] = None
    material["parent_configuration_id"] = configuration["configuration_id"]
    material["configuration_policy"] = "AUTHORITATIVE_REFERENCE_REFRESH_V1"
    material["rollover_preparations"] = preparations
    return {**material, "configuration_id":sha256(_bytes(material)).hexdigest()}


def publish_successor(repository: Path, configuration: dict) -> tuple[Path, Path]:
    repository=repository.resolve(); versions=repository/"config/es_nq_forward_versions"
    data=_bytes(configuration); path=versions/(configuration["configuration_id"]+".json")
    manifest_path=versions/(configuration["configuration_id"]+".manifest.json")
    _atomic(path,data); _atomic(manifest_path,_bytes({"schema_version":"es-nq-forward-configuration-manifest-v1",
        "configuration_id":configuration["configuration_id"],"configuration_sha256":sha256(data).hexdigest(),
        "parent_configuration_id":configuration.get("parent_configuration_id")}))
    pointer=repository/"config/es_nq_forward_current.json";pointer_data=_bytes({"configuration_path":path.relative_to(repository).as_posix(),
        "manifest_path":manifest_path.relative_to(repository).as_posix(),"configuration_id":configuration["configuration_id"],
        "configuration_sha256":sha256(data).hexdigest()});partial=pointer.with_suffix(".json.partial")
    partial.write_bytes(pointer_data);os.replace(partial,pointer)
    return path,manifest_path


def resolve_current(repository:Path,bootstrap:Path)->tuple[Path,Path]:
    repository=repository.resolve();pointer=repository/"config/es_nq_forward_current.json"
    if not pointer.exists():return bootstrap.resolve(),bootstrap.with_name("es_nq_forward_sessions.manifest.json")
    value=json.loads(pointer.read_text(encoding="utf-8"));path=(repository/value["configuration_path"]).resolve();manifest=(repository/value["manifest_path"]).resolve()
    if repository not in path.parents or repository not in manifest.parents or sha256(path.read_bytes()).hexdigest()!=value["configuration_sha256"]:
        raise ForwardCollectorError("current configuration pointer rejected")
    return path,manifest


def reconcile_retained_refresh(repository:Path,refresh_id:str,bootstrap:dict)->dict:
    repository=repository.resolve();base=repository/"data/futures_forward/references"/refresh_id
    schedules=[];contracts=[];evidence=[];events={"ES":[],"NQ":[]}
    for root in ("ES","NQ"):
        for endpoint in ("schedules","contracts"):
            raw_path=base/root/"raw"/(endpoint+".json");manifest_path=base/root/"manifests"/(endpoint+".json")
            manifest=json.loads(manifest_path.read_text(encoding="utf-8"));raw=raw_path.read_bytes();digest=sha256(raw).hexdigest()
            if manifest.get("http_status")!=200 or manifest.get("raw_sha256")!=digest or manifest.get("automatic_retry") is not False:
                raise ForwardCollectorError("retained reference evidence rejected")
            payload=json.loads(raw);rows=payload.get("results")
            if not isinstance(rows,list) or payload.get("next_url"):raise ForwardCollectorError("retained reference schema rejected")
            evidence.append({"path":raw_path.relative_to(repository).as_posix(),"sha256":digest})
            if endpoint=="schedules":events[root].extend(rows)
            else:contracts.extend(_validate_contract(root,x) for x in rows)
    parsed={root:_events_to_schedules(root,events[root],bootstrap["verified_coverage"]["end_exclusive"]) for root in ("ES","NQ")}
    canonical=lambda xs:[(x["session_date"],x["active_intervals"]) for x in xs]
    if canonical(parsed["ES"])!=canonical(parsed["NQ"]):raise ForwardCollectorError("retained ES/NQ schedule conflict")
    successor=build_successor(bootstrap,[*parsed["ES"],*parsed["NQ"]],contracts)
    material={k:v for k,v in successor.items() if k!="configuration_id"};material["evidence"]=[*material.get("evidence",[]),*evidence]
    successor={**material,"configuration_id":sha256(_bytes(material)).hexdigest()}
    path,manifest=publish_successor(repository,successor)
    return {"configuration":successor,"configuration_path":path,"manifest_path":manifest,"refresh_id":refresh_id,"network_calls":0}
