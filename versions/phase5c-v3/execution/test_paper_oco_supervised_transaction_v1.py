import json

import pytest

from execution.paper_oco_supervised_transaction_v1 import (
    PaperOCOSupervisedStage,
    PaperOCOSupervisedTransactionError,
    PaperOCOSupervisedTransactionStoreV1,
    PaperOCOSupervisedTransactionV1,
)
from execution.test_paper_performance_ledger_v1 import H


def prepared():
    return PaperOCOSupervisedTransactionV1.prepare(
        bridge_id=H("bridge"),
        oco_before_checkpoint_id=H("oco-before"),
        adapter_before_id=H("adapter-before"),
        performance_before_id=H("performance-before"),
    )


def test_records_every_checkpoint_boundary_with_cas(tmp_path):
    store = PaperOCOSupervisedTransactionStoreV1(tmp_path)
    first = store.initialize(prepared())
    performance = store.advance(expected_transaction_id=first.transaction_id,
        expected_stage=PaperOCOSupervisedStage.PREPARED,
        stage=PaperOCOSupervisedStage.PERFORMANCE_COMMITTED,
        adapter_after_id=H("adapter-after"),
        performance_after_id=H("performance-after"))
    accounting = store.advance(expected_transaction_id=first.transaction_id,
        expected_stage=PaperOCOSupervisedStage.PERFORMANCE_COMMITTED,
        stage=PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED,
        oco_accounting_checkpoint_id=H("oco-accounting"))
    final = store.advance(expected_transaction_id=first.transaction_id,
        expected_stage=PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED,
        stage=PaperOCOSupervisedStage.COMMITTED,
        oco_final_checkpoint_id=H("oco-final"))
    assert performance.stage is PaperOCOSupervisedStage.PERFORMANCE_COMMITTED
    assert accounting.stage is PaperOCOSupervisedStage.ACCOUNTING_ACKNOWLEDGED
    assert final.stage is PaperOCOSupervisedStage.COMMITTED
    assert store.load() == final
    assert final.trading_authority is False


def test_exact_prepare_replay_and_conflict(tmp_path):
    store = PaperOCOSupervisedTransactionStoreV1(tmp_path)
    first = store.initialize(prepared())
    assert store.initialize(prepared()) == first
    other = PaperOCOSupervisedTransactionV1.prepare(
        bridge_id=H("other"),
        oco_before_checkpoint_id=H("oco-before"),
        adapter_before_id=H("adapter-before"),
        performance_before_id=H("performance-before"),
    )
    with pytest.raises(PaperOCOSupervisedTransactionError, match="conflicting"):
        store.initialize(other)


@pytest.mark.parametrize("damage", ["payload", "checksum", "duplicate", "stage"])
def test_tamper_or_incomplete_stage_rejects(tmp_path, damage):
    store = PaperOCOSupervisedTransactionStoreV1(tmp_path)
    store.initialize(prepared())
    document = json.loads(store.path.read_text("utf-8"))
    if damage == "payload":
        document["payload"]["bridge_id"] = H("tampered")
    elif damage == "checksum":
        document["payload_sha256"] = H("bad")
    elif damage == "duplicate":
        raw = store.path.read_text("utf-8").replace(
            '"payload":', '"payload":{},"payload":', 1)
        store.path.write_text(raw, "utf-8")
        with pytest.raises(PaperOCOSupervisedTransactionError):
            store.load()
        return
    else:
        document["payload"]["stage"] = "COMMITTED"
    store.path.write_text(json.dumps(document), "utf-8")
    with pytest.raises(PaperOCOSupervisedTransactionError):
        store.load()


def test_stale_or_skipped_transition_preserves_prepared_state(tmp_path):
    store = PaperOCOSupervisedTransactionStoreV1(tmp_path)
    first = store.initialize(prepared())
    with pytest.raises(PaperOCOSupervisedTransactionError):
        store.advance(expected_transaction_id=H("stale"),
            expected_stage=PaperOCOSupervisedStage.PREPARED,
            stage=PaperOCOSupervisedStage.PERFORMANCE_COMMITTED,
            adapter_after_id=H("adapter-after"),
            performance_after_id=H("performance-after"))
    with pytest.raises(PaperOCOSupervisedTransactionError):
        store.advance(expected_transaction_id=first.transaction_id,
            expected_stage=PaperOCOSupervisedStage.PREPARED,
            stage=PaperOCOSupervisedStage.COMMITTED,
            oco_final_checkpoint_id=H("oco-final"))
    assert store.load() == first


def test_writer_lock_and_interrupted_replace_fail_closed(tmp_path, monkeypatch):
    store = PaperOCOSupervisedTransactionStoreV1(tmp_path)
    store.lock.write_text("held", "utf-8")
    with pytest.raises(PaperOCOSupervisedTransactionError, match="lock"):
        store.initialize(prepared())
    store.lock.unlink()
    store.initialize(prepared())
    original = store.path.read_bytes()
    monkeypatch.setattr("execution.paper_oco_supervised_transaction_v1.os.replace",
                        lambda *_: (_ for _ in ()).throw(OSError("power loss")))
    with pytest.raises(OSError, match="power loss"):
        store.advance(expected_transaction_id=prepared().transaction_id,
            expected_stage=PaperOCOSupervisedStage.PREPARED,
            stage=PaperOCOSupervisedStage.PERFORMANCE_COMMITTED,
            adapter_after_id=H("adapter-after"),
            performance_after_id=H("performance-after"))
    assert store.path.read_bytes() == original
    assert not store.lock.exists()


def test_module_has_no_runtime_or_transport_surface():
    from pathlib import Path
    source = Path(__file__).with_name(
        "paper_oco_supervised_transaction_v1.py").read_text("utf-8").lower()
    for word in ("requests", "httpx", "socket", "websocket", "api_key",
                 "private_key", "place_order", "submit_live", "subprocess"):
        assert word not in source
