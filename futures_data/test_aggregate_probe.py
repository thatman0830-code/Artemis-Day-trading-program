import json
from datetime import datetime, timezone

import pytest

from futures_data.aggregate_probe import (MAX_BARS, ProbeError, credential_free_mock_opener,
    previous_quarter_ticker, run_probe, select_five_sessions)

NOW=datetime(2026,8,26,tzinfo=timezone.utc)


def metadata(tmp_path):
    path=tmp_path/"metadata.json";path.write_text(json.dumps({"status":"DRY_RUN_VALIDATED","as_of_utc":"2026-08-26T00:00:00Z","contracts":{"ES":[{"ticker":"ESU6"}],"NQ":[{"ticker":"NQU6"}]}}));return path


def test_contract_derivation_and_five_ordinary_sessions():
    assert previous_quarter_ticker("ES",("ESU6",),as_of_year=2026)=="ESM6"
    sessions=select_five_sessions(datetime(2026,6,19,tzinfo=timezone.utc).date())
    assert len(sessions)==5 and all(x.weekday()<5 and x.isoformat()!="2026-06-19" for x in sessions)


def test_full_two_market_probe_mock_is_deterministic_and_separate(tmp_path):
    first=run_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=credential_free_mock_opener,sleep=lambda _:None)
    assert first["status"]=="ES_NQ_PROBE_VALIDATED" and first["aggregate_request_count"]==2 and first["total_rows"]==13800
    for root,name in (("ES","es_probe_staging_1"),("NQ","nq_probe_staging_1")):
        folder=tmp_path/"data/backtests"/name;manifest=json.loads((folder/"manifest.json").read_text());data=(folder/"bars.jsonl").read_bytes()
        assert manifest["root"]==root and manifest["row_count"]==6900 and manifest["gap_count"]==0
        assert manifest["normalized_sha256"]==__import__("hashlib").sha256(data).hexdigest()


@pytest.mark.parametrize("mutation,category",[("micro","PROVIDER_CONTRACT_MISMATCH"),("spread","PROVIDER_CONTRACT_MISMATCH"),("venue","PROVIDER_CONTRACT_MISMATCH"),("active","NOT_EXPIRED")])
def test_contract_scope_failures_promote_neither_market(tmp_path,mutation,category):
    def opener(request,timeout):
        status,raw=credential_free_mock_opener(request,timeout);payload=json.loads(raw)
        if request.full_url.find("/contracts")>=0:
            row=payload["results"][0]
            if mutation=="micro":row["ticker"]="MESM6"
            if mutation=="spread":row["type"]="combo"
            if mutation=="venue":row["trading_venue"]="XCBT"
            if mutation=="active":row["last_trade_date"]="2026-09-18";row["settlement_date"]="2026-09-18"
        return status,json.dumps(payload).encode()
    with pytest.raises(ProbeError) as caught:run_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
    assert caught.value.safe["rejection_category"]==category
    assert not (tmp_path/"data/backtests/es_probe_staging_1").exists() and not (tmp_path/"data/backtests/nq_probe_staging_1").exists()


@pytest.mark.parametrize("mutation,category",[("duplicate","DUPLICATE_OR_TIMESTAMP"),("wrong","CONTRACT_CONTAMINATION"),("ohlc","OHLC_OR_VOLUME"),("gap","GAPPED"),("page","PAGINATION_REQUIRED")])
def test_bar_validation_failures(tmp_path,mutation,category):
    def opener(request,timeout):
        status,raw=credential_free_mock_opener(request,timeout);payload=json.loads(raw)
        if "/aggs/" in request.full_url:
            if mutation=="duplicate":payload["results"].append(dict(payload["results"][0]))
            if mutation=="wrong":payload["results"][0]["ticker"]="MESM6"
            if mutation=="ohlc":payload["results"][0]["high"]="1"
            if mutation=="gap":payload["results"].pop(10)
            if mutation=="page":payload["next_url"]="https://api.massive.com/futures/v1/aggs/ESM6?cursor=opaque"
        return status,json.dumps(payload).encode()
    with pytest.raises(ProbeError) as caught:run_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
    assert caught.value.safe["rejection_category"]==category


def test_header_only_and_exact_request_budget(tmp_path):
    calls=[]
    def opener(request,timeout):
        calls.append(request);return credential_free_mock_opener(request,timeout)
    run_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
    assert len(calls)==6 and sum("/aggs/" in x.full_url for x in calls)==2
    assert all("apiKey" not in x.full_url and x.get_header("Authorization")=="Bearer synthetic-offline-only" for x in calls)
    contract_urls=[x.full_url for x in calls if "/contracts" in x.full_url]
    assert sum("product_code=ES" in x for x in contract_urls)==1 and sum("product_code=NQ" in x for x in contract_urls)==1
    assert sum("ticker=ESM6" in x for x in contract_urls)==1 and sum("ticker=NQM6" in x for x in contract_urls)==1


@pytest.mark.parametrize("case",["zero","duplicates","conflict","ignored","micro","combo","venue","expiration"])
def test_exact_ticker_lookup_provider_contract_mismatches(tmp_path,case):
    from urllib.parse import parse_qs,urlparse
    def opener(request,timeout):
        status,raw=credential_free_mock_opener(request,timeout);payload=json.loads(raw);query=parse_qs(urlparse(request.full_url).query)
        if "/contracts" in request.full_url and "ticker" in query:
            row=payload["results"][0]
            if case=="zero":payload["results"]=[]
            elif case=="duplicates":payload["results"].append(dict(row))
            elif case=="conflict":row["first_trade_date"]="2024-02-01"
            elif case=="ignored":row["ticker"]="ESZ6" if row["product_code"]=="ES" else "NQZ6"
            elif case=="micro":row["ticker"]="MESM6" if row["product_code"]=="ES" else "MNQM6"
            elif case=="combo":row["type"]="combo"
            elif case=="venue":row["trading_venue"]="XCBT"
            elif case=="expiration":row["settlement_date"]="2026-06-18"
        return status,json.dumps(payload).encode()
    with pytest.raises(ProbeError) as caught:
        run_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
    assert caught.value.safe["rejection_category"]=="PROVIDER_CONTRACT_MISMATCH"
    assert caught.value.safe["http_status"]==200
    assert isinstance(caught.value.safe["returned_contracts"],list)


@pytest.mark.parametrize("root,micro",[("ES","MESM6"),("NQ","MNQM6")])
def test_discovery_mixed_with_micro_is_provider_mismatch(tmp_path,root,micro):
    from urllib.parse import parse_qs,urlparse
    def opener(request,timeout):
        status,raw=credential_free_mock_opener(request,timeout);payload=json.loads(raw);query=parse_qs(urlparse(request.full_url).query)
        if "/contracts" in request.full_url and query.get("product_code")==[root]:
            bad=dict(payload["results"][0]);bad["ticker"]=micro;bad["product_code"]="MES" if root=="ES" else "MNQ";payload["results"].append(bad)
        return status,json.dumps(payload).encode()
    with pytest.raises(ProbeError) as caught:
        run_probe(key="synthetic-offline-only",metadata_report=metadata(tmp_path),repository=tmp_path,now=NOW,opener=opener,sleep=lambda _:None)
    assert caught.value.safe["rejection_category"]=="PROVIDER_CONTRACT_MISMATCH"
