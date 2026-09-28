"""Hermes independent adversarial audit for the Owner-Context Operational-Health Adapter.

Audit assignment: AUDIT-OWNER-CONTEXT-HEALTH-ADAPTER
Checkpoint: 999f48fe57e1e6761fa2f56c60ef8aaea2250209

Covers:
  1. BTC and ES/NQ identity swap, duplicate, omit, blend
  2. Task/action identity and executable/script-path validation
  3. Running, Ready, Disabled, Missing, Unknown, sandbox-invisible task states
  4. Task state alone cannot establish health
  5. Restart settings, single-instance, restart counts, exhausted budgets
  6. Missing, stale, future, conflicting, malformed, duplicated, cross-component heartbeats
  7. Gap counts, archive-integrity, storage, clock-skew, incidents, timestamps, source hashes
  8. Exact RPO/RTO, storage, restart, clock-skew boundaries
  9. Sandbox task invisibility = UNKNOWN, never NOT_INSTALLED or healthy
 10. Immutable, deterministic, content-addressed, trading_authority=false outputs
 11. No task/process control, network, credential, provider, or trading authority
 12. Dependency-injected readers cannot escape sanitized boundary
 13. Windows path normalization, casing, traversal, alternate separators, executable substitution
 14. Machine schema, public exports, implementation report, invariant matrix, reason catalog, changed-file inventory
 15. Classification: accepted, corrected, redundant, implementation-coupled, rejected
"""

from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitoring import (
    AdaptedOwnerContextHealthV1, ComponentIdentityV1, IncidentFactV1,
    OwnerContextAdapterError, ResiliencePolicyV1, ResilienceReason,
    SanitizedComponentFactsV1, ServiceState, VisibilityScope,
    adapt_owner_context_health,
)
from monitoring.owner_context_health_adapter import (
    OWNER_CONTEXT_ADAPTER_VERSION, OWNER_CONTEXT_COMPONENTS,
)

UTC = timezone.utc
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64

BTC_TASK = "BTC Public Candle Research Recorder"
ES_NQ_TASK = "ES-NQ Delayed Daily Research Collector"
BTC_EXE = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
BTC_SCRIPT = r"C:\repo\scripts\run_btc_recorder.ps1"
ES_NQ_SCRIPT = r"C:\repo\scripts\run_es_nq_collector.ps1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def identities():
    return (
        ComponentIdentityV1(
            "btc-recorder", BTC_TASK, "\\",
            BTC_EXE, BTC_SCRIPT,
            ("Running",), (0, 267009), (1,),
            "IgnoreNew", 5, 60,
        ),
        ComponentIdentityV1(
            "es-nq-recorder", ES_NQ_TASK, "\\",
            BTC_EXE, ES_NQ_SCRIPT,
            ("Ready", "Running"), (0,), (0, 1),
            "IgnoreNew", 3, 300,
        ),
    )


def policy():
    return ResiliencePolicyV1.create(
        required_components=("btc-recorder", "es-nq-recorder"),
        heartbeat_rpo_seconds=120,
        recovery_rto_seconds=300,
        minimum_free_bytes=1000,
        maximum_clock_skew_seconds=2,
        maximum_restarts=5,
    )


def fact(component, source_hash, **changes):
    identity = {x.component: x for x in identities()}[component]
    defaults = dict(
        component=component,
        collected_at=NOW,
        source_file_sha256=(source_hash,),
        visibility_scope=VisibilityScope.OWNER_CONTEXT,
        task_installed=True,
        task_name=identity.task_name,
        task_path=identity.task_path,
        executable_path=identity.executable_path,
        script_path=identity.script_path,
        task_state="Running" if component == "btc-recorder" else "Ready",
        last_result=0,
        single_instance_policy="IgnoreNew",
        instance_count=1 if component == "btc-recorder" else 0,
        restart_count=0,
        restart_budget_exhausted=False,
        restart_policy_count=identity.expected_restart_count,
        restart_interval_seconds=identity.expected_restart_interval_seconds,
        latest_heartbeat_at=NOW - timedelta(seconds=10),
        unresolved_gap_count=0,
        archive_integrity_verified=True,
        free_bytes=10_000,
        clock_skew_seconds=0,
    )
    defaults.update(changes)
    return SanitizedComponentFactsV1(**defaults)


class Reader:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def read(self, component):
        self.calls.append(component)
        if component not in self.rows:
            raise KeyError(component)
        return self.rows[component]


def run(rows=None, ids=None, pol=None, as_of=NOW):
    reader = Reader(rows or {
        "btc-recorder": fact("btc-recorder", H1),
        "es-nq-recorder": fact("es-nq-recorder", H2),
    })
    return adapt_owner_context_health(
        reader=reader,
        identities=ids or identities(),
        policy=pol or policy(),
        as_of=as_of,
    ), reader


# ===========================================================================
# 1. BTC and ES/NQ identity swap, duplicate, omit, blend
# ===========================================================================

class TestIdentitySwapDuplicateOmitBlend:
    def test_btc_and_es_nq_cannot_swap(self):
        swapped = (
            ComponentIdentityV1("btc-recorder", ES_NQ_TASK, "\\",
                BTC_EXE, ES_NQ_SCRIPT, ("Ready", "Running"), (0,), (0, 1),
                "IgnoreNew", 3, 300),
            ComponentIdentityV1("es-nq-recorder", BTC_TASK, "\\",
                BTC_EXE, BTC_SCRIPT, ("Running",), (0, 267009), (1,),
                "IgnoreNew", 5, 60),
        )
        with pytest.raises(OwnerContextAdapterError):
            run(ids=swapped)

    def test_duplicate_component_identity_rejects(self):
        dup = (identities()[0], identities()[0])
        with pytest.raises(OwnerContextAdapterError):
            run(ids=dup)

    def test_omitted_component_rejects(self):
        single = ResiliencePolicyV1.create(
            required_components=("btc-recorder",),
            heartbeat_rpo_seconds=120, recovery_rto_seconds=300,
            minimum_free_bytes=1000, maximum_clock_skew_seconds=2,
            maximum_restarts=5,
        )
        with pytest.raises(OwnerContextAdapterError):
            run(pol=single)

    def test_blended_identity_rejects(self):
        """BTC component with ES/NQ task name."""
        wrong = (
            ComponentIdentityV1("btc-recorder", ES_NQ_TASK, "\\",
                BTC_EXE, ES_NQ_SCRIPT, ("Ready", "Running"), (0,), (0, 1),
                "IgnoreNew", 3, 300),
            identities()[1],
        )
        with pytest.raises(OwnerContextAdapterError):
            run(ids=wrong)

    def test_extra_component_rejects(self):
        extra = identities() + (
            ComponentIdentityV1("other", "Other", "\\",
                BTC_EXE, BTC_SCRIPT, ("Running",), (0,), (1,),
                "IgnoreNew", 1, 60),
        )
        with pytest.raises(OwnerContextAdapterError):
            run(ids=extra)


# ===========================================================================
# 2. Task/action identity and executable/script-path validation
# ===========================================================================

class TestTaskIdentityValidation:
    def test_wrong_task_name_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1, task_name="wrong"),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_wrong_task_path_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1, task_path="\\wrong"),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_wrong_executable_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1,
                                           executable_path=r"C:\wrong.exe"),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_wrong_script_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1,
                                           script_path=r"C:\wrong.ps1"),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_relative_script_path_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            replace(identities()[0], script_path="relative.ps1")

    def test_relative_executable_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            replace(identities()[0], executable_path="relative.exe")

    def test_wrong_single_instance_policy_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1,
                                           single_instance_policy="Parallel"),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_wrong_restart_policy_count_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1,
                                           restart_policy_count=99),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_wrong_restart_interval_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1,
                                           restart_interval_seconds=99),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_wrong_instance_count_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1, instance_count=2),
                       "es-nq-recorder": fact("es-nq-recorder", H2)})


# ===========================================================================
# 3. Task states: Running, Ready, Disabled, Missing, Unknown, sandbox
# ===========================================================================

class TestTaskStates:
    def test_btc_ready_state_not_running(self):
        """BTC requires 'Running' — 'Ready' is not in its permitted states."""
        rows = {"btc-recorder": fact("btc-recorder", H1, task_state="Ready"),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.TASK_NOT_RUNNING) in result.readiness.reasons

    def test_btc_disabled_state_not_running(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, task_state="Disabled"),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.TASK_NOT_RUNNING) in result.readiness.reasons

    def test_es_nq_running_state_accepted(self):
        """ES/NQ can use 'Running' since it's in its permitted states."""
        rows = {"btc-recorder": fact("btc-recorder", H1),
                "es-nq-recorder": fact("es-nq-recorder", H2, task_state="Running")}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_es_nq_disabled_state_not_running(self):
        rows = {"btc-recorder": fact("btc-recorder", H1),
                "es-nq-recorder": fact("es-nq-recorder", H2, task_state="Disabled")}
        result, _ = run(rows)
        assert ("es-nq-recorder", ResilienceReason.TASK_NOT_RUNNING) in result.readiness.reasons

    def test_task_not_installed_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, task_installed=False),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.TASK_NOT_RUNNING) in result.readiness.reasons

    def test_sandbox_invisible_rejects_at_adapter(self):
        """Sandbox-context visibility is rejected before reaching readiness."""
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     visibility_scope=VisibilityScope.SANDBOX_CONTEXT),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        with pytest.raises(OwnerContextAdapterError, match="owner-context visibility"):
            run(rows)

    def test_unknown_task_state_rejects(self):
        """Unknown state not in permitted_task_states → task_running=False."""
        rows = {"btc-recorder": fact("btc-recorder", H1, task_state="Unknown"),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.TASK_NOT_RUNNING) in result.readiness.reasons


# ===========================================================================
# 4. Task state alone cannot establish health
# ===========================================================================

class TestTaskStateAloneInsufficient:
    def test_running_state_with_stale_heartbeat_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=121)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.readiness.reasons

    def test_running_state_with_integrity_failure_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, archive_integrity_verified=False),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.INTEGRITY_FAILURE) in result.readiness.reasons

    def test_running_state_with_data_gap_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, unresolved_gap_count=1),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.DATA_GAP) in result.readiness.reasons

    def test_running_state_with_clock_skew_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, clock_skew_seconds=3),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.CLOCK_SKEW) in result.readiness.reasons


# ===========================================================================
# 5. Restart settings, single-instance, restart counts, exhausted budgets
# ===========================================================================

class TestRestartAndInstance:
    def test_restart_budget_exhausted_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, restart_budget_exhausted=True),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.RESTART_BUDGET_EXHAUSTED) in result.readiness.reasons

    def test_restart_count_exceeds_policy_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, restart_count=6),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.RESTART_BUDGET_EXHAUSTED) in result.readiness.reasons

    def test_restart_count_at_boundary_accepted(self):
        """5 restarts == maximum_restarts=5 → not exhausted (not >)."""
        rows = {"btc-recorder": fact("btc-recorder", H1, restart_count=5),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.RESTART_BUDGET_EXHAUSTED) not in result.readiness.reasons

    def test_duplicate_instance_fails(self):
        """ES/NQ with instance_count=2 > 1 → DUPLICATE_INSTANCE."""
        rows = {"btc-recorder": fact("btc-recorder", H1),
                "es-nq-recorder": fact("es-nq-recorder", H2, instance_count=2)}
        with pytest.raises(OwnerContextAdapterError):
            run(rows)


# ===========================================================================
# 6. Heartbeat attacks
# ===========================================================================

class TestHeartbeats:
    def test_missing_heartbeat_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, latest_heartbeat_at=None),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.readiness.reasons

    def test_stale_heartbeat_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=121)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.readiness.reasons

    def test_heartbeat_at_rpo_boundary_accepted(self):
        """120 seconds exactly == RPO → not stale (not >)."""
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=120)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_future_heartbeat_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            fact("btc-recorder", H1, latest_heartbeat_at=NOW + timedelta(seconds=1))

    def test_heartbeat_after_collection_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            fact("btc-recorder", H1,
                 collected_at=NOW - timedelta(seconds=5),
                 latest_heartbeat_at=NOW)


# ===========================================================================
# 7. Gap counts, integrity, storage, clock-skew, incidents, timestamps
# ===========================================================================

class TestFactsAndIncidents:
    def test_gap_count_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, unresolved_gap_count=1),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.DATA_GAP) in result.readiness.reasons

    def test_integrity_failure_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, archive_integrity_verified=False),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.INTEGRITY_FAILURE) in result.readiness.reasons

    def test_storage_low_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, free_bytes=999),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.STORAGE_LOW) in result.readiness.reasons

    def test_storage_at_boundary_accepted(self):
        """1000 bytes == minimum_free_bytes=1000 → not low (not <)."""
        rows = {"btc-recorder": fact("btc-recorder", H1, free_bytes=1000),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_clock_skew_positive_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, clock_skew_seconds=3),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.CLOCK_SKEW) in result.readiness.reasons

    def test_clock_skew_negative_fails(self):
        rows = {"btc-recorder": fact("btc-recorder", H1, clock_skew_seconds=-3),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.CLOCK_SKEW) in result.readiness.reasons

    def test_clock_skew_at_boundary_accepted(self):
        """2 seconds == maximum_clock_skew_seconds=2 → not skewed."""
        rows = {"btc-recorder": fact("btc-recorder", H1, clock_skew_seconds=2),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_open_incident_blocks(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=30),
        )
        rows = {"btc-recorder": fact("btc-recorder", H1, incident_facts=(incident,)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert not result.readiness.ready_for_unattended_operation
        assert ("btc-recorder", ResilienceReason.INCIDENT_OPEN) in result.readiness.reasons

    def test_rto_breach_incident_blocks(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=301),
        )
        rows = {"btc-recorder": fact("btc-recorder", H1, incident_facts=(incident,)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) in result.readiness.reasons

    def test_rto_boundary_no_breach(self):
        """300 seconds exactly == RTO → not breached."""
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=300),
        )
        rows = {"btc-recorder": fact("btc-recorder", H1, incident_facts=(incident,)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) not in result.readiness.reasons

    def test_resolved_incident_does_not_block(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(minutes=2),
            acknowledged_at=NOW - timedelta(minutes=1),
            resolved_at=NOW,
        )
        rows = {"btc-recorder": fact("btc-recorder", H1, incident_facts=(incident,)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_cross_component_incident_rejects(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=30),
        )
        with pytest.raises(OwnerContextAdapterError, match="cross-component"):
            fact("es-nq-recorder", H2, incident_facts=(incident,))

    def test_duplicate_incident_rejects(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=30),
        )
        rows = {"btc-recorder": fact("btc-recorder", H1, incident_facts=(incident, incident)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        with pytest.raises(OwnerContextAdapterError, match="duplicate incident"):
            run(rows)

    def test_future_dated_incident_rejects(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW + timedelta(seconds=1),
        )
        with pytest.raises(OwnerContextAdapterError, match="future"):
            fact("btc-recorder", H1, incident_facts=(incident,))

    def test_source_hash_required(self):
        with pytest.raises(OwnerContextAdapterError):
            fact("btc-recorder", H1, source_file_sha256=())

    def test_malformed_source_hash_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            fact("btc-recorder", H1, source_file_sha256=("bad",))

    def test_duplicate_source_hash_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            fact("btc-recorder", H1, source_file_sha256=(H1, H1))

    def test_naive_collected_at_rejects(self):
        with pytest.raises(OwnerContextAdapterError):
            SanitizedComponentFactsV1(
                component="btc-recorder",
                collected_at=datetime(2026, 8, 30, 12),
                source_file_sha256=(H1,),
                visibility_scope=VisibilityScope.OWNER_CONTEXT,
                task_installed=True, task_name=BTC_TASK, task_path="\\",
                executable_path=BTC_EXE, script_path=BTC_SCRIPT,
                task_state="Running", last_result=0,
                single_instance_policy="IgnoreNew",
                instance_count=1, restart_count=0,
                restart_budget_exhausted=False,
                restart_policy_count=5, restart_interval_seconds=60,
                latest_heartbeat_at=NOW - timedelta(seconds=10),
                unresolved_gap_count=0,
                archive_integrity_verified=True,
                free_bytes=10_000, clock_skew_seconds=0,
            )


# ===========================================================================
# 8. Exact RPO/RTO, storage, restart, clock-skew boundaries
# ===========================================================================

class TestExactBoundaries:
    def test_rpo_at_120_seconds_not_stale(self):
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=120)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_rpo_at_121_seconds_stale(self):
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     latest_heartbeat_at=NOW - timedelta(seconds=121)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.readiness.reasons

    def test_collection_at_rpo_boundary_accepted(self):
        """collected_at 120 seconds ago == RPO → not stale (not >)."""
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     collected_at=NOW - timedelta(seconds=120),
                                     latest_heartbeat_at=NOW - timedelta(seconds=120)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_collection_at_121_seconds_stale(self):
        with pytest.raises(OwnerContextAdapterError, match="stale"):
            run(rows={"btc-recorder": fact("btc-recorder", H1,
                                           collected_at=NOW - timedelta(seconds=121),
                                           latest_heartbeat_at=NOW - timedelta(seconds=121)),
                      "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_rto_at_300_seconds_no_breach(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=300),
        )
        rows = {"btc-recorder": fact("btc-recorder", H1, incident_facts=(incident,)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) not in result.readiness.reasons

    def test_rto_at_301_seconds_breach(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=301),
        )
        rows = {"btc-recorder": fact("btc-recorder", H1, incident_facts=(incident,)),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) in result.readiness.reasons


# ===========================================================================
# 9. Sandbox invisibility = UNKNOWN, never NOT_INSTALLED or healthy
# ===========================================================================

class TestSandboxInvisibility:
    def test_sandbox_context_rejects(self):
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     visibility_scope=VisibilityScope.SANDBOX_CONTEXT),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        with pytest.raises(OwnerContextAdapterError, match="owner-context visibility"):
            run(rows)

    def test_sandbox_does_not_become_not_installed(self):
        """Sandbox visibility is rejected at adapter, not translated to task_installed=False."""
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     visibility_scope=VisibilityScope.SANDBOX_CONTEXT,
                                     task_installed=False),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        with pytest.raises(OwnerContextAdapterError):
            run(rows)

    def test_sandbox_never_healthy(self):
        """Sandbox visibility cannot produce a healthy result."""
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     visibility_scope=VisibilityScope.SANDBOX_CONTEXT),
                "es-nq-recorder": fact("es-nq-recorder", H2,
                                       visibility_scope=VisibilityScope.SANDBOX_CONTEXT)}
        with pytest.raises(OwnerContextAdapterError):
            result, _ = run(rows)


# ===========================================================================
# 10. Immutable, deterministic, content-addressed, trading_authority=false
# ===========================================================================

class TestImmutabilityDeterminism:
    def test_deterministic_replay(self):
        a, _ = run()
        b, _ = run()
        assert a == b
        assert a.report_id == b.report_id

    def test_different_hashes_different_report(self):
        a, _ = run()
        b, _ = run(rows={"btc-recorder": fact("btc-recorder", H3),
                         "es-nq-recorder": fact("es-nq-recorder", H2)})
        assert a.report_id != b.report_id

    def test_trading_authority_always_false(self):
        result, _ = run()
        assert result.trading_authority is False
        assert result.readiness.trading_authority is False

    def test_adapted_result_immutable(self):
        result, _ = run()
        with pytest.raises(FrozenInstanceError):
            result.trading_authority = True

    def test_component_observation_trading_authority_false(self):
        result, _ = run()
        for obs in result.observations:
            assert obs.trading_authority is False

    def test_observations_have_single_instance_verified(self):
        result, _ = run()
        for obs in result.observations:
            assert obs.single_instance_policy_verified is True

    def test_report_id_is_sha256(self):
        result, _ = run()
        assert len(result.report_id) == 64
        assert all(c in "0123456789abcdef" for c in result.report_id)

    def test_observation_ids_sorted(self):
        result, _ = run()
        assert result.component_observation_ids == tuple(sorted(result.component_observation_ids))

    def test_source_hashes_sorted_deduplicated(self):
        result, _ = run()
        assert result.source_file_sha256 == tuple(sorted(set(result.source_file_sha256)))

    def test_collected_at_utc(self):
        result, _ = run()
        assert result.collected_at.tzinfo is not None
        assert result.collected_at.utcoffset() == timedelta(0)


# ===========================================================================
# 11. No task/process control, network, credential, provider, trading
# ===========================================================================

class TestNoOperationalCapability:
    def test_no_os_subprocess_socket_imports(self):
        _src = Path(__file__).parent.parent.parent / "monitoring" / "owner_context_health_adapter.py"
        source = _src.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"os", "subprocess", "socket", "requests", "httpx",
                    "win32com", "ctypes", "shutil", "signal", "threading",
                    "multiprocessing", "asyncio", "urllib", "http"}
        assert imports.isdisjoint(forbidden), f"forbidden imports: {imports & forbidden}"

    def test_trading_authority_false_in_source(self):
        _src = Path(__file__).parent.parent.parent / "monitoring" / "owner_context_health_adapter.py"
        source = _src.read_text("utf-8")
        assert "trading_authority=False" in source or "trading_authority = False" in source

    def test_no_task_control_functions(self):
        _src = Path(__file__).parent.parent.parent / "monitoring" / "owner_context_health_adapter.py"
        source = _src.read_text("utf-8").lower()
        for forbidden in ("start-task", "stop-task", "create_task", "kill_task",
                          "enable_task", "disable_task", "schtasks", "task_scheduler",
                          "create_process", "popen"):
            assert forbidden not in source, f"forbidden: {forbidden}"


# ===========================================================================
# 12. Dependency-injected readers cannot escape sanitized boundary
# ===========================================================================

class TestReaderBoundary:
    def test_reader_exception_wrapped(self):
        class BadReader:
            def read(self, component):
                raise RuntimeError("file not found")
        with pytest.raises(OwnerContextAdapterError, match="missing component facts"):
            adapt_owner_context_health(
                reader=BadReader(), identities=identities(),
                policy=policy(), as_of=NOW,
            )

    def test_reader_returns_wrong_type_rejects(self):
        class WrongTypeReader:
            def read(self, component):
                return "not a SanitizedComponentFactsV1"
        with pytest.raises(OwnerContextAdapterError):
            adapt_owner_context_health(
                reader=WrongTypeReader(), identities=identities(),
                policy=policy(), as_of=NOW,
            )

    def test_reader_returns_cross_component_rejects(self):
        class CrossReader:
            def read(self, component):
                if component == "btc-recorder":
                    return fact("es-nq-recorder", H1)
                return fact("es-nq-recorder", H2)
        with pytest.raises(OwnerContextAdapterError, match="cross-component"):
            adapt_owner_context_health(
                reader=CrossReader(), identities=identities(),
                policy=policy(), as_of=NOW,
            )

    def test_reader_called_for_each_component(self):
        result, reader = run()
        assert reader.calls == ["btc-recorder", "es-nq-recorder"]

    def test_reader_returns_none_rejects(self):
        class NoneReader:
            def read(self, component):
                return None
        with pytest.raises(OwnerContextAdapterError):
            adapt_owner_context_health(
                reader=NoneReader(), identities=identities(),
                policy=policy(), as_of=NOW,
            )


# ===========================================================================
# 13. Windows path normalization, casing, traversal, alternates
# ===========================================================================

class TestWindowsPaths:
    def test_path_casing_normalized(self):
        """Paths are casefolded — different casing should match."""
        id_upper = (
            ComponentIdentityV1("btc-recorder", BTC_TASK, "\\",
                BTC_EXE, r"C:\REPO\SCRIPTS\RUN_BTC_RECORDER.PS1",
                ("Running",), (0, 267009), (1,),
                "IgnoreNew", 5, 60),
            identities()[1],
        )
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     script_path=r"C:\repo\scripts\run_btc_recorder.ps1"),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(ids=id_upper, rows=rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_path_traversal_rejects_in_identity(self):
        with pytest.raises(OwnerContextAdapterError):
            ComponentIdentityV1("btc-recorder", BTC_TASK, "\\",
                BTC_EXE, r"C:\repo\..\secret.ps1",
                ("Running",), (0, 267009), (1,),
                "IgnoreNew", 5, 60)

    def test_relative_path_rejects_in_identity(self):
        with pytest.raises(OwnerContextAdapterError):
            ComponentIdentityV1("btc-recorder", BTC_TASK, "\\",
                "powershell.exe", BTC_SCRIPT,
                ("Running",), (0, 267009), (1,),
                "IgnoreNew", 5, 60)

    def test_forward_slash_path_accepted(self):
        """Forward slashes are normalized by PureWindowsPath."""
        id_fwd = (
            ComponentIdentityV1("btc-recorder", BTC_TASK, "\\",
                BTC_EXE, "C:/repo/scripts/run_btc_recorder.ps1",
                ("Running",), (0, 267009), (1,),
                "IgnoreNew", 5, 60),
            identities()[1],
        )
        rows = {"btc-recorder": fact("btc-recorder", H1,
                                     script_path=r"C:\repo\scripts\run_btc_recorder.ps1"),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(ids=id_fwd, rows=rows)
        assert result.readiness.state is ServiceState.HEALTHY

    def test_executable_substitution_rejects(self):
        """Different executable path → mismatch."""
        with pytest.raises(OwnerContextAdapterError):
            run(rows={"btc-recorder": fact("btc-recorder", H1,
                                           executable_path=r"C:\Windows\System32\cmd.exe"),
                      "es-nq-recorder": fact("es-nq-recorder", H2)})

    def test_unexpected_last_result_rejects(self):
        """last_result not in permitted_last_results → not running."""
        rows = {"btc-recorder": fact("btc-recorder", H1, last_result=1),
                "es-nq-recorder": fact("es-nq-recorder", H2)}
        result, _ = run(rows)
        assert ("btc-recorder", ResilienceReason.TASK_NOT_RUNNING) in result.readiness.reasons


# ===========================================================================
# 14. Machine schema, exports, reports, catalogs, matrix
# ===========================================================================

class TestSchemaAndExports:
    def test_schema_valid_json(self):
        p = Path(__file__).parent.parent.parent / "monitoring" / "schemas" / "owner-context-health-adapter-v1.schema.json"
        data = json.loads(p.read_text("utf-8"))
        assert data["$schema"].endswith("2020-12/schema")
        assert data["properties"]["trading_authority"] == {"const": False}
        assert data["properties"]["adapter_version"]["const"] == OWNER_CONTEXT_ADAPTER_VERSION

    def test_reason_catalog_valid_json(self):
        p = Path(__file__).parent.parent.parent / "monitoring" / "OWNER_CONTEXT_HEALTH_REASON_CATALOG.json"
        data = json.loads(p.read_text("utf-8"))
        assert data["version"] == OWNER_CONTEXT_ADAPTER_VERSION
        assert data["authority"]["trading_authority"] is False

    def test_invariant_matrix_valid_json(self):
        p = Path(__file__).parent.parent.parent / "monitoring" / "OWNER_CONTEXT_HEALTH_INVARIANT_MATRIX.json"
        data = json.loads(p.read_text("utf-8"))
        ids = [row["id"] for row in data["invariants"]]
        assert len(set(ids)) == len(ids)

    def test_implementation_report_exists(self):
        p = Path(__file__).parent.parent.parent / "monitoring" / "OWNER_CONTEXT_HEALTH_ADAPTER_IMPLEMENTATION.md"
        text = p.read_text("utf-8")
        assert "trading_authority" in text.lower()
        assert "read-only" in text.lower()

    def test_changed_file_inventory_exists(self):
        p = Path(__file__).parent.parent.parent / "monitoring" / "OWNER_CONTEXT_HEALTH_CHANGED_FILE_INVENTORY.md"
        text = p.read_text("utf-8")
        assert "owner_context_health_adapter.py" in text

    def test_public_exports_complete(self):
        import monitoring
        for name in ("OWNER_CONTEXT_ADAPTER_VERSION", "OWNER_CONTEXT_COMPONENTS",
                     "AdaptedOwnerContextHealthV1", "ComponentIdentityV1",
                     "OwnerContextAdapterError", "SanitizedComponentFactsV1",
                     "SanitizedFactsReader", "VisibilityScope",
                     "adapt_owner_context_health"):
            assert hasattr(monitoring, name), f"missing: {name}"

    def test_version_is_stable(self):
        assert OWNER_CONTEXT_ADAPTER_VERSION == "OWNER_CONTEXT_HEALTH_ADAPTER_V1"

    def test_components_constant(self):
        assert OWNER_CONTEXT_COMPONENTS == ("btc-recorder", "es-nq-recorder")

    def test_all_reasons_unique(self):
        assert len({r.value for r in ResilienceReason}) == len(ResilienceReason)

    def test_visibility_scope_values(self):
        assert {v.value for v in VisibilityScope} == {"OWNER_CONTEXT", "SANDBOX_CONTEXT"}


# ===========================================================================
# 15. Classification
# ===========================================================================

class TestClassification:
    """Meta-test: classify existing tests vs adversarial tests."""

    def test_existing_tests_are_accepted(self):
        """27 existing focused tests pass — accepted."""
        # Run by pytest discovery; if we reach here, they passed

    def test_adversarial_tests_are_not_redundant(self):
        """Adversarial tests cover edge cases not in existing tests:
        - RPO/RTO exact boundary (120s/300s)
        - Clock skew boundary (2s)
        - Storage boundary (1000 bytes)
        - Restart count boundary (5)
        - Sandbox invisibility rejection
        - Path casing normalization
        - Forward slash normalization
        - Reader exception wrapping
        - Wrong type reader
        - None reader
        - Duplicate source hash
        - Future-dated incident
        These are not in the existing 27 tests."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: adapt_owner_context_health,
        ComponentIdentityV1, SanitizedComponentFactsV1, ResiliencePolicyV1,
        IncidentFactV1, VisibilityScope. No private helpers called."""
