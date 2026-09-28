"""Validate and retain public BTC L2 depth for paper-impact research only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation,localcontext
import hashlib,json,os
from pathlib import Path
import uuid

VERSION="btc-perpetual-l2-evidence-v1"
ENDPOINT="https://api.hyperliquid.xyz/info"
REQUEST_BYTES=b'{"coin":"BTC","type":"l2Book"}'
MAXIMUM_BYTES=512*1024
PAPER_NOTIONAL=Decimal("100")


class BTCL2EvidenceError(ValueError):pass


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise BTCL2EvidenceError("duplicate provider JSON field")
        result[key]=value
    return result
def _positive(value,name):
    if not isinstance(value,str):raise BTCL2EvidenceError(f"{name} must use string decimal encoding")
    try:result=Decimal(value)
    except InvalidOperation as exc:raise BTCL2EvidenceError(f"{name} is invalid") from exc
    if not result.is_finite() or result<=0:raise BTCL2EvidenceError(f"{name} is invalid")
    return result


@dataclass(frozen=True,slots=True)
class BTCL2EvidenceV1:
    captured_at:datetime
    observed_at:datetime
    response_sha256:str
    raw_relative_path:str
    best_bid:Decimal
    best_ask:Decimal
    midpoint:Decimal
    spread_bps:Decimal
    buy_vwap_100:Decimal
    sell_vwap_100:Decimal
    buy_impact_bps_100:Decimal
    sell_impact_bps_100:Decimal
    bid_depth_notional:Decimal
    ask_depth_notional:Decimal
    maximum_observed_participation_percent:Decimal
    receipt_id:str
    policy_approved:bool=False
    trading_authority:bool=False

    def __post_init__(self):
        if (any(x.tzinfo is None or x.utcoffset()!=timedelta(0) for x in (self.captured_at,self.observed_at))
                or not self.observed_at<=self.captured_at<=self.observed_at+timedelta(seconds=5)
                or self.policy_approved is not False or self.trading_authority is not False):raise BTCL2EvidenceError("L2 evidence chronology or authority is invalid")
        if len(self.response_sha256)!=64 or any(character not in "0123456789abcdef" for character in self.response_sha256):raise BTCL2EvidenceError("L2 response hash is invalid")
        if any(type(x) is not Decimal or not x.is_finite() or x<=0 for x in (
                self.best_bid,self.best_ask,self.midpoint,self.buy_vwap_100,self.sell_vwap_100,
                self.bid_depth_notional,self.ask_depth_notional)):
            raise BTCL2EvidenceError("L2 prices or depth are invalid")
        if any(type(x) is not Decimal or not x.is_finite() or x<0 for x in (self.spread_bps,self.buy_impact_bps_100,self.sell_impact_bps_100,self.maximum_observed_participation_percent)):raise BTCL2EvidenceError("L2 metrics are invalid")
        body={name:(value.isoformat() if isinstance(value,datetime) else str(value) if isinstance(value,Decimal) else value)
            for name,value in ((n,getattr(self,n)) for n in self.__dataclass_fields__) if name!="receipt_id"}
        body={"version":VERSION,**body}
        if hashlib.sha256(_canonical(body)).hexdigest()!=self.receipt_id:raise BTCL2EvidenceError("L2 receipt identity mismatch")


def _side(rows,name,descending):
    if type(rows) is not list or not 1<=len(rows)<=20:raise BTCL2EvidenceError(f"{name} depth is invalid")
    parsed=[]
    for row in rows:
        if not isinstance(row,dict) or not {"px","sz","n"}.issubset(row):raise BTCL2EvidenceError(f"{name} level is invalid")
        px=_positive(row["px"],"px");sz=_positive(row["sz"],"sz")
        if type(row["n"]) is not int or row["n"]<=0:raise BTCL2EvidenceError("level order count is invalid")
        parsed.append((px,sz))
    prices=[x[0] for x in parsed]
    if len(prices)!=len(set(prices)) or prices!=sorted(prices,reverse=descending):raise BTCL2EvidenceError(f"{name} levels are not strictly ordered")
    return tuple(parsed)


def _vwap(levels,quantity):
    remaining=quantity;total=Decimal(0)
    for price,size in levels:
        used=min(size,remaining);total+=used*price;remaining-=used
        if remaining==0:break
    if remaining>0:raise BTCL2EvidenceError("insufficient retained depth for $100 observation")
    return total/quantity


def validate_btc_l2_response(*,payload:bytes,captured_at:datetime,raw_relative_path:str):
    if captured_at.tzinfo is None or captured_at.utcoffset()!=timedelta(0):raise BTCL2EvidenceError("capture time must be UTC")
    if type(payload) is not bytes or not 0<len(payload)<=MAXIMUM_BYTES:raise BTCL2EvidenceError("L2 response size is invalid")
    path=Path(raw_relative_path)
    if path.is_absolute() or path.drive or ".." in path.parts or "\\" in raw_relative_path:raise BTCL2EvidenceError("raw path is unsafe")
    try:value=json.loads(payload,object_pairs_hook=_pairs)
    except (UnicodeError,json.JSONDecodeError) as exc:raise BTCL2EvidenceError("L2 response is invalid JSON") from exc
    if not isinstance(value,dict) or value.get("coin")!="BTC" or set(value)!={"coin","time","levels"}:raise BTCL2EvidenceError("L2 envelope is invalid")
    millis=value["time"]
    if type(millis) is not int or millis<0 or type(value["levels"]) is not list or len(value["levels"])!=2:raise BTCL2EvidenceError("L2 time or sides are invalid")
    observed=datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(milliseconds=millis)
    if not observed<=captured_at<=observed+timedelta(seconds=5):raise BTCL2EvidenceError("L2 response is stale or future-dated")
    bids=_side(value["levels"][0],"bid",True);asks=_side(value["levels"][1],"ask",False)
    best_bid=bids[0][0];best_ask=asks[0][0]
    if best_bid>=best_ask:raise BTCL2EvidenceError("L2 book is locked or crossed")
    with localcontext() as context:
        context.prec=80;mid=(best_bid+best_ask)/2;quantity=PAPER_NOTIONAL/mid
        buy=_vwap(asks,quantity);sell=_vwap(bids,quantity)
        spread=(best_ask-best_bid)/mid*Decimal(10000)
        buy_impact=(buy-mid)/mid*Decimal(10000);sell_impact=(mid-sell)/mid*Decimal(10000)
        bid_depth=sum((p*s for p,s in bids),Decimal(0));ask_depth=sum((p*s for p,s in asks),Decimal(0))
        participation=PAPER_NOTIONAL/min(bid_depth,ask_depth)*Decimal(100)
    response_hash=hashlib.sha256(payload).hexdigest()
    values=dict(captured_at=captured_at,observed_at=observed,response_sha256=response_hash,
        raw_relative_path=raw_relative_path,best_bid=best_bid,best_ask=best_ask,midpoint=mid,
        spread_bps=spread,buy_vwap_100=buy,sell_vwap_100=sell,buy_impact_bps_100=buy_impact,
        sell_impact_bps_100=sell_impact,bid_depth_notional=bid_depth,ask_depth_notional=ask_depth,
        maximum_observed_participation_percent=participation,policy_approved=False,trading_authority=False)
    body={name:(v.isoformat() if isinstance(v,datetime) else str(v) if isinstance(v,Decimal) else v) for name,v in values.items()}
    receipt_id=hashlib.sha256(_canonical({"version":VERSION,**body})).hexdigest()
    return BTCL2EvidenceV1(**values,receipt_id=receipt_id)


def collect_btc_l2_evidence(*,transport,output_root,captured_at,timeout_seconds=10):
    if not callable(transport) or type(timeout_seconds) is not int or not 1<=timeout_seconds<=15:raise BTCL2EvidenceError("collector dependency or timeout is invalid")
    status,payload=transport(ENDPOINT,REQUEST_BYTES,{"Content-Type":"application/json"},timeout_seconds)
    if status!=200:raise BTCL2EvidenceError("L2 request failed")
    capture_time=captured_at(timezone.utc) if callable(captured_at) else captured_at
    digest=hashlib.sha256(payload).hexdigest() if isinstance(payload,bytes) else "invalid"
    receipt=validate_btc_l2_response(payload=payload,captured_at=capture_time,raw_relative_path=f"raw/{digest}.json")
    root=Path(output_root).absolute()
    if root.is_symlink() or not root.is_dir():raise BTCL2EvidenceError("evidence root is unsafe")
    raw=root/receipt.raw_relative_path;raw.parent.mkdir(exist_ok=True)
    if raw.parent.is_symlink() or not raw.parent.is_dir() or not raw.resolve().is_relative_to(root.resolve()):raise BTCL2EvidenceError("raw evidence directory is unsafe")
    document={name:(v.isoformat() if isinstance(v,datetime) else str(v) if isinstance(v,Decimal) else v) for name,v in ((n,getattr(receipt,n)) for n in receipt.__dataclass_fields__)}
    for path,data in ((raw,payload),(root/f"{receipt.receipt_id}.receipt.json",_canonical(document)+b"\n")):
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=data:raise BTCL2EvidenceError("retained L2 evidence conflict")
            continue
        temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary,"xb") as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
        finally:temporary.unlink(missing_ok=True)
    return receipt
