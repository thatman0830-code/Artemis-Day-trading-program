"""Decode bounded Windows clock and BTC recorder facts for paper control."""
from __future__ import annotations

from datetime import datetime,timedelta
import hashlib,json
from pathlib import Path,PureWindowsPath

from execution.paper_windows_clock_evidence_v1 import (
    PaperClockError,WindowsClockPolicyV1,decode_windows_clock_status,
)
from execution.supervised_btc_paper_session_controller_v1 import PaperCycleOperationalHealthV1

VERSION="btc-paper-cycle-health-facts-v1"
POLICY_TEXT="time.windows.com,0x8|local_uncertainty_ns=100000000|drift_ns_per_second=15000|supervised-paper-only"
POLICY=WindowsClockPolicyV1(("time.windows.com,0x8",),100_000_000,15_000,
    hashlib.sha256(POLICY_TEXT.encode()).hexdigest())


class WindowsBTCPaperCycleHealthError(ValueError):pass


def _strict_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise WindowsBTCPaperCycleHealthError("cycle-health facts contain duplicate keys")
        result[key]=value
    return result


def _time(value,name):
    if not isinstance(value,str):raise WindowsBTCPaperCycleHealthError(f"{name} must be UTC")
    try:result=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise WindowsBTCPaperCycleHealthError(f"{name} is invalid") from exc
    if result.tzinfo is None or result.utcoffset()!=timedelta(0):raise WindowsBTCPaperCycleHealthError(f"{name} must be UTC")
    return result


def read_windows_btc_paper_cycle_health(*,facts_path,repository,as_of):
    path=Path(facts_path);repository=Path(repository).resolve()
    if path.is_symlink()or not path.is_file()or not 0<path.stat().st_size<=65536:
        raise WindowsBTCPaperCycleHealthError("cycle-health facts are unsafe")
    payload=path.read_bytes()
    try:doc=json.loads(payload,object_pairs_hook=_strict_object)
    except (UnicodeError,json.JSONDecodeError) as exc:raise WindowsBTCPaperCycleHealthError("cycle-health facts are unreadable")from exc
    required={"schema_version","collected_at","task_name","task_path","task_state",
        "single_instance_policy","instance_count","script_path","latest_heartbeat_at",
        "unresolved_gap_count","manifest_sha256","clock_query_started_at",
        "clock_query_completed_at","clock_raw_sha256","trading_authority"}
    expected_script=str(PureWindowsPath(str(repository))/"scripts"/"run_btc_forward_recorder_task.ps1").casefold()
    if (not isinstance(doc,dict)or set(doc)!=required or doc["schema_version"]!=VERSION
            or doc["task_name"]!="BTC Public Candle Research Recorder"or doc["task_path"]!="\\"
            or doc["task_state"]!="Running"or doc["single_instance_policy"]!="IgnoreNew"
            or doc["instance_count"]!=1 or str(PureWindowsPath(doc["script_path"])).casefold()!=expected_script
            or doc["unresolved_gap_count"]!=0 or doc["trading_authority"] is not False):
        raise WindowsBTCPaperCycleHealthError("cycle-health identity or state is ineligible")
    collected=_time(doc["collected_at"],"collected_at");heartbeat=_time(doc["latest_heartbeat_at"],"latest_heartbeat_at")
    started=_time(doc["clock_query_started_at"],"clock_query_started_at");completed=_time(doc["clock_query_completed_at"],"clock_query_completed_at")
    if (as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0)
            or not timedelta(0)<=as_of-collected<=timedelta(seconds=10)
            or heartbeat>collected):raise WindowsBTCPaperCycleHealthError("cycle-health chronology is invalid")
    for name in ("manifest_sha256","clock_raw_sha256"):
        value=doc[name]
        if not isinstance(value,str)or len(value)!=64 or any(c not in"0123456789abcdef"for c in value):raise WindowsBTCPaperCycleHealthError("cycle-health hash is invalid")
    manifest_path=Path(str(path)+".archive-manifest.json")
    if (manifest_path.is_symlink()or not manifest_path.is_file()
            or not 0<manifest_path.stat().st_size<=1024*1024
            or hashlib.sha256(manifest_path.read_bytes()).hexdigest()!=doc["manifest_sha256"]):
        raise WindowsBTCPaperCycleHealthError("archive manifest evidence does not match")
    try:manifest=json.loads(manifest_path.read_bytes(),object_pairs_hook=_strict_object)
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise WindowsBTCPaperCycleHealthError("archive manifest evidence is unreadable")from exc
    streams=manifest.get("streams") if isinstance(manifest,dict) else None
    if (manifest.get("state")!="RECORDING"or manifest.get("symbol")!="BTC"
            or not isinstance(streams,dict)or not streams
            or any(not isinstance(value,dict)or value.get("gap_count")!=0 for value in streams.values())):
        raise WindowsBTCPaperCycleHealthError("archive manifest evidence is ineligible")
    raw_path=Path(str(path)+".clock-status.txt")
    if raw_path.is_symlink()or not raw_path.is_file():raise WindowsBTCPaperCycleHealthError("clock evidence is missing")
    raw=raw_path.read_bytes()
    try:
        receipt=decode_windows_clock_status(raw,expected_sha256=doc["clock_raw_sha256"],
            query_started_at=started,query_completed_at=completed,as_of=as_of,policy=POLICY)
    except PaperClockError as exc:
        raise WindowsBTCPaperCycleHealthError("clock evidence is ineligible")from exc
    report_id=hashlib.sha256(payload).hexdigest()
    return PaperCycleOperationalHealthV1.create(observed_at=collected,
        watchdog_report_id=report_id,btc_heartbeat_at=heartbeat,clock=receipt.health,
        watchdog_healthy=True,btc_recorder_healthy=True,unresolved_gap_count=0)
