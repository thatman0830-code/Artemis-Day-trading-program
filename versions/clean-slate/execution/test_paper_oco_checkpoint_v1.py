import json
from decimal import Decimal

import pytest

import execution.paper_oco_checkpoint_v1 as module
from execution.paper_oco_checkpoint_v1 import PaperOCOCheckpointV1
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.test_paper_oco_execution_v1 import fixture, observed, account
from backtesting.execution_accounting_v2.specifications import canonical_fingerprint as fingerprint


def setup(tmp_path, **bar_values):
    args, _, _ = fixture()
    store = PaperOCOCheckpointV1(tmp_path, initial=args)
    doc = store.initialize()
    candle = observed(**bar_values)
    payload = dict(bar=candle, evaluated_at=candle.available_at, accounting=args["accounting"])
    return args, store, doc, payload


def advance(store, doc, payload, evidence=None, kind="EVALUATE"):
    return store.advance(kind=kind, payload=payload, evidence=evidence or {},
        expected_checkpoint_id=doc["checkpoint_id"])


@pytest.mark.parametrize("volume,state", [("100", "FLAT_REQUIRES_SIBLING_CANCELLATION"),
    ("10", "PARTIAL_REQUIRES_REARM")])
def test_restart_preserves_pending_and_acknowledged_block(tmp_path, volume, state):
    args, store, doc, payload = setup(tmp_path, volume=Decimal(volume))
    doc = advance(store, doc, payload)
    evidence = {fingerprint(payload): payload}
    restarted = PaperOCOCheckpointV1(tmp_path, initial=args)
    loaded, coordinator = restarted.load(evidence=evidence)
    assert loaded == doc and coordinator.state == "AWAITING_ACCOUNTING"
    assert coordinator.pending.evaluation.fills
    ack = {"accounting": account(args["accounting"], coordinator.pending)}
    doc = advance(restarted, doc, ack, evidence, "ACK")
    evidence[fingerprint(ack)] = ack
    loaded, coordinator = PaperOCOCheckpointV1(tmp_path, initial=args).load(evidence=evidence)
    assert coordinator.state == state and loaded == doc
    assert loaded["body"]["trading_authority"] is False
    with pytest.raises(PaperOCOError, match="blocked"):
        coordinator.evaluate(**payload)


def test_no_touch_replay_preserves_bar_cursor(tmp_path):
    args, store, doc, payload = setup(tmp_path, open=Decimal(100), high=Decimal(100),
        low=Decimal(100), close=Decimal(100))
    doc = advance(store, doc, payload)
    evidence = {fingerprint(payload): payload}
    _, coordinator = store.load(evidence=evidence)
    assert coordinator.state == "ARMED" and coordinator.last_close == payload["bar"].close_time
    with pytest.raises(PaperOCOError, match="replay"):
        advance(store, doc, payload, evidence)
    with pytest.raises(PaperOCOError, match="blocked"):
        store.load(evidence=evidence)


def test_missing_or_replaced_evidence_never_rearms(tmp_path):
    _, store, doc, payload = setup(tmp_path)
    advance(store, doc, payload)
    for evidence in ({}, {fingerprint(payload): {"accounting": payload["accounting"]}}):
        with pytest.raises(PaperOCOError, match="evidence"):
            store.load(evidence=evidence)
    with pytest.raises(PaperOCOError, match="already exists"):
        store.initialize()


@pytest.mark.parametrize("failure_call", [1, 2])
def test_replace_failure_before_commit_is_conservative(tmp_path, monkeypatch, failure_call):
    _, store, doc, payload = setup(tmp_path)
    original = module.os.replace
    calls = 0
    def fail(source, destination):
        nonlocal calls
        calls += 1
        if calls == failure_call:
            raise OSError("injected interruption")
        original(source, destination)
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        advance(store, doc, payload)
    if failure_call == 1:
        assert store.load(evidence={})[0] == doc  # evaluation never began
    else:
        with pytest.raises(PaperOCOError, match="blocked"):
            store.load(evidence={})
    assert not store.lock.exists()


def test_failure_after_final_replace_reloads_committed_result(tmp_path, monkeypatch):
    _, store, doc, payload = setup(tmp_path)
    original = module.os.replace
    calls = 0
    def fail(source, destination):
        nonlocal calls
        calls += 1
        original(source, destination)
        if calls == 2:
            raise OSError("lost acknowledgement")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        advance(store, doc, payload)
    evidence = {fingerprint(payload): payload}
    loaded, coordinator = store.load(evidence=evidence)
    assert coordinator.state == "AWAITING_ACCOUNTING"
    assert loaded["checkpoint_id"] != doc["checkpoint_id"]
    with pytest.raises(PaperOCOError, match="stale"):
        advance(store, doc, payload, evidence)


def test_foreign_lock_is_preserved_and_stale_cas_does_not_modify(tmp_path):
    _, store, doc, payload = setup(tmp_path)
    store.lock.touch()
    with pytest.raises(PaperOCOError, match="lock conflict"):
        advance(store, doc, payload)
    assert store.lock.exists()
    store.lock.unlink()
    with pytest.raises(PaperOCOError, match="stale"):
        advance(store, {"checkpoint_id": "0" * 64}, payload)
    assert store.load(evidence={})[0] == doc


@pytest.mark.parametrize("damage", ["checksum", "duplicate", "oversized", "state", "authority"])
def test_corruption_and_rehashed_invalid_state_reject(tmp_path, damage):
    _, store, doc, _ = setup(tmp_path)
    if damage == "duplicate":
        raw = '{"body":{},"body":{}}'
    elif damage == "oversized":
        raw = " " * (module.MAX_BYTES + 1)
    else:
        doc["body"]["state"] = "AWAITING_ACCOUNTING"
        if damage == "authority":
            doc["body"]["trading_authority"] = True
        if damage != "checksum":
            doc["checkpoint_id"] = fingerprint(doc["body"])
        raw = json.dumps(doc)
    store.path.write_text(raw, encoding="utf-8")
    with pytest.raises(PaperOCOError):
        store.load(evidence={})


def test_missing_checkpoint_and_wrong_initial_identity_reject(tmp_path):
    args, store, _, _ = setup(tmp_path)
    altered, _, _ = fixture("2")
    with pytest.raises(PaperOCOError):
        PaperOCOCheckpointV1(tmp_path, initial=altered).load(evidence={})
    store.path.unlink()
    with pytest.raises(FileNotFoundError):
        store.load(evidence={})


def test_invalid_accounting_ack_durably_blocks(tmp_path):
    _, store, doc, payload = setup(tmp_path)
    doc = advance(store, doc, payload)
    with pytest.raises(PaperOCOError, match="reconcile"):
        advance(store, doc, {"accounting": payload["accounting"]},
            {fingerprint(payload): payload}, "ACK")
    with pytest.raises(PaperOCOError, match="blocked"):
        store.load(evidence={fingerprint(payload): payload})
