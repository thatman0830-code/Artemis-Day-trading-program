from datetime import timedelta
import hashlib,json
from pathlib import Path,PureWindowsPath

import pytest

from execution.test_paper_performance_ledger_v1 import T
from execution.test_paper_windows_clock_evidence_v1 import RAW
from execution.windows_btc_paper_cycle_health_v1 import (
    WindowsBTCPaperCycleHealthError,read_windows_btc_paper_cycle_health,
)


def facts(tmp_path,**changes):
    repository=tmp_path/"repo";repository.mkdir(parents=True)
    manifest=repository/"data"/"backtests"/"btc_forward_archive_2"/"archive_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"state":"RECORDING","symbol":"BTC","streams":{"1m":{"gap_count":0}}}))
    path=tmp_path/"cycle.json";raw_path=Path(str(path)+".clock-status.txt");raw_path.write_bytes(RAW)
    manifest_snapshot=Path(str(path)+".archive-manifest.json")
    manifest_snapshot.write_bytes(manifest.read_bytes())
    doc={"schema_version":"btc-paper-cycle-health-facts-v1","collected_at":T.isoformat(),
        "task_name":"BTC Public Candle Research Recorder","task_path":"\\","task_state":"Running",
        "single_instance_policy":"IgnoreNew","instance_count":1,
        "script_path":str(PureWindowsPath(str(repository.resolve()))/"scripts"/"run_btc_forward_recorder_task.ps1"),
        "latest_heartbeat_at":T.isoformat(),"unresolved_gap_count":0,
        "manifest_sha256":hashlib.sha256(manifest_snapshot.read_bytes()).hexdigest(),"clock_query_started_at":T.isoformat(),
        "clock_query_completed_at":T.isoformat(),"clock_raw_sha256":hashlib.sha256(RAW).hexdigest(),
        "trading_authority":False}
    doc.update(changes);path.write_text(json.dumps(doc));return path,repository


def test_strict_windows_facts_produce_typed_non_authoritative_health(tmp_path):
    path,repository=facts(tmp_path)
    result=read_windows_btc_paper_cycle_health(facts_path=path,repository=repository,as_of=T)
    assert result.watchdog_healthy and result.btc_recorder_healthy
    assert result.unresolved_gap_count==0 and result.clock.synchronized
    assert result.clock.uncertainty_ns>100_000_000 and result.trading_authority is False


@pytest.mark.parametrize("change",[
    {"task_state":"Ready"},{"instance_count":0},{"unresolved_gap_count":1},
    {"trading_authority":True},{"script_path":r"C:\other.ps1"},
    {"collected_at":(T-timedelta(seconds=11)).isoformat()},
])
def test_wrong_identity_state_gap_authority_and_staleness_reject(tmp_path,change):
    path,repository=facts(tmp_path,**change)
    with pytest.raises(WindowsBTCPaperCycleHealthError):
        read_windows_btc_paper_cycle_health(facts_path=path,repository=repository,as_of=T)


def test_clock_byte_tampering_rejects(tmp_path):
    path,repository=facts(tmp_path)
    Path(str(path)+".clock-status.txt").write_bytes(RAW+b"x")
    with pytest.raises(WindowsBTCPaperCycleHealthError):
        read_windows_btc_paper_cycle_health(facts_path=path,repository=repository,as_of=T)


def test_manifest_tampering_and_duplicate_json_keys_reject(tmp_path):
    path,repository=facts(tmp_path)
    Path(str(path)+".archive-manifest.json").write_text('{"changed":true}')
    with pytest.raises(WindowsBTCPaperCycleHealthError,match="manifest evidence"):
        read_windows_btc_paper_cycle_health(facts_path=path,repository=repository,as_of=T)
    path,repository=facts(tmp_path/"duplicate")
    text=path.read_text();path.write_text(text[:-1]+',"task_name":"BTC Public Candle Research Recorder"}')
    with pytest.raises(WindowsBTCPaperCycleHealthError,match="duplicate keys"):
        read_windows_btc_paper_cycle_health(facts_path=path,repository=repository,as_of=T)


def test_live_manifest_rotation_does_not_invalidate_immutable_health_snapshot(tmp_path):
    path,repository=facts(tmp_path)
    (repository/"data"/"backtests"/"btc_forward_archive_2"/"archive_manifest.json").write_text('{"changed":true}')
    result=read_windows_btc_paper_cycle_health(facts_path=path,repository=repository,as_of=T)
    assert result.btc_recorder_healthy and result.trading_authority is False


def test_powershell_collector_is_read_only_bounded_and_atomic():
    source=Path(__file__).parents[1].joinpath("scripts","collect_btc_paper_cycle_health.ps1").read_text("utf-8")
    assert "w32tm.exe" in source and "/query /status /verbose" in source
    assert "Get-ScheduledTask" in source and "Get-CimInstance" in source
    assert "[IO.FileShare]::ReadWrite" in source and "[IO.FileShare]::Delete" in source
    assert "Select-Object -Last 100" in source and "gapCount-ne 0" in source
    assert "Move-Item -LiteralPath $temporary" in source
    assert "manifestSnapshotPath" in source and "WriteAllBytes" in source
    assert "Get-Sha256Hex" in source and "Get-FileHash" not in source
    for prohibited in ("Start-ScheduledTask","Stop-ScheduledTask","Register-ScheduledTask",
            "Invoke-WebRequest","Invoke-RestMethod","Start-Process","Stop-Process"):
        assert prohibited not in source
