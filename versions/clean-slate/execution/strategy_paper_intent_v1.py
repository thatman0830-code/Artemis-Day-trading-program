"""Translate frozen strategy qualification into an advisory V2 limit intent.

No gateway submission, fill generation, sizing approval, or protective execution.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from strategy.trading_brain.p29_1_entry_execution import (
    EntryExecutionEngine, EntryExecutionContext, PositionAvailability, ExecutionMode,
)
from strategy.trading_brain.p27_setup_qualification import FinalSetupQualification
from strategy.trading_brain.p28_entry_zone_selection import EntryZoneSelection
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from backtesting.execution_accounting_v2.contracts import (
    OrderIntentV2, OrderSide, OrderType, TimeInForce, InstrumentSpecificationV2,
)
from backtesting.execution_accounting_v2.specifications import InstrumentProfile, canonical_fingerprint
from backtesting.execution_accounting_v2.validation import validate_order_against_instrument, is_on_grid
from execution.paper_closed_bar_input_v1 import _sha, _utc
from execution.supervised_paper_launch_decision_v1 import MAXIMUM_ORDER_NOTIONAL

VERSION = "strategy-paper-intent-v1"


class StrategyPaperIntentError(ValueError):
    pass


def _milliseconds(value):
    _utc(value)
    if value.microsecond % 1000:
        raise StrategyPaperIntentError("exact millisecond timestamp required")
    delta = value-datetime(1970,1,1,tzinfo=timezone.utc)
    return (delta.days*86400+delta.seconds)*1000+delta.microseconds//1000


@dataclass(frozen=True, slots=True)
class StrategyPaperIntentV1:
    receipt_id: str
    intent: OrderIntentV2
    strategy_order_id: str
    stop_price: Decimal
    target_price: Decimal
    source_sha256: str
    quantity_evidence_sha256: str
    input_fingerprint: str
    submission_authorized: bool = False
    protective_orders_created: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if any(value is not False for value in (self.submission_authorized,
                self.protective_orders_created,self.trading_authority)):
            raise StrategyPaperIntentError("translation cannot grant authority or create protection")


def compile_strategy_paper_intent(*, qualification, selection, context,
        position_availability, instrument, quantity, quantity_evidence_sha256,
        source_sha256, source_closed_at, source_available_at, now, expires_at,
        run_id, configuration_version, execution_policy_version):
    """Inputs are trusted frozen records, not authenticated serialized evidence.

    The provided quantity remains a proposal, even if accompanied by evidence.
    Source hash binds supplied lineage but does not reconstruct qualification.
    """
    for value, expected in ((qualification,FinalSetupQualification),(selection,EntryZoneSelection),
            (context,EntryExecutionContext),(position_availability,PositionAvailability),
            (instrument,InstrumentSpecificationV2)):
        if not isinstance(value,expected):
            raise StrategyPaperIntentError("typed frozen strategy and instrument inputs required")
    for value in (qualification,selection,context,position_availability):
        if value.immutable is not True:
            raise StrategyPaperIntentError("immutable strategy inputs required")
    for value in (quantity_evidence_sha256,source_sha256,run_id): _sha(value)
    now_ms = _milliseconds(now)
    for timestamp in (source_closed_at,source_available_at,expires_at): _utc(timestamp)
    if not source_closed_at <= source_available_at <= now < expires_at <= now+timedelta(minutes=5):
        raise StrategyPaperIntentError("source or expiry chronology invalid")
    if now-source_closed_at > timedelta(minutes=16):
        raise StrategyPaperIntentError("source bar is stale")
    times = (qualification.finalized_time,selection.eligibility_time,selection.selection_time,
             context.confirmed_time,position_availability.checked_time)
    if any(type(t) is not int or t < 0 or t > now_ms for t in times):
        raise StrategyPaperIntentError("exact nonfuture epoch-millisecond strategy times required")
    if (now_ms-qualification.finalized_time > 300000
            or qualification.finalized_time < _milliseconds(source_available_at)):
        raise StrategyPaperIntentError("qualification is stale or precedes source availability")
    if (context.mode is not ExecutionMode.PAPER or context.symbol != "BTC"
            or context.timeframe not in ("1m","15m")
            or instrument.profile is not InstrumentProfile.BTC_SPOT
            or (instrument.market,instrument.instrument_id,instrument.contract_id) != ("BTC","BTC",None)
            or qualification.direction is not StructuralRegime.BULLISH):
        raise StrategyPaperIntentError("only BTC spot bullish paper entries are supported")
    if (position_availability.confirmed is not True
            or type(position_availability.open_position_count) is not int
            or position_availability.open_position_count != 0):
        raise StrategyPaperIntentError("confirmed flat position required")
    q = qualification
    for value in (q.entry,q.stop,q.target,q.risk,q.reward,q.minimum_required_r,quantity,context.minimum_tick):
        if type(value) is not Decimal or not value.is_finite() or value <= 0:
            raise StrategyPaperIntentError("positive exact Decimal economics required")
    if (q.geometry_valid is not True or q.executable is not True or not q.stop < q.entry < q.target
            or q.risk != q.entry-q.stop or q.reward != q.target-q.entry
            or q.reward < q.minimum_required_r*q.risk):
        raise StrategyPaperIntentError("qualification geometry or reward/risk conflicts")
    if context.minimum_tick != instrument.tick_size or any(
            not is_on_grid(price,instrument.tick_size) for price in (q.entry,q.stop,q.target)):
        raise StrategyPaperIntentError("entry/protection tick grid mismatch")
    if quantity*q.entry*instrument.contract_multiplier > MAXIMUM_ORDER_NOTIONAL:
        raise StrategyPaperIntentError("bounded paper order notional exceeded")
    if instrument.effective_to is not None and expires_at > instrument.effective_to:
        raise StrategyPaperIntentError("intent outlives instrument specification")
    result = EntryExecutionEngine().create_order(qualification=q,selection=selection,context=context,
        position_availability=position_availability,created_time=now_ms)
    if not result.valid or result.order is None:
        raise StrategyPaperIntentError("strategy rejected: " + result.error.reason)
    inputs_id = canonical_fingerprint(VERSION,q,selection,context,position_availability,instrument,
        quantity,quantity_evidence_sha256,source_sha256,source_closed_at,source_available_at,
        now,expires_at,run_id,configuration_version,execution_policy_version)
    intent = OrderIntentV2("order-intent-v2-1",canonical_fingerprint(VERSION,"order",inputs_id),
        run_id,canonical_fingerprint(VERSION,"action",inputs_id),"BTC","BTC",None,
        OrderSide.BUY,quantity,OrderType.LIMIT,TimeInForce.GTC,q.entry,None,now,now,expires_at,
        None,None,configuration_version,execution_policy_version)
    report = validate_order_against_instrument(intent,instrument)
    if not report.valid:
        raise StrategyPaperIntentError("instrument validation: " + ",".join(i.field for i in report.issues))
    receipt_id = canonical_fingerprint(VERSION,inputs_id,intent,result.order,q.stop,q.target)
    return StrategyPaperIntentV1(receipt_id,intent,result.order.id,q.stop,q.target,
        source_sha256,quantity_evidence_sha256,inputs_id)
