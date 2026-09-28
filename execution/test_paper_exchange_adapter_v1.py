from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import pytest

from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderSide, OrderType, TimeInForce
from execution.paper_exchange_adapter_v1 import *
from execution.paper_gateway_v2 import *

NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
sha = lambda value: hashlib.sha256(value.encode()).hexdigest()


def intent(name="a"):
    return OrderIntentV2("order-intent-v2-1", sha("order-"+name), sha("run"), sha("action-"+name),
        "BTC", "BTC-PERP", None, OrderSide.BUY, Decimal("1"), OrderType.MARKET,
        TimeInForce.IOC, None, None, NOW, NOW, None, None, None, "config-v1", "policy-v1")


def gateway():
    return PaperGatewaySnapshotV1.create(PaperGatewayPolicyV1(
        Decimal("500"), Decimal("800"), 2, timedelta(seconds=5)))


def submission(name="a", **changes):
    value = PaperSubmissionV1(sha("key-"+name), intent(name), Decimal("100"), NOW, NOW,
                              sha("auth-"+name), True)
    return replace(value, **changes)


def command(adapter, name="a", **changes):
    value = PaperAdapterCommandV1(sha("command-"+name), adapter.gateway.snapshot_id,
                                  submission=submission(name))
    return replace(value, **changes)


def test_submission_is_snapshot_bound_and_paper_only():
    adapter = PaperExchangeAdapterV1.create(gateway())
    updated, receipt = adapter.execute(command(adapter))
    assert receipt.accepted and receipt.reason is PaperAdapterReason.SUBMISSION_APPLIED
    assert len(updated.gateway.records) == 1 and not updated.trading_authority


def test_exact_command_replay_is_idempotent():
    adapter = PaperExchangeAdapterV1.create(gateway()); value = command(adapter)
    updated, first = adapter.execute(value); replayed, second = updated.execute(value)
    assert replayed is updated and second.reason is PaperAdapterReason.IDEMPOTENT_REPLAY
    assert second.paper_order_id == first.paper_order_id and len(updated.gateway.records) == 1


def test_command_identity_conflict_rejects_without_mutation():
    adapter = PaperExchangeAdapterV1.create(gateway()); value = command(adapter)
    updated, _ = adapter.execute(value)
    conflict = replace(value, submission=replace(value.submission, reference_price=Decimal("101")))
    same, receipt = updated.execute(conflict)
    assert same is updated and receipt.reason is PaperAdapterReason.COMMAND_CONFLICT


def test_stale_snapshot_rejects_without_recording_receipt():
    adapter = PaperExchangeAdapterV1.create(gateway())
    same, receipt = adapter.execute(replace(command(adapter), expected_gateway_snapshot_id=sha("old")))
    assert same is adapter and receipt.reason is PaperAdapterReason.STALE_GATEWAY_SNAPSHOT
    assert not same.receipts


def test_gateway_rejection_is_durably_idempotent():
    adapter = PaperExchangeAdapterV1.create(gateway())
    value = command(adapter, submission=replace(submission(), authorized=False))
    updated, first = adapter.execute(value); replayed, second = updated.execute(value)
    assert not first.accepted and first.reason is PaperAdapterReason.GATEWAY_REJECTED
    assert second.reason is PaperAdapterReason.IDEMPOTENT_REPLAY and replayed is updated


def test_distinct_command_cannot_duplicate_order():
    adapter = PaperExchangeAdapterV1.create(gateway()); adapter, _ = adapter.execute(command(adapter))
    duplicate = PaperAdapterCommandV1(sha("other-command"), adapter.gateway.snapshot_id,
        submission=replace(submission("b"), intent=intent("a")))
    updated, receipt = adapter.execute(duplicate)
    assert not receipt.accepted and receipt.gateway_reason == PaperGatewayReason.DUPLICATE_CONFLICT.value
    assert len(updated.gateway.records) == 1


def test_event_application_and_replay():
    adapter = PaperExchangeAdapterV1.create(gateway()); adapter, submitted = adapter.execute(command(adapter))
    event = PaperOrderEventV1(sha("event"), submitted.paper_order_id, PaperEventKind.FILL,
        NOW + timedelta(seconds=1), 0, Decimal("1"))
    value = PaperAdapterCommandV1(sha("event-command"), adapter.gateway.snapshot_id, event=event)
    updated, receipt = adapter.execute(value); replayed, replay = updated.execute(value)
    assert receipt.reason is PaperAdapterReason.EVENT_APPLIED
    assert updated.gateway.records[0].state is PaperOrderState.FILLED
    assert replayed is updated and replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY


def test_event_is_snapshot_bound():
    adapter = PaperExchangeAdapterV1.create(gateway())
    fake = PaperOrderEventV1(sha("event"), sha("order"), PaperEventKind.CANCEL, NOW, 0)
    _, receipt = adapter.execute(PaperAdapterCommandV1(sha("cmd"), sha("stale"), event=fake))
    assert receipt.reason is PaperAdapterReason.STALE_GATEWAY_SNAPSHOT


def test_disconnect_blocks_submission_until_exact_reconciliation():
    adapter = PaperExchangeAdapterV1.create(gateway()); adapter, _ = adapter.execute(command(adapter))
    disconnected = adapter.disconnect()
    blocked, receipt = disconnected.execute(command(disconnected, "b"))
    assert receipt.gateway_reason == PaperGatewayReason.DISCONNECTED.value
    record = disconnected.gateway.records[0]
    observed = ((record.paper_order_id, record.state, record.filled_quantity,
                 record.remaining_quantity, record.version),)
    recovered, reason = disconnected.reconcile(disconnected.gateway.snapshot_id, observed)
    assert reason is PaperAdapterReason.RECONCILED and recovered.gateway.connected
    recovered, receipt = recovered.execute(command(recovered, "b"))
    assert receipt.accepted


def test_reconciliation_mismatch_activates_kill_switch():
    adapter = PaperExchangeAdapterV1.create(gateway()); adapter, _ = adapter.execute(command(adapter))
    disconnected = adapter.disconnect(); failed, reason = disconnected.reconcile(disconnected.gateway.snapshot_id, ())
    assert reason is PaperAdapterReason.RECONCILIATION_MISMATCH
    assert failed.gateway.kill_switch_active and not failed.gateway.connected


def test_reconciliation_itself_is_snapshot_bound():
    adapter = PaperExchangeAdapterV1.create(gateway()).disconnect()
    same, reason = adapter.reconcile(sha("stale"), ())
    assert same is adapter and reason is PaperAdapterReason.STALE_GATEWAY_SNAPSHOT


def test_adapter_integrity_detects_tampering():
    adapter = PaperExchangeAdapterV1.create(gateway())
    with pytest.raises(ValueError, match="integrity"):
        replace(adapter, adapter_id=sha("tampered")).verify_integrity()


def test_command_requires_exactly_one_action_and_no_authority():
    adapter = PaperExchangeAdapterV1.create(gateway())
    with pytest.raises(ValueError, match="exactly one"):
        PaperAdapterCommandV1(sha("x"), adapter.gateway.snapshot_id)
    with pytest.raises(ValueError, match="exactly one"):
        PaperAdapterCommandV1(sha("x"), adapter.gateway.snapshot_id, submission=submission(),
                              event=PaperOrderEventV1(sha("e"), sha("o"), PaperEventKind.CANCEL, NOW, 0))
    with pytest.raises(ValueError, match="trading authority"):
        replace(command(adapter), trading_authority=True)


def test_receipts_are_immutable_and_content_addressed():
    adapter = PaperExchangeAdapterV1.create(gateway()); updated, receipt = adapter.execute(command(adapter))
    assert isinstance(updated.receipts, tuple)
    assert updated.adapter_id != adapter.adapter_id
    assert receipt.before_snapshot_id == adapter.gateway.snapshot_id
    assert receipt.after_snapshot_id == updated.gateway.snapshot_id


def test_module_has_no_external_transport_or_credentials():
    from pathlib import Path
    source = Path(__file__).with_name("paper_exchange_adapter_v1.py").read_text("utf-8").lower()
    for prohibited in ("requests", "httpx", "socket", "websocket", "private_key", "api_key",
                       "password", "place_order", "submit_live", "scheduledtask", "subprocess"):
        assert prohibited not in source
