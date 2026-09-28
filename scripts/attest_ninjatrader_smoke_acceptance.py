"""Publish the current completed ES/NQ smoke acceptance attestation."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataclasses import asdict
from datetime import datetime,timezone
import json,os,uuid
from backtesting.ninjatrader_smoke_acceptance_v1 import attest_ninjatrader_smoke_acceptance
from backtesting.ninjatrader_smoke_maturity_gate_v1 import evaluate_ninjatrader_smoke_maturity
def clean(value):
 if hasattr(value,'isoformat'):return value.isoformat()
 if isinstance(value,tuple):return[clean(x)for x in value]
 if isinstance(value,dict):return{k:clean(v)for k,v in value.items()}
 return value
def main():
 now=datetime.now(timezone.utc);status=json.loads((ROOT/'outputs/operational_health/ninjatrader-canonical-smoke-task-status.json').read_text(encoding='utf-8-sig'));history=ROOT/'outputs/ninjatrader_canonical_smoke_history';gate=evaluate_ninjatrader_smoke_maturity(history_root=history,task_status=status,as_of=now);attestation=attest_ninjatrader_smoke_acceptance(gate=gate,history_root=history,attested_at=now);document=clean(asdict(attestation));target=ROOT/'outputs/ninjatrader_canonical_smoke_acceptance/latest.json';target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temporary.open('x')as stream:json.dump(document,stream,sort_keys=True,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,target)
 finally:temporary.unlink(missing_ok=True)
 print(json.dumps(document,sort_keys=True,separators=(',',':')));return 0
if __name__=='__main__':raise SystemExit(main())
