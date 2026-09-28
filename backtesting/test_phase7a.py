import ast
import json
import urllib.error
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.__main__ import main
from backtesting.downloader import DownloadRequest, HistoricalCandleDownloader
from backtesting.file_runner import load_inputs
from backtesting.market_data import CanonicalTimeframe, GapPolicy


UTC=timezone.utc
START=datetime(2026,8,20,tzinfo=UTC)


class FakeTransport:
    def __init__(self, *, fail=0, malformed=None, duplicate=False, omit=None, inclusive_close=False, inclusive_end=False):
        self.calls=[]; self.fail=fail; self.malformed=malformed; self.duplicate=duplicate; self.omit=omit; self.inclusive_close=inclusive_close; self.inclusive_end=inclusive_end
    def post(self, *, url, payload, timeout):
        request=json.loads(payload); self.calls.append((url,request,timeout))
        if self.fail:
            self.fail-=1; raise urllib.error.HTTPError(url,429,"rate",{},None)
        if self.malformed is not None: return json.dumps(self.malformed).encode()
        req=request["req"]; duration={"1m":60000,"5m":300000,"15m":900000,
            "1h":3600000,"4h":14400000}[req["interval"]]
        rows=[]; cursor=req["startTime"]
        while cursor+duration<=req["endTime"]:
            if cursor != self.omit:
                row={"t":cursor,"T":cursor+duration-(1 if self.inclusive_close else 0),"s":req["coin"],"i":req["interval"],
                     "o":"100.00","h":"101.00","l":"99.00","c":"100.50","v":"10.00"}
                rows.append(row)
            cursor+=duration
        if self.inclusive_end:
            rows.append({"t":req["endTime"],"T":req["endTime"]+duration-1,
                         "s":req["coin"],"i":req["interval"],"o":"100.00",
                         "h":"101.00","l":"99.00","c":"100.50","v":"10.00"})
        if self.duplicate and rows: rows.append(dict(rows[0]))
        return json.dumps(rows).encode()


def request(tmp_path, **changes):
    base=dict(symbol="BTC",timeframes=(CanonicalTimeframe.M1,),start=START,
        end=START+timedelta(minutes=5),data_network="testnet",output=tmp_path/"dataset",
        gap_policy=GapPolicy.REJECT,window_candles=2)
    base.update(changes); return DownloadRequest(**base)


def test_successful_multiwindow_multitimeframe_is_deterministic_and_phase6_compatible(tmp_path):
    transport=FakeTransport(); downloader=HistoricalCandleDownloader(transport=transport,now=lambda:START+timedelta(days=1))
    req=request(tmp_path,timeframes=(CanonicalTimeframe.M1,CanonicalTimeframe.M5))
    manifest_path=downloader.download(req,progress=lambda _:None)
    manifest=json.loads(manifest_path.read_text())
    assert [x["timeframe"] for x in manifest["files"]]==["1m","5m"]
    assert len(transport.calls)==4 and manifest["data_network"]=="testnet"
    assert manifest["checksums"] and manifest["dataset_fingerprint"]
    # Phase 6 loader accepts the produced manifest directly.
    example=Path(__file__).parents[1]/"examples"/"backtesting"/"backtest_config.json"
    dataset,_,_=load_inputs(manifest_path,example)
    assert dataset.fingerprint==manifest["dataset_fingerprint"]


def test_forming_candle_is_excluded_and_recorded(tmp_path):
    now=START+timedelta(minutes=3)
    path=HistoricalCandleDownloader(transport=FakeTransport(),now=lambda:now).download(
        request(tmp_path,gap_policy=GapPolicy.RECORD),progress=lambda _:None)
    manifest=json.loads(path.read_text())
    rows=(path.parent/"BTC_1m.csv").read_text().splitlines()
    assert len(rows)==4 and manifest["approved_exclusions"]


def test_rate_limit_retries_are_bounded_with_exponential_backoff(tmp_path):
    transport=FakeTransport(fail=2); sleeps=[]
    HistoricalCandleDownloader(transport=transport,sleeper=sleeps.append,now=lambda:START+timedelta(days=1)).download(
        request(tmp_path,retry_limit=2),progress=lambda _:None)
    assert sleeps[:2]==[1,2]
    failing=FakeTransport(fail=4)
    with pytest.raises(urllib.error.HTTPError):
        HistoricalCandleDownloader(transport=failing,sleeper=lambda _:None,now=lambda:START+timedelta(days=1)).download(
            request(tmp_path,output=tmp_path/"failed",retry_limit=1),progress=lambda _:None)
    assert len(failing.calls)==2


@pytest.mark.parametrize("response", [{"error":"bad"}, [{"t":1}]])
def test_malformed_or_permanent_response_fails_closed(tmp_path,response):
    with pytest.raises(ValueError,match="malformed"):
        HistoricalCandleDownloader(transport=FakeTransport(malformed=response),now=lambda:START+timedelta(days=1)).download(
            request(tmp_path),progress=lambda _:None)


def test_duplicates_and_gaps_are_detected_without_synthesis(tmp_path):
    with pytest.raises(ValueError,match="duplicate"):
        HistoricalCandleDownloader(transport=FakeTransport(duplicate=True),now=lambda:START+timedelta(days=1)).download(
            request(tmp_path),progress=lambda _:None)
    omitted=int((START+timedelta(minutes=2)).timestamp()*1000)
    with pytest.raises(ValueError,match="gaps"):
        HistoricalCandleDownloader(transport=FakeTransport(omit=omitted),now=lambda:START+timedelta(days=1)).download(
            request(tmp_path,output=tmp_path/"gap"),progress=lambda _:None)


def test_interrupted_resume_verifies_partial_and_requests_only_missing_windows(tmp_path):
    class Interrupt(FakeTransport):
        def post(self,**kwargs):
            if len(self.calls)==1: raise TimeoutError("interrupted")
            return super().post(**kwargs)
    first=Interrupt()
    with pytest.raises(TimeoutError):
        HistoricalCandleDownloader(transport=first,sleeper=lambda _:None,now=lambda:START+timedelta(days=1)).download(
            request(tmp_path,retry_limit=0),progress=lambda _:None)
    # Nothing was committed as a complete dataset; verified partial state remains.
    assert not (tmp_path/"dataset").exists() and (tmp_path/"dataset.partial").exists()
    resumed=FakeTransport()
    manifest=HistoricalCandleDownloader(transport=resumed,now=lambda:START+timedelta(days=1)).download(
        request(tmp_path,resume=True),progress=lambda _:None)
    assert manifest.exists()
    partial=tmp_path/"corrupt.partial"; partial.mkdir(); (partial/"partial_manifest.json").write_text("{}")
    with pytest.raises(ValueError,match="incompatible"):
        HistoricalCandleDownloader(transport=FakeTransport(),now=lambda:START+timedelta(days=1)).download(
            request(tmp_path,output=tmp_path/"corrupt",resume=True),progress=lambda _:None)


def test_existing_output_overwrite_and_cli_data_network_semantics(tmp_path,capsys):
    downloader=HistoricalCandleDownloader(transport=FakeTransport(),now=lambda:START+timedelta(days=1))
    req=request(tmp_path); downloader.download(req,progress=lambda _:None)
    with pytest.raises(FileExistsError): downloader.download(req,progress=lambda _:None)
    downloader.download(request(tmp_path,overwrite=True),progress=lambda _:None)
    help_text=__import__("backtesting.__main__",fromlist=["parser"]).parser().format_help()
    assert "download" in help_text


def test_downloader_has_no_order_wallet_or_secret_code_imports_and_preserves_decimal(tmp_path):
    module=Path(__file__).parent/"downloader.py"; tree=ast.parse(module.read_text())
    imports={node.module or "" for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
    imports|={alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names}
    forbidden=("exchange","eth_account","wallet","signing","private_key")
    assert not any(any(word in name.lower() for word in forbidden) for name in imports)
    path=HistoricalCandleDownloader(transport=FakeTransport(),now=lambda:START+timedelta(days=1)).download(
        request(tmp_path),progress=lambda _:None)
    assert "100.00" in (path.parent/"BTC_1m.csv").read_text()


def test_hyperliquid_inclusive_final_millisecond_normalizes_to_exclusive_close(tmp_path):
    path=HistoricalCandleDownloader(
        transport=FakeTransport(inclusive_close=True),
        now=lambda:START+timedelta(days=1),
    ).download(request(tmp_path),progress=lambda _:None)
    rows=(path.parent/"BTC_1m.csv").read_text().splitlines()
    assert rows[1].split(",")[3] == "2026-08-20T00:01:00.000Z"


def test_empty_leading_boundary_cannot_be_silently_accepted(tmp_path):
    with pytest.raises(ValueError, match="boundary coverage incomplete"):
        HistoricalCandleDownloader(
            transport=FakeTransport(malformed=[]),
            now=lambda:START+timedelta(days=1),
        ).download(request(tmp_path),progress=lambda _:None)


def test_endpoint_inclusive_end_candle_is_reserved_for_next_window(tmp_path):
    path=HistoricalCandleDownloader(
        transport=FakeTransport(inclusive_end=True),
        now=lambda:START+timedelta(days=1),
    ).download(request(tmp_path),progress=lambda _:None)
    assert len((path.parent/"BTC_1m.csv").read_text().splitlines()) == 6


@pytest.mark.parametrize("timeframe",(
    CanonicalTimeframe.M1,CanonicalTimeframe.M5,CanonicalTimeframe.M15,
    CanonicalTimeframe.H1,CanonicalTimeframe.H4,
))
def test_downloader_unaligned_visibility_cutoff_excludes_forming_candle_for_all_streams(
        tmp_path,timeframe):
    end=START+timedelta(hours=8); now=START+timedelta(hours=4,seconds=37)
    req=request(tmp_path,output=tmp_path/timeframe.value,timeframes=(timeframe,),
                start=START,end=end,window_candles=1000,gap_policy=GapPolicy.RECORD)
    path=HistoricalCandleDownloader(transport=FakeTransport(),now=lambda:now).download(
        req,progress=lambda _:None)
    rows=(path.parent/f"BTC_{timeframe.value}.csv").read_text().splitlines()
    expected=int((now-START)//timeframe.duration)
    assert len(rows)==expected+1
    manifest=json.loads(path.read_text())
    assert manifest["approved_exclusions"] and manifest["validation_time"].endswith("Z")
