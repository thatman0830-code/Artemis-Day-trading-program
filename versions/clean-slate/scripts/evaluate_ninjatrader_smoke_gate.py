"""Evaluate and atomically publish the ES/NQ smoke maturity gate."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataclasses import asdict
from datetime import datetime,timezone
from enum import Enum
import json,os,uuid
from backtesting.ninjatrader_smoke_maturity_gate_v1 import evaluate_ninjatrader_smoke_maturity
def clean(v):
 if isinstance(v,Enum):return v.value
 if hasattr(v,'isoformat'):return v.isoformat()
 if isinstance(v,tuple):return[clean(x)for x in v]
 if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
 return v
def main():
 status_path=ROOT/'outputs/operational_health/ninjatrader-canonical-smoke-task-status.json';output=ROOT/'outputs/ninjatrader_canonical_smoke_gate/latest.json'
 status=json.loads(status_path.read_text(encoding='utf-8-sig'));gate=evaluate_ninjatrader_smoke_maturity(history_root=ROOT/'outputs/ninjatrader_canonical_smoke_history',task_status=status,as_of=datetime.now(timezone.utc));document=clean(asdict(gate));output.parent.mkdir(parents=True,exist_ok=True);temporary=output.with_name('.'+output.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temporary.open('x')as stream:json.dump(document,stream,sort_keys=True,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,output)
 finally:temporary.unlink(missing_ok=True)
 print(json.dumps(document,sort_keys=True,separators=(',',':')));return 0
if __name__=='__main__':raise SystemExit(main())
