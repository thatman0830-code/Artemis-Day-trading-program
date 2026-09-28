from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from monitoring.operational_resilience import (
    ComponentObservationV1, IncidentFactV1, OperationalReadinessV1,
    ResiliencePolicyV1, ResilienceReason, ServiceState,
    evaluate_operational_readiness,
)

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def policy():
    return ResiliencePolicyV1.create(required_components=("btc-recorder", "es-nq-recorder"),
        heartbeat_rpo_seconds=120, recovery_rto_seconds=300,
        minimum_free_bytes=1_000_000, maximum_clock_skew_seconds=2, maximum_restarts=5)


def observation(component):
    return ComponentObservationV1(component, NOW, NOW - timedelta(seconds=10), True,
        1, 0, False, 0, True, 10_000_000, 0)


def evaluate(*, observations=None, incidents=(), as_of=NOW):
    rows = observations or (observation("btc-recorder"), observation("es-nq-recorder"))
    return evaluate_operational_readiness(policy=policy(), observations=rows,
                                          incidents=incidents, as_of=as_of)


def test_healthy_is_deterministic_advisory_and_has_no_trading_authority():
    first = evaluate(); second = evaluate()
    assert first == second and first.state is ServiceState.HEALTHY
    assert first.ready_for_unattended_operation and not first.trading_authority
    assert isinstance(first, OperationalReadinessV1)


def test_missing_component_fails_closed():
    result = evaluate(observations=(observation("btc-recorder"),))
    assert not result.ready_for_unattended_operation
    assert ("es-nq-recorder", ResilienceReason.MISSING_COMPONENT) in result.reasons


def test_component_specific_heartbeat_sla_preserves_continuous_and_daily_semantics():
    btc = replace(observation("btc-recorder"), latest_heartbeat_at=NOW - timedelta(seconds=121),
                  heartbeat_rpo_seconds=120)
    daily = replace(observation("es-nq-recorder"), latest_heartbeat_at=NOW - timedelta(hours=25),
                    heartbeat_rpo_seconds=26 * 60 * 60)
    result = evaluate(observations=(btc, daily))
    assert ("btc-recorder", ResilienceReason.STALE_HEARTBEAT) in result.reasons
    assert ("es-nq-recorder", ResilienceReason.STALE_HEARTBEAT) not in result.reasons


def test_invalid_component_heartbeat_sla_rejects():
    with pytest.raises(ValueError):
        replace(observation("btc-recorder"), heartbeat_rpo_seconds=0)


@pytest.mark.parametrize(("change", "reason"), (
    ({"latest_heartbeat_at": NOW - timedelta(seconds=121)}, ResilienceReason.STALE_HEARTBEAT),
    ({"task_running": False}, ResilienceReason.TASK_NOT_RUNNING),
    ({"instance_count": 2}, ResilienceReason.DUPLICATE_INSTANCE),
    ({"restart_budget_exhausted": True}, ResilienceReason.RESTART_BUDGET_EXHAUSTED),
    ({"restart_count": 6}, ResilienceReason.RESTART_BUDGET_EXHAUSTED),
    ({"unresolved_gap_count": 1}, ResilienceReason.DATA_GAP),
    ({"integrity_verified": False}, ResilienceReason.INTEGRITY_FAILURE),
    ({"free_bytes": 999_999}, ResilienceReason.STORAGE_LOW),
    ({"clock_skew_seconds": -3}, ResilienceReason.CLOCK_SKEW),
    ({"trading_authority": True}, ResilienceReason.UNAUTHORIZED_TRADING_AUTHORITY),
))
def test_each_critical_control_fails_closed(change, reason):
    result = evaluate(observations=(replace(observation("btc-recorder"), **change),
                                    observation("es-nq-recorder")))
    assert result.state is ServiceState.UNHEALTHY
    assert ("btc-recorder", reason) in result.reasons


def test_future_observation_and_duplicate_observation_rejected():
    future = replace(observation("btc-recorder"), observed_at=NOW + timedelta(seconds=1),
                     latest_heartbeat_at=NOW)
    assert ("btc-recorder", ResilienceReason.OBSERVATION_FROM_FUTURE) in evaluate(
        observations=(future, observation("es-nq-recorder"))).reasons
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(observations=(observation("btc-recorder"), observation("btc-recorder")))


def test_open_incident_blocks_and_resolved_incident_is_retained_without_blocking():
    opened = IncidentFactV1.create(component="btc-recorder", reason=ResilienceReason.DATA_GAP,
                                   detected_at=NOW - timedelta(minutes=1))
    blocked = evaluate(incidents=(opened,))
    assert opened.incident_id in blocked.open_incident_ids
    old = IncidentFactV1.create(component="es-nq-recorder", reason=ResilienceReason.DATA_GAP,
                                detected_at=NOW - timedelta(minutes=6))
    assert ("es-nq-recorder", ResilienceReason.RECOVERY_RTO_BREACH) in evaluate(
        incidents=(old,)).reasons
    resolved = IncidentFactV1.create(component="btc-recorder", reason=ResilienceReason.DATA_GAP,
        detected_at=NOW - timedelta(minutes=2), acknowledged_at=NOW - timedelta(minutes=1),
        resolved_at=NOW)
    assert evaluate(incidents=(resolved,)).ready_for_unattended_operation


def test_invalid_policy_and_incident_chronology_reject():
    with pytest.raises(ValueError):
        ResiliencePolicyV1.create(required_components=(), heartbeat_rpo_seconds=1,
            recovery_rto_seconds=1, minimum_free_bytes=1,
            maximum_clock_skew_seconds=1, maximum_restarts=1)
    with pytest.raises(ValueError):
        IncidentFactV1.create(component="x", reason=ResilienceReason.OK, detected_at=NOW)
    with pytest.raises(ValueError):
        IncidentFactV1.create(component="x", reason=ResilienceReason.DATA_GAP,
            detected_at=NOW, resolved_at=NOW - timedelta(seconds=1))
