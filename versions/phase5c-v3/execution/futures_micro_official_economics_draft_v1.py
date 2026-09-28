"""Validate retained IBKR pages and compile a fail-closed economics draft."""
from __future__ import annotations
import hashlib,json
from html.parser import HTMLParser
from pathlib import Path
from execution.futures_micro_official_docs_v1 import SOURCES,VERSION as EVIDENCE_VERSION

VERSION="futures-micro-official-economics-draft-v1"
class FuturesMicroEconomicsDraftError(ValueError):pass
class _Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,data):self.parts.append(data)
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def compile_draft(*,evidence_root,evidence_path):
 root=Path(evidence_root).absolute();path=Path(evidence_path).absolute()
 if root.is_symlink()or not root.is_dir()or path.is_symlink()or not path.is_file()or not path.resolve().is_relative_to(root.resolve()):raise FuturesMicroEconomicsDraftError("evidence path is unsafe")
 try:manifest=json.loads(path.read_bytes())
 except Exception as exc:raise FuturesMicroEconomicsDraftError("manifest is unreadable")from exc
 if (manifest.get("schema_version")!=EVIDENCE_VERSION or manifest.get("credentials_used")is not False
     or manifest.get("owner_approved")is not False or manifest.get("trading_authority")is not False):raise FuturesMicroEconomicsDraftError("manifest authority is invalid")
 records={x["name"]:x for x in manifest.get("records",[])if isinstance(x,dict)and"name"in x}
 if set(records)!=set(SOURCES):raise FuturesMicroEconomicsDraftError("official source set is incomplete")
 texts={}
 for name,url in SOURCES.items():
  record=records[name];raw=root/record.get("relative_path","")
  if record.get("canonical_url")!=url or raw.is_symlink()or not raw.is_file()or hashlib.sha256(raw.read_bytes()).hexdigest()!=record.get("sha256"):raise FuturesMicroEconomicsDraftError("official source binding failed")
  parser=_Text();parser.feed(raw.read_text(encoding="utf-8"));texts[name]=" ".join(" ".join(parser.parts).split())
 if not all(x in texts["commissions"]for x in ("MES, MNQ","≤ 1,000","USD 0.25 /contract")):raise FuturesMicroEconomicsDraftError("retail commission statement is absent")
 if not all(x in texts["cme_fees"]for x in ("Micro E-Mini Futures Products","MES, MNQ, M2K, VOLQ","0.35")):raise FuturesMicroEconomicsDraftError("passed-through fee statement is absent")
 if not all(x in texts["margins"]for x in ("Margin Requirements","Overnight")):raise FuturesMicroEconomicsDraftError("dynamic margin policy statement is absent")
 body={"schema_version":VERSION,"markets":["MES","MNQ"],"source_evidence_id":manifest["evidence_id"],
  "verified_facts":{"ibkr_commission_usd_per_contract_per_side":"0.25","ibkr_exchange_and_regulatory_fees_usd_per_contract_per_side":"0.35","total_usd_per_contract_per_side_before_slippage":"0.60","broker_margin_is_dynamic":True},
  "missing_runtime_facts":["CURRENT_CONTRACT_INITIAL_MARGIN","CURRENT_CONTRACT_MAINTENANCE_MARGIN","ACCOUNT_SPECIFIC_MARGIN","EXECUTION_SLIPPAGE_EVIDENCE"],
  "owner_approved":False,"paper_use_permitted":False,"live_trading_permitted":False,"trading_authority":False}
 return {**body,"draft_id":hashlib.sha256(_canonical(body)).hexdigest()}
