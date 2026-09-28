import json
import pytest

from execution.btc_perpetual_intake_public_draft_v1 import *
from execution.btc_perpetual_public_evidence_collector_v1 import collect_btc_perpetual_public_evidence,read_btc_perpetual_public_evidence
from execution.btc_perpetual_specification_intake_v1 import create_blank_intake_template
from execution.test_btc_perpetual_public_evidence_collector_v1 import payload,T


def retained(tmp_path):
    receipt=collect_btc_perpetual_public_evidence(transport=lambda *args:(200,payload()),output_root=tmp_path,captured_at=T)
    path=tmp_path/f"{receipt.receipt_id}.receipt.json"
    return receipt,path


def test_verified_public_facts_populate_only_unapproved_categories(tmp_path):
    receipt,path=retained(tmp_path);loaded=read_btc_perpetual_public_evidence(output_root=tmp_path,receipt_path=path)
    result=apply_public_evidence_to_intake(intake=create_blank_intake_template(),receipt=loaded)
    changed={x["specification_type"]:x for x in result["records"] if x["values"]}
    assert set(changed)=={"INSTRUMENT","MARK_PRICE","ORACLE_PRICE","FUNDING","MARGIN_TIER"}
    assert result["size_decimals"]==5 and changed["INSTRUMENT"]["values"]["quantity_step"]=="0.00001"
    assert all(x["owner_approved"] is False for x in result["records"])
    assert not result["trading_authority"]


def test_modified_template_and_tampered_raw_evidence_reject(tmp_path):
    receipt,path=retained(tmp_path);blank=create_blank_intake_template();blank["market"]="BTC"
    with pytest.raises(BTCPerpetualIntakeDraftError,match="blank"):
        apply_public_evidence_to_intake(intake=blank,receipt=receipt)
    (tmp_path/receipt.raw_relative_path).write_text("tampered")
    with pytest.raises(Exception): read_btc_perpetual_public_evidence(output_root=tmp_path,receipt_path=path)


def test_draft_write_is_exclusive(tmp_path):
    receipt,_=retained(tmp_path);draft=apply_public_evidence_to_intake(intake=create_blank_intake_template(),receipt=receipt)
    path=tmp_path/"draft.json";write_public_intake_draft(path,draft)
    assert json.loads(path.read_text())==draft
    with pytest.raises(FileExistsError):write_public_intake_draft(path,draft)
