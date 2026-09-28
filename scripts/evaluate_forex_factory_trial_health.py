from __future__ import annotations
import hashlib,json,sys,uuid
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.forex_factory_trial_health_v1 import evaluate_trial_health
from scripts.associate_news_with_strategy_decisions import decisions
def dt(v):return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc)
def clean(v):
 if isinstance(v,datetime):return v.isoformat()
 if isinstance(v,tuple):return list(v)
 if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
 return v
def main():
 base=ROOT/'outputs/forex_factory_shadow_trial';latest=json.loads((base/'latest.json').read_text());raw=(base/'raw'/(latest['source_sha256']+'.json')).read_bytes();expected=decisions(set(latest['trial_days']));covered=[]
 for path in (base/'decision-diagnostics/events').glob('*.json'):
  row=json.loads(path.read_text());
  if row['source_snapshot_id']==latest['snapshot_id']:covered.append(row['decision']['decision_id'])
 gate=evaluate_trial_health(observed_at=datetime.now(timezone.utc),source_observed_at=dt(latest['observed_at']),source_hash_verified=hashlib.sha256(raw).hexdigest()==latest['source_sha256'],trial_days=tuple(latest['trial_days']),expected_decision_ids=tuple(x.decision_id for x in expected),covered_decision_ids=tuple(covered));doc=clean(asdict(gate));target=ROOT/'outputs/operational_health/forex-factory-trial-health.json';target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(doc,sort_keys=True,separators=(',',':')));tmp.replace(target);print(json.dumps(doc,separators=(',',':')))
if __name__=='__main__':main()
