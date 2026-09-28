from dataclasses import replace
from datetime import timedelta
import json

import pytest

from backtesting.execution_accounting_v2.accounting import PriceEvidenceV2
from execution.paper_performance_checkpoint_v1 import (
    PaperPerformanceCheckpointError, PaperPerformanceCheckpointStoreV1,
    checkpoint_bytes, ledger_from_bytes,
)
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.test_paper_performance_ledger_v1 import T, H, accounting, gateway_fill


def filled_ledger():
    gateway, event, fill, costs = gateway_fill()
    ledger = PaperPerformanceLedgerV1.create(accounting(), gateway).apply_fill(
        gateway=gateway, paper_event=event, fill=fill, economics=costs)
    mark = PriceEvidenceV2("price-evidence-v2-1", H("checkpoint-mark"),
        "BTC", "BTC", None, T + timedelta(minutes=15),
        T + timedelta(minutes=15), fill.economic_price + 1000,
        "MARK", H("mark-spec"), "btc-15m-archive-v1")
    return ledger.apply_mark(mark)


def test_rich_checkpoint_round_trip_is_byte_stable():
    source = filled_ledger()
    restored = ledger_from_bytes(checkpoint_bytes(source))
    assert restored == source
    assert checkpoint_bytes(restored) == checkpoint_bytes(source)
    assert restored.snapshot.equity == source.snapshot.equity


def test_empty_ledger_round_trip():
    gateway, *_ = gateway_fill()
    source = PaperPerformanceLedgerV1.create(accounting(), gateway)
    assert ledger_from_bytes(checkpoint_bytes(source)) == source


def test_checksum_tamper_rejects():
    document = json.loads(checkpoint_bytes(filled_ledger()))
    document["payload_sha256"] = "0" * 64
    with pytest.raises(PaperPerformanceCheckpointError, match="checksum"):
        ledger_from_bytes(json.dumps(document).encode())


def test_authority_tamper_rejects_even_with_recomputed_checksum():
    import hashlib
    from execution.paper_performance_checkpoint_v1 import _canonical
    document = json.loads(checkpoint_bytes(filled_ledger()))
    document["payload"]["trading_authority"] = True
    document["payload_sha256"] = hashlib.sha256(_canonical(document["payload"])).hexdigest()
    with pytest.raises(PaperPerformanceCheckpointError, match="authority"):
        ledger_from_bytes(json.dumps(document).encode())


@pytest.mark.parametrize("raw,match", [
    (b"", "size"),
    (b"not-json", "UTF-8 JSON"),
    (b'{"schema_version":"x","schema_version":"y"}', "duplicate"),
])
def test_malformed_checkpoint_rejects(raw, match):
    with pytest.raises(PaperPerformanceCheckpointError, match=match):
        ledger_from_bytes(raw)


def test_unknown_type_rejects_after_valid_checksum():
    import hashlib
    from execution.paper_performance_checkpoint_v1 import _canonical
    document = json.loads(checkpoint_bytes(filled_ledger()))
    document["payload"]["ledger"]["$type"] = "DangerousClass"
    document["payload_sha256"] = hashlib.sha256(_canonical(document["payload"])).hexdigest()
    with pytest.raises(PaperPerformanceCheckpointError, match="unsupported"):
        ledger_from_bytes(json.dumps(document).encode())


def test_json_float_inside_decimal_tag_rejects_even_with_valid_checksum():
    import hashlib
    from execution.paper_performance_checkpoint_v1 import _canonical
    document = json.loads(checkpoint_bytes(filled_ledger()))
    document["payload"]["ledger"]["fields"]["accounting"]["fields"]["starting_cash"]["$decimal"] = 10000.0
    document["payload_sha256"] = hashlib.sha256(_canonical(document["payload"])).hexdigest()
    with pytest.raises(PaperPerformanceCheckpointError, match="canonical string"):
        ledger_from_bytes(_canonical(document))


def test_atomic_store_initialize_load_and_compare_and_swap(tmp_path):
    source = filled_ledger(); store = PaperPerformanceCheckpointStoreV1(tmp_path / "performance.json")
    store.initialize(source)
    assert store.load() == source
    store.save(source, expected_ledger_id=source.ledger_id)
    assert store.load() == source
    with pytest.raises(PaperPerformanceCheckpointError, match="compare-and-swap"):
        store.save(source, expected_ledger_id="0" * 64)
    assert not store.lock_path.exists()


def test_existing_checkpoint_and_writer_lock_reject(tmp_path):
    source = filled_ledger(); store = PaperPerformanceCheckpointStoreV1(tmp_path / "performance.json")
    store.initialize(source)
    with pytest.raises(PaperPerformanceCheckpointError, match="already exists"):
        store.initialize(source)
    store.lock_path.write_text("held", "utf-8")
    with pytest.raises(PaperPerformanceCheckpointError, match="lock already exists"):
        store.save(source, expected_ledger_id=source.ledger_id)


def test_symlink_checkpoint_rejects(tmp_path):
    source = filled_ledger(); target = tmp_path / "target.json"
    target.write_bytes(checkpoint_bytes(source)); link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(PaperPerformanceCheckpointError, match="unsafe"):
        PaperPerformanceCheckpointStoreV1(link).load()
