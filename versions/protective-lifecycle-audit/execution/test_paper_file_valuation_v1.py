from dataclasses import replace
from datetime import timedelta
import hashlib

import pytest

from execution.paper_file_valuation_v1 import (
    PaperSnapshotReferenceV1, PaperFileValuationV1, PaperFileValuationError, read_paper_snapshot,
)
from execution.paper_closed_bar_input_v1 import MAX_BYTES
from execution.test_paper_closed_bar_input_v1 import HEADER, row
from execution.test_bounded_paper_session_v1 import driver
from execution.test_paper_clock_guard_v1 import health
from execution.test_paper_performance_ledger_v1 import T, H
from monitoring.paper_performance_view_v1 import load_performance_view


def setup(tmp_path):
    root = tmp_path / "snapshots"; root.mkdir()
    payload = (HEADER+row(-1)).encode()
    (root/"btc.csv").write_bytes(payload)
    reference = PaperSnapshotReferenceV1("btc.csv",hashlib.sha256(payload).hexdigest(),T)
    session = driver(tmp_path)
    runner = PaperFileValuationV1(session=session,snapshot_root=root,timeframe="1m",
        maximum_bar_age=timedelta(minutes=1),instrument_id="BTC",
        mark_specification_id=H("mark-spec"),source_version="synthetic-file-v1")
    runner.start(lambda:health(),utc_reader=lambda:T,monotonic_reader=lambda:0)
    return runner, session, root, reference


def poll(runner, reference, sec, reader=None):
    return runner.poll(reference, reader or (lambda:health(sec)),
        utc_reader=lambda:T+timedelta(seconds=sec),monotonic_reader=lambda:sec*1_000_000_000)


def test_file_to_clock_to_checkpoint_to_dashboard_view_and_stop(tmp_path):
    runner, session, root, ref = setup(tmp_path)
    receipt, _ = poll(runner,ref,1)
    first = session.bridge.store.path.read_bytes()
    repeated, _ = poll(runner,ref,2)
    assert repeated is receipt
    assert session.bridge.store.path.read_bytes() == first
    for sec in range(5,60,5):
        poll(runner,ref,sec)
    payload = (HEADER+row(-1)+row(0,close="50700")).encode()
    (root/"btc.csv").write_bytes(payload)
    ref2 = PaperSnapshotReferenceV1("btc.csv",hashlib.sha256(payload).hexdigest(),T+timedelta(minutes=1))
    next_receipt, _ = poll(runner,ref2,60)
    assert next_receipt.receipt_id != receipt.receipt_id
    view = load_performance_view(session.bridge.store.path,observed_at=T+timedelta(minutes=1))
    assert view["available"] and view["integrity"] == "VERIFIED"
    assert view["position"]["mark_price"] == "50700"
    assert view["position"]["quantity"] == "0"
    assert view["trade_markers"] == []
    assert view["gateway_snapshot_id"] == session.workflow.store.load().gateway.snapshot_id
    assert session.stop(T+timedelta(minutes=1)).state == "STOPPED"
    assert not session.workflow.store.load().gateway.connected


@pytest.mark.parametrize("fault", ["missing","hash","csv","future","clock","gap"])
def test_input_faults_stop_and_do_not_add_orders(tmp_path,fault):
    runner, session, root, ref = setup(tmp_path)
    poll(runner,ref,1)
    retained = session.bridge.store.load().snapshot
    if fault == "missing": ref = replace(ref,relative_path="absent.csv")
    elif fault == "hash": ref = replace(ref,sha256="a"*64)
    elif fault == "csv":
        payload = b"not a csv"; (root/"btc.csv").write_bytes(payload)
        ref = replace(ref,sha256=hashlib.sha256(payload).hexdigest())
    elif fault == "future": ref = replace(ref,available_at=T+timedelta(seconds=3))
    reader = (lambda:replace(health(2),synchronized=False)) if fault == "clock" else None
    with pytest.raises(PaperFileValuationError):
        poll(runner,ref,7 if fault == "gap" else 2,reader)
    assert runner.failed and not session.active
    assert not session.workflow.lock_path.exists()
    assert not session.workflow.store.load().gateway.connected
    assert not session.workflow.store.load().gateway.records
    assert session.bridge.store.load().snapshot == retained
    with pytest.raises(PaperFileValuationError,match="latched"):
        poll(runner,ref,3)


def test_repolling_old_file_does_not_refresh_bar_age(tmp_path):
    runner, session, _, ref = setup(tmp_path)
    for sec in range(5,65,5): poll(runner,ref,sec)
    with pytest.raises(PaperFileValuationError) as error:
        poll(runner,ref,65)
    assert "stale" in str(error.value.__cause__)
    assert not session.active


def test_failed_stop_is_explicit(tmp_path,monkeypatch):
    runner, session, _, ref = setup(tmp_path)
    def fail(now): raise OSError("stop storage unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(session,"stop",fail)
        with pytest.raises(PaperFileValuationError,match="unconfirmed"):
            poll(runner,replace(ref,relative_path="missing.csv"),1)
        assert runner.failed and session.active
    session.stop(T)


@pytest.mark.parametrize("path",["../escape.csv","C:/escape.csv","/absolute.csv","btc.csv:stream","..\\escape.csv"])
def test_unsafe_reference_paths_reject(path):
    with pytest.raises(PaperFileValuationError):
        PaperSnapshotReferenceV1(path,H("file"),T)


def test_oversized_file_rejected_before_read(tmp_path):
    payload = b"x"*(MAX_BYTES+1)
    (tmp_path/"big.csv").write_bytes(payload)
    ref = PaperSnapshotReferenceV1("big.csv",hashlib.sha256(payload).hexdigest(),T)
    with pytest.raises(PaperFileValuationError,match="size"):
        read_paper_snapshot(tmp_path,ref)


def test_observed_change_during_read_rejects(tmp_path,monkeypatch):
    import execution.paper_file_valuation_v1 as module
    payload = (HEADER+row(-1)).encode(); (tmp_path/"btc.csv").write_bytes(payload)
    ref = PaperSnapshotReferenceV1("btc.csv",hashlib.sha256(payload).hexdigest(),T)
    original = module.os.fstat
    calls = 0
    def changed(fd):
        nonlocal calls
        calls += 1
        result = original(fd)
        if calls == 2:
            from types import SimpleNamespace
            return SimpleNamespace(st_dev=result.st_dev,st_ino=result.st_ino,
                st_size=result.st_size+1,st_mtime_ns=result.st_mtime_ns,st_ctime_ns=result.st_ctime_ns)
        return result
    monkeypatch.setattr(module.os,"fstat",changed)
    with pytest.raises(PaperFileValuationError,match="changed"):
        read_paper_snapshot(tmp_path,ref)
