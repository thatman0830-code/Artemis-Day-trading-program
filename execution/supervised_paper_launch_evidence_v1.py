"""Strict evidence and owner-confirmation adapter for the paper launch gate."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from execution.supervised_paper_launch_gate_v1 import (
    SupervisedPaperLaunchDecisionV1, SupervisedPaperLaunchFactsV1,
    SupervisedPaperLaunchPolicyV1, evaluate_supervised_paper_launch,
)

EVIDENCE_VERSION="supervised-paper-launch-evidence-v1"
CONFIRMATION_VERSION="supervised-paper-owner-confirmation-v1"


def _canonical(value: object) -> str:
    return json.dumps(value,sort_keys=True,separators=(",",":"))


def _sha(value: str, name: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _git_oid(value: str, name: str) -> None:
    if len(value) not in (40,64) or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be a lowercase SHA-1 or SHA-256 object ID")


def _time(value: object,name: str) -> datetime:
    if not isinstance(value,str): raise ValueError(f"{name} must be an ISO UTC timestamp")
    try: parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc: raise ValueError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset()!=timedelta(0): raise ValueError(f"{name} must be UTC")
    return parsed


def _object(path: Path) -> dict:
    try: value=json.loads(Path(path).read_text("utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise ValueError("launch evidence is unreadable") from exc
    if not isinstance(value,dict): raise ValueError("launch evidence must be an object")
    return value


@dataclass(frozen=True,slots=True)
class OwnerSupervisionConfirmationV1:
    confirmed_at: datetime
    expires_at: datetime
    repository_checkpoint: str
    owner_supervision_confirmed: bool
    stop_control_verified: bool
    maximum_session_seconds: int
    maximum_commands: int
    maximum_order_notional: Decimal
    maximum_gross_exposure: Decimal
    confirmation_id: str
    trading_authority: bool=False

    def __post_init__(self) -> None:
        if self.trading_authority is not False:
            raise ValueError("owner confirmation cannot grant trading authority")

    @classmethod
    def create(cls,*,confirmed_at:datetime,expires_at:datetime,repository_checkpoint:str,
               owner_supervision_confirmed:bool,stop_control_verified:bool,
               maximum_session_seconds:int,maximum_commands:int,
               maximum_order_notional:Decimal,maximum_gross_exposure:Decimal):
        for value,name in ((confirmed_at,"confirmed_at"),(expires_at,"expires_at")):
            if value.tzinfo is None or value.utcoffset()!=timedelta(0): raise ValueError(f"{name} must be UTC")
        _git_oid(repository_checkpoint,"repository_checkpoint")
        if not confirmed_at < expires_at <= confirmed_at+timedelta(minutes=5):
            raise ValueError("owner confirmation lifetime exceeds five minutes")
        body={"schema_version":CONFIRMATION_VERSION,"confirmed_at":confirmed_at.isoformat(),
            "expires_at":expires_at.isoformat(),"repository_checkpoint":repository_checkpoint,
            "owner_supervision_confirmed":owner_supervision_confirmed,
            "stop_control_verified":stop_control_verified,"maximum_session_seconds":maximum_session_seconds,
            "maximum_commands":maximum_commands,"maximum_order_notional":str(maximum_order_notional),
            "maximum_gross_exposure":str(maximum_gross_exposure),"trading_authority":False}
        identity=hashlib.sha256(_canonical(body).encode()).hexdigest()
        return cls(confirmed_at,expires_at,repository_checkpoint,owner_supervision_confirmed,
            stop_control_verified,maximum_session_seconds,maximum_commands,maximum_order_notional,
            maximum_gross_exposure,identity,False)


@dataclass(frozen=True,slots=True)
class SupervisedPaperLaunchEvidenceV1:
    collected_at: datetime
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
    source_file_sha256: tuple[str,...]
    evidence_id: str
    trading_authority: bool=False

    def __post_init__(self) -> None:
        if self.trading_authority is not False:
            raise ValueError("launch evidence cannot grant trading authority")


def read_launch_evidence(path: Path) -> SupervisedPaperLaunchEvidenceV1:
    value=_object(path)
    required={"schema_version","collected_at","repository_checkpoint","repository_clean",
        "watchdog_state","watchdog_report_id","btc_task_state","btc_recorder_health",
        "btc_heartbeat_at","btc_unresolved_gap_count","es_nq_task_state","es_nq_last_result",
        "es_nq_missed_runs","recovery_drill_result","recovery_drill_report_id",
        "stale_alert_drill_result","stale_alert_drill_report_id","unhealthy_alert_delivered",
        "healthy_alert_delivered","clock_skew_seconds","source_file_sha256","evidence_id",
        "trading_authority"}
    if set(value)!=required or value["schema_version"]!=EVIDENCE_VERSION:
        raise ValueError("launch evidence shape or version mismatch")
    if value["trading_authority"] is not False: raise ValueError("launch evidence authority mismatch")
    hashes=value["source_file_sha256"]
    if not isinstance(hashes,list) or not hashes or len(set(hashes))!=len(hashes):
        raise ValueError("source hashes must be a nonempty unique array")
    for item in hashes:_sha(item,"source_file_sha256")
    supplied=value["evidence_id"];
    body={key:item for key,item in value.items() if key!="evidence_id"}
    _sha(supplied,"evidence_id")
    if supplied!=hashlib.sha256(_canonical(body).encode()).hexdigest(): raise ValueError("evidence identity mismatch")
    _git_oid(value["repository_checkpoint"],"repository_checkpoint")
    for name in ("watchdog_report_id","recovery_drill_report_id","stale_alert_drill_report_id"):
        _sha(value[name],name)
    for name in ("repository_clean","unhealthy_alert_delivered","healthy_alert_delivered"):
        if not isinstance(value[name],bool): raise ValueError(f"{name} must be boolean")
    for name in ("btc_unresolved_gap_count","es_nq_last_result","es_nq_missed_runs","clock_skew_seconds"):
        if isinstance(value[name],bool) or not isinstance(value[name],int): raise ValueError(f"{name} must be integer")
    if value["btc_unresolved_gap_count"]<0 or value["es_nq_missed_runs"]<0: raise ValueError("counts must be nonnegative")
    return SupervisedPaperLaunchEvidenceV1(_time(value["collected_at"],"collected_at"),
        value["repository_checkpoint"],value["repository_clean"],value["watchdog_state"],
        value["watchdog_report_id"],value["btc_task_state"],value["btc_recorder_health"],
        _time(value["btc_heartbeat_at"],"btc_heartbeat_at"),value["btc_unresolved_gap_count"],
        value["es_nq_task_state"],value["es_nq_last_result"],value["es_nq_missed_runs"],
        value["recovery_drill_result"],value["recovery_drill_report_id"],
        value["stale_alert_drill_result"],value["stale_alert_drill_report_id"],
        value["unhealthy_alert_delivered"],value["healthy_alert_delivered"],
        value["clock_skew_seconds"],tuple(hashes),supplied,False)


def evaluate_collected_launch_evidence(*,evidence:SupervisedPaperLaunchEvidenceV1,
        confirmation:OwnerSupervisionConfirmationV1,policy:SupervisedPaperLaunchPolicyV1,
        as_of:datetime)->SupervisedPaperLaunchDecisionV1:
    if as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0): raise ValueError("as_of must be UTC")
    if not confirmation.confirmed_at<=as_of<confirmation.expires_at: raise ValueError("owner confirmation is not current")
    if confirmation.repository_checkpoint!=evidence.repository_checkpoint or confirmation.repository_checkpoint!=policy.expected_checkpoint:
        raise ValueError("owner confirmation checkpoint mismatch")
    expected=(int(policy.maximum_session_duration.total_seconds()),policy.maximum_commands,
        policy.maximum_order_notional,policy.maximum_gross_exposure)
    actual=(confirmation.maximum_session_seconds,confirmation.maximum_commands,
        confirmation.maximum_order_notional,confirmation.maximum_gross_exposure)
    if actual!=expected: raise ValueError("owner confirmation risk limits mismatch")
    facts=SupervisedPaperLaunchFactsV1(evidence.collected_at,evidence.repository_checkpoint,
        evidence.repository_clean,evidence.watchdog_state,evidence.watchdog_report_id,
        evidence.btc_task_state,evidence.btc_recorder_health,evidence.btc_heartbeat_at,
        evidence.btc_unresolved_gap_count,evidence.es_nq_task_state,evidence.es_nq_last_result,
        evidence.es_nq_missed_runs,evidence.recovery_drill_result,evidence.recovery_drill_report_id,
        evidence.stale_alert_drill_result,evidence.stale_alert_drill_report_id,
        evidence.unhealthy_alert_delivered,evidence.healthy_alert_delivered,evidence.clock_skew_seconds,
        confirmation.owner_supervision_confirmed,confirmation.stop_control_verified,False)
    return evaluate_supervised_paper_launch(facts=facts,policy=policy,as_of=as_of)
