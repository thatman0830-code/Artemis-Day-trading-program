from dataclasses import replace
from datetime import timedelta

import pytest

from execution.paper_oco_evidence_v1 import DurablePaperOCOReplayV1
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.test_paper_oco_evidence_v1 import setup
from execution.test_paper_oco_execution_v1 import account
from backtesting.execution_accounting_v2.test_order_ledger import event, H
from backtesting.execution_accounting_v2.order_ledger import LedgerEventKind
from backtesting.execution_accounting_v2.contracts import OrderState


def prepared(tmp_path, volume="100"):
    initial, runner, doc, payload = setup(tmp_path, volume)
    doc = runner.advance(kind="EVALUATE", payload=payload, expected_checkpoint_id=doc["checkpoint_id"])
    _, coordinator = runner.load()
    book = account(initial["accounting"], coordinator.pending)
    doc = runner.advance(kind="ACK", payload={"accounting": book}, expected_checkpoint_id=doc["checkpoint_id"])
    _, coordinator = runner.load()
    ledger = coordinator.ledger
    cancellations = []
    at = book.snapshot.as_of
    for order in ledger.orders:
        if order.state is OrderState.FILLED:
            continue
        for kind in (LedgerEventKind.CANCEL_REQUEST, LedgerEventKind.CANCEL):
            at += timedelta(seconds=1)
            value = event(ledger, kind, order_id=order.intent.order_id, at=at,
                source_event_id=coordinator.pending.result_id)
            ledger = ledger.apply(value)
            cancellations.append(value)
    return initial, runner, doc, dict(accounting=book, cancellations=tuple(cancellations))


@pytest.mark.parametrize("volume,state,count", [("100", "CLOSED_FLAT", 1),
    ("10", "CANCELLED_REQUIRES_REARM", 2)])
def test_cancellation_replays_from_disk_and_never_rearms(tmp_path, volume, state, count):
    initial, runner, doc, payload = prepared(tmp_path, volume)
    doc = runner.advance(kind="CANCEL_ACK", payload=payload, expected_checkpoint_id=doc["checkpoint_id"])
    del runner, payload
    loaded, coordinator = DurablePaperOCOReplayV1(tmp_path, initial=initial).load()
    assert loaded == doc and coordinator.state == state
    assert sum(o.state is OrderState.CANCELLED for o in coordinator.ledger.orders) == count
    assert coordinator.quantity == 3  # original generation, not a new active position
    with pytest.raises(PaperOCOError, match="blocked"):
        coordinator.evaluate(bar=None, evaluated_at=None, accounting=initial["accounting"])


@pytest.mark.parametrize("damage", ["request_only", "one_order_only", "wrong_binding", "stale_version", "duplicate", "same_time"])
def test_bad_cancellation_cannot_clear_old_protection(tmp_path, damage):
    _, runner, doc, payload = prepared(tmp_path, "10")
    events = payload["cancellations"]
    if damage == "request_only":
        events = events[:1]
    elif damage == "one_order_only":
        events = events[:2]
    elif damage == "wrong_binding":
        events = (replace(events[0], source_event_id=H("foreign")), *events[1:])
    elif damage == "stale_version":
        events = (replace(events[0], expected_order_version=0), *events[1:])
    elif damage == "duplicate":
        events = (events[0], events[0])
    else:
        events = (replace(events[0], event_time=payload["accounting"].snapshot.as_of), *events[1:])
    with pytest.raises(ValueError):
        runner.advance(kind="CANCEL_ACK", payload={**payload, "cancellations": events},
            expected_checkpoint_id=doc["checkpoint_id"])
    with pytest.raises(PaperOCOError, match="blocked"):
        runner.load()


def test_changed_accounting_does_not_release_generation(tmp_path):
    initial, runner, doc, payload = prepared(tmp_path)
    with pytest.raises(PaperOCOError, match="changed"):
        runner.advance(kind="CANCEL_ACK", payload={**payload, "accounting": initial["accounting"]},
            expected_checkpoint_id=doc["checkpoint_id"])
    with pytest.raises(PaperOCOError, match="blocked"):
        runner.load()


def test_non_cancellation_event_rejects_before_journal_write(tmp_path):
    _, runner, doc, payload = prepared(tmp_path)
    invalid = replace(payload["cancellations"][0], kind=LedgerEventKind.EXPIRE)
    with pytest.raises(PaperOCOError):
        runner.advance(kind="CANCEL_ACK", payload={**payload, "cancellations": (invalid,)},
            expected_checkpoint_id=doc["checkpoint_id"])
    assert runner.load()[0] == doc
