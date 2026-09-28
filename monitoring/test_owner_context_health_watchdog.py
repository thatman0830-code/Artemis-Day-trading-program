from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from monitoring.owner_context_health_watchdog import evaluate_and_persist, record_failure

NOW = datetime(2026, 8, 31, 18, tzinfo=timezone.utc)
H = "a" * 64


def _row(component: str, repository: Path) -> dict:
    btc = component == "btc-recorder"
    return {"component":component,"collected_at":NOW.isoformat(),"source_file_sha256":[H],
        "task_installed":True,"task_name":"BTC Public Candle Research Recorder" if btc else "NinjaTrader MES-NQ Closed Bar Recorder",
        "task_path":"\\","executable_path":r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "script_path":str(repository / "scripts" / ("run_btc_forward_recorder_task.ps1" if btc else "run_ninjatrader_closed_bar_recorder.ps1")),
        "task_state":"Running","last_result":0,"single_instance_policy":"IgnoreNew",
        "instance_count":1,"restart_count":0,"restart_budget_exhausted":False,
        "restart_policy_count":3,"restart_interval_seconds":60,
        "latest_heartbeat_at":(NOW-timedelta(seconds=10)).isoformat(),
        "unresolved_gap_count":0,"archive_integrity_verified":True,"free_bytes":10_000_000_000,
        "clock_skew_seconds":0,"incident_facts":[],"trading_authority":False}


def _facts(tmp_path: Path, repository: Path) -> Path:
    value={"schema_version":"owner-context-health-facts-v1","collected_at":NOW.isoformat(),
        "visibility_scope":"OWNER_CONTEXT","trading_authority":False,
        "components":[_row("btc-recorder",repository),_row("es-nq-recorder",repository)]}
    path=tmp_path/"facts.json"; path.write_text(json.dumps(value),encoding="utf-8"); return path


def _alerts(output: Path) -> list[dict]:
    return [json.loads(line) for line in (output/"alerts.jsonl").read_text("utf-8").splitlines()]


def test_watchdog_persists_content_addressed_report_and_deduplicates_state(tmp_path):
    repository=Path(r"C:\repo"); output=tmp_path/"watchdog"; facts=_facts(tmp_path,repository)
    first=evaluate_and_persist(facts_path=facts,repository=repository,output_dir=output,as_of=NOW)
    second=evaluate_and_persist(facts_path=facts,repository=repository,output_dir=output,as_of=NOW)
    assert first == second and first["readiness"]["state"] == "HEALTHY"
    assert json.loads((output/"latest-readiness.json").read_text("utf-8")) == first
    status=json.loads((output/"latest-watchdog-status.json").read_text("utf-8"))
    assert status["state"] == "HEALTHY" and status["failure_reason"] is None
    assert (output/"reports"/f"{first['report_id']}.json").is_file()
    assert len(_alerts(output)) == 1 and _alerts(output)[0]["trading_authority"] is False


def test_health_transition_and_failure_are_append_only_and_secret_free(tmp_path):
    repository=Path(r"C:\repo"); output=tmp_path/"watchdog"; facts=_facts(tmp_path,repository)
    evaluate_and_persist(facts_path=facts,repository=repository,output_dir=output,as_of=NOW)
    document=json.loads(facts.read_text("utf-8")); document["components"][0]["unresolved_gap_count"]=1
    facts.write_text(json.dumps(document),encoding="utf-8")
    unhealthy=evaluate_and_persist(facts_path=facts,repository=repository,output_dir=output,as_of=NOW)
    assert unhealthy["readiness"]["state"] == "UNHEALTHY"
    assert record_failure(output_dir=output,reason="HEALTH_COLLECTION_FAILED",as_of=NOW)
    assert not record_failure(output_dir=output,reason="HEALTH_COLLECTION_FAILED",as_of=NOW)
    status=json.loads((output/"latest-watchdog-status.json").read_text("utf-8"))
    assert status["state"] == "UNHEALTHY" and not status["ready_for_unattended_operation"]
    assert status["report_id"] is None and status["trading_authority"] is False
    alerts=_alerts(output); assert len(alerts) == 3
    assert alerts[-1]["event"] == "WATCHDOG_FAILURE"
    assert "secret" not in (output/"alerts.jsonl").read_text("utf-8").lower()


def test_runner_notifies_only_on_a_new_transition_and_never_grants_authority():
    runner = (Path(__file__).parents[1] / "scripts" / "run_owner_context_health_watchdog.ps1").read_text("utf-8")
    assert "Get-LatestAlert" in runner
    assert "latest.event_id -eq $PreviousEventId" in runner
    assert "msg.exe" in runner
    assert "No order authority was granted" in runner
    assert "No orders were placed" in runner
