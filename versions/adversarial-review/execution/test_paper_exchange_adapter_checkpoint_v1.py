from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import pytest

from backtesting.execution_accounting_v2.contracts import OrderIntentV2, OrderSide, OrderType, TimeInForce
from execution.paper_exchange_adapter_checkpoint_v1 import *
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1, PaperAdapterReason, PaperExchangeAdapterV1
from execution.paper_gateway_v2 import PaperGatewayPolicyV1, PaperGatewaySnapshotV1, PaperSubmissionV1

NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
sha = lambda value: hashlib.sha256(value.encode()).hexdigest()
canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def adapter():
    policy = PaperGatewayPolicyV1(Decimal("500"), Decimal("800"), 2, timedelta(seconds=5))
    return PaperExchangeAdapterV1.create(PaperGatewaySnapshotV1.create(policy))


def command(value, name="a"):
    intent = OrderIntentV2("order-intent-v2-1", sha("order-"+name), sha("run"), sha("action-"+name),
        "BTC", "BTC-PERP", None, OrderSide.BUY, Decimal("1"), OrderType.MARKET,
        TimeInForce.IOC, None, None, NOW, NOW, None, None, None, "config-v1", "policy-v1")
    submission = PaperSubmissionV1(sha("key-"+name), intent, Decimal("100"), NOW, NOW,
                                   sha("auth-"+name), True)
    return PaperAdapterCommandV1(sha("command-"+name), value.gateway.snapshot_id,
                                 submission=submission)


def test_deterministic_round_trip_preserves_gateway_and_receipts():
    value = adapter(); value, _ = value.execute(command(value))
    loaded = adapter_from_bytes(adapter_checkpoint_bytes(value))
    assert loaded == value
    assert adapter_checkpoint_bytes(loaded) == adapter_checkpoint_bytes(value)


def test_initialize_execute_and_exact_retry_are_atomic(tmp_path):
    store = PaperAdapterCheckpointStoreV1(tmp_path / "adapter.json"); initial = adapter()
    store.initialize(initial); updated, first = store.execute(command(initial))
    replayed, replay = store.execute(command(initial))
    assert replayed == updated == store.load()
    assert first.accepted and replay.reason is PaperAdapterReason.IDEMPOTENT_REPLAY
    assert len(replayed.gateway.records) == len(replayed.receipts) == 1


def test_restart_is_durably_disconnected_and_requires_reconciliation(tmp_path):
    store = PaperAdapterCheckpointStoreV1(tmp_path / "adapter.json"); initial = adapter()
    store.initialize(initial); submitted, _ = store.execute(command(initial))
    restarted = store.restart(); persisted = store.load()
    assert restarted == persisted and not persisted.gateway.connected
    assert persisted.gateway.reconciliation_required
    blocked, receipt = store.execute(command(restarted, "b"))
    assert not receipt.accepted and blocked.gateway.records == restarted.gateway.records


def test_exact_reconciliation_persists_before_submission_resumes(tmp_path):
    store = PaperAdapterCheckpointStoreV1(tmp_path / "adapter.json"); initial = adapter()
    store.initialize(initial); submitted, _ = store.execute(command(initial)); restarted = store.restart()
    record = restarted.gateway.records[0]
    observed = ((record.paper_order_id, record.state, record.filled_quantity,
                 record.remaining_quantity, record.version),)
    recovered, reason = store.reconcile(restarted.gateway.snapshot_id, observed)
    assert reason is PaperAdapterReason.RECONCILED and store.load() == recovered
    recovered, receipt = store.execute(command(recovered, "b"))
    assert receipt.accepted


def test_reconciliation_mismatch_is_durably_fail_closed(tmp_path):
    store = PaperAdapterCheckpointStoreV1(tmp_path / "adapter.json"); initial = adapter()
    store.initialize(initial); submitted, _ = store.execute(command(initial)); restarted = store.restart()
    failed, reason = store.reconcile(restarted.gateway.snapshot_id, ())
    assert reason is PaperAdapterReason.RECONCILIATION_MISMATCH
    assert store.load() == failed and failed.gateway.kill_switch_active and not failed.gateway.connected


def test_existing_lock_preserves_checkpoint(tmp_path):
    store = PaperAdapterCheckpointStoreV1(tmp_path / "adapter.json"); store.initialize(adapter())
    before = store.path.read_bytes(); store.lock_path.write_text("busy")
    with pytest.raises(PaperAdapterCheckpointError, match="lock"):
        store.restart()
    assert store.path.read_bytes() == before


def test_failed_operation_preserves_checkpoint_and_removes_lock(tmp_path):
    store = PaperAdapterCheckpointStoreV1(tmp_path / "adapter.json"); initial = adapter()
    store.initialize(initial); before = store.path.read_bytes()
    with pytest.raises(ValueError):
        store.execute(replace(command(initial), command_id="bad"))
    assert store.path.read_bytes() == before and not store.lock_path.exists()


def test_tamper_truncation_unknown_duplicate_and_authority_reject():
    raw = adapter_checkpoint_bytes(adapter()); doc = json.loads(raw)
    doc["payload"]["adapter_id"] = sha("tampered")
    with pytest.raises(PaperAdapterCheckpointError, match="checksum"):
        adapter_from_bytes(canonical(doc))
    with pytest.raises(PaperAdapterCheckpointError): adapter_from_bytes(raw[:20])
    doc = json.loads(raw); doc["extra"] = 1
    with pytest.raises(PaperAdapterCheckpointError, match="fields"): adapter_from_bytes(canonical(doc))
    with pytest.raises(PaperAdapterCheckpointError, match="duplicate"):
        adapter_from_bytes(b'{"schema_version":"a","schema_version":"b"}')
    doc = json.loads(raw); doc["payload"]["trading_authority"] = True
    doc["payload_sha256"] = hashlib.sha256(canonical(doc["payload"])).hexdigest()
    with pytest.raises(PaperAdapterCheckpointError, match="authority"):
        adapter_from_bytes(canonical(doc))


def test_receipt_tamper_rejects_even_when_outer_checksum_is_recomputed():
    value = adapter(); value, _ = value.execute(command(value)); doc = json.loads(adapter_checkpoint_bytes(value))
    doc["payload"]["receipts"][0]["accepted"] = False
    doc["payload_sha256"] = hashlib.sha256(canonical(doc["payload"])).hexdigest()
    with pytest.raises(PaperAdapterCheckpointError, match="payload"):
        adapter_from_bytes(canonical(doc))


def test_missing_parent_existing_checkpoint_and_missing_load_reject(tmp_path):
    with pytest.raises(PaperAdapterCheckpointError, match="parent"):
        PaperAdapterCheckpointStoreV1(tmp_path / "missing" / "a.json").initialize(adapter())
    store = PaperAdapterCheckpointStoreV1(tmp_path / "a.json"); store.initialize(adapter())
    with pytest.raises(PaperAdapterCheckpointError, match="already"):
        store.initialize(adapter())
    with pytest.raises(PaperAdapterCheckpointError, match="missing"):
        PaperAdapterCheckpointStoreV1(tmp_path / "none.json").load()


def test_module_has_no_external_transport_credentials_pickle_or_live_submission():
    source = Path(__file__).with_name("paper_exchange_adapter_checkpoint_v1.py").read_text("utf-8").lower()
    for prohibited in ("requests", "httpx", "socket", "websocket", "pickle", "private_key",
                       "api_key", "password", "submit_live", "place_order", "subprocess"):
        assert prohibited not in source
