from pathlib import Path
import sys,json,os,uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal
from enum import Enum
from backtesting.ninjatrader_shadow_profile_comparison_v1 import compare_shadow_profiles
def clean(v):
 if isinstance(v,Decimal):return format(v,'f')
 if isinstance(v,Enum):return v.value
 if hasattr(v,'isoformat'):return v.isoformat()
 if isinstance(v,tuple):return[clean(x)for x in v]
 if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
 return v
def main():
 result=compare_shadow_profiles(trades=(),evaluated_at=datetime.now(timezone.utc));document=clean(asdict(result));target=ROOT/'outputs/ninjatrader_shadow_profile_comparison/latest.json';target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temporary.open('x')as stream:json.dump(document,stream,sort_keys=True,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,target)
 finally:temporary.unlink(missing_ok=True)
 print(json.dumps(document,sort_keys=True,separators=(',',':')));return 0
if __name__=='__main__':raise SystemExit(main())
