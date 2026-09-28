"""Convert one canonical BTC strategy observation into a durable paper reservation.

This module creates no submission request and carries no trading authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from backtesting.execution_accounting_v2.accounting import FundingFactV2, PriceEvidenceV2
from backtesting.execution_accounting_v2.risk_sessions import (
    PortfolioRiskContextV2, RiskLimitsV2, VerifiedSessionV2, RISK_POLICY_VERSION,
)
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from execution.btc_canonical_strategy_observation_v1 import BTCCanonicalStrategyObservationV1
from execution.btc_perpetual_paper_specification_bundle_v1 import BTCPerpetualPaperEconomicEligibilityV1
from execution.strategy_paper_intent_v1 import _milliseconds
from execution.strategy_paper_pretrade_v1 import PaperSizingPolicyV1
from execution.supervised_btc_paper_session_assembly_v1 import SupervisedBTCPaperSessionAssemblyV1
from execution.strategy_paper_pretrade_v1 import PaperPretradePlanV1,plan_strategy_paper_pretrade
from execution.paper_file_valuation_v1 import PaperSnapshotReferenceV1
from execution.supervised_btc_paper_runtime_v1 import prepare_btc_perpetual_runtime_input
from strategy.trading_brain.p29_1_entry_execution import EntryExecutionContext, ExecutionMode, PositionAvailability

VERSION="btc-canonical-paper-reservation-bridge-v1"


class BTCCanonicalPaperReservationError(ValueError):pass


@dataclass(frozen=True,slots=True)
class BTCCanonicalPaperReservationV1:
    checkpoint_id:str
    plan:PaperPretradePlanV1
    reference:PaperSnapshotReferenceV1
    observation_id:str
    trading_authority:bool=False

    def __post_init__(self):
        if (not isinstance(self.plan,PaperPretradePlanV1)
                or not isinstance(self.reference,PaperSnapshotReferenceV1)
                or self.plan.strategy_intent.source_sha256!=self.reference.sha256
                or self.trading_authority is not False):
            raise BTCCanonicalPaperReservationError("reservation receipt identity or authority mismatch")


def prepare_btc_canonical_paper_reservation(*,assembly,observation,as_of,
        expected_reservation_checkpoint_id):
    """Prepare, but never submit, one content-bound paper reservation."""
    if (not isinstance(assembly,SupervisedBTCPaperSessionAssemblyV1)
            or not isinstance(observation,BTCCanonicalStrategyObservationV1)
            or as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0)):
        raise BTCCanonicalPaperReservationError("typed canonical observation required")
    assembly.__post_init__()
    observation.__post_init__()
    if not observation.actionable:
        raise BTCCanonicalPaperReservationError("canonical observation is not actionable")
    if not assembly.session.active or assembly.session.deadline is None:
        raise BTCCanonicalPaperReservationError("active supervised paper session required")
    gate=assembly.economic_gate
    if not isinstance(gate,BTCPerpetualPaperEconomicEligibilityV1):
        raise BTCCanonicalPaperReservationError("explicit paper economics gate required")
    gate.__post_init__()
    public=assembly.public_evidence;public.__post_init__()
    if public.receipt_id not in gate.evidence_ids or not timedelta(0)<=as_of-public.captured_at<=timedelta(minutes=1):
        raise BTCCanonicalPaperReservationError("fresh public evidence outside paper gate")
    performance=assembly.session.bridge.store.load()
    gateway=assembly.session.workflow.store.load().gateway
    book=performance.accounting;snapshot=book.snapshot
    if performance.reconcile_gateway(gateway)!=performance:
        raise BTCCanonicalPaperReservationError("durable accounting and gateway differ")
    if not timedelta(0)<=as_of-snapshot.as_of<=timedelta(seconds=5):
        raise BTCCanonicalPaperReservationError("fresh durable accounting snapshot required")
    q=observation.result.setup_fact.final_qualification
    selection=observation.result.setup_fact.entry_zone
    source_closed=observation.result.context.evaluation_time
    source_available=observation.one_minute.reference.available_at
    if source_closed!=observation.one_minute.latest_close or source_available>as_of:
        raise BTCCanonicalPaperReservationError("canonical source chronology mismatch")
    now_ms=_milliseconds(as_of)
    identity=("BTC-PERP","BTC","BTC-PERP")
    mark=PriceEvidenceV2("price-evidence-v2-1",canonical_fingerprint(VERSION,"mark",public.receipt_id),
        *identity,public.captured_at,public.captured_at,public.mark_price,"MARK",gate.specification_ids[1],VERSION)
    oracle=PriceEvidenceV2("price-evidence-v2-1",canonical_fingerprint(VERSION,"oracle",public.receipt_id),
        *identity,public.captured_at,public.captured_at,public.oracle_price,"ORACLE",gate.specification_ids[2],VERSION)
    funding=FundingFactV2("funding-fact-v2-1",canonical_fingerprint(VERSION,"funding",public.receipt_id),
        *identity,public.captured_at,public.captured_at,public.funding_rate,mark.price,oracle.price,
        (gate.specification_ids[3],gate.specification_ids[1],gate.specification_ids[2]),VERSION)
    source_id=observation.result.source_candle_ids[-1]
    context=EntryExecutionContext(canonical_fingerprint(VERSION,"context",observation.observation_id,snapshot.snapshot_id),
        "BTC","1m",gate.instrument.tick_size,ExecutionMode.PAPER,now_ms,True)
    availability=PositionAvailability(canonical_fingerprint(VERSION,"availability",snapshot.snapshot_id),
        "BTC",0,_milliseconds(snapshot.as_of),True,True)
    close=assembly.session.deadline
    verified_session=VerifiedSessionV2.create(market=identity[0],instrument_id=identity[1],contract_id=identity[2],
        session_date=as_of.date(),timezone="UTC",open_time=as_of,close_time=close,
        effective_from=gate.instrument.effective_from,effective_to=gate.instrument.effective_to,
        calendar_version=VERSION,source_ids=(assembly.session.launch_decision.launch_id,))
    limits=RiskLimitsV2.create(run_id=book.run_id,market=identity[0],instrument_id=identity[1],contract_id=identity[2],
        effective_from=as_of,effective_to=close,max_gross_exposure=Decimal("100"),max_net_exposure=Decimal("100"),
        max_position_quantity=Decimal("100"),max_concentration=Decimal("1"),max_leverage=Decimal("1"),
        max_initial_margin=Decimal("100"),max_session_loss=Decimal("5"),max_drawdown=Decimal("5"),
        flatten_buffer_seconds=1,risk_policy_version=RISK_POLICY_VERSION,source_ids=(assembly.risk_policy_id,))
    equities=tuple(item.equity for item in book.snapshots)
    portfolio=PortfolioRiskContextV2.create(run_id=book.run_id,as_of=snapshot.as_of,equity=snapshot.equity,
        gross_exposure_before=Decimal("0"),net_exposure_before=Decimal("0"),
        session_reference_equity=equities[0],session_peak_equity=max(equities),
        source_snapshot_ids=(snapshot.snapshot_id,))
    expiry=min(as_of+timedelta(minutes=2),close-timedelta(seconds=1))
    sizing=PaperSizingPolicyV1(as_of,close,Decimal("0.05"),Decimal("5"),Decimal("0"),
        q.entry*Decimal("0.0013"),canonical_fingerprint(VERSION,"sizing",assembly.economics_policy_id,
            assembly.risk_policy_id,observation.observation_id))
    inputs=dict(qualification=q,selection=selection,context=context,position_availability=availability,
        economics=gate,precision=gate.precision,mark=mark,oracle=oracle,funding=funding,
        margin=book.margin_specification,source_sha256=observation.one_minute.reference.sha256,
        source_closed_at=source_closed,source_available_at=source_available,now=as_of,expires_at=expiry,
        run_id=book.run_id,configuration_version=observation.result.context.strategy_configuration_version,
        execution_policy_version=VERSION)
    pretrade=dict(strategy_inputs=inputs,
        performance=performance,gateway=gateway,context=portfolio,limits=limits,session=verified_session,
        sizing_policy=sizing,source_bar_id=source_id)
    plan=plan_strategy_paper_pretrade(**pretrade)
    checkpoint=assembly.session.reservation.prepare(pretrade_inputs=pretrade,
        expected_checkpoint_id=expected_reservation_checkpoint_id)
    record=checkpoint["body"]["reservation"]
    if (record["plan_id"]!=plan.plan_id or record["strategy_order_id"]!=plan.strategy_intent.strategy_order_id
            or record["order_id"]!=plan.strategy_intent.intent.order_id):
        raise BTCCanonicalPaperReservationError("durable reservation differs from typed plan")
    return BTCCanonicalPaperReservationV1(checkpoint["checkpoint_id"],plan,
        observation.one_minute.reference,observation.observation_id,False)


def prepare_reserved_btc_paper_runtime_input(*,assembly,reservation,launch,requested_at):
    """Form an in-memory paper command only from the current exact reservation."""
    if (not isinstance(assembly,SupervisedBTCPaperSessionAssemblyV1)
            or not isinstance(reservation,BTCCanonicalPaperReservationV1)
            or not assembly.session.active):
        raise BTCCanonicalPaperReservationError("active typed reservation boundary required")
    reservation.__post_init__()
    current=assembly.session.reservation.load()
    record=current["body"]["reservation"]
    plan=reservation.plan
    if (current["checkpoint_id"]!=reservation.checkpoint_id or current["body"]["state"]!="PREPARED"
            or record["plan_id"]!=plan.plan_id or record["gateway_snapshot_id"]!=assembly.session.workflow.store.load().gateway.snapshot_id):
        raise BTCCanonicalPaperReservationError("current durable reservation identity mismatch")
    if (not isinstance(launch,dict) or launch.get("launch_id")!=assembly.session.launch_decision.launch_id
            or launch.get("confirmation_id")!=assembly.session.confirmation.confirmation_id):
        raise BTCCanonicalPaperReservationError("launch authorization differs from active session")
    decision=assembly.session.launch_decision
    expected=(decision.evaluated_at.isoformat(),decision.expires_at.isoformat(),list(decision.permitted_markets),
        int(decision.maximum_session_duration.total_seconds()),decision.maximum_commands,
        str(decision.maximum_order_notional),str(decision.maximum_gross_exposure),decision.advisory_only,
        decision.live_trading_permitted,decision.trading_authority)
    actual=tuple(launch.get(name) for name in ("evaluated_at","expires_at","permitted_markets",
        "maximum_session_seconds","maximum_commands","maximum_order_notional","maximum_gross_exposure",
        "advisory_only","live_trading_permitted","trading_authority"))
    if actual!=expected:
        raise BTCCanonicalPaperReservationError("launch limits differ from active session")
    return prepare_btc_perpetual_runtime_input(plan=plan,launch=launch,reference=reservation.reference,
        expected_gateway_snapshot_id=record["gateway_snapshot_id"],requested_at=requested_at,
        market_data_at=assembly.public_evidence.captured_at)
