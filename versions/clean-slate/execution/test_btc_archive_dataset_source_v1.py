from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from backtesting.downloader import CANDLE_SCHEMA, CSV_FIELDS
from backtesting.recorder import ARCHIVE_SCHEMA
from backtesting.execution_accounting_v2.specifications import InstrumentProfile
from execution.btc_archive_dataset_source_v1 import (
    BTCArchiveDatasetError, read_btc_archive_dataset,
)


T = datetime(2026, 8, 31, 16, tzinfo=timezone.utc)
TIMEFRAMES = (("1m", 1), ("5m", 5), ("15m", 15), ("1h", 60), ("4h", 240))


def archive(root):
    checksums, streams = {}, {}
    header = ",".join(CSV_FIELDS) + "\n"
    for timeframe, minutes in TIMEFRAMES:
        start = T - timedelta(minutes=minutes * 2)
        rows = []
        for index in range(2):
            opened = start + timedelta(minutes=minutes * index)
            closed = opened + timedelta(minutes=minutes)
            rows.append(f"BTC,{timeframe},{opened.isoformat()},{closed.isoformat()},50000,51000,49000,50500,12,true\n")
        payload = (header + "".join(rows)).encode()
        name = f"BTC_{timeframe}.csv"
        (root / name).write_bytes(payload)
        checksums[name] = hashlib.sha256(payload).hexdigest()
        streams[timeframe] = {"backfill_attempts": 0, "count": 2,
            "earliest": start.isoformat(), "gap_count": 0,
            "latest_close": T.isoformat(), "stale": False}
    archive_id = hashlib.sha256((ARCHIVE_SCHEMA + "BTC" + "mainnet").encode()).hexdigest()
    manifest = {"archive_id": archive_id, "candle_schema_version": CANDLE_SCHEMA,
        "checksums": checksums, "data_network": "mainnet", "schema_version": ARCHIVE_SCHEMA,
        "source": "hyperliquid-public-mainnet", "state": "RECORDING", "streams": streams,
        "symbol": "BTC", "timeframes": [item[0] for item in TIMEFRAMES],
        "updated_at": T.isoformat()}
    (root / "archive_manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    return manifest


def read(root):
    return read_btc_archive_dataset(root, as_of=T + timedelta(seconds=10))


def test_five_streams_become_one_immutable_content_addressed_dataset(tmp_path):
    manifest = archive(tmp_path)
    result = read(tmp_path)
    assert len(result.dataset.candles) == 10
    assert {item.timeframe.value for item in result.dataset.candles} == {x[0] for x in TIMEFRAMES}
    assert result.dataset.validation_status.value == "VALID"
    assert result.archive_id == manifest["archive_id"]
    assert len(result.bundle_id) == len(result.dataset.dataset_id) == 64
    assert result.trading_authority is False
    assert result.instrument_profile is InstrumentProfile.BTC_LINEAR_PERPETUAL
    assert read(tmp_path) == result
    with pytest.raises(FrozenInstanceError):
        result.bundle_id = "x"
    with pytest.raises(BTCArchiveDatasetError, match="identity"):
        replace(result, bundle_id="a" * 64)


@pytest.mark.parametrize("mutation", ["checksum", "count", "range", "gap", "state", "inventory"])
def test_manifest_and_byte_conflicts_fail_closed(tmp_path, mutation):
    manifest = archive(tmp_path)
    if mutation == "checksum": manifest["checksums"]["BTC_5m.csv"] = "a" * 64
    elif mutation == "count": manifest["streams"]["15m"]["count"] = 3
    elif mutation == "range": manifest["streams"]["1h"]["earliest"] = T.isoformat()
    elif mutation == "gap": manifest["streams"]["4h"]["gap_count"] = 1
    elif mutation == "state": manifest["state"] = "STOPPED"
    else: del manifest["checksums"]["BTC_1m.csv"]
    (tmp_path / "archive_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BTCArchiveDatasetError): read(tmp_path)


def test_csv_lineage_gap_and_incomplete_bar_fail_closed(tmp_path):
    for old, new in ((b"BTC,5m", b"ETH,5m"), (b",true\n", b",false\n")):
        manifest = archive(tmp_path); path = tmp_path / "BTC_5m.csv"
        payload = path.read_bytes().replace(old, new, 1); path.write_bytes(payload)
        manifest["checksums"][path.name] = hashlib.sha256(payload).hexdigest()
        (tmp_path / "archive_manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(BTCArchiveDatasetError): read(tmp_path)
    manifest = archive(tmp_path); path = tmp_path / "BTC_1m.csv"
    lines = path.read_text().splitlines(keepends=True)
    payload = (lines[0] + lines[2]).encode(); path.write_bytes(payload)
    manifest["checksums"][path.name] = hashlib.sha256(payload).hexdigest()
    manifest["streams"]["1m"]["count"] = 1
    (tmp_path / "archive_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BTCArchiveDatasetError): read(tmp_path)


@pytest.mark.parametrize("marker", ["recorder_transaction.json", ".recorder_transaction"])
def test_transaction_markers_and_stale_manifest_reject(tmp_path, marker):
    archive(tmp_path); path = tmp_path / marker
    path.mkdir() if marker.startswith(".") else path.write_text("{}")
    with pytest.raises(BTCArchiveDatasetError, match="in progress"): read(tmp_path)
    if path.is_dir(): path.rmdir()
    else: path.unlink()
    with pytest.raises(BTCArchiveDatasetError, match="stale"):
        read_btc_archive_dataset(tmp_path, as_of=T + timedelta(seconds=46))
