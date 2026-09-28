"""Parse sanitized owner facts and produce a read-only readiness report."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path, PureWindowsPath

from .operational_resilience import ResiliencePolicyV1
from .owner_context_health_adapter import (
    AdaptedOwnerContextHealthV1, ComponentIdentityV1, OwnerContextAdapterError,
    SanitizedComponentFactsV1, VisibilityScope, adapt_owner_context_health,
)

FACTS_VERSION = "owner-context-health-facts-v1"


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise OwnerContextAdapterError(f"{field} must be an ISO UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OwnerContextAdapterError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise OwnerContextAdapterError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


class _Reader:
    def __init__(self, rows: dict[str, SanitizedComponentFactsV1]): self.rows = rows
    def read(self, component: str) -> SanitizedComponentFactsV1: return self.rows[component]


def _identities(repository: Path) -> tuple[ComponentIdentityV1, ...]:
    root = PureWindowsPath(str(repository.resolve()))
    powershell = PureWindowsPath("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    return (
        ComponentIdentityV1("btc-recorder", "BTC Public Candle Research Recorder", "\\",
            str(powershell), str(root / "scripts/run_btc_forward_recorder_task.ps1"),
            # 0x800710E0 is recorded when Task Scheduler refuses a duplicate
            # start under IgnoreNew.  Running state, exact process identity,
            # single-instance count, and a fresh heartbeat still prove health.
            ("Running",), (0, 267009, 2147946720), (0, 1), "IgnoreNew", 3, 60, 90),
        ComponentIdentityV1("es-nq-recorder", "NinjaTrader MES-NQ Closed Bar Recorder", "\\",
            str(powershell), str(root / "scripts/run_ninjatrader_closed_bar_recorder.ps1"),
            ("Running",), (0, 267009, 2147946720), (1,), "IgnoreNew", 3, 60, 120),
    )


def _facts(row: object) -> SanitizedComponentFactsV1:
    if not isinstance(row, dict): raise OwnerContextAdapterError("component fact must be an object")
    required = {"component","collected_at","source_file_sha256","task_installed","task_name",
        "task_path","executable_path","script_path","task_state","last_result",
        "single_instance_policy","instance_count","restart_count","restart_budget_exhausted",
        "restart_policy_count","restart_interval_seconds","latest_heartbeat_at",
        "unresolved_gap_count","archive_integrity_verified","free_bytes","clock_skew_seconds",
        "incident_facts","trading_authority"}
    if set(row) != required: raise OwnerContextAdapterError("component fact keys are not canonical")
    if row["trading_authority"] is not False: raise OwnerContextAdapterError("trading authority prohibited")
    if row["incident_facts"]: raise OwnerContextAdapterError("collector incident parsing is not yet supported")
    heartbeat = _time(row["latest_heartbeat_at"], "latest_heartbeat_at") if row["latest_heartbeat_at"] else None
    return SanitizedComponentFactsV1(
        component=row["component"], collected_at=_time(row["collected_at"], "collected_at"),
        source_file_sha256=tuple(row["source_file_sha256"]), visibility_scope=VisibilityScope.OWNER_CONTEXT,
        task_installed=row["task_installed"], task_name=row["task_name"], task_path=row["task_path"],
        executable_path=row["executable_path"], script_path=row["script_path"], task_state=row["task_state"],
        last_result=row["last_result"], single_instance_policy=row["single_instance_policy"],
        instance_count=row["instance_count"], restart_count=row["restart_count"],
        restart_budget_exhausted=row["restart_budget_exhausted"],
        restart_policy_count=row["restart_policy_count"], restart_interval_seconds=row["restart_interval_seconds"],
        latest_heartbeat_at=heartbeat, unresolved_gap_count=row["unresolved_gap_count"],
        archive_integrity_verified=row["archive_integrity_verified"], free_bytes=row["free_bytes"],
        clock_skew_seconds=row["clock_skew_seconds"], incident_facts=())


def evaluate_sanitized_owner_facts(*, facts_path: Path, repository: Path,
                                   as_of: datetime) -> AdaptedOwnerContextHealthV1:
    try: document = json.loads(facts_path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise OwnerContextAdapterError("facts file is unreadable") from exc
    if not isinstance(document, dict) or document.get("schema_version") != FACTS_VERSION:
        raise OwnerContextAdapterError("facts schema version mismatch")
    if document.get("visibility_scope") != "OWNER_CONTEXT" or document.get("trading_authority") is not False:
        raise OwnerContextAdapterError("facts authority boundary mismatch")
    rows = document.get("components")
    if not isinstance(rows, list): raise OwnerContextAdapterError("components must be an array")
    parsed = tuple(_facts(row) for row in rows)
    by_component = {row.component: row for row in parsed}
    if len(by_component) != len(parsed): raise OwnerContextAdapterError("duplicate component facts")
    policy = ResiliencePolicyV1.create(required_components=("btc-recorder", "es-nq-recorder"),
        heartbeat_rpo_seconds=120, recovery_rto_seconds=300,
        minimum_free_bytes=5_000_000_000, maximum_clock_skew_seconds=2, maximum_restarts=5)
    return adapt_owner_context_health(reader=_Reader(by_component), identities=_identities(repository),
                                      policy=policy, as_of=as_of)


def report_json(report: AdaptedOwnerContextHealthV1) -> str:
    def convert(value):
        if hasattr(value, "value"): return value.value
        if isinstance(value, datetime): return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        raise TypeError(type(value).__name__)
    payload = asdict(report)
    return json.dumps(payload, default=convert, sort_keys=True, separators=(",", ":")) + "\n"
