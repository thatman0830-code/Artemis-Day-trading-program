from datetime import timedelta
from decimal import Decimal

import pytest

from execution.paper_gateway_v2 import (
    PaperContingentResolutionV1,PaperEventKind,PaperGatewayReason,PaperOrderEventV1,
    PaperOrderState,
)
from execution.test_paper_gateway_contingent_v1 import constrained,pair
from execution.test_paper_gateway_v2 import NOW,sha


def admitted():
    item=pair();state,decisions=constrained().submit_contingent_pair(item)
    records=tuple(decision.record for decision in decisions)
    return item,state,records


def resolution(item,records,quantity="1",damage=None):
    winner,sibling=records
    fill=PaperOrderEventV1(sha("resolution-fill"),winner.paper_order_id,PaperEventKind.FILL,
        NOW+timedelta(seconds=1),0,Decimal(quantity))
    cancellations=[]
    if Decimal(quantity)<winner.quantity:
        cancellations.append(PaperOrderEventV1(sha("cancel-winner"),winner.paper_order_id,
            PaperEventKind.CANCEL,NOW+timedelta(seconds=2),1))
    cancellations.append(PaperOrderEventV1(sha("cancel-sibling"),sibling.paper_order_id,
        PaperEventKind.CANCEL,NOW+timedelta(seconds=2),0))
    if damage=="missing":cancellations=cancellations[:-1]
    elif damage=="stale":cancellations[-1]=PaperOrderEventV1(sha("cancel-sibling"),
        sibling.paper_order_id,PaperEventKind.CANCEL,NOW+timedelta(seconds=2),1)
    elif damage=="early":cancellations[-1]=PaperOrderEventV1(sha("cancel-sibling"),
        sibling.paper_order_id,PaperEventKind.CANCEL,NOW,0)
    elif damage=="foreign":cancellations[-1]=PaperOrderEventV1(sha("cancel-sibling"),
        sha("foreign"),PaperEventKind.CANCEL,NOW+timedelta(seconds=2),0)
    return PaperContingentResolutionV1.create(pair_id=item.pair_id,
        paper_order_ids=tuple(record.paper_order_id for record in records),fill=fill,
        cancellations=tuple(cancellations))


@pytest.mark.parametrize("quantity",["1","0.4"])
def test_fill_and_required_cancellations_apply_atomically(quantity):
    item,state,records=admitted();value=resolution(item,records,quantity)
    updated,decisions=state.resolve_contingent_pair(value)
    assert all(result.accepted for result in decisions)
    assert all(record.state in (PaperOrderState.FILLED,PaperOrderState.CANCELLED)
        for record in updated.records)
    winner=next(record for record in updated.records if record.paper_order_id==records[0].paper_order_id)
    if quantity=="0.4":
        assert winner.state is PaperOrderState.CANCELLED and winner.filled_quantity==Decimal("0.4")
        assert len(decisions)==3
    else:assert winner.state is PaperOrderState.FILLED and len(decisions)==2
    replayed,replay=updated.resolve_contingent_pair(value)
    assert replayed is updated and all(result.reason is PaperGatewayReason.EVENT_REPLAY for result in replay)


@pytest.mark.parametrize("damage",["missing","stale","early","foreign"])
def test_invalid_resolution_preserves_both_original_records(damage):
    item,state,records=admitted();value=resolution(item,records,"0.4",damage)
    unchanged,decisions=state.resolve_contingent_pair(value)
    assert unchanged is state and len(unchanged.records)==2
    assert all(record.state is PaperOrderState.ACCEPTED for record in unchanged.records)
    assert decisions[0].reason is PaperGatewayReason.EVENT_CONFLICT


def test_overfill_and_unhealthy_gateway_preserve_snapshot():
    item,state,records=admitted();value=resolution(item,records,"1.1")
    unchanged,_=state.resolve_contingent_pair(value);assert unchanged is state
    for unhealthy,reason in ((state.disconnect(),PaperGatewayReason.DISCONNECTED),
            (state.activate_kill_switch(),PaperGatewayReason.KILL_SWITCH_ACTIVE)):
        unchanged,decisions=unhealthy.resolve_contingent_pair(resolution(item,records))
        assert unchanged is unhealthy and decisions[0].reason is reason
