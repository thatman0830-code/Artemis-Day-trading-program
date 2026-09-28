"""Promote one verified NinjaTrader closed-bar chain to a canonical smoke dataset."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
import hashlib,json
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import GapPolicy,HistoricalDataset,normalize_historical_candle,validate_dataset
from futures_data.sessions import IntervalClassification,SessionCalendar

VERSION="ninjatrader-closed-bar-dataset-v1";RECORD_VERSION="ninjatrader-closed-bar-recorder-v1"
_INSTRUMENT={FuturesCanonicalMarket.ES:"MES SEP26",FuturesCanonicalMarket.NQ:"MNQ SEP26"}
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _utc(v):
 value=datetime.fromisoformat(v.replace("Z","+00:00"))
 if value.tzinfo is None or value.utcoffset()!=timedelta(0):raise ValueError("UTC required")
 return value
@dataclass(frozen=True)
class NinjaTraderClosedBarDatasetV1:
 market:FuturesCanonicalMarket;instrument:str;day:str;dataset:HistoricalDataset;chain_head_sha256:str;record_count:int
 smoke_replay_eligible:bool=True;training_validation_eligible:bool=False;untouched_oos_eligible:bool=False
 advisory_only:bool=True;paper_execution_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def read_closed_bar_dataset(archive_root,*,market,day,as_of):
 if not isinstance(market,FuturesCanonicalMarket):raise TypeError("explicit ES or NQ market required")
 if not isinstance(day,str)or len(day)!=10:raise ValueError("ISO day required")
 if not isinstance(as_of,datetime)or as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0):raise ValueError("UTC as_of required")
 root=Path(archive_root)/market.value;chain=root/(day+".jsonl");manifest=root/"manifest.json";instrument=_INSTRUMENT[market]
 if not chain.is_file()or chain.is_symlink()or not manifest.is_file()or manifest.is_symlink():raise ValueError("plain archive evidence required")
 meta=json.loads(manifest.read_bytes());keys={"archive_file","head_record_sha256","instrument","last_close_time_utc","market","record_count","schema_version","state","trading_authority","unresolved_gap_count"};optional={"scheduled_non_trading_minute_count"}
 if(set(meta)-optional!=keys or meta["archive_file"]!=chain.name or meta["instrument"]!=instrument or meta["market"]!=market.value or meta["schema_version"]!=RECORD_VERSION or meta["state"]!="RECORDING" or meta["trading_authority"]is not False or meta["unresolved_gap_count"]!=0 or not isinstance(meta.get("scheduled_non_trading_minute_count",0),int) or meta.get("scheduled_non_trading_minute_count",0)<0):raise ValueError("archive manifest is ineligible")
 previous="0"*64;rows=[];prior=None
 for raw in chain.read_bytes().splitlines():
  doc=json.loads(raw);digest=doc.pop("record_sha256")
  required={"close","close_time_utc","high","instrument","low","market","open","open_time_utc","paper_only","previous_record_sha256","schema_version","source_payload_sha256","trading_authority","volume"}
  if(set(doc)!=required or doc["schema_version"]!=RECORD_VERSION or doc["previous_record_sha256"]!=previous or hashlib.sha256(_canonical(doc)).hexdigest()!=digest or doc["market"]!=market.value or doc["instrument"]!=instrument or doc["paper_only"]is not True or doc["trading_authority"]is not False):raise ValueError("closed-bar chain invalid")
  opened,closed=_utc(doc["open_time_utc"]),_utc(doc["close_time_utc"])
  if closed>as_of or closed-opened!=timedelta(minutes=1):raise ValueError("closed-bar chronology has a gap")
  if prior is not None and opened!=prior:
   cursor=prior
   while cursor<opened:
    if SessionCalendar().classify(cursor) is IntervalClassification.OPEN:raise ValueError("closed-bar chronology has an open-session gap")
    cursor+=timedelta(minutes=1)
  rows.append((opened,closed,*(Decimal(doc[x])for x in("open","high","low","close")),Decimal(doc["volume"])))
  previous=digest;prior=closed
 if not rows or meta["record_count"]!=len(rows)or meta["head_record_sha256"]!=previous or _utc(meta["last_close_time_utc"])!=rows[-1][1]:raise ValueError("manifest and chain differ")
 dataset_id=hashlib.sha256((VERSION+market.value+instrument+day+previous).encode()).hexdigest()
 candles=tuple(normalize_historical_candle({"symbol":market.value,"timeframe":"1m","open_time":r[0],"close_time":r[1],"open":r[2],"high":r[3],"low":r[4],"close":r[5],"volume":r[6],"is_closed":True},dataset_id=dataset_id,schema_version="historical-candle-v1",source="ninjatrader-simulation-closed-bars",exchange="XCME")for r in rows)
 dataset=validate_dataset(candles,dataset_id=dataset_id,schema_version="historical-candle-v1",source="ninjatrader-simulation-closed-bars",exchange="XCME",gap_policy=GapPolicy.RECORD,validation_time=as_of)
 return NinjaTraderClosedBarDatasetV1(market,instrument,day,dataset,previous,len(rows))
