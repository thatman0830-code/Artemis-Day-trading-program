"""Canonical persistence for owner-approved BTC perpetual economic evidence."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal,InvalidOperation
import hashlib,json,os
from pathlib import Path
import uuid

from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2
from backtesting.execution_accounting_v2.specifications import (
    EvidenceRecord,InstrumentProfile,SpecificationRecord,SpecificationRepository,SpecificationType,
)
from execution.hyperliquid_perpetual_precision_v1 import HyperliquidBTCPerpetualPrecisionV1

SCHEMA="btc-perpetual-specification-bundle-v1"
MAXIMUM_BYTES=4*1024*1024


class BTCPerpetualSpecificationBundleError(ValueError): pass


def _canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _time(value):
    result=datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset().total_seconds()!=0: raise ValueError
    return result
def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise BTCPerpetualSpecificationBundleError("duplicate JSON field")
        result[key]=value
    return result
def _exact(value,keys,name):
    if not isinstance(value,dict) or set(value)!=set(keys):
        raise BTCPerpetualSpecificationBundleError(f"{name} fields do not match schema")
    return value
def _sha(value,name):
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise BTCPerpetualSpecificationBundleError(f"{name} must be lowercase SHA-256")


def bundle_document(repository,instrument,precision):
    if not isinstance(repository,SpecificationRepository): raise BTCPerpetualSpecificationBundleError("typed repository required")
    if not isinstance(instrument,InstrumentSpecificationV2): raise BTCPerpetualSpecificationBundleError("typed instrument required")
    if not isinstance(precision,HyperliquidBTCPerpetualPrecisionV1): raise BTCPerpetualSpecificationBundleError("typed precision required")
    repository.__post_init__();instrument.__post_init__();precision.__post_init__()
    evidence=[{"evidence_id":x.evidence_id,"source_organization":x.source_organization,
        "document_identity":x.document_identity,"canonical_url":x.canonical_url,
        "local_snapshot_path":x.local_snapshot_path,"snapshot_sha256":x.snapshot_sha256,
        "retrieved_at":x.retrieved_at.isoformat(),"effective_from":x.effective_from.isoformat(),
        "effective_to":None if x.effective_to is None else x.effective_to.isoformat(),"market":x.market,
        "instrument_id":x.instrument_id,"fact_names":list(x.fact_names),
        "assumptions_and_gaps":list(x.assumptions_and_gaps),"schema_version":x.schema_version}
        for x in repository.evidence]
    specifications=[{"specification_id":x.specification_id,"schema_version":x.schema_version,
        "specification_type":x.specification_type.value,"market":x.market,"instrument_id":x.instrument_id,
        "effective_from":x.effective_from.isoformat(),"effective_to":None if x.effective_to is None else x.effective_to.isoformat(),
        "values":[list(v) for v in x.values],"evidence_ids":list(x.evidence_ids),
        "owner_approved":x.owner_approved,"synthetic_test_only":x.synthetic_test_only}
        for x in repository.specifications]
    inst={"schema_version":instrument.schema_version,"specification_id":instrument.specification_id,
        "market":instrument.market,"instrument_id":instrument.instrument_id,"contract_id":instrument.contract_id,
        "profile":instrument.profile.value,"currency":instrument.currency,"tick_size":str(instrument.tick_size),
        "quantity_step":str(instrument.quantity_step),"contract_multiplier":str(instrument.contract_multiplier),
        "point_value":None if instrument.point_value is None else str(instrument.point_value),
        "effective_from":instrument.effective_from.isoformat(),"effective_to":None if instrument.effective_to is None else instrument.effective_to.isoformat(),
        "evidence_ids":list(instrument.evidence_ids)}
    prec={"size_decimals":precision.size_decimals,"quantity_step":str(precision.quantity_step),
        "source_evidence_ids":list(precision.source_evidence_ids),"precision_id":precision.precision_id,
        "trading_authority":False}
    body={"schema_version":SCHEMA,"evidence":evidence,"specifications":specifications,
        "instrument":inst,"precision":prec,"trading_authority":False}
    return {**body,"bundle_id":hashlib.sha256(_canonical(body)).hexdigest()}


def write_btc_perpetual_specification_bundle(path,repository,instrument,precision):
    path=Path(path)
    if path.parent.is_symlink() or not path.parent.is_dir(): raise BTCPerpetualSpecificationBundleError("bundle parent is unsafe")
    payload=_canonical(bundle_document(repository,instrument,precision))+b"\n"
    temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary,"xb") as stream: stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally: temporary.unlink(missing_ok=True)


def read_btc_perpetual_specification_bundle(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAXIMUM_BYTES:
        raise BTCPerpetualSpecificationBundleError("bundle file is missing or unsafe")
    before=path.stat()
    try: payload=path.read_bytes();after=path.stat();doc=json.loads(payload,object_pairs_hook=_pairs)
    except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise BTCPerpetualSpecificationBundleError("bundle is unreadable") from exc
    if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns) or len(payload)!=before.st_size:
        raise BTCPerpetualSpecificationBundleError("bundle changed during read")
    keys={"schema_version","evidence","specifications","instrument","precision","trading_authority","bundle_id"}
    _exact(doc,keys,"bundle")
    body={k:doc[k] for k in doc if k!="bundle_id"}
    if doc["schema_version"]!=SCHEMA or doc["trading_authority"] is not False or hashlib.sha256(_canonical(body)).hexdigest()!=doc["bundle_id"]:
        raise BTCPerpetualSpecificationBundleError("bundle identity or authority is invalid")
    try:
        if type(doc["evidence"]) is not list or type(doc["specifications"]) is not list:
            raise TypeError
        for x in doc["evidence"]:
            _exact(x,{"evidence_id","source_organization","document_identity","canonical_url","local_snapshot_path",
                "snapshot_sha256","retrieved_at","effective_from","effective_to","market","instrument_id",
                "fact_names","assumptions_and_gaps","schema_version"},"evidence")
            _sha(x["evidence_id"],"evidence_id");_sha(x["snapshot_sha256"],"snapshot_sha256")
            if x["market"]!="BTC-PERP" or x["instrument_id"]!="BTC": raise ValueError
        for x in doc["specifications"]:
            _exact(x,{"specification_id","schema_version","specification_type","market","instrument_id",
                "effective_from","effective_to","values","evidence_ids","owner_approved","synthetic_test_only"},"specification")
            _sha(x["specification_id"],"specification_id")
            if (x["market"],x["instrument_id"])!=("BTC-PERP","BTC") or x["owner_approved"] is not True or x["synthetic_test_only"] is not False: raise ValueError
        _exact(doc["instrument"],{"schema_version","specification_id","market","instrument_id","contract_id","profile",
            "currency","tick_size","quantity_step","contract_multiplier","point_value","effective_from","effective_to","evidence_ids"},"instrument")
        _exact(doc["precision"],{"size_decimals","quantity_step","source_evidence_ids","precision_id","trading_authority"},"precision")
        _sha(doc["bundle_id"],"bundle_id");_sha(doc["precision"]["precision_id"],"precision_id")
        if doc["precision"]["trading_authority"] is not False: raise ValueError
        evidence=tuple(EvidenceRecord(x["evidence_id"],x["source_organization"],x["document_identity"],x["canonical_url"],
            x["local_snapshot_path"],x["snapshot_sha256"],_time(x["retrieved_at"]),_time(x["effective_from"]),
            None if x["effective_to"] is None else _time(x["effective_to"]),x["market"],x["instrument_id"],
            tuple(x["fact_names"]),tuple(x["assumptions_and_gaps"]),x["schema_version"]) for x in doc["evidence"])
        specs=tuple(SpecificationRecord(x["specification_id"],x["schema_version"],SpecificationType(x["specification_type"]),
            x["market"],x["instrument_id"],_time(x["effective_from"]),None if x["effective_to"] is None else _time(x["effective_to"]),
            tuple(tuple(v) for v in x["values"]),tuple(x["evidence_ids"]),x["owner_approved"],x["synthetic_test_only"])
            for x in doc["specifications"])
        x=doc["instrument"]
        instrument=InstrumentSpecificationV2(x["schema_version"],x["specification_id"],x["market"],x["instrument_id"],
            x["contract_id"],InstrumentProfile(x["profile"]),x["currency"],Decimal(x["tick_size"]),Decimal(x["quantity_step"]),
            Decimal(x["contract_multiplier"]),None if x["point_value"] is None else Decimal(x["point_value"]),
            _time(x["effective_from"]),None if x["effective_to"] is None else _time(x["effective_to"]),tuple(x["evidence_ids"]))
        p=doc["precision"]
        precision=HyperliquidBTCPerpetualPrecisionV1(p["size_decimals"],Decimal(p["quantity_step"]),
            tuple(p["source_evidence_ids"]),p["precision_id"],p["trading_authority"])
        repository=SpecificationRepository(evidence,specs)
    except (KeyError,TypeError,ValueError,InvalidOperation) as exc:
        raise BTCPerpetualSpecificationBundleError("bundle records are invalid") from exc
    if bundle_document(repository,instrument,precision)!=doc:
        raise BTCPerpetualSpecificationBundleError("bundle canonical reconstruction failed")
    return repository,instrument,precision,doc["bundle_id"]
