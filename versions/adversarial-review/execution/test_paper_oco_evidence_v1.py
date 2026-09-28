from decimal import Decimal
import json

import pytest

import execution.paper_oco_evidence_v1 as module
from execution.paper_oco_evidence_v1 import DurablePaperOCOReplayV1
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.test_paper_oco_execution_v1 import fixture, observed, account
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint


def setup(tmp_path, volume="100"):
    initial, _, _ = fixture()
    runner = DurablePaperOCOReplayV1(tmp_path, initial=initial)
    checkpoint = runner.initialize()
    bar = observed(volume=Decimal(volume))
    payload = dict(bar=bar, evaluated_at=bar.available_at, accounting=initial["accounting"])
    return initial, runner, checkpoint, payload


@pytest.mark.parametrize("volume,state", [("100", "FLAT_REQUIRES_SIBLING_CANCELLATION"),
    ("10", "PARTIAL_REQUIRES_REARM")])
def test_disk_only_action_replay_then_accounting_ack(tmp_path, volume, state):
    initial, runner, doc, payload = setup(tmp_path, volume)
    doc = runner.advance(kind="EVALUATE", payload=payload, expected_checkpoint_id=doc["checkpoint_id"])
    del runner, payload
    restarted = DurablePaperOCOReplayV1(tmp_path, initial=initial)
    loaded, coordinator = restarted.load()
    assert loaded == doc and coordinator.state == "AWAITING_ACCOUNTING"
    ack = dict(accounting=account(initial["accounting"], coordinator.pending))
    doc = restarted.advance(kind="ACK", payload=ack, expected_checkpoint_id=doc["checkpoint_id"])
    del restarted, ack, coordinator
    loaded, coordinator = DurablePaperOCOReplayV1(tmp_path, initial=initial).load()
    assert loaded == doc and coordinator.state == state
    assert loaded["body"]["trading_authority"] is False


def test_exact_duplicate_put_is_read_only(tmp_path):
    _, runner, _, payload = setup(tmp_path)
    identity = runner.evidence.put(payload)
    path = runner.evidence._path(identity)
    before = path.stat().st_mtime_ns
    assert runner.evidence.put(payload) == identity
    assert path.stat().st_mtime_ns == before
    assert runner.evidence.get(identity) == payload


@pytest.mark.parametrize("damage", ["missing", "partial", "tampered", "duplicate", "authority", "type"])
def test_bad_retained_evidence_blocks_restart(tmp_path, damage):
    _, runner, doc, payload = setup(tmp_path)
    runner.advance(kind="EVALUATE", payload=payload, expected_checkpoint_id=doc["checkpoint_id"])
    path = runner.evidence._path(canonical_fingerprint(payload))
    if damage == "missing":
        path.unlink()
    elif damage == "partial":
        path.write_bytes(b'{')
    elif damage == "duplicate":
        path.write_text('{"version":1,"version":2}', encoding="utf-8")
    else:
        value = json.loads(path.read_text())
        if damage == "tampered":
            value["payload"]["bar"]["close"]["$decimal"] = "100"
        elif damage == "authority":
            value["trading_authority"] = True
        else:
            value["payload"]["accounting"]["$type"] = "UnknownExecutableType"
        path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises((PaperOCOError, FileNotFoundError)):
        runner.load()
    if damage != "missing":
        with pytest.raises(PaperOCOError):
            runner.evidence.put(payload)  # corrupt evidence is not overwritten


def test_evidence_write_failure_never_advances_journal(tmp_path, monkeypatch):
    _, runner, doc, payload = setup(tmp_path)
    def fail(_):
        raise OSError("injected fsync failure")
    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError):
        runner.advance(kind="EVALUATE", payload=payload, expected_checkpoint_id=doc["checkpoint_id"])
    assert runner.load()[0] == doc


def test_stale_update_can_leave_only_unreferenced_evidence(tmp_path):
    _, runner, doc, payload = setup(tmp_path)
    with pytest.raises(PaperOCOError, match="stale"):
        runner.advance(kind="EVALUATE", payload=payload, expected_checkpoint_id="0" * 64)
    assert runner.load()[0] == doc
    assert runner.evidence.get(canonical_fingerprint(payload)) == payload


def test_identity_path_and_operation_reject(tmp_path):
    _, runner, doc, payload = setup(tmp_path)
    for identity in ("../other", "A" * 64, "0" * 63):
        with pytest.raises(PaperOCOError):
            runner.evidence.get(identity)
    with pytest.raises(PaperOCOError):
        runner.advance(kind="ACK", payload=payload, expected_checkpoint_id=doc["checkpoint_id"])
    assert runner.load()[0] == doc


def test_size_limit_rejects_before_write(tmp_path, monkeypatch):
    _, runner, doc, payload = setup(tmp_path)
    monkeypatch.setattr(module, "MAX_EVIDENCE_BYTES", 10)
    with pytest.raises(PaperOCOError, match="size"):
        runner.evidence.put(payload)
    assert runner.load()[0] == doc
