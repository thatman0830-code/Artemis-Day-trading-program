import json
from pathlib import Path

import pytest

from execution.btc_perpetual_paper_risk_policy_v1 import (
    APPROVAL, VALUES, BTCPaperRiskPolicyError, issue_policy, read_risk_policy, write_policy,
)
from execution.test_btc_perpetual_paper_economics_policy_v1 import sources
from execution.btc_perpetual_paper_economics_policy_v1 import write_policy as write_economics
from execution.test_btc_perpetual_public_evidence_collector_v1 import payload
from execution.btc_perpetual_public_evidence_collector_v1 import collect_btc_perpetual_public_evidence
from execution.test_paper_performance_ledger_v1 import T


def inputs(tmp_path):
    l2,economics=sources(tmp_path)
    economics_path=tmp_path/"economics-policy.json"
    write_economics(output_path=economics_path,l2_proposal_path=l2,
        economics_draft_path=economics,owner_approval=__import__(
            "execution.btc_perpetual_paper_economics_policy_v1",fromlist=["APPROVAL"]).APPROVAL)
    evidence_root=tmp_path/"public";evidence_root.mkdir()
    receipt=collect_btc_perpetual_public_evidence(transport=lambda *_:(200,payload()),
        output_root=evidence_root,captured_at=T)
    return economics_path,evidence_root,evidence_root/f"{receipt.receipt_id}.receipt.json"


def test_exact_approval_issues_content_addressed_paper_only_policy(tmp_path):
    economics,root,receipt=inputs(tmp_path)
    output=tmp_path/"risk.json"
    result=write_policy(output_path=output,economics_policy_path=economics,
        public_evidence_root=root,public_evidence_receipt_path=receipt,owner_approval=APPROVAL)
    assert result["values"]==VALUES
    assert result["owner_approved"] and result["paper_use_permitted"]
    assert result["live_trading_permitted"] is result["trading_authority"] is False
    assert read_risk_policy(output)==result


def test_wrong_approval_tampering_and_wrong_public_root_reject(tmp_path):
    economics,root,receipt=inputs(tmp_path)
    with pytest.raises(BTCPaperRiskPolicyError,match="approval"):
        issue_policy(economics_policy_path=economics,public_evidence_root=root,
            public_evidence_receipt_path=receipt,owner_approval="yes")
    output=tmp_path/"risk.json"
    result=write_policy(output_path=output,economics_policy_path=economics,
        public_evidence_root=root,public_evidence_receipt_path=receipt,owner_approval=APPROVAL)
    result["values"]["maximum_total_exposure_usd"]="1000"
    output.write_text(json.dumps(result))
    with pytest.raises(BTCPaperRiskPolicyError,match="fields or identity"):
        read_risk_policy(output)
    with pytest.raises(ValueError):
        issue_policy(economics_policy_path=economics,public_evidence_root=tmp_path/"other",
            public_evidence_receipt_path=receipt,owner_approval=APPROVAL)


def test_policy_has_all_required_fail_closed_evidence_classes():
    assert VALUES["fail_closed_evidence"] == [
        "CLOCK","FUNDING","MARK","ORACLE","RECONCILIATION","RECORDER"]
    assert VALUES["collateral_fraction"]=="1" and VALUES["leverage_credit"]=="0"


def test_issued_policy_does_not_alias_module_constants(tmp_path):
    economics,root,receipt=inputs(tmp_path)
    result=issue_policy(economics_policy_path=economics,public_evidence_root=root,
        public_evidence_receipt_path=receipt,owner_approval=APPROVAL)
    result["values"]["fail_closed_evidence"].append("TAMPER")
    result["values"]["maximum_total_exposure_usd"]="1000"
    assert VALUES["fail_closed_evidence"] == [
        "CLOCK","FUNDING","MARK","ORACLE","RECONCILIATION","RECORDER"]
    assert VALUES["maximum_total_exposure_usd"]=="100"
