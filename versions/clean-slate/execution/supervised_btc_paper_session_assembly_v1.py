"""Assemble verified local dependencies for one supervised BTC paper session.

This module has no external-data, fill-generation, or live-order transport.
It creates a fresh paper-only ledger/gateway and a no-signal-safe archive reader.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from backtesting.execution_accounting_v2.accounting import (
    ACCOUNTING_VERSION, AccountingPolicyV2, InstrumentAccountingLedgerV2,
    MarginBasis, MarginSpecificationV2,
)
from backtesting.execution_accounting_v2.contracts import InstrumentSpecificationV2
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from execution.bounded_paper_session_v1 import BoundedPaperSessionV1
from execution.btc_archive_snapshot_source_v1 import read_btc_archive_snapshot
from execution.btc_perpetual_paper_economics_policy_v1 import read_policy
from execution.btc_perpetual_paper_risk_policy_v1 import read_risk_policy
from execution.btc_perpetual_economic_gate_v1 import (
    BTCPerpetualEconomicEligibilityV1,evaluate_btc_perpetual_economics,
)
from execution.btc_perpetual_specification_bundle_v1 import (
    read_btc_perpetual_specification_bundle,
)
from execution.btc_perpetual_paper_specification_bundle_v1 import (
    BTCPerpetualPaperEconomicEligibilityV1,read_paper_specification_bundle,
)
from execution.btc_perpetual_public_evidence_collector_v1 import (
    BTCPerpetualPublicEvidenceV1, read_btc_perpetual_public_evidence,
)
from execution.paper_exchange_adapter_v1 import PaperExchangeAdapterV1
from execution.paper_file_valuation_v1 import PaperFileValuationV1
from execution.paper_gateway_v2 import PaperGatewayPolicyV1, PaperGatewaySnapshotV1
from execution.supervised_btc_paper_runtime_v1 import (
    SupervisedBTCPaperRuntimeV1, SupervisedPaperRuntimeInputV1,
)
from execution.supervised_paper_launch_evidence_v1 import OwnerSupervisionConfirmationV1


VERSION="supervised-btc-paper-session-assembly-v1"


class BTCPaperSessionAssemblyError(ValueError): pass


def _id(*values):
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(",",":"),
        default=str).encode()).hexdigest()


@dataclass(frozen=True,slots=True)
class SupervisedBTCPaperSessionAssemblyV1:
    runtime: SupervisedBTCPaperRuntimeV1
    session: BoundedPaperSessionV1
    archive_root: Path
    snapshot_root: Path
    economics_policy_id: str
    risk_policy_id: str
    public_evidence: BTCPerpetualPublicEvidenceV1
    economic_gate: BTCPerpetualEconomicEligibilityV1|BTCPerpetualPaperEconomicEligibilityV1|None
    specification_bundle_id: str|None
    assembly_id: str
    trading_authority: bool=False

    def __post_init__(self):
        if (not isinstance(self.runtime,SupervisedBTCPaperRuntimeV1)
                or not isinstance(self.session,BoundedPaperSessionV1)
                or not isinstance(self.public_evidence,BTCPerpetualPublicEvidenceV1)
                or self.runtime.valuation.clock.session is not self.session
                or self.trading_authority is not False):
            raise BTCPaperSessionAssemblyError("assembly dependency or authority mismatch")
        self.public_evidence.__post_init__()
        expected=_id(VERSION,self.session.workflow.session_id,str(self.archive_root.absolute()),str(self.snapshot_root.absolute()),
            self.economics_policy_id,self.risk_policy_id,self.public_evidence.receipt_id,
            None if self.economic_gate is None else self.economic_gate.gate_id,
            self.specification_bundle_id,False)
        if self.assembly_id!=expected:
            raise BTCPaperSessionAssemblyError("assembly identity mismatch")

    @property
    def public_evidence_id(self):
        return self.public_evidence.receipt_id

    def no_signal_input(self, *, as_of: datetime):
        snapshot=read_btc_archive_snapshot(self.archive_root,timeframe="1m",as_of=as_of,
            snapshot_root=self.snapshot_root)
        return SupervisedPaperRuntimeInputV1(snapshot.reference)


def assemble_supervised_btc_paper_session(*,session_root,archive_root,evidence_path,
        confirmation,expected_checkpoint,session_id,economics_policy_path,risk_policy_path,
        public_evidence_root,public_evidence_receipt_path,as_of,
        specification_bundle_path=None,specification_repository_root=None,
        paper_specification_bundle_path=None):
    if (not isinstance(confirmation,OwnerSupervisionConfirmationV1)
            or as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0)):
        raise BTCPaperSessionAssemblyError("typed confirmation and UTC as_of are required")
    economics=read_policy(economics_policy_path);risk=read_risk_policy(risk_policy_path)
    public=read_btc_perpetual_public_evidence(output_root=public_evidence_root,
        receipt_path=public_evidence_receipt_path)
    approved_public=read_btc_perpetual_public_evidence(output_root=public_evidence_root,
        receipt_path=Path(public_evidence_root)/(risk["source_ids"][1]+".receipt.json"))
    immutable_public=lambda item:(item.asset_index,item.size_decimals,item.maximum_leverage,
        item.margin_table_id)
    if (risk["source_ids"][0]!=economics["policy_id"]
            or immutable_public(approved_public)!=immutable_public(public)
            or not timedelta(0)<=as_of-public.captured_at<=timedelta(minutes=1)):
        raise BTCPaperSessionAssemblyError("policy lineage or public evidence freshness failed")
    if risk["values"]!={
        "price_increment_usd":"1","collateral_fraction":"1","leverage_credit":"0",
        "maximum_total_exposure_usd":"100","maximum_positions":1,"maximum_entry_orders":1,
        "maximum_session_loss_usd":"5","maximum_session_drawdown_usd":"5",
        "fail_closed_evidence":["CLOCK","FUNDING","MARK","ORACLE","RECONCILIATION","RECORDER"]}:
        raise BTCPaperSessionAssemblyError("risk policy values are incompatible")
    archive=Path(archive_root).absolute()
    read_btc_archive_snapshot(archive,timeframe="1m",as_of=as_of)
    gate=None;bundle_id=None
    if specification_bundle_path is not None and paper_specification_bundle_path is not None:
        raise BTCPaperSessionAssemblyError("only one specification bundle type is permitted")
    if paper_specification_bundle_path is not None:
        gate,bundle_id=read_paper_specification_bundle(paper_specification_bundle_path,
            economics_policy_path=economics_policy_path,risk_policy_path=risk_policy_path,
            public_evidence_root=public_evidence_root,
            public_evidence_receipt_path=public_evidence_receipt_path)
        instrument=gate.instrument;precision=gate.precision
        margin_id=gate.specification_ids[4]
    elif specification_bundle_path is not None:
        if specification_repository_root is None:
            raise BTCPaperSessionAssemblyError("specification repository root is required")
        repository,instrument,precision,bundle_id=read_btc_perpetual_specification_bundle(
            specification_bundle_path)
        gate=evaluate_btc_perpetual_economics(repository=repository,
            repository_root=specification_repository_root,instrument=instrument,
            precision=precision,as_of=as_of)
        if (precision.size_decimals!=public.size_decimals or instrument.tick_size!=Decimal("1")
                or instrument.contract_multiplier!=Decimal("1")):
            raise BTCPaperSessionAssemblyError("strategy specification conflicts with public or risk evidence")
        from backtesting.execution_accounting_v2.specifications import SpecificationType
        margin_record=repository.resolve(SpecificationType.MARGIN_TIER,"BTC-PERP","BTC",as_of)
        if margin_record is None:raise BTCPaperSessionAssemblyError("effective margin specification is absent")
        margin_id=margin_record.specification_id
    else:
        instrument_id=_id(VERSION,"instrument",public.receipt_id,risk["policy_id"])
        instrument_sources=tuple(dict.fromkeys((approved_public.receipt_id,public.receipt_id)))
        instrument=InstrumentSpecificationV2("instrument-spec-v2-1",instrument_id,"BTC-PERP",
            "BTC","BTC-PERP",InstrumentProfile.BTC_LINEAR_PERPETUAL,"USDC",Decimal("1"),
            Decimal(1).scaleb(-public.size_decimals),Decimal("1"),None,approved_public.captured_at,None,
            instrument_sources)
        margin_id=_id(VERSION,"margin",risk["policy_id"])
    margin=MarginSpecificationV2("margin-specification-v2-1",margin_id,"BTC-PERP","BTC",
        "BTC-PERP",approved_public.captured_at,None,MarginBasis.NOTIONAL_RATE,
        Decimal("1"),Decimal("1"),Decimal("1"),Decimal("1"),VERSION)
    # A strategy-capable assembly must use the exact approved mark specification.
    # The operational no-signal assembly has no economic gate and retains its
    # content-addressed local valuation identity.
    mark_id=(gate.specification_ids[1] if gate is not None else
        _id(VERSION,"mark",public.receipt_id))
    accounting_policy=AccountingPolicyV2("accounting-policy-v2-1",ACCOUNTING_VERSION,
        "btc-paper-approved-cost-v1","MARK",True,
        tuple(dict.fromkeys((economics["policy_id"],risk["policy_id"],public.receipt_id,
            mark_id,*(() if gate is None else gate.specification_ids)))))
    run_id=_id(VERSION,"run",session_id,expected_checkpoint,risk["policy_id"])
    book=InstrumentAccountingLedgerV2.create(run_id=run_id,starting_cash=Decimal("100"),
        instrument=instrument,policy=accounting_policy,margin_specification=margin)
    gateway=PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(
        Decimal("100"),Decimal("100"),1,timedelta(seconds=5)))
    adapter=PaperExchangeAdapterV1.create(gateway)
    root=Path(session_root);root.mkdir(parents=True,exist_ok=True)
    snapshot_root=root.parent/(root.name+"-market-snapshots")
    read_btc_archive_snapshot(archive,timeframe="1m",as_of=as_of,snapshot_root=snapshot_root)
    session=BoundedPaperSessionV1(root=root,initial_adapter=adapter,initial_accounting=book,
        evidence_path=evidence_path,confirmation=confirmation,
        expected_checkpoint=expected_checkpoint,session_id=session_id,
        refresh_launch_evidence_each_step=False)
    valuation=PaperFileValuationV1(session=session,snapshot_root=snapshot_root,timeframe="1m",
        maximum_bar_age=timedelta(minutes=2),instrument_id="BTC",
        mark_specification_id=mark_id,source_version="btc-forward-archive-v1",
        market="BTC-PERP",contract_id="BTC-PERP")
    # Two independent health refreshes occur per cycle. Keep the wait at two
    # seconds so their measured runtime remains inside the five-second gap guard.
    runtime=SupervisedBTCPaperRuntimeV1(valuation,poll_interval=timedelta(seconds=2))
    assembly_id=_id(VERSION,session_id,str(archive),str(snapshot_root.absolute()),economics["policy_id"],
        risk["policy_id"],public.receipt_id,None if gate is None else gate.gate_id,bundle_id,False)
    return SupervisedBTCPaperSessionAssemblyV1(runtime,session,archive,snapshot_root,
        economics["policy_id"],risk["policy_id"],public,gate,bundle_id,assembly_id,False)
