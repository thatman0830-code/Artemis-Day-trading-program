"""Recoverable coordinator for an offline supervised OCO resolution."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path

from backtesting.execution_accounting_v2.accounting import FillEconomicsV2
from backtesting.execution_accounting_v2.ohlc_execution import ExecutionFillV2
from backtesting.execution_accounting_v2.order_ledger import OrderLedgerEventV2
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1, PaperAdapterPairReceiptV1
from execution.paper_gateway_v2 import (
    PaperContingentResolutionV1, PaperEventKind, PaperOrderEventV1,
)
from execution.paper_oco_evidence_v1 import DurablePaperOCOReplayV1
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.paper_oco_gateway_bridge_v1 import (
    PaperOCOGatewayHandoffV1, build_oco_gateway_handoff,
)
from execution.paper_oco_initial_v1 import _pack, _unpack
from execution.paper_oco_supervised_transaction_v1 import (
    PaperOCOSupervisedStage, PaperOCOSupervisedTransactionError,
    PaperOCOSupervisedTransactionStoreV1, PaperOCOSupervisedTransactionV1,
)
from execution.paper_performance_checkpoint_v1 import _decode, _encode
from execution.supervised_paper_performance_v1 import (
    SupervisedPaperPerformanceV1, VerifiedPaperFillV1,
)
from execution.supervised_paper_workflow_v1 import SupervisedPaperCycleV1


EVIDENCE_VERSION = "paper-oco-supervised-evidence-v1"
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise PaperOCOSupervisedTransactionError("duplicate handoff evidence field")
        result[key]=value
    return result


def _event_doc(event):
    return dict(event_id=event.event_id, paper_order_id=event.paper_order_id,
        kind=event.kind.value, occurred_at=_encode(event.occurred_at),
        expected_version=event.expected_version,
        fill_quantity=_encode(event.fill_quantity), trading_authority=False)


def _event_load(doc):
    fields={"event_id","paper_order_id","kind","occurred_at","expected_version",
        "fill_quantity","trading_authority"}
    if type(doc) is not dict or set(doc)!=fields or doc["trading_authority"] is not False:
        raise PaperOCOSupervisedTransactionError("invalid retained paper event")
    return PaperOrderEventV1(doc["event_id"],doc["paper_order_id"],
        PaperEventKind(doc["kind"]),_decode(doc["occurred_at"]),doc["expected_version"],
        _decode(doc["fill_quantity"]),False)


def _handoff_doc(handoff):
    resolution=handoff.command.contingent_resolution
    return dict(version=EVIDENCE_VERSION,bridge_id=handoff.bridge_id,
        command_id=handoff.command.command_id,
        expected_gateway_snapshot_id=handoff.command.expected_gateway_snapshot_id,
        resolution=dict(resolution_id=resolution.resolution_id,pair_id=resolution.pair_id,
            paper_order_ids=list(resolution.paper_order_ids),fill=_event_doc(resolution.fill),
            cancellations=[_event_doc(item) for item in resolution.cancellations],
            trading_authority=False),
        execution_fill=_encode(handoff.verified_fill.fill),
        economics=_encode(handoff.verified_fill.economics),
        oco_cancellations=[_pack(item) for item in handoff.oco_cancellations],
        trading_authority=False)


def _handoff_load(doc):
    fields={"version","bridge_id","command_id","expected_gateway_snapshot_id",
        "resolution","execution_fill","economics","oco_cancellations","trading_authority"}
    if (type(doc) is not dict or set(doc)!=fields or doc["version"]!=EVIDENCE_VERSION
            or doc["trading_authority"] is not False):
        raise PaperOCOSupervisedTransactionError("invalid retained handoff evidence")
    raw=doc["resolution"]
    rfields={"resolution_id","pair_id","paper_order_ids","fill","cancellations","trading_authority"}
    if (type(raw) is not dict or set(raw)!=rfields or raw["trading_authority"] is not False
            or type(raw["paper_order_ids"]) is not list or type(raw["cancellations"]) is not list):
        raise PaperOCOSupervisedTransactionError("invalid retained resolution")
    resolution=PaperContingentResolutionV1(raw["resolution_id"],raw["pair_id"],
        tuple(raw["paper_order_ids"]),_event_load(raw["fill"]),
        tuple(_event_load(item) for item in raw["cancellations"]),False)
    command=PaperAdapterCommandV1(doc["command_id"],doc["expected_gateway_snapshot_id"],
        contingent_resolution=resolution)
    fill=_decode(doc["execution_fill"]);economics=_decode(doc["economics"])
    cancellations=tuple(_unpack(item) for item in doc["oco_cancellations"])
    if (type(fill) is not ExecutionFillV2 or type(economics) is not FillEconomicsV2
            or not cancellations or any(type(item) is not OrderLedgerEventV2 for item in cancellations)):
        raise PaperOCOSupervisedTransactionError("invalid retained typed handoff")
    verified=VerifiedPaperFillV1(resolution.fill,fill,economics)
    return PaperOCOGatewayHandoffV1(doc["bridge_id"],command,verified,cancellations,False)


class PaperOCOSupervisedCoordinatorV1:
    def __init__(self, *, runner: DurablePaperOCOReplayV1,
                 performance: SupervisedPaperPerformanceV1):
        if type(runner) is not DurablePaperOCOReplayV1 or type(performance) is not SupervisedPaperPerformanceV1:
            raise PaperOCOSupervisedTransactionError("typed durable coordinators required")
        self.runner=runner;self.performance=performance
        self.transactions=PaperOCOSupervisedTransactionStoreV1(runner.journal.root)
        self.evidence_path=Path(runner.journal.root)/"oco-supervised-evidence.json"

    def _put_handoff(self,handoff):
        payload=_handoff_doc(handoff)
        envelope={"payload":payload,"payload_sha256":canonical_fingerprint(payload)}
        raw=json.dumps(envelope,sort_keys=True,separators=(",",":"),allow_nan=False).encode()+b"\n"
        if len(raw)>MAX_EVIDENCE_BYTES:raise PaperOCOSupervisedTransactionError("handoff evidence size limit")
        try:
            with self.evidence_path.open("xb") as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
        except FileExistsError:pass
        retained=self._load_handoff()
        if retained!=handoff:raise PaperOCOSupervisedTransactionError("retained handoff conflicts")
        with self.evidence_path.open("r+b") as stream:stream.flush();os.fsync(stream.fileno())

    def _load_handoff(self):
        self.runner.journal._safe()
        if self.evidence_path.is_symlink() or not self.evidence_path.is_file():
            raise PaperOCOSupervisedTransactionError("handoff evidence missing or unsafe")
        try:
            raw=self.evidence_path.read_bytes()
            if not raw or len(raw)>MAX_EVIDENCE_BYTES:raise ValueError("size")
            doc=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constant")))
            if type(doc) is not dict or set(doc)!={"payload","payload_sha256"}:
                raise ValueError("envelope")
            if doc["payload_sha256"]!=canonical_fingerprint(doc["payload"]):
                raise ValueError("checksum")
            return _handoff_load(doc["payload"])
        except (OSError,UnicodeError,json.JSONDecodeError,ValueError,TypeError,KeyError) as exc:
            if isinstance(exc,PaperOCOSupervisedTransactionError):raise
            raise PaperOCOSupervisedTransactionError("handoff evidence is unreadable") from exc

    def prepare(self, *, pair_receipt: PaperAdapterPairReceiptV1,
                economics: FillEconomicsV2, resolved_at: datetime):
        oco_doc,coordinator=self.runner.load()
        adapter=self.performance.workflow.store.load();ledger=self.performance.store.load()
        handoff=build_oco_gateway_handoff(coordinator=coordinator,result=coordinator.pending,
            adapter=adapter,pair_receipt=pair_receipt,economics=economics,resolved_at=resolved_at)
        value=PaperOCOSupervisedTransactionV1.prepare(bridge_id=handoff.bridge_id,
            oco_before_checkpoint_id=oco_doc["checkpoint_id"],adapter_before_id=adapter.adapter_id,
            performance_before_id=ledger.ledger_id)
        self._put_handoff(handoff);return self.transactions.initialize(value)

    def resume(self):
        tx=self.transactions.load();handoff=self._load_handoff()
        if handoff.bridge_id!=tx.bridge_id:raise PaperOCOSupervisedTransactionError("transaction evidence mismatch")
        if tx.stage is PaperOCOSupervisedStage.PREPARED:
            at=max(event.occurred_at for event in handoff.command.contingent_resolution.cancellations)
            adapter,receipt,_,ledger=self.performance.cycle(
                SupervisedPaperCycleV1(at,at,handoff.command),verified_fill=handoff.verified_fill)
            if not receipt.accepted:raise PaperOCOSupervisedTransactionError("gateway resolution rejected")
            tx=self.transactions.advance(expected_transaction_id=tx.transaction_id,
                expected_stage=tx.stage,stage=PaperOCOSupervisedStage.PERFORMANCE_COMMITTED,
                adapter_after_id=adapter.adapter_id,performance_after_id=ledger.ledger_id)
        adapter=self.performance.workflow.store.load();ledger=self.performance.store.load()
        if adapter.adapter_id!=tx.adapter_after_id or ledger.ledger_id!=tx.performance_after_id:
            raise PaperOCOSupervisedTransactionError("committed performance state changed")
        if tx.stage is PaperOCOSupervisedStage.PERFORMANCE_COMMITTED:
            oco_doc,oco=self.runner.load()
            if oco_doc["checkpoint_id"]==tx.oco_before_checkpoint_id:
                acknowledged=self.runner.advance(kind="ACK",payload={"accounting":ledger.accounting},
                    expected_checkpoint_id=oco_doc["checkpoint_id"])
            elif (oco.state in ("FLAT_REQUIRES_SIBLING_CANCELLATION","PARTIAL_REQUIRES_REARM")
                    and oco.acknowledged_accounting==ledger.accounting):
                acknowledged=oco_doc
            else:
                raise PaperOCOSupervisedTransactionError("OCO checkpoint changed before acknowledgement")
            tx=self.transactions.advance(expected_transaction_id=tx.transaction_id,
                expected_stage=tx.stage,stage=PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED,
                oco_accounting_checkpoint_id=acknowledged["checkpoint_id"])
        if tx.stage is PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED:
            oco_doc,oco=self.runner.load()
            if oco_doc["checkpoint_id"]==tx.oco_accounting_checkpoint_id:
                final=self.runner.advance(kind="CANCEL_ACK",
                    payload={"accounting":ledger.accounting,"cancellations":handoff.oco_cancellations},
                    expected_checkpoint_id=oco_doc["checkpoint_id"])
            elif (oco.state in ("CLOSED_FLAT","CANCELLED_REQUIRES_REARM")
                    and oco.acknowledged_accounting==ledger.accounting):
                final=oco_doc
            else:
                raise PaperOCOSupervisedTransactionError("OCO accounting checkpoint changed")
            tx=self.transactions.advance(expected_transaction_id=tx.transaction_id,
                expected_stage=tx.stage,stage=PaperOCOSupervisedStage.COMMITTED,
                oco_final_checkpoint_id=final["checkpoint_id"])
        if tx.stage is not PaperOCOSupervisedStage.COMMITTED:
            raise PaperOCOSupervisedTransactionError("transaction did not commit")
        final_doc,coordinator=self.runner.load()
        if final_doc["checkpoint_id"]!=tx.oco_final_checkpoint_id or coordinator.state not in (
                "CLOSED_FLAT","CANCELLED_REQUIRES_REARM"):
            raise PaperOCOSupervisedTransactionError("final OCO state does not reconcile")
        return tx,adapter,ledger,coordinator
