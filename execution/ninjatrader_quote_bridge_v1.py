"""Verify sanitized snapshots written by the isolated NinjaTrader indicator."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal,InvalidOperation
import hashlib,json,re
from pathlib import Path
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket

SCHEMA="ninjatrader-read-only-quote-v1"
class NinjaTraderQuoteBridgeError(ValueError):pass
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
@dataclass(frozen=True,slots=True)
class NinjaTraderQuoteSnapshotV1:
 market:FuturesCanonicalMarket;instrument:str;captured_at:datetime;bid:Decimal;ask:Decimal;last:Decimal;last_volume:int;sequence:int
 source:str="NINJATRADER_SIMULATION";entitlement_confirmed:bool=False;decision_use_permitted:bool=False
 paper_only:bool=True;trading_authority:bool=False
def read_quote_snapshot(*,path,as_of):
 try:
  p=Path(path)
  if p.is_symlink()or not p.is_file():raise ValueError
  doc=json.loads(p.read_bytes());digest=doc.pop("payload_sha256")
  if hashlib.sha256(_canonical(doc)).hexdigest()!=digest:raise ValueError
  if set(doc)!={"ask","bid","captured_at_utc","instrument","last","last_volume","paper_only","schema_version","sequence","source","trading_authority"}:raise ValueError
  if doc["schema_version"]!=SCHEMA or doc["source"]!="NINJATRADER_SIMULATION"or doc["paper_only"]is not True or doc["trading_authority"]is not False:raise ValueError
  match=re.fullmatch(r"(MES|MNQ)\s+(MAR|JUN|SEP|DEC)(\d{2})",doc["instrument"].upper())
  if not match:raise ValueError
  captured=datetime.fromisoformat(doc["captured_at_utc"].replace("Z","+00:00"))
  if any(x.tzinfo is None or x.utcoffset()!=timedelta(0)for x in(captured,as_of))or captured>as_of or as_of-captured>timedelta(seconds=1):raise ValueError
  bid,ask,last=(Decimal(str(doc[x]))for x in("bid","ask","last"))
  if any(not x.is_finite()or x<=0 for x in(bid,ask,last))or ask<bid:raise ValueError
  if any(isinstance(doc[x],bool)or not isinstance(doc[x],int)or doc[x]<0 for x in("last_volume","sequence"))or doc["sequence"]<1:raise ValueError
  market=FuturesCanonicalMarket.ES if match.group(1)=="MES"else FuturesCanonicalMarket.NQ
  return NinjaTraderQuoteSnapshotV1(market,doc["instrument"],captured,bid,ask,last,doc["last_volume"],doc["sequence"])
 except(OSError,KeyError,TypeError,ValueError,InvalidOperation,json.JSONDecodeError)as exc:
  raise NinjaTraderQuoteBridgeError("NinjaTrader quote evidence is invalid")from exc
