from datetime import timedelta
from decimal import Decimal
import json

import pytest

from backtesting.futures_canonical_evaluation_v1 import evaluate_futures_canonical_lane
from backtesting.futures_canonical_history_v1 import (
    FuturesCanonicalHistoryError,
    append_futures_canonical_evaluation,
    read_futures_canonical_history,
)
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.test_futures_canonical_evaluation_v1 import NOW, SPEC, prepared


def report(tmp_path, market=FuturesCanonicalMarket.ES, as_of=NOW):
    lane, adapter = prepared(tmp_path, market)
    return evaluate_futures_canonical_lane(lane=lane, adapter=adapter,
        minimum_tick=Decimal("0.25"), instrument_specification_id=SPEC, as_of=as_of)


def test_append_and_read_are_immutable_hash_chained_and_advisory(tmp_path):
    first_report = report(tmp_path / "one")
    second_report = report(tmp_path / "two", as_of=NOW + timedelta(minutes=1))
    first = append_futures_canonical_evaluation(tmp_path / "history", report=first_report)
    second = append_futures_canonical_evaluation(tmp_path / "history", report=second_report)
    history = read_futures_canonical_history(tmp_path / "history", market=FuturesCanonicalMarket.ES)
    assert history == (first, second)
    assert first.sequence == 0 and first.previous_event_id is None
    assert second.sequence == 1 and second.previous_event_id == first.event_id
    assert all(event.report["trading_authority"] is False for event in history)


def test_exact_replay_is_idempotent(tmp_path):
    value = report(tmp_path / "source")
    first = append_futures_canonical_evaluation(tmp_path / "history", report=value)
    assert append_futures_canonical_evaluation(tmp_path / "history", report=value) == first
    assert len(read_futures_canonical_history(tmp_path / "history",
                                              market=FuturesCanonicalMarket.ES)) == 1


def test_es_and_nq_histories_are_physically_separate(tmp_path):
    es = report(tmp_path / "es", FuturesCanonicalMarket.ES)
    nq = report(tmp_path / "nq", FuturesCanonicalMarket.NQ)
    append_futures_canonical_evaluation(tmp_path / "history", report=es)
    append_futures_canonical_evaluation(tmp_path / "history", report=nq)
    assert read_futures_canonical_history(tmp_path / "history", market=FuturesCanonicalMarket.ES)[0].report_id == es.report_id
    assert read_futures_canonical_history(tmp_path / "history", market=FuturesCanonicalMarket.NQ)[0].report_id == nq.report_id


def test_tampering_inventory_and_chronology_fail_closed(tmp_path):
    history_root = tmp_path / "history"
    current = report(tmp_path / "source")
    append_futures_canonical_evaluation(history_root, report=current)
    path = history_root / "ES" / "events" / "00000000000000000000.json"
    value = json.loads(path.read_text()); value["latest_outcome"] = "CANDIDATE"
    path.write_text(json.dumps(value))
    with pytest.raises(FuturesCanonicalHistoryError, match="chain or report binding"):
        read_futures_canonical_history(history_root, market=FuturesCanonicalMarket.ES)

    clean = tmp_path / "clean"
    later = report(tmp_path / "later", as_of=NOW + timedelta(minutes=1))
    append_futures_canonical_evaluation(clean, report=later)
    older = report(tmp_path / "older", as_of=NOW)
    with pytest.raises(FuturesCanonicalHistoryError, match="chronology regressed"):
        append_futures_canonical_evaluation(clean, report=older)


def test_unexpected_file_and_symlink_root_reject(tmp_path):
    root = tmp_path / "history"; current = report(tmp_path / "source")
    append_futures_canonical_evaluation(root, report=current)
    (root / "ES" / "events" / "note.txt").write_text("unexpected")
    with pytest.raises(FuturesCanonicalHistoryError, match="inventory"):
        read_futures_canonical_history(root, market=FuturesCanonicalMarket.ES)
