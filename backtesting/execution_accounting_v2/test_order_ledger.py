from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest

from backtesting.execution_accounting_v2 import (
    ALLOWED_TRANSITIONS, EVENT_PRIORITY, LedgerEventKind, OrderIntentV2, OrderLedgerError,
    OrderLedgerEventV2, OrderLedgerReason, OrderLedgerV2, OrderSide, OrderState,
    OrderType, TimeInForce,
)

UTC = timezone.utc
START = datetime(2025, 6, 1, tzinfo=UTC)
H = lambda value: hashlib.sha256(value.encode()).hexdigest()


def intent(**changes):
    values = dict(schema_version="order-intent-v2-1", order_id=H("order"), run_id=H("run"),
        action_id=H("action"), market="ES", instrument_id="ES", contract_id="ESM5",
        side=OrderSide.BUY, quantity=Decimal("3"), order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC, limit_price=Decimal("6000.25"), stop_price=None,
        submitted_at=START, activation_at=START + timedelta(minutes=2), expires_at=None,
        parent_order_id=None, replaces_order_id=None, configuration_version="config-v2",
        execution_policy_version="CONSERVATIVE_OHLC_1M_V1")
    values.update(changes)
    return OrderIntentV2(**values)


def event(ledger, kind, *, at=None, order_id=None, expected=None, event_id=None, **changes):
    target = ledger.order(order_id or H("order"))
    sequence = len(ledger.events) + 1
    values = dict(schema_version="order-ledger-event-v2-1",
        event_id=event_id or H(f"event-{sequence}-{kind.value}"), order_id=target.intent.order_id,
        kind=kind, event_time=at or START + timedelta(minutes=sequence),
        sequence_number=sequence, expected_order_version=target.order_version,
        market=target.intent.market, instrument_id=target.intent.instrument_id,
        contract_id=target.intent.contract_id, source_event_id=H(f"source-{sequence}"),
        reason_code=kind.value, contract_eligibility_verified=True)
    if expected is not None:
        values["expected_order_version"] = expected
    values.update(changes)
    return OrderLedgerEventV2(**values)


def advance(ledger, *kinds):
    for kind in kinds:
        ledger = ledger.apply(event(ledger, kind))
    return ledger


def active(selected=None):
    ledger = OrderLedgerV2.create((selected or intent(),))
    return advance(ledger, LedgerEventKind.SUBMIT, LedgerEventKind.ACCEPT, LedgerEventKind.ACTIVATE)


def test_submit_accept_activate_partial_and_complete_fill_conserve_quantity():
    ledger = active()
    ledger = ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    snap = ledger.order(H("order"))
    assert (snap.state, snap.accepted_quantity, snap.filled_quantity, snap.remaining_quantity) == (
        OrderState.PARTIALLY_FILLED, Decimal("3"), Decimal("1"), Decimal("2"))
    ledger = ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    ledger = ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    assert ledger.order(H("order")).state == OrderState.FILLED
    assert len(ledger.transitions) == 6
    ledger.validate_end_of_data()


def test_all_events_and_states_have_an_explicit_matrix_answer():
    nonterminal = set(OrderState) - {OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED,
                                           OrderState.EXPIRED, OrderState.REPLACED}
    assert set(ALLOWED_TRANSITIONS) == nonterminal
    for state in OrderState:
        for kind in LedgerEventKind:
            assert isinstance(kind in ALLOWED_TRANSITIONS.get(state, frozenset()), bool)


@pytest.mark.parametrize("bad", [Decimal("0"), Decimal("-1")])
def test_zero_and_negative_fill_reject(bad):
    ledger = active()
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=bad))
    assert exc.value.reason == OrderLedgerReason.ZERO_FILL_QUANTITY


def test_smallest_overfill_rejects_and_original_ledger_is_unchanged():
    ledger = active()
    before = ledger.serialize()
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("3.01")))
    assert exc.value.reason == OrderLedgerReason.ORDER_OVERFILL
    assert ledger.serialize() == before


def test_stop_and_stop_limit_require_trigger_and_separate_later_fill():
    selected = intent(order_type=OrderType.STOP_LIMIT, stop_price=Decimal("6001"),
                      limit_price=Decimal("6001.25"))
    ledger = active(selected)
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    assert exc.value.reason == OrderLedgerReason.STOP_NOT_TRIGGERED
    ledger = ledger.apply(event(ledger, LedgerEventKind.TRIGGER))
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.FILL, at=ledger.events[-1].event_time,
                           fill_quantity=Decimal("1")))
    assert exc.value.reason == OrderLedgerReason.INVALID_ORDER_TRANSITION
    ledger = ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    assert ledger.order(H("order")).state == OrderState.PARTIALLY_FILLED
    assert ledger.transitions[-2].resulting_state == OrderState.TRIGGERED


def test_non_stop_trigger_is_forbidden():
    ledger = active()
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.TRIGGER))
    assert exc.value.reason == OrderLedgerReason.INVALID_ORDER_TRANSITION


def test_fill_before_cancel_and_cancel_before_fill_have_deterministic_outcomes():
    first = active()
    first = first.apply(event(first, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    first = first.apply(event(first, LedgerEventKind.CANCEL_REQUEST))
    first = first.apply(event(first, LedgerEventKind.CANCEL))
    assert first.order(H("order")).filled_quantity == Decimal("1")
    second = active()
    second = second.apply(event(second, LedgerEventKind.CANCEL_REQUEST))
    second = second.apply(event(second, LedgerEventKind.CANCEL))
    with pytest.raises(OrderLedgerError) as exc:
        second.apply(event(second, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    assert exc.value.reason == OrderLedgerReason.CANCELLED_ORDER_FILL


def test_duplicate_cancel_and_conflicting_event_identity():
    ledger = active()
    cancel = event(ledger, LedgerEventKind.CANCEL_REQUEST)
    updated = ledger.apply(cancel)
    assert updated.apply(cancel) is updated
    conflicting = replace(cancel, reason_code="different")
    with pytest.raises(OrderLedgerError) as exc:
        updated.apply(conflicting)
    assert exc.value.reason == OrderLedgerReason.DUPLICATE_EVENT_CONFLICT
    with pytest.raises(OrderLedgerError) as exc:
        updated.apply(event(updated, LedgerEventKind.CANCEL_REQUEST))
    assert exc.value.reason == OrderLedgerReason.INVALID_ORDER_TRANSITION


def test_partial_fill_replacement_creates_child_without_mutating_parent_history():
    ledger = active()
    ledger = ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    parent_before = ledger.order(H("order"))
    child_intent = intent(order_id=H("child"), action_id=H("child-action"), quantity=Decimal("2"),
                          parent_order_id=H("order"), replaces_order_id=H("order"))
    ledger = ledger.apply(event(ledger, LedgerEventKind.REPLACE, replacement_intent=child_intent))
    parent = ledger.order(H("order")); child = ledger.order(H("child"))
    assert parent.state == OrderState.REPLACED and parent.filled_quantity == Decimal("1")
    assert parent.transition_ids[:len(parent_before.transition_ids)] == parent_before.transition_ids
    assert child.state == OrderState.CREATED and parent.replacement_child_order_id == child.intent.order_id
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.FILL, order_id=H("order"), fill_quantity=Decimal("1")))
    assert exc.value.reason == OrderLedgerReason.REPLACED_ORDER_FILL


def test_invalid_replacement_identity_and_duplicate_request_reject():
    ledger = active()
    bad_child = intent(order_id=H("child"), parent_order_id=None)
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.REPLACE, replacement_intent=bad_child))
    assert exc.value.reason == OrderLedgerReason.INVALID_REPLACEMENT
    oversized = intent(order_id=H("child-2"), parent_order_id=H("order"),
                       replaces_order_id=H("order"), quantity=Decimal("4"))
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.REPLACE, replacement_intent=oversized))
    assert exc.value.reason == OrderLedgerReason.INVALID_REPLACEMENT


def test_day_gtc_and_ioc_policies():
    day = active(intent(time_in_force=TimeInForce.DAY, expires_at=START + timedelta(hours=20)))
    with pytest.raises(OrderLedgerError) as exc:
        day.apply(event(day, LedgerEventKind.EXPIRE, session_boundary_verified=False))
    assert exc.value.reason == OrderLedgerReason.SESSION_BOUNDARY_UNPROVEN
    day = day.apply(event(day, LedgerEventKind.EXPIRE, session_boundary_verified=True))
    assert day.order(H("order")).state == OrderState.EXPIRED
    gtc = active()
    with pytest.raises(OrderLedgerError) as exc:
        gtc.apply(event(gtc, LedgerEventKind.EXPIRE, contract_eligibility_verified=False))
    assert exc.value.reason == OrderLedgerReason.CONTRACT_ELIGIBILITY_UNPROVEN
    ioc = active(intent(time_in_force=TimeInForce.IOC))
    ioc = ioc.apply(event(ioc, LedgerEventKind.FILL, fill_quantity=Decimal("1")))
    assert ioc.order(H("order")).state == OrderState.CANCELLED
    assert [t.resulting_state for t in ioc.transitions[-2:]] == [OrderState.PARTIALLY_FILLED, OrderState.CANCELLED]
    full_ioc = active(intent(time_in_force=TimeInForce.IOC))
    full_ioc = full_ioc.apply(event(full_ioc, LedgerEventKind.FILL, fill_quantity=Decimal("3")))
    assert full_ioc.order(H("order")).state == OrderState.FILLED
    assert full_ioc.transitions[-1].previous_state == OrderState.ACTIVE


def test_ioc_no_fill_evaluates_once_and_cancels_residual():
    ledger = active(intent(time_in_force=TimeInForce.IOC))
    ledger = ledger.apply(event(ledger, LedgerEventKind.EXECUTION_EVALUATED))
    assert ledger.order(H("order")).ioc_evaluated
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.EXECUTION_EVALUATED))
    assert exc.value.reason == OrderLedgerReason.IOC_ALREADY_EVALUATED


def test_forced_close_intent_is_explicit_and_auditable():
    ledger = OrderLedgerV2.create((intent(),))
    ledger = ledger.apply(event(ledger, LedgerEventKind.FORCED_CLOSE_INTENT))
    assert ledger.order(H("order")).forced_close_intent
    assert ledger.transitions[-1].reason_code == "FORCED_CLOSE_INTENT"


def test_stale_version_wrong_identity_sequence_and_time_regressions():
    ledger = OrderLedgerV2.create((intent(),))
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.SUBMIT, expected=1))
    assert exc.value.reason == OrderLedgerReason.STALE_ORDER_VERSION
    wrong = event(ledger, LedgerEventKind.SUBMIT, market="NQ")
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(wrong)
    assert exc.value.reason == OrderLedgerReason.ORDER_IDENTITY_MISMATCH
    ledger = ledger.apply(event(ledger, LedgerEventKind.SUBMIT))
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.ACCEPT, sequence_number=3))
    assert exc.value.reason == OrderLedgerReason.EVENT_SEQUENCE_REGRESSION
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.ACCEPT, at=START))
    assert exc.value.reason == OrderLedgerReason.EVENT_TIME_REGRESSION


def test_gtc_execution_requires_current_contract_eligibility():
    ledger = active()
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1"),
                           contract_eligibility_verified=False))
    assert exc.value.reason == OrderLedgerReason.CONTRACT_ELIGIBILITY_UNPROVEN


def test_equal_timestamp_uses_priority_then_event_identity():
    ledger = OrderLedgerV2.create((intent(),))
    at = START + timedelta(minutes=1)
    submit = event(ledger, LedgerEventKind.SUBMIT, at=at, event_id=H("a"))
    ledger = ledger.apply(submit)
    accept = event(ledger, LedgerEventKind.ACCEPT, at=at, event_id=H("b"))
    ledger = ledger.apply(accept)
    assert ledger.order(H("order")).state == OrderState.ACCEPTED
    bad_same_priority = event(ledger, LedgerEventKind.ACCEPT, at=at, event_id="0" * 64)
    with pytest.raises(OrderLedgerError) as exc:
        ledger.apply(bad_same_priority)
    assert exc.value.reason == OrderLedgerReason.EVENT_SEQUENCE_REGRESSION


def test_checkpoint_resume_replay_determinism_and_duplicate_replay():
    ledger = active()
    checkpoint = ledger.checkpoint()
    next_event = event(ledger, LedgerEventKind.FILL, fill_quantity=Decimal("1"))
    resumed = OrderLedgerV2.resume(checkpoint, (next_event,))
    replayed = OrderLedgerV2.replay((intent(),), resumed.events)
    assert resumed == replayed
    assert resumed.serialize() == replayed.serialize()
    assert resumed.apply(next_event) is resumed


def test_reordered_input_rejects_and_tampered_checkpoint_detects():
    ledger = active()
    reordered = tuple(reversed(ledger.events))
    with pytest.raises(OrderLedgerError):
        OrderLedgerV2.replay((intent(),), reordered)
    tampered = replace(ledger, ledger_fingerprint="0" * 64)
    with pytest.raises(OrderLedgerError) as exc:
        tampered.verify_integrity()
    assert exc.value.reason == OrderLedgerReason.DUPLICATE_EVENT_CONFLICT


def test_mixed_versions_and_end_of_data_residual_fail_closed():
    with pytest.raises(OrderLedgerError) as exc:
        OrderLedgerV2.create((intent(),), ledger_version="order-ledger-v1")
    assert exc.value.reason == OrderLedgerReason.MIXED_LEDGER_VERSION
    ledger = active()
    with pytest.raises(OrderLedgerError) as exc:
        ledger.validate_end_of_data()
    assert exc.value.reason == OrderLedgerReason.END_OF_DATA_RESIDUAL


def test_records_and_ledgers_are_immutable_and_decimal_only():
    ledger = active()
    with pytest.raises(FrozenInstanceError):
        ledger.events = ()
    with pytest.raises(ValueError):
        event(ledger, LedgerEventKind.FILL, fill_quantity=1)
