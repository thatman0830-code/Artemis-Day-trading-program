from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from execution.paper_oco_replacement_v1 import review_protective_replacement
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.test_paper_oco_cancellation_v1 import prepared
from execution.test_paper_oco_execution_v1 import observed, H


def proposal(tmp_path):
    _, runner, doc, payload = prepared(tmp_path, "10")
    doc = runner.advance(kind="CANCEL_ACK", payload=payload, expected_checkpoint_id=doc["checkpoint_id"])
    _, old = runner.load()
    opening = max(e.event_time for e in old.ledger.events).replace(second=0) + timedelta(minutes=1)
    now = opening + timedelta(minutes=1)
    source = observed(open_time=opening, close_time=now, available_at=now,
        open=Decimal(100), high=Decimal(100), low=Decimal(100), close=Decimal(100))
    def candidate(identity, name):
        original = old.ledger.order(identity).intent
        return replace(original, order_id=H(name), action_id=H(name+"-action"),
            replaces_order_id=identity, quantity=Decimal(2), submitted_at=now, activation_at=now)
    return dict(predecessor=runner, expected_checkpoint_id=doc["checkpoint_id"],
        accounting=payload["accounting"], stop=candidate(old.group.adverse_order_id, "new-stop"),
        target=candidate(old.group.favorable_order_id, "new-target"), source_bar=source, reviewed_at=now)


def test_quantity_only_review_is_deterministic_read_only_and_not_permission(tmp_path):
    args = proposal(tmp_path)
    before = args["predecessor"].load()[0]
    one = review_protective_replacement(**args)
    assert one == review_protective_replacement(**args)
    assert one.quantity == 2 and one.requires_gap_review
    assert not one.rearm_authorized and not one.trading_authority
    assert args["predecessor"].load()[0] == before
    with pytest.raises(PaperOCOError):
        replace(one, rearm_authorized=True)


@pytest.mark.parametrize("change", ["quantity", "stop", "target", "policy", "reuse", "parent", "offgrid", "activation", "mapping"])
def test_unsafe_replacement_rejects(tmp_path, change):
    args = proposal(tmp_path)
    candidate = args["stop"]
    changes = {
        "quantity": dict(quantity=Decimal(3)), "stop": dict(stop_price=Decimal(98)),
        "target": dict(limit_price=Decimal(102)), "policy": dict(configuration_version="changed"),
        "reuse": dict(order_id=args["target"].replaces_order_id), "parent": dict(parent_order_id=H("foreign")),
        "offgrid": dict(stop_price=Decimal("99.001")),
        "activation": dict(activation_at=args["reviewed_at"]+timedelta(seconds=1)),
        "mapping": dict(replaces_order_id=H("unrelated"))}
    key = "target" if change == "target" else "stop"
    args[key] = replace(args[key], **changes[change])
    with pytest.raises(ValueError):
        review_protective_replacement(**args)


@pytest.mark.parametrize("change", ["stale", "future", "forming", "pre_cancel", "outside"])
def test_unusable_source_rejects(tmp_path, change):
    args = proposal(tmp_path)
    bar = args["source_bar"]
    if change == "stale":
        args["reviewed_at"] += timedelta(minutes=2)
    elif change == "future":
        args["source_bar"] = replace(bar, available_at=bar.available_at+timedelta(seconds=1))
    elif change == "forming":
        args["source_bar"] = replace(bar, finalized=False)
    elif change == "pre_cancel":
        args["source_bar"] = replace(bar, open_time=bar.open_time-timedelta(minutes=2),
            close_time=bar.close_time-timedelta(minutes=2))
    else:
        args["source_bar"] = replace(bar, close=Decimal(102), high=Decimal(102))
    with pytest.raises(ValueError):
        review_protective_replacement(**args)


def test_stale_checkpoint_and_uncancelled_predecessor_reject(tmp_path):
    args = proposal(tmp_path)
    with pytest.raises(PaperOCOError, match="stale"):
        review_protective_replacement(**{**args, "expected_checkpoint_id": "0" * 64})
    other = tmp_path / "uncancelled"
    other.mkdir()
    _, runner, doc, _ = prepared(other, "10")
    with pytest.raises(PaperOCOError, match="cancellation"):
        review_protective_replacement(**{**args, "predecessor": runner, "expected_checkpoint_id": doc["checkpoint_id"]})
