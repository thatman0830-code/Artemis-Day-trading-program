import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from futures_data.metadata_dry_run import MetadataDryRunError, run_metadata_dry_run

NOW=datetime(2026,8,26,tzinfo=timezone.utc)


def mock_open(request, timeout):
    assert request.get_header("Authorization") == "Bearer synthetic-key-123456"
    assert "apiKey" not in request.full_url
    query=parse_qs(urlparse(request.full_url).query); root=query["product_code"][0]
    if "/contracts" in request.full_url:
        suffix="U6"; result={"product_code":root,"ticker":root+suffix,"type":"single",
          "first_trade_date":"2025-01-01","last_trade_date":"2026-09-18","settlement_date":"2026-09-18",
          "trade_tick_size":0.25,"trading_venue":"XCME"}
    else:
        result={"product_code":root,"name":root+" E-mini","type":"single","trading_venue":"XCME",
          "unit_of_measure":"index points","unit_of_measure_qty":50 if root=="ES" else 20,"settlement_currency_code":"USD"}
    return 200,json.dumps({"status":"OK","results":[result]}).encode()


def test_metadata_only_dry_run_is_bounded_and_header_authenticated(tmp_path):
    sleeps=[]; report=run_metadata_dry_run(key="synthetic-key-123456",as_of=NOW,repository=tmp_path,opener=mock_open,sleep=sleeps.append)
    assert report["status"]=="DRY_RUN_VALIDATED" and report["request_count"]==4
    assert report["aggregate_requests"]==0 and report["collector_started"] is False
    assert sleeps==[15.0,15.0,15.0]


@pytest.mark.parametrize("root,ticker,kind", [
    ("ES","MESU6","MICRO"), ("NQ","MNQU6","MICRO"),
    ("ES","ESU6-ESZ6","OPTION_OR_SPREAD_OR_CONTINUOUS_OR_MALFORMED"),
    ("NQ","NQU6C25000","OPTION_OR_SPREAD_OR_CONTINUOUS_OR_MALFORMED"),
    ("ES","ES1!","OPTION_OR_SPREAD_OR_CONTINUOUS_OR_MALFORMED")])
def test_mixed_or_prohibited_contract_fixture_is_rejected(tmp_path,root,ticker,kind):
    def mixed(request,timeout):
        status,raw=mock_open(request,timeout); payload=json.loads(raw)
        if "/contracts" in request.full_url and parse_qs(urlparse(request.full_url).query)["product_code"][0]==root:
            prohibited=dict(payload["results"][0]); prohibited["ticker"]=ticker
            payload["results"].append(prohibited)
        return status,json.dumps(payload).encode()
    with pytest.raises(MetadataDryRunError) as caught:
        run_metadata_dry_run(key="synthetic-key-123456",as_of=NOW,repository=tmp_path,opener=mixed,sleep=lambda _:None)
    assert caught.value.safe["offending_instrument_class"]==kind


def test_wrong_venue_and_missing_fields_are_safely_classified(tmp_path):
    for mutation,category in (("venue","WRONG_VENUE"),("missing","MISSING_FIELD")):
        def bad(request,timeout):
            status,raw=mock_open(request,timeout); payload=json.loads(raw)
            if "/contracts" in request.full_url:
                if mutation=="venue": payload["results"][0]["trading_venue"]="XCBT"
                else: payload["results"][0].pop("settlement_date")
            return status,json.dumps(payload).encode()
        with pytest.raises(MetadataDryRunError) as caught:
            run_metadata_dry_run(key="synthetic-key-123456",as_of=NOW,repository=tmp_path,opener=bad,sleep=lambda _:None)
        assert caught.value.safe["rejection_category"]==category


@pytest.mark.parametrize("mutation", ["micro","combo","wrong","page"])
def test_invalid_universe_and_pagination_fail_closed(tmp_path,mutation):
    def bad(request,timeout):
        status,raw=mock_open(request,timeout); payload=json.loads(raw)
        if "/contracts" in request.full_url:
            if mutation=="micro": payload["results"][0]["ticker"]="MESU2026"
            if mutation=="combo": payload["results"][0]["type"]="combo"
            if mutation=="wrong": payload["results"][0]["product_code"]="CL"
            if mutation=="page": payload["next_url"]="https://api.massive.com/futures/v1/contracts?cursor=opaque"
        return status,json.dumps(payload).encode()
    with pytest.raises(MetadataDryRunError):
        run_metadata_dry_run(key="synthetic-key-123456",as_of=NOW,repository=tmp_path,opener=bad,sleep=lambda _:None)


def test_auth_and_rate_failures_are_sanitized(tmp_path):
    for status in (401,403,429,500):
        with pytest.raises(MetadataDryRunError) as caught:
            run_metadata_dry_run(key="synthetic-key-123456",as_of=NOW,repository=tmp_path,
                opener=lambda *_:(status,b'{}'),sleep=lambda _:None)
        assert "synthetic-key" not in str(caught.value)
