"""Compile retained official documents into an unapproved economics review draft."""
from __future__ import annotations
import argparse,hashlib,json,os,uuid
from html.parser import HTMLParser
from pathlib import Path
from execution.btc_perpetual_official_docs_v1 import SOURCES
VERSION="btc-perpetual-official-economics-draft-v1"
class BTCEconomicsDraftError(ValueError):pass
class _Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,data):self.parts.append(data)
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def compile_draft(*,evidence_root,evidence_path):
 root=Path(evidence_root).absolute();path=Path(evidence_path).absolute()
 if root.is_symlink()or not root.is_dir()or path.is_symlink()or not path.is_file()or not path.resolve().is_relative_to(root.resolve()):raise BTCEconomicsDraftError("evidence path is unsafe")
 try:manifest=json.loads(path.read_bytes())
 except Exception as exc:raise BTCEconomicsDraftError("evidence manifest is unreadable")from exc
 if manifest.get("credentials_used")is not False or manifest.get("owner_approved")is not False or manifest.get("trading_authority")is not False:raise BTCEconomicsDraftError("evidence authority is invalid")
 records={r["name"]:r for r in manifest.get("records",[]) if isinstance(r,dict)and"name"in r}
 if set(records)!=set(SOURCES):raise BTCEconomicsDraftError("official source set is incomplete")
 texts={}
 for name,url in SOURCES.items():
  record=records[name];raw=root/record["relative_path"]
  if record.get("canonical_url")!=url or raw.is_symlink()or not raw.is_file()or hashlib.sha256(raw.read_bytes()).hexdigest()!=record.get("sha256"):raise BTCEconomicsDraftError("official source binding failed")
  parser=_Text();parser.feed(raw.read_text(encoding="utf-8"));texts[name]=" ".join(" ".join(parser.parts).split())
 required={"fees":("0.045%","0.015%","rolling 14 day volume"),"funding":("paid every hour","4%/hour","position_size * oracle_price * funding_rate"),"contract_specifications":("Linear perpetual","1 unit of underlying spot asset","20000 USDC")}
 if any(token not in texts[name]for name,tokens in required.items()for token in tokens):raise BTCEconomicsDraftError("required official statement is absent")
 body={"schema_version":VERSION,"market":"BTC-PERP","source_evidence_id":manifest["evidence_id"],"facts":{"base_perpetual_taker_fee_bps":"4.5","base_perpetual_maker_fee_bps":"1.5","fee_tier_basis":"rolling_14_day_weighted_volume","funding_interval":"PT1H","funding_hourly_cap":"0.04","funding_payment_basis":"position_size_x_oracle_price_x_funding_rate","btc_funding_impact_notional_usdc":"20000","instrument_type":"LINEAR_PERPETUAL","contract_unit":"1 BTC"},"assumptions_and_gaps":["NO_ACCOUNT_SPECIFIC_FEE_TIER_EVIDENCE","BASE_UNDISCOUNTED_FEES_PROPOSED_FOR_PAPER_ONLY","EFFECTIVE_DATE_NOT_PUBLISHED_IN_RETAINED_PAGE"],"owner_approved":False,"paper_use_permitted":False,"live_trading_permitted":False,"trading_authority":False}
 return {**body,"draft_id":hashlib.sha256(_canonical(body)).hexdigest()}
def write_draft(*,evidence_root,evidence_path,output_path):
 result=compile_draft(evidence_root=evidence_root,evidence_path=evidence_path);path=Path(output_path);data=_canonical(result)+b"\n";tmp=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
 try:
  with open(tmp,"xb")as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(tmp,path)
 finally:tmp.unlink(missing_ok=True)
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--evidence-root",type=Path,required=True);p.add_argument("--evidence",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();r=write_draft(evidence_root=a.evidence_root,evidence_path=a.evidence,output_path=a.output);print("BTC_OFFICIAL_ECONOMICS_DRAFT_WRITTEN:"+r["draft_id"]);return 0
if __name__=="__main__":raise SystemExit(main())
