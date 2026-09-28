from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import ast
import json
from pathlib import Path

import pytest

from monitoring import (
    ComponentIdentityV1, IncidentFactV1, OwnerContextAdapterError, ResiliencePolicyV1,
    ResilienceReason, SanitizedComponentFactsV1, ServiceState, VisibilityScope,
    adapt_owner_context_health,
)

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
H1 = "1" * 64
H2 = "2" * 64


class Reader:
    def __init__(self, rows): self.rows = rows; self.calls = []
    def read(self, component): self.calls.append(component); return self.rows[component]


def identities():
    return (
        ComponentIdentityV1("btc-recorder", "BTC Public Candle Research Recorder", "\\",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\repo\scripts\run_btc_recorder.ps1", ("Running",), (0, 267009), (1,),
            "IgnoreNew", 5, 60),
        ComponentIdentityV1("es-nq-recorder", "ES-NQ Delayed Daily Research Collector", "\\",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\repo\scripts\run_es_nq_collector.ps1", ("Ready", "Running"), (0,), (0, 1),
            "IgnoreNew", 3, 300),
    )


def policy():
    return ResiliencePolicyV1.create(required_components=("btc-recorder", "es-nq-recorder"),
        heartbeat_rpo_seconds=120, recovery_rto_seconds=300, minimum_free_bytes=1000,
        maximum_clock_skew_seconds=2, maximum_restarts=5)


def fact(component, source_hash):
    identity = {x.component: x for x in identities()}[component]
    return SanitizedComponentFactsV1(component, NOW, (source_hash,),
        VisibilityScope.OWNER_CONTEXT, True, identity.task_name, identity.task_path,
        identity.executable_path, identity.script_path,
        "Running" if component == "btc-recorder" else "Ready", 0, "IgnoreNew",
        1 if component == "btc-recorder" else 0, 0,
        False, identity.expected_restart_count, identity.expected_restart_interval_seconds,
        NOW - timedelta(seconds=10), 0, True, 10_000, 0)


def run(rows=None, as_of=NOW):
    reader = Reader(rows or {"btc-recorder": fact("btc-recorder", H1),
                             "es-nq-recorder": fact("es-nq-recorder", H2)})
    return adapt_owner_context_health(reader=reader, identities=identities(),
                                      policy=policy(), as_of=as_of), reader


def test_valid_owner_context_is_deterministic_immutable_and_advisory_only():
    first, reader = run(); second, _ = run()
    assert first == second and first.report_id == second.report_id
    assert first.readiness.state is ServiceState.HEALTHY
    assert first.readiness.ready_for_unattended_operation
    assert not first.trading_authority and not first.readiness.trading_authority
    assert reader.calls == ["btc-recorder", "es-nq-recorder"]
    assert first.source_file_sha256 == (H1, H2)
    with pytest.raises(FrozenInstanceError): first.trading_authority = True


def test_ready_is_component_specific_and_task_state_alone_never_suffices():
    rows = {"btc-recorder": replace(fact("btc-recorder", H1), task_state="Ready"),
            "es-nq-recorder": fact("es-nq-recorder", H2)}
    result, _ = run(rows)
    assert ("btc-recorder", ResilienceReason.TASK_NOT_RUNNING) in result.readiness.reasons


def test_identity_propagates_component_heartbeat_sla():
    rows = {"btc-recorder": fact("btc-recorder", H1),
            "es-nq-recorder": fact("es-nq-recorder", H2)}
    configured = tuple(replace(item, heartbeat_rpo_seconds=90 if item.component == "btc-recorder" else 93600)
                       for item in identities())
    result = adapt_owner_context_health(reader=Reader(rows), identities=configured,
        policy=policy(), as_of=NOW)
    assert tuple(x.heartbeat_rpo_seconds for x in result.observations) == (90, 93600)
    rows["btc-recorder"] = replace(fact("btc-recorder", H1), archive_integrity_verified=False)
    result, _ = run(rows)
    assert result.readiness.state is ServiceState.UNHEALTHY


@pytest.mark.parametrize("change", [
    {"visibility_scope": VisibilityScope.SANDBOX_CONTEXT},
    {"component": "es-nq-recorder"},
    {"collected_at": NOW + timedelta(seconds=1)},
    {"collected_at": NOW - timedelta(seconds=121), "latest_heartbeat_at": NOW - timedelta(seconds=122)},
    {"task_name": "wrong"}, {"task_path": "\\wrong"},
    {"executable_path": r"C:\wrong.exe"}, {"script_path": r"C:\wrong.ps1"},
    {"single_instance_policy": "Parallel"}, {"restart_policy_count": 99},
    {"restart_interval_seconds": 99}, {"instance_count": 2},
])
def test_missing_stale_future_cross_component_or_mismatched_facts_fail_closed(change):
    rows = {"btc-recorder": replace(fact("btc-recorder", H1), **change),
            "es-nq-recorder": fact("es-nq-recorder", H2)}
    with pytest.raises(OwnerContextAdapterError): run(rows)


@pytest.mark.parametrize(("change", "reason"), [
    ({"task_installed": False}, ResilienceReason.TASK_NOT_RUNNING),
    ({"last_result": 1}, ResilienceReason.TASK_NOT_RUNNING),
    ({"latest_heartbeat_at": NOW - timedelta(seconds=121)}, ResilienceReason.STALE_HEARTBEAT),
    ({"restart_budget_exhausted": True}, ResilienceReason.RESTART_BUDGET_EXHAUSTED),
    ({"unresolved_gap_count": 1}, ResilienceReason.DATA_GAP),
    ({"archive_integrity_verified": False}, ResilienceReason.INTEGRITY_FAILURE),
    ({"free_bytes": 999}, ResilienceReason.STORAGE_LOW),
    ({"clock_skew_seconds": 3}, ResilienceReason.CLOCK_SKEW),
])
def test_sanitized_controls_map_to_existing_fail_closed_reasons(change, reason):
    rows = {"btc-recorder": replace(fact("btc-recorder", H1), **change),
            "es-nq-recorder": fact("es-nq-recorder", H2)}
    result, _ = run(rows)
    assert ("btc-recorder", reason) in result.readiness.reasons


def test_source_hashes_are_required_and_content_address_the_report():
    changed, _ = run({"btc-recorder": fact("btc-recorder", "3" * 64),
                      "es-nq-recorder": fact("es-nq-recorder", H2)})
    baseline, _ = run()
    assert changed.report_id != baseline.report_id
    shared, _ = run({"btc-recorder": fact("btc-recorder", H1),
                     "es-nq-recorder": fact("es-nq-recorder", H1)})
    assert shared.source_file_sha256 == (H1,)


def test_invalid_hash_timestamp_path_and_policy_identity_reject():
    with pytest.raises(OwnerContextAdapterError): replace(fact("btc-recorder", H1), source_file_sha256=("bad",))
    with pytest.raises(OwnerContextAdapterError): replace(fact("btc-recorder", H1), latest_heartbeat_at=NOW + timedelta(seconds=1))
    with pytest.raises(OwnerContextAdapterError): replace(identities()[0], script_path="relative.ps1")
    bad_policy = ResiliencePolicyV1.create(required_components=("btc-recorder",),
        heartbeat_rpo_seconds=1, recovery_rto_seconds=1, minimum_free_bytes=1,
        maximum_clock_skew_seconds=1, maximum_restarts=1)
    with pytest.raises(OwnerContextAdapterError):
        adapt_owner_context_health(reader=Reader({}), identities=identities(), policy=bad_policy, as_of=NOW)


def test_duplicate_and_cross_component_incidents_fail_closed():
    incident = IncidentFactV1.create(component="btc-recorder", reason=ResilienceReason.DATA_GAP,
                                     detected_at=NOW - timedelta(seconds=30))
    rows = {"btc-recorder": replace(fact("btc-recorder", H1), incident_facts=(incident, incident)),
            "es-nq-recorder": fact("es-nq-recorder", H2)}
    with pytest.raises(OwnerContextAdapterError, match="duplicate incident"):
        run(rows)
    with pytest.raises(OwnerContextAdapterError, match="cross-component"):
        replace(fact("es-nq-recorder", H2), incident_facts=(incident,))


def test_machine_schema_catalog_and_matrix_are_valid_json_contracts():
    root = Path(__file__).parent
    schema = json.loads((root / "schemas/owner-context-health-adapter-v1.schema.json").read_text("utf-8"))
    catalog = json.loads((root / "OWNER_CONTEXT_HEALTH_REASON_CATALOG.json").read_text("utf-8"))
    matrix = json.loads((root / "OWNER_CONTEXT_HEALTH_INVARIANT_MATRIX.json").read_text("utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["properties"]["trading_authority"] == {"const": False}
    assert catalog["authority"]["trading_authority"] is False
    assert len({row["id"] for row in matrix["invariants"]}) == len(matrix["invariants"])


def test_adapter_has_no_operational_or_trading_dependency():
    source = Path(__file__).with_name("owner_context_health_adapter.py").read_text("utf-8")
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(ast.parse(source))
               if isinstance(node, ast.Import)}
    imports.update(node.module.split(".")[0] for node in ast.walk(ast.parse(source))
                   if isinstance(node, ast.ImportFrom) and node.module and node.level == 0)
    assert imports.isdisjoint({"os", "subprocess", "socket", "requests", "httpx", "win32com"})
    assert "trading_authority=False" in source
