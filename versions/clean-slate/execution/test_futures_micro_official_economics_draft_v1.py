import hashlib,json
from pathlib import Path
import pytest
from execution.futures_micro_official_docs_v1 import SOURCES,VERSION as EVIDENCE_VERSION
from execution.futures_micro_official_economics_draft_v1 import *

def evidence(tmp_path):
 texts={"commissions":"MES, MNQ ≤ 1,000 USD 0.25 /contract","cme_fees":"Micro E-Mini Futures Products MES, MNQ, M2K, VOLQ 0.35","margins":"Margin Requirements Overnight dynamic"};records=[]
 for name,url in SOURCES.items():
  raw=("<html>"+texts[name]+"</html>").encode();digest=hashlib.sha256(raw).hexdigest();p=tmp_path/f"{name}.html";p.write_bytes(raw);records.append({"name":name,"canonical_url":url,"sha256":digest,"relative_path":p.name})
 body={"schema_version":EVIDENCE_VERSION,"records":records,"credentials_used":False,"owner_approved":False,"trading_authority":False};body["evidence_id"]="a"*64;p=tmp_path/"manifest.json";p.write_text(json.dumps(body));return p
def test_compile_verifies_costs_but_keeps_dynamic_margin_closed(tmp_path):
 value=compile_draft(evidence_root=tmp_path,evidence_path=evidence(tmp_path))
 assert value["verified_facts"]["total_usd_per_contract_per_side_before_slippage"]=="0.60"
 assert "CURRENT_CONTRACT_INITIAL_MARGIN"in value["missing_runtime_facts"]
 assert value["owner_approved"]is False and value["paper_use_permitted"]is False and value["trading_authority"]is False
def test_tamper_and_missing_statements_reject(tmp_path):
 manifest=evidence(tmp_path);doc=json.loads(manifest.read_text());(tmp_path/doc["records"][0]["relative_path"]).write_text("tampered")
 with pytest.raises(FuturesMicroEconomicsDraftError,match="binding"):compile_draft(evidence_root=tmp_path,evidence_path=manifest)
 manifest=evidence(tmp_path);doc=json.loads(manifest.read_text());target=tmp_path/doc["records"][2]["relative_path"];target.write_text("<html>Margin Requirements</html>");doc["records"][2]["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest();manifest.write_text(json.dumps(doc))
 with pytest.raises(FuturesMicroEconomicsDraftError,match="margin"):compile_draft(evidence_root=tmp_path,evidence_path=manifest)
