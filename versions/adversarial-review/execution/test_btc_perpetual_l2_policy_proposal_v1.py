from datetime import datetime,timedelta,timezone
import hashlib
import json
import pytest

from execution.btc_perpetual_l2_policy_proposal_v1 import *
from execution.test_btc_perpetual_l2_aggregate_v1 import _retain


START=datetime(2026,9,3,tzinfo=timezone.utc)


def _complete(root):return [_retain(root,START+timedelta(minutes=20*i),i) for i in range(24)]


def test_complete_evidence_produces_deterministic_unapproved_proposal(tmp_path):
    paths=_complete(tmp_path)
    first=create_l2_policy_proposal(root=tmp_path,receipt_paths=paths)
    second=create_l2_policy_proposal(root=tmp_path,receipt_paths=reversed(paths))
    assert first==second and first["proposed_paper_only_values"]["slippage_bps_per_fill"]=="2"
    assert first["proposed_paper_only_values"]["maximum_order_notional_usd"]=="100"
    assert first["owner_approved"] is first["paper_use_permitted"] is False
    assert first["live_trading_permitted"] is first["trading_authority"] is False
    assert "OWNER_APPROVED_FEE_TIER" in first["remaining_blockers"]


def test_incomplete_evidence_rejects(tmp_path):
    path=_retain(tmp_path,START)
    with pytest.raises(BTCL2PolicyProposalError,match="incomplete"):
        create_l2_policy_proposal(root=tmp_path,receipt_paths=[path])


def test_writer_is_canonical_and_replaces_existing_output(tmp_path):
    evidence=tmp_path/"evidence";evidence.mkdir();_complete(evidence)
    output=tmp_path/"proposal.json";output.write_text("old")
    result=write_l2_policy_proposal(root=evidence,output_path=output)
    assert json.loads(output.read_bytes())==result and output.read_bytes().endswith(b"\n")
    body={key:result[key] for key in result if key!="proposal_id"}
    canonical=json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    assert hashlib.sha256(canonical).hexdigest()==result["proposal_id"]
