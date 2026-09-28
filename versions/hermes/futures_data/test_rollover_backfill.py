from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from futures_data.rollover_backfill import (ActiveWindow, ContractFact, DailyVolumeFact,
    FrozenRollDecision, PairPlan, RequestStore, RolloverBackfillError, build_active_windows,
    _normalize_volume, build_fixed_inventory, build_pass_a_plan, decide_roll)
from futures_data.contracts import identity

NOW = datetime(2026, 8, 26, 20, 44, tzinfo=timezone.utc)


def pair() -> PairPlan:
    sessions = tuple(date(2026, 6, day) for day in (12, 15, 16, 17, 18))
    return PairPlan("pair-1", "ES", "old", "ESH6", "new", "ESM6", sessions,
                    datetime(2026, 6, 11, 22, tzinfo=timezone.utc),
                    datetime(2026, 6, 18, 21, tzinfo=timezone.utc), ("req-old", "req-new"))


def volume_facts(p: PairPlan, comparisons: tuple[tuple[str, str], ...]) -> tuple[DailyVolumeFact, ...]:
    facts = []
    for session, (old, new) in zip(p.sessions, comparisons):
        finalized = datetime.combine(session, datetime.min.time(), timezone.utc) + timedelta(hours=22)
        for contract_id, ticker, value in ((p.outgoing_id, p.outgoing_ticker, old),
                                            (p.incoming_id, p.incoming_ticker, new)):
            ident = identity(p.id, contract_id, session, value)
            facts.append(DailyVolumeFact(ident, p.id, contract_id, ticker, session,
                                         Decimal(value), finalized, "request"))
    return tuple(facts)


def test_two_completed_session_crossover_is_effective_next_session():
    p = pair(); facts = volume_facts(p, (("10","9"),("10","11"),("10","12"),("1","99"),("1","99")))
    result = decide_roll(p, facts, evaluated_at=NOW)
    assert result.reason == "TWO_CONSECUTIVE_FINALIZED_DAILY_VOLUME_CROSSOVER"
    assert result.decision_session == p.sessions[2]
    assert result.effective_session == p.sessions[3]


def test_future_fact_is_rejected_and_later_data_does_not_move_first_decision():
    p = pair(); base = volume_facts(p, (("10","11"),("10","12"),("10","1"),("10","99"),("10","99")))
    first = decide_roll(p, base, evaluated_at=NOW)
    assert first.effective_session == p.sessions[2]
    future = replace(base[0], finalized_at=NOW + timedelta(minutes=1))
    with pytest.raises(RolloverBackfillError, match="future"):
        decide_roll(p, (future,) + base[1:], evaluated_at=NOW)


def test_missing_crossover_uses_completed_calendar_fallback_before_last_trade():
    p = pair(); facts = volume_facts(p, (("10","9"),)*5)
    result = decide_roll(p, facts, evaluated_at=NOW)
    assert result.reason == "CALENDAR_FALLBACK_BEFORE_LAST_TRADABLE_SESSION"
    assert result.decision_session == p.sessions[-2]
    assert result.effective_session == p.sessions[-1]
    incomplete = tuple(x for x in facts if not (x.session == p.sessions[-2] and x.contract_id == p.incoming_id))
    with pytest.raises(RolloverBackfillError, match="fallback evidence"):
        decide_roll(p, incomplete, evaluated_at=NOW)


def test_active_windows_are_nonoverlapping_and_preserve_contract_identity():
    contracts = tuple(ContractFact(x, "ES", ticker, month, 2026, date(2024,1,1), expiry, expiry, "XCME", ("hash",))
        for x,ticker,month,expiry in (("a","ESH6",3,date(2026,3,20)),("b","ESM6",6,date(2026,6,18)),("c","ESU6",9,date(2026,9,18))))
    decisions = (FrozenRollDecision("d1","p1","ES","a","b",date(2026,3,16),NOW,date(2026,3,17),"x",()),
                 FrozenRollDecision("d2","p2","ES","b","c",date(2026,6,15),NOW,date(2026,6,16),"x",()))
    windows = build_active_windows(contracts, decisions, start=date(2025,6,1), end=date(2026,8,26))
    assert [x.ticker for x in windows] == ["ESH6","ESM6","ESU6"]
    assert all(left.end_exclusive == right.start for left,right in zip(windows,windows[1:]))


def test_actual_metadata_deduplicates_and_uses_lifecycle_year_and_excludes_far_future():
    repository = Path(__file__).resolve().parents[1]
    es = build_fixed_inventory(repository, "ES"); nq = build_fixed_inventory(repository, "NQ")
    assert [x.ticker for x in es["contracts"]] == ["ESM5","ESU5","ESZ5","ESH6","ESM6","ESU6"]
    assert [x.ticker for x in nq["contracts"]] == ["NQM5","NQU5","NQZ5","NQH6","NQM6","NQU6"]
    assert len({x.id for x in es["contracts"]}) == 6 and all(len(x.provenance_sha256) >= 1 for x in es["contracts"])
    assert "ESZ0" in es["excluded"]["FAR_FUTURE_CONTRACTS"]
    assert next(x for x in es["contracts"] if x.ticker == "ESU6").contract_year == 2026


def test_corrected_estimate_is_bounded_and_separate():
    plan = build_pass_a_plan(Path(__file__).resolve().parents[1])
    assert plan["aggregate_requests_made"] == 0 and plan["automatic_retry"] is False
    assert plan["combined_pass_a"]["requests"] == 20
    assert plan["combined_pass_a"]["rows"] == 138000
    assert plan["markets"]["ES"]["pass_a_estimate"]["requests"] == 10
    assert plan["markets"]["NQ"]["pass_a_estimate"]["requests"] == 10


def test_request_store_checkpoint_resume_checksum_stop_isolation_and_redaction(tmp_path):
    store = RequestStore(tmp_path, "plan")
    facts = {"endpoint_class":"futures_minute_aggregates","ticker":"ESH6"}
    store.commit("ES", "request", raw=b'{"status":"OK"}', normalized=b'[]\n', request_facts=facts)
    assert store.is_complete("ES", "request")
    store.commit("ES", "request", raw=b"different", normalized=b"different", request_facts=facts)
    assert not (store.stage / "NQ").exists()
    raw = store.stage / "ES/raw/request.json"; raw.write_bytes(b"tamper")
    with pytest.raises(RolloverBackfillError, match="checksum"):
        store.is_complete("ES", "request")
    other = RequestStore(tmp_path / "other", "plan")
    other.stop_file.parent.mkdir(parents=True, exist_ok=True); other.stop_file.write_text("stop")
    with pytest.raises(RolloverBackfillError, match="stop"):
        other.commit("NQ", "request", raw=b"{}", normalized=b"[]", request_facts=facts)
    clean = RequestStore(tmp_path / "clean", "plan")
    with pytest.raises(RolloverBackfillError, match="credential"):
        clean.commit("ES", "request", raw=b"{}", normalized=b"[]",
                     request_facts={"Authorization":"Bearer synthetic-canary-secret"})
    assert not any("synthetic-canary-secret" in p.read_text(errors="ignore") for p in tmp_path.rglob("*") if p.is_file())


def test_raw_is_retained_before_schema_failure_and_promotion_is_atomic(tmp_path):
    store = RequestStore(tmp_path, "plan")
    facts = {"endpoint_class":"futures_minute_aggregates","ticker":"ESH6"}
    store.retain_raw("ES", "bad", raw=b'{"unexpected":true}', request_facts=facts)
    assert (store.stage / "ES/raw/bad.json").read_bytes() == b'{"unexpected":true}'
    assert not (store.stage / "ES/checkpoints/bad.json").exists()
    store.commit("NQ", "good", raw=b'{"status":"OK"}', normalized=b'[]\n', request_facts={**facts,"ticker":"NQH6"})
    destination = store.promote()
    assert destination.name == "es_nq_rollover_discovery_1" and not store.stage.exists()
    assert (destination / "NQ/raw/good.json").read_bytes() == b'{"status":"OK"}'


def test_request_store_resumes_verified_raw_without_redownload(tmp_path):
    store = RequestStore(tmp_path, "plan")
    raw = b'{"results":[]}'
    facts = {"endpoint_class": "futures_minute_aggregates", "ticker": "ESM6",
             "start_utc": "2026-01-01T00:00:00Z", "end_utc": "2026-01-02T00:00:00Z",
             "http_status": 200, "response_content_type": "application/json",
             "provider_request_id": "safe-request-id"}
    store.retain_raw("ES", "request", raw=raw, request_facts=facts)

    resumed = store.retained_raw("ES", "request")
    assert resumed is not None
    assert resumed[0] == raw
    assert resumed[1]["raw_sha256"] == sha256(raw).hexdigest()

    (store.stage / "ES/raw/request.json").write_bytes(b"corrupt")
    with pytest.raises(RolloverBackfillError, match="checksum conflict"):
        store.retained_raw("ES", "request")


def test_volume_normalization_preserves_contract_and_rejects_partial_response():
    p = pair(); stamp = int(p.start_utc.timestamp() * 1_000_000_000)
    row = {"ticker":p.outgoing_ticker,"window_start":stamp,"session_end_date":p.sessions[0].isoformat(),
           "open":"100","high":"101","low":"99","close":"100.5","volume":"7"}
    raw = json.dumps({"status":"OK","results":[row]}).encode()
    result = json.loads(_normalize_volume(raw, asdict_pair := {
        "id":p.id,"sessions":[x.isoformat() for x in p.sessions],
        "start_utc":p.start_utc.isoformat().replace("+00:00","Z"),
        "end_utc":p.end_utc.isoformat().replace("+00:00","Z")},
        p.outgoing_id,p.outgoing_ticker,"request",NOW))
    assert result[0]["contract_id"] == p.outgoing_id and result[0]["ticker"] == p.outgoing_ticker
    with pytest.raises(RolloverBackfillError, match="partial"):
        _normalize_volume(json.dumps({"status":"OK","results":[row],"next_url":"bounded-page"}).encode(),
                          asdict_pair,p.outgoing_id,p.outgoing_ticker,"request",NOW)
