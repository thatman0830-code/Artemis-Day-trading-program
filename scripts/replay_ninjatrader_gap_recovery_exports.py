"""Run isolated canonical replay on complete MES/MNQ NinjaTrader exports."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import argparse,json,os,uuid
from dataclasses import asdict
from datetime import datetime,timezone
from enum import Enum
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_historical_export_v1 import read_ninjatrader_historical_export
from backtesting.ninjatrader_export_canonical_replay_v1 import evaluate_ninjatrader_export

SPECS={FuturesCanonicalMarket.ES:"8ca4cd9fe42ab3816b946df409e43f22d9bca2dc0aa3bece74707daf4efa16a5",FuturesCanonicalMarket.NQ:"f3d54999d53d2f460db25f67acc5bf3634b927cbe2bfb675b360d81c7aba63f8"}
def clean(v):
 if isinstance(v,Enum):return v.value
 if isinstance(v,tuple):return[clean(x)for x in v]
 if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
 return v
def main():
 p=argparse.ArgumentParser();p.add_argument("--mes",required=True);p.add_argument("--mnq",required=True);p.add_argument("--start");p.add_argument("--end");a=p.parse_args();now=datetime.now(timezone.utc);reports=[]
 start=datetime.fromisoformat(a.start) if a.start else None;end=datetime.fromisoformat(a.end) if a.end else None
 for market,path in ((FuturesCanonicalMarket.ES,a.mes),(FuturesCanonicalMarket.NQ,a.mnq)):
  evidence=read_ninjatrader_historical_export(path,market=market,as_of=now,start_at=start,end_at=end);reports.append(clean(asdict(evaluate_ninjatrader_export(evidence=evidence,specification_id=SPECS[market],as_of=now))))
 result={"schema_version":"ninjatrader-gap-recovery-canonical-replay-cycle-v1","state":"COMPLETE","reports":reports,"cross_source_equivalence_claimed":False,"paper_execution_permitted":False,"trading_authority":False}
 target=ROOT/"outputs/ninjatrader_gap_recovery/canonical-replay.json";target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_name("."+target.name+"."+uuid.uuid4().hex+".tmp")
 try:
  with tmp.open("x")as f:json.dump(result,f,sort_keys=True,separators=(",",":"));f.flush();os.fsync(f.fileno())
  os.replace(tmp,target)
 finally:tmp.unlink(missing_ok=True)
 print(json.dumps(result,sort_keys=True,separators=(",",":")));return 0
if __name__=="__main__":raise SystemExit(main())
