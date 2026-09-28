from datetime import timedelta
from decimal import Decimal
import hashlib
from pathlib import Path

import pytest

from execution.btc_perpetual_paper_risk_policy_v1 import APPROVAL, write_policy
from execution.btc_perpetual_public_evidence_collector_v1 import collect_btc_perpetual_public_evidence
from execution.test_btc_perpetual_public_evidence_collector_v1 import payload
from execution.supervised_btc_paper_session_assembly_v1 import (
    BTCPaperSessionAssemblyError, assemble_supervised_btc_paper_session,
)
from execution.supervised_paper_launch_evidence_v1 import OwnerSupervisionConfirmationV1
from execution.test_btc_archive_snapshot_source_v1 import archive
from execution.test_btc_perpetual_paper_risk_policy_v1 import inputs
from execution.test_paper_performance_ledger_v1 import T
from execution.test_btc_perpetual_economic_gate_v1 import build
from execution.btc_perpetual_specification_bundle_v1 import write_btc_perpetual_specification_bundle
from execution.btc_perpetual_paper_specification_bundle_v1 import compile_paper_specification_bundle


CHECKPOINT="a"*64


def prepared(tmp_path, *, as_of=T):
    economics,public_root,receipt=inputs(tmp_path)
    risk=tmp_path/"risk.json"
    write_policy(output_path=risk,economics_policy_path=economics,
        public_evidence_root=public_root,public_evidence_receipt_path=receipt,
        owner_approval=APPROVAL)
    archive_root=tmp_path/"archive";archive_root.mkdir();archive(archive_root)
    confirmation=OwnerSupervisionConfirmationV1.create(confirmed_at=T,
        expires_at=T+timedelta(minutes=5),repository_checkpoint=CHECKPOINT,
        owner_supervision_confirmed=True,stop_control_verified=True,
        maximum_session_seconds=300,maximum_commands=5,
        maximum_order_notional=Decimal("100"),maximum_gross_exposure=Decimal("100"))
    result=assemble_supervised_btc_paper_session(session_root=tmp_path/"session",
        archive_root=archive_root,evidence_path=tmp_path/"launch-evidence.json",
        confirmation=confirmation,expected_checkpoint=CHECKPOINT,session_id="1"*32,
        economics_policy_path=economics,risk_policy_path=risk,
        public_evidence_root=public_root,public_evidence_receipt_path=receipt,as_of=as_of)
    return result,risk


def test_assembly_creates_fully_collateralized_single_order_paper_dependencies(tmp_path):
    result,_=prepared(tmp_path)
    book=result.session.bridge.initial_accounting
    gateway=result.session.workflow.initial.gateway
    assert book.market=="BTC-PERP" and book.snapshot.cash==Decimal("100")
    assert book.margin_specification.customer_initial==Decimal("1")
    assert book.instrument.effective_from<=book.margin_specification.effective_from
    assert len(book.instrument.evidence_ids)>=1
    assert book.policy.perpetual_capability_enabled is True
    assert result.runtime.valuation.validation["mark_specification_id"] in book.policy.specification_ids
    assert gateway.policy.max_order_notional==gateway.policy.max_total_notional==Decimal("100")
    assert gateway.policy.max_open_orders==1
    assert result.runtime.poll_interval==timedelta(seconds=2)
    snapshots=list(result.snapshot_root.glob("BTC_1m.*.csv"))
    assert len(snapshots)==1 and len(snapshots[0].read_text().splitlines())<=1001
    assert result.no_signal_input(as_of=T).command is None
    assert result.trading_authority is False and len(result.assembly_id)==64


def test_stale_public_evidence_and_policy_tampering_fail_closed(tmp_path):
    with pytest.raises(BTCPaperSessionAssemblyError,match="freshness"):
        prepared(tmp_path,as_of=T+timedelta(seconds=61))
    other=tmp_path/"other";other.mkdir()
    result,risk=prepared(other)
    text=risk.read_text().replace('"maximum_total_exposure_usd":"100"',
        '"maximum_total_exposure_usd":"1000"')
    risk.write_text(text)
    with pytest.raises(ValueError):
        result.session  # retained object remains immutable; altered disk is not silently re-read
        assemble_supervised_btc_paper_session(session_root=other/"another-session",
            archive_root=result.archive_root,evidence_path=other/"launch-evidence.json",
            confirmation=result.session.confirmation,expected_checkpoint=CHECKPOINT,
            session_id="2"*32,economics_policy_path=other/"economics-policy.json",
            risk_policy_path=risk,public_evidence_root=other/"public",
            public_evidence_receipt_path=next((other/"public").glob("*.receipt.json")),as_of=T)


def test_fresh_rotating_market_evidence_preserves_approved_immutable_lineage(tmp_path):
    result,risk=prepared(tmp_path)
    public_root=tmp_path/"public"
    changed=payload().replace(b'"markPx":"50000"',b'"markPx":"50001"')
    fresh=collect_btc_perpetual_public_evidence(transport=lambda *_:(200,changed),
        output_root=public_root,captured_at=T+timedelta(seconds=30))
    rotated=assemble_supervised_btc_paper_session(session_root=tmp_path/"rotated",
        archive_root=result.archive_root,evidence_path=tmp_path/"launch-evidence.json",
        confirmation=result.session.confirmation,expected_checkpoint=CHECKPOINT,
        session_id="2"*32,economics_policy_path=tmp_path/"economics-policy.json",
        risk_policy_path=risk,public_evidence_root=public_root,
        public_evidence_receipt_path=public_root/f"{fresh.receipt_id}.receipt.json",
        as_of=T+timedelta(seconds=30))
    assert rotated.public_evidence_id==fresh.receipt_id
    assert len(rotated.session.bridge.initial_accounting.instrument.evidence_ids)==2


def test_strategy_assembly_uses_exact_eligible_specification_bundle(tmp_path):
    result,_=prepared(tmp_path)
    repository,instrument,precision=build(tmp_path,at=T)
    bundle=tmp_path/"specification-bundle.json"
    write_btc_perpetual_specification_bundle(bundle,repository,instrument,precision)
    strategy=assemble_supervised_btc_paper_session(session_root=tmp_path/"strategy-session",
        archive_root=result.archive_root,evidence_path=tmp_path/"launch-evidence.json",
        confirmation=result.session.confirmation,expected_checkpoint=CHECKPOINT,session_id="3"*32,
        economics_policy_path=tmp_path/"economics-policy.json",risk_policy_path=tmp_path/"risk.json",
        public_evidence_root=tmp_path/"public",
        public_evidence_receipt_path=next((tmp_path/"public").glob("*.receipt.json")),as_of=T,
        specification_bundle_path=bundle,specification_repository_root=tmp_path)
    assert strategy.economic_gate is not None and strategy.economic_gate.eligibility.eligible
    assert strategy.session.bridge.initial_accounting.instrument==instrument
    assert strategy.specification_bundle_id is not None


def test_strategy_assembly_accepts_explicit_paper_only_bundle(tmp_path):
    result,_=prepared(tmp_path)
    values=dict(economics_policy_path=tmp_path/"economics-policy.json",
        risk_policy_path=tmp_path/"risk.json",public_evidence_root=tmp_path/"public",
        public_evidence_receipt_path=next((tmp_path/"public").glob("*.receipt.json")))
    bundle=tmp_path/"paper-specification-bundle.json"
    gate,_=compile_paper_specification_bundle(**values,as_of=T,output_path=bundle)
    strategy=assemble_supervised_btc_paper_session(session_root=tmp_path/"paper-strategy-session",
        archive_root=result.archive_root,evidence_path=tmp_path/"launch-evidence.json",
        confirmation=result.session.confirmation,expected_checkpoint=CHECKPOINT,session_id="4"*32,
        **values,as_of=T,paper_specification_bundle_path=bundle)
    assert strategy.economic_gate==gate
    assert strategy.session.bridge.initial_accounting.instrument==gate.instrument
    assert strategy.public_evidence.receipt_id==strategy.public_evidence_id
    assert strategy.runtime.valuation.validation["mark_specification_id"]==gate.specification_ids[1]
    assert strategy.session.bridge.initial_accounting.policy.specification_ids.count(
        gate.specification_ids[1])==1


def test_assembly_source_has_no_live_execution_surface():
    source=Path(__file__).with_name("supervised_btc_paper_session_assembly_v1.py").read_text("utf-8").lower()
    for prohibited in ("urllib","requests","websocket","credential","private_key","signing","broker"):
        assert prohibited not in source
    assert "trading_authority: bool=false" in source
