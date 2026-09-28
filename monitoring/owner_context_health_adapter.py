"""Read-only owner-context facts adapter for operational resilience.

All acquisition is dependency injected.  This module has no Windows, process,
network, credential, archive-writing, or trading capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import PureWindowsPath
from typing import Protocol

from .operational_resilience import (
    ComponentObservationV1, IncidentFactV1, OperationalReadinessV1,
    ResiliencePolicyV1, evaluate_operational_readiness,
)

OWNER_CONTEXT_ADAPTER_VERSION = "OWNER_CONTEXT_HEALTH_ADAPTER_V1"
OWNER_CONTEXT_COMPONENTS = ("btc-recorder", "es-nq-recorder")


class OwnerContextAdapterError(ValueError):
    """A sanitized owner-context input cannot be proven compatible."""


class VisibilityScope(str, Enum):
    OWNER_CONTEXT = "OWNER_CONTEXT"
    SANDBOX_CONTEXT = "SANDBOX_CONTEXT"


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise OwnerContextAdapterError(f"{field} must be UTC timezone-aware")
    return value.astimezone(timezone.utc)


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OwnerContextAdapterError(f"{field} is required")
    return value.strip()


def _path(value: str, field: str) -> str:
    text = _text(value, field)
    path = PureWindowsPath(text)
    if not path.is_absolute() or ".." in path.parts:
        raise OwnerContextAdapterError(f"{field} must be an absolute normalized Windows path")
    return str(path).casefold()


def _hash(value: str, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise OwnerContextAdapterError(f"{field} must be SHA-256 hex")
    return text


def _id(*values: object) -> str:
    raw = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ComponentIdentityV1:
    component: str
    task_name: str
    task_path: str
    executable_path: str
    script_path: str
    permitted_task_states: tuple[str, ...]
    permitted_last_results: tuple[int, ...]
    permitted_instance_counts: tuple[int, ...]
    single_instance_policy: str
    expected_restart_count: int
    expected_restart_interval_seconds: int
    heartbeat_rpo_seconds: int | None = None

    def __post_init__(self) -> None:
        for name in ("component", "task_name", "task_path", "single_instance_policy"):
            _text(getattr(self, name), name)
        _path(self.executable_path, "executable_path"); _path(self.script_path, "script_path")
        if not self.permitted_task_states or len(set(self.permitted_task_states)) != len(self.permitted_task_states):
            raise OwnerContextAdapterError("permitted_task_states must be nonempty and unique")
        if any(not isinstance(x, str) or not x for x in self.permitted_task_states):
            raise OwnerContextAdapterError("task states must be text")
        for name in ("permitted_last_results", "permitted_instance_counts"):
            values = getattr(self, name)
            if not values or len(set(values)) != len(values):
                raise OwnerContextAdapterError(f"{name} must be nonempty and unique")
            if any(isinstance(x, bool) or not isinstance(x, int)
                   or (name == "permitted_instance_counts" and x < 0) for x in values):
                raise OwnerContextAdapterError(f"{name} contains an invalid value")
        for name in ("expected_restart_count", "expected_restart_interval_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OwnerContextAdapterError(f"{name} must be a nonnegative integer")
        if (self.heartbeat_rpo_seconds is not None
                and (isinstance(self.heartbeat_rpo_seconds, bool)
                     or not isinstance(self.heartbeat_rpo_seconds, int)
                     or self.heartbeat_rpo_seconds <= 0)):
            raise OwnerContextAdapterError("heartbeat_rpo_seconds must be positive when supplied")


@dataclass(frozen=True, slots=True)
class SanitizedComponentFactsV1:
    component: str
    collected_at: datetime
    source_file_sha256: tuple[str, ...]
    visibility_scope: VisibilityScope
    task_installed: bool
    task_name: str
    task_path: str
    executable_path: str
    script_path: str
    task_state: str
    last_result: int
    single_instance_policy: str
    instance_count: int
    restart_count: int
    restart_budget_exhausted: bool
    restart_policy_count: int
    restart_interval_seconds: int
    latest_heartbeat_at: datetime | None
    unresolved_gap_count: int
    archive_integrity_verified: bool
    free_bytes: int
    clock_skew_seconds: int
    incident_facts: tuple[IncidentFactV1, ...] = ()

    def __post_init__(self) -> None:
        _text(self.component, "component"); observed = _utc(self.collected_at, "collected_at")
        if not self.source_file_sha256:
            raise OwnerContextAdapterError("source_file_sha256 is required")
        hashes = tuple(_hash(x, "source_file_sha256") for x in self.source_file_sha256)
        if len(set(hashes)) != len(hashes):
            raise OwnerContextAdapterError("duplicate source-file hash")
        if self.latest_heartbeat_at is not None and _utc(self.latest_heartbeat_at, "latest_heartbeat_at") > observed:
            raise OwnerContextAdapterError("heartbeat cannot follow collection")
        for name in ("task_name", "task_path", "task_state", "single_instance_policy"):
            _text(getattr(self, name), name)
        _path(self.executable_path, "executable_path"); _path(self.script_path, "script_path")
        for name in ("last_result", "clock_skew_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise OwnerContextAdapterError(f"{name} must be an integer")
        for name in ("instance_count", "restart_count", "restart_policy_count",
                     "restart_interval_seconds", "unresolved_gap_count", "free_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OwnerContextAdapterError(f"{name} must be a nonnegative integer")
        for name in ("task_installed", "restart_budget_exhausted", "archive_integrity_verified"):
            if not isinstance(getattr(self, name), bool):
                raise OwnerContextAdapterError(f"{name} must be bool")
        for incident in self.incident_facts:
            if incident.component != self.component:
                raise OwnerContextAdapterError("cross-component incident")
            if incident.detected_at > observed:
                raise OwnerContextAdapterError("future-dated incident")


class SanitizedFactsReader(Protocol):
    def read(self, component: str) -> SanitizedComponentFactsV1: ...


@dataclass(frozen=True, slots=True)
class AdaptedOwnerContextHealthV1:
    adapter_version: str
    report_id: str
    collected_at: datetime
    component_observation_ids: tuple[str, ...]
    source_file_sha256: tuple[str, ...]
    observations: tuple[ComponentObservationV1, ...]
    readiness: OperationalReadinessV1
    trading_authority: bool = False


def adapt_owner_context_health(*, reader: SanitizedFactsReader,
                               identities: tuple[ComponentIdentityV1, ...],
                               policy: ResiliencePolicyV1,
                               as_of: datetime) -> AdaptedOwnerContextHealthV1:
    """Read sanitized facts once, validate lineage, and evaluate readiness."""
    now = _utc(as_of, "as_of")
    by_name = {item.component: item for item in identities}
    if (len(by_name) != len(identities)
            or set(by_name) != set(policy.required_components)
            or tuple(sorted(policy.required_components)) != OWNER_CONTEXT_COMPONENTS):
        raise OwnerContextAdapterError("component identities must exactly match policy")
    observations: list[ComponentObservationV1] = []
    incidents: list[IncidentFactV1] = []
    source_hashes: list[str] = []
    observation_ids: list[str] = []
    for component in sorted(policy.required_components):
        expected = by_name[component]
        try:
            facts = reader.read(component)
        except OwnerContextAdapterError:
            raise
        except Exception as exc:
            raise OwnerContextAdapterError("missing component facts") from exc
        if not isinstance(facts, SanitizedComponentFactsV1) or facts.component != component:
            raise OwnerContextAdapterError("missing or cross-component facts")
        if facts.visibility_scope is not VisibilityScope.OWNER_CONTEXT:
            raise OwnerContextAdapterError("task installation requires owner-context visibility")
        if facts.collected_at > now:
            raise OwnerContextAdapterError("future-dated collection")
        if (now - facts.collected_at).total_seconds() > policy.heartbeat_rpo_seconds:
            raise OwnerContextAdapterError("stale owner-context collection")
        matches = (
            facts.task_name == expected.task_name
            and facts.task_path == expected.task_path
            and _path(facts.executable_path, "executable_path") == _path(expected.executable_path, "executable_path")
            and _path(facts.script_path, "script_path") == _path(expected.script_path, "script_path")
            and facts.single_instance_policy == expected.single_instance_policy
            and facts.restart_policy_count == expected.expected_restart_count
            and facts.restart_interval_seconds == expected.expected_restart_interval_seconds
            and facts.instance_count in expected.permitted_instance_counts
        )
        if not matches:
            raise OwnerContextAdapterError("task identity or policy mismatch")
        task_running = (facts.task_installed and facts.task_state in expected.permitted_task_states
                        and facts.last_result in expected.permitted_last_results)
        observation = ComponentObservationV1(
            component=component, observed_at=facts.collected_at,
            latest_heartbeat_at=facts.latest_heartbeat_at, task_running=task_running,
            instance_count=facts.instance_count, restart_count=facts.restart_count,
            restart_budget_exhausted=facts.restart_budget_exhausted,
            unresolved_gap_count=facts.unresolved_gap_count,
            integrity_verified=facts.archive_integrity_verified,
            free_bytes=facts.free_bytes, clock_skew_seconds=facts.clock_skew_seconds,
            trading_authority=False, single_instance_policy_verified=True,
            heartbeat_rpo_seconds=expected.heartbeat_rpo_seconds,
        )
        oid = _id(OWNER_CONTEXT_ADAPTER_VERSION, observation, tuple(sorted(facts.source_file_sha256)))
        observations.append(observation); observation_ids.append(oid)
        incidents.extend(facts.incident_facts); source_hashes.extend(facts.source_file_sha256)
    readiness = evaluate_operational_readiness(
        policy=policy, observations=tuple(observations),
        incidents=_unique_incidents(incidents), as_of=now)
    ordered_ids = tuple(sorted(observation_ids)); ordered_hashes = tuple(sorted(set(source_hashes)))
    report_id = _id(OWNER_CONTEXT_ADAPTER_VERSION, now, ordered_ids, ordered_hashes,
                    readiness.decision_id)
    return AdaptedOwnerContextHealthV1(OWNER_CONTEXT_ADAPTER_VERSION, report_id, now,
                                       ordered_ids, ordered_hashes, tuple(observations),
                                       readiness, False)


def _unique_incidents(incidents: list[IncidentFactV1]) -> tuple[IncidentFactV1, ...]:
    seen: set[str] = set()
    for incident in incidents:
        if incident.incident_id in seen:
            raise OwnerContextAdapterError("duplicate incident identity")
        seen.add(incident.incident_id)
    return tuple(incidents)
