from datetime import datetime,timezone
from decimal import Decimal
import json
import pytest

from execution.btc_perpetual_l2_evidence_v1 import *

T=datetime(2026,9,3,tzinfo=timezone.utc);MS=int(T.timestamp()*1000)


def payload(**changes):
    value={"coin":"BTC","time":MS,"levels":[
        [{"px":"99999","sz":"0.01","n":2},{"px":"99998","sz":"0.02","n":3}],
        [{"px":"100001","sz":"0.01","n":2},{"px":"100002","sz":"0.02","n":3}]]}
    value.update(changes);return json.dumps(value,separators=(",",":")).encode()


def test_exact_depth_metrics_are_deterministic_and_unapproved():
    result=validate_btc_l2_response(payload=payload(),captured_at=T,raw_relative_path="raw/a.json")
    assert result.midpoint==Decimal("100000") and result.buy_vwap_100==Decimal("100001")
    assert result.sell_vwap_100==Decimal("99999") and result.spread_bps==Decimal("0.2")
    assert result.buy_impact_bps_100==result.sell_impact_bps_100==Decimal("0.1")
    assert result.policy_approved is result.trading_authority is False
    assert result==validate_btc_l2_response(payload=payload(),captured_at=T,raw_relative_path="raw/a.json")


def test_injected_collection_retains_bytes_and_calls_once(tmp_path):
    raw=payload();calls=[]
    result=collect_btc_l2_evidence(transport=lambda *args:(calls.append(args) or (200,raw)),output_root=tmp_path,captured_at=T)
    assert len(calls)==1 and (tmp_path/result.raw_relative_path).read_bytes()==raw


def test_raw_directory_link_redirection_rejects(tmp_path):
    outside=tmp_path/"outside";outside.mkdir()
    try:(tmp_path/"raw").symlink_to(outside,target_is_directory=True)
    except OSError:pytest.skip("directory links are unavailable")
    with pytest.raises(BTCL2EvidenceError,match="unsafe"):
        collect_btc_l2_evidence(transport=lambda *_:(200,payload()),output_root=tmp_path,captured_at=T)


@pytest.mark.parametrize("raw",[b"",b"{}",payload(coin="ETH"),payload(time=MS+1),
    payload(levels=[[],[]]),payload(levels=[[{"px":"100001","sz":"1","n":1}],[{"px":"100000","sz":"1","n":1}]])])
def test_malformed_wrong_stale_empty_and_crossed_books_reject(raw):
    with pytest.raises(BTCL2EvidenceError):validate_btc_l2_response(payload=raw,captured_at=T,raw_relative_path="raw/a.json")


def test_wrong_decimal_encoding_order_and_insufficient_depth_reject():
    value=json.loads(payload());value["levels"][0][0]["px"]=99999
    with pytest.raises(BTCL2EvidenceError,match="string"):validate_btc_l2_response(payload=json.dumps(value).encode(),captured_at=T,raw_relative_path="raw/a.json")
    value=json.loads(payload());value["levels"][0].reverse()
    with pytest.raises(BTCL2EvidenceError,match="ordered"):validate_btc_l2_response(payload=json.dumps(value).encode(),captured_at=T,raw_relative_path="raw/a.json")
    value=json.loads(payload());value["levels"][1]=[{"px":"100001","sz":"0.0001","n":1}]
    with pytest.raises(BTCL2EvidenceError,match="insufficient"):validate_btc_l2_response(payload=json.dumps(value).encode(),captured_at=T,raw_relative_path="raw/a.json")
