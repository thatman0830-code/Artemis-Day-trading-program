"""Normalize one independently retained Databento day for research only."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe,GapPolicy,HistoricalDataset,normalize_historical_candle,validate_dataset
VERSION="databento-research-dataset-v2";INSTRUMENT={FuturesCanonicalMarket.ES:"MESU6",FuturesCanonicalMarket.NQ:"MNQU6"}
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def exact(value,field):
 if isinstance(value,float):raise ValueError("binary float forbidden for "+field)
 number=Decimal(str(value))
 if not number.is_finite()or number<0 or(field!="volume"and number==0):raise ValueError("invalid "+field)
 return number
def derive_complete_m5(candles,*,dataset_id):
 one_minute=tuple(c for c in candles if c.timeframe is CanonicalTimeframe.M1);buckets={}
 for candle in one_minute:
  opened=candle.open_time;bucket=opened.replace(minute=opened.minute-opened.minute%5,second=0,microsecond=0);buckets.setdefault(bucket,[]).append(candle)
 result=[]
 for opened,group in sorted(buckets.items()):
  ordered=tuple(sorted(group,key=lambda c:c.open_time));expected=tuple(opened+timedelta(minutes=i)for i in range(5))
  if len(ordered)!=5 or tuple(c.open_time for c in ordered)!=expected:continue
  volumes=tuple(c.volume for c in ordered);volume=None if any(v is None for v in volumes)else sum(volumes,Decimal('0'))
  result.append(normalize_historical_candle({"symbol":ordered[0].symbol,"timeframe":"5m","open_time":opened,"close_time":opened+timedelta(minutes=5),"open":ordered[0].open,"high":max(c.high for c in ordered),"low":min(c.low for c in ordered),"close":ordered[-1].close,"volume":volume,"is_closed":True},dataset_id=dataset_id,schema_version="historical-candle-v1",source="databento-historical-recovery",exchange="XCME"))
 return tuple(result)
@dataclass(frozen=True)
class DatabentoResearchDatasetV1:
 market:FuturesCanonicalMarket;instrument:str;day:str;dataset:HistoricalDataset;source_sha256:str;record_count:int;advisory_only:bool=True;paper_execution_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
 @property
 def chain_head_sha256(self):return self.source_sha256
def read_databento_research_dataset(root,*,market,day,as_of):
 if not isinstance(market,FuturesCanonicalMarket):raise TypeError("explicit market required")
 path=Path(root)/day/(market.value+".jsonl");manifest=Path(root)/day/"manifest.json"
 meta=json.loads(manifest.read_text());digest=meta.pop("manifest_sha256",None)
 if digest!=sha256(canonical(meta)).hexdigest()or meta.get("state")!="RECOVERY_EVIDENCE_RETAINED"or meta.get("trading_authority")is not False:raise ValueError("recovery manifest invalid")
 raw=path.read_bytes();lane=meta["lanes"][market.value]
 if sha256(raw).hexdigest()!=lane["sha256"]or lane["row_count"]!=len(raw.splitlines()):raise ValueError("recovery source hash invalid")
 dataset_id=sha256((VERSION+market.value+day+lane["sha256"]).encode()).hexdigest();candles=[]
 for line in raw.splitlines():
  row=json.loads(line);hd=row["hd"];opened=datetime.fromisoformat(hd["ts_event"].replace("Z","+00:00"));closed=opened+timedelta(minutes=1)
  candles.append(normalize_historical_candle({"symbol":market.value,"timeframe":"1m","open_time":opened,"close_time":closed,**{field:exact(row[field],field)for field in("open","high","low","close","volume")},"is_closed":True},dataset_id=dataset_id,schema_version="historical-candle-v1",source="databento-historical-recovery",exchange="XCME"))
 dataset=validate_dataset(tuple(candles),dataset_id=dataset_id,schema_version="historical-candle-v1",source="databento-historical-recovery",exchange="XCME",gap_policy=GapPolicy.RECORD,validation_time=as_of)
 return DatabentoResearchDatasetV1(market,INSTRUMENT[market],day,dataset,lane["sha256"],len(candles))
def read_databento_research_days(root,*,market,days,as_of):
 if not isinstance(days,tuple)or len(days)<2 or tuple(sorted(set(days)))!=days:raise ValueError("ordered distinct context days required")
 parts=tuple(read_databento_research_dataset(root,market=market,day=day,as_of=as_of)for day in days)
 combined=tuple(candle for part in parts for candle in part.dataset.candles);identity=sha256((VERSION+market.value+''.join(days)+''.join(part.source_sha256 for part in parts)).encode()).hexdigest()
 one_minute=tuple(normalize_historical_candle({"symbol":market.value,"timeframe":"1m","open_time":c.open_time,"close_time":c.close_time,"open":c.open,"high":c.high,"low":c.low,"close":c.close,"volume":c.volume,"is_closed":True},dataset_id=identity,schema_version="historical-candle-v1",source="databento-historical-recovery",exchange="XCME")for c in combined)
 candles=tuple(sorted(one_minute+derive_complete_m5(one_minute,dataset_id=identity),key=lambda c:(c.open_time,c.symbol,c.timeframe.value,c.id)))
 dataset=validate_dataset(candles,dataset_id=identity,schema_version="historical-candle-v1",source="databento-historical-recovery",exchange="XCME",gap_policy=GapPolicy.RECORD,validation_time=as_of);source=sha256(''.join(part.source_sha256 for part in parts).encode()).hexdigest()
 return DatabentoResearchDatasetV1(market,INSTRUMENT[market],days[-1],dataset,source,len(candles))
