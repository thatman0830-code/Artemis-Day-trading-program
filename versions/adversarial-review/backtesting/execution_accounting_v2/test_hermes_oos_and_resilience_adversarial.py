"""Hermes independent adversarial audit for OOS Evidence Readiness and
Institutional Operational Resilience.

Audit assignment: AUDIT-OOS-AND-OPERATIONAL-RESILIENCE

Covers OOS objectives:
  - BTC/ES/NQ market isolation
  - File paths, hashes, counts, coverage, fingerprints
  - Partition ordering, overlap, half-open boundaries
  - Missing interval intersecting UNTOUCHED_OOS fails closed
  - Authoritative-evidence coverage, chronology, plan freezing
  - No strategy/provider/credential/execution/trading capability

Covers operational-resilience objectives:
  - Missing, stale, future, duplicate observations
  - Exactly-one-instance enforcement
  - Restart-budget, storage, integrity, data-gap, clock-skew gates
  - RPO and RTO exact boundaries
  - Incident detection, acknowledgement, resolution, chronology
  - Unresolved incidents and RTO breaches block unattended readiness
  - Unexpected trading_authority always blocks readiness
  - No health result can grant trading authority
  - Deterministic identities and dataclass tampering
  - Redundant, incorrect, implementation-coupled tests
  - Public exports and documentation claims
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

# OOS evidence imports
from backtesting.execution_accounting_v2.oos_evidence import (
    OOS_EVIDENCE_VERSION, AuthorityEvidenceV1, EvidenceFileV1,
    FrozenPartitionV1, MissingIntervalV1, OOSReadinessError,
    OOSReadinessPlanV1, OOSReadinessReason,
)
from backtesting.execution_accounting_v2.reporting_validation import (
    EvidencePartition,
)

# Operational resilience imports
from monitoring.operational_resilience import (
    RESILIENCE_VERSION, ComponentObservationV1, IncidentFactV1,
    OperationalReadinessV1, ResiliencePolicyV1, ResilienceReason,
    ServiceState, evaluate_operational_readiness,
)


UTC = timezone.utc
T = datetime(2025, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 8, 30, tzinfo=UTC)
H = "a" * 64


# ---------------------------------------------------------------------------
# OOS Evidence helpers
# ---------------------------------------------------------------------------

def oos_evidence(path="btc.csv", start=T, end=T + timedelta(days=90)):
    return EvidenceFileV1(path, H, 100, 90, "1d", start, end)

def oos_partitions():
    return (
        FrozenPartitionV1(EvidencePartition.TRAINING, T, T + timedelta(days=30)),
        FrozenPartitionV1(EvidencePartition.VALIDATION,
                          T + timedelta(days=30), T + timedelta(days=60)),
        FrozenPartitionV1(EvidencePartition.UNTOUCHED_OOS,
                          T + timedelta(days=60), T + timedelta(days=90)),
    )

def oos_authority(kind="fees", start=T, end=T + timedelta(days=90)):
    return AuthorityEvidenceV1(
        kind, "official", H, start, end,
        start - timedelta(days=1), T + timedelta(days=91),
    )

def oos_plan(**changes):
    values = dict(
        market="BTC", dataset_id="dataset",
        files=(oos_evidence(),),
        missing_intervals=(),
        authorities=(oos_authority(),),
        required_authority_kinds=("fees",),
        partitions=oos_partitions(),
        frozen_at=T + timedelta(days=92),
    )
    values.update(changes)
    return OOSReadinessPlanV1.create(**values)


# ---------------------------------------------------------------------------
# Operational resilience helpers
# ---------------------------------------------------------------------------

def policy():
    return ResiliencePolicyV1.create(
        required_components=("btc-recorder", "es-nq-recorder"),
        heartbeat_rpo_seconds=120,
        recovery_rto_seconds=300,
        minimum_free_bytes=1_000_000,
        maximum_clock_skew_seconds=2,
        maximum_restarts=5,
    )

def obs(component):
    return ComponentObservationV1(
        component, NOW, NOW - timedelta(seconds=10), True,
        1, 0, False, 0, True, 10_000_000, 0,
    )

def eval_ready(*, observations=None, incidents=(), as_of=NOW):
    rows = observations or (obs("btc-recorder"), obs("es-nq-recorder"))
    return evaluate_operational_readiness(
        policy=policy(), observations=rows,
        incidents=incidents, as_of=as_of,
    )


# ===========================================================================
# OOS: Market isolation
# ===========================================================================

class TestOOSMarketIsolation:
    @pytest.mark.parametrize("market", ("BTC", "ES", "NQ"))
    def test_each_market_creates_plan(self, market):
        assert oos_plan(market=market).market == market

    def test_unknown_market_rejects(self):
        with pytest.raises(OOSReadinessError):
            oos_plan(market="ALL")

    def test_market_isolation_in_plan_id(self):
        assert oos_plan(market="BTC").plan_id != oos_plan(market="ES").plan_id


# ===========================================================================
# OOS: Path, hash, count, fingerprint
# ===========================================================================

class TestOOSPathsAndHashes:
    @pytest.mark.parametrize("bad_path", (
        "C:/secret.csv", "../secret.csv", "/secret.csv",
        "data/../secret.csv",
    ))
    def test_path_traversal_rejects(self, bad_path):
        with pytest.raises(OOSReadinessError):
            oos_evidence(path=bad_path)

    def test_duplicate_files_rejects(self):
        with pytest.raises(OOSReadinessError):
            oos_plan(files=(oos_evidence(), oos_evidence()))

    def test_malformed_hash_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", "X" * 64, 100, 90, "1d", T,
                           T + timedelta(days=90))

    def test_zero_byte_count_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", H, 0, 90, "1d", T,
                           T + timedelta(days=90))

    def test_zero_record_count_rejects(self):
        with pytest.raises(OOSReadinessError):
            EvidenceFileV1("ok.csv", H, 100, 0, "1d", T,
                           T + timedelta(days=90))

    def test_fingerprint_tampering_rejects(self):
        with pytest.raises((OOSReadinessError, ValueError, FrozenInstanceError)):
            replace(oos_plan(), plan_id="b" * 64)


# ===========================================================================
# OOS: Partition ordering, overlap, boundaries
# ===========================================================================

class TestOOSPartitions:
    def test_reversed_order_rejects(self):
        with pytest.raises(OOSReadinessError):
            oos_plan(partitions=tuple(reversed(oos_partitions())))

    def test_overlapping_rejects(self):
        overlapping = list(oos_partitions())
        overlapping[1] = replace(overlapping[1],
                                 start_inclusive=T + timedelta(days=29))
        with pytest.raises(OOSReadinessError):
            oos_plan(partitions=tuple(overlapping))

    def test_outside_coverage_rejects(self):
        with pytest.raises(OOSReadinessError):
            oos_plan(files=(oos_evidence(start=T + timedelta(days=1)),))

    def test_paper_partition_rejects(self):
        with pytest.raises(ValueError):
            FrozenPartitionV1(EvidencePartition.PAPER, T, T + timedelta(days=30))


# ===========================================================================
# OOS: Missing interval intersecting UNTOUCHED_OOS
# ===========================================================================

class TestOOSMissingInterval:
    def test_oos_gap_rejects(self):
        gap = MissingIntervalV1("1d", T + timedelta(days=70),
                                T + timedelta(days=71), "outage")
        with pytest.raises(OOSReadinessError) as exc:
            oos_plan(missing_intervals=(gap,))
        assert exc.value.reason is OOSReadinessReason.OOS_GAP

    def test_training_gap_accepted(self):
        gap = MissingIntervalV1("1d", T + timedelta(days=2),
                                T + timedelta(days=3), "outage")
        assert oos_plan(missing_intervals=(gap,)).missing_intervals == (gap,)

    def test_gap_at_oos_start_boundary_accepted(self):
        """Gap ending exactly at OOS start → not OOS_GAP (half-open)."""
        gap = MissingIntervalV1("1d", T + timedelta(days=59),
                                T + timedelta(days=60), "boundary")
        assert oos_plan(missing_intervals=(gap,)).missing_intervals == (gap,)

    def test_gap_at_oos_end_boundary_accepted(self):
        """Gap starting exactly at OOS end → not OOS_GAP (half-open)."""
        gap = MissingIntervalV1("1d", T + timedelta(days=90),
                                T + timedelta(days=91), "boundary")
        assert oos_plan(missing_intervals=(gap,)).missing_intervals == (gap,)


# ===========================================================================
# OOS: Authority coverage and chronology
# ===========================================================================

class TestOOSAuthority:
    def test_missing_authority_rejects(self):
        with pytest.raises(OOSReadinessError):
            oos_plan(required_authority_kinds=("fees", "instrument"))

    def test_authority_gap_rejects(self):
        short = oos_authority(end=T + timedelta(days=80))
        with pytest.raises(OOSReadinessError) as exc:
            oos_plan(authorities=(short,))
        assert exc.value.reason is OOSReadinessReason.AUTHORITY_GAP

    def test_contiguous_authority_accepted(self):
        first = oos_authority(end=T + timedelta(days=75))
        second = oos_authority(start=T + timedelta(days=75),
                               end=T + timedelta(days=90))
        assert oos_plan(authorities=(first, second)).ready

    def test_late_published_rejects(self):
        with pytest.raises(OOSReadinessError):
            replace(oos_authority(), published_at=T + timedelta(seconds=1))

    def test_post_freeze_capture_rejects(self):
        late = replace(oos_authority(), captured_at=T + timedelta(days=100))
        with pytest.raises(OOSReadinessError):
            oos_plan(authorities=(late,))

    def test_required_kinds_must_be_sorted(self):
        with pytest.raises(ValueError):
            oos_plan(required_authority_kinds=("instrument", "fees"))


# ===========================================================================
# OOS: Immutability and determinism
# ===========================================================================

class TestOOSImmutability:
    def test_plan_immutable(self):
        with pytest.raises(FrozenInstanceError):
            oos_plan().market = "ES"

    def test_plan_id_deterministic(self):
        assert oos_plan().plan_id == oos_plan().plan_id

    def test_evidence_immutable(self):
        with pytest.raises(FrozenInstanceError):
            oos_evidence().sha256 = "b" * 64


# ===========================================================================
# OOS: Import isolation
# ===========================================================================

class TestOOSImportIsolation:
    def test_no_provider_imports(self):
        import inspect
        import backtesting.execution_accounting_v2.oos_evidence as module
        source = inspect.getsource(module)
        import_lines = [l for l in source.split("\n")
                        if l.strip().startswith("import ")
                        or l.strip().startswith("from ")]
        joined = "\n".join(import_lines).lower()
        for forbidden in ("requests", "private_key", "submit_order",
                         "broker", "wallet", "credential", "collector",
                         "recorder", "scheduledtask"):
            assert forbidden not in joined


# ===========================================================================
# OOS: Schema verification
# ===========================================================================

class TestOOSSchema:
    def test_schema_valid_json(self):
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert data["$id"] == "oos-evidence-readiness-v1.schema.json"

    def test_schema_market_enum(self):
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert set(data["properties"]["market"]["enum"]) == {"BTC", "ES", "NQ"}

    def test_schema_version_const(self):
        p = (Path(__file__).parent / "schemas"
             / "oos-evidence-readiness-v1.schema.json")
        data = json.loads(p.read_text())
        assert data["properties"]["version"]["const"] == OOS_EVIDENCE_VERSION


# ===========================================================================
# Operational resilience: Missing, stale, future, duplicate observations
# ===========================================================================

class TestResilienceObservations:
    def test_healthy_deterministic(self):
        a = eval_ready()
        b = eval_ready()
        assert a == b
        assert a.state is ServiceState.HEALTHY
        assert a.ready_for_unattended_operation

    def test_missing_component_fails(self):
        result = eval_ready(observations=(obs("btc-recorder"),))
        assert not result.ready_for_unattended_operation
        assert ("es-nq-recorder", ResilienceReason.MISSING_COMPONENT) in result.reasons

    def test_stale_heartbeat_fails(self):
        bad = replace(obs("btc-recorder"),
                      latest_heartbeat_at=NOW - timedelta(seconds=121))
        result = eval_ready(observations=(bad, obs("es-nq-recorder")))
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.reasons

    def test_future_observation_fails(self):
        future = replace(obs("btc-recorder"),
                         observed_at=NOW + timedelta(seconds=1),
                         latest_heartbeat_at=NOW)
        result = eval_ready(observations=(future, obs("es-nq-recorder")))
        assert ("btc-recorder", ResilienceReason.OBSERVATION_FROM_FUTURE) in result.reasons

    def test_duplicate_observation_rejects(self):
        with pytest.raises(ValueError, match="duplicate"):
            eval_ready(observations=(obs("btc-recorder"), obs("btc-recorder")))


# ===========================================================================
# Operational resilience: Exactly-one-instance, restart, storage, integrity,
# data-gap, clock-skew
# ===========================================================================

class TestResilienceControls:
    @pytest.mark.parametrize("change,reason", [
        ({"instance_count": 2}, ResilienceReason.DUPLICATE_INSTANCE),
        ({"instance_count": 0}, ResilienceReason.DUPLICATE_INSTANCE),
        ({"task_running": False}, ResilienceReason.TASK_NOT_RUNNING),
        ({"restart_budget_exhausted": True}, ResilienceReason.RESTART_BUDGET_EXHAUSTED),
        ({"restart_count": 6}, ResilienceReason.RESTART_BUDGET_EXHAUSTED),
        ({"unresolved_gap_count": 1}, ResilienceReason.DATA_GAP),
        ({"integrity_verified": False}, ResilienceReason.INTEGRITY_FAILURE),
        ({"free_bytes": 999_999}, ResilienceReason.STORAGE_LOW),
        ({"clock_skew_seconds": 3}, ResilienceReason.CLOCK_SKEW),
        ({"clock_skew_seconds": -3}, ResilienceReason.CLOCK_SKEW),
        ({"trading_authority": True}, ResilienceReason.UNAUTHORIZED_TRADING_AUTHORITY),
    ])
    def test_control_fails_closed(self, change, reason):
        result = eval_ready(
            observations=(replace(obs("btc-recorder"), **change),
                          obs("es-nq-recorder"))
        )
        assert result.state is ServiceState.UNHEALTHY
        assert ("btc-recorder", reason) in result.reasons

    def test_rpo_boundary_exact(self):
        """Heartbeat at exactly RPO boundary → not stale (120 seconds)."""
        ok = replace(obs("btc-recorder"),
                     latest_heartbeat_at=NOW - timedelta(seconds=120))
        result = eval_ready(observations=(ok, obs("es-nq-recorder")))
        # 120 seconds is NOT > 120, so not stale
        assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) not in result.reasons

    def test_rto_boundary_exact(self):
        """Incident detected exactly RTO ago → not RTO breach (300 seconds)."""
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=300),
        )
        result = eval_ready(incidents=(incident,))
        # 300 seconds is NOT > 300, so no RTO breach
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) not in result.reasons
        # But incident is still open
        assert ("btc-recorder", ResilienceReason.INCIDENT_OPEN) in result.reasons

    def test_rto_breach_at_301_seconds(self):
        """Incident at 301 seconds → RTO breach."""
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=301),
        )
        result = eval_ready(incidents=(incident,))
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) in result.reasons


# ===========================================================================
# Operational resilience: Incident lifecycle
# ===========================================================================

class TestResilienceIncidents:
    def test_open_incident_blocks(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(minutes=1),
        )
        result = eval_ready(incidents=(incident,))
        assert not result.ready_for_unattended_operation
        assert incident.incident_id in result.open_incident_ids

    def test_resolved_incident_does_not_block(self):
        resolved = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(minutes=2),
            acknowledged_at=NOW - timedelta(minutes=1),
            resolved_at=NOW,
        )
        result = eval_ready(incidents=(resolved,))
        assert result.ready_for_unattended_operation
        assert resolved.incident_id not in result.open_incident_ids

    def test_ok_reason_cannot_create_incident(self):
        with pytest.raises(ValueError):
            IncidentFactV1.create(
                component="x",
                reason=ResilienceReason.OK,
                detected_at=NOW,
            )

    def test_acknowledgement_before_detection_rejects(self):
        with pytest.raises(ValueError):
            IncidentFactV1.create(
                component="x",
                reason=ResilienceReason.DATA_GAP,
                detected_at=NOW,
                acknowledged_at=NOW - timedelta(seconds=1),
            )

    def test_resolution_before_detection_rejects(self):
        with pytest.raises(ValueError):
            IncidentFactV1.create(
                component="x",
                reason=ResilienceReason.DATA_GAP,
                detected_at=NOW,
                resolved_at=NOW - timedelta(seconds=1),
            )

    def test_resolution_before_acknowledgement_rejects(self):
        with pytest.raises(ValueError):
            IncidentFactV1.create(
                component="x",
                reason=ResilienceReason.DATA_GAP,
                detected_at=NOW - timedelta(minutes=2),
                acknowledged_at=NOW,
                resolved_at=NOW - timedelta(minutes=1),
            )

    def test_incident_immutable(self):
        incident = IncidentFactV1.create(
            component="x",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW,
        )
        with pytest.raises(FrozenInstanceError):
            incident.component = "y"

    def test_incident_id_deterministic(self):
        a = IncidentFactV1.create(
            component="x", reason=ResilienceReason.DATA_GAP,
            detected_at=NOW,
        )
        b = IncidentFactV1.create(
            component="x", reason=ResilienceReason.DATA_GAP,
            detected_at=NOW,
        )
        assert a.incident_id == b.incident_id


# ===========================================================================
# Operational resilience: Trading authority and readiness
# ===========================================================================

class TestResilienceTradingAuthority:
    def test_trading_authority_always_false(self):
        """OperationalReadinessV1.trading_authority is always False."""
        result = eval_ready()
        assert result.trading_authority is False

    def test_trading_authority_true_in_observation_blocks(self):
        """If observation has trading_authority=True, readiness blocks."""
        bad = replace(obs("btc-recorder"), trading_authority=True)
        result = eval_ready(observations=(bad, obs("es-nq-recorder")))
        assert not result.ready_for_unattended_operation
        assert ("btc-recorder",
                ResilienceReason.UNAUTHORIZED_TRADING_AUTHORITY) in result.reasons

    def test_healthy_result_has_no_trading_authority(self):
        """Even healthy result has trading_authority=False."""
        result = eval_ready()
        assert result.state is ServiceState.HEALTHY
        assert result.trading_authority is False

    def test_unhealthy_result_has_no_trading_authority(self):
        """Unhealthy result also has trading_authority=False."""
        result = eval_ready(observations=(obs("btc-recorder"),))
        assert result.state is ServiceState.UNHEALTHY
        assert result.trading_authority is False


# ===========================================================================
# Operational resilience: Policy validation
# ===========================================================================

class TestResiliencePolicy:
    def test_empty_components_rejects(self):
        with pytest.raises(ValueError):
            ResiliencePolicyV1.create(
                required_components=(),
                heartbeat_rpo_seconds=1, recovery_rto_seconds=1,
                minimum_free_bytes=1, maximum_clock_skew_seconds=1,
                maximum_restarts=1,
            )

    def test_duplicate_components_rejects(self):
        with pytest.raises(ValueError):
            ResiliencePolicyV1.create(
                required_components=("a", "a"),
                heartbeat_rpo_seconds=1, recovery_rto_seconds=1,
                minimum_free_bytes=1, maximum_clock_skew_seconds=1,
                maximum_restarts=1,
            )

    def test_zero_rpo_rejects(self):
        with pytest.raises(ValueError):
            ResiliencePolicyV1.create(
                required_components=("a",),
                heartbeat_rpo_seconds=0, recovery_rto_seconds=1,
                minimum_free_bytes=1, maximum_clock_skew_seconds=1,
                maximum_restarts=1,
            )

    def test_zero_rto_rejects(self):
        with pytest.raises(ValueError):
            ResiliencePolicyV1.create(
                required_components=("a",),
                heartbeat_rpo_seconds=1, recovery_rto_seconds=0,
                minimum_free_bytes=1, maximum_clock_skew_seconds=1,
                maximum_restarts=1,
            )

    def test_zero_storage_rejects(self):
        with pytest.raises(ValueError):
            ResiliencePolicyV1.create(
                required_components=("a",),
                heartbeat_rpo_seconds=1, recovery_rto_seconds=1,
                minimum_free_bytes=0, maximum_clock_skew_seconds=1,
                maximum_restarts=1,
            )

    def test_negative_restarts_rejects(self):
        with pytest.raises(ValueError):
            ResiliencePolicyV1.create(
                required_components=("a",),
                heartbeat_rpo_seconds=1, recovery_rto_seconds=1,
                minimum_free_bytes=1, maximum_clock_skew_seconds=1,
                maximum_restarts=-1,
            )

    def test_policy_id_deterministic(self):
        a = policy()
        b = policy()
        assert a.policy_id == b.policy_id

    def test_policy_immutable(self):
        with pytest.raises(FrozenInstanceError):
            policy().required_components = ("other",)

    def test_components_sorted(self):
        p = ResiliencePolicyV1.create(
            required_components=("b", "a"),
            heartbeat_rpo_seconds=1, recovery_rto_seconds=1,
            minimum_free_bytes=1, maximum_clock_skew_seconds=1,
            maximum_restarts=1,
        )
        assert p.required_components == ("a", "b")


# ===========================================================================
# Operational resilience: ComponentObservation validation
# ===========================================================================

class TestResilienceObservation:
    def test_naive_datetime_rejects(self):
        with pytest.raises(ValueError):
            ComponentObservationV1(
                "x", datetime(2026, 8, 30), NOW, True,
                1, 0, False, 0, True, 10_000_000, 0,
            )

    def test_heartbeat_after_observation_rejects(self):
        with pytest.raises(ValueError):
            ComponentObservationV1(
                "x", NOW, NOW + timedelta(seconds=1), True,
                1, 0, False, 0, True, 10_000_000, 0,
            )

    def test_negative_instance_count_rejects(self):
        with pytest.raises(ValueError):
            ComponentObservationV1(
                "x", NOW, NOW, True,
                -1, 0, False, 0, True, 10_000_000, 0,
            )

    def test_bool_clock_skew_rejects(self):
        with pytest.raises(ValueError):
            ComponentObservationV1(
                "x", NOW, NOW, True,
                1, 0, False, 0, True, 10_000_000, True,
            )

    def test_trading_authority_not_bool_rejects(self):
        with pytest.raises(TypeError):
            ComponentObservationV1(
                "x", NOW, NOW, True,
                1, 0, False, 0, True, 10_000_000, 0,
                trading_authority="yes",
            )

    def test_observation_immutable(self):
        with pytest.raises(FrozenInstanceError):
            obs("x").component = "y"


# ===========================================================================
# Operational resilience: Determinism and tampering
# ===========================================================================

class TestResilienceDeterminism:
    def test_decision_id_deterministic(self):
        a = eval_ready()
        b = eval_ready()
        assert a.decision_id == b.decision_id

    def test_different_policy_different_decision(self):
        p1 = ResiliencePolicyV1.create(
            required_components=("btc-recorder", "es-nq-recorder"),
            heartbeat_rpo_seconds=120, recovery_rto_seconds=300,
            minimum_free_bytes=1_000_000, maximum_clock_skew_seconds=2,
            maximum_restarts=5,
        )
        p2 = ResiliencePolicyV1.create(
            required_components=("btc-recorder", "es-nq-recorder"),
            heartbeat_rpo_seconds=60, recovery_rto_seconds=300,
            minimum_free_bytes=1_000_000, maximum_clock_skew_seconds=2,
            maximum_restarts=5,
        )
        r1 = evaluate_operational_readiness(
            policy=p1,
            observations=(obs("btc-recorder"), obs("es-nq-recorder")),
            incidents=(), as_of=NOW,
        )
        r2 = evaluate_operational_readiness(
            policy=p2,
            observations=(obs("btc-recorder"), obs("es-nq-recorder")),
            incidents=(), as_of=NOW,
        )
        assert r1.decision_id != r2.decision_id

    def test_readiness_immutable(self):
        with pytest.raises(FrozenInstanceError):
            eval_ready().state = ServiceState.UNHEALTHY


# ===========================================================================
# Operational resilience: Import isolation
# ===========================================================================

class TestResilienceImportIsolation:
    def test_no_provider_or_submission(self):
        import inspect
        import monitoring.operational_resilience as module
        source = inspect.getsource(module)
        import_lines = [l for l in source.split("\n")
                        if l.strip().startswith("import ")
                        or l.strip().startswith("from ")]
        joined = "\n".join(import_lines).lower()
        for forbidden in ("requests", "private_key", "submit_order",
                         "broker", "wallet", "credential", "collector",
                         "recorder", "scheduledtask", "websocket"):
            assert forbidden not in joined, f"forbidden: {forbidden}"

    def test_no_task_control(self):
        """operational_resilience.py has no task scheduler or subprocess."""
        import inspect
        import monitoring.operational_resilience as module
        source = inspect.getsource(module).lower()
        # Check code lines (not docstring)
        code_lines = [l for l in source.split("\n")
                      if not l.strip().startswith("\"\"\"")
                      and not l.strip().startswith("#")]
        code = "\n".join(code_lines)
        for forbidden in ("subprocess", "start_task", "create_task",
                         "kill_task", "task_scheduler"):
            assert forbidden not in code, f"forbidden: {forbidden}"


# ===========================================================================
# Operational resilience: Public exports
# ===========================================================================

class TestResilienceExports:
    def test_all_expected_exports_present(self):
        import monitoring
        for name in ("RESILIENCE_VERSION", "ComponentObservationV1",
                     "IncidentFactV1", "OperationalReadinessV1",
                     "ResiliencePolicyV1", "ResilienceReason",
                     "ServiceState", "evaluate_operational_readiness"):
            assert hasattr(monitoring, name), f"missing: {name}"

    def test_version_is_stable(self):
        from monitoring.operational_resilience import RESILIENCE_VERSION
        assert RESILIENCE_VERSION == "OPERATIONAL_RESILIENCE_V1"

    def test_all_reasons_unique(self):
        assert len({r.value for r in ResilienceReason}) == len(ResilienceReason)

    def test_all_expected_reasons_present(self):
        expected = {
            "OK", "MISSING_COMPONENT", "STALE_HEARTBEAT", "TASK_NOT_RUNNING",
            "DUPLICATE_INSTANCE", "RESTART_BUDGET_EXHAUSTED", "DATA_GAP",
            "INTEGRITY_FAILURE", "STORAGE_LOW", "CLOCK_SKEW",
            "OBSERVATION_FROM_FUTURE", "INCIDENT_OPEN", "RECOVERY_RTO_BREACH",
            "UNAUTHORIZED_TRADING_AUTHORITY",
        }
        actual = {r.value for r in ResilienceReason}
        assert expected.issubset(actual)


# ===========================================================================
# Operational resilience: RTO breach blocks unattended readiness
# ===========================================================================

class TestRTOBreach:
    def test_rto_breach_blocks_unattended(self):
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(minutes=10),
        )
        result = eval_ready(incidents=(incident,))
        assert not result.ready_for_unattended_operation
        assert ("btc-recorder", ResilienceReason.INCIDENT_OPEN) in result.reasons
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) in result.reasons

    def test_open_incident_without_breach_still_blocks(self):
        """Open incident within RTO still blocks (INCIDENT_OPEN)."""
        incident = IncidentFactV1.create(
            component="btc-recorder",
            reason=ResilienceReason.DATA_GAP,
            detected_at=NOW - timedelta(seconds=30),
        )
        result = eval_ready(incidents=(incident,))
        assert not result.ready_for_unattended_operation
        assert ("btc-recorder", ResilienceReason.INCIDENT_OPEN) in result.reasons
        # 30 seconds < 300 RTO, so no RTO breach
        assert ("btc-recorder", ResilienceReason.RECOVERY_RTO_BREACH) not in result.reasons
