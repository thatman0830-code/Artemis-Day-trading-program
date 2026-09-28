import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from execution.paper_oco_execution_v1 import PaperOCOError
from execution.paper_oco_handoff_v1 import PaperOCOHandoffStoreV1
from execution.test_paper_oco_replacement_v1 import proposal
from execution.test_paper_oco_execution_v1 import H


def setup(tmp_path):
    args = proposal(tmp_path)
    store = PaperOCOHandoffStoreV1(args.pop("predecessor"))
    source = args["source_bar"]
    first = replace(source, bar_id=H("first-gap"),
        open_time=source.open_time-timedelta(minutes=1), close_time=source.open_time,
        available_at=source.open_time)
    args["gap_bars"] = (first, source)
    return store, args


def test_preparation_replays_without_activating_or_mutating_predecessor(tmp_path):
    store, args = setup(tmp_path)
    before = store.predecessor.load()[0]
    doc = store.prepare(**args)
    assert doc == store.prepare(**args)
    assert doc == PaperOCOHandoffStoreV1(store.predecessor).load()
    assert doc["state"] == "PREPARED_ONLY"
    assert doc["trading_authority"] is False and doc["rearm_authorized"] is False
    assert doc["assessment"]["requires_runtime_revalidation"] is True
    assert doc["assessment"]["uncovered_tail"] is False
    assert store.predecessor.load()[0] == before


def test_conflicting_retry_preserves_first_proposal(tmp_path):
    store, args = setup(tmp_path)
    doc = store.prepare(**args)
    args["stop"] = replace(args["stop"], order_id=H("different"), action_id=H("different-action"))
    with pytest.raises(PaperOCOError, match="conflicting"):
        store.prepare(**args)
    assert store.load() == doc


def test_directory_only_reopen_preserves_prepared_handoff(tmp_path):
    from execution.paper_oco_initial_v1 import create_persisted_protective_session, open_persisted_protective_session
    store, args = setup(tmp_path)
    root = tmp_path / "persisted"
    root.mkdir()
    runner = create_persisted_protective_session(root, initial=store.predecessor.journal.initial)
    old_doc, _ = store.predecessor.load()
    for action in old_doc["body"]["actions"]:
        doc, _ = runner.load()
        runner.advance(kind=action["kind"], payload=store.predecessor.evidence.get(action["evidence_id"]),
            expected_checkpoint_id=doc["checkpoint_id"])
    prepared = PaperOCOHandoffStoreV1(runner).prepare(**args)
    del runner, store, args
    assert PaperOCOHandoffStoreV1(open_persisted_protective_session(root)).load() == prepared


@pytest.mark.parametrize("fault", ["missing", "empty", "duplicate", "version", "future", "ineligible", "touch_stop", "touch_target", "end", "stale"])
def test_incomplete_or_unsafe_gap_rejected_without_record(tmp_path, fault):
    store, args = setup(tmp_path)
    first, source = args["gap_bars"]
    if fault == "missing": args["gap_bars"] = (source,)
    elif fault == "empty": args["gap_bars"] = ()
    elif fault == "duplicate": args["gap_bars"] = (first, first, source)
    elif fault == "end": args["gap_bars"] = (first,)
    elif fault == "stale": args["expected_checkpoint_id"] = "0"*64
    else:
        changes = {"version": dict(source_version="foreign"),
            "future": dict(available_at=args["reviewed_at"]+timedelta(seconds=1)),
            "ineligible": dict(data_quality_valid=False),
            "touch_stop": dict(low=Decimal(99)), "touch_target": dict(high=Decimal(101))}
        args["gap_bars"] = (replace(first, **changes[fault]), source)
    with pytest.raises(ValueError): store.prepare(**args)
    assert not store.path.exists()
    assert not store.predecessor.journal.lock.exists()


@pytest.mark.parametrize("fault", ["truncated", "identity", "authority", "assessment"])
def test_corrupt_record_blocks_retry_without_repair(tmp_path, fault):
    store, args = setup(tmp_path)
    doc = store.prepare(**args)
    if fault == "truncated": raw = b'{"version":'
    else:
        if fault == "identity": doc["handoff_id"] = "0"*64
        elif fault == "authority": doc["rearm_authorized"] = True
        else: doc["assessment"]["requires_runtime_revalidation"] = False
        raw = json.dumps(doc).encode()
    store.path.write_bytes(raw)
    with pytest.raises(PaperOCOError): store.prepare(**args)
    assert store.path.read_bytes() == raw


def test_foreign_lock_preserved(tmp_path):
    store, args = setup(tmp_path)
    store.predecessor.journal.lock.write_bytes(b"other-writer")
    with pytest.raises(PaperOCOError): store.prepare(**args)
    assert store.predecessor.journal.lock.read_bytes() == b"other-writer"
    assert not store.path.exists()


def test_sync_failure_reports_failure_and_retry_revalidates(tmp_path, monkeypatch):
    store, args = setup(tmp_path)
    import execution.paper_oco_handoff_v1 as module
    with monkeypatch.context() as patch:
        patch.setattr(module.os, "fsync", lambda _: (_ for _ in ()).throw(OSError("sync failed")))
        with pytest.raises(OSError, match="sync failed"): store.prepare(**args)
    assert not store.predecessor.journal.lock.exists()
    assert store.prepare(**args)["state"] == "PREPARED_ONLY"


def test_uncovered_tail_is_explicit_and_never_authorized(tmp_path):
    store, args = setup(tmp_path)
    args["reviewed_at"] += timedelta(seconds=20)
    for key in ("stop", "target"):
        args[key] = replace(args[key], submitted_at=args["reviewed_at"], activation_at=args["reviewed_at"])
    doc = store.prepare(**args)
    assert doc["assessment"]["uncovered_tail"] is True
    assert doc["rearm_authorized"] is False
