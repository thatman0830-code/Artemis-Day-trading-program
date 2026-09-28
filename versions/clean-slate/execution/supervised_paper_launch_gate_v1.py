"""Fail-closed advisory gate for a bounded supervised BTC paper session."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json


LAUNCH_GATE_VERSION = "supervised-paper-launch-gate-v1"
HARD_MAXIMUM_SESSION = timedelta(minutes=30)
HARD_MAXIMUM_COMMANDS = 10
HARD_MAXIMUM_ORDER_NOTIONAL = Decimal("500")
HARD_MAXIMUM_GROSS_EXPOSURE = Decimal("800")


class PaperLaunchReason(str, Enum):
    REPOSITORY_NOT_CLEAN = "REPOSITORY_NOT_CLEAN"
    CHECKPOINT_MISMATCH = "CHECKPOINT_MISMATCH"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    WATCHDOG_NOT_HEALTHY = "WATCHDOG_NOT_HEALTHY"
    BTC_RECORDER_NOT_HEALTHY = "BTC_RECORDER_NOT_HEALTHY"
    BTC_DATA_GAP = "BTC_DATA_GAP"
    ES_NQ_NOT_HEALTHY = "ES_NQ_NOT_HEALTHY"
    RECOVERY_DRILL_UNVERIFIED = "RECOVERY_DRILL_UNVERIFIED"
    STALE_ALERT_DRILL_UNVERIFIED = "STALE_ALERT_DRILL_UNVERIFIED"
    CLOCK_SKEW = "CLOCK_SKEW"
    OWNER_SUPERVISION_MISSING = "OWNER_SUPERVISION_MISSING"
    STOP_CONTROL_UNVERIFIED = "STOP_CONTROL_UNVERIFIED"


def _sha(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _git_oid(value: str, name: str) -> None:
    if len(value) not in (40, 64) or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be a lowercase SHA-1 or SHA-256 object ID")


def _utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC")


def _canonical(value: object) -> str:
    def encode(item: object):
        if isinstance(item, Enum): return item.value
        if isinstance(item, datetime): return item.isoformat()
        if isinstance(item, timedelta): return item.total_seconds()
        if isinstance(item, Decimal): return str(item)
        if hasattr(item, "__dataclass_fields__"):
            return {name: getattr(item, name) for name in item.__dataclass_fields__}
        raise TypeError(type(item).__name__)
    return json.dumps(value, default=encode, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class SupervisedPaperLaunchPolicyV1:
    expected_checkpoint: str
    evidence_maximum_age: timedelta
    permit_lifetime: timedelta
    maximum_session_duration: timedelta
    maximum_commands: int
    maximum_order_notional: Decimal
    maximum_gross_exposure: Decimal
    allowed_markets: tuple[str, ...] = ("BTC",)
    trading_authority: bool = False

    def __post_init__(self):
        _git_oid(self.expected_checkpoint, "expected_checkpoint")
        if not timedelta(0) < self.evidence_maximum_age <= timedelta(minutes=5):
            raise ValueError("evidence maximum age exceeds hard ceiling")
        if not timedelta(0) < self.permit_lifetime <= timedelta(minutes=5):
            raise ValueError("permit lifetime exceeds hard ceiling")
        if not timedelta(0) < self.maximum_session_duration <= HARD_MAXIMUM_SESSION:
            raise ValueError("session duration exceeds hard ceiling")
        if isinstance(self.maximum_commands, bool) or not 0 < self.maximum_commands <= HARD_MAXIMUM_COMMANDS:
            raise ValueError("command count exceeds hard ceiling")
        if not Decimal("0") < self.maximum_order_notional <= HARD_MAXIMUM_ORDER_NOTIONAL:
            raise ValueError("order notional exceeds hard ceiling")
        if not Decimal("0") < self.maximum_gross_exposure <= HARD_MAXIMUM_GROSS_EXPOSURE:
            raise ValueError("gross exposure exceeds hard ceiling")
        if self.allowed_markets not in (("BTC",), ("BTC-PERP",)):
            raise ValueError("initial supervised paper launch requires exactly one BTC-only instrument")
        if self.trading_authority:
            raise ValueError("launch policy cannot carry trading authority")


@dataclass(frozen=True, slots=True)
class SupervisedPaperLaunchFactsV1:
    observed_at: datetime
    repository_checkpoint: str
    repository_clean: bool
    watchdog_state: str
    watchdog_report_id: str
    btc_task_state: str
    btc_recorder_health: str
    btc_heartbeat_at: datetime
    btc_unresolved_gap_count: int
    es_nq_task_state: str
    es_nq_last_result: int
    es_nq_missed_runs: int
    recovery_drill_result: str
    recovery_drill_report_id: str
    stale_alert_drill_result: str
    stale_alert_drill_report_id: str
    unhealthy_alert_delivered: bool
    healthy_alert_delivered: bool
    clock_skew_seconds: int
    owner_supervision_confirmed: bool
    stop_control_verified: bool
    trading_authority: bool = False

    def __post_init__(self):
        _utc(self.observed_at, "observed_at"); _utc(self.btc_heartbeat_at, "btc_heartbeat_at")
        _git_oid(self.repository_checkpoint, "repository_checkpoint")
        for value, name in ((self.watchdog_report_id, "watchdog_report_id"),
                            (self.recovery_drill_report_id, "recovery_drill_report_id"),
                            (self.stale_alert_drill_report_id, "stale_alert_drill_report_id")):
            _sha(value, name)
        for value, name in ((self.btc_unresolved_gap_count, "btc_unresolved_gap_count"),
                            (self.es_nq_missed_runs, "es_nq_missed_runs")):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if isinstance(self.clock_skew_seconds, bool) or not isinstance(self.clock_skew_seconds, int):
            raise ValueError("clock_skew_seconds must be an integer")
        if self.trading_authority:
            raise ValueError("launch facts cannot carry trading authority")


@dataclass(frozen=True, slots=True)
class SupervisedPaperLaunchDecisionV1:
    schema_version: str
    evaluated_at: datetime
    eligible: bool
    reasons: tuple[PaperLaunchReason, ...]
    expires_at: datetime | None
    permitted_markets: tuple[str, ...]
    maximum_session_duration: timedelta
    maximum_commands: int
    maximum_order_notional: Decimal
    maximum_gross_exposure: Decimal
    launch_id: str
    advisory_only: bool = True
    live_trading_permitted: bool = False
    trading_authority: bool = False


def evaluate_supervised_paper_launch(*, facts: SupervisedPaperLaunchFactsV1,
                                     policy: SupervisedPaperLaunchPolicyV1,
                                     as_of: datetime) -> SupervisedPaperLaunchDecisionV1:
    _utc(as_of, "as_of")
    if facts.observed_at > as_of or facts.btc_heartbeat_at > as_of:
        raise ValueError("launch evidence cannot be future-dated")
    reasons: list[PaperLaunchReason] = []
    add = reasons.append
    if not facts.repository_clean: add(PaperLaunchReason.REPOSITORY_NOT_CLEAN)
    if facts.repository_checkpoint != policy.expected_checkpoint: add(PaperLaunchReason.CHECKPOINT_MISMATCH)
    if as_of - facts.observed_at > policy.evidence_maximum_age: add(PaperLaunchReason.STALE_EVIDENCE)
    if facts.watchdog_state != "HEALTHY": add(PaperLaunchReason.WATCHDOG_NOT_HEALTHY)
    if (facts.btc_task_state != "Running" or facts.btc_recorder_health != "HEALTHY" or
            as_of - facts.btc_heartbeat_at > timedelta(seconds=90)):
        add(PaperLaunchReason.BTC_RECORDER_NOT_HEALTHY)
    if facts.btc_unresolved_gap_count: add(PaperLaunchReason.BTC_DATA_GAP)
    if facts.es_nq_task_state != "Ready" or facts.es_nq_last_result != 0 or facts.es_nq_missed_runs:
        add(PaperLaunchReason.ES_NQ_NOT_HEALTHY)
    if facts.recovery_drill_result != "RECOVERY_VERIFIED": add(PaperLaunchReason.RECOVERY_DRILL_UNVERIFIED)
    if (facts.stale_alert_drill_result != "STALE_ALERT_AND_RECOVERY_VERIFIED" or
            not facts.unhealthy_alert_delivered or not facts.healthy_alert_delivered):
        add(PaperLaunchReason.STALE_ALERT_DRILL_UNVERIFIED)
    if abs(facts.clock_skew_seconds) > 2: add(PaperLaunchReason.CLOCK_SKEW)
    if not facts.owner_supervision_confirmed: add(PaperLaunchReason.OWNER_SUPERVISION_MISSING)
    if not facts.stop_control_verified: add(PaperLaunchReason.STOP_CONTROL_UNVERIFIED)
    ordered = tuple(sorted(set(reasons), key=lambda reason: reason.value)); eligible = not ordered
    expires = as_of + policy.permit_lifetime if eligible else None
    core = (LAUNCH_GATE_VERSION, as_of, facts, policy, eligible, ordered, expires, True, False, False)
    launch_id = hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()
    return SupervisedPaperLaunchDecisionV1(LAUNCH_GATE_VERSION, as_of, eligible, ordered, expires,
        policy.allowed_markets if eligible else (), policy.maximum_session_duration,
        policy.maximum_commands, policy.maximum_order_notional, policy.maximum_gross_exposure,
        launch_id, True, False, False)
