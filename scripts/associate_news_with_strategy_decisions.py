from __future__ import annotations
import json,sys,uuid
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.forex_factory_shadow_trial_v1 import NewsEventV1
from research.news_decision_diagnostics_v1 import DecisionFactV1,associate,scorecard
def dt(v):return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc)
def clean(v):
 if isinstance(v,datetime):return v.isoformat()
 if isinstance(v,tuple):return[clean(x)for x in v]
 if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
 return v
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(clean(value),sort_keys=True,separators=(',',':')),encoding='utf-8');tmp.replace(path)
def decisions(days):
 found={}
 for path in (ROOT/'outputs/ninjatrader_canonical_smoke_history').glob('*/events/*.json'):
  row=json.loads(path.read_text(encoding='utf-8-sig'));report=row['report'];when=dt(report['evaluated_at'])
  if when.date().isoformat()in days:found[report['report_id']]=DecisionFactV1(report['report_id'],report['market'],when,report['latest_outcome'])
 for path in (ROOT/'outputs/paper_sessions').glob('*/canonical-strategy-status.json'):
  row=json.loads(path.read_text(encoding='utf-8-sig'));when=dt(row['observed_at'])
  if when.date().isoformat()in days:found[row['status_id']]=DecisionFactV1(row['status_id'],'BTC-PERP',when,row.get('result_outcome')or row['state'])
 return tuple(sorted(found.values(),key=lambda x:(x.decided_at,x.market,x.decision_id)))
def main():
 latest=json.loads((ROOT/'outputs/forex_factory_shadow_trial/latest.json').read_text());events=tuple(NewsEventV1(x['event_id'],x['title'],x['currency'],dt(x['scheduled_at']),x['impact'],x['forecast'],x['previous'],x['actual'])for x in latest['events']);days=tuple(latest['trial_days'])
 diagnostics=tuple(associate(decision=x,events=events,source_snapshot_id=latest['snapshot_id'])for x in decisions(set(days)));base=ROOT/'outputs/forex_factory_shadow_trial/decision-diagnostics'
 for item in diagnostics:write(base/'events'/(item.diagnostic_id+'.json'),asdict(item))
 result=scorecard(diagnostics=diagnostics,trial_days=days,as_of=datetime.now(timezone.utc));write(base/'scorecard.json',result);print(json.dumps(result,separators=(',',':')))
if __name__=='__main__':main()
