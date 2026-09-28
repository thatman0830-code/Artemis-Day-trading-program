from pathlib import Path
import sys,json,os,uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from backtesting.ninjatrader_micro_instrument_specs_v1 import verified_micro_instrument_specifications,verify_micro_instrument_specifications
def clean(v):
 if isinstance(v,Decimal):return format(v,'f')
 if isinstance(v,Enum):return v.value
 if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
 return v
def main():
 specs=verify_micro_instrument_specifications(verified_micro_instrument_specifications());document={"schema_version":"ninjatrader-micro-instrument-specifications-evidence-v1","specifications":[clean(asdict(x))for x in specs],"paper_execution_permitted":False,"trading_authority":False};target=ROOT/'outputs/ninjatrader_micro_instrument_specs/latest.json';target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temporary.open('x')as stream:json.dump(document,stream,sort_keys=True,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,target)
 finally:temporary.unlink(missing_ok=True)
 print(json.dumps(document,sort_keys=True,separators=(',',':')));return 0
if __name__=='__main__':raise SystemExit(main())
