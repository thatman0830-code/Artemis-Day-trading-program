"""Retain and validate public Hyperliquid BTC perpetual metadata evidence.

Network acquisition is dependency-injected. This module contains no credential,
account, signing, order, or trading transport.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal,InvalidOperation
import hashlib,json,os
from pathlib import Path
import uuid

VERSION="btc-perpetual-public-evidence-collector-v1"
ENDPOINT="https://api.hyperliquid.xyz/info"
REQUEST_BYTES=b'{"type":"metaAndAssetCtxs"}'
MAXIMUM_BYTES=2*1024*1024


class BTCPerpetualPublicEvidenceError(ValueError): pass


def _canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise BTCPerpetualPublicEvidenceError("duplicate provider JSON field")
        result[key]=value
    return result
def _decimal(value,name):
    if not isinstance(value,str): raise BTCPerpetualPublicEvidenceError(f"{name} must use string decimal encoding")
    try: result=Decimal(value)
    except InvalidOperation as exc: raise BTCPerpetualPublicEvidenceError(f"{name} is invalid") from exc
    if not result.is_finite() or (name in ("markPx","oraclePx") and result<=0): raise BTCPerpetualPublicEvidenceError(f"{name} is invalid")
    return result
def _sha(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value): raise BTCPerpetualPublicEvidenceError("invalid SHA-256")


@dataclass(frozen=True,slots=True)
class BTCPerpetualPublicEvidenceV1:
    captured_at:datetime
    response_sha256:str
    byte_count:int
    asset_index:int
    size_decimals:int
    maximum_leverage:int
    margin_table_id:int
    mark_price:Decimal
    oracle_price:Decimal
    funding_rate:Decimal
    raw_relative_path:str
    receipt_id:str
    trading_authority:bool=False

    def __post_init__(self):
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset()!=timedelta(0): raise BTCPerpetualPublicEvidenceError("capture time must be UTC")
        _sha(self.response_sha256);_sha(self.receipt_id)
        if (type(self.byte_count) is not int or not 0<self.byte_count<=MAXIMUM_BYTES
                or type(self.asset_index) is not int or self.asset_index<0
                or type(self.size_decimals) is not int or not 0<=self.size_decimals<=6
                or type(self.maximum_leverage) is not int or self.maximum_leverage<=0
                or type(self.margin_table_id) is not int or self.margin_table_id<0
                or self.trading_authority is not False): raise BTCPerpetualPublicEvidenceError("public evidence fields are invalid")
        body={"version":VERSION,"captured_at":self.captured_at.isoformat(),"endpoint":ENDPOINT,
            "request_sha256":hashlib.sha256(REQUEST_BYTES).hexdigest(),"response_sha256":self.response_sha256,
            "byte_count":self.byte_count,"asset_index":self.asset_index,"asset":"BTC",
            "size_decimals":self.size_decimals,"maximum_leverage":self.maximum_leverage,
            "margin_table_id":self.margin_table_id,"mark_price":str(self.mark_price),
            "oracle_price":str(self.oracle_price),"funding_rate":str(self.funding_rate),
            "raw_relative_path":self.raw_relative_path,"trading_authority":False}
        if hashlib.sha256(_canonical(body)).hexdigest()!=self.receipt_id: raise BTCPerpetualPublicEvidenceError("receipt identity mismatch")


def validate_btc_perpetual_public_response(*,payload:bytes,captured_at:datetime,raw_relative_path:str):
    if captured_at.tzinfo is None or captured_at.utcoffset()!=timedelta(0): raise BTCPerpetualPublicEvidenceError("capture time must be UTC")
    if type(payload) is not bytes or not 0<len(payload)<=MAXIMUM_BYTES: raise BTCPerpetualPublicEvidenceError("provider response size is invalid")
    path=Path(raw_relative_path)
    if path.is_absolute() or path.drive or ".." in path.parts or "\\" in raw_relative_path: raise BTCPerpetualPublicEvidenceError("raw evidence path is unsafe")
    try: value=json.loads(payload,object_pairs_hook=_pairs)
    except (UnicodeError,json.JSONDecodeError) as exc: raise BTCPerpetualPublicEvidenceError("provider response is invalid JSON") from exc
    if type(value) is not list or len(value)!=2 or not isinstance(value[0],dict) or not isinstance(value[1],list): raise BTCPerpetualPublicEvidenceError("provider response envelope is invalid")
    universe=value[0].get("universe")
    if type(universe) is not list or len(universe)!=len(value[1]): raise BTCPerpetualPublicEvidenceError("metadata/context cardinality mismatch")
    matches=[(index,item) for index,item in enumerate(universe) if isinstance(item,dict) and item.get("name")=="BTC"]
    if len(matches)!=1: raise BTCPerpetualPublicEvidenceError("unique BTC perpetual metadata is required")
    index,asset=matches[0];context=value[1][index]
    if not isinstance(context,dict): raise BTCPerpetualPublicEvidenceError("BTC asset context is invalid")
    required_asset=("szDecimals","maxLeverage","marginTableId")
    required_context=("markPx","oraclePx","funding")
    if any(key not in asset for key in required_asset) or any(key not in context for key in required_context): raise BTCPerpetualPublicEvidenceError("required BTC public facts are absent")
    size=asset["szDecimals"];leverage=asset["maxLeverage"];margin=asset["marginTableId"]
    mark=_decimal(context["markPx"],"markPx");oracle=_decimal(context["oraclePx"],"oraclePx");funding=_decimal(context["funding"],"funding")
    response_hash=hashlib.sha256(payload).hexdigest()
    body={"version":VERSION,"captured_at":captured_at.isoformat(),"endpoint":ENDPOINT,
        "request_sha256":hashlib.sha256(REQUEST_BYTES).hexdigest(),"response_sha256":response_hash,
        "byte_count":len(payload),"asset_index":index,"asset":"BTC","size_decimals":size,
        "maximum_leverage":leverage,"margin_table_id":margin,"mark_price":str(mark),
        "oracle_price":str(oracle),"funding_rate":str(funding),"raw_relative_path":raw_relative_path,
        "trading_authority":False}
    receipt=BTCPerpetualPublicEvidenceV1(captured_at,response_hash,len(payload),index,size,leverage,margin,
        mark,oracle,funding,raw_relative_path,hashlib.sha256(_canonical(body)).hexdigest(),False)
    return receipt


def collect_btc_perpetual_public_evidence(*,transport,output_root,captured_at,timeout_seconds=10):
    if not callable(transport) or type(timeout_seconds) is not int or not 1<=timeout_seconds<=15: raise BTCPerpetualPublicEvidenceError("collector dependency or timeout is invalid")
    status,payload=transport(ENDPOINT,REQUEST_BYTES,{"Content-Type":"application/json"},timeout_seconds)
    if status!=200: raise BTCPerpetualPublicEvidenceError("public metadata request failed")
    response_hash=hashlib.sha256(payload).hexdigest() if isinstance(payload,bytes) else "invalid"
    relative=f"raw/{response_hash}.json"
    receipt=validate_btc_perpetual_public_response(payload=payload,captured_at=captured_at,raw_relative_path=relative)
    root=Path(output_root).absolute()
    if root.is_symlink() or not root.is_dir(): raise BTCPerpetualPublicEvidenceError("evidence root is unsafe")
    raw=root/relative;raw.parent.mkdir(exist_ok=True)
    if raw.parent.is_symlink() or not raw.parent.is_dir() or not raw.resolve().is_relative_to(root.resolve()):
        raise BTCPerpetualPublicEvidenceError("raw evidence directory is unsafe")
    receipt_path=root/f"{receipt.receipt_id}.receipt.json"
    document={name:(value.isoformat() if isinstance(value,datetime) else str(value) if isinstance(value,Decimal) else value)
        for name,value in ((n,getattr(receipt,n)) for n in receipt.__dataclass_fields__)}
    for path,data in ((raw,payload),(receipt_path,_canonical(document)+b"\n")):
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=data: raise BTCPerpetualPublicEvidenceError("retained evidence conflict")
            continue
        temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary,"xb") as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
        finally: temporary.unlink(missing_ok=True)
    return receipt


def read_btc_perpetual_public_evidence(*,output_root,receipt_path):
    root=Path(output_root).absolute();path=Path(receipt_path).absolute()
    if (root.is_symlink() or path.is_symlink() or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve()) or not 0<path.stat().st_size<=65536):
        raise BTCPerpetualPublicEvidenceError("receipt path is unsafe")
    try: doc=json.loads(path.read_bytes(),object_pairs_hook=_pairs)
    except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise BTCPerpetualPublicEvidenceError("receipt is unreadable") from exc
    keys=set(BTCPerpetualPublicEvidenceV1.__dataclass_fields__)
    if not isinstance(doc,dict) or set(doc)!=keys: raise BTCPerpetualPublicEvidenceError("receipt fields do not match schema")
    try:
        receipt=BTCPerpetualPublicEvidenceV1(datetime.fromisoformat(doc["captured_at"]),doc["response_sha256"],
            doc["byte_count"],doc["asset_index"],doc["size_decimals"],doc["maximum_leverage"],
            doc["margin_table_id"],Decimal(doc["mark_price"]),Decimal(doc["oracle_price"]),
            Decimal(doc["funding_rate"]),doc["raw_relative_path"],doc["receipt_id"],doc["trading_authority"])
        raw=root/receipt.raw_relative_path
        if raw.is_symlink() or not raw.is_file() or not raw.resolve().is_relative_to(root.resolve()): raise ValueError
        rebuilt=validate_btc_perpetual_public_response(payload=raw.read_bytes(),captured_at=receipt.captured_at,
            raw_relative_path=receipt.raw_relative_path)
    except (TypeError,ValueError,InvalidOperation) as exc: raise BTCPerpetualPublicEvidenceError("receipt or raw evidence is invalid") from exc
    if rebuilt!=receipt: raise BTCPerpetualPublicEvidenceError("receipt conflicts with raw evidence")
    return receipt
