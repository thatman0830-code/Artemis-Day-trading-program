from dataclasses import replace
import hashlib
import pytest

from execution.btc_perpetual_specification_intake_v1 import *
from execution.btc_perpetual_specification_bundle_v1 import read_btc_perpetual_specification_bundle
from execution.test_btc_perpetual_economic_gate_v1 import build,T


def document(root):
    repo,_,precision=build(root);records=[]
    for spec in repo.specifications:
        ev=next(x for x in repo.evidence if x.evidence_id==spec.evidence_ids[0])
        records.append({"specification_type":spec.specification_type.value,"source_organization":ev.source_organization,
            "document_identity":ev.document_identity,"canonical_url":ev.canonical_url,
            "local_snapshot_path":ev.local_snapshot_path,"snapshot_sha256":ev.snapshot_sha256,
            "retrieved_at":ev.retrieved_at.isoformat(),"effective_from":spec.effective_from.isoformat(),
            "effective_to":None,"values":dict(spec.values),"owner_approved":True,"assumptions_and_gaps":[]})
    body={"schema_version":SCHEMA,"market":"BTC-PERP","instrument_id":"BTC",
        "size_decimals":precision.size_decimals,"records":records,"trading_authority":False}
    return finalize_intake_document(body)


def test_blank_template_contains_all_requirements_without_defaults():
    value=create_blank_intake_template()
    assert {x["specification_type"] for x in value["records"]}=={x.value for x in REQUIRED_TYPES}
    assert all(not x["owner_approved"] and x["values"]=={} for x in value["records"])
    assert value["size_decimals"] is None and not value["trading_authority"]


def test_template_file_is_exclusive_and_duplicate_input_rejects(tmp_path):
    path=tmp_path/"intake.json";write_blank_intake_template(path)
    assert read_intake_document(path)==create_blank_intake_template()
    with pytest.raises(FileExistsError): write_blank_intake_template(path)
    path.write_text('{"schema_version":"x","schema_version":"y"}')
    with pytest.raises(BTCPerpetualSpecificationIntakeError,match="duplicate"):
        read_intake_document(path)


def test_explicit_intake_compiles_persisted_eligible_bundle(tmp_path):
    value=document(tmp_path);path=tmp_path/"bundle.json"
    result=compile_btc_perpetual_specification_intake(document=value,repository_root=tmp_path,
        bundle_path=path,as_of=T)
    repository,instrument,precision,_=read_btc_perpetual_specification_bundle(path)
    assert result.eligibility.eligible and len(repository.specifications)==9
    assert instrument.contract_id=="BTC-PERP" and precision.size_decimals==5
    assert not result.trading_authority


@pytest.mark.parametrize("mutation",["unapproved","missing","tampered","path"])
def test_incomplete_unapproved_tampered_or_unsafe_intake_rejects(tmp_path,mutation):
    value=document(tmp_path)
    if mutation=="unapproved": value["records"][0]["owner_approved"]=False
    elif mutation=="missing": value["records"].pop()
    elif mutation=="path": value["records"][0]["local_snapshot_path"]="../escape"
    elif mutation=="tampered": value["size_decimals"]=4
    body={k:value[k] for k in value if k!="intake_id"};value=finalize_intake_document(body)
    with pytest.raises(BTCPerpetualSpecificationIntakeError):
        compile_btc_perpetual_specification_intake(document=value,repository_root=tmp_path,
            bundle_path=tmp_path/"bundle.json",as_of=T)
