from datetime import timedelta
from decimal import Decimal

import pytest

from backtesting.execution_accounting_v2.accounting import FillEconomicsV2
from execution.paper_oco_evidence_v1 import DurablePaperOCOReplayV1
from execution.paper_oco_supervised_coordinator_v1 import PaperOCOSupervisedCoordinatorV1
from execution.paper_oco_supervised_transaction_v1 import PaperOCOSupervisedStage
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.supervised_paper_performance_v1 import SupervisedPaperPerformanceV1
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperPolicyV1, SupervisedPaperWorkflowV1,
)
from execution.test_paper_oco_execution_v1 import fixture, observed
from execution.test_paper_oco_gateway_bridge_v1 import prepared as bridge_prepared
from execution.test_paper_performance_ledger_v1 import H


def setup(tmp_path, volume="100"):
    args, _, _ = fixture()
    oco_root = tmp_path / "oco"; oco_root.mkdir()
    runner = DurablePaperOCOReplayV1(oco_root, initial=args)
    document = runner.initialize()
    bar = observed(volume=Decimal(volume))
    document = runner.advance(kind="EVALUATE",
        payload={"accounting":args["accounting"],"bar":bar,"evaluated_at":bar.available_at},
        expected_checkpoint_id=document["checkpoint_id"])

    _, result, adapter, receipt, _, resolved_at = bridge_prepared(volume)
    assert runner.load()[1].pending == result
    fill=result.evaluation.fills[0]
    costs=FillEconomicsV2("fill-economics-v2-1",H("cost"+fill.fill_id),fill.fill_id,
        Decimal(0),Decimal(0),
        fill.adverse_friction*fill.quantity*args["accounting"].instrument.contract_multiplier,
        "USD",(H("fee-spec"),),"cost-v1")
    root = tmp_path / "workflow"; root.mkdir()
    workflow = SupervisedPaperWorkflowV1(root,SupervisedPaperPolicyV1(timedelta(seconds=5)),
        adapter,"1"*32)
    workflow.acquire();workflow.start()
    performance = SupervisedPaperPerformanceV1(workflow,args["accounting"])
    performance.store.initialize(PaperPerformanceLedgerV1._build(
        adapter.gateway.snapshot_id,args["accounting"],()))
    coordinator = PaperOCOSupervisedCoordinatorV1(runner=runner,performance=performance)
    coordinator.prepare(pair_receipt=receipt,economics=costs,resolved_at=resolved_at)
    return workflow,coordinator


@pytest.mark.parametrize("volume,final_state", [
    ("100","CLOSED_FLAT"),("10","CANCELLED_REQUIRES_REARM")])
def test_commits_all_three_durable_stores(volume, final_state, tmp_path):
    workflow,coordinator=setup(tmp_path,volume)
    try:
        tx,adapter,ledger,oco=coordinator.resume()
        assert tx.stage is PaperOCOSupervisedStage.COMMITTED
        assert tx.adapter_after_id==adapter.adapter_id
        assert tx.performance_after_id==ledger.ledger_id
        assert oco.state==final_state
        assert ledger.accounting==oco.acknowledged_accounting
    finally:workflow.release()


@pytest.mark.parametrize("failed_stage", [
    PaperOCOSupervisedStage.PERFORMANCE_COMMITTED,
    PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED,
    PaperOCOSupervisedStage.COMMITTED])
def test_resume_after_progress_marker_write_interruption(tmp_path,monkeypatch,failed_stage):
    workflow,coordinator=setup(tmp_path)
    original=coordinator.transactions.advance;failed=False
    def interrupted(**kwargs):
        nonlocal failed
        if kwargs["stage"] is failed_stage and not failed:
            failed=True;raise BaseException("power loss")
        return original(**kwargs)
    monkeypatch.setattr(coordinator.transactions,"advance",interrupted)
    try:
        with pytest.raises(BaseException,match="power loss"):coordinator.resume()
        tx,_,ledger,oco=coordinator.resume()
        assert tx.stage is PaperOCOSupervisedStage.COMMITTED
        assert ledger.accounting==oco.acknowledged_accounting
    finally:workflow.release()


def test_corrupt_retained_handoff_blocks_before_store_progress(tmp_path):
    workflow,coordinator=setup(tmp_path)
    try:
        coordinator.evidence_path.write_bytes(b"corrupt")
        with pytest.raises(Exception):coordinator.resume()
        assert coordinator.transactions.load().stage is PaperOCOSupervisedStage.PREPARED
    finally:workflow.release()


def test_duplicate_handoff_field_is_rejected(tmp_path):
    workflow,coordinator=setup(tmp_path)
    try:
        raw=coordinator.evidence_path.read_text("utf-8").replace(
            '"payload":','"payload":{},"payload":',1)
        coordinator.evidence_path.write_text(raw,"utf-8")
        with pytest.raises(Exception,match="duplicate"):coordinator.resume()
        assert coordinator.transactions.load().stage is PaperOCOSupervisedStage.PREPARED
    finally:workflow.release()


def test_module_has_no_transport_or_runtime_launcher():
    from pathlib import Path
    source=Path(__file__).with_name("paper_oco_supervised_coordinator_v1.py").read_text("utf-8").lower()
    for word in ("requests","httpx","socket","websocket","api_key","private_key",
                 "place_order","submit_live","subprocess","scheduledtask"):
        assert word not in source
