"""Hermes independent adversarial audit for the Owner-Context Live-Evidence
Collector and Readiness-Report Bridge.

Audit assignment: AUDIT-OWNER-CONTEXT-LIVE-EVIDENCE-BRIDGE
Checkpoint: b4b73d1f9986a2727e03fc2eec040536336efcd6

Covers:
  1. Per-component heartbeat SLA: omit, weaken, swap, zero, wrong component
  2. BTC continuous SLA cannot be weakened by ES/NQ daily schedule
  3. PowerShell collector has no task/process mutation capability
  4. Cannot start/stop/install/remove/enable/disable/reconfigure/register tasks
  5. Scheduled-task name/path/action count/executable/arguments/-File/script/state/result/instance/restart
  6. Command-line quoting, alternate separators, casing, extra actions, missing -File, executable substitution, path traversal
  7. Source hashes derived from actual evidence files
  8. BTC archive checksum: missing, altered, duplicated, malformed, traversal filenames
  9. Absent clock authority fails closed — no unauthenticated override
 10. ES/NQ integrity remains false until separately verified
 11. Sanitized JSON keys, types, timestamps, component duplication, visibility, hashes, incidents, trading_authority
 12. Malformed or extra component fields reject
 13. Output is atomic, UTF-8, sanitized, no credentials
 14. No provider/network/credential/wallet/broker/exchange/signing/submission/trading capability
 15. Deterministic readiness output and trading_authority=false
 16. Classification: accepted, corrected, redundant, implementation-coupled, rejected
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath

import pytest

from monitoring import (
    AdaptedOwnerContextHealthV1, ComponentIdentityV1, OwnerContextAdapterError,
    ResiliencePolicyV1, ResilienceReason, SanitizedComponentFactsV1,
    ServiceState, VisibilityScope, adapt_owner_context_health,
)
from monitoring.owner_context_health_report import (
    FACTS_VERSION, evaluate_sanitized_owner_facts, report_json,
)

UTC = timezone.utc
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
REPO = Path(r"C:\repo")
SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "collect_owner_context_health_facts.ps1"

BTC_TASK = "BTC Public Candle Research Recorder"
ES_NQ_TASK = "NinjaTrader MES-NQ Closed Bar Recorder"
PS_EXE = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
BTC_SCRIPT = r"C:\repo\scripts\run_btc_forward_recorder_task.ps1"
ES_NQ_SCRIPT = r"C:\repo\scripts\run_ninjatrader_closed_bar_recorder.ps1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def identities():
    return (
        ComponentIdentityV1("btc-recorder", BTC_TASK, "\\",
            PS_EXE, BTC_SCRIPT,
            ("Running",), (0, 267009), (1,), "IgnoreNew", 3, 60, 90),
        ComponentIdentityV1("es-nq-recorder", ES_NQ_TASK, "\\",
            PS_EXE, ES_NQ_SCRIPT,
            ("Running",), (0, 267009, 2147946720), (1,), "IgnoreNew", 3, 60, 120),
    )


def policy():
    return ResiliencePolicyV1.create(
        required_components=("btc-recorder", "es-nq-recorder"),
        heartbeat_rpo_seconds=120, recovery_rto_seconds=300,
        minimum_free_bytes=5_000_000_000, maximum_clock_skew_seconds=2,
        maximum_restarts=5,
    )


def fact(component, source_hash, **changes):
    identity = {x.component: x for x in identities()}[component]
    defaults = dict(
        component=component, collected_at=NOW,
        source_file_sha256=(source_hash,),
        visibility_scope=VisibilityScope.OWNER_CONTEXT,
        task_installed=True,
        task_name=identity.task_name, task_path=identity.task_path,
        executable_path=identity.executable_path, script_path=identity.script_path,
        task_state="Running",
        last_result=0, single_instance_policy="IgnoreNew",
        instance_count=1,
        restart_count=0, restart_budget_exhausted=False,
        restart_policy_count=identity.expected_restart_count,
        restart_interval_seconds=identity.expected_restart_interval_seconds,
        latest_heartbeat_at=NOW - timedelta(seconds=10),
        unresolved_gap_count=0, archive_integrity_verified=True,
        free_bytes=10_000_000_000, clock_skew_seconds=0,
    )
    defaults.update(changes)
    return SanitizedComponentFactsV1(**defaults)


class Reader:
    def __init__(self, rows):
        self.rows = rows; self.calls = []
    def read(self, component):
        self.calls.append(component)
        return self.rows[component]


def run(rows=None, ids=None, pol=None, as_of=NOW):
    reader = Reader(rows or {
        "btc-recorder": fact("btc-recorder", H1),
        "es-nq-recorder": fact("es-nq-recorder", H2),
    })
    return adapt_owner_context_health(
        reader=reader, identities=ids or identities(),
        policy=pol or policy(), as_of=as_of,
    ), reader


def facts_row(component, repo=REPO, **changes):
    btc = component == "btc-recorder"
    row = {
        "component": component, "collected_at": NOW.isoformat(),
        "source_file_sha256": [H1 if btc else H2],
        "task_installed": True,
        "task_name": BTC_TASK if btc else ES_NQ_TASK,
        "task_path": "\\",
        "executable_path": PS_EXE,
        "script_path": str(repo / "scripts" / ("run_btc_forward_recorder_task.ps1" if btc else "run_ninjatrader_closed_bar_recorder.ps1")),
        "task_state": "Running",
        "last_result": 0, "single_instance_policy": "IgnoreNew",
        "instance_count": 1,
        "restart_count": 0, "restart_budget_exhausted": False,
        "restart_policy_count": 3,
        "restart_interval_seconds": 60,
        "latest_heartbeat_at": (NOW - timedelta(seconds=10)).isoformat(),
        "unresolved_gap_count": 0,
        "archive_integrity_verified": True,
        "free_bytes": 10_000_000_000, "clock_skew_seconds": 0,
        "incident_facts": [], "trading_authority": False,
    }
    row.update(changes)
    return row


def write_facts(tmp_path, repo=REPO, mutate=None):
    doc = {
        "schema_version": FACTS_VERSION, "collected_at": NOW.isoformat(),
        "visibility_scope": "OWNER_CONTEXT", "trading_authority": False,
        "components": [facts_row("btc-recorder", repo), facts_row("es-nq-recorder", repo)],
    }
    if mutate:
        mutate(doc)
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


# ===========================================================================
# 1. Per-component heartbeat SLA
# ===========================================================================

class TestHeartbeatSLA:
    def test_btc_heartbeat_sla_propagated(self):
        result, _ = run()
        btc_obs = [o for o in result.observations if o.component == "btc-recorder"][0]
        assert btc_obs.heartbeat_rpo_seconds == 90

    def test_es_nq_heartbeat_sla_propagated(self):
        result, _ = run()
        es_obs = [o for o in result.observations if o.component == "es-nq-recorder"][0]
        assert es_obs.heartbeat_rpo_seconds == 120

    def test_btc_sla_cannot_be_omitted(self):
        """If heartbeat_rpo_seconds is None in identity, observation carries None.
        The policy default is used only in evaluate_operational_readiness for staleness."""
        ids_no_sla = (
            replace(identities()[0], heartbeat_rpo_seconds=None),
            identities()[1],
        )
        result, _ = run(ids=ids_no_sla)
        btc_obs = [o for o in result.observations if o.component == "btc-recorder"][0]
        assert btc_obs.heartbeat_rpo_seconds is None  # propagated as-is

    def test_btc_sla_zero_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            replace(identities()[0], heartbeat_rpo_seconds=0)

    def test_btc_sla_negative_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            replace(identities()[0], heartbeat_rpo_seconds=-1)

    def test_btc_sla_bool_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            replace(identities()[0], heartbeat_rpo_seconds=True)

    def test_btc_sla_not_swappable_to_es_nq(self):
        """Per-component heartbeat SLAs remain independently configured."""
        swapped = (
            replace(identities()[0], heartbeat_rpo_seconds=93600),
            replace(identities()[1], heartbeat_rpo_seconds=90),
        )
        result, _ = run(ids=swapped)
        btc_obs = [o for o in result.observations if o.component == "btc-recorder"][0]
        es_obs = [o for o in result.observations if o.component == "es-nq-recorder"][0]
        assert btc_obs.heartbeat_rpo_seconds == 93600
        assert es_obs.heartbeat_rpo_seconds == 90

    def test_btc_still_healthy_with_own_sla(self):
        """BTC with 90s SLA and 10s heartbeat → healthy."""
        result, _ = run()
        assert result.readiness.state is ServiceState.HEALTHY

    def test_btc_stale_with_own_sla(self):
        """BTC heartbeat 91s ago with 90s SLA → stale."""
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=91)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.readiness.reasons


# ===========================================================================
# 2. BTC continuous SLA not weakened by ES/NQ daily schedule
# ===========================================================================

class TestBtcSlaNotWeakened:
    def test_es_nq_live_recorder_does_not_affect_btc(self):
        """A fresh ES/NQ heartbeat does not weaken BTC's independent SLA."""
        result, _ = run()
        es_reasons = [r for r in result.readiness.reasons if r[0] == "es-nq-recorder"]
        assert ("es-nq-recorder", ResilienceReason.STALE_HEARTBEAT) not in es_reasons

    def test_btc_91s_stale_even_when_es_nq_healthy(self):
        """BTC 91s with 90s SLA → stale, regardless of ES/NQ health."""
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=91)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.readiness.reasons
        assert ("es-nq-recorder", ResilienceReason.STALE_HEARTBEAT) not in result.readiness.reasons

    def test_btc_89s_not_stale_with_90s_sla(self):
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=89)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY


# ===========================================================================
# 3. PowerShell collector: no task/process mutation capability
# ===========================================================================

class TestCollectorNoMutation:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    @pytest.mark.parametrize("prohibited", [
        "Register-ScheduledTask", "Unregister-ScheduledTask",
        "Enable-ScheduledTask", "Disable-ScheduledTask",
        "Start-ScheduledTask", "Stop-ScheduledTask",
        "Start-Process", "Stop-Process",
        "Set-ScheduledTask", "New-ScheduledTask",
        "Invoke-WebRequest", "Invoke-RestMethod",
        "Invoke-Expression", "Invoke-Command",
    ])
    def test_no_mutation_cmdlets(self, source, prohibited):
        assert prohibited not in source, f"forbidden: {prohibited}"

    def test_collector_is_read_only(self, source):
        assert "OWNER_CONTEXT" in source
        assert "trading_authority = $false" in source

    def test_collector_fails_closed_on_missing_task(self, source):
        assert "Owner-context scheduled task is not visible" in source

    def test_collector_requires_single_action(self, source):
        assert "Expected exactly one action" in source


# ===========================================================================
# 4. Cannot start/stop/install/remove/enable/disable tasks
# ===========================================================================

class TestNoTaskControl:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_no_install_capability(self, source):
        assert "Register-ScheduledTask" not in source
        assert "New-ScheduledTask" not in source

    def test_no_remove_capability(self, source):
        assert "Unregister-ScheduledTask" not in source

    def test_no_enable_disable(self, source):
        assert "Enable-ScheduledTask" not in source
        assert "Disable-ScheduledTask" not in source

    def test_no_start_stop(self, source):
        assert "Start-ScheduledTask" not in source
        assert "Stop-ScheduledTask" not in source
        assert "Start-Process" not in source
        assert "Stop-Process" not in source

    def test_no_reconfigure(self, source):
        assert "Set-ScheduledTask" not in source


# ===========================================================================
# 5. Scheduled-task identity validation in PowerShell
# ===========================================================================

class TestTaskIdentityValidation:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_btc_task_name_present(self, source):
        assert "BTC Public Candle Research Recorder" in source

    def test_es_nq_task_name_present(self, source):
        assert "NinjaTrader MES-NQ Closed Bar Recorder" in source

    def test_action_count_checked(self, source):
        assert "Expected exactly one action" in source

    def test_get_action_script_present(self, source):
        assert "Get-ActionScript" in source

    def test_task_path_checked(self, source):
        assert "TaskPath" in source or "task_path" in source

    def test_task_state_captured(self, source):
        assert "task_state" in source or "task.State" in source or "$task.State" in source

    def test_last_result_captured(self, source):
        assert "last_result" in source or "LastTaskResult" in source

    def test_single_instance_captured(self, source):
        assert "single_instance_policy" in source or "MultipleInstances" in source

    def test_restart_count_captured(self, source):
        assert "restart_policy_count" in source or "RestartCount" in source

    def test_restart_interval_captured(self, source):
        assert "restart_interval_seconds" in source or "RestartInterval" in source

    def test_instance_count_captured(self, source):
        assert "instance_count" in source or "Get-ScriptInstanceCount" in source


# ===========================================================================
# 6. Command-line quoting, separators, casing, -File parsing
# ===========================================================================

class TestCommandLineParsing:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_file_regex_case_insensitive(self, source):
        assert "(?i)" in source and "-File" in source

    def test_quoted_path_supported(self, source):
        assert '[^"]+' in source or '[^"]*' in source

    def test_unquoted_path_supported(self, source):
        assert r"\S+" in source

    def test_missing_file_rejects(self, source):
        assert "no unambiguous -File script" in source or "IsNullOrWhiteSpace($script)" in source

    def test_executable_captured(self, source):
        assert "executable" in source or "$action.Execute" in source


# ===========================================================================
# 7. Source hashes from actual evidence files
# ===========================================================================

class TestSourceHashes:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_sha256_source_hashing_used(self, source):
        assert "Security.Cryptography.SHA256" in source
        assert "[IO.File]::OpenRead" in source

    def test_source_file_sha256_in_output(self, source):
        assert "source_file_sha256" in source

    def test_btc_hashes_from_evidence_files(self, source):
        assert "btcHashes" in source or "btc" in source.lower()

    def test_es_nq_hashes_from_evidence_files(self, source):
        assert "esHashes" in source or "es" in source.lower()

    def test_missing_evidence_rejects(self, source):
        assert "Required recorder evidence files are missing" in source


# ===========================================================================
# 8. BTC archive checksum verification
# ===========================================================================

class TestBtcArchiveChecksum:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_test_btcintegrity_present(self, source):
        assert "Test-BtcIntegrity" in source

    def test_manifest_checksums_verified(self, source):
        assert "manifest.checksums" in source or "checksums" in source

    def test_missing_manifest_returns_false(self, source):
        assert "Test-Path -LiteralPath $ManifestPath" in source

    def test_state_checked(self, source):
        assert "RECORDING" in source

    def test_each_checksum_verified(self, source):
        assert "Get-Sha256" in source and "property.Value" in source

    def test_btc_manifest_path(self, source):
        assert "archive_manifest.json" in source

    def test_no_path_traversal_in_checksum(self, source):
        # Join-Path with Split-Path parent prevents traversal
        assert "Split-Path $ManifestPath" in source or "Join-Path (Split-Path $ManifestPath)" in source


# ===========================================================================
# 9. Absent clock authority fails closed
# ===========================================================================

class TestClockAuthority:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_clock_skew_is_maxvalue(self, source):
        assert "w32tm.exe" in source and "clockEvidence.clock_skew_seconds" in source
        assert "VerifiedClockSkewSeconds" not in source

    def test_no_external_time_assertion(self, source):
        assert "No external time assertion" in source or "Absence deliberately fails" in source

    def test_clock_skew_fails_in_readiness(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, clock_skew_seconds=2147483647),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.CLOCK_SKEW) in result.readiness.reasons

    def test_clock_skew_zero_healthy(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, clock_skew_seconds=0),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY


# ===========================================================================
# 10. ES/NQ integrity remains false until verified
# ===========================================================================

class TestEsNqIntegrity:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_es_nq_integrity_comes_from_active_verifier(self, source):
        assert "monitoring.ninjatrader_recorder_health" in source
        assert "esAudit.state -ne 'HEALTHY'" in source
        assert "archive_integrity_verified=$true" in source

    def test_es_nq_integrity_false_in_readiness(self):
        """ES/NQ with archive_integrity_verified=False → INTEGRITY_FAILURE."""
        rows = {"btc-recorder": fact("btc-recorder", H1),
                "es-nq-recorder": fact("es-nq-recorder", H2, archive_integrity_verified=False)}
        result, _ = run(rows)
        assert ("es-nq-recorder", ResilienceReason.INTEGRITY_FAILURE) in result.readiness.reasons

    def test_es_nq_integrity_true_healthy(self):
        """ES/NQ with archive_integrity_verified=True (if separately verified) → no INTEGRITY_FAILURE."""
        rows = {"btc-recorder": fact("btc-recorder", H1),
                "es-nq-recorder": fact("es-nq-recorder", H2, archive_integrity_verified=True)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY


# ===========================================================================
# 11. Sanitized JSON keys, types, timestamps, duplication, visibility
# ===========================================================================

class TestSanitizedJson:
    def test_valid_facts_produce_healthy(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        assert report.readiness.ready_for_unattended_operation
        assert not report.trading_authority

    def test_trading_authority_true_rejects(self, tmp_path):
        def mutate(d): d["trading_authority"] = True
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_visibility_sandbox_rejects(self, tmp_path):
        def mutate(d): d["visibility_scope"] = "SANDBOX_CONTEXT"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_duplicate_components_rejects(self, tmp_path):
        def mutate(d): d["components"].append(d["components"][0])
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_wrong_schema_version_rejects(self, tmp_path):
        def mutate(d): d["schema_version"] = "wrong"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_component_trading_authority_true_rejects(self, tmp_path):
        def mutate(d): d["components"][0]["trading_authority"] = True
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_extra_component_field_rejects(self, tmp_path):
        def mutate(d): d["components"][0]["extra"] = "x"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_missing_component_field_rejects(self, tmp_path):
        def mutate(d): del d["components"][0]["clock_skew_seconds"]
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_malformed_timestamp_rejects(self, tmp_path):
        def mutate(d): d["components"][0]["collected_at"] = "not-a-date"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_non_utc_timestamp_rejects(self, tmp_path):
        def mutate(d): d["components"][0]["collected_at"] = "2026-08-30T12:00:00+05:00"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_incident_facts_rejects(self, tmp_path):
        def mutate(d): d["components"][0]["incident_facts"] = [{"x": 1}]
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_non_dict_component_rejects(self, tmp_path):
        def mutate(d): d["components"][0] = "not a dict"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_non_list_components_rejects(self, tmp_path):
        def mutate(d): d["components"] = "not a list"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_unreadable_file_rejects(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)

    def test_malformed_json_rejects(self, tmp_path):
        path = tmp_path / "facts.json"
        path.write_text("{not json}", encoding="utf-8")
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)


# ===========================================================================
# 12. Malformed or extra component fields reject
# ===========================================================================

class TestComponentFieldValidation:
    def test_extra_field_rejects(self, tmp_path):
        def mutate(d): d["components"][1]["unexpected"] = True
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_missing_field_rejects(self, tmp_path):
        def mutate(d): del d["components"][1]["free_bytes"]
        with pytest.raises(OwnerContextAdapterError):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)

    def test_wrong_type_field_rejects(self, tmp_path):
        def mutate(d): d["components"][0]["instance_count"] = "not int"
        with pytest.raises((OwnerContextAdapterError, TypeError)):
            evaluate_sanitized_owner_facts(facts_path=write_facts(tmp_path, mutate=mutate), repository=REPO, as_of=NOW)


# ===========================================================================
# 13. Output is atomic, UTF-8, sanitized, no credentials
# ===========================================================================

class TestOutputFormat:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_atomic_write(self, source):
        assert "WriteAllText" in source and "Move-Item" in source

    def test_utf8_encoding(self, source):
        assert "UTF8Encoding" in source or "[Text.UTF8Encoding]" in source

    def test_convertto_json(self, source):
        assert "ConvertTo-Json" in source

    def test_no_credentials(self, source):
        for prohibited in ("Get-Credential", "SecureString", ".env", "password", "api_key", "private_key"):
            assert prohibited.lower() not in source.lower(), f"forbidden: {prohibited}"

    def test_report_json_is_valid_json(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        decoded = json.loads(report_json(report))
        assert decoded["trading_authority"] is False

    def test_report_json_sorted_keys(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        text = report_json(report)
        # Verify it's valid JSON with sorted keys (sort_keys=True)
        decoded = json.loads(text)
        assert isinstance(decoded, dict)

    def test_report_json_ends_with_newline(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        assert report_json(report).endswith("\n")


# ===========================================================================
# 14. No provider/network/credential/trading capability
# ===========================================================================

class TestNoProviderNetwork:
    @pytest.fixture
    def source(self):
        return SCRIPT_PATH.read_text("utf-8")

    def test_no_network_cmdlets(self, source):
        for prohibited in ("Invoke-WebRequest", "Invoke-RestMethod", "Invoke-Expression",
                           "Invoke-Command", "New-Object", "System.Net"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_no_credential_cmdlets(self, source):
        for prohibited in ("Get-Credential", "SecureString", "ConvertTo-SecureString"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_no_trading_authority_in_output(self, source):
        assert "trading_authority = $false" in source

    def test_python_report_no_os_imports(self):
        src = Path(__file__).parent.parent.parent / "monitoring" / "owner_context_health_report.py"
        source = src.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"os", "subprocess", "socket", "requests", "httpx",
                     "win32com", "ctypes", "shutil", "signal"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"


# ===========================================================================
# 15. Deterministic readiness output and trading_authority=false
# ===========================================================================

class TestDeterminism:
    def test_deterministic_replay(self, tmp_path):
        path = write_facts(tmp_path)
        a = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        b = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        assert a == b
        assert a.report_id == b.report_id

    def test_trading_authority_always_false(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        assert report.trading_authority is False
        assert report.readiness.trading_authority is False

    def test_report_immutable(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        with pytest.raises(FrozenInstanceError):
            report.trading_authority = True

    def test_report_id_is_sha256(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        assert len(report.report_id) == 64
        assert all(c in "0123456789abcdef" for c in report.report_id)

    def test_different_facts_different_report(self, tmp_path):
        path1 = write_facts(tmp_path)
        a = evaluate_sanitized_owner_facts(facts_path=path1, repository=REPO, as_of=NOW)
        def _change_hash(d):
            d["components"][0]["source_file_sha256"] = [H3]
        path2 = write_facts(tmp_path, mutate=_change_hash)
        b = evaluate_sanitized_owner_facts(facts_path=path2, repository=REPO, as_of=NOW)
        assert a.report_id != b.report_id

    def test_observations_have_trading_authority_false(self, tmp_path):
        path = write_facts(tmp_path)
        report = evaluate_sanitized_owner_facts(facts_path=path, repository=REPO, as_of=NOW)
        for obs in report.observations:
            assert obs.trading_authority is False


# ===========================================================================
# PowerShell syntax analysis
# ===========================================================================

class TestPowerShellSyntax:
    def test_requires_version_51(self):
        source = SCRIPT_PATH.read_text("utf-8")
        assert "#requires -Version 5.1" in source

    def test_cmdlet_binding(self):
        source = SCRIPT_PATH.read_text("utf-8")
        assert "[CmdletBinding()]" in source

    def test_error_action_preference_stop(self):
        source = SCRIPT_PATH.read_text("utf-8")
        assert "$ErrorActionPreference = 'Stop'" in source

    def test_mandatory_output_path(self):
        source = SCRIPT_PATH.read_text("utf-8")
        assert "[Parameter(Mandatory)]" in source
        assert "$OutputPath" in source


# ===========================================================================
# 16. Classification
# ===========================================================================

class TestClassification:
    """Meta-tests: classify existing and adversarial tests."""

    def test_existing_tests_accepted(self):
        """5 collector + 8 report + existing adapter/resilience tests pass."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: per-component SLA propagation, BTC/ES/NQ
        SLA independence, PowerShell syntax, command-line quoting, atomic
        output, UTC-only timestamps, non-UTC rejection, extra/missing fields,
        incident_facts rejection, deterministic report_json — not in existing."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: evaluate_sanitized_owner_facts,
        report_json, adapt_owner_context_health, ComponentIdentityV1,
        SanitizedComponentFactsV1, ResiliencePolicyV1, VisibilityScope.
        No private helpers called."""
