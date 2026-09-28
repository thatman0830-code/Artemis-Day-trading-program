from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable

from futures_data import pass_b_backfill as base

SCHEMA_VERSION = "es-nq-pass-b-storage-continuation-v1"
PLAN_DIR = "es_nq_pass_b_continuation_plan_1"
NORMALIZED_CAP = 400 * 1024 * 1024
COMBINED_CAP = 650 * 1024 * 1024
RAW_CAP = base.MAX_RAW_BYTES
ROW_CAP = base.MAX_ROWS
REQUEST_CAP = base.MAX_REQUESTS
CONTINUATION_START_ORDINAL = 124
FIRST_NETWORK_ORDINAL = 125
UNCERTAINTY_PERCENT = 25


class ContinuationError(RuntimeError):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, default=str) + "\n").encode("utf-8")


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _ordered(plan: dict) -> list[tuple[int, str, dict]]:
    values = []
    for root in base.ROOTS:
        for request in plan["markets"][root]["requests"]:
            values.append((len(values) + 1, root, request))
    return values


def _evidence(repository: Path, plan: dict, *, require_initial: bool = False) -> dict:
    stage = repository / "data/backtests" / base.STAGING_DIR
    if not stage.exists() and (repository/"data/backtests"/base.ARCHIVE_DIR).exists():
        stage=repository/"data/backtests"/base.ARCHIVE_DIR
    entries = []
    raw_bytes = normalized_bytes = manifest_bytes = checkpoint_bytes = pending_bytes = rows = 0
    committed = 0
    for ordinal, root, request in _ordered(plan):
        files = {
            "raw": stage / root / "raw" / (request["id"] + ".json"),
            "pending": stage / root / "pending" / (request["id"] + ".json"),
            "normalized": stage / root / "normalized" / (request["id"] + ".jsonl"),
            "manifest": stage / root / "manifests" / (request["id"] + ".json"),
            "checkpoint": stage / root / "checkpoints" / (request["id"] + ".json"),
        }
        present = {name: path.exists() for name, path in files.items()}
        if not any(present.values()):
            continue
        if not files["raw"].exists() or not files["pending"].exists():
            raise ContinuationError("incomplete raw-first evidence")
        pending = json.loads(files["pending"].read_text(encoding="utf-8"))
        if pending["plan_id"] != plan["id"] or pending["request_id"] != request["id"] or _hash(files["raw"]) != pending["raw_sha256"]:
            raise ContinuationError("raw-first evidence conflict")
        raw_bytes += files["raw"].stat().st_size; pending_bytes += files["pending"].stat().st_size
        item = {"ordinal": ordinal, "root": root, "request_id": request["id"],
                "raw_sha256": _hash(files["raw"]), "pending_sha256": _hash(files["pending"])}
        if files["manifest"].exists():
            if not files["normalized"].exists() or not files["checkpoint"].exists():
                raise ContinuationError("committed evidence incomplete")
            manifest = json.loads(files["manifest"].read_text(encoding="utf-8")); checkpoint = json.loads(files["checkpoint"].read_text(encoding="utf-8"))
            if (manifest["plan_id"] != plan["id"] or manifest["request_id"] != request["id"] or
                    _hash(files["raw"]) != manifest["raw_sha256"] or _hash(files["normalized"]) != manifest["normalized_sha256"] or
                    _hash(files["manifest"]) != checkpoint["manifest_sha256"]):
                raise ContinuationError("checkpoint evidence conflict")
            committed += 1; rows += manifest["normalized_rows"]
            normalized_bytes += files["normalized"].stat().st_size; manifest_bytes += files["manifest"].stat().st_size; checkpoint_bytes += files["checkpoint"].stat().st_size
            item.update({"manifest_sha256": _hash(files["manifest"]), "checkpoint_sha256": _hash(files["checkpoint"]),
                         "normalized_sha256": _hash(files["normalized"]),
                         "continuation_plan_id":manifest.get("continuation_plan_id")})
        entries.append(item)
    if require_initial and (committed != 123 or len(entries) != 124 or entries[-1]["ordinal"] != CONTINUATION_START_ORDINAL or "manifest_sha256" in entries[-1]):
        raise ContinuationError("continuation boundary mismatch")
    fingerprint = sha256(_canonical(entries)).hexdigest()
    stable_prefix=[]
    for item in entries:
        if item["ordinal"] > CONTINUATION_START_ORDINAL: continue
        stable={key:item[key] for key in ("ordinal","root","request_id","raw_sha256","pending_sha256")}
        if item["ordinal"] < CONTINUATION_START_ORDINAL:
            stable.update({key:item[key] for key in ("manifest_sha256","checkpoint_sha256","normalized_sha256")})
        stable_prefix.append(stable)
    stable_prefix_fingerprint=sha256(_canonical(stable_prefix)).hexdigest()
    return {"fingerprint": fingerprint, "entries": entries, "committed_requests": committed, "retained_requests": len(entries),
            "stable_prefix_fingerprint":stable_prefix_fingerprint,
            "raw_bytes": raw_bytes, "normalized_rows": rows, "normalized_bytes": normalized_bytes,
            "manifest_bytes": manifest_bytes, "checkpoint_bytes": checkpoint_bytes, "pending_bytes": pending_bytes,
            "combined_data_bytes": raw_bytes + normalized_bytes,
            "combined_all_artifact_bytes": raw_bytes + normalized_bytes + manifest_bytes + checkpoint_bytes + pending_bytes}


def _distribution(repository: Path, plan: dict) -> dict:
    stage = repository / "data/backtests" / base.STAGING_DIR; groups = {}
    for _, root, request in _ordered(plan):
        path = stage / root / "manifests" / (request["id"] + ".json")
        if not path.exists(): continue
        manifest = json.loads(path.read_text(encoding="utf-8")); key = f"{root}:{request['ticker']}"
        group = groups.setdefault(key, {"root": root, "ticker": request["ticker"], "requests": 0, "rows": 0,
            "raw_bytes": 0, "normalized_bytes": 0, "raw_bytes_per_request": [], "normalized_bytes_per_request": []})
        group["requests"] += 1; group["rows"] += manifest["normalized_rows"]; group["raw_bytes"] += manifest["raw_bytes"]
        group["normalized_bytes"] += manifest["normalized_bytes"]; group["raw_bytes_per_request"].append(manifest["raw_bytes"])
        group["normalized_bytes_per_request"].append(manifest["normalized_bytes"])
    for group in groups.values():
        group["normalized_bytes_per_row"] = str(group["normalized_bytes"] / group["rows"])
        for field in ("raw_bytes_per_request", "normalized_bytes_per_request"):
            values = sorted(group.pop(field)); group[field.replace("_per_request", "_request_distribution")] = {
                "minimum": values[0], "median": values[len(values)//2], "maximum": values[-1]}
    return groups


def build_plan(repository: Path) -> dict:
    original_path = repository / "data/backtests" / base.PLAN_DIR / "plan.json"
    original = json.loads(original_path.read_text(encoding="utf-8")); evidence = _evidence(repository, original, require_initial=True)
    distribution = _distribution(repository, original); nq_upper = max(x["normalized_bytes_request_distribution"]["maximum"] for x in distribution.values() if x["root"] == "NQ")
    raw_upper = max(x["raw_bytes_request_distribution"]["maximum"] for x in distribution.values() if x["root"] == "NQ")
    request124 = next(request for ordinal, _, request in _ordered(original) if ordinal == 124)
    raw124 = repository / "data/backtests" / base.STAGING_DIR / "NQ/raw" / (request124["id"] + ".json")
    normalized124, rows124, reconciliation124 = base._normalize(raw124.read_bytes(), {**request124, "plan_id": original["id"]}, original["calendar"])
    future_requests = 6
    extra_normalized = len(normalized124) + nq_upper * future_requests
    extra_raw = raw_upper * future_requests
    normalized_margin = (extra_normalized * UNCERTAINTY_PERCENT + 99) // 100
    raw_margin = (extra_raw * UNCERTAINTY_PERCENT + 99) // 100
    estimate = {"request_124_exact_rows": rows124, "request_124_exact_normalized_bytes": len(normalized124),
        "request_124_reconciliation": reconciliation124, "future_request_count": future_requests,
        "observed_nq_normalized_upper_bytes_per_request": nq_upper, "observed_nq_raw_upper_bytes_per_request": raw_upper,
        "uncertainty_percent": UNCERTAINTY_PERCENT,
        "conservative_final_normalized_bytes": evidence["normalized_bytes"] + extra_normalized + normalized_margin,
        "conservative_final_raw_bytes": evidence["raw_bytes"] + extra_raw + raw_margin}
    estimate["conservative_final_combined_bytes"] = estimate["conservative_final_normalized_bytes"] + estimate["conservative_final_raw_bytes"]
    free = shutil.disk_usage(repository).free
    required_free = extra_normalized + extra_raw + normalized_margin + raw_margin + base.MAX_RESPONSE_BYTES
    if estimate["conservative_final_normalized_bytes"] > NORMALIZED_CAP or estimate["conservative_final_combined_bytes"] > COMBINED_CAP:
        raise ContinuationError("revised owner caps remain insufficient")
    if free < required_free:
        raise ContinuationError("insufficient destination free space")
    diagnostic_dir = repository / "data/backtests/pass_b_diagnostics"
    diagnostic_hashes = {path.name: _hash(path) for path in sorted(diagnostic_dir.glob("diagnostic-*.json"))}
    original_artifact = repository / "data/backtests" / base.PLAN_DIR / "artifact_manifest.json"
    body = {"schema_version": SCHEMA_VERSION, "original_plan_id": original["id"], "original_plan_sha256": _hash(original_path),
        "original_artifact_manifest_sha256": _hash(original_artifact), "original_evidence_fingerprint": evidence["fingerprint"],
        "stable_prefix_fingerprint":evidence["stable_prefix_fingerprint"],
        "attempt_diagnostic_sha256": diagnostic_hashes, "retained_request_124_raw_sha256": evidence["entries"][-1]["raw_sha256"],
        "retained_request_124_pending_sha256": evidence["entries"][-1]["pending_sha256"], "continuation_start_ordinal": CONTINUATION_START_ORDINAL,
        "first_network_ordinal": FIRST_NETWORK_ORDINAL, "base_state": {key:value for key,value in evidence.items() if key != "entries"},
        "distribution": distribution, "estimate": estimate, "available_free_bytes_at_plan_creation": free,
        "minimum_required_free_bytes": required_free, "caps": {"requests": REQUEST_CAP, "rows": ROW_CAP, "raw_bytes": RAW_CAP,
            "normalized_bytes": NORMALIZED_CAP, "combined_bytes": COMBINED_CAP, "response_bytes": base.MAX_RESPONSE_BYTES},
        "call_interval_seconds": base.MIN_CALL_INTERVAL_SECONDS, "automatic_retry": False, "recorder_start_allowed": False,
        "execution_authorized": False}
    body["id"] = sha256(_canonical(body)).hexdigest()
    target = repository / "data/backtests" / PLAN_DIR
    if target.exists(): raise ContinuationError("versioned continuation plan already exists")
    base._atomic_new(target / "plan.json", _canonical(body))
    base._atomic_new(target / "artifact_manifest.json", _canonical({"schema_version": SCHEMA_VERSION, "plan_id": body["id"],
        "plan_sha256": _hash(target / "plan.json")}))
    return body


def _load_and_verify(repository: Path) -> tuple[dict, dict, dict]:
    path = repository / "data/backtests" / PLAN_DIR / "plan.json"; continuation = json.loads(path.read_text(encoding="utf-8"))
    expected = dict(continuation); plan_id = expected.pop("id")
    if sha256(_canonical(expected)).hexdigest() != plan_id: raise ContinuationError("continuation plan identity conflict")
    original_path = repository / "data/backtests" / base.PLAN_DIR / "plan.json"; original = json.loads(original_path.read_text(encoding="utf-8"))
    if original["id"] != continuation["original_plan_id"] or _hash(original_path) != continuation["original_plan_sha256"]:
        raise ContinuationError("original plan link conflict")
    evidence = _evidence(repository, original)
    if evidence["stable_prefix_fingerprint"] != continuation["stable_prefix_fingerprint"]: raise ContinuationError("checkpoint-chain fingerprint conflict")
    return continuation, original, evidence


class ContinuationStore(base.PassBStore):
    def __init__(self, repository: Path, original: dict, continuation: dict):
        super().__init__(repository, original); self.continuation = continuation; self.caps = continuation["caps"]
        self.continuation_request_ids={request["id"] for ordinal,_,request in _ordered(original) if ordinal>=CONTINUATION_START_ORDINAL}

    def complete(self,root:str,request:dict)->bool:
        result=super().complete(root,request)
        if result and request["id"] in self.continuation_request_ids:
            manifest=json.loads((self.stage/root/"manifests"/(request["id"]+".json")).read_text(encoding="utf-8"))
            checkpoint=json.loads((self.stage/root/"checkpoints"/(request["id"]+".json")).read_text(encoding="utf-8"))
            if manifest.get("continuation_plan_id")!=self.continuation["id"] or checkpoint.get("continuation_plan_id")!=self.continuation["id"]:
                raise ContinuationError("continuation plan-link conflict")
        return result

    def retain(self, root: str, request: dict, raw: bytes, status: int, request_id: str | None):
        if self.stop.exists(): raise ContinuationError("owner stop requested")
        if len(raw) > self.caps["response_bytes"]: raise ContinuationError("response cap exceeded")
        totals = self.totals(); projected_raw = totals["raw"] + len(raw)
        if (totals["requests"] + 1 > self.caps["requests"] or projected_raw > self.caps["raw_bytes"] or
                projected_raw + totals["normalized"] > self.caps["combined_bytes"]): raise ContinuationError("continuation cumulative cap exceeded")
        path = self.stage/root/"raw"/(request["id"]+".json"); base._atomic_new(path, raw)
        base._atomic_new(self.stage/root/"pending"/(request["id"]+".json"), base._json_bytes({"schema_version":base.SCHEMA_VERSION,
            "plan_id":self.plan["id"],"continuation_plan_id":self.continuation["id"],"request_id":request["id"],"root":root,
            "http_status":status,"provider_request_id":request_id,"raw_sha256":sha256(raw).hexdigest(),"raw_bytes":len(raw),
            "automatic_retry":False,"aggregate_endpoint":True}))

    def commit(self, root: str, request: dict, normalized: bytes, rows: int, reconciliation: dict | None = None):
        retained=self.retained(root,request)
        if retained is None: raise ContinuationError("raw-first transaction missing")
        raw,pending=retained;totals=self.totals();combined=totals["raw"]+totals["normalized"]+len(normalized)
        if (totals["rows"]+rows>self.caps["rows"] or totals["normalized"]+len(normalized)>self.caps["normalized_bytes"] or
                combined>self.caps["combined_bytes"]): raise ContinuationError("continuation cumulative cap exceeded")
        norm=self.stage/root/"normalized"/(request["id"]+".jsonl");base._atomic_new(norm,normalized)
        manifest={**pending,"continuation_plan_id":self.continuation["id"],"normalized_rows":rows,"normalized_bytes":len(normalized),
            "normalized_sha256":sha256(normalized).hexdigest(),"expected_maximum_rows":request["maximum_rows"],
            "missing_aggregate_minutes":request["maximum_rows"]-rows,"raw_relative_path":"raw/"+request["id"]+".json",
            "normalized_relative_path":"normalized/"+request["id"]+".jsonl","ticker":request["ticker"],"contract_id":request["contract_id"],
            "session_reconciliation":reconciliation or {"policy":"STRICT_SESSION_TIMESTAMP_PAIR_V1","excluded_provider_duplicates":0}}
        mp=self.stage/root/"manifests"/(request["id"]+".json");base._atomic_new(mp,base._json_bytes(manifest))
        base._atomic_new(self.stage/root/"checkpoints"/(request["id"]+".json"),base._json_bytes({"plan_id":self.plan["id"],
            "continuation_plan_id":self.continuation["id"],"request_id":request["id"],"manifest_sha256":_hash(mp)}))


def execute(repository: Path, key: str, *, fetch: Callable = base._fetch, sleep: Callable = time.sleep) -> dict:
    continuation, original, evidence = _load_and_verify(repository)
    if shutil.disk_usage(repository).free < continuation["minimum_required_free_bytes"]: raise ContinuationError("insufficient destination free space")
    store=ContinuationStore(repository,original,continuation);calls=0;started=datetime.now(timezone.utc).isoformat()
    attempt_id=sha256(f"CONTINUATION|{continuation['id']}|{started}".encode()).hexdigest()
    for ordinal,root,source in _ordered(original):
        request={**source,"plan_id":original["id"]}
        if store.complete(root,request): continue
        if ordinal < CONTINUATION_START_ORDINAL: raise ContinuationError("verified prefix is incomplete")
        retained=store.retained(root,request)
        if retained is None:
            if ordinal < FIRST_NETWORK_ORDINAL: raise ContinuationError("retained request 124 is missing")
            if calls:sleep(base.MIN_CALL_INTERVAL_SECONDS)
            try: status,raw,provider_id=fetch(request,key)
            except Exception as error: raise ContinuationError(f"provider request failed ({type(error).__name__})",details={"request_ordinal":ordinal}) from None
            calls+=1;store.retain(root,request,raw,status,provider_id)
        else: raw,pending=retained;status=pending["http_status"]
        if status!=200: raise ContinuationError("provider response rejected",details={"request_ordinal":ordinal})
        try: normalized,rows,reconciliation=base._normalize(raw,request,original["calendar"]);store.commit(root,request,normalized,rows,reconciliation)
        except (base.PassBError,ContinuationError) as error: raise ContinuationError(str(error),details={"request_ordinal":ordinal}) from None
    store.promote();return {"state":"PASS_B_VALIDATED_ARCHIVE","continuation_plan_id":continuation["id"],"attempt_id":attempt_id,
        "network_calls":calls,"automatic_retry":False,"recorder_started":False}


def main(argv=None) -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--repository",type=Path,required=True);parser.add_argument("--build-plan",action="store_true");parser.add_argument("--execute",action="store_true");args=parser.parse_args(argv)
    try:
        if args.build_plan: print(json.dumps(build_plan(args.repository.resolve()),sort_keys=True));return 0
        if args.execute:
            key=sys.stdin.readline().rstrip("\r\n")
            try: print(json.dumps(execute(args.repository.resolve(),key),sort_keys=True));return 0
            finally: key=""
        raise ContinuationError("explicit mode required")
    except (ContinuationError,base.PassBError) as error:
        directory=args.repository.resolve()/"data/backtests/pass_b_continuation_diagnostics";name="diagnostic-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json"
        details=getattr(error,"details",{});base._atomic_new(directory/name,base._json_bytes({"schema_version":SCHEMA_VERSION,
            "failure_phase":"PASS_B_CONTINUATION","exception_class":type(error).__name__,"sanitized_message":str(error)[:200],**details}))
        print("BLOCKED: Pass B continuation failed closed; see local sanitized diagnostic",file=sys.stderr);return 2
    except Exception as error:
        directory=args.repository.resolve()/"data/backtests/pass_b_continuation_diagnostics";name="diagnostic-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json"
        base._atomic_new(directory/name,base._json_bytes({"schema_version":SCHEMA_VERSION,"failure_phase":"PASS_B_CONTINUATION",
            "exception_class":type(error).__name__,"sanitized_message":"unexpected local failure"}))
        print("BLOCKED: Pass B continuation failed closed; see local sanitized diagnostic",file=sys.stderr);return 2


if __name__ == "__main__": raise SystemExit(main())
