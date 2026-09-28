"""Fail-closed, read-only assembly of supervised paper launch evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

from execution.supervised_paper_launch_evidence_v1 import EVIDENCE_VERSION, read_launch_evidence

COLLECTOR_VERSION = "supervised-paper-launch-evidence-collector-v1"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path, name: str) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    if value.get("trading_authority") is not False:
        raise ValueError(f"{name} authority boundary mismatch")
    return value


def _utc(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be UTC")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC")
    return parsed


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _git_oid(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) not in (40,64) or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be a lowercase SHA-1 or SHA-256 object ID")
    return value


def collect_launch_evidence(*, watchdog_path: Path, recovery_drill_path: Path,
        stale_drill_path: Path, repository_checkpoint: str, repository_clean: bool,
        btc_task_state: str, es_nq_task_state: str, es_nq_last_result: int,
        es_nq_missed_runs: int, collected_at: datetime) -> dict:
    _git_oid(repository_checkpoint, "repository_checkpoint")
    if repository_clean is not True:
        raise ValueError("repository must be clean")
    if collected_at.tzinfo is None or collected_at.utcoffset() != timedelta(0):
        raise ValueError("collected_at must be UTC")
    if isinstance(es_nq_last_result, bool) or not isinstance(es_nq_last_result, int):
        raise ValueError("es_nq_last_result must be integer")
    if isinstance(es_nq_missed_runs, bool) or not isinstance(es_nq_missed_runs, int) or es_nq_missed_runs < 0:
        raise ValueError("es_nq_missed_runs must be nonnegative integer")

    watchdog = _read(watchdog_path, "watchdog report")
    recovery = _read(recovery_drill_path, "recovery drill")
    stale = _read(stale_drill_path, "stale alert drill")
    if watchdog.get("adapter_version") != "OWNER_CONTEXT_HEALTH_ADAPTER_V1":
        raise ValueError("watchdog report version mismatch")
    if watchdog.get("readiness", {}).get("state") != "HEALTHY":
        raise ValueError("watchdog is not healthy")
    watchdog_id = _sha(watchdog.get("report_id"), "watchdog_report_id")
    if recovery.get("schema_version") != "controlled-btc-recorder-recovery-drill-v1" or recovery.get("result") != "RECOVERY_VERIFIED":
        raise ValueError("recovery drill is not verified")
    if stale.get("schema_version") != "controlled-stale-alert-drill-v1" or stale.get("result") != "STALE_ALERT_AND_RECOVERY_VERIFIED":
        raise ValueError("stale alert drill is not verified")
    for key in ("stale_observed", "unhealthy_alert_delivered", "recovery_observed", "healthy_alert_delivered"):
        if stale.get(key) is not True:
            raise ValueError(f"stale alert drill missing {key}")
    observations = watchdog.get("observations")
    if not isinstance(observations, list) or len(observations) != 2:
        raise ValueError("watchdog observations mismatch")
    by_component = {item.get("component"): item for item in observations if isinstance(item, dict)}
    if set(by_component) != {"btc-recorder", "es-nq-recorder"}:
        raise ValueError("watchdog component set mismatch")
    btc = by_component["btc-recorder"]
    if btc.get("trading_authority") is not False or btc.get("task_running") is not True:
        raise ValueError("BTC recorder observation is not running")
    heartbeat = _utc(btc.get("latest_heartbeat_at"), "btc_heartbeat_at")
    gap_count = btc.get("unresolved_gap_count")
    skew = btc.get("clock_skew_seconds")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (gap_count, skew)) or gap_count < 0:
        raise ValueError("watchdog numeric facts are invalid")
    source_paths = (watchdog_path, recovery_drill_path, stale_drill_path)
    body = {
        "schema_version": EVIDENCE_VERSION,
        "collected_at": collected_at.astimezone(timezone.utc).isoformat(),
        "repository_checkpoint": repository_checkpoint,
        "repository_clean": True,
        "watchdog_state": "HEALTHY",
        "watchdog_report_id": watchdog_id,
        "btc_task_state": btc_task_state,
        "btc_recorder_health": "HEALTHY",
        "btc_heartbeat_at": heartbeat.isoformat(),
        "btc_unresolved_gap_count": gap_count,
        "es_nq_task_state": es_nq_task_state,
        "es_nq_last_result": es_nq_last_result,
        "es_nq_missed_runs": es_nq_missed_runs,
        "recovery_drill_result": recovery["result"],
        "recovery_drill_report_id": _sha(recovery.get("report_id"), "recovery_drill_report_id"),
        "stale_alert_drill_result": stale["result"],
        "stale_alert_drill_report_id": _sha(stale.get("report_id"), "stale_alert_drill_report_id"),
        "unhealthy_alert_delivered": True,
        "healthy_alert_delivered": True,
        "clock_skew_seconds": skew,
        "source_file_sha256": sorted(_sha_bytes(path) for path in source_paths),
        "trading_authority": False,
    }
    return {**body, "evidence_id": hashlib.sha256(_canonical(body).encode()).hexdigest()}


def write_launch_evidence(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(_canonical(value) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    read_launch_evidence(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect read-only supervised paper launch evidence")
    parser.add_argument("--watchdog", type=Path, required=True)
    parser.add_argument("--recovery-drill", type=Path, required=True)
    parser.add_argument("--stale-drill", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--repository-clean", choices=("true", "false"), required=True)
    parser.add_argument("--btc-task-state", required=True)
    parser.add_argument("--es-nq-task-state", required=True)
    parser.add_argument("--es-nq-last-result", type=int, required=True)
    parser.add_argument("--es-nq-missed-runs", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = collect_launch_evidence(watchdog_path=args.watchdog, recovery_drill_path=args.recovery_drill,
        stale_drill_path=args.stale_drill, repository_checkpoint=args.checkpoint,
        repository_clean=args.repository_clean == "true", btc_task_state=args.btc_task_state,
        es_nq_task_state=args.es_nq_task_state, es_nq_last_result=args.es_nq_last_result,
        es_nq_missed_runs=args.es_nq_missed_runs, collected_at=datetime.now(timezone.utc))
    write_launch_evidence(args.output, value)
    print(f"SUPERVISED_PAPER_LAUNCH_EVIDENCE_WRITTEN:{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
