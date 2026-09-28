from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from backtesting.execution_accounting_v2.contracts import OrderSide,OrderType,TimeInForce
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1,PaperAdapterPairReceiptV1
from execution.paper_gateway_v2 import PaperContingentPairV1,PaperSubmissionV1
from execution.supervised_paper_performance_v1 import VerifiedPaperFillV1
from execution.supervised_paper_workflow_v1 import SupervisedPaperCycleV1
from execution.test_bounded_paper_session_v1 import driver,submit
from execution.test_paper_performance_ledger_v1 import T,H,gateway_fill
from execution.paper_gateway_v2 import PaperEventKind,PaperOrderEventV1


def open_position(item):
    item.start(T);command=submit(item);adapter,receipt,_,_=item.step(SupervisedPaperCycleV1(T,T,command))
    _,_,source,costs=gateway_fill();fill=replace(source,order_id=command.submission.intent.order_id,
        quantity=Decimal("0.001"))
    event=PaperOrderEventV1(H("entry-fill"),receipt.paper_order_id,PaperEventKind.FILL,
        fill.fill_time,0,fill.quantity,False)
    fill_command=PaperAdapterCommandV1(H("entry-fill-command"),adapter.gateway.snapshot_id,event=event)
    item.step(SupervisedPaperCycleV1(fill.fill_time,fill.fill_time,fill_command),
        verified_fill=VerifiedPaperFillV1(event,fill,costs))
    return command.submission.intent,fill.fill_time


def protective_pair(parent,now):
    common=dict(side=OrderSide.SELL,quantity=Decimal("0.001"),time_in_force=TimeInForce.GTC,
        submitted_at=now,activation_at=now,parent_order_id=parent.order_id,replaces_order_id=None)
    stop=replace(parent,**common,order_id=H("bounded-stop"),action_id=H("bounded-stop-action"),
        order_type=OrderType.STOP_MARKET,limit_price=None,stop_price=Decimal(49000))
    target=replace(parent,**common,order_id=H("bounded-target"),action_id=H("bounded-target-action"),
        order_type=OrderType.LIMIT,limit_price=Decimal(51000),stop_price=None)
    authorization=H("bounded-pair-authorization")
    return PaperContingentPairV1.create(
        PaperSubmissionV1(H("bounded-stop-key"),stop,Decimal(50000),now,now,authorization,True),
        PaperSubmissionV1(H("bounded-target-key"),target,Decimal(50000),now,now,authorization,True))


def test_bounded_session_admits_protective_pair_without_increasing_gross_exposure(tmp_path):
    item=driver(tmp_path);parent,fill_time=open_position(item);now=fill_time+timedelta(seconds=1)
    pair=protective_pair(parent,now)
    command=PaperAdapterCommandV1(H("bounded-pair-command"),
        item.workflow.store.load().gateway.snapshot_id,contingent_pair=pair)
    adapter,receipt,health,ledger=item.step(SupervisedPaperCycleV1(now,now,command))
    assert type(receipt) is PaperAdapterPairReceiptV1 and receipt.accepted
    assert len(adapter.gateway.records)==3 and item.reserved==Decimal("50")
    assert item.contingent_pairs=={pair.adverse.intent.order_id:pair.pair_id,
        pair.favorable.intent.order_id:pair.pair_id}
    assert health.state.value=="HEALTHY" and ledger.snapshot.position.signed_quantity==Decimal("0.001")
    item.stop(now+timedelta(seconds=1))
