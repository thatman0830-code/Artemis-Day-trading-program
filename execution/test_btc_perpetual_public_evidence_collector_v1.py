from datetime import datetime,timezone
import json
from dataclasses import replace
import pytest

from execution.btc_perpetual_public_evidence_collector_v1 import *

T=datetime(2026,9,3,tzinfo=timezone.utc)


def payload(**changes):
    asset={"name":"BTC","szDecimals":5,"maxLeverage":40,"marginTableId":56};asset.update(changes)
    return json.dumps([{"universe":[asset,{"name":"ETH","szDecimals":4,"maxLeverage":25,"marginTableId":51}]},
        [{"markPx":"110000","oraclePx":"109990","funding":"0.0000125"},{"markPx":"4400","oraclePx":"4399","funding":"0"}]],separators=(",",":")).encode()


def test_validates_exact_btc_public_facts_without_authority():
    raw=payload();result=validate_btc_perpetual_public_response(payload=raw,captured_at=T,raw_relative_path="raw/f.json")
    assert result.size_decimals==5 and result.maximum_leverage==40 and result.margin_table_id==56
    assert str(result.mark_price)=="110000" and str(result.oracle_price)=="109990"
    assert result.trading_authority is False and result==validate_btc_perpetual_public_response(payload=raw,captured_at=T,raw_relative_path="raw/f.json")
    with pytest.raises(BTCPerpetualPublicEvidenceError,match="identity"): replace(result,receipt_id="0"*64)


def test_injected_collection_retains_exact_bytes_and_is_idempotent(tmp_path):
    raw=payload();calls=[]
    def transport(*args): calls.append(args);return 200,raw
    result=collect_btc_perpetual_public_evidence(transport=transport,output_root=tmp_path,captured_at=T)
    replay=collect_btc_perpetual_public_evidence(transport=transport,output_root=tmp_path,captured_at=T)
    assert replay==result and (tmp_path/result.raw_relative_path).read_bytes()==raw
    assert calls[0][0]==ENDPOINT and calls[0][1]==REQUEST_BYTES and len(calls)==2


@pytest.mark.parametrize("raw",[b"",b"{}",b"[{},[]]",b'[{"universe":[]},[]]',
    b'[{"universe":[{"name":"BTC","szDecimals":5,"maxLeverage":40}]},[{}]]',
    b'[{"universe":[{"name":"BTC","name":"BTC","szDecimals":5,"maxLeverage":40,"marginTableId":1}]},[{}]]'])
def test_malformed_missing_and_duplicate_provider_data_reject(raw):
    with pytest.raises(BTCPerpetualPublicEvidenceError):
        validate_btc_perpetual_public_response(payload=raw,captured_at=T,raw_relative_path="raw/f.json")


def test_numeric_prices_wrong_types_and_http_failure_reject(tmp_path):
    raw=payload();value=json.loads(raw);value[1][0]["markPx"]=110000
    with pytest.raises(BTCPerpetualPublicEvidenceError,match="string"):
        validate_btc_perpetual_public_response(payload=json.dumps(value).encode(),captured_at=T,raw_relative_path="raw/f.json")
    with pytest.raises(BTCPerpetualPublicEvidenceError,match="request failed"):
        collect_btc_perpetual_public_evidence(transport=lambda *args:(500,b"x"),output_root=tmp_path,captured_at=T)
