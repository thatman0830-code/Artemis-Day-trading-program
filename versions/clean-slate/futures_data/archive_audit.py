from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
import argparse

from futures_data import pass_b_backfill as base
from futures_data import pass_b_continuation as continuation


class ArchiveAuditError(RuntimeError):
    pass


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _tree_fingerprint(entries: list[dict]) -> str:
    payload=(json.dumps(entries,sort_keys=True,separators=(",",":"))+"\n").encode()
    return sha256(payload).hexdigest()


def audit(repository: Path) -> dict:
    original_path=repository/"data/backtests"/base.PLAN_DIR/"plan.json"
    continuation_path=repository/"data/backtests"/continuation.PLAN_DIR/"plan.json"
    original=json.loads(original_path.read_text(encoding="utf-8"));overlay=json.loads(continuation_path.read_text(encoding="utf-8"))
    expected=dict(overlay);identity=expected.pop("id")
    if sha256(continuation._canonical(expected)).hexdigest()!=identity:raise ArchiveAuditError("continuation plan identity conflict")
    if original["id"]!=overlay["original_plan_id"] or _hash(original_path)!=overlay["original_plan_sha256"]:raise ArchiveAuditError("original plan link conflict")
    archive=repository/"data/backtests"/base.ARCHIVE_DIR
    if not archive.is_dir() or (repository/"data/backtests"/base.STAGING_DIR).exists():raise ArchiveAuditError("promotion boundary invalid")
    calendar={x["session_date"]:x for x in original["calendar"]["sessions"]};chicago=ZoneInfo("America/Chicago")
    totals=Counter();hash_entries=[];seen=set();last_by_contract={};roots={root:Counter() for root in base.ROOTS};missing=[]
    request_summaries=[]
    ordered=continuation._ordered(original)
    if len(ordered)!=130:raise ArchiveAuditError("request inventory is not 130")
    for ordinal,root,request in ordered:
        paths={"raw":archive/root/"raw"/(request["id"]+".json"),"pending":archive/root/"pending"/(request["id"]+".json"),
            "normalized":archive/root/"normalized"/(request["id"]+".jsonl"),"manifest":archive/root/"manifests"/(request["id"]+".json"),
            "checkpoint":archive/root/"checkpoints"/(request["id"]+".json")}
        if not all(path.is_file() for path in paths.values()):raise ArchiveAuditError(f"request {ordinal} artifact incomplete")
        manifest=json.loads(paths["manifest"].read_text(encoding="utf-8"));pending=json.loads(paths["pending"].read_text(encoding="utf-8"));checkpoint=json.loads(paths["checkpoint"].read_text(encoding="utf-8"))
        if any((manifest["plan_id"]!=original["id"],manifest["request_id"]!=request["id"],manifest["root"]!=root,
                manifest["ticker"]!=request["ticker"],manifest["contract_id"]!=request["contract_id"],pending["request_id"]!=request["id"],
                checkpoint["request_id"]!=request["id"])):raise ArchiveAuditError(f"request {ordinal} identity conflict")
        if ordinal>=124 and (manifest.get("continuation_plan_id")!=overlay["id"] or checkpoint.get("continuation_plan_id")!=overlay["id"]):
            raise ArchiveAuditError(f"request {ordinal} continuation link conflict")
        hashes={name:_hash(path) for name,path in paths.items()}
        if hashes["raw"]!=manifest["raw_sha256"] or hashes["raw"]!=pending["raw_sha256"] or hashes["normalized"]!=manifest["normalized_sha256"] or hashes["manifest"]!=checkpoint["manifest_sha256"]:
            raise ArchiveAuditError(f"request {ordinal} checksum conflict")
        raw=json.loads(paths["raw"].read_text(encoding="utf-8"),parse_float=Decimal)
        raw_by_key={}
        for row in raw.get("results",[]):
            raw_by_key.setdefault((row.get("ticker"),row.get("session_end_date"),int(row["window_start"])),[]).append(row)
        row_count=0;previous=None
        with paths["normalized"].open(encoding="utf-8") as handle:
            for line in handle:
                row=json.loads(line,parse_float=Decimal);row_count+=1
                if row["root"]!=root or row["ticker"]!=request["ticker"] or row["contract_id"]!=request["contract_id"] or row["plan_id"]!=original["id"]:
                    raise ArchiveAuditError(f"request {ordinal} normalized identity conflict")
                timestamp=int(row["window_start_ns"]);key=(root,row["contract_id"],timestamp)
                if key in seen:raise ArchiveAuditError("duplicate market-contract-timestamp")
                seen.add(key)
                if previous is not None and timestamp<=previous:raise ArchiveAuditError(f"request {ordinal} timestamp order conflict")
                previous=timestamp
                if timestamp<=last_by_contract.get((root,row["contract_id"]),-1):raise ArchiveAuditError("cross-request timestamp order conflict")
                last_by_contract[(root,row["contract_id"])]=timestamp
                session=row["session_date"]
                if session not in request["sessions"] or session not in calendar:raise ArchiveAuditError("session identity conflict")
                minute=timestamp//60_000_000_000
                if minute not in base._active_minutes(calendar[session]):raise ArchiveAuditError("timestamp outside verified schedule")
                stamp=datetime.fromtimestamp(timestamp/1_000_000_000,tz=timezone.utc)
                if stamp.astimezone(chicago).utcoffset() is None:raise ArchiveAuditError("Chicago conversion failed")
                candidates=raw_by_key.get((row["ticker"],session,timestamp),[])
                economic={name:Decimal(str(row[name])) for name in ("open","high","low","close","volume")}
                if not any(all(Decimal(str(candidate[name]))==economic[name] for name in economic) for candidate in candidates):
                    raise ArchiveAuditError("normalized row lacks exact raw lineage")
        if row_count!=manifest["normalized_rows"] or paths["normalized"].stat().st_size!=manifest["normalized_bytes"] or paths["raw"].stat().st_size!=manifest["raw_bytes"]:
            raise ArchiveAuditError(f"request {ordinal} size or row-count conflict")
        expected_missing=request["maximum_rows"]-row_count
        if manifest["missing_aggregate_minutes"]!=expected_missing or expected_missing<0:raise ArchiveAuditError("missing-minute classification conflict")
        missing.append({"request_ordinal":ordinal,"root":root,"ticker":request["ticker"],"missing_minutes":expected_missing,
            "classification":"ZERO_OBSERVED_ELIGIBLE_TRADE_VOLUME_NO_OHLC"})
        for name,path in paths.items():hash_entries.append({"path":str(path.relative_to(repository)).replace("\\","/"),"sha256":hashes[name],"bytes":path.stat().st_size})
        totals["requests"]+=1;totals["rows"]+=row_count;totals["raw_bytes"]+=paths["raw"].stat().st_size;totals["normalized_bytes"]+=paths["normalized"].stat().st_size
        totals["manifest_bytes"]+=paths["manifest"].stat().st_size;totals["checkpoint_bytes"]+=paths["checkpoint"].stat().st_size;totals["pending_bytes"]+=paths["pending"].stat().st_size
        roots[root]["requests"]+=1;roots[root]["rows"]+=row_count;roots[root]["raw_bytes"]+=paths["raw"].stat().st_size;roots[root]["normalized_bytes"]+=paths["normalized"].stat().st_size
        request_summaries.append({"ordinal":ordinal,"root":root,"ticker":request["ticker"],"contract_id":request["contract_id"],"sessions":request["sessions"],"rows":row_count,"missing":expected_missing})
    totals["combined_data_bytes"]=totals["raw_bytes"]+totals["normalized_bytes"]
    totals["combined_all_bytes"]=totals["combined_data_bytes"]+totals["manifest_bytes"]+totals["checkpoint_bytes"]+totals["pending_bytes"]
    caps=overlay["caps"]
    if totals["requests"]>caps["requests"] or totals["rows"]>caps["rows"] or totals["raw_bytes"]>caps["raw_bytes"] or totals["normalized_bytes"]>caps["normalized_bytes"] or totals["combined_data_bytes"]>caps["combined_bytes"]:
        raise ArchiveAuditError("final cap conflict")
    windows=original["rollovers"]["markets"]
    for summary in request_summaries:
        matches=[window for window in windows[summary["root"]]["active_windows"] if window["ticker"]==summary["ticker"] and all(window["start"]<=session<window["end_exclusive"] for session in summary["sessions"])]
        if len(matches)!=1:raise ArchiveAuditError("active-contract window conflict")
    evidence_paths=[original_path,repository/"data/backtests"/base.PLAN_DIR/"artifact_manifest.json",continuation_path,
        repository/"data/backtests"/continuation.PLAN_DIR/"artifact_manifest.json"]
    evidence_hashes={str(path.relative_to(repository)).replace("\\","/"):_hash(path) for path in evidence_paths}
    return {"state":"FINAL_ES_NQ_ARCHIVE_AUDIT_PASS","original_plan_id":original["id"],"continuation_plan_id":overlay["id"],
        "archive_path":str(archive),"archive_tree_sha256":_tree_fingerprint(sorted(hash_entries,key=lambda x:x["path"])),
        "artifact_hashes":hash_entries,"plan_hashes":evidence_hashes,"totals":dict(totals),"markets":{root:dict(value) for root,value in roots.items()},
        "missing_minutes":missing,"missing_total":sum(x["missing_minutes"] for x in missing),"duplicate_count":0,
        "synthesized_rows":0,"continuous_adjustment":False,"request_summaries":request_summaries,
        "caps":caps,"automatic_retry":False,"recorder_started":False}


def main(argv=None)->int:
    parser=argparse.ArgumentParser();parser.add_argument("--repository",type=Path,required=True);parser.add_argument("--write-report",action="store_true");args=parser.parse_args(argv)
    try:
        result=audit(args.repository.resolve())
        if args.write_report:
            target=args.repository.resolve()/"outputs/archive_audits/es_nq_pass_b_final_audit.json"
            if target.exists():raise ArchiveAuditError("audit report destination exists")
            base._atomic_new(target,base._json_bytes(result));print(target)
        else:print(json.dumps(result,sort_keys=True))
        return 0
    except ArchiveAuditError as error:
        print(f"BLOCKED: archive audit failed closed ({error})");return 2


if __name__=="__main__":raise SystemExit(main())
