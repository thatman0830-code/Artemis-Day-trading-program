from __future__ import annotations

import ast
import json
import os
import shutil
import ssl
import subprocess
import urllib.error
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtesting.file_runner import load_inputs
from backtesting.coverage import (
    RecentCoverageProbe, StreamCoverage, select_diagnostic_interval,
)
from backtesting.market_data import CanonicalTimeframe
from backtesting.recorder import (
    ArchiveState, ForwardCandleRecorder, JsonLineEventSink,
    RecorderConfiguration, RecorderEvent, freeze_snapshot,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 23, 6, tzinfo=UTC)


class RecentTransport:
    def __init__(self, *, omit=None, conflict=False, fail=0):
        self.omit=omit; self.conflict=conflict; self.fail=fail; self.calls=[]
    def post(self, *, url, payload, timeout):
        if self.fail:
            self.fail-=1; raise OSError("temporary")
        req=json.loads(payload)["req"]; self.calls.append(req)
        duration={"1m":60000,"5m":300000}[req["interval"]]
        start=max(req["startTime"],req["endTime"]-5*duration)
        rows=[]
        for opened in range(start,req["endTime"]+1,duration):
            if opened==self.omit: continue
            close="101.5" if self.conflict and opened==start else "100.5"
            rows.append({"t":opened,"T":opened+duration-1,"s":req["coin"],
                "i":req["interval"],"o":"100","h":"102","l":"99",
                "c":close,"v":"10"})
        return json.dumps(rows).encode()


def config(tmp_path, **changes):
    values=dict(symbol="BTC",timeframes=(CanonicalTimeframe.M1,),
        data_network="testnet",output=tmp_path/"archive",poll_seconds=0,
        bootstrap_candles=5)
    values.update(changes); return RecorderConfiguration(**values)


def test_rest_bootstrap_closed_only_decimal_atomic_and_resume_deduplicates(tmp_path):
    transport=RecentTransport(); recorder=ForwardCandleRecorder(
        configuration=config(tmp_path),transport=transport,now=lambda:NOW,sleeper=lambda _:None)
    first=recorder.poll_once()
    assert first["state"]==ArchiveState.RECORDING.value
    assert first["trading_authority"] is False and first["paper_only"] is True
    assert first["account_access"] is False and first["order_endpoints_present"] is False
    assert first["streams"]["1m"]["count"]==5
    csv_path=tmp_path/"archive"/"BTC_1m.csv"
    assert "100.5" in csv_path.read_text() and not list(csv_path.parent.glob("*.tmp"))
    second=recorder.poll_once()
    assert second["streams"]["1m"]["count"]==5
    assert len(csv_path.read_text().splitlines())==6


def test_gap_stale_retry_and_conflicting_resume_fail_closed(tmp_path):
    missing=int((NOW-timedelta(minutes=3)).timestamp()*1000)
    gapped=ForwardCandleRecorder(configuration=config(tmp_path),
        transport=RecentTransport(omit=missing),now=lambda:NOW,sleeper=lambda _:None)
    assert gapped.poll_once()["state"]==ArchiveState.GAPPED.value
    archive=tmp_path/"archive"; manifest=json.loads((archive/"archive_manifest.json").read_text())
    (archive/"BTC_1m.csv").write_text("corrupt",encoding="utf-8")
    with pytest.raises(ValueError,match="checksum"):
        gapped.poll_once()
    other=tmp_path/"retry"
    retry=ForwardCandleRecorder(configuration=config(tmp_path,output=other),
        transport=RecentTransport(fail=2),now=lambda:NOW,sleeper=lambda _:None)
    retry.poll_once()


class FailureSequenceTransport:
    def __init__(self, failures, fallback=None):
        self.failures=list(failures); self.fallback=fallback or RecentTransport(); self.calls=0
    def post(self, **kwargs):
        self.calls += 1
        if self.failures: raise self.failures.pop(0)
        return self.fallback.post(**kwargs)


def test_dns_tls_timeout_and_transient_http_reconnect_with_bounded_jitter(tmp_path):
    transient = [urllib.error.URLError("dns"), ssl.SSLError("tls"),
                 TimeoutError("timeout"), urllib.error.HTTPError(
                     "https://public.invalid", 503, "unavailable", {}, None)]
    transport=FailureSequenceTransport(transient)
    delays=[]; events=[]
    recorder=ForwardCandleRecorder(configuration=replace(config(tmp_path),retry_limit=4,
        retry_base_seconds=2,retry_max_seconds=5,retry_jitter_fraction=.25),
        transport=transport,now=lambda:NOW,sleeper=delays.append,jitter=lambda:.5,
        event_sink=events.append)
    assert recorder.poll_once()["state"]==ArchiveState.RECORDING.value
    assert delays==[2,4,5,5] and transport.calls==5
    assert [event.event for event in events].count("request_retry")==4
    assert all(dict(event.details)["error_type"] in
        {"URLError","SSLError","TimeoutError","HTTPError"} for event in events
        if event.event=="request_retry")


def test_permanent_http_and_malformed_payload_are_not_retried(tmp_path):
    permanent=FailureSequenceTransport([urllib.error.HTTPError(
        "https://public.invalid",400,"bad request",{},None)])
    recorder=ForwardCandleRecorder(configuration=config(tmp_path),transport=permanent,
        now=lambda:NOW,sleeper=lambda _:pytest.fail("permanent HTTP was retried"))
    with pytest.raises(urllib.error.HTTPError): recorder.poll_once()
    assert permanent.calls==1
    malformed=FailureSequenceTransport([],fallback=type("Malformed",(),{
        "post":lambda self,**kwargs:b'{"unexpected":true}'})())
    recorder=ForwardCandleRecorder(configuration=config(tmp_path,output=tmp_path/"bad"),
        transport=malformed,now=lambda:NOW,
        sleeper=lambda _:pytest.fail("validation error was retried"))
    with pytest.raises(ValueError,match="malformed"): recorder.poll_once()
    assert malformed.calls==1


def test_run_recovers_across_poll_failures_marks_stale_and_alerts(tmp_path):
    transport=FailureSequenceTransport([OSError("dns"),OSError("tls"),OSError("timeout")])
    events=[]; alerts=[]
    recorder=ForwardCandleRecorder(configuration=replace(config(tmp_path),retry_limit=0,
        cycle_failure_limit=2),transport=transport,now=lambda:NOW,sleeper=lambda _:None,
        jitter=lambda:.5,event_sink=events.append,alert_hook=alerts.append)
    result=recorder.run(max_cycles=4)
    assert result["state"]==ArchiveState.RECORDING.value and transport.calls==4
    assert any(event.event=="poll_reconnect" for event in events)
    assert any(event.state==ArchiveState.STALE.value for event in alerts)


class HealingGapTransport(RecentTransport):
    def post(self, *, url, payload, timeout):
        req=json.loads(payload)["req"]
        duration={"1m":60000}[req["interval"]]
        # Omit one row from the broad poll, but return it when the recorder
        # explicitly requests the detected missing window.
        self.omit = (req["startTime"] + 2*duration
                     if req["endTime"]-req["startTime"] > duration else None)
        return super().post(url=url,payload=payload,timeout=timeout)


def test_detected_gap_is_backfilled_without_synthesis(tmp_path):
    events=[]
    recorder=ForwardCandleRecorder(configuration=config(tmp_path),
        transport=HealingGapTransport(),now=lambda:NOW,sleeper=lambda _:None,
        event_sink=events.append)
    result=recorder.poll_once()
    assert result["state"]==ArchiveState.RECORDING.value
    assert result["streams"]["1m"]["gap_count"]==0
    assert result["streams"]["1m"]["backfill_attempts"]==1
    assert any(event.event=="gap_backfill_attempt" for event in events)
    assert len((tmp_path/"archive"/"BTC_1m.csv").read_text().splitlines())==6


class InclusivePollingTransport:
    def __init__(self, *, future_offset=0, malformed_boundary=False):
        self.future_offset=future_offset; self.malformed_boundary=malformed_boundary
    def post(self, *, url, payload, timeout):
        req=json.loads(payload)["req"]
        duration={"1m":60_000,"5m":300_000,"15m":900_000,
                  "1h":3_600_000,"4h":14_400_000}[req["interval"]]
        boundary=(req["endTime"]//duration)*duration
        if self.malformed_boundary:
            return json.dumps([{"t":req["endTime"]}]).encode()
        forming=boundary+self.future_offset*duration
        rows=[{"t":boundary-duration,"T":boundary-1,"s":req["coin"],
               "i":req["interval"],"o":"100","h":"102","l":"99",
               "c":"100.5","v":"10"},
              {"t":forming,"T":forming+duration-1,"s":req["coin"],
               "i":req["interval"],"o":"100","h":"102","l":"99",
               "c":"100.5","v":"10"}]
        return json.dumps(rows).encode()


@pytest.mark.parametrize("timeframe",(
    CanonicalTimeframe.M1,CanonicalTimeframe.M5,CanonicalTimeframe.M15,
    CanonicalTimeframe.H1,CanonicalTimeframe.H4,
))
def test_inclusive_end_forming_candle_is_excluded_after_full_validation_for_every_stream(
        tmp_path,timeframe):
    observed_end=NOW+timedelta(seconds=37,microseconds=186000)
    events=[]
    recorder=ForwardCandleRecorder(configuration=replace(config(tmp_path),
        timeframes=(timeframe,)),transport=InclusivePollingTransport(),
        now=lambda:observed_end,sleeper=lambda _:None,event_sink=events.append)
    result=recorder.poll_once()
    assert result["state"]==ArchiveState.RECORDING.value
    assert result["streams"][timeframe.value]["count"]==1
    assert any(event.event=="forming_candle_excluded"
               and event.timeframe==timeframe.value for event in events)
    rows=(tmp_path/"archive"/f"BTC_{timeframe.value}.csv").read_text().splitlines()
    assert len(rows)==2 and rows[1].endswith(",true")


def test_only_the_precise_inclusive_forming_boundary_is_excluded(tmp_path):
    observed_end=NOW+timedelta(seconds=37)
    events=[]
    recorder=ForwardCandleRecorder(configuration=config(tmp_path),
        transport=InclusivePollingTransport(future_offset=1),
        now=lambda:observed_end,sleeper=lambda _:None,event_sink=events.append)
    with pytest.raises(ValueError,match="outside requested recorder window"):
        recorder.poll_once()
    rejected=next(event for event in events if event.event=="response_boundary_rejected")
    assert set(dict(rejected.details)) >= {"requested_start","requested_end",
                                          "open_time","close_time"}
    malformed=ForwardCandleRecorder(configuration=config(tmp_path,output=tmp_path/"bad-boundary"),
        transport=InclusivePollingTransport(malformed_boundary=True),
        now=lambda:observed_end,sleeper=lambda _:None)
    with pytest.raises(ValueError,match="malformed public candle fields"):
        malformed.poll_once()


def test_partial_multi_stream_commit_is_completed_from_checksum_transaction(tmp_path,monkeypatch):
    cfg=replace(config(tmp_path),timeframes=(CanonicalTimeframe.M1,CanonicalTimeframe.M5))
    recorder=ForwardCandleRecorder(configuration=cfg,transport=RecentTransport(),
        now=lambda:NOW,sleeper=lambda _:None)
    original=ForwardCandleRecorder._atomic_bytes; replaced=[]
    def crash_after_first_target(path,payload):
        original(path,payload)
        if path.parent==cfg.output and path.suffix==".csv":
            replaced.append(path.name)
            if len(replaced)==1: raise OSError("simulated power loss")
    monkeypatch.setattr(ForwardCandleRecorder,"_atomic_bytes",staticmethod(crash_after_first_target))
    with pytest.raises(OSError,match="power loss"): recorder.poll_once()
    assert recorder.transaction_path.is_file()
    monkeypatch.setattr(ForwardCandleRecorder,"_atomic_bytes",staticmethod(original))
    recovered=ForwardCandleRecorder(configuration=cfg,transport=RecentTransport(),
        now=lambda:NOW,sleeper=lambda _:None)
    result=recovered.poll_once()
    assert result["state"]==ArchiveState.RECORDING.value
    assert not recovered.transaction_path.exists() and not recovered.transaction_directory.exists()
    assert set(result["checksums"])=={"BTC_1m.csv","BTC_5m.csv"}
    recovered._load_manifest()


def test_staleness_structured_logs_and_unexpected_stop_alert_are_secret_free(tmp_path):
    log=tmp_path/"logs"/"events.jsonl"; alert=tmp_path/"logs"/"alerts.jsonl"
    stale_now=NOW+timedelta(hours=1)
    recorder=ForwardCandleRecorder(configuration=config(tmp_path),
        transport=RecentTransport(),now=lambda:stale_now,sleeper=lambda _:None,
        event_sink=JsonLineEventSink(log),alert_hook=JsonLineEventSink(alert))
    result=recorder.poll_once()
    # RecentTransport responds relative to the requested end, so force a
    # deterministic empty stream to exercise explicit stale health separately.
    assert result["state"]==ArchiveState.RECORDING.value
    class Empty:
        def post(self,**kwargs): return b"[]"
    failed=ForwardCandleRecorder(configuration=config(tmp_path,output=tmp_path/"empty"),
        transport=Empty(),now=lambda:NOW,sleeper=lambda _:None,
        event_sink=JsonLineEventSink(log),alert_hook=JsonLineEventSink(alert))
    assert failed.poll_once()["state"]==ArchiveState.STALE.value
    class Invalid:
        def post(self,**kwargs): return b"{}"
    stopped=ForwardCandleRecorder(configuration=config(tmp_path,output=tmp_path/"invalid"),
        transport=Invalid(),now=lambda:NOW,sleeper=lambda _:None,
        event_sink=JsonLineEventSink(log),alert_hook=JsonLineEventSink(alert))
    with pytest.raises(ValueError): stopped.run(max_cycles=1)
    decoded=[json.loads(line) for line in alert.read_text().splitlines()]
    assert {item["state"] for item in decoded} >= {"STALE","STOPPED"}
    text=log.read_text()+alert.read_text()
    assert "secret" not in text.lower() and "private" not in text.lower()
    assert all(set(item)=={"timestamp","level","event","state","symbol","timeframe","details"}
               for item in decoded)


def test_graceful_interrupt_marks_stopped(tmp_path):
    recorder=ForwardCandleRecorder(configuration=config(tmp_path),
        transport=RecentTransport(),now=lambda:NOW,
        sleeper=lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    result=recorder.run()
    assert result["state"]==ArchiveState.STOPPED.value


def test_snapshot_is_immutable_phase6_compatible_and_refuses_incomplete(tmp_path):
    recorder=ForwardCandleRecorder(configuration=config(tmp_path),
        transport=RecentTransport(),now=lambda:NOW,sleeper=lambda _:None)
    recorder.poll_once()
    output=tmp_path/"snapshot"
    manifest=freeze_snapshot(archive=tmp_path/"archive",output=output,
        start=NOW-timedelta(minutes=5),end=NOW)
    raw=json.loads(manifest.read_text())
    assert raw["schema_version"]=="backtesting-data-manifest-v1"
    example=Path(__file__).parents[1]/"examples"/"backtesting"/"backtest_config.json"
    cfg=json.loads(example.read_text()); cfg["replay_start_inclusive"]="2026-08-23T05:55:00Z"
    cfg["replay_end_exclusive"]="2026-08-23T06:00:00Z"
    cfg_path=tmp_path/"config.json"; cfg_path.write_text(json.dumps(cfg))
    dataset,_,_=load_inputs(manifest,cfg_path)
    assert len(dataset.candles)==5
    with pytest.raises((FileExistsError,ValueError)):
        freeze_snapshot(archive=tmp_path/"archive",output=output,
            start=NOW-timedelta(minutes=4),end=NOW)


def test_recorder_imports_no_exchange_wallet_signing_or_strategy(tmp_path):
    module=Path(__file__).parent/"recorder.py"; tree=ast.parse(module.read_text())
    imports={node.module or "" for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
    forbidden=("exchange","wallet","signing","private_key","strategy")
    assert not any(any(value in name.lower() for value in forbidden) for name in imports)
    script=(Path(__file__).parents[1]/"scripts"/"record_backtest_data.ps1").read_text()
    assert "-m','backtesting','record'" in script and "$LASTEXITCODE" in script
    supervisor=(Path(__file__).parents[1]/"scripts"/"supervise_backtest_recorder.ps1").read_text()
    assert "MaximumRestarts" in supervisor and "restart_budget_exhausted" in supervisor
    assert "healthyRuntimeSeconds -ge 300" in supervisor and "restart_budget_recovered" in supervisor
    assert "-m','backtesting','record'" in supervisor
    assert "IsPathRooted" in supervisor and "Join-Path $repo $Value" in supervisor
    assert supervisor.index("$archivePath = Resolve-RepositoryPath") < supervisor.index("& $python @arguments")
    forbidden_text=("scheduledtask","new-service","exchange","wallet","private_key",
                    "signing","order submission")
    assert not any(value in supervisor.lower() for value in forbidden_text)


def test_btc_logon_task_is_research_only_single_instance_and_health_checked():
    root=Path(__file__).parents[1]
    runner=(root/"scripts"/"run_btc_forward_recorder_task.ps1").read_text()
    installer=(root/"scripts"/"install_btc_forward_recorder_task.ps1").read_text()
    enabler=(root/"scripts"/"enable_btc_forward_recorder_task.ps1").read_text()
    verifier=(root/"scripts"/"start_and_verify_btc_forward_recorder_task.ps1").read_text()
    status=(root/"scripts"/"get_btc_forward_recorder_status.ps1").read_text()
    supervisor=(root/"scripts"/"supervise_backtest_recorder.ps1").read_text()
    assert "SingleInstanceName" in supervisor and "Threading.Mutex" in supervisor
    assert "Local\\HyperliquidTradingBot-BTC-Forward-Recorder" in runner
    assert "-AtLogOn" in installer and "IgnoreNew" in installer
    assert "Interactive" in installer and "RunLevel Limited" in installer
    assert "Disable-ScheduledTask" in installer and "Start-ScheduledTask" not in installer
    assert "Enable-ScheduledTask" in enabler and "Start-ScheduledTask" not in enabler
    assert "poll_complete" in verifier and "RECORDING" in verifier
    assert "EventAgeSeconds" in status and "LatestCompletedPollUtc" in status
    assert "UNKNOWN_OR_NOT_VISIBLE" in status and "TaskVisibilityVerified" in status
    assert "'NOT_INSTALLED'" not in status
    assert "Trading = $false" in status and "-Tail 30" in status
    combined=(runner+installer+enabler+verifier+status).lower()
    forbidden=("private_key","wallet","signing","order submission","exchange client")
    assert not any(value in combined for value in forbidden)


@pytest.mark.skipif(os.name != "nt" or shutil.which("pwsh.exe") is None,
                    reason="PowerShell supervisor requires PowerShell 7 on Windows")
def test_supervisor_resolves_relative_paths_against_repository_before_launch(tmp_path):
    repo=Path(__file__).parents[1]
    script=repo/"scripts"/"supervise_backtest_recorder.ps1"
    completed=subprocess.run([shutil.which("pwsh.exe"),"-NoProfile","-NonInteractive",
        "-File",str(script),"-Symbol","BTC","-Timeframes","1m",
        "-Archive",r"data\backtests\btc_forward_archive_2",
        "-LogDirectory",r"outputs\recorder_health\btc_forward_archive_2",
        "-ResolvePathsOnly"],cwd=tmp_path,capture_output=True,text=True,check=True)
    resolved=json.loads(completed.stdout)
    assert Path(resolved["archive"])==repo/"data"/"backtests"/"btc_forward_archive_2"
    assert Path(resolved["log_directory"])==repo/"outputs"/"recorder_health"/"btc_forward_archive_2"
    assert not (tmp_path/"data").exists() and not (tmp_path/"outputs").exists()


def test_coverage_probe_and_deterministic_sufficiency_selection():
    transport=RecentTransport()
    coverage=RecentCoverageProbe(transport=transport,now=lambda:NOW).probe(
        symbol="BTC",timeframes=(CanonicalTimeframe.M1,CanonicalTimeframe.M5),
        data_network="testnet")
    assert len(coverage)==2 and all(item.candle_count==5 for item in coverage)
    assert all(item.gap_count==item.duplicate_count==item.overlap_count==0
               for item in coverage)
    base=datetime(2026,8,1,tzinfo=UTC); end=datetime(2026,8,10,tzinfo=UTC)
    sufficient=tuple(StreamCoverage(tf,base,end,100,((base,end),),0,0,0,0)
        for tf in (CanonicalTimeframe.M1,CanonicalTimeframe.M5,
                   CanonicalTimeframe.M15,CanonicalTimeframe.H1,CanonicalTimeframe.H4))
    selected=select_diagnostic_interval(sufficient)
    assert selected.sufficient and selected.scored_start < selected.replay_end
    restricted=tuple(StreamCoverage(tf,end-timedelta(hours=82),end,100,
        ((end-timedelta(hours=82),end),),0,0,0,0) for tf in
        (CanonicalTimeframe.M1,CanonicalTimeframe.M5,CanonicalTimeframe.M15,
         CanonicalTimeframe.H1,CanonicalTimeframe.H4))
    refused=select_diagnostic_interval(restricted)
    assert not refused.sufficient and "SIX_HOUR_SCORED_REPLAY_UNAVAILABLE" in refused.reasons
