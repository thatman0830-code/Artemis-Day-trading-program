from datetime import datetime,timedelta,timezone
import hashlib,json

import pytest

from backtesting.recorder import ARCHIVE_SCHEMA
from execution.btc_canonical_strategy_observation_v1 import (
    BTCCanonicalStrategyObservationError,BTCCanonicalStrategyObserverV1,
    observe_btc_canonical_strategy,
)

BASE=datetime(2026,9,5,6,0,tzinfo=timezone.utc)
HEADER="symbol,timeframe,open_time,close_time,open,high,low,close,volume,is_closed\n"


def rows(timeframe,count):
    minutes={"1m":1,"5m":5}[timeframe];values=[]
    for index in range(count):
        opened=BASE+timedelta(minutes=index*minutes);closed=opened+timedelta(minutes=minutes)
        values.append(f"BTC,{timeframe},{opened.isoformat().replace('+00:00','Z')},"
            f"{closed.isoformat().replace('+00:00','Z')},100,101,99,100,10,true\n")
    return (HEADER+"".join(values)).encode(),BASE+timedelta(minutes=count*minutes)


def archive(root):
    root.mkdir();streams={};checksums={};latest={}
    for timeframe,count in (("1m",15),("5m",3),("15m",1),("1h",1),("4h",1)):
        if timeframe in ("1m","5m"):payload,closed=rows(timeframe,count)
        else:payload,closed=rows("1m",1)
        name=f"BTC_{timeframe}.csv";(root/name).write_bytes(payload)
        checksums[name]=hashlib.sha256(payload).hexdigest();latest[timeframe]=closed
        streams[timeframe]={"backfill_attempts":0,"count":count,"earliest":BASE.isoformat(),
            "gap_count":0,"latest_close":closed.isoformat(),"stale":False}
    archive_id=hashlib.sha256((ARCHIVE_SCHEMA+"BTC"+"mainnet").encode()).hexdigest()
    manifest={"archive_id":archive_id,"candle_schema_version":"historical-candle-v1",
        "checksums":checksums,"data_network":"mainnet","schema_version":ARCHIVE_SCHEMA,
        "source":"hyperliquid-public-mainnet","state":"RECORDING","streams":streams,
        "symbol":"BTC","timeframes":["1m","5m","15m","1h","4h"],
        "updated_at":latest["1m"].isoformat()}
    (root/"archive_manifest.json").write_text(json.dumps(manifest,sort_keys=True))
    return latest["1m"]


def test_real_canonical_engine_produces_deterministic_read_only_observation(tmp_path):
    as_of=archive(tmp_path/"archive")
    args={"archive_root":tmp_path/"archive","snapshot_root":tmp_path/"snapshots","as_of":as_of}
    first=observe_btc_canonical_strategy(**args);second=observe_btc_canonical_strategy(**args)
    assert first==second and first.candle_count==18
    assert first.result.outcome.value in {"NO_SETUP","CANDIDATE","WAITING","REJECTED","INVALID_FAIL_CLOSED"}
    assert first.actionable is False and first.trading_authority is False
    assert len(first.observation_id)==64


def test_cross_manifest_strategy_streams_fail_closed(tmp_path,monkeypatch):
    as_of=archive(tmp_path/"archive")
    import execution.btc_canonical_strategy_observation_v1 as module
    original=module.read_btc_archive_snapshot;calls=0
    def changed(*args,**kwargs):
        nonlocal calls
        value=original(*args,**kwargs);calls+=1
        if calls==2:
            manifest_sha="f"*64
            body={"version":"btc-archive-snapshot-source-v1","reference":{
                "relative_path":value.reference.relative_path,"sha256":value.reference.sha256,
                "available_at":value.reference.available_at.isoformat()},
                "manifest_sha256":manifest_sha,"archive_id":value.archive_id,
                "latest_close":value.latest_close.isoformat(),
                "manifest_updated_at":value.manifest_updated_at.isoformat(),
                "trading_authority":False}
            snapshot_id=hashlib.sha256(json.dumps(body,sort_keys=True,
                separators=(",",":")).encode()).hexdigest()
            return value.__class__(value.reference,manifest_sha,value.archive_id,
                value.latest_close,value.manifest_updated_at,snapshot_id,False)
        return value
    monkeypatch.setattr(module,"read_btc_archive_snapshot",changed)
    with pytest.raises((BTCCanonicalStrategyObservationError,ValueError)):
        observe_btc_canonical_strategy(archive_root=tmp_path/"archive",
            snapshot_root=tmp_path/"snapshots",as_of=as_of)


def test_unchanged_content_addressed_snapshots_are_cached(tmp_path,monkeypatch):
    as_of=archive(tmp_path/"archive")
    observer=BTCCanonicalStrategyObserverV1(archive_root=tmp_path/"archive",
        snapshot_root=tmp_path/"snapshots")
    first=observer.observe(as_of=as_of)
    import execution.btc_canonical_strategy_observation_v1 as module
    monkeypatch.setattr(module,"_observe_snapshots",lambda **_:(_ for _ in ()).throw(
        AssertionError("unchanged snapshots must not replay")))
    assert observer.observe(as_of=as_of)==first


def test_observer_has_no_order_or_network_surface():
    source=__import__("inspect").getsource(
        __import__("execution.btc_canonical_strategy_observation_v1",fromlist=["*"])) .lower()
    for prohibited in ("requests","urllib","websocket","private_key","place_order","submit_order"):
        assert prohibited not in source
    assert "trading_authority: bool=false" in source
