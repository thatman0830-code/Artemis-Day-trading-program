"""Fail-closed policy for promoting only a separate-source research lane."""
from __future__ import annotations
import argparse,json
from hashlib import sha256
from pathlib import Path
VERSION="databento-recovery-policy-v1";EXPECTED={"42003239":"MESU6","42004800":"MNQU6"}
class PolicyError(ValueError):pass
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def authenticated(path):
 doc=json.loads(path.read_text());digest=doc.pop("report_sha256",None)
 if digest!=sha256(canonical(doc)).hexdigest():raise PolicyError("report digest invalid")
 return doc
def evaluate(*,es_path:Path,nq_path:Path,lineage_path:Path):
 reports={"ES":authenticated(es_path),"NQ":authenticated(nq_path)};lineage=authenticated(lineage_path)
 observed={key:value.get("s")for key,value in lineage.get("instrument_mappings",{}).items()}
 if observed!=EXPECTED or lineage.get("state")!="LINEAGE_RESOLVED":raise PolicyError("contract lineage rejected")
 reasons=[]
 for lane,report in reports.items():
  overlap=report.get("ninjatrader_minute_count",0);price=report.get("price_conflict_count",0)
  if report.get("lane")!=lane or report.get("missing_databento_count")!=0 or report.get("databento_minute_count")!=1380:reasons.append(lane+"_COVERAGE")
  if not overlap or price/overlap>0.01:reasons.append(lane+"_PRICE_DIVERGENCE")
 eligible=not reasons
 result={"cross_source_merge_permitted":False,"databento_day_utc":"2026-09-10","decision":"SEPARATE_SOURCE_RESEARCH_ELIGIBLE"if eligible else"REJECTED","execution_permitted":False,"lineage":observed,"ninjatrader_archive_mutated":False,"paper_only":True,"price_conflict_limit_fraction":"0.01","reasons":reasons,"schema_version":VERSION,"volume_policy":"PROVIDER_CONSISTENT_DATABENTO_ONLY","trading_authority":False}
 result["policy_sha256"]=sha256(canonical(result)).hexdigest();return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--es',type=Path,required=True);p.add_argument('--nq',type=Path,required=True);p.add_argument('--lineage',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=evaluate(es_path=a.es,nq_path=a.nq,lineage_path=a.lineage);a.output.parent.mkdir(parents=True,exist_ok=True);tmp=a.output.with_suffix('.tmp');tmp.write_bytes(canonical(result)+b'\n');tmp.replace(a.output);print(json.dumps(result,sort_keys=True,separators=(',',':')));return 0
if __name__=='__main__':raise SystemExit(main())
