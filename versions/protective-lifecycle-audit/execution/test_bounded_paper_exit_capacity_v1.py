from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from execution.test_bounded_paper_session_v1 import driver,submit
from execution.test_paper_performance_ledger_v1 import T,H,gateway_fill
from execution.supervised_paper_workflow_v1 import SupervisedPaperCycleV1
from execution.supervised_paper_performance_v1 import VerifiedPaperFillV1
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.paper_gateway_v2 import PaperOrderEventV1,PaperEventKind
from backtesting.execution_accounting_v2.contracts import OrderSide
from execution.bounded_paper_session_v1 import BoundedPaperSessionError


def sell(item,name="exit",quantity="0.002",second=2):
    now=T+timedelta(seconds=second)
    command=submit(item,name,quantity=quantity)
    intent=replace(command.submission.intent,side=OrderSide.SELL,submitted_at=now,activation_at=now)
    return replace(command,submission=replace(command.submission,intent=intent,requested_at=now,market_data_at=now))


def fill(item, order_id, *, quantity, second, side):
    adapter=item.workflow.store.load()
    record=next(r for r in adapter.gateway.records if r.order_id==order_id)
    _,_,source,costs=gateway_fill()
    value=replace(source,fill_id=H("exit-cap-fill"+str(second)),order_id=order_id,
        quantity=Decimal(quantity),side=side,fill_time=T+timedelta(seconds=second))
    costs=replace(costs,economics_id=H("exit-cap-cost"+str(second)),fill_id=value.fill_id)
    event=PaperOrderEventV1(H("exit-cap-event"+str(second)),record.paper_order_id,
        PaperEventKind.FILL,value.fill_time,record.version,value.quantity,False)
    command=PaperAdapterCommandV1(H("exit-cap-cmd"+str(second)),adapter.gateway.snapshot_id,event=event)
    return item.step(SupervisedPaperCycleV1(value.fill_time,value.fill_time,command),
        verified_fill=VerifiedPaperFillV1(event,value,costs))


def positioned(tmp_path,quantity="0.002"):
    item=driver(tmp_path);item.start(T)
    entry=submit(item,quantity=quantity)
    item.step(SupervisedPaperCycleV1(T,T,entry))
    fill(item,entry.submission.intent.order_id,quantity=quantity,second=1,side=OrderSide.BUY)
    return item


def test_flat_spot_sell_rejects_before_gateway_order_creation(tmp_path):
    item=driver(tmp_path);item.start(T)
    with pytest.raises(BoundedPaperSessionError,match="exit capacity"):
        item.step(SupervisedPaperCycleV1(T,T,sell(item,quantity="0.001",second=0)))
    assert item.workflow.store.load().gateway.records==()
    assert item.workflow.store.load().gateway.kill_switch_active


def test_unfilled_buy_does_not_provide_exit_capacity(tmp_path):
    item=driver(tmp_path);item.start(T)
    item.step(SupervisedPaperCycleV1(T,T,submit(item)))
    before=item.workflow.store.load().gateway.records
    with pytest.raises(BoundedPaperSessionError,match="exit capacity"):
        item.step(SupervisedPaperCycleV1(T,T,sell(item,quantity="0.001",second=0)))
    assert item.workflow.store.load().gateway.records==before


def test_two_independent_full_position_exits_cannot_double_reserve(tmp_path):
    item=positioned(tmp_path,quantity="0.001")
    exit_cmd=sell(item,quantity="0.001")
    now=T+timedelta(seconds=2)
    item.step(SupervisedPaperCycleV1(now,now,exit_cmd))
    before=item.workflow.store.load().gateway.records
    with pytest.raises(BoundedPaperSessionError,match="exit capacity"):
        item.step(SupervisedPaperCycleV1(now,now,sell(item,"second-exit",quantity="0.001")))
    assert item.workflow.store.load().gateway.records==before
    assert item.bridge.store.load().snapshot.position.signed_quantity==Decimal("0.001")


def test_partial_exit_fills_reduce_to_flat_with_exact_accounting(tmp_path):
    item=positioned(tmp_path);cmd=sell(item);now=T+timedelta(seconds=2)
    item.step(SupervisedPaperCycleV1(now,now,cmd))
    fill(item,cmd.submission.intent.order_id,quantity="0.001",second=3,side=OrderSide.SELL)
    assert item.bridge.store.load().snapshot.position.signed_quantity==Decimal("0.001")
    fill(item,cmd.submission.intent.order_id,quantity="0.001",second=4,side=OrderSide.SELL)
    assert item.bridge.store.load().snapshot.position.signed_quantity==0
    assert item.bridge.store.load().snapshot.total_costs==Decimal(9)
    assert item.stop(T+timedelta(seconds=4)).state=="STOPPED"


def test_oversized_exit_fill_blocks_before_adapter_fill_mutation(tmp_path):
    item=positioned(tmp_path);cmd=sell(item);now=T+timedelta(seconds=2)
    item.step(SupervisedPaperCycleV1(now,now,cmd))
    records=item.workflow.store.load().gateway.records
    checkpoint=item.bridge.store.path.read_bytes()
    with pytest.raises(BoundedPaperSessionError,match="exit fill exceeds"):
        fill(item,cmd.submission.intent.order_id,quantity="0.003",second=3,side=OrderSide.SELL)
    assert item.workflow.store.load().gateway.records==records
    assert item.bridge.store.path.read_bytes()==checkpoint


def test_partial_fill_reserves_only_remaining_exit_quantity(tmp_path):
    item=positioned(tmp_path);cmd=sell(item);now=T+timedelta(seconds=2)
    item.step(SupervisedPaperCycleV1(now,now,cmd))
    fill(item,cmd.submission.intent.order_id,quantity="0.001",second=3,side=OrderSide.SELL)
    assert item._spot_exit_capacity()==(Decimal("0.001"),Decimal("0.001"))
    now=T+timedelta(seconds=4)
    with pytest.raises(BoundedPaperSessionError,match="exit capacity"):
        item.step(SupervisedPaperCycleV1(now,now,sell(item,"duplicate",quantity="0.001",second=4)))


def test_confirmed_cancellation_releases_units_not_session_notional_budget(tmp_path):
    item=positioned(tmp_path,quantity="0.001")
    cmd=sell(item,quantity="0.001");now=T+timedelta(seconds=2)
    item.step(SupervisedPaperCycleV1(now,now,cmd))
    adapter=item.workflow.store.load();record=adapter.gateway.records[-1]
    now=T+timedelta(seconds=3)
    event=PaperOrderEventV1(H("confirmed-cancel"),record.paper_order_id,PaperEventKind.CANCEL,
        now,record.version,None,False)
    cancel=PaperAdapterCommandV1(H("cancel-command"),adapter.gateway.snapshot_id,event=event)
    item.step(SupervisedPaperCycleV1(now,now,cancel))
    assert item._spot_exit_capacity()==(Decimal("0.001"),Decimal(0))
    assert item.reserved==Decimal(100)
    now=T+timedelta(seconds=4)
    _,receipt,_,_=item.step(SupervisedPaperCycleV1(now,now,sell(item,"replacement",quantity="0.001",second=4)))
    assert receipt.accepted and item.reserved==Decimal(150)
    assert item.stop(now).state=="STOPPED"


def test_changed_checkpoint_cannot_supply_exit_capacity(tmp_path):
    item=positioned(tmp_path)
    item.workflow.store.halt()
    records=item.workflow.store.load().gateway.records
    now=T+timedelta(seconds=2)
    with pytest.raises(BoundedPaperSessionError,match="reconciled"):
        item.step(SupervisedPaperCycleV1(now,now,sell(item)))
    assert item.workflow.store.load().gateway.records==records
