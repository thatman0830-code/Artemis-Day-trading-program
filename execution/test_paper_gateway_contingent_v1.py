from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from backtesting.execution_accounting_v2.contracts import OrderSide, OrderType, TimeInForce
from execution.paper_gateway_v2 import (
    PaperContingentPairV1, PaperEventKind, PaperGatewayPolicyV1, PaperGatewayReason,
    PaperGatewaySnapshotV1, PaperOrderEventV1, PaperOrderState, PaperSubmissionV1,
)
from execution.test_paper_gateway_v2 import NOW, gateway, intent, request, sha


def pair(**changes):
    parent=sha("accounted-entry")
    stop=replace(intent("stop"),side=OrderSide.SELL,order_type=OrderType.STOP_MARKET,
        time_in_force=TimeInForce.GTC,limit_price=None,stop_price=Decimal(99),
        parent_order_id=parent)
    target=replace(intent("target"),side=OrderSide.SELL,order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC,limit_price=Decimal(101),stop_price=None,
        parent_order_id=parent)
    adverse=PaperSubmissionV1(sha("stop-key"),stop,Decimal(100),NOW,NOW,sha("pair-auth"),True)
    favorable=PaperSubmissionV1(sha("target-key"),target,Decimal(100),NOW,NOW,sha("pair-auth"),True)
    values=dict(adverse=adverse,favorable=favorable)
    values.update(changes)
    return PaperContingentPairV1.create(**values)


def constrained(total="150",orders=2):
    policy=PaperGatewayPolicyV1(Decimal(120),Decimal(total),orders,timedelta(seconds=5))
    return PaperGatewaySnapshotV1.create(policy)


def test_pair_is_admitted_atomically_with_shared_exposure():
    state,decisions=constrained().submit_contingent_pair(pair())
    assert len(state.records)==2 and all(item.accepted for item in decisions)
    assert all(item.reason is PaperGatewayReason.ACCEPTED for item in decisions)
    assert sum(item.notional for item in state.records)==Decimal(200)
    assert not state.trading_authority and not pair().trading_authority


def test_pair_exact_replay_and_conflict_never_add_records():
    state,first=constrained().submit_contingent_pair(pair())
    replay,decisions=state.submit_contingent_pair(pair())
    assert replay is state and all(x.reason is PaperGatewayReason.IDEMPOTENT_REPLAY for x in decisions)
    changed=PaperContingentPairV1.create(pair().adverse,
        replace(pair().favorable,reference_price=Decimal(100.5)))
    same,conflict=state.submit_contingent_pair(changed)
    assert same is state and len(same.records)==2
    assert all(x.reason is PaperGatewayReason.DUPLICATE_CONFLICT for x in conflict)


@pytest.mark.parametrize("damage",["unauthorized","geometry","parent","quantity","time","identity"])
def test_invalid_pair_rejects_both_without_half_admission(damage):
    value=pair(); adverse=value.adverse; favorable=value.favorable
    if damage=="unauthorized": adverse=replace(adverse,authorized=False)
    elif damage=="geometry": adverse=replace(adverse,intent=replace(adverse.intent,stop_price=Decimal(100)))
    elif damage=="parent": favorable=replace(favorable,intent=replace(favorable.intent,parent_order_id=sha("other")))
    elif damage=="quantity": favorable=replace(favorable,intent=replace(favorable.intent,quantity=Decimal(2)))
    elif damage=="time": favorable=replace(favorable,requested_at=NOW+timedelta(seconds=1))
    else: favorable=replace(favorable,intent=replace(favorable.intent,order_id=adverse.intent.order_id))
    state,decisions=constrained().submit_contingent_pair(PaperContingentPairV1.create(adverse,favorable))
    assert not state.records and not any(item.accepted for item in decisions)


def test_open_order_and_shared_exposure_limits_apply_to_whole_pair():
    state,count=constrained(orders=1).submit_contingent_pair(pair())
    assert not state.records and all(x.reason is PaperGatewayReason.OPEN_ORDER_LIMIT for x in count)
    large=PaperContingentPairV1.create(
        replace(pair().adverse,intent=replace(pair().adverse.intent,quantity=Decimal(2))),
        replace(pair().favorable,intent=replace(pair().favorable.intent,quantity=Decimal(2))))
    state,exposure=constrained().submit_contingent_pair(large)
    assert not state.records and all(x.reason is PaperGatewayReason.EXPOSURE_LIMIT for x in exposure)


def test_partial_order_remains_in_open_exposure_and_count():
    policy=PaperGatewayPolicyV1(Decimal(120),Decimal(150),2,timedelta(seconds=5))
    state,_=PaperGatewaySnapshotV1.create(policy).submit(request())
    record=state.records[0]
    event=PaperOrderEventV1(sha("partial"),record.paper_order_id,PaperEventKind.FILL,
        NOW+timedelta(seconds=1),0,Decimal("0.5"))
    state,_=state.apply_event(event)
    assert state.records[0].state is PaperOrderState.PARTIALLY_FILLED
    unchanged,decision=state.submit(request("second"))
    assert unchanged is state and decision.reason is PaperGatewayReason.EXPOSURE_LIMIT


def test_health_time_and_existing_half_pair_all_fail_closed():
    for state,expected in ((gateway(connected=False),PaperGatewayReason.DISCONNECTED),
            (gateway(kill_switch_active=True),PaperGatewayReason.KILL_SWITCH_ACTIVE),
            (gateway(reconciliation_required=True),PaperGatewayReason.RECONCILIATION_REQUIRED)):
        unchanged,decisions=state.submit_contingent_pair(pair())
        assert unchanged is state and all(x.reason is expected for x in decisions)
    one,_=constrained().submit(pair().adverse)
    unchanged,decisions=one.submit_contingent_pair(pair())
    assert unchanged is one and all(x.reason is PaperGatewayReason.DUPLICATE_CONFLICT for x in decisions)
