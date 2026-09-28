"""Issue the exact owner-approved BTC supervised-paper economics policy."""
from __future__ import annotations
import argparse,hashlib,json,os,uuid
from pathlib import Path
VERSION="btc-perpetual-paper-economics-policy-v1"
APPROVAL="I approve the verified BTC economics draft and conservative paper-only policy: 4.5 bps taker fee per fill, 2 bps slippage per fill, $100 maximum order notional, 0.01% participation limit, and verified hourly funding. No discounts are assumed. This approval applies only to supervised BTC paper trading and grants no live-trading authority."
VALUES={"taker_fee_bps_per_fill":"4.5","slippage_bps_per_fill":"2","maximum_order_notional_usd":"100","participation_limit_percent":"0.01","funding_method":"verified_hourly_position_size_x_oracle_price_x_funding_rate","discounts_assumed":False}
class BTCPaperEconomicsPolicyError(ValueError):pass
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _read(path,id_name):
 path=Path(path)
 if path.is_symlink()or not path.is_file():raise BTCPaperEconomicsPolicyError("source artifact is unsafe")
 try:doc=json.loads(path.read_bytes())
 except Exception as exc:raise BTCPaperEconomicsPolicyError("source artifact is unreadable")from exc
 identity=doc.get(id_name);body={k:doc[k]for k in doc if k!=id_name}
 if not isinstance(identity,str)or hashlib.sha256(_canonical(body)).hexdigest()!=identity or doc.get("trading_authority")is not False:raise BTCPaperEconomicsPolicyError("source identity or authority is invalid")
 return doc
def read_policy(path):
 doc=_read(path,"policy_id")
 required={"schema_version","market","values","source_ids","scope","owner_approved","paper_use_permitted","live_trading_permitted","trading_authority","policy_id"}
 if set(doc)!=required or doc["schema_version"]!=VERSION or doc["market"]!="BTC-PERP"or doc["values"]!=VALUES or len(doc["source_ids"])!=2 or any(not isinstance(x,str)or len(x)!=64 for x in doc["source_ids"])or doc["scope"]!="SUPERVISED_PAPER_ONLY"or doc["owner_approved"]is not True or doc["paper_use_permitted"]is not True or doc["live_trading_permitted"]is not False:raise BTCPaperEconomicsPolicyError("policy fields are invalid")
 return doc
def issue_policy(*,l2_proposal_path,economics_draft_path,owner_approval):
 if owner_approval!=APPROVAL:raise BTCPaperEconomicsPolicyError("exact owner approval is required")
 l2=_read(l2_proposal_path,"proposal_id");economics=_read(economics_draft_path,"draft_id")
 if not l2.get("evidence_sufficient")or l2.get("proposed_paper_only_values")!={"maximum_order_notional_usd":"100","participation_limit_percent":"0.01","slippage_bps_per_fill":"2"}:raise BTCPaperEconomicsPolicyError("L2 proposal is incompatible")
 if economics.get("facts",{}).get("base_perpetual_taker_fee_bps")!="4.5":raise BTCPaperEconomicsPolicyError("economics draft is incompatible")
 body={"schema_version":VERSION,"market":"BTC-PERP","values":VALUES,"source_ids":[l2["proposal_id"],economics["draft_id"]],"scope":"SUPERVISED_PAPER_ONLY","owner_approved":True,"paper_use_permitted":True,"live_trading_permitted":False,"trading_authority":False}
 return {**body,"policy_id":hashlib.sha256(_canonical(body)).hexdigest()}
def write_policy(*,output_path,**kwargs):
 result=issue_policy(**kwargs);path=Path(output_path);data=_canonical(result)+b"\n";tmp=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
 try:
  with open(tmp,"xb")as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(tmp,path)
 finally:tmp.unlink(missing_ok=True)
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--l2",type=Path,required=True);p.add_argument("--economics",type=Path,required=True);p.add_argument("--approval",required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();r=write_policy(output_path=a.output,l2_proposal_path=a.l2,economics_draft_path=a.economics,owner_approval=a.approval);print("BTC_PAPER_ECONOMICS_POLICY_WRITTEN:"+r["policy_id"]);return 0
if __name__=="__main__":raise SystemExit(main())
