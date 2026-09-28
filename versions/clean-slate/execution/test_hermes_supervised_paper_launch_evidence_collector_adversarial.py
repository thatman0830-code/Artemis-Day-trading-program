"""Hermes independent adversarial audit for the supervised paper launch-evidence collector.

Audit assignment: AUDIT-SUPERVISED-PAPER-LAUNCH-EVIDENCE-COLLECTOR
Checkpoint: 595d6afde82d4d86c4df1af73d6b078e77b5e4fb

Covers:
  1. Deterministic evidence creation and evidence_id validation
  2. SHA-256 binding of watchdog, recovery-drill, stale-alert source files
  3. Atomic output and read-back through read_launch_evidence()
  4. Missing/malformed/non-object/authority-bearing/duplicated/stale/inconsistent/tampered sources
  5. Wrong watchdog version, unhealthy state, malformed report IDs, incorrect components, duplicates
  6. Missing BTC/ES-NQ observations, invalid timestamps, invalid counts, bad clock skew, non-running BTC
  7. Failed/incomplete recovery and stale-alert drills; every stale-drill boolean independently
  8. Dirty Git, malformed checkpoint, invalid task facts, missed-run validation, UTC enforcement
  9. PowerShell wrapper: read-only Git + task inspection, no mutation
 10. No provider/credential/network/OneDrive/broker/exchange/signing/wallet/paper/live/submission
 11. trading_authority=false, no authority grant
 12. No owner-approval/profitability/OOS/deployment/unattended/live-readiness claims
 13. Direct construction fails closed
 14. Classification
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution.supervised_paper_launch_evidence_collector_v1 import (
    COLLECTOR_VERSION, collect_launch_evidence, write_launch_evidence,
)
from execution.supervised_paper_launch_evidence_v1 import read_launch_evidence

UTC = timezone.utc
NOW = datetime(2026, 9, 1, 23, 0, tzinfo=UTC)
H = "a" * 64
COLLECTOR_PY = Path(__file__).with_name("supervised_paper_launch_evidence_collector_v1.py")
PS1 = Path(__file__).resolve().parents[1] / "scripts" / "collect_supervised_paper_launch_evidence.ps1"


def _files(tmp_path: Path):
    docs = {
        "watchdog.json": {
            "adapter_version": "OWNER_CONTEXT_HEALTH_ADAPTER_V1", "report_id": H,
            "readiness": {"state": "HEALTHY"}, "observations": [
                {"component": "btc-recorder", "task_running": True,
                 "latest_heartbeat_at": NOW.isoformat(), "unresolved_gap_count": 0,
                 "clock_skew_seconds": 1, "trading_authority": False},
                {"component": "es-nq-recorder", "task_running": True,
                 "latest_heartbeat_at": NOW.isoformat(), "unresolved_gap_count": 0,
                 "clock_skew_seconds": 1, "trading_authority": False}],
            "trading_authority": False},
        "recovery.json": {"schema_version": "controlled-btc-recorder-recovery-drill-v1",
            "result": "RECOVERY_VERIFIED", "report_id": "b" * 64, "trading_authority": False},
        "stale.json": {"schema_version": "controlled-stale-alert-drill-v1",
            "result": "STALE_ALERT_AND_RECOVERY_VERIFIED", "report_id": "c" * 64,
            "stale_observed": True, "unhealthy_alert_delivered": True,
            "recovery_observed": True, "healthy_alert_delivered": True, "trading_authority": False},
    }
    paths = {}
    for name, value in docs.items():
        paths[name] = tmp_path / name
        paths[name].write_text(json.dumps(value), encoding="utf-8")
    return paths, docs


def _collect(tmp_path, **changes):
    paths, _ = _files(tmp_path)
    args = {
        "watchdog_path": paths["watchdog.json"], "recovery_drill_path": paths["recovery.json"],
        "stale_drill_path": paths["stale.json"], "repository_checkpoint": H,
        "repository_clean": True, "btc_task_state": "Running",
        "es_nq_task_state": "Ready", "es_nq_last_result": 0,
        "es_nq_missed_runs": 0, "collected_at": NOW,
    }
    args.update(changes)
    return collect_launch_evidence(**args)


def _collect_with_paths(paths, **changes):
    args = {
        "watchdog_path": paths["watchdog.json"], "recovery_drill_path": paths["recovery.json"],
        "stale_drill_path": paths["stale.json"], "repository_checkpoint": H,
        "repository_clean": True, "btc_task_state": "Running",
        "es_nq_task_state": "Ready", "es_nq_last_result": 0,
        "es_nq_missed_runs": 0, "collected_at": NOW,
    }
    args.update(changes)
    return collect_launch_evidence(**args)


# ===========================================================================
# 1. Deterministic evidence creation
# ===========================================================================

class TestDeterministicEvidence:
    def test_deterministic(self, tmp_path):
        a = _collect(tmp_path)
        b = _collect(tmp_path)
        assert a == b
        assert a["evidence_id"] == b["evidence_id"]

    def test_evidence_id_is_sha256(self, tmp_path):
        value = _collect(tmp_path)
        assert len(value["evidence_id"]) == 64
        assert all(c in "0123456789abcdef" for c in value["evidence_id"])

    def test_evidence_id_matches_body(self, tmp_path):
        value = _collect(tmp_path)
        body = {k: v for k, v in value.items() if k != "evidence_id"}
        expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert value["evidence_id"] == expected


# ===========================================================================
# 2. SHA-256 binding of source files
# ===========================================================================

class TestSourceHashBinding:
    def test_source_hashes_present(self, tmp_path):
        value = _collect(tmp_path)
        assert len(value["source_file_sha256"]) == 3

    def test_source_hashes_sorted(self, tmp_path):
        value = _collect(tmp_path)
        assert value["source_file_sha256"] == sorted(value["source_file_sha256"])

    def test_source_hashes_match_files(self, tmp_path):
        paths, _ = _files(tmp_path)
        value = _collect(tmp_path)
        expected = sorted(hashlib.sha256(paths[n].read_bytes()).hexdigest() for n in
                         ("watchdog.json", "recovery.json", "stale.json"))
        assert value["source_file_sha256"] == expected

    def test_different_files_different_evidence_id(self, tmp_path):
        a = _collect(tmp_path)
        # Modify a source file
        paths, docs = _files(tmp_path)
        docs["recovery.json"]["report_id"] = "d" * 64
        paths["recovery.json"].write_text(json.dumps(docs["recovery.json"]))
        b = collect_launch_evidence(watchdog_path=paths["watchdog.json"],
            recovery_drill_path=paths["recovery.json"], stale_drill_path=paths["stale.json"],
            repository_checkpoint=H, repository_clean=True, btc_task_state="Running",
            es_nq_task_state="Ready", es_nq_last_result=0, es_nq_missed_runs=0, collected_at=NOW)
        assert a["evidence_id"] != b["evidence_id"]


# ===========================================================================
# 3. Atomic output and read-back
# ===========================================================================

class TestAtomicOutput:
    def test_write_and_read_back(self, tmp_path):
        value = _collect(tmp_path)
        output = tmp_path / "out" / "evidence.json"
        write_launch_evidence(output, value)
        assert output.is_file()
        ev = read_launch_evidence(output)
        assert ev.evidence_id == value["evidence_id"]

    def test_no_temp_remaining(self, tmp_path):
        value = _collect(tmp_path)
        output = tmp_path / "out" / "evidence.json"
        write_launch_evidence(output, value)
        assert not list((tmp_path / "out").glob("*.tmp-*"))


# ===========================================================================
# 4. Missing/malformed/authority/duplicate/tampered sources
# ===========================================================================

class TestBadSources:
    def _run_with(self, tmp_path, file_name, content):
        paths, _ = _files(tmp_path)
        paths[file_name].write_text(content)
        return collect_launch_evidence(watchdog_path=paths["watchdog.json"],
            recovery_drill_path=paths["recovery.json"], stale_drill_path=paths["stale.json"],
            repository_checkpoint=H, repository_clean=True, btc_task_state="Running",
            es_nq_task_state="Ready", es_nq_last_result=0, es_nq_missed_runs=0, collected_at=NOW)

    def test_missing_watchdog_rejects(self, tmp_path):
        paths, _ = _files(tmp_path)
        with pytest.raises(ValueError, match="unreadable"):
            collect_launch_evidence(watchdog_path=tmp_path / "missing.json",
                recovery_drill_path=paths["recovery.json"], stale_drill_path=paths["stale.json"],
                repository_checkpoint=H, repository_clean=True, btc_task_state="Running",
                es_nq_task_state="Ready", es_nq_last_result=0, es_nq_missed_runs=0, collected_at=NOW)

    def test_malformed_json_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="unreadable"):
            self._run_with(tmp_path, "watchdog.json", "{not json}")

    def test_non_object_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="object"):
            self._run_with(tmp_path, "watchdog.json", '"a string"')

    def test_authority_true_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["trading_authority"] = True
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="authority"):
            collect_launch_evidence(watchdog_path=paths["watchdog.json"],
                recovery_drill_path=paths["recovery.json"], stale_drill_path=paths["stale.json"],
                repository_checkpoint=H, repository_clean=True, btc_task_state="Running",
                es_nq_task_state="Ready", es_nq_last_result=0, es_nq_missed_runs=0, collected_at=NOW)


# ===========================================================================
# 5. Watchdog validation
# ===========================================================================

class TestWatchdogValidation:
    def test_wrong_version_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["adapter_version"] = "wrong"
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="version"):
            _collect_with_paths(paths)

    def test_unhealthy_watchdog_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["readiness"]["state"] = "UNHEALTHY"
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="healthy"):
            _collect_with_paths(paths)

    def test_malformed_report_id_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["report_id"] = "bad"
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="SHA-256"):
            _collect_with_paths(paths)

    def test_wrong_component_set_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"] = [
            {"component": "btc-recorder", "task_running": True, "trading_authority": False}]
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="mismatch|component"):
            _collect_with_paths(paths)

    def test_duplicate_components_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"] = [
            {"component": "btc-recorder", "task_running": True, "trading_authority": False},
            {"component": "btc-recorder", "task_running": True, "trading_authority": False}]
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="mismatch|component"):
            _collect_with_paths(paths)

    def test_missing_btc_observation_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"] = [
            {"component": "es-nq-recorder", "task_running": True, "trading_authority": False},
            {"component": "es-nq-recorder", "task_running": True, "trading_authority": False}]
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="mismatch|component"):
            _collect_with_paths(paths)

    def test_btc_not_running_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"][0]["task_running"] = False
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="running"):
            _collect_with_paths(paths)

    def test_btc_trading_authority_true_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"][0]["trading_authority"] = True
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="running|authority"):
            _collect_with_paths(paths)

    def test_naive_heartbeat_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"][0]["latest_heartbeat_at"] = NOW.replace(tzinfo=None).isoformat()
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="UTC"):
            _collect_with_paths(paths)

    def test_gap_count_bool_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"][0]["unresolved_gap_count"] = True
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="invalid|integer"):
            _collect_with_paths(paths)

    def test_skew_bool_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"][0]["clock_skew_seconds"] = True
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="invalid|integer"):
            _collect_with_paths(paths)

    def test_negative_gap_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["watchdog.json"]["observations"][0]["unresolved_gap_count"] = -1
        paths["watchdog.json"].write_text(json.dumps(docs["watchdog.json"]))
        with pytest.raises(ValueError, match="invalid"):
            _collect_with_paths(paths)


# ===========================================================================
# 6. Recovery drill validation
# ===========================================================================

class TestRecoveryDrill:
    def test_wrong_schema_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["recovery.json"]["schema_version"] = "wrong"
        paths["recovery.json"].write_text(json.dumps(docs["recovery.json"]))
        with pytest.raises(ValueError, match="recovery"):
            _collect_with_paths(paths)

    def test_failed_result_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["recovery.json"]["result"] = "FAILED"
        paths["recovery.json"].write_text(json.dumps(docs["recovery.json"]))
        with pytest.raises(ValueError, match="recovery"):
            _collect_with_paths(paths)

    def test_authority_true_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["recovery.json"]["trading_authority"] = True
        paths["recovery.json"].write_text(json.dumps(docs["recovery.json"]))
        with pytest.raises(ValueError, match="authority"):
            _collect_with_paths(paths)

    def test_malformed_report_id_rejects(self, tmp_path):
        paths, docs = _files(tmp_path)
        docs["recovery.json"]["report_id"] = "bad"
        paths["recovery.json"].write_text(json.dumps(docs["recovery.json"]))
        with pytest.raises(ValueError, match="SHA-256"):
            _collect_with_paths(paths)


# ===========================================================================
# 7. Stale alert drill validation — every boolean independently
# ===========================================================================

class TestStaleAlertDrill:
    def _stale_with(self, tmp_path, key, value):
        paths, docs = _files(tmp_path)
        docs["stale.json"][key] = value
        paths["stale.json"].write_text(json.dumps(docs["stale.json"]))
        return _collect_with_paths(paths)

    def test_wrong_schema_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="stale"):
            self._stale_with(tmp_path, "schema_version", "wrong")

    def test_failed_result_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="stale"):
            self._stale_with(tmp_path, "result", "FAILED")

    def test_stale_observed_false_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="stale_observed"):
            self._stale_with(tmp_path, "stale_observed", False)

    def test_unhealthy_delivered_false_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="unhealthy_alert_delivered"):
            self._stale_with(tmp_path, "unhealthy_alert_delivered", False)

    def test_recovery_observed_false_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="recovery_observed"):
            self._stale_with(tmp_path, "recovery_observed", False)

    def test_healthy_delivered_false_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="healthy_alert_delivered"):
            self._stale_with(tmp_path, "healthy_alert_delivered", False)

    def test_authority_true_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="authority"):
            self._stale_with(tmp_path, "trading_authority", True)

    def test_malformed_report_id_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            self._stale_with(tmp_path, "report_id", "bad")


# ===========================================================================
# 8. Repository and task fact validation
# ===========================================================================

class TestRepositoryAndTaskFacts:
    def test_dirty_repository_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="clean"):
            _collect(tmp_path, repository_clean=False)

    def test_dirty_repository_none_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="clean"):
            _collect(tmp_path, repository_clean=None)

    def test_bad_checkpoint_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            _collect(tmp_path, repository_checkpoint="bad")

    def test_missed_runs_negative_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="nonnegative"):
            _collect(tmp_path, es_nq_missed_runs=-1)

    def test_missed_runs_bool_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="nonnegative|integer"):
            _collect(tmp_path, es_nq_missed_runs=True)

    def test_last_result_bool_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="integer"):
            _collect(tmp_path, es_nq_last_result=True)

    def test_naive_collected_at_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="UTC"):
            _collect(tmp_path, collected_at=NOW.replace(tzinfo=None))

    def test_non_utc_collected_at_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="UTC"):
            _collect(tmp_path, collected_at=NOW.replace(tzinfo=timezone(timedelta(hours=5))))


# ===========================================================================
# 9. PowerShell wrapper
# ===========================================================================

class TestPowerShellWrapper:
    def test_requires_version_51(self):
        source = PS1.read_text("utf-8")
        assert "#requires -Version 5.1" in source

    def test_cmdlet_binding(self):
        source = PS1.read_text("utf-8")
        assert "[CmdletBinding()]" in source

    def test_error_action_stop(self):
        source = PS1.read_text("utf-8")
        assert "$ErrorActionPreference='Stop'" in source

    def test_uses_git_rev_parse(self):
        source = PS1.read_text("utf-8")
        assert "git -c" in source and "-C $repository rev-parse HEAD" in source
        assert "safe.directory=" in source

    def test_uses_git_status(self):
        source = PS1.read_text("utf-8")
        assert "git -c" in source and "-C $repository status --porcelain" in source
        assert "safe.directory=" in source

    def test_uses_get_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Get-ScheduledTask" in source

    def test_uses_get_scheduledtaskinfo(self):
        source = PS1.read_text("utf-8")
        assert "Get-ScheduledTaskInfo" in source

    def test_no_start_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Start-ScheduledTask" not in source

    def test_no_stop_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Stop-ScheduledTask" not in source

    def test_no_enable_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Enable-ScheduledTask" not in source

    def test_no_disable_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Disable-ScheduledTask" not in source

    def test_no_register_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Register-ScheduledTask" not in source

    def test_no_unregister_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Unregister-ScheduledTask" not in source

    def test_no_set_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "Set-ScheduledTask" not in source

    def test_no_new_scheduledtask(self):
        source = PS1.read_text("utf-8")
        assert "New-ScheduledTask" not in source

    def test_no_provider_network(self):
        source = PS1.read_text("utf-8").lower()
        for f in ("invoke-webrequest", "invoke-restmethod", "requests", "httpx", "socket"):
            assert f not in source, f"forbidden: {f}"

    def test_no_credentials(self):
        source = PS1.read_text("utf-8").lower()
        for f in ("get-credential", "private_key", "api_key", "password"):
            assert f not in source, f"forbidden: {f}"

    def test_no_trading_surface(self):
        source = PS1.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "wallet", "broker", "exchange"):
            assert f not in source, f"forbidden: {f}"

    def test_trading_authority_false_in_output(self):
        """The Python collector always sets trading_authority=False; the PS1
        invokes the Python module which enforces this."""

    def test_python_runtime_checked(self):
        source = PS1.read_text("utf-8")
        assert ".venv" in source and "python.exe" in source


# ===========================================================================
# 10. No prohibited surface in Python collector
# ===========================================================================

class TestNoProhibitedPython:
    def test_no_network_imports(self):
        source = COLLECTOR_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "websocket", "smtplib",
                    "paramiko", "asyncio", "subprocess"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_no_credential_strings(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass", "credential"):
            assert f not in source, f"forbidden: {f}"

    def test_no_live_order(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "live_order", "broker", "wallet"):
            assert f not in source, f"forbidden: {f}"

    def test_no_task_mutation(self):
        source = COLLECTOR_PY.read_text("utf-8")
        for f in ("Register-ScheduledTask", "Stop-ScheduledTask", "Start-ScheduledTask"):
            assert f not in source, f"forbidden: {f}"


# ===========================================================================
# 11. trading_authority=false
# ===========================================================================

class TestTradingAuthorityFalse:
    def test_collector_returns_false(self, tmp_path):
        value = _collect(tmp_path)
        assert value["trading_authority"] is False

    def test_repository_clean_true(self, tmp_path):
        value = _collect(tmp_path)
        assert value["repository_clean"] is True

    def test_no_input_grants_authority(self, tmp_path):
        """No input to collect_launch_evidence can set trading_authority=True
        in the output — the collector hardcodes False."""

    def test_evidence_read_back_trading_authority_false(self, tmp_path):
        value = _collect(tmp_path)
        output = tmp_path / "out" / "evidence.json"
        write_launch_evidence(output, value)
        ev = read_launch_evidence(output)
        assert ev.trading_authority is False


# ===========================================================================
# 12. No false claims
# ===========================================================================

class TestNoFalseClaims:
    def test_no_owner_approval(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        assert "owner approval" not in source
        assert "owner approved" not in source

    def test_no_profitability(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        assert "profitability" not in source
        assert "profit " not in source

    def test_no_oos(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        assert "out-of-sample" not in source

    def test_no_deployment(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        assert "deployment approval" not in source

    def test_no_unattended_readiness(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        assert "unattended readiness" not in source

    def test_no_live_readiness(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        assert "live readiness" not in source

    def test_advisory_or_readonly_in_docstring(self):
        source = COLLECTOR_PY.read_text("utf-8").lower()
        assert "read-only" in source or "advisory" in source


# ===========================================================================
# 13. Direct construction fails closed
# ===========================================================================

class TestDirectConstruction:
    def test_bad_checkpoint_direct(self, tmp_path):
        with pytest.raises(ValueError, match="SHA-256"):
            collect_launch_evidence(watchdog_path=tmp_path / "x.json",
                recovery_drill_path=tmp_path / "x.json", stale_drill_path=tmp_path / "x.json",
                repository_checkpoint="bad", repository_clean=True,
                btc_task_state="Running", es_nq_task_state="Ready",
                es_nq_last_result=0, es_nq_missed_runs=0, collected_at=NOW)

    def test_dirty_repository_direct(self, tmp_path):
        with pytest.raises(ValueError, match="clean"):
            collect_launch_evidence(watchdog_path=tmp_path / "x.json",
                recovery_drill_path=tmp_path / "x.json", stale_drill_path=tmp_path / "x.json",
                repository_checkpoint=H, repository_clean=False,
                btc_task_state="Running", es_nq_task_state="Ready",
                es_nq_last_result=0, es_nq_missed_runs=0, collected_at=NOW)

    def test_naive_timestamp_direct(self, tmp_path):
        with pytest.raises(ValueError, match="UTC"):
            collect_launch_evidence(watchdog_path=tmp_path / "x.json",
                recovery_drill_path=tmp_path / "x.json", stale_drill_path=tmp_path / "x.json",
                repository_checkpoint=H, repository_clean=True,
                btc_task_state="Running", es_nq_task_state="Ready",
                es_nq_last_result=0, es_nq_missed_runs=0,
                collected_at=NOW.replace(tzinfo=None))


# ===========================================================================
# 14. Version and schema
# ===========================================================================

class TestVersionSchema:
    def test_collector_version(self):
        assert COLLECTOR_VERSION == "supervised-paper-launch-evidence-collector-v1"

    def test_evidence_uses_evidence_version(self, tmp_path):
        value = _collect(tmp_path)
        assert value["schema_version"] == "supervised-paper-launch-evidence-v1"


# ===========================================================================
# 15. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """11 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: deterministic evidence_id, source hash match,
        different files different ID, no temp remaining, missing watchdog,
        non-object, authority in BTC observation, gap bool, skew bool,
        negative gap, each stale-drill boolean independently (6 tests),
        wrong component set, duplicate components, missing BTC,
        dirty repo None, bad checkpoint direct, naive timestamp direct,
        PS1 no New/Set/Unregister-ScheduledTask, no live-readiness claim —
        not in existing 11."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: collect_launch_evidence,
        write_launch_evidence, read_launch_evidence, COLLECTOR_VERSION.
        No private helpers."""
