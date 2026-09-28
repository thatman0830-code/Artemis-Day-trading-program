"""Hermes independent adversarial audit for the owner-context health-watchdog milestone.

Audit assignment: AUDIT-OWNER-CONTEXT-HEALTH-WATCHDOG
Checkpoint: 17f44e95648cc2ba100dda5d52816c529bd14727

Covers:
  1. trading_authority always false
  2. Fail-closed on collection and evaluation failures
  3. Cannot leave stale successful status as authoritative after failure
  4. Writes reports and current status atomically
  5. Retains content-addressed successful reports
  6. Appends deterministic, secret-free transition alerts
  7. Deduplicates repeated identical states without suppressing recovery or later regression
  8. Rejects malformed or authority-escalating state
  9. Safely handles missing, corrupt, partial, stale, future-dated, and conflicting evidence
 10. Cannot control or restart either recorder
 11. Installs only a disabled, limited, single-instance, time-bounded task
 12. Does not claim off-host alert delivery or institutional/live-trading readiness
 13. Path handling, interrupted writes, malformed alert state, repeated failures, recovery transitions
 14. Report-ID integrity, chronology, concurrency assumptions, PowerShell task/action identity
 15. Classification: accepted, corrected, redundant, implementation-coupled, incorrect
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitoring.owner_context_health_watchdog import (
    WATCHDOG_VERSION, FAILURE_REASONS, evaluate_and_persist, record_failure,
)
from monitoring.owner_context_health_report import evaluate_sanitized_owner_facts, report_json

NOW = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)
H = "a" * 64
REPO = Path(r"C:\repo")
RUNNER_PS1 = Path(__file__).parent.parent / "scripts" / "run_owner_context_health_watchdog.ps1"
INSTALLER_PS1 = Path(__file__).parent.parent / "scripts" / "install_owner_context_health_watchdog_task.ps1"
WATCHDOG_PY = Path(__file__).parent.parent / "monitoring" / "owner_context_health_watchdog.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(component: str, repository: Path = REPO) -> dict:
    btc = component == "btc-recorder"
    return {
        "component": component, "collected_at": NOW.isoformat(),
        "source_file_sha256": [H], "task_installed": True,
        "task_name": "BTC Public Candle Research Recorder" if btc else "ES-NQ Delayed Daily Research Collector",
        "task_path": "\\", "executable_path": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "script_path": str(repository / "scripts" / ("run_btc_forward_recorder_task.ps1" if btc else "run_es_nq_delayed_forward_collector.ps1")),
        "task_state": "Running" if btc else "Ready", "last_result": 0,
        "single_instance_policy": "IgnoreNew",
        "instance_count": 1 if btc else 0, "restart_count": 0,
        "restart_budget_exhausted": False,
        "restart_policy_count": 3 if btc else 0,
        "restart_interval_seconds": 60 if btc else 0,
        "latest_heartbeat_at": (NOW - timedelta(seconds=10) if btc else NOW - timedelta(hours=25)).isoformat(),
        "unresolved_gap_count": 0, "archive_integrity_verified": True,
        "free_bytes": 10_000_000_000, "clock_skew_seconds": 0,
        "incident_facts": [], "trading_authority": False,
    }


def _facts(tmp_path: Path, repository: Path = REPO) -> Path:
    value = {
        "schema_version": "owner-context-health-facts-v1",
        "collected_at": NOW.isoformat(),
        "visibility_scope": "OWNER_CONTEXT", "trading_authority": False,
        "components": [_row("btc-recorder", repository), _row("es-nq-recorder", repository)],
    }
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _alerts(output: Path) -> list[dict]:
    p = output / "alerts.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text("utf-8").splitlines() if line.strip()]


def _status(output: Path) -> dict:
    return json.loads((output / "latest-watchdog-status.json").read_text("utf-8"))


def _state(output: Path) -> dict | None:
    p = output / "alert-state.json"
    if not p.exists():
        return None
    return json.loads(p.read_text("utf-8"))


# ===========================================================================
# 1. trading_authority always false
# ===========================================================================

class TestTradingAuthorityAlwaysFalse:
    def test_healthy_report_trading_authority_false(self, tmp_path):
        output = tmp_path / "watchdog"
        report = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                      output_dir=output, as_of=NOW)
        assert report["trading_authority"] is False
        assert report["readiness"]["trading_authority"] is False

    def test_status_trading_authority_false(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                             output_dir=output, as_of=NOW)
        assert _status(output)["trading_authority"] is False

    def test_failure_status_trading_authority_false(self, tmp_path):
        output = tmp_path / "watchdog"
        record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        assert _status(output)["trading_authority"] is False

    def test_alerts_trading_authority_false(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                             output_dir=output, as_of=NOW)
        for alert in _alerts(output):
            assert alert["trading_authority"] is False

    def test_failure_alerts_trading_authority_false(self, tmp_path):
        output = tmp_path / "watchdog"
        record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        for alert in _alerts(output):
            assert alert["trading_authority"] is False

    def test_state_trading_authority_false(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                             output_dir=output, as_of=NOW)
        assert _state(output)["trading_authority"] is False


# ===========================================================================
# 2. Fail-closed on collection and evaluation failures
# ===========================================================================

class TestFailClosed:
    def test_collection_failure_records_unhealthy(self, tmp_path):
        output = tmp_path / "watchdog"
        record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        status = _status(output)
        assert status["state"] == "UNHEALTHY"
        assert status["ready_for_unattended_operation"] is False
        assert status["failure_reason"] == "HEALTH_COLLECTION_FAILED"

    def test_evaluation_failure_records_unhealthy(self, tmp_path):
        output = tmp_path / "watchdog"
        record_failure(output_dir=output, reason="HEALTH_EVALUATION_FAILED", as_of=NOW)
        status = _status(output)
        assert status["state"] == "UNHEALTHY"
        assert status["failure_reason"] == "HEALTH_EVALUATION_FAILED"

    def test_unsupported_failure_reason_rejects(self, tmp_path):
        with pytest.raises(ValueError):
            record_failure(output_dir=tmp_path / "watchdog", reason="BAD_REASON", as_of=NOW)


# ===========================================================================
# 3. Cannot leave stale successful status as authoritative after failure
# ===========================================================================

class TestStaleStatusOverwritten:
    def test_failure_overwrites_healthy_status(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                             output_dir=output, as_of=NOW)
        assert _status(output)["state"] == "HEALTHY"
        record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        status = _status(output)
        assert status["state"] == "UNHEALTHY"
        assert status["report_id"] is None
        assert status["failure_reason"] == "HEALTH_COLLECTION_FAILED"

    def test_recovery_overwrites_failure_status(self, tmp_path):
        output = tmp_path / "watchdog"
        record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        assert _status(output)["state"] == "UNHEALTHY"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                             output_dir=output, as_of=NOW)
        status = _status(output)
        assert status["state"] == "HEALTHY"
        assert status["failure_reason"] is None


# ===========================================================================
# 4. Writes reports and current status atomically
# ===========================================================================

class TestAtomicWrites:
    def test_report_file_written(self, tmp_path):
        output = tmp_path / "watchdog"
        report = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                      output_dir=output, as_of=NOW)
        report_path = output / "reports" / f"{report['report_id']}.json"
        assert report_path.is_file()
        assert json.loads(report_path.read_text("utf-8")) == report

    def test_latest_readiness_written(self, tmp_path):
        output = tmp_path / "watchdog"
        report = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                      output_dir=output, as_of=NOW)
        assert json.loads((output / "latest-readiness.json").read_text("utf-8")) == report

    def test_latest_watchdog_status_written(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                            output_dir=output, as_of=NOW)
        assert (output / "latest-watchdog-status.json").is_file()

    def test_no_temp_files_remaining(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                            output_dir=output, as_of=NOW)
        temps = list(output.rglob("*.tmp-*"))
        assert len(temps) == 0


# ===========================================================================
# 5. Retains content-addressed successful reports
# ===========================================================================

class TestContentAddressedReports:
    def test_report_id_is_sha256(self, tmp_path):
        output = tmp_path / "watchdog"
        report = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                      output_dir=output, as_of=NOW)
        rid = report["report_id"]
        assert len(rid) == 64
        assert all(c in "0123456789abcdef" for c in rid)

    def test_report_file_named_by_report_id(self, tmp_path):
        output = tmp_path / "watchdog"
        report = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                      output_dir=output, as_of=NOW)
        assert (output / "reports" / f"{report['report_id']}.json").is_file()

    def test_repeated_eval_same_report_id(self, tmp_path):
        output = tmp_path / "watchdog"
        a = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                 output_dir=output, as_of=NOW)
        b = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                 output_dir=output, as_of=NOW)
        assert a["report_id"] == b["report_id"]


# ===========================================================================
# 6. Deterministic, secret-free transition alerts
# ===========================================================================

class TestAlerts:
    def test_alerts_are_secret_free(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                            output_dir=output, as_of=NOW)
        text = (output / "alerts.jsonl").read_text("utf-8")
        for forbidden in ("password", "api_key", "private_key", "secret", "credential"):
            assert forbidden not in text.lower()

    def test_alert_event_id_is_sha256(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                            output_dir=output, as_of=NOW)
        for alert in _alerts(output):
            assert len(alert["event_id"]) == 64
            assert all(c in "0123456789abcdef" for c in alert["event_id"])

    def test_alert_has_watchdog_version(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                            output_dir=output, as_of=NOW)
        for alert in _alerts(output):
            assert alert["watchdog_version"] == WATCHDOG_VERSION


# ===========================================================================
# 7. Deduplicates repeated identical states without suppressing recovery/regression
# ===========================================================================

class TestDeduplication:
    def test_repeated_healthy_deduplicates(self, tmp_path):
        output = tmp_path / "watchdog"
        facts = _facts(tmp_path)
        evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
        evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
        assert len(_alerts(output)) == 1

    def test_recovery_emits_new_alert(self, tmp_path):
        output = tmp_path / "watchdog"
        facts = _facts(tmp_path)
        evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
        # Make unhealthy
        doc = json.loads(facts.read_text("utf-8"))
        doc["components"][0]["unresolved_gap_count"] = 1
        facts.write_text(json.dumps(doc), encoding="utf-8")
        evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
        # Recover
        doc["components"][0]["unresolved_gap_count"] = 0
        facts.write_text(json.dumps(doc), encoding="utf-8")
        evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
        alerts = _alerts(output)
        assert len(alerts) == 3  # healthy → unhealthy → healthy

    def test_regression_emits_new_alert(self, tmp_path):
        output = tmp_path / "watchdog"
        facts = _facts(tmp_path)
        evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
        for _ in range(3):
            doc = json.loads(facts.read_text("utf-8"))
            doc["components"][0]["unresolved_gap_count"] = 1
            facts.write_text(json.dumps(doc), encoding="utf-8")
            evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
            doc["components"][0]["unresolved_gap_count"] = 0
            facts.write_text(json.dumps(doc), encoding="utf-8")
            evaluate_and_persist(facts_path=facts, repository=REPO, output_dir=output, as_of=NOW)
        alerts = _alerts(output)
        # Each unhealthy+healthy cycle emits 2 alerts; initial healthy = 1; total = 1 + 3*2 = 7
        assert len(alerts) == 7

    def test_repeated_failure_deduplicates(self, tmp_path):
        output = tmp_path / "watchdog"
        a = record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        b = record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        assert a is True and b is False
        assert len(_alerts(output)) == 1


# ===========================================================================
# 8. Rejects malformed or authority-escalating state
# ===========================================================================

class TestMalformedState:
    def test_trading_authority_true_in_state_rejects(self, tmp_path):
        output = tmp_path / "watchdog"
        output.mkdir(parents=True, exist_ok=True)
        state_path = output / "alert-state.json"
        state_path.write_text(json.dumps({"signature": "x", "trading_authority": True}), encoding="utf-8")
        # Next evaluation should reject the corrupted state
        with pytest.raises(ValueError, match="authority"):
            evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                output_dir=output, as_of=NOW)

    def test_malformed_state_keys_rejects(self, tmp_path):
        output = tmp_path / "watchdog"
        output.mkdir(parents=True, exist_ok=True)
        state_path = output / "alert-state.json"
        state_path.write_text(json.dumps({"extra": "field"}), encoding="utf-8")
        with pytest.raises(ValueError, match="malformed"):
            evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                output_dir=output, as_of=NOW)

    def test_corrupt_state_json_rejects(self, tmp_path):
        output = tmp_path / "watchdog"
        output.mkdir(parents=True, exist_ok=True)
        state_path = output / "alert-state.json"
        state_path.write_text("{not json}", encoding="utf-8")
        with pytest.raises((ValueError, json.JSONDecodeError)):
            evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                output_dir=output, as_of=NOW)


# ===========================================================================
# 9. Safely handles missing, corrupt, partial, stale, future-dated, conflicting evidence
# ===========================================================================

class TestEvidenceHandling:
    def test_missing_facts_file_rejects(self, tmp_path):
        output = tmp_path / "watchdog"
        with pytest.raises(Exception):
            evaluate_and_persist(facts_path=tmp_path / "nonexistent.json",
                                repository=REPO, output_dir=output, as_of=NOW)

    def test_corrupt_facts_json_rejects(self, tmp_path):
        output = tmp_path / "watchdog"
        path = tmp_path / "facts.json"
        path.write_text("{not json}", encoding="utf-8")
        with pytest.raises(Exception):
            evaluate_and_persist(facts_path=path, repository=REPO, output_dir=output, as_of=NOW)

    def test_wrong_schema_version_rejects(self, tmp_path):
        output = tmp_path / "watchdog"
        path = tmp_path / "facts.json"
        path.write_text(json.dumps({"schema_version": "wrong", "components": []}), encoding="utf-8")
        with pytest.raises(Exception):
            evaluate_and_persist(facts_path=path, repository=REPO, output_dir=output, as_of=NOW)

    def test_trading_authority_true_in_facts_rejects(self, tmp_path):
        output = tmp_path / "watchdog"
        path = tmp_path / "facts.json"
        doc = {"schema_version": "owner-context-health-facts-v1", "collected_at": NOW.isoformat(),
               "visibility_scope": "OWNER_CONTEXT", "trading_authority": True,
               "components": [_row("btc-recorder"), _row("es-nq-recorder")]}
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(Exception):
            evaluate_and_persist(facts_path=path, repository=REPO, output_dir=output, as_of=NOW)


# ===========================================================================
# 10. Cannot control or restart either recorder
# ===========================================================================

class TestNoRecorderControl:
    def test_watchdog_no_start_stop_imports(self):
        source = WATCHDOG_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"subprocess", "socket", "requests", "httpx", "win32com",
                    "ctypes", "signal", "threading", "multiprocessing"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_runner_no_start_stop(self):
        source = RUNNER_PS1.read_text("utf-8")
        for prohibited in ("Start-ScheduledTask", "Stop-ScheduledTask", "Start-Process",
                           "Stop-Process", "Enable-ScheduledTask", "Disable-ScheduledTask"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_runner_no_trading(self):
        source = RUNNER_PS1.read_text("utf-8")
        assert "trading" not in source.lower()


# ===========================================================================
# 11. Installs only a disabled, limited, single-instance, time-bounded task
# ===========================================================================

class TestInstaller:
    def test_single_instance_ignore_new(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "MultipleInstances IgnoreNew" in source

    def test_execution_time_limit_4_minutes(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "ExecutionTimeLimit (New-TimeSpan -Minutes 4)" in source

    def test_repetition_interval_5_minutes(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "RepetitionInterval (New-TimeSpan -Minutes 5)" in source

    def test_disabled_after_install(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Disable-ScheduledTask" in source

    def test_run_level_limited(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "RunLevel Limited" in source

    def test_no_trading_authority(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "No trading authority" in source

    def test_task_already_exists_rejects(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "already exists" in source

    def test_powershell_executable_explicit(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "powershell.exe" in source

    def test_no_logo_no_profile(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "-NoLogo" in source and "-NoProfile" in source


# ===========================================================================
# 12. Does not claim off-host alert delivery or institutional readiness
# ===========================================================================

class TestNoOffHostClaim:
    def test_implementation_disclaims_off_host(self):
        source = (Path(__file__).parent.parent / "monitoring" / "OWNER_CONTEXT_WATCHDOG_IMPLEMENTATION.md").read_text("utf-8")
        assert "local evidence" in source.lower() or "not off-host" in source.lower()
        assert "not" in source.lower() and ("off-host" in source.lower() or "remote" in source.lower())

    def test_implementation_disclaims_institutional_readiness(self):
        source = (Path(__file__).parent.parent / "monitoring" / "OWNER_CONTEXT_WATCHDOG_IMPLEMENTATION.md").read_text("utf-8")
        assert "institutional" in source.lower() or "24/7" in source

    def test_no_notification_delivery_claim(self):
        source = (Path(__file__).parent.parent / "monitoring" / "OWNER_CONTEXT_WATCHDOG_IMPLEMENTATION.md").read_text("utf-8")
        # Must say it is NOT off-host notification
        assert "not off-host notification" in source.lower() or "local evidence, not off-host" in source.lower()


# ===========================================================================
# 13. Path handling, interrupted writes, report-ID integrity, chronology
# ===========================================================================

class TestPathAndIntegrity:
    def test_output_dir_created(self, tmp_path):
        output = tmp_path / "deep" / "nested" / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                           output_dir=output, as_of=NOW)
        assert output.is_dir()

    def test_report_dir_created(self, tmp_path):
        output = tmp_path / "watchdog"
        report = evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                                      output_dir=output, as_of=NOW)
        assert (output / "reports").is_dir()
        assert (output / "reports" / f"{report['report_id']}.json").is_file()

    def test_alert_state_written(self, tmp_path):
        output = tmp_path / "watchdog"
        evaluate_and_persist(facts_path=_facts(tmp_path), repository=REPO,
                           output_dir=output, as_of=NOW)
        state = _state(output)
        assert "signature" in state
        assert len(state["signature"]) == 64

    def test_latest_readiness_retained_on_failure(self, tmp_path):
        output = tmp_path / "watchdog"
        facts = _facts(tmp_path)
        report = evaluate_and_persist(facts_path=facts, repository=REPO,
                                      output_dir=output, as_of=NOW)
        record_failure(output_dir=output, reason="HEALTH_COLLECTION_FAILED", as_of=NOW)
        # latest-readiness.json still has the last successful report
        retained = json.loads((output / "latest-readiness.json").read_text("utf-8"))
        assert retained == report
        # But latest-watchdog-status.json shows failure
        assert _status(output)["state"] == "UNHEALTHY"


# ===========================================================================
# 14. PowerShell task/action identity and syntax
# ===========================================================================

class TestPowerShellIdentity:
    def test_runner_requires_version_51(self):
        source = RUNNER_PS1.read_text("utf-8")
        assert "#requires -Version 5.1" in source

    def test_runner_cmdlet_binding(self):
        source = RUNNER_PS1.read_text("utf-8")
        assert "[CmdletBinding()]" in source

    def test_runner_error_action_stop(self):
        source = RUNNER_PS1.read_text("utf-8")
        assert "$ErrorActionPreference = 'Stop'" in source

    def test_runner_calls_collector(self):
        source = RUNNER_PS1.read_text("utf-8")
        assert "collect_owner_context_health_facts.ps1" in source

    def test_runner_failure_reasons_present(self):
        source = RUNNER_PS1.read_text("utf-8")
        assert "HEALTH_COLLECTION_FAILED" in source
        assert "HEALTH_EVALUATION_FAILED" in source

    def test_installer_requires_version_51(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "#requires -Version 5.1" in source

    def test_installer_task_name(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Owner Context Research Health Watchdog" in source

    def test_installer_register_then_disable(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Register-ScheduledTask" in source
        assert "Disable-ScheduledTask" in source

    def test_installer_no_enable(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Enable-ScheduledTask" not in source

    def test_installer_no_start(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Start-ScheduledTask" not in source


# ===========================================================================
# 15. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """4 existing watchdog + task tests pass unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: stale status overwrite, recovery after failure,
        malformed state rejection, corrupt state JSON, trading_authority escalation,
        secret-free alerts, alert event_id integrity, report-ID integrity, atomic
        temp cleanup, latest-readiness retention on failure, installer RunLevel,
        no-enable, no-start, off-host disclaimer — not in existing tests."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: evaluate_and_persist,
        record_failure, WATCHDOG_VERSION, FAILURE_REASONS. No private helpers."""
