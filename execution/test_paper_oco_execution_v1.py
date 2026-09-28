from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from execution.paper_oco_execution_v1 import PaperOCOCoordinatorV1, PaperOCOError
from backtesting.execution_accounting_v2.test_ohlc_execution import (
    intent,ledger_for,instruction,bar,policy,START,H,
)
from backtesting.execution_accounting_v2.test_accounting import ledger,fill_event
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from backtesting.execution_accounting_v2.contracts import OrderSide,OrderType
from backtesting.execution_accounting_v2.accounting import AccountingEventV2,AccountingEventKind,FillEconomicsV2


def fixture(quantity="3"):
    book=ledger(InstrumentProfile.BTC_SPOT)
    book=book.apply(fill_event(book.instrument,"entry",OrderSide.BUY,quantity,"100"))
    common=dict(market="BTC",instrument_id="BTC",contract_id=None,side=OrderSide.SELL,
                quantity=Decimal(quantity),parent_order_id=H("order-entry"))
    stop=intent("oco-stop",order_type=OrderType.STOP_MARKET,stop_price=Decimal(99),**common)
    target=intent("oco-target",order_type=OrderType.LIMIT,limit_price=Decimal(101),**common)
    args=dict(accounting=book,ledger=ledger_for(stop,target),stop_order_id=stop.order_id,
        target_order_id=target.order_id,policy=policy(),instructions=(instruction(stop),instruction(target)),
        armed_at=START+timedelta(minutes=3))
    return args,stop,target


def observed(**kwargs):
    values=dict(market="BTC",instrument_id="BTC",contract_id=None,
        open_time=START+timedelta(minutes=3),close_time=START+timedelta(minutes=4),
        available_at=START+timedelta(minutes=4))
    return bar(**{**values,**kwargs})


def account(book,result):
    for value in result.evaluation.fills:
        costs=FillEconomicsV2("fill-economics-v2-1",H("cost"+value.fill_id),value.fill_id,
            Decimal(0),Decimal(0),value.adverse_friction*value.quantity*book.instrument.contract_multiplier,
            "USD",(H("fee-spec"),),"cost-v1")
        event=AccountingEventV2("accounting-event-v2-1",H("account"+value.fill_id),AccountingEventKind.FILL,
            value.fill_time,value.fill_time,fill=value,fill_economics=costs)
        book=book.apply(event)
    return book


@pytest.mark.parametrize("volume,state,remaining",[("100","FLAT_REQUIRES_SIBLING_CANCELLATION","0"),
    ("10","PARTIAL_REQUIRES_REARM","2")])
def test_both_touched_stop_wins_then_blocks_sibling_and_reconciles_actual_v2_fills(volume,state,remaining):
    args,stop,target=fixture(); coordinator=PaperOCOCoordinatorV1(**args)
    candle=observed(volume=Decimal(volume))
    result=coordinator.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])
    assert [f.order_id for f in result.evaluation.fills]==[stop.order_id]
    assert result.evaluation.suppressed_favorable_order_ids==(target.order_id,)
    assert result.projected_remaining_quantity==Decimal(remaining)
    assert result.state=="AWAITING_ACCOUNTING" and not result.trading_authority
    next_bar=observed(open_time=candle.close_time,close_time=candle.close_time+timedelta(minutes=1),
        available_at=candle.close_time+timedelta(minutes=1))
    with pytest.raises(PaperOCOError,match="blocked"):
        coordinator.evaluate(bar=next_bar,evaluated_at=next_bar.available_at,accounting=args["accounting"])
    book=account(args["accounting"],result)
    assert coordinator.acknowledge_accounting(book)==state
    assert book.snapshot.position.signed_quantity==Decimal(remaining)
    with pytest.raises(PaperOCOError,match="blocked"):
        coordinator.evaluate(bar=next_bar,evaluated_at=next_bar.available_at,accounting=book)


def test_target_only_fill_is_also_reconciliation_gated():
    args,_,target=fixture();c=PaperOCOCoordinatorV1(**args)
    candle=observed(open=Decimal(100),low=Decimal(100),high=Decimal(102),close=Decimal(101))
    result=c.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])
    assert [f.order_id for f in result.evaluation.fills]==[target.order_id]
    assert c.state=="AWAITING_ACCOUNTING"


def test_no_touch_contiguous_progress_and_replay_latches():
    args,_,_=fixture();c=PaperOCOCoordinatorV1(**args)
    candle=observed(open=Decimal(100),high=Decimal(100),low=Decimal(100),close=Decimal(100))
    first=c.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])
    assert not first.evaluation.fills and c.state=="ARMED"
    with pytest.raises(PaperOCOError,match="replay"):
        c.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])
    assert c.state=="HALTED"


def test_missing_accounted_fill_does_not_acknowledge():
    args,_,_=fixture();c=PaperOCOCoordinatorV1(**args);candle=observed()
    c.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])
    with pytest.raises(PaperOCOError,match="do not reconcile"):
        c.acknowledge_accounting(args["accounting"])
    assert c.state=="HALTED"


def test_foreign_parent_or_wrong_shared_quantity_reject():
    args,stop,target=fixture()
    for altered in (replace(target,parent_order_id=H("foreign")),replace(target,quantity=Decimal(4))):
        with pytest.raises(PaperOCOError):
            PaperOCOCoordinatorV1(**{**args,"ledger":ledger_for(stop,altered)})


def test_forming_bar_error_latches_without_returning_fill():
    args,_,_=fixture();c=PaperOCOCoordinatorV1(**args);candle=observed(finalized=False)
    with pytest.raises(ValueError):
        c.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])
    assert c.state=="HALTED" and c.pending is None


def test_same_inputs_produce_same_execution_result():
    args,_,_=fixture();candle=observed()
    results=[PaperOCOCoordinatorV1(**args).evaluate(bar=candle,evaluated_at=candle.available_at,
                accounting=args["accounting"]) for _ in range(2)]
    assert results[0]==results[1]


def test_first_bar_gap_and_non_aligned_arming_reject():
    args,_,_=fixture()
    with pytest.raises(PaperOCOError):
        PaperOCOCoordinatorV1(**{**args,"armed_at":args["armed_at"]+timedelta(seconds=1)})
    c=PaperOCOCoordinatorV1(**args)
    candle=observed(open_time=START+timedelta(minutes=4),close_time=START+timedelta(minutes=5),
        available_at=START+timedelta(minutes=5))
    with pytest.raises(PaperOCOError,match="gap"):
        c.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])


def test_zero_volume_has_no_fabricated_fill_and_can_process_next_bar():
    args,_,_=fixture();c=PaperOCOCoordinatorV1(**args)
    candle=observed(volume=Decimal(0))
    result=c.evaluate(bar=candle,evaluated_at=candle.available_at,accounting=args["accounting"])
    assert result.evaluation.fills==() and c.state=="ARMED"
    later=observed(open_time=candle.close_time,close_time=candle.close_time+timedelta(minutes=1),
        available_at=candle.close_time+timedelta(minutes=1))
    assert c.evaluate(bar=later,evaluated_at=later.available_at,accounting=args["accounting"]).evaluation.fills
