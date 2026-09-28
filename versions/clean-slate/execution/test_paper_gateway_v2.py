from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import pytest

from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderSide, OrderType, TimeInForce
from execution.paper_gateway_v2 import *

NOW=datetime(2026,8,31,20,tzinfo=timezone.utc)
sha=lambda value: hashlib.sha256(value.encode()).hexdigest()

def intent(name="a", quantity="1"):
    return OrderIntentV2("order-intent-v2-1",sha("order-"+name),sha("run"),sha("action-"+name),
        "BTC","BTC-PERP",None,OrderSide.BUY,Decimal(quantity),OrderType.MARKET,TimeInForce.IOC,
        None,None,NOW,NOW,None,None,None,"config-v1","policy-v1")

def request(name="a", **changes):
    base=PaperSubmissionV1(sha("key-"+name),intent(name),Decimal("100"),NOW,NOW,sha("auth-"+name),True)
    return replace(base,**changes)

def gateway(**changes):
    policy=PaperGatewayPolicyV1(Decimal("500"),Decimal("800"),2,timedelta(seconds=5))
    return replace(PaperGatewaySnapshotV1.create(policy),**changes)

def test_accepts_paper_request_and_never_grants_trading_authority():
    state,result=gateway().submit(request())
    assert result.accepted and result.reason is PaperGatewayReason.ACCEPTED
    assert not result.trading_authority and not state.trading_authority

def test_exact_retry_is_idempotent_without_second_order():
    state,first=gateway().submit(request()); replay,second=state.submit(request())
    assert replay is state and second.reason is PaperGatewayReason.IDEMPOTENT_REPLAY
    assert second.record==first.record and len(state.records)==1

def test_conflicting_idempotency_key_and_duplicate_order_reject():
    state,_=gateway().submit(request())
    _,conflict=state.submit(replace(request(),reference_price=Decimal("101")))
    _,duplicate=state.submit(replace(request("b"),intent=request().intent))
    assert conflict.reason is duplicate.reason is PaperGatewayReason.DUPLICATE_CONFLICT

@pytest.mark.parametrize("change,reason",[
    ({"connected":False},PaperGatewayReason.DISCONNECTED),
    ({"kill_switch_active":True},PaperGatewayReason.KILL_SWITCH_ACTIVE),
    ({"reconciliation_required":True},PaperGatewayReason.RECONCILIATION_REQUIRED)])
def test_gateway_state_gates_fail_closed(change,reason):
    _,result=gateway(**change).submit(request())
    assert not result.accepted and result.reason is reason

def test_authorization_and_stale_data_reject():
    _,unauthorized=gateway().submit(request(authorized=False))
    _,stale=gateway().submit(request(market_data_at=NOW-timedelta(seconds=6)))
    _,future=gateway().submit(request(market_data_at=NOW+timedelta(microseconds=1)))
    assert unauthorized.reason is PaperGatewayReason.AUTHORIZATION_REJECTED
    assert stale.reason is PaperGatewayReason.STALE_MARKET_DATA
    assert future.reason is PaperGatewayReason.FUTURE_MARKET_DATA

def test_order_and_total_exposure_limits_and_open_order_limit():
    _,large=gateway().submit(request(intent=intent("a","6")))
    state,_=gateway().submit(request("a",intent=intent("a","4")))
    _,total=state.submit(request("b",intent=intent("b","5")))
    state,_=gateway().submit(request("a"));state,_=state.submit(request("b"))
    _,count=state.submit(request("c"))
    assert large.reason is total.reason is PaperGatewayReason.EXPOSURE_LIMIT
    assert count.reason is PaperGatewayReason.OPEN_ORDER_LIMIT

def test_disconnect_requires_exact_reconciliation_before_recovery():
    state,_=gateway().submit(request()); disconnected=state.disconnect()
    mismatch=disconnected.reconcile(())
    assert mismatch.kill_switch_active and mismatch.reconciliation_required and not mismatch.connected
    observed=((state.records[0].paper_order_id,PaperOrderState.ACCEPTED,Decimal(0),Decimal(1),0),)
    recovered=disconnected.reconcile(observed)
    assert recovered.connected and not recovered.reconciliation_required

def test_snapshot_resume_detects_tampering():
    state,_=gateway().submit(request())
    assert PaperGatewaySnapshotV1.resume(state) is state
    with pytest.raises(ValueError,match="integrity"):
        PaperGatewaySnapshotV1.resume(replace(state,snapshot_id=sha("tampered")))

def test_paper_submission_rejects_trading_authority():
    with pytest.raises(ValueError,match="trading authority"):
        request(trading_authority=True)

def event(record,name,kind=PaperEventKind.FILL,quantity="0.4",version=0,when=NOW+timedelta(seconds=1)):
    return PaperOrderEventV1(sha("event-"+name),record.paper_order_id,kind,when,version,
        Decimal(quantity) if kind is PaperEventKind.FILL else None)

def test_partial_and_final_fill_conserve_quantity():
    state,_=gateway().submit(request());record=state.records[0]
    state,partial=state.apply_event(event(record,"one"))
    assert partial.record.state is PaperOrderState.PARTIALLY_FILLED
    assert partial.record.filled_quantity+partial.record.remaining_quantity==partial.record.quantity
    state,final=state.apply_event(event(record,"two",quantity="0.6",version=1,when=NOW+timedelta(seconds=2)))
    assert final.record.state is PaperOrderState.FILLED and final.record.remaining_quantity==0

def test_exact_event_replay_is_idempotent_and_conflict_rejects():
    state,_=gateway().submit(request());record=state.records[0];value=event(record,"one")
    applied,_=state.apply_event(value);replayed,result=applied.apply_event(value)
    assert replayed is applied and result.reason is PaperGatewayReason.EVENT_REPLAY
    conflict=replace(value,fill_quantity=Decimal("0.5"))
    _,result=applied.apply_event(conflict)
    assert result.reason is PaperGatewayReason.EVENT_CONFLICT

def test_overfill_stale_version_and_time_regression_reject():
    state,_=gateway().submit(request());record=state.records[0]
    _,overfill=state.apply_event(event(record,"over",quantity="1.1"))
    _,stale=state.apply_event(event(record,"stale",version=1))
    _,regression=state.apply_event(event(record,"old",when=NOW-timedelta(seconds=1)))
    assert overfill.reason is PaperGatewayReason.INVALID_FILL_QUANTITY
    assert stale.reason is PaperGatewayReason.STALE_ORDER_VERSION
    assert regression.reason is PaperGatewayReason.EVENT_TIME_REGRESSION

def test_cancel_is_terminal_and_preserves_partial_fill():
    state,_=gateway().submit(request());record=state.records[0]
    state,_=state.apply_event(event(record,"fill"));record=state.records[0]
    state,cancel=state.apply_event(event(record,"cancel",kind=PaperEventKind.CANCEL,version=1,when=NOW+timedelta(seconds=2)))
    assert cancel.record.state is PaperOrderState.CANCELLED and cancel.record.filled_quantity==Decimal("0.4")
    _,late=state.apply_event(event(record,"late",version=2,when=NOW+timedelta(seconds=3)))
    assert late.reason is PaperGatewayReason.TERMINAL_ORDER

def test_reconciliation_checks_quantities_and_version():
    state,_=gateway().submit(request());disconnected=state.disconnect();record=state.records[0]
    bad=((record.paper_order_id,record.state,Decimal("0.1"),Decimal("0.9"),0),)
    assert disconnected.reconcile(bad).kill_switch_active

def test_record_rejects_quantity_and_version_tampering():
    state,_=gateway().submit(request());record=state.records[0]
    with pytest.raises(ValueError,match="conservation"):
        replace(record,remaining_quantity=Decimal("0.9"))
    with pytest.raises(ValueError,match="version/event"):
        replace(record,version=1)

def test_module_has_no_provider_network_credential_or_live_order_capability():
    source=__import__('pathlib').Path(__file__).with_name('paper_gateway_v2.py').read_text('utf-8').lower()
    for prohibited in ('requests','httpx','websocket','private_key','api_key','place_order','submit_live'):
        assert prohibited not in source
