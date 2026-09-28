from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal

import pytest

from backtesting.execution_accounting_v2.accounting import (
    FundingFactV2, MarginBasis, MarginSpecificationV2, PriceEvidenceV2,
)
from backtesting.execution_accounting_v2.contracts import OrderSide, OrderType
from backtesting.execution_accounting_v2.specifications import SpecificationType
from execution.btc_perpetual_economic_gate_v1 import evaluate_btc_perpetual_economics
from execution.btc_perpetual_strategy_intent_v1 import (
    BTCPerpetualStrategyIntentError, compile_btc_perpetual_strategy_intent,
)
from execution.strategy_paper_intent_v1 import _milliseconds
from execution.test_btc_perpetual_economic_gate_v1 import T, build
from execution.test_paper_performance_ledger_v1 import H
from execution.btc_perpetual_paper_specification_bundle_v1 import (
    BTCPerpetualPaperEconomicEligibilityV1,_id as paper_id,
)
from backtesting.execution_accounting_v2.specifications import Capability
from strategy.trading_brain.test_p29_1_entry_execution import inputs


def arguments(tmp_path):
    repo,instrument,precision=build(tmp_path)
    gate=evaluate_btc_perpetual_economics(repository=repo,repository_root=tmp_path,
        instrument=instrument,precision=precision,as_of=T)
    ids={item.specification_type:item.specification_id for item in repo.specifications}
    q,s,c,a=inputs(); ms=_milliseconds(T)
    mark=PriceEvidenceV2("price-evidence-v2-1",H("mark"),"BTC-PERP","BTC","BTC-PERP",
        T-timedelta(seconds=2),T-timedelta(seconds=1),Decimal("100"),"MARK",
        ids[SpecificationType.MARK_PRICE],"fixture")
    oracle=replace(mark,price_event_id=H("oracle"),price_type="ORACLE",
        specification_id=ids[SpecificationType.ORACLE_PRICE])
    funding=FundingFactV2("funding-fact-v2-1",H("funding"),"BTC-PERP","BTC","BTC-PERP",
        T-timedelta(hours=1),T-timedelta(minutes=1),Decimal("0.00001"),mark.price,oracle.price,
        (ids[SpecificationType.FUNDING],ids[SpecificationType.MARK_PRICE],
         ids[SpecificationType.ORACLE_PRICE]),"fixture")
    margin=MarginSpecificationV2("margin-specification-v2-1",ids[SpecificationType.MARGIN_TIER],
        "BTC-PERP","BTC","BTC-PERP",T,None,MarginBasis.NOTIONAL_RATE,
        Decimal("0.025"),Decimal("0.0125"),Decimal("0.025"),Decimal("0.0125"),"fixture")
    return dict(qualification=replace(q,finalized_time=ms),
        selection=replace(s,eligibility_time=ms-1000,selection_time=ms-1000,
                          minimum_tick=Decimal("1")),
        context=replace(c,confirmed_time=ms,minimum_tick=Decimal("1")),
        position_availability=replace(a,checked_time=ms),economics=gate,precision=precision,
        mark=mark,oracle=oracle,funding=funding,margin=margin,quantity=Decimal("0.00001"),
        quantity_evidence_sha256=H("quantity"),source_sha256=H("source"),
        source_closed_at=T-timedelta(minutes=1),source_available_at=T-timedelta(seconds=2),
        now=T,expires_at=T+timedelta(minutes=2),run_id=H("run"),
        configuration_version="fixture",execution_policy_version="paper-perp-v1")


def test_complete_perpetual_evidence_compiles_unsigned_advisory_intent(tmp_path):
    args=arguments(tmp_path); result=compile_btc_perpetual_strategy_intent(**args)
    assert result==compile_btc_perpetual_strategy_intent(**args)
    assert (result.intent.market,result.intent.instrument_id,result.intent.contract_id)==("BTC-PERP","BTC","BTC-PERP")
    assert result.intent.side is OrderSide.BUY and result.intent.order_type is OrderType.LIMIT
    assert result.intent.quantity==Decimal("0.00001") and result.intent.limit_price==Decimal("100")
    assert not result.submission_authorized and not result.protective_orders_created and not result.trading_authority
    with pytest.raises(FrozenInstanceError): result.receipt_id="x"


def test_explicit_paper_only_economic_gate_compiles_same_advisory_intent(tmp_path):
    args=arguments(tmp_path);old=args["economics"]
    report=replace(old.eligibility,capability=Capability.SUPERVISED_PAPER_ECONOMICS)
    gate_id=paper_id(report,old.instrument,args["precision"],old.specification_ids,
        old.evidence_ids,True,False,False)
    args["economics"]=BTCPerpetualPaperEconomicEligibilityV1(gate_id,report,
        old.instrument,args["precision"],old.specification_ids,old.evidence_ids,True,False,False)
    result=compile_btc_perpetual_strategy_intent(**args)
    assert result.economic_gate_id==gate_id and not result.trading_authority


@pytest.mark.parametrize("field,change",[
    ("mark",{"observed_at":T-timedelta(minutes=2),"available_at":T-timedelta(minutes=2)}),
    ("oracle",{"price_type":"MARK"}),
    ("funding",{"funding_time":T-timedelta(minutes=66),"available_at":T-timedelta(minutes=66)}),
    ("margin",{"effective_to":T+timedelta(minutes=1)}),
    ("context",{"minimum_tick":Decimal("0.1")}),
    ("position_availability",{"open_position_count":1}),
])
def test_stale_mismatched_or_unsafe_inputs_fail_closed(tmp_path,field,change):
    args=arguments(tmp_path); args[field]=replace(args[field],**change)
    with pytest.raises(BTCPerpetualStrategyIntentError):
        compile_btc_perpetual_strategy_intent(**args)


def test_dynamic_precision_and_notional_limit_fail_closed(tmp_path):
    args=arguments(tmp_path); args["qualification"]=replace(args["qualification"],
        entry=Decimal("12345.6"),stop=Decimal("12300"),target=Decimal("12400"),
        risk=Decimal("45.6"),reward=Decimal("54.4"),minimum_required_r=Decimal("1"))
    with pytest.raises(BTCPerpetualStrategyIntentError): compile_btc_perpetual_strategy_intent(**args)
    args=arguments(tmp_path);args["quantity"]=Decimal("1000")
    with pytest.raises(BTCPerpetualStrategyIntentError,match="notional"):
        compile_btc_perpetual_strategy_intent(**args)
