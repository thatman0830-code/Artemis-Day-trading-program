from dataclasses import replace, FrozenInstanceError
from datetime import timedelta
from decimal import Decimal

import pytest

from execution.strategy_paper_intent_v1 import compile_strategy_paper_intent, StrategyPaperIntentError, _milliseconds
from strategy.trading_brain.test_p29_1_entry_execution import inputs
from strategy.trading_brain.p29_1_entry_execution import ExecutionMode
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from backtesting.execution_accounting_v2.contracts import OrderType, OrderSide
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from execution.test_paper_performance_ledger_v1 import T,H,accounting


def arguments():
    q,s,c,a = inputs()
    ms = _milliseconds(T)
    return dict(qualification=replace(q,finalized_time=ms),
        selection=replace(s,eligibility_time=ms-1000,selection_time=ms-1000),
        context=replace(c,confirmed_time=ms),position_availability=replace(a,checked_time=ms),
        instrument=replace(accounting().instrument,tick_size=Decimal("0.5")),quantity=Decimal("0.1"),
        quantity_evidence_sha256=H("synthetic quantity proposal"),source_sha256=H("synthetic candles"),
        source_closed_at=T-timedelta(minutes=1),source_available_at=T-timedelta(seconds=2),
        now=T,expires_at=T+timedelta(minutes=2),run_id=H("run"),
        configuration_version="fixture-config",execution_policy_version="CONSERVATIVE_OHLC_1M_V1")


def test_real_qualification_engine_to_v2_limit_contract_no_fill_or_authority():
    args = arguments()
    result = compile_strategy_paper_intent(**args)
    assert result == compile_strategy_paper_intent(**args)
    assert result.intent.order_type is OrderType.LIMIT
    assert result.intent.side is OrderSide.BUY
    assert result.intent.limit_price == Decimal("100")
    assert result.intent.quantity == Decimal("0.1")
    assert result.stop_price == Decimal("98") and result.target_price == Decimal("104")
    assert result.intent.stop_price is None  # Not a stop-limit entry; protection is separate.
    assert not result.submission_authorized and not result.protective_orders_created and not result.trading_authority
    with pytest.raises(FrozenInstanceError): result.stop_price = Decimal("99")
    for field in ("submission_authorized","protective_orders_created","trading_authority"):
        with pytest.raises(StrategyPaperIntentError): replace(result,**{field:True})


@pytest.mark.parametrize("field,changes",[
    ("qualification",dict(executable=False)),("qualification",dict(geometry_valid=False)),
    ("qualification",dict(stop=Decimal("101"))), ("qualification",dict(reward=Decimal("5"))),
    ("qualification",dict(minimum_required_r=Decimal("3"))),
    ("qualification",dict(direction=StructuralRegime.BEARISH)),
    ("qualification",dict(immutable=False)),
    ("context",dict(mode=ExecutionMode.TESTNET)),("context",dict(symbol="ES")),
    ("context",dict(minimum_tick=Decimal("0.25"))),
    ("position_availability",dict(open_position_count=1)),
    ("position_availability",dict(open_position_count=False)),
    ("position_availability",dict(confirmed="yes")),
    ("qualification",dict(finalized_time=True)),
    ("selection",dict(setup_id="different")),
])
def test_invalid_strategy_inputs_reject(field,changes):
    args=arguments(); args[field]=replace(args[field],**changes)
    with pytest.raises(StrategyPaperIntentError): compile_strategy_paper_intent(**args)


@pytest.mark.parametrize("quantity",[Decimal("0.0001"),Decimal("2"),Decimal("NaN"),0.1,True])
def test_quantity_grid_budget_and_types(quantity):
    args=arguments(); args["quantity"]=quantity
    with pytest.raises(StrategyPaperIntentError): compile_strategy_paper_intent(**args)


@pytest.mark.parametrize("field,value",[
    ("source_available_at",T+timedelta(seconds=1)),
    ("source_closed_at",T-timedelta(minutes=17)),
    ("expires_at",T),("expires_at",T+timedelta(minutes=6)),
    ("now",T.replace(tzinfo=None)),("now",T+timedelta(microseconds=1)),
    ("source_sha256",""),
])
def test_chronology_and_lineage_fail_closed(field,value):
    args=arguments(); args[field]=value
    with pytest.raises(ValueError): compile_strategy_paper_intent(**args)


def test_relabelled_qualification_before_available_source_rejects():
    args=arguments(); args["qualification"]=replace(args["qualification"],finalized_time=_milliseconds(T)-3000)
    with pytest.raises(StrategyPaperIntentError,match="precedes"):
        compile_strategy_paper_intent(**args)


def test_instrument_effective_date_and_protection_grid():
    for changes in (dict(effective_from=T+timedelta(seconds=1)),
                    dict(effective_to=T+timedelta(seconds=1))):
        args=arguments(); args["instrument"]=replace(args["instrument"],**changes)
        with pytest.raises(StrategyPaperIntentError): compile_strategy_paper_intent(**args)
    args=arguments()
    args["qualification"]=replace(args["qualification"],stop=Decimal("98.1"),risk=Decimal("1.9"))
    with pytest.raises(StrategyPaperIntentError,match="grid"): compile_strategy_paper_intent(**args)


def test_full_input_changes_bound_in_identity_not_just_strategy_ids():
    args=arguments(); first=compile_strategy_paper_intent(**args)
    for changes in (dict(source_sha256=H("other candles")),dict(quantity=Decimal("0.2")),
                    dict(quantity_evidence_sha256=H("other proposal")),dict(configuration_version="other")):
        second=compile_strategy_paper_intent(**{**args,**changes})
        assert second.receipt_id != first.receipt_id
        assert second.intent.order_id != first.intent.order_id
        assert second.strategy_order_id == first.strategy_order_id
