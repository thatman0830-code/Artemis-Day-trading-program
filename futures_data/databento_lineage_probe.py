"""Free, bounded instrument-id-to-raw-symbol lineage probe."""
from __future__ import annotations
import argparse,json,sys,urllib.parse,urllib.request
from datetime import date,timedelta
from hashlib import sha256
from pathlib import Path
from futures_data.databento_historical_recovery import RecoveryError,canonical,request
ENDPOINT="https://hist.databento.com/v0/symbology.resolve";IDS=("42003239","42004800");VERSION="databento-lineage-probe-v1"
def resolve(*,key,day,output,opener=urllib.request.urlopen):
 end=(date.fromisoformat(day)+timedelta(days=1)).isoformat()
 raw=request(ENDPOINT,{"dataset":"GLBX.MDP3","symbols":",".join(IDS),"stype_in":"instrument_id","stype_out":"raw_symbol","start_date":day,"end_date":end},key,opener)
 try:payload=json.loads(raw)
 except json.JSONDecodeError:raise RecoveryError("lineage schema rejected")from None
 if payload.get("status")!=0 or payload.get("partial")or payload.get("not_found")or set(payload.get("result",{}))!=set(IDS):raise RecoveryError("lineage resolution incomplete")
 mappings={}
 for instrument in IDS:
  rows=payload["result"][instrument]
  if len(rows)!=1 or set(rows[0])!={"d0","d1","s"}:raise RecoveryError("lineage mapping ambiguous")
  mappings[instrument]=rows[0]
 report={"account_access":False,"dataset":"GLBX.MDP3","day":day,"instrument_mappings":mappings,"metadata_cost_usd":"0","order_endpoints_present":False,"paper_only":True,"schema_version":VERSION,"state":"LINEAGE_RESOLVED","trading_authority":False};report["report_sha256"]=sha256(canonical(report)).hexdigest();output.parent.mkdir(parents=True,exist_ok=True);tmp=output.with_suffix('.tmp');tmp.write_bytes(canonical(report)+b'\n');tmp.replace(output);return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--day',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 try:print(json.dumps(resolve(key=sys.stdin.readline().strip(),day=a.day,output=a.output.resolve()),sort_keys=True,separators=(',',':')));return 0
 except RecoveryError as exc:print('DATABENTO_LINEAGE_FAILED_SANITIZED:'+str(exc),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
