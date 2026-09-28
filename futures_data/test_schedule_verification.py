from __future__ import annotations

import json
import io
from hashlib import sha256

import pytest

from futures_data.schedule_verification import (RESULT_NAME, ScheduleVerificationError,
    verify_schedules)


def page(root: str, *, next_url: str | None = None) -> bytes:
    product_name = "E-mini S&P 500 Futures" if root == "ES" else "E-mini Nasdaq-100 Futures"
    value = {"results": [
        {"product_code": root, "product_name": product_name, "trading_venue": "XCME",
         "session_end_date": "2025-06-02", "event": "open",
         "timestamp": "2025-06-01T22:00:00Z"},
        {"product_code": root, "product_name": product_name, "trading_venue": "XCME",
         "session_end_date": "2025-06-02", "event": "close",
         "timestamp": "2025-06-02T21:00:00Z"}]}
    if next_url:
        value["next_url"] = next_url
    return json.dumps(value).encode()


def test_schedules_only_raw_first_isolated_and_no_retry(tmp_path):
    calls = []
    def fetch(url, key):
        calls.append((url, key))
        root = "ES" if "product_code=ES" in url else "NQ"
        return 200, page(root), {"content_type": "application/json", "request_id": "safe-id"}
    result = verify_schedules(tmp_path, "synthetic-canary", fetch=fetch, sleep=lambda _: None)
    assert result["network_calls"] == 2 and result["aggregate_requests"] == 0
    assert result["automatic_retry"] is False
    archive = tmp_path / "data/backtests" / RESULT_NAME
    assert (archive / "ES/raw").resolve() != (archive / "NQ/raw").resolve()
    for root in ("ES", "NQ"):
        manifest_path = next((archive / root / "manifests").glob("*.json"))
        manifest = json.loads(manifest_path.read_text())
        raw = archive / root / manifest["raw_relative_path"]
        assert sha256(raw.read_bytes()).hexdigest() == manifest["raw_sha256"]
        assert manifest["aggregate_requests"] == 0 and manifest["automatic_retry"] is False
        assert b"synthetic-canary" not in raw.read_bytes()
    assert "synthetic-canary" not in "".join(p.read_text(errors="ignore") for p in archive.rglob("*") if p.is_file())


@pytest.mark.parametrize("mutation,match", [
    (lambda value: value["results"][0].update(product_code="MES"), "wrong-product"),
    (lambda value: value["results"][0].pop("timestamp"), "fields"),
    (lambda value: value.update(next_url="https://evil.example/x"), "pagination boundary"),
])
def test_schema_and_scope_fail_closed(tmp_path, mutation, match):
    def fetch(url, key):
        root = "ES" if "product_code=ES" in url else "NQ"
        value = json.loads(page(root)); mutation(value)
        return 200, json.dumps(value).encode(), {}
    with pytest.raises(ScheduleVerificationError, match=match):
        verify_schedules(tmp_path, "synthetic-canary", fetch=fetch, sleep=lambda _: None)


def test_existing_path_and_provider_failure_are_not_retried(tmp_path):
    calls = []
    def failed(url, key):
        calls.append(url); return 403, b'{"error":"forbidden"}', {}
    with pytest.raises(ScheduleVerificationError, match="provider"):
        verify_schedules(tmp_path, "synthetic-canary", fetch=failed, sleep=lambda _: None)
    assert len(calls) == 1
    with pytest.raises(ScheduleVerificationError, match="existing"):
        verify_schedules(tmp_path, "synthetic-canary", fetch=failed, sleep=lambda _: None)


def test_response_and_pagination_caps_fail_closed(tmp_path, monkeypatch):
    import futures_data.schedule_verification as module
    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 4)
    with pytest.raises(ScheduleVerificationError, match="cap"):
        verify_schedules(tmp_path, "synthetic-canary",
                         fetch=lambda *_: (200, b"12345", {}), sleep=lambda _: None)


def test_outight_and_spread_with_same_events_are_not_false_duplicates(tmp_path):
    def fetch(url, key):
        root = "ES" if "product_code=ES" in url else "NQ"
        value = json.loads(page(root))
        spread_name = "ES Equity Calendar Spread" if root == "ES" else "NQ Calendar Spread"
        value["results"] += [{**row, "product_name": spread_name} for row in value["results"]]
        return 200, json.dumps(value).encode(), {}
    report = verify_schedules(tmp_path, "synthetic-canary", fetch=fetch, sleep=lambda _: None)
    assert report["markets"]["ES"]["returned_records"] == 4
    assert report["markets"]["ES"]["outright_records"] == 2
    assert report["markets"]["ES"]["excluded_other_product_records"] == 2


def test_true_duplicate_and_conflicting_product_fail_closed(tmp_path):
    def duplicate(url, key):
        root = "ES" if "product_code=ES" in url else "NQ"
        value = json.loads(page(root)); value["results"].append(dict(value["results"][0]))
        return 200, json.dumps(value).encode(), {}
    with pytest.raises(ScheduleVerificationError, match="duplicated within one source"):
        verify_schedules(tmp_path, "synthetic-canary", fetch=duplicate, sleep=lambda _: None)


def test_empty_range_is_not_assumed_to_be_non_session(tmp_path):
    with pytest.raises(ScheduleVerificationError, match="empty without adjacent"):
        verify_schedules(tmp_path, "synthetic-canary",
                         fetch=lambda *_: (200, b'{"results":[]}', {}), sleep=lambda _: None)


def test_no_recorder_or_aggregate_capability_is_exposed():
    import futures_data.schedule_verification as module
    source = open(module.__file__, encoding="utf-8").read().lower()
    assert "start_recorder" not in source and "execute_pass_b" not in source
    assert '"aggregate_requests": 0' in source


def test_cli_failure_is_concise_redacted_and_persists_safe_diagnostic(tmp_path, monkeypatch, capsys):
    import futures_data.schedule_verification as module
    (tmp_path / "data/backtests" / module.STAGING_NAME).mkdir(parents=True)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO("synthetic-canary-secret\n"))
    assert module.main(["--repository", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err and "synthetic-canary-secret" not in captured.err
    diagnostic = next((tmp_path / "data/backtests/schedule_verification_diagnostics").glob("*.json"))
    assert "synthetic-canary-secret" not in diagnostic.read_text()
