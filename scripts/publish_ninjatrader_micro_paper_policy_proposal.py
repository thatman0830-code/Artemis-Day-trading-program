from pathlib import Path
import sys,json,os,uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from backtesting.ninjatrader_micro_paper_policy_proposal_v1 import micro_paper_policy_proposals,verify_micro_paper_policy_proposals
def clean(v):return format(v,'f')if isinstance(v,Decimal)else v.value if isinstance(v,Enum)else v
def main():
 profiles=verify_micro_paper_policy_proposals(micro_paper_policy_proposals());document={"schema_version":"ninjatrader-micro-paper-policy-comparison-v1","profiles":[{k:clean(v)for k,v in asdict(p).items()}for p in profiles],"comparison_only":True,"approved":False,"paper_execution_permitted":False,"trading_authority":False};target=ROOT/'outputs/ninjatrader_micro_paper_policy/proposal.json';target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temporary.open('x')as stream:json.dump(document,stream,sort_keys=True,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,target)
 finally:temporary.unlink(missing_ok=True)
 print(json.dumps(document,sort_keys=True,separators=(',',':')));return 0
if __name__=='__main__':raise SystemExit(main())
