from dataclasses import replace
from datetime import timedelta
import hashlib
import json

import pytest

from backtesting.recorder import ARCHIVE_SCHEMA
from execution.btc_archive_snapshot_source_v1 import (
    BTCArchiveSnapshotError, read_btc_archive_snapshot,
)
from execution.test_paper_closed_bar_input_v1 import HEADER, row
from execution.test_paper_performance_ledger_v1 import T


def archive(tmp_path):
    payload = (HEADER + row(-1)).encode(); filename = "BTC_1m.csv"
    (tmp_path / filename).write_bytes(payload)
    archive_id = hashlib.sha256((ARCHIVE_SCHEMA + "BTC" + "mainnet").encode()).hexdigest()
    streams = {}
    checksums = {}
    for timeframe in ("1m","5m","15m","1h","4h"):
        name = f"BTC_{timeframe}.csv"
        if timeframe != "1m":
            (tmp_path / name).write_bytes(payload)
        checksums[name] = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        streams[timeframe] = {"backfill_attempts":0,"count":1,"earliest":T.isoformat(),
            "gap_count":0,"latest_close":T.isoformat(),"stale":False}
    manifest = {"archive_id":archive_id,"candle_schema_version":"historical-candle-v1",
        "checksums":checksums,"data_network":"mainnet","schema_version":ARCHIVE_SCHEMA,
        "source":"hyperliquid-public-mainnet","state":"RECORDING","streams":streams,
        "symbol":"BTC","timeframes":["1m","5m","15m","1h","4h"],
        "updated_at":T.isoformat()}
    (tmp_path / "archive_manifest.json").write_text(json.dumps(manifest,sort_keys=True))
    return manifest, payload


def test_current_transaction_safe_manifest_yields_content_addressed_reference(tmp_path):
    manifest, payload = archive(tmp_path)
    result = read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T+timedelta(seconds=10))
    assert result.reference.relative_path == "BTC_1m.csv"
    assert result.reference.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.reference.available_at == T and result.latest_close == T
    assert result.archive_id == manifest["archive_id"] and len(result.snapshot_id) == 64
    assert result.trading_authority is False
    with pytest.raises(BTCArchiveSnapshotError,match="identity"):
        replace(result,snapshot_id="a"*64)


@pytest.mark.parametrize("change", [
    {"state":"STOPPED"},{"symbol":"ES"},{"data_network":"testnet"},
    {"source":"other"},{"schema_version":"other"},{"archive_id":"a"*64},
    {"timeframes":["1m"]},
])
def test_manifest_identity_and_state_fail_closed(tmp_path,change):
    manifest,_=archive(tmp_path);manifest.update(change)
    (tmp_path/"archive_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BTCArchiveSnapshotError):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T)


@pytest.mark.parametrize("field,value", [
    ("gap_count",1),("stale",True),("count",0),("latest_close","bad")])
def test_unhealthy_or_invalid_stream_rejects(tmp_path,field,value):
    manifest,_=archive(tmp_path);manifest["streams"]["1m"][field]=value
    (tmp_path/"archive_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BTCArchiveSnapshotError):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T)


def test_stale_future_checksum_and_extra_fields_reject(tmp_path):
    manifest,_=archive(tmp_path)
    with pytest.raises(BTCArchiveSnapshotError,match="stale"):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T+timedelta(seconds=46))
    manifest["updated_at"]=(T+timedelta(seconds=1)).isoformat()
    (tmp_path/"archive_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BTCArchiveSnapshotError,match="future"):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T)
    manifest["updated_at"]=T.isoformat();manifest["checksums"]["BTC_1m.csv"]="a"*64
    (tmp_path/"archive_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BTCArchiveSnapshotError,match="checksum"):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T)
    manifest,_=archive(tmp_path);manifest["unexpected"]=True
    (tmp_path/"archive_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BTCArchiveSnapshotError,match="identity"):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T)


@pytest.mark.parametrize("marker",["recorder_transaction.json",".recorder_transaction"])
def test_in_progress_recorder_transaction_rejects(tmp_path,marker):
    archive(tmp_path);path=tmp_path/marker
    path.mkdir() if marker.startswith(".") else path.write_text("{}")
    with pytest.raises(BTCArchiveSnapshotError,match="in progress"):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T)


def test_manifest_race_is_detected(tmp_path,monkeypatch):
    archive(tmp_path)
    original = type(tmp_path).read_bytes; calls=0
    def changed(path):
        nonlocal calls
        value=original(path)
        if path.name=="archive_manifest.json":
            calls+=1
            if calls==2:return value+b" "
        return value
    monkeypatch.setattr(type(tmp_path),"read_bytes",changed)
    with pytest.raises(BTCArchiveSnapshotError,match="changed"):
        read_btc_archive_snapshot(tmp_path,timeframe="1m",as_of=T)


@pytest.mark.parametrize("timeframe",["1h","4h","ES"])
def test_only_supported_paper_timeframes(timeframe,tmp_path):
    archive(tmp_path)
    with pytest.raises(BTCArchiveSnapshotError,match="unsupported"):
        read_btc_archive_snapshot(tmp_path,timeframe=timeframe,as_of=T)


def test_five_minute_strategy_stream_is_supported(tmp_path):
    manifest,_=archive(tmp_path)
    result=read_btc_archive_snapshot(tmp_path,timeframe="5m",as_of=T)
    assert result.reference.relative_path=="BTC_5m.csv"
    assert result.manifest_sha256==hashlib.sha256(
        (tmp_path/"archive_manifest.json").read_bytes()).hexdigest()
