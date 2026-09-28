import hashlib,json,pytest
from execution.btc_perpetual_paper_economics_policy_v1 import *
def artifact(path,id_name,body):
 canonical=lambda value:json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
 doc={**body,id_name:hashlib.sha256(canonical(body)).hexdigest()};path.write_bytes(canonical(doc)+b"\n");return path
def sources(tmp_path):
 l2=artifact(tmp_path/"l2.json","proposal_id",{"evidence_sufficient":True,"proposed_paper_only_values":{"maximum_order_notional_usd":"100","participation_limit_percent":"0.01","slippage_bps_per_fill":"2"},"trading_authority":False})
 econ=artifact(tmp_path/"econ.json","draft_id",{"facts":{"base_perpetual_taker_fee_bps":"4.5"},"trading_authority":False});return l2,econ
def test_exact_approval_issues_only_supervised_paper_authority(tmp_path):
 l2,econ=sources(tmp_path);p=issue_policy(l2_proposal_path=l2,economics_draft_path=econ,owner_approval=APPROVAL)
 assert p["values"]==VALUES and p["owner_approved"]and p["paper_use_permitted"]
 assert p["scope"]=="SUPERVISED_PAPER_ONLY"and p["live_trading_permitted"]is p["trading_authority"]is False
def test_wrong_approval_or_tampered_source_rejects(tmp_path):
 l2,econ=sources(tmp_path)
 with pytest.raises(BTCPaperEconomicsPolicyError,match="approval"):issue_policy(l2_proposal_path=l2,economics_draft_path=econ,owner_approval="yes")
 doc=json.loads(l2.read_bytes());doc["proposed_paper_only_values"]["slippage_bps_per_fill"]="0"
 l2.write_text(json.dumps(doc))
 with pytest.raises(BTCPaperEconomicsPolicyError,match="identity"):issue_policy(l2_proposal_path=l2,economics_draft_path=econ,owner_approval=APPROVAL)
