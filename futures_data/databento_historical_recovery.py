"""Cost-capped, immutable one-day Databento MES/MNQ recovery acquisition."""
from __future__ import annotations
import argparse,base64,json,os,sys,urllib.error,urllib.parse,urllib.request,uuid
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from hashlib import sha256
from pathlib import Path

DATASET="GLBX.MDP3";SCHEMA="ohlcv-1m";SYMBOLS={"ES":"MES.v.0","NQ":"MNQ.v.0"}
COST_ENDPOINT="https://hist.databento.com/v0/metadata.get_cost"
DATA_ENDPOINT="https://hist.databento.com/v0/timeseries.get_range"
MAX_COST=Decimal("0.25");MAX_ROWS=1500;MAX_BYTES=8_000_000;TIMEOUT=30
VERSION="databento-historical-recovery-v1"
class RecoveryError(RuntimeError):pass
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def request(endpoint,params,key,opener):
 req=urllib.request.Request(endpoint+"?"+urllib.parse.urlencode(params));token=base64.b64encode((key+":").encode()).decode();req.add_header("Authorization","Basic "+token)
 try:
  with opener(req,timeout=TIMEOUT) as response:status=response.status;payload=response.read(MAX_BYTES+1)
 except urllib.error.HTTPError as exc:raise RecoveryError("AUTH_OR_PROVIDER_HTTP_"+str(exc.code))from None
 except (urllib.error.URLError,TimeoutError,OSError):raise RecoveryError("NETWORK_OR_TIMEOUT")from None
 finally:req.headers.pop("Authorization",None);token=""
 if status!=200:raise RecoveryError("PROVIDER_HTTP_"+str(status))
 if len(payload)>MAX_BYTES:raise RecoveryError("response cap exceeded")
 return payload
def acquire(*,key:str,day:date,root:Path,opener=urllib.request.urlopen):
 if len(key)!=32 or not key.startswith("db-"):raise RecoveryError("credential format rejected")
 start=datetime(day.year,day.month,day.day,tzinfo=timezone.utc);end=start+timedelta(days=1)
 common={"dataset":DATASET,"schema":SCHEMA,"stype_in":"continuous","start":start.isoformat(),"end":end.isoformat(),"limit":str(MAX_ROWS)}
 costs={}
 for lane,symbol in SYMBOLS.items():
  raw=request(COST_ENDPOINT,{**common,"symbols":symbol},key,opener)
  try:costs[lane]=Decimal(raw.decode().strip())
  except (InvalidOperation,UnicodeError):raise RecoveryError("cost schema rejected")from None
 if sum(costs.values())>MAX_COST:raise RecoveryError("cost ceiling exceeded")
 target=root/day.isoformat()
 if target.exists():raise RecoveryError("recovery day already retained")
 staging=root/(".staging-"+uuid.uuid4().hex);staging.mkdir(parents=True)
 try:
  lanes={}
  for lane,symbol in SYMBOLS.items():
   raw=request(DATA_ENDPOINT,{**common,"symbols":symbol,"encoding":"json","pretty_px":"true","pretty_ts":"true","map_symbols":"true"},key,opener)
   rows=[line for line in raw.splitlines()if line.strip()]
   if not rows or len(rows)>MAX_ROWS:raise RecoveryError("row boundary rejected")
   for line in rows:
    item=json.loads(line);hd=item.get("hd",{})
    if not all(x in item for x in("open","high","low","close","volume"))or not all(x in hd for x in("ts_event","instrument_id")):raise RecoveryError("OHLCV schema rejected")
   path=staging/(lane+".jsonl");path.write_bytes(b"\n".join(rows)+b"\n")
   lanes[lane]={"cost_estimate_usd":format(costs[lane],"f"),"row_count":len(rows),"sha256":sha256(path.read_bytes()).hexdigest(),"symbol":symbol}
  manifest={"account_access":False,"cross_source_merge_performed":False,"dataset":DATASET,"day_utc":day.isoformat(),"lanes":lanes,"maximum_cost_usd":format(MAX_COST,"f"),"order_endpoints_present":False,"paper_only":True,"schema":SCHEMA,"schema_version":VERSION,"state":"RECOVERY_EVIDENCE_RETAINED","trading_authority":False}
  manifest["manifest_sha256"]=sha256(canonical(manifest)).hexdigest();(staging/"manifest.json").write_bytes(canonical(manifest)+b"\n");target.parent.mkdir(parents=True,exist_ok=True);os.replace(staging,target);return manifest
 finally:
  if staging.exists():
   for path in staging.iterdir():path.unlink()
   staging.rmdir()
def main():
 p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--root",type=Path,required=True);a=p.parse_args()
 try:result=acquire(key=sys.stdin.readline().strip(),day=date.fromisoformat(a.day),root=a.root.resolve());print(json.dumps(result,sort_keys=True,separators=(",",":")));return 0
 except (RecoveryError,ValueError,json.JSONDecodeError)as exc:print("DATABENTO_RECOVERY_FAILED_SANITIZED:"+str(exc),file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
