import json
from dataclasses import replace

import pytest

from backtesting.execution_accounting_v2.specifications import Capability
from execution.btc_perpetual_paper_specification_bundle_v1 import (
    BTCPerpetualPaperSpecificationError,compile_paper_specification_bundle,
    read_paper_specification_bundle,
)
from execution.btc_perpetual_paper_risk_policy_v1 import APPROVAL,write_policy
from execution.test_btc_perpetual_paper_risk_policy_v1 import inputs
from execution.test_paper_performance_ledger_v1 import T
from execution.btc_perpetual_public_evidence_collector_v1 import collect_btc_perpetual_public_evidence
from execution.test_btc_perpetual_public_evidence_collector_v1 import payload


def sources(tmp_path):
    economics,public_root,receipt=inputs(tmp_path)
    risk=tmp_path/"risk.json"
    write_policy(output_path=risk,economics_policy_path=economics,
        public_evidence_root=public_root,public_evidence_receipt_path=receipt,
        owner_approval=APPROVAL)
    return dict(economics_policy_path=economics,risk_policy_path=risk,
        public_evidence_root=public_root,public_evidence_receipt_path=receipt)


def test_compiles_reconstructible_explicit_paper_only_bundle(tmp_path):
    values=sources(tmp_path);path=tmp_path/"paper-bundle.json"
    gate,document=compile_paper_specification_bundle(**values,as_of=T,output_path=path)
    loaded,bundle_id=read_paper_specification_bundle(path,**values)
    assert loaded==gate and bundle_id==document["bundle_id"]
    assert gate.eligibility.capability is Capability.SUPERVISED_PAPER_ECONOMICS
    assert gate.instrument.tick_size==1 and gate.precision.quantity_step.as_tuple().exponent==-5
    assert gate.paper_use_permitted and not gate.live_trading_permitted and not gate.trading_authority
    assert document["scope"]=="SUPERVISED_PAPER_ONLY"


def test_tampering_or_source_rotation_rejects(tmp_path):
    values=sources(tmp_path);path=tmp_path/"paper-bundle.json"
    _,document=compile_paper_specification_bundle(**values,as_of=T,output_path=path)
    document["scope"]="LIVE";path.write_text(json.dumps(document))
    with pytest.raises(BTCPerpetualPaperSpecificationError):
        read_paper_specification_bundle(path,**values)


def test_stale_public_evidence_rejects(tmp_path):
    values=sources(tmp_path)
    with pytest.raises(BTCPerpetualPaperSpecificationError,match="freshness"):
        compile_paper_specification_bundle(**values,as_of=T+__import__("datetime").timedelta(seconds=61))


def test_gate_cannot_be_relabelled_live(tmp_path):
    gate,_=compile_paper_specification_bundle(**sources(tmp_path),as_of=T)
    with pytest.raises(BTCPerpetualPaperSpecificationError):
        replace(gate,live_trading_permitted=True)


def test_rotating_prices_preserve_approved_instrument_lineage(tmp_path):
    values=sources(tmp_path)
    fresh=collect_btc_perpetual_public_evidence(transport=lambda *_:(200,
        payload().replace(b'"markPx":"110000"',b'"markPx":"110001"')),
        output_root=values["public_evidence_root"],captured_at=T+__import__("datetime").timedelta(seconds=30))
    values["public_evidence_receipt_path"]=values["public_evidence_root"]/f"{fresh.receipt_id}.receipt.json"
    _,document=compile_paper_specification_bundle(**values,
        as_of=T+__import__("datetime").timedelta(seconds=30))
    assert document["approved_public_evidence_id"]!=document["public_evidence_id"]
