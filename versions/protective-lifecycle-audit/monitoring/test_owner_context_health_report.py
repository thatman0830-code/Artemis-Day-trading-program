from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from monitoring.owner_context_health_adapter import OwnerContextAdapterError
from monitoring.owner_context_health_report import evaluate_sanitized_owner_facts, report_json

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
H = "a" * 64


def row(component, repo):
    btc = component == "btc-recorder"
    return {"component":component,"collected_at":NOW.isoformat(),"source_file_sha256":[H],
        "task_installed":True,"task_name":"BTC Public Candle Research Recorder" if btc else "ES-NQ Delayed Daily Research Collector",
        "task_path":"\\","executable_path":r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "script_path":str(repo / "scripts" / ("run_btc_forward_recorder_task.ps1" if btc else "run_es_nq_delayed_forward_collector.ps1")),
        "task_state":"Running" if btc else "Ready","last_result":0,"single_instance_policy":"IgnoreNew",
        "instance_count":1 if btc else 0,"restart_count":0,"restart_budget_exhausted":False,
        "restart_policy_count":3 if btc else 0,"restart_interval_seconds":60 if btc else 0,
        "latest_heartbeat_at":(NOW-timedelta(seconds=10) if btc else NOW-timedelta(hours=25)).isoformat(),
        "unresolved_gap_count":0,"archive_integrity_verified":True,"free_bytes":10_000_000_000,
        "clock_skew_seconds":0,"incident_facts":[],"trading_authority":False}


def write(tmp_path, repo, mutate=None):
    doc={"schema_version":"owner-context-health-facts-v1","collected_at":NOW.isoformat(),
         "visibility_scope":"OWNER_CONTEXT","trading_authority":False,
         "components":[row("btc-recorder",repo),row("es-nq-recorder",repo)]}
    if mutate: mutate(doc)
    path=tmp_path/"facts.json"; path.write_text(json.dumps(doc),encoding="utf-8"); return path


def test_sanitized_facts_produce_healthy_nontrading_report(tmp_path):
    repo=Path(r"C:\repo")
    report=evaluate_sanitized_owner_facts(facts_path=write(tmp_path,repo),repository=repo,as_of=NOW)
    assert report.readiness.ready_for_unattended_operation and not report.trading_authority
    decoded=json.loads(report_json(report)); assert decoded["trading_authority"] is False


def test_daily_es_nq_heartbeat_does_not_weaken_btc_sla(tmp_path):
    repo=Path(r"C:\repo")
    def mutate(doc): doc["components"][0]["latest_heartbeat_at"]=(NOW-timedelta(seconds=91)).isoformat()
    report=evaluate_sanitized_owner_facts(facts_path=write(tmp_path,repo,mutate),repository=repo,as_of=NOW)
    assert not report.readiness.ready_for_unattended_operation


def test_stopped_stale_btc_is_classified_unhealthy_not_rejected(tmp_path):
    repo=Path(r"C:\repo")
    def mutate(doc):
        doc["components"][0]["task_state"]="Ready"
        doc["components"][0]["instance_count"]=0
        doc["components"][0]["latest_heartbeat_at"]=(NOW-timedelta(seconds=91)).isoformat()
    report=evaluate_sanitized_owner_facts(facts_path=write(tmp_path,repo,mutate),repository=repo,as_of=NOW)
    reasons={(component,reason.value) for component,reason in report.readiness.reasons}
    assert ("btc-recorder","TASK_NOT_RUNNING") in reasons
    assert ("btc-recorder","STALE_HEARTBEAT") in reasons
    assert not report.readiness.ready_for_unattended_operation


@pytest.mark.parametrize("mutate",(
    lambda d:d.update(trading_authority=True),
    lambda d:d.update(visibility_scope="SANDBOX_CONTEXT"),
    lambda d:d["components"].append(d["components"][0]),
    lambda d:d["components"][0].update(trading_authority=True),
    lambda d:d["components"][0].update(extra="x"),
))
def test_authority_duplicate_and_shape_attacks_reject(tmp_path,mutate):
    repo=Path(r"C:\repo")
    with pytest.raises(OwnerContextAdapterError):
        evaluate_sanitized_owner_facts(facts_path=write(tmp_path,repo,mutate),repository=repo,as_of=NOW)


def test_absent_clock_and_es_integrity_remain_unhealthy(tmp_path):
    repo=Path(r"C:\repo")
    def mutate(doc):
        doc["components"][0]["clock_skew_seconds"]=2147483647
        doc["components"][1]["archive_integrity_verified"]=False
    report=evaluate_sanitized_owner_facts(facts_path=write(tmp_path,repo,mutate),repository=repo,as_of=NOW)
    reasons={reason.value for _,reason in report.readiness.reasons}
    assert {"CLOCK_SKEW","INTEGRITY_FAILURE"} <= reasons
