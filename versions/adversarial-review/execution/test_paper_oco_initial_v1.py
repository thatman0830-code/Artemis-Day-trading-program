from decimal import Decimal
import json

import pytest

import execution.paper_oco_initial_v1 as module
from execution.paper_oco_initial_v1 import create_persisted_protective_session, open_persisted_protective_session
from execution.paper_oco_execution_v1 import PaperOCOError
from execution.test_paper_oco_execution_v1 import fixture, observed, account
from execution.test_paper_oco_cancellation_v1 import prepared


@pytest.mark.parametrize("volume,state", [("100", "FLAT_REQUIRES_SIBLING_CANCELLATION"),
    ("10", "PARTIAL_REQUIRES_REARM")])
def test_reopen_entire_protective_replay_with_directory_only(tmp_path, volume, state):
    initial, _, _ = fixture()
    runner = create_persisted_protective_session(tmp_path, initial=initial)
    doc, _ = runner.load()
    candle = observed(volume=Decimal(volume))
    doc = runner.advance(kind="EVALUATE", payload=dict(bar=candle, evaluated_at=candle.available_at,
        accounting=initial["accounting"]), expected_checkpoint_id=doc["checkpoint_id"])
    del initial, runner
    runner = open_persisted_protective_session(tmp_path)
    loaded, coordinator = runner.load()
    assert loaded == doc and coordinator.state == "AWAITING_ACCOUNTING"
    updated = account(coordinator.accounting, coordinator.pending)
    runner.advance(kind="ACK", payload={"accounting": updated}, expected_checkpoint_id=doc["checkpoint_id"])
    del runner, coordinator, updated
    assert open_persisted_protective_session(tmp_path).load()[1].state == state
    # Obtain the matching synthetic cancellation facts from the existing fixture;
    # reopen still receives only the directory, not any constructor inputs.
    fixture_root = tmp_path / "cancellation-fixture"
    fixture_root.mkdir()
    _, _, _, cancellation_payload = prepared(fixture_root, volume)
    reopened = open_persisted_protective_session(tmp_path)
    doc, _ = reopened.load()
    reopened.advance(kind="CANCEL_ACK", payload=cancellation_payload,
        expected_checkpoint_id=doc["checkpoint_id"])
    final = open_persisted_protective_session(tmp_path).load()[1]
    assert final.state == ("CLOSED_FLAT" if volume == "100" else "CANCELLED_REQUIRES_REARM")


def test_initial_round_trip_and_reinitialization_refusal(tmp_path):
    initial, _, _ = fixture()
    runner = create_persisted_protective_session(tmp_path, initial=initial)
    assert runner.journal.initial == initial
    assert runner.load()[1].state == "ARMED"
    with pytest.raises(PaperOCOError, match="already exists"):
        create_persisted_protective_session(tmp_path, initial=initial)


@pytest.mark.parametrize("damage", ["partial", "duplicate", "type", "authority", "checksum", "missing_field"])
def test_invalid_configuration_blocks_reopen(tmp_path, damage):
    initial, _, _ = fixture()
    create_persisted_protective_session(tmp_path, initial=initial)
    path = tmp_path / "oco-initial.json"
    doc = json.loads(path.read_text())
    if damage == "partial":
        raw = "{"
    elif damage == "duplicate":
        raw = '{"version":1,"version":2}'
    else:
        if damage == "type":
            doc["initial"]["ledger"]["oco_type"] = "Executable"
        elif damage == "authority":
            doc["trading_authority"] = True
        elif damage == "checksum":
            doc["initial_id"] = "0" * 64
        else:
            del doc["initial"]["instructions"]
        raw = json.dumps(doc)
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(PaperOCOError):
        open_persisted_protective_session(tmp_path)


def test_failed_initial_write_never_creates_journal(tmp_path, monkeypatch):
    initial, _, _ = fixture()
    def fail(_):
        raise OSError("injected sync failure")
    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError):
        create_persisted_protective_session(tmp_path, initial=initial)
    assert not (tmp_path / "oco-checkpoint.json").exists()
    with pytest.raises(FileNotFoundError):
        open_persisted_protective_session(tmp_path)
    with pytest.raises(PaperOCOError, match="already exists"):
        create_persisted_protective_session(tmp_path, initial=initial)


def test_missing_journal_does_not_reinitialize(tmp_path):
    initial, _, _ = fixture()
    create_persisted_protective_session(tmp_path, initial=initial)
    (tmp_path / "oco-checkpoint.json").unlink()
    with pytest.raises(FileNotFoundError):
        open_persisted_protective_session(tmp_path)


def test_foreign_lock_blocks_open_and_is_preserved(tmp_path):
    initial, _, _ = fixture()
    create_persisted_protective_session(tmp_path, initial=initial)
    lock = tmp_path / "oco-checkpoint.lock"
    lock.touch()
    with pytest.raises(PaperOCOError, match="lock"):
        open_persisted_protective_session(tmp_path)
    assert lock.exists()


def test_oversized_configuration_rejects(tmp_path, monkeypatch):
    initial, _, _ = fixture()
    create_persisted_protective_session(tmp_path, initial=initial)
    monkeypatch.setattr(module, "MAX_INITIAL_BYTES", 10)
    with pytest.raises(PaperOCOError, match="size"):
        open_persisted_protective_session(tmp_path)
