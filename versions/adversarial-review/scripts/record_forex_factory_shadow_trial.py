from __future__ import annotations
import json,sys,urllib.request,uuid
from dataclasses import asdict
from datetime import date,datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.forex_factory_shadow_trial_v1 import POLICIES,classify_news_context,daily_risk_map,parse_snapshot
URL="https://nfs.faireconomy.media/ff_calendar_thisweek.json"
START=date(2026,9,9)

def clean(v):
 if isinstance(v,datetime):return v.isoformat()
 if isinstance(v,tuple):return[clean(x) for x in v]
 if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
 return v
def write(path,body):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name("."+path.name+"."+uuid.uuid4().hex+".tmp");tmp.write_bytes(body);tmp.replace(path)
def main():
 now=datetime.now(timezone.utc);request=urllib.request.Request(URL,headers={"User-Agent":"HermesResearchRecorder/1.0"})
 with urllib.request.urlopen(request,timeout=20)as response:raw=response.read()
 snapshot=parse_snapshot(raw,observed_at=now,start_day=START);doc=json.dumps(clean(asdict(snapshot)),sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
 base=ROOT/"outputs/forex_factory_shadow_trial";write(base/"raw"/(snapshot.source_sha256+".json"),raw);write(base/"snapshots"/(snapshot.snapshot_id+".json"),doc);write(base/"latest.json",doc)
 risk=json.dumps(daily_risk_map(snapshot),sort_keys=True,separators=(",",":")).encode();write(base/"daily-risk-map.json",risk)
 contexts=[clean(asdict(classify_news_context(events=snapshot.events,as_of=now,policy=policy)))for policy in POLICIES]
 comparison={"schema_version":"forex-factory-shadow-policy-comparison-v1","observed_at":now.isoformat(),"source_snapshot_id":snapshot.snapshot_id,"contexts":contexts,"metrics":{"baseline_decisions":0,"news_changed_decisions":0,"completed_outcomes":0,"status":"COLLECTING"},"strategy_confirmation":"PRICE_AND_VOLUME_REQUIRED_AFTER_NEWS","diagnostics_join_enabled":True,"pattern_analysis_enabled":True,"position_management":"COUNTERFACTUAL_RESEARCH_ONLY","order_influence_permitted":False,"trading_authority":False}
 write(base/"policy-comparison.json",json.dumps(comparison,sort_keys=True,separators=(",",":")).encode())
 print("FOREX_FACTORY_SHADOW_TRIAL_RECORDED:"+snapshot.snapshot_id)
if __name__=="__main__":main()
