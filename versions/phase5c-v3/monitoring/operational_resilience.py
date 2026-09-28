"""Fail-closed operational resilience facts and service-readiness evaluation.

The evaluator is side-effect free. It cannot start tasks, access credentials,
submit orders, or convert a health decision into trading authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json

RESILIENCE_VERSION = "OPERATIONAL_RESILIENCE_V1"


class ServiceState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ResilienceReason(str, Enum):
    OK = "OK"
    MISSING_COMPONENT = "MISSING_COMPONENT"
    STALE_HEARTBEAT = "STALE_HEARTBEAT"
    TASK_NOT_RUNNING = "TASK_NOT_RUNNING"
    DUPLICATE_INSTANCE = "DUPLICATE_INSTANCE"
    RESTART_BUDGET_EXHAUSTED = "RESTART_BUDGET_EXHAUSTED"
    DATA_GAP = "DATA_GAP"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    STORAGE_LOW = "STORAGE_LOW"
    CLOCK_SKEW = "CLOCK_SKEW"
    OBSERVATION_FROM_FUTURE = "OBSERVATION_FROM_FUTURE"
    INCIDENT_OPEN = "INCIDENT_OPEN"
    RECOVERY_RTO_BREACH = "RECOVERY_RTO_BREACH"
    UNAUTHORIZED_TRADING_AUTHORITY = "UNAUTHORIZED_TRADING_AUTHORITY"


def _utc(value: datetime, field: str) -> datetime:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError(f"{field} must be UTC timezone-aware")
    return value.astimezone(timezone.utc)


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _fingerprint(*values: object) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ResiliencePolicyV1:
    policy_id: str
    required_components: tuple[str, ...]
    heartbeat_rpo_seconds: int
    recovery_rto_seconds: int
    minimum_free_bytes: int
    maximum_clock_skew_seconds: int
    maximum_restarts: int

    @classmethod
    def create(cls, *, required_components: tuple[str, ...], heartbeat_rpo_seconds: int,
               recovery_rto_seconds: int, minimum_free_bytes: int,
               maximum_clock_skew_seconds: int, maximum_restarts: int) -> "ResiliencePolicyV1":
        components = tuple(sorted(_text(x, "component") for x in required_components))
        if not components or len(set(components)) != len(components):
            raise ValueError("required components must be nonempty and unique")
        values = (heartbeat_rpo_seconds, recovery_rto_seconds, minimum_free_bytes,
                  maximum_clock_skew_seconds, maximum_restarts)
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in values):
            raise ValueError("resilience limits must be nonnegative integers")
        if heartbeat_rpo_seconds == 0 or recovery_rto_seconds == 0 or minimum_free_bytes == 0:
            raise ValueError("RPO, RTO and minimum storage must be positive")
        ident = _fingerprint(RESILIENCE_VERSION, components, *values)
        return cls(ident, components, *values)


@dataclass(frozen=True, slots=True)
class ComponentObservationV1:
    component: str
    observed_at: datetime
    latest_heartbeat_at: datetime | None
    task_running: bool
    instance_count: int
    restart_count: int
    restart_budget_exhausted: bool
    unresolved_gap_count: int
    integrity_verified: bool
    free_bytes: int
    clock_skew_seconds: int
    trading_authority: bool = False
    single_instance_policy_verified: bool = False
    heartbeat_rpo_seconds: int | None = None

    def __post_init__(self) -> None:
        _text(self.component, "component"); observed = _utc(self.observed_at, "observed_at")
        if self.latest_heartbeat_at is not None:
            heartbeat = _utc(self.latest_heartbeat_at, "latest_heartbeat_at")
            if heartbeat > observed:
                raise ValueError("heartbeat cannot follow observation")
        for name in ("instance_count", "restart_count", "unresolved_gap_count", "free_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if (isinstance(self.clock_skew_seconds, bool)
                or not isinstance(self.clock_skew_seconds, int)):
            raise ValueError("clock_skew_seconds must be an integer")
        for name in ("task_running", "restart_budget_exhausted", "integrity_verified",
                     "trading_authority", "single_instance_policy_verified"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if (self.heartbeat_rpo_seconds is not None
                and (isinstance(self.heartbeat_rpo_seconds, bool)
                     or not isinstance(self.heartbeat_rpo_seconds, int)
                     or self.heartbeat_rpo_seconds <= 0)):
            raise ValueError("heartbeat_rpo_seconds must be a positive integer when supplied")


@dataclass(frozen=True, slots=True)
class IncidentFactV1:
    incident_id: str
    component: str
    reason: ResilienceReason
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    @classmethod
    def create(cls, *, component: str, reason: ResilienceReason, detected_at: datetime,
               acknowledged_at: datetime | None = None,
               resolved_at: datetime | None = None) -> "IncidentFactV1":
        component = _text(component, "component"); detected = _utc(detected_at, "detected_at")
        if reason is ResilienceReason.OK:
            raise ValueError("incidents require a non-OK reason")
        acknowledged = _utc(acknowledged_at, "acknowledged_at") if acknowledged_at else None
        resolved = _utc(resolved_at, "resolved_at") if resolved_at else None
        if acknowledged and acknowledged < detected:
            raise ValueError("acknowledgement precedes detection")
        if resolved and resolved < (acknowledged or detected):
            raise ValueError("resolution precedes incident lifecycle")
        ident = _fingerprint(RESILIENCE_VERSION, component, reason.value, detected,
                             acknowledged, resolved)
        return cls(ident, component, reason, detected, acknowledged, resolved)


@dataclass(frozen=True, slots=True)
class OperationalReadinessV1:
    decision_id: str
    policy_id: str
    as_of: datetime
    state: ServiceState
    reasons: tuple[tuple[str, ResilienceReason], ...]
    component_observation_ids: tuple[str, ...]
    open_incident_ids: tuple[str, ...]
    ready_for_unattended_operation: bool
    trading_authority: bool = False


def evaluate_operational_readiness(*, policy: ResiliencePolicyV1,
                                   observations: tuple[ComponentObservationV1, ...],
                                   incidents: tuple[IncidentFactV1, ...],
                                   as_of: datetime) -> OperationalReadinessV1:
    """Evaluate service health; never grants trading authority."""
    now = _utc(as_of, "as_of")
    by_component: dict[str, ComponentObservationV1] = {}
    reasons: list[tuple[str, ResilienceReason]] = []
    observation_ids: list[str] = []
    for item in observations:
        if item.component in by_component:
            raise ValueError("duplicate component observation")
        by_component[item.component] = item
        observation_ids.append(_fingerprint(RESILIENCE_VERSION, item))
    for component in policy.required_components:
        item = by_component.get(component)
        if item is None:
            reasons.append((component, ResilienceReason.MISSING_COMPONENT)); continue
        if item.observed_at > now:
            reasons.append((component, ResilienceReason.OBSERVATION_FROM_FUTURE))
        heartbeat_limit = item.heartbeat_rpo_seconds or policy.heartbeat_rpo_seconds
        if item.latest_heartbeat_at is None or (now - item.latest_heartbeat_at).total_seconds() > heartbeat_limit:
            reasons.append((component, ResilienceReason.STALE_HEARTBEAT))
        if not item.task_running:
            reasons.append((component, ResilienceReason.TASK_NOT_RUNNING))
        if item.instance_count > 1 or (item.instance_count == 0 and not item.single_instance_policy_verified):
            reasons.append((component, ResilienceReason.DUPLICATE_INSTANCE))
        if item.restart_budget_exhausted or item.restart_count > policy.maximum_restarts:
            reasons.append((component, ResilienceReason.RESTART_BUDGET_EXHAUSTED))
        if item.unresolved_gap_count:
            reasons.append((component, ResilienceReason.DATA_GAP))
        if not item.integrity_verified:
            reasons.append((component, ResilienceReason.INTEGRITY_FAILURE))
        if item.free_bytes < policy.minimum_free_bytes:
            reasons.append((component, ResilienceReason.STORAGE_LOW))
        if abs(item.clock_skew_seconds) > policy.maximum_clock_skew_seconds:
            reasons.append((component, ResilienceReason.CLOCK_SKEW))
        if item.trading_authority:
            reasons.append((component, ResilienceReason.UNAUTHORIZED_TRADING_AUTHORITY))
    open_incidents = tuple(sorted(x.incident_id for x in incidents if x.resolved_at is None))
    for item in incidents:
        if item.resolved_at is None:
            reasons.append((item.component, ResilienceReason.INCIDENT_OPEN))
            if (now - item.detected_at).total_seconds() > policy.recovery_rto_seconds:
                reasons.append((item.component, ResilienceReason.RECOVERY_RTO_BREACH))
    ordered = tuple(sorted(set(reasons), key=lambda x: (x[0], x[1].value)))
    state = ServiceState.HEALTHY if not ordered else ServiceState.UNHEALTHY
    decision_id = _fingerprint(RESILIENCE_VERSION, policy.policy_id, now, state.value,
                               ordered, tuple(sorted(observation_ids)), open_incidents)
    return OperationalReadinessV1(decision_id, policy.policy_id, now, state, ordered,
                                  tuple(sorted(observation_ids)), open_incidents,
                                  not ordered, False)
