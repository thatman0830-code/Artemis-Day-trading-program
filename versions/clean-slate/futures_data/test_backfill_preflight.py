from __future__ import annotations

import json
import shutil
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from futures_data.backfill_preflight import (PREFLIGHT_NAMES, PROBE_NAMES, PreflightError,
    _classify_contract_rows, _discover_metadata, _discovery_dates, _validate_contract_rows,
    build_inventory, credential_free_mock_opener,
    run_preflight, validate_raw_probe)
from futures_data.raw_probe import run_raw_probe
from futures_data.aggregate_probe import credential_free_mock_opener as raw_mock_opener

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _metadata(repository: Path) -> Path:
    path = repository / "data/backtests/es_nq_metadata_dry_run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"as_of_utc": NOW.isoformat().replace("+00:00", "Z"),
        "contracts": {"ES": [{"ticker": "ESU6"}], "NQ": [{"ticker": "NQU6"}]}},
        sort_keys=True), encoding="utf-8")
    return path


def _raw_probe(repository: Path) -> None:
    run_raw_probe(key="synthetic-offline-only", metadata_report=_metadata(repository),
                  repository=repository, now=NOW, opener=raw_mock_opener, sleep=lambda _: None)


def test_real_probe_artifacts_recompute_and_are_market_isolated():
    repository = Path(__file__).resolve().parents[1]
    result = validate_raw_probe(repository)
    assert result["status"] == "ES_NQ_RAW_PROBE_VALIDATED"
    assert result["markets"]["ES"]["ticker"] == "ESM6"
    assert result["markets"]["NQ"]["ticker"] == "NQM6"
    assert all(x["row_count"] == 6900 and x["raw_retained"] for x in result["markets"].values())
    assert (repository / "data/backtests" / PROBE_NAMES["ES"]).resolve() != (repository / "data/backtests" / PROBE_NAMES["NQ"]).resolve()


def test_preflight_is_metadata_only_separate_and_deterministic(tmp_path):
    _raw_probe(tmp_path)
    calls = []
    def opener(request, timeout):
        calls.append(request)
        assert "/aggs/" not in request.full_url
        assert "apikey" not in request.full_url.lower()
        assert request.get_header("Authorization") == "Bearer synthetic-offline-only"
        return credential_free_mock_opener(request, timeout)
    result = run_preflight(key="synthetic-offline-only", repository=tmp_path, as_of=NOW,
                           opener=opener, sleep=lambda _: None)
    assert result["aggregate_requests"] == 0 and len(calls) == result["metadata_requests"]
    assert 4 <= len(calls) <= 24
    for root in ("ES", "NQ"):
        market = tmp_path / "data/backtests" / PREFLIGHT_NAMES[root]
        raw = market / "raw/001_contract_discovery.json"
        manifest = json.loads((market / "manifests/001_metadata_request.json").read_text())
        inventory = json.loads((market / "plans/inventory.json").read_text())
        assert sha256(raw.read_bytes()).hexdigest() == manifest["raw_response_sha256"]
        assert manifest["raw_retained"] is True and manifest["aggregate_requests"] == 0
        assert inventory["backfill_started"] is False and inventory["contract_count"] > 0
        assert inventory["minimum_untouched_oos_trades_for_acceptance"] == 200
    assert (tmp_path / "data/backtests/es_backfill_preflight_1").resolve() != (tmp_path / "data/backtests/nq_backfill_preflight_1").resolve()


def test_preflight_refuses_existing_destination_without_network(tmp_path):
    _raw_probe(tmp_path)
    (tmp_path / "data/backtests/es_backfill_preflight_1").mkdir()
    called = False
    def forbidden(*args):
        nonlocal called
        called = True
        raise AssertionError("network must not run")
    with pytest.raises(PreflightError, match="destination exists"):
        run_preflight(key="synthetic-offline-only", repository=tmp_path, as_of=NOW,
                      opener=forbidden, sleep=lambda _: None)
    assert called is False


@pytest.mark.parametrize("mutation", [
    {"ticker": "ESU6", "product_code": "ES", "type": "combo"},
    {"ticker": "ESU6", "product_code": "ES", "trading_venue": "XNYM"},
    {"ticker": "NQU6", "product_code": "NQ"},
])
def test_contract_scope_fails_closed(mutation):
    row = {"ticker": "ESU6", "product_code": "ES", "type": "single", "trading_venue": "XCME",
           "first_trade_date": "2025-01-01", "last_trade_date": "2026-09-18", "settlement_date": "2026-09-18"}
    row.update(mutation)
    with pytest.raises(PreflightError):
        _validate_contract_rows("ES", [row], start=NOW.date().replace(year=2024), end=NOW.date())


def test_retained_shape_standard_outright_is_accepted_and_spread_is_excluded():
    common = {"product_code": "ES", "type": "single", "trading_venue": "XCME",
              "first_trade_date": "2024-06-21", "last_trade_date": "2025-06-20",
              "settlement_date": "2025-06-20", "active": True, "date": "2025-06-01",
              "days_to_maturity": 19, "group_code": "structural-fixture",
              "max_order_quantity": 100, "min_order_quantity": 1, "name": "sanitized",
              "settlement_tick_size": 0.25, "spread_tick_size": 0.05, "trade_tick_size": 0.25}
    rows = [{**common, "ticker": "ESM5"}, {**common, "ticker": "ESM5-ESU5"}]
    accepted, excluded = _classify_contract_rows("ES", rows, start=NOW.date().replace(year=2024), end=NOW.date())
    assert [x["ticker"] for x in accepted] == ["ESM5"]
    assert excluded == ({"category": "SPREAD_OR_COMBO", "sanitized_ticker_pattern": "AAA9-AAA9", "ticker_length": 9},)


@pytest.mark.parametrize(("ticker", "category"), [
    ("MESU6", "MICRO"), ("ES1!", "CONTINUOUS_OR_SYNTHETIC"),
    ("ESM6C7000", "OPTION_OR_NON_OUTRIGHT_OR_MALFORMED"), ("BAD", "OPTION_OR_NON_OUTRIGHT_OR_MALFORMED"),
])
def test_non_outright_tickers_are_excluded_never_accepted(ticker, category):
    outright = {"ticker": "ESU6", "product_code": "ES", "type": "single", "trading_venue": "XCME",
                "first_trade_date": "2025-01-01", "last_trade_date": "2026-09-18",
                "settlement_date": "2026-09-18"}
    candidate = {**outright, "ticker": ticker}
    accepted, excluded = _classify_contract_rows("ES", [outright, candidate],
        start=NOW.date().replace(year=2024), end=NOW.date())
    assert [x["ticker"] for x in accepted] == ["ESU6"]
    assert excluded[0]["category"] == category


def test_raw_probe_tamper_is_detected(tmp_path):
    _raw_probe(tmp_path)
    raw = tmp_path / "data/backtests/es_probe_staging_2/raw/003_aggregates.json"
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(PreflightError, match="checksum conflict"):
        validate_raw_probe(tmp_path)


def test_inventory_uses_bounded_five_session_windows():
    contracts = ({"ticker": "ESH6", "root": "ES", "eligible_start": "2026-01-05",
                  "eligible_end_exclusive": "2026-01-13"},)
    result = build_inventory("ES", contracts, raw_bytes_per_row=__import__("decimal").Decimal("200"))
    assert result["estimated_sessions"] == 6
    assert result["estimated_aggregate_requests"] == 2
    assert result["estimated_duration_minutes_at_4_requests_per_minute"] == 1


def test_reports_and_manifests_never_contain_credentials(tmp_path):
    _raw_probe(tmp_path)
    canary = "massive_canary_secret_fragment_123456789"
    run_preflight(key=canary, repository=tmp_path, as_of=NOW,
                  opener=lambda request, timeout: credential_free_mock_opener(
                      type("Request", (), {"full_url": request.full_url,
                           "get_header": lambda self, name: "Bearer synthetic-offline-only"})(), timeout),
                  sleep=lambda _: None)
    for path in (tmp_path / "data/backtests").rglob("*"):
        if path.is_file():
            assert canary.encode() not in path.read_bytes()


def test_http_failure_retains_only_bounded_sanitized_diagnostic(tmp_path):
    _raw_probe(tmp_path)
    canary = "massive_canary_secret_fragment_123456789"
    body = json.dumps({"request_id": "request-safe-1", "error": {"code": "BAD_FILTER",
        "type": "invalid_request", "param": "first_trade_date.lt",
        "message": "Authorization Bearer " + canary}}).encode()
    with pytest.raises(PreflightError) as caught:
        run_preflight(key=canary, repository=tmp_path, as_of=NOW,
                      opener=lambda request, timeout: (422, body, {"Content-Type": "application/json"}),
                      sleep=lambda _: None)
    assert caught.value.safe["rejection_category"] == "INVALID_ENDPOINT_OR_PARAMETERS"
    rejected = next((tmp_path / "data/backtests/rejected_preflights").glob("preflight_*"))
    diagnostic = json.loads((rejected / "sanitized_diagnostic.json").read_text())
    assert diagnostic["http_status"] == 422 and diagnostic["provider_error_code"] == "BAD_FILTER"
    assert diagnostic["pagination_page_number"] == 1 and diagnostic["aggregate_requests"] == 0
    assert diagnostic["sanitized_error_message"] == "[REDACTED]"
    assert canary not in json.dumps(diagnostic) and not any(p.name.startswith("raw") for p in rejected.rglob("*"))


def test_metadata_pagination_is_bounded_filtered_and_checkpointed(tmp_path):
    calls = []
    pagination_sent = False
    def opener(request, timeout):
        nonlocal pagination_sent
        calls.append(request.full_url)
        parsed = urllib.parse.urlparse(request.full_url)
        query = urllib.parse.parse_qs(parsed.query)
        if "cursor" not in query:
            assert query["product_code"] == ["ES"] and query["type"] == ["single"]
            assert query["active"] == ["true"] and "date" in query
            payload = {"status": "OK", "request_id": "page-1", "results": []}
            if not pagination_sent:
                payload["next_url"] = "https://api.massive.com/futures/v1/contracts?cursor=opaque-page-2"
                pagination_sent = True
        else:
            assert query == {"cursor": ["opaque-page-2"]}
            payload = {"status": "OK", "request_id": "page-2", "results": []}
        return 200, json.dumps(payload).encode(), {"Content-Type": "application/json"}
    rows, count = _discover_metadata("ES", "synthetic-offline-only", start=NOW.date().replace(year=2024),
        end=NOW.date(), opener=opener, sleep=lambda _: None, market=tmp_path,
        prior_calls=0, retrieved_at=NOW)
    expected = len(_discovery_dates(NOW.date().replace(year=2024), NOW.date())) + 1
    assert rows == [] and count == expected and len(calls) == expected
    assert len(list((tmp_path / "raw").glob("*.json"))) == expected
    assert len(list((tmp_path / "checkpoints").glob("*.json"))) == expected


def test_timeout_is_distinct_and_no_retry_occurs(tmp_path):
    _raw_probe(tmp_path)
    calls = 0
    def opener(request, timeout):
        nonlocal calls
        calls += 1
        raise TimeoutError("timed out")
    with pytest.raises(PreflightError) as caught:
        run_preflight(key="synthetic-offline-only", repository=tmp_path, as_of=NOW,
                      opener=opener, sleep=lambda _: None)
    assert calls == 1
    assert caught.value.safe["rejection_category"] == "TIMEOUT_OR_CONNECTIVITY"
    assert caught.value.safe["timeout_category"] == "TIMEOUT"
    assert caught.value.safe["exception_class"] == "TimeoutError"
