"""Validate one complete signed MES/MNQ minute bar from NinjaTrader."""
from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
import hashlib,json,re
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket

SCHEMA="ninjatrader-closed-bar-v1"
_NAME=re.compile(r"^(MES|MNQ) SEP26$")
class NinjaTraderClosedBarError(ValueError):pass
@dataclass(frozen=True)
class NinjaTraderClosedBarV1:
 market:FuturesCanonicalMarket;instrument:str;open_time:datetime;close_time:datetime
 open:Decimal;high:Decimal;low:Decimal;close:Decimal;volume:int;payload_sha256:str
 complete_market_bar:bool=True;backtest_eligible:bool=True;signal_eligible:bool=False
 paper_only:bool=True;trading_authority:bool=False
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _utc(value):
 result=datetime.fromisoformat(value.replace("Z","+00:00"))
 if result.tzinfo is None or result.utcoffset()!=timedelta(0):raise ValueError
 return result
def read_closed_bar(*,path,as_of,maximum_age=timedelta(minutes=2)):
 try:
  path=Path(path)
  if not path.is_file()or path.is_symlink()or not isinstance(as_of,datetime)or as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0):raise ValueError
  raw=path.read_bytes()
  if len(raw)>4096:raise ValueError
  doc=json.loads(raw);digest=doc.pop("payload_sha256")
  expected={"close","close_time_utc","exchange","high","instrument","is_closed","low","open","open_time_utc","paper_only","schema_version","source","timeframe","trading_authority","volume"}
  if set(doc)!=expected or hashlib.sha256(_canonical(doc)).hexdigest()!=digest:raise ValueError
  match=_NAME.fullmatch(doc["instrument"])
  if (not match or doc["schema_version"]!=SCHEMA or doc["exchange"]!="XCME" or doc["source"]!="NINJATRADER_SIMULATION"
      or doc["timeframe"]!="1m" or doc["is_closed"] is not True or doc["paper_only"] is not True or doc["trading_authority"] is not False):raise ValueError
  opened,closed=_utc(doc["open_time_utc"]),_utc(doc["close_time_utc"])
  if closed-opened!=timedelta(minutes=1)or opened.second or opened.microsecond or closed>as_of or as_of-closed>maximum_age:raise ValueError
  prices=tuple(Decimal(str(doc[x]))for x in("open","high","low","close"))
  if any(not x.is_finite()or x<=0 for x in prices)or prices[1]<max(prices[0],prices[3])or prices[2]>min(prices[0],prices[3])or prices[1]<prices[2]:raise ValueError
  if type(doc["volume"])is not int or doc["volume"]<0:raise ValueError
  market=FuturesCanonicalMarket.ES if match.group(1)=="MES"else FuturesCanonicalMarket.NQ
  return NinjaTraderClosedBarV1(market,doc["instrument"],opened,closed,*prices,doc["volume"],digest)
 except (OSError,UnicodeError,json.JSONDecodeError,KeyError,TypeError,ValueError)as exc:raise NinjaTraderClosedBarError("NinjaTrader closed-bar evidence is invalid")from exc
