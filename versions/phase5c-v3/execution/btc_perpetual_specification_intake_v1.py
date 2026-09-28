"""Explicit owner intake for BTC perpetual economics; no values are inferred."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal,InvalidOperation
import argparse,hashlib,json
from pathlib import Path

from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2
from backtesting.execution_accounting_v2.specifications import (
    EvidenceRecord,InstrumentProfile,SpecificationRecord,SpecificationRepository,
    SpecificationType,canonical_fingerprint,
)
from execution.btc_perpetual_economic_gate_v1 import REQUIRED_TYPES,evaluate_btc_perpetual_economics
from execution.btc_perpetual_specification_bundle_v1 import write_btc_perpetual_specification_bundle
from execution.hyperliquid_perpetual_precision_v1 import HyperliquidBTCPerpetualPrecisionV1

SCHEMA="btc-perpetual-specification-intake-v1"
RECORD_KEYS={"specification_type","source_organization","document_identity","canonical_url",
    "local_snapshot_path","snapshot_sha256","retrieved_at","effective_from","effective_to",
    "values","owner_approved","assumptions_and_gaps"}


class BTCPerpetualSpecificationIntakeError(ValueError): pass


def _canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _time(value):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset().total_seconds()!=0: raise ValueError
    return result
def _sha(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value): raise ValueError
def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise BTCPerpetualSpecificationIntakeError("duplicate JSON field")
        result[key]=value
    return result


def create_blank_intake_template():
    records=[]
    for kind in REQUIRED_TYPES:
        records.append({"specification_type":kind.value,"source_organization":None,
            "document_identity":None,"canonical_url":None,"local_snapshot_path":None,
            "snapshot_sha256":None,"retrieved_at":None,"effective_from":None,"effective_to":None,
            "values":{},"owner_approved":False,"assumptions_and_gaps":[]})
    return {"schema_version":SCHEMA,"market":"BTC-PERP","instrument_id":"BTC",
        "size_decimals":None,"records":records,"trading_authority":False}


def write_blank_intake_template(path):
    path=Path(path)
    if path.parent.is_symlink() or not path.parent.is_dir(): raise BTCPerpetualSpecificationIntakeError("template parent is unsafe")
    with open(path,"xb") as stream:
        stream.write(_canonical(create_blank_intake_template())+b"\n")


def read_intake_document(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=1024*1024:
        raise BTCPerpetualSpecificationIntakeError("intake file is missing or unsafe")
    try:return json.loads(path.read_bytes(),object_pairs_hook=_pairs)
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise BTCPerpetualSpecificationIntakeError("intake file is unreadable") from exc


def finalize_intake_document(body):
    if not isinstance(body,dict) or "intake_id" in body: raise BTCPerpetualSpecificationIntakeError("unfinalized intake body required")
    return {**body,"intake_id":hashlib.sha256(_canonical(body)).hexdigest()}


def compile_btc_perpetual_specification_intake(*,document,repository_root,bundle_path,as_of):
    keys={"schema_version","market","instrument_id","size_decimals","records","trading_authority","intake_id"}
    if not isinstance(document,dict) or set(document)!=keys: raise BTCPerpetualSpecificationIntakeError("intake fields do not match schema")
    body={key:document[key] for key in document if key!="intake_id"}
    try:_sha(document["intake_id"]);_time(as_of.isoformat())
    except (TypeError,ValueError): raise BTCPerpetualSpecificationIntakeError("intake identity or time is invalid")
    if (hashlib.sha256(_canonical(body)).hexdigest()!=document["intake_id"]
            or document["schema_version"]!=SCHEMA or document["market"]!="BTC-PERP"
            or document["instrument_id"]!="BTC" or document["trading_authority"] is not False
            or type(document["records"]) is not list):
        raise BTCPerpetualSpecificationIntakeError("intake identity or boundary is invalid")
    kinds=[];evidence=[];specs=[];instrument_values=None;instrument_evidence=None
    try:
        for item in document["records"]:
            if not isinstance(item,dict) or set(item)!=RECORD_KEYS or item["owner_approved"] is not True: raise ValueError
            kind=SpecificationType(item["specification_type"]);kinds.append(kind)
            if not isinstance(item["values"],dict) or not item["values"] or any(not isinstance(k,str) or not isinstance(v,str) or not k or not v for k,v in item["values"].items()): raise ValueError
            path=Path(item["local_snapshot_path"])
            if path.is_absolute() or path.drive or ".." in path.parts or "\\" in item["local_snapshot_path"]: raise ValueError
            _sha(item["snapshot_sha256"])
            retrieved=_time(item["retrieved_at"]);effective=_time(item["effective_from"])
            effective_to=None if item["effective_to"] is None else _time(item["effective_to"])
            assumptions=tuple(item["assumptions_and_gaps"])
            eid=canonical_fingerprint(SCHEMA,"evidence",item["source_organization"],item["document_identity"],
                item["canonical_url"],item["local_snapshot_path"],item["snapshot_sha256"],retrieved,effective,effective_to,
                "BTC-PERP","BTC",kind.value,assumptions)
            ev=EvidenceRecord(eid,item["source_organization"],item["document_identity"],item["canonical_url"],
                item["local_snapshot_path"],item["snapshot_sha256"],retrieved,effective,effective_to,
                "BTC-PERP","BTC",(kind.value,),assumptions)
            values=tuple(sorted(item["values"].items()))
            sid=canonical_fingerprint(SCHEMA,"specification",kind,"BTC-PERP","BTC",effective,effective_to,values,(eid,),True,False)
            spec=SpecificationRecord(sid,"economic-specification-v2-1",kind,"BTC-PERP","BTC",effective,effective_to,values,(eid,),True,False)
            evidence.append(ev);specs.append(spec)
            if kind is SpecificationType.INSTRUMENT: instrument_values=dict(values);instrument_evidence=eid
        if tuple(sorted(k.value for k in kinds))!=tuple(sorted(k.value for k in REQUIRED_TYPES)) or len(kinds)!=len(set(kinds)): raise ValueError
        required={"contract_id","contract_multiplier","currency","profile","quantity_step","tick_size"}
        if set(instrument_values)!=required or instrument_values["contract_id"]!="BTC-PERP" or instrument_values["profile"]!="BTC_LINEAR_PERPETUAL": raise ValueError
        instrument_spec=next(x for x in specs if x.specification_type is SpecificationType.INSTRUMENT)
        instrument=InstrumentSpecificationV2("instrument-spec-v2-1",instrument_spec.specification_id,"BTC-PERP","BTC","BTC-PERP",
            InstrumentProfile.BTC_LINEAR_PERPETUAL,instrument_values["currency"],Decimal(instrument_values["tick_size"]),
            Decimal(instrument_values["quantity_step"]),Decimal(instrument_values["contract_multiplier"]),None,
            instrument_spec.effective_from,instrument_spec.effective_to,(instrument_evidence,))
        precision=HyperliquidBTCPerpetualPrecisionV1.create(size_decimals=document["size_decimals"],source_evidence_ids=(instrument_evidence,))
        repository=SpecificationRepository(tuple(evidence),tuple(specs))
        eligibility=evaluate_btc_perpetual_economics(repository=repository,repository_root=repository_root,
            instrument=instrument,precision=precision,as_of=as_of)
    except (KeyError,TypeError,ValueError,InvalidOperation) as exc:
        raise BTCPerpetualSpecificationIntakeError("intake records are incomplete or invalid") from exc
    write_btc_perpetual_specification_bundle(bundle_path,repository,instrument,precision)
    return eligibility


def main():
    parser=argparse.ArgumentParser(description="Create or compile explicit BTC perpetual specification intake")
    commands=parser.add_subparsers(dest="command",required=True)
    template=commands.add_parser("template");template.add_argument("--output",type=Path,required=True)
    compile_cmd=commands.add_parser("compile");compile_cmd.add_argument("--input",type=Path,required=True)
    compile_cmd.add_argument("--repository-root",type=Path,required=True);compile_cmd.add_argument("--bundle",type=Path,required=True)
    compile_cmd.add_argument("--as-of",required=True)
    args=parser.parse_args()
    if args.command=="template":
        write_blank_intake_template(args.output);print(f"BTC_PERPETUAL_INTAKE_TEMPLATE_WRITTEN:{args.output}")
    else:
        result=compile_btc_perpetual_specification_intake(document=read_intake_document(args.input),
            repository_root=args.repository_root,bundle_path=args.bundle,as_of=_time(args.as_of))
        print(f"BTC_PERPETUAL_SPECIFICATION_BUNDLE_WRITTEN:{args.bundle}:{result.gate_id}")
    return 0


if __name__=="__main__": raise SystemExit(main())
