from datetime import datetime,timedelta,timezone
import json
import pytest

from execution.btc_perpetual_l2_aggregate_v1 import *
from execution.btc_perpetual_l2_evidence_v1 import collect_btc_l2_evidence


def _payload(at,index=0):
    middle=100000+index;millis=int(at.timestamp()*1000)
    return json.dumps({"coin":"BTC","time":millis,"levels":[
        [{"px":str(middle-1),"sz":"0.01","n":2},{"px":str(middle-2),"sz":"0.02","n":3}],
        [{"px":str(middle+1),"sz":"0.01","n":2},{"px":str(middle+2),"sz":"0.02","n":3}]]},separators=(",",":")).encode()


def _retain(root,at,index=0):
    raw=_payload(at,index)
    result=collect_btc_l2_evidence(transport=lambda *_:(200,raw),output_root=root,captured_at=at)
    return root/f"{result.receipt_id}.receipt.json"


def test_verified_aggregate_is_deterministic_and_never_approves_policy(tmp_path):
    start=datetime(2026,9,3,tzinfo=timezone.utc)
    paths=[_retain(tmp_path,start+timedelta(minutes=20*i),i) for i in range(24)]
    first=aggregate_verified_receipts(root=tmp_path,receipt_paths=reversed(paths))
    second=aggregate_verified_receipts(root=tmp_path,receipt_paths=paths)
    assert first==second and first.evidence_sufficient and first.hour_bucket_count>=4
    assert first.policy_approved is first.trading_authority is False
    assert first.p95_spread_bps<=first.maximum_spread_bps


def test_short_or_concentrated_sample_remains_insufficient(tmp_path):
    start=datetime(2026,9,3,tzinfo=timezone.utc)
    paths=[_retain(tmp_path,start+timedelta(minutes=i),i) for i in range(3)]
    result=aggregate_verified_receipts(root=tmp_path,receipt_paths=paths)
    assert result.evidence_sufficient is False


def test_tampered_raw_or_receipt_rejects(tmp_path):
    at=datetime(2026,9,3,tzinfo=timezone.utc);path=_retain(tmp_path,at)
    document=json.loads(path.read_text());raw=tmp_path/document["raw_relative_path"]
    raw.write_bytes(raw.read_bytes()+b" ")
    with pytest.raises(BTCL2AggregateError,match="validation|match"):
        aggregate_verified_receipts(root=tmp_path,receipt_paths=[path])


def test_duplicate_receipt_rejects(tmp_path):
    path=_retain(tmp_path,datetime(2026,9,3,tzinfo=timezone.utc))
    with pytest.raises(BTCL2AggregateError,match="duplicate receipt"):
        aggregate_verified_receipts(root=tmp_path,receipt_paths=[path,path])


def test_receipt_outside_root_rejects(tmp_path):
    root=tmp_path/"root";root.mkdir();outside=tmp_path/"outside";outside.mkdir()
    path=_retain(outside,datetime(2026,9,3,tzinfo=timezone.utc))
    with pytest.raises(BTCL2AggregateError,match="escapes"):
        aggregate_verified_receipts(root=root,receipt_paths=[path])
