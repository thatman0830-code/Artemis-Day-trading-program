"""Compile a canonical strategy qualification into an advisory BTC-perp intent."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from backtesting.execution_accounting_v2.accounting import (
    FundingFactV2, MarginSpecificationV2, PriceEvidenceV2,
)
from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderSide, OrderType, TimeInForce
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint
from backtesting.execution_accounting_v2.validation import validate_order_against_instrument
from execution.btc_perpetual_economic_gate_v1 import BTCPerpetualEconomicEligibilityV1
from execution.btc_perpetual_paper_specification_bundle_v1 import (
    BTCPerpetualPaperEconomicEligibilityV1,
)
from execution.hyperliquid_perpetual_precision_v1 import HyperliquidBTCPerpetualPrecisionV1
from execution.hyperliquid_perpetual_precision_v1 import HyperliquidPerpetualPrecisionError
from execution.strategy_paper_intent_v1 import _milliseconds
from execution.paper_closed_bar_input_v1 import _sha, _utc
from execution.supervised_paper_launch_decision_v1 import MAXIMUM_ORDER_NOTIONAL
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import FinalSetupQualification
from strategy.trading_brain.p28_entry_zone_selection import EntryZoneSelection
from strategy.trading_brain.p29_1_entry_execution import (
    EntryExecutionContext, EntryExecutionEngine, ExecutionMode, PositionAvailability,
)


VERSION = "btc-perpetual-strategy-intent-v1"


class BTCPerpetualStrategyIntentError(ValueError): pass


@dataclass(frozen=True, slots=True)
class BTCPerpetualStrategyIntentV1:
    receipt_id: str
    intent: OrderIntentV2
    strategy_order_id: str
    stop_price: Decimal
    target_price: Decimal
    economic_gate_id: str
    source_sha256: str
    input_fingerprint: str
    submission_authorized: bool = False
    protective_orders_created: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if any(value is not False for value in (self.submission_authorized,
                self.protective_orders_created, self.trading_authority)):
            raise BTCPerpetualStrategyIntentError("intent cannot grant trading authority")


def compile_btc_perpetual_strategy_intent(*, qualification, selection, context,
        position_availability, economics, precision, mark, oracle, funding, margin,
        quantity, quantity_evidence_sha256, source_sha256, source_closed_at,
        source_available_at, now, expires_at, run_id, configuration_version,
        execution_policy_version):
    required=((qualification,FinalSetupQualification),(selection,EntryZoneSelection),
        (context,EntryExecutionContext),(position_availability,PositionAvailability),
        (precision,HyperliquidBTCPerpetualPrecisionV1),(mark,PriceEvidenceV2),
        (oracle,PriceEvidenceV2),(funding,FundingFactV2),(margin,MarginSpecificationV2))
    if any(not isinstance(value, expected) for value,expected in required):
        raise BTCPerpetualStrategyIntentError("typed frozen perpetual inputs are required")
    if not isinstance(economics,(BTCPerpetualEconomicEligibilityV1,
            BTCPerpetualPaperEconomicEligibilityV1)):
        raise BTCPerpetualStrategyIntentError("typed frozen perpetual economics are required")
    if (economics.live_trading_permitted or economics.trading_authority
            or not economics.eligibility.eligible
            or economics.precision_id != precision.precision_id):
        raise BTCPerpetualStrategyIntentError("economic or precision identity mismatch")
    instrument=economics.instrument
    for value in (quantity_evidence_sha256,source_sha256,run_id): _sha(value)
    now_ms=_milliseconds(now)
    for value in (source_closed_at,source_available_at,expires_at): _utc(value)
    if not source_closed_at <= source_available_at <= now < expires_at <= now+timedelta(minutes=5):
        raise BTCPerpetualStrategyIntentError("source or expiry chronology invalid")
    if now-source_closed_at > timedelta(minutes=16):
        raise BTCPerpetualStrategyIntentError("source bar is stale")
    if (context.mode is not ExecutionMode.PAPER or context.symbol!="BTC"
            or context.timeframe not in ("1m","15m")
            or qualification.direction is not StructuralRegime.BULLISH):
        raise BTCPerpetualStrategyIntentError("unsupported paper strategy context")
    times=(qualification.finalized_time,selection.eligibility_time,selection.selection_time,
        context.confirmed_time,position_availability.checked_time)
    if any(type(value) is not int or value<0 or value>now_ms for value in times):
        raise BTCPerpetualStrategyIntentError("strategy chronology invalid")
    if (now_ms-qualification.finalized_time>300000
            or qualification.finalized_time<_milliseconds(source_available_at)):
        raise BTCPerpetualStrategyIntentError("qualification is stale or precedes source")
    if (position_availability.confirmed is not True
            or type(position_availability.open_position_count) is not int
            or position_availability.open_position_count!=0):
        raise BTCPerpetualStrategyIntentError("confirmed flat position required")
    q=qualification
    if (q.geometry_valid is not True or q.executable is not True
            or not q.stop<q.entry<q.target or q.risk!=q.entry-q.stop
            or q.reward!=q.target-q.entry or q.reward<q.minimum_required_r*q.risk):
        raise BTCPerpetualStrategyIntentError("qualification geometry is invalid")
    try:
        precision.validate_order_geometry(entry=q.entry,stop=q.stop,target=q.target,quantity=quantity)
    except HyperliquidPerpetualPrecisionError as exc:
        raise BTCPerpetualStrategyIntentError("perpetual precision validation failed") from exc
    if context.minimum_tick!=instrument.tick_size:
        raise BTCPerpetualStrategyIntentError("strategy tick conflicts with instrument")
    identity=("BTC-PERP","BTC","BTC-PERP")
    if any((item.market,item.instrument_id,item.contract_id)!=identity
           for item in (mark,oracle,funding,margin)):
        raise BTCPerpetualStrategyIntentError("perpetual evidence identity mismatch")
    if mark.price_type!="MARK" or oracle.price_type!="ORACLE":
        raise BTCPerpetualStrategyIntentError("mark and oracle evidence types are required")
    if not mark.available_at<=now or not oracle.available_at<=now or now-mark.available_at>timedelta(minutes=1) or now-oracle.available_at>timedelta(minutes=1):
        raise BTCPerpetualStrategyIntentError("mark or oracle evidence is stale or future")
    if (funding.available_at>now or now-funding.available_at>timedelta(minutes=65)
            or funding.mark_price!=mark.price or funding.oracle_price!=oracle.price):
        raise BTCPerpetualStrategyIntentError("funding evidence is stale or inconsistent")
    if (margin.effective_from>now or (margin.effective_to is not None and expires_at>margin.effective_to)):
        raise BTCPerpetualStrategyIntentError("margin specification is not effective")
    lineage={mark.specification_id,oracle.specification_id,margin.margin_specification_id,
             *funding.specification_ids}
    if not lineage.issubset(set(economics.specification_ids)):
        raise BTCPerpetualStrategyIntentError("economic evidence lineage is outside gate")
    if quantity*q.entry*instrument.contract_multiplier>MAXIMUM_ORDER_NOTIONAL:
        raise BTCPerpetualStrategyIntentError("bounded paper order notional exceeded")
    result=EntryExecutionEngine().create_order(qualification=q,selection=selection,context=context,
        position_availability=position_availability,created_time=now_ms)
    if not result.valid or result.order is None:
        raise BTCPerpetualStrategyIntentError("strategy order creation rejected")
    inputs=canonical_fingerprint(VERSION,q,selection,context,position_availability,economics,
        precision,mark,oracle,funding,margin,quantity,quantity_evidence_sha256,source_sha256,
        source_closed_at,source_available_at,now,expires_at,run_id,configuration_version,
        execution_policy_version)
    intent=OrderIntentV2("order-intent-v2-1",canonical_fingerprint(VERSION,"order",inputs),
        run_id,canonical_fingerprint(VERSION,"action",inputs),*identity,OrderSide.BUY,quantity,
        OrderType.LIMIT,TimeInForce.GTC,q.entry,None,now,now,expires_at,None,None,
        configuration_version,execution_policy_version)
    if not validate_order_against_instrument(intent,instrument).valid:
        raise BTCPerpetualStrategyIntentError("instrument validation failed")
    receipt=canonical_fingerprint(VERSION,inputs,intent,result.order,q.stop,q.target)
    return BTCPerpetualStrategyIntentV1(receipt,intent,result.order.id,q.stop,q.target,
        economics.gate_id,source_sha256,inputs,False,False,False)
