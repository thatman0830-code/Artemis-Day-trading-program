"""Persist read-only owner-context readiness and secret-free alert transitions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from .owner_context_health_report import evaluate_sanitized_owner_facts, report_json

WATCHDOG_VERSION = "OWNER_CONTEXT_HEALTH_WATCHDOG_V1"
FAILURE_REASONS = ("HEALTH_COLLECTION_FAILED", "HEALTH_EVALUATION_FAILED")


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("watchdog timestamp must be UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical(value) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _read_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict) or set(value) != {"signature", "trading_authority"}:
        raise ValueError("watchdog state is malformed")
    if value["trading_authority"] is not False:
        raise ValueError("watchdog state authority boundary mismatch")
    return value


def _append_transition(output_dir: Path, *, signature: str, event: dict) -> bool:
    state_path = output_dir / "alert-state.json"
    previous = _read_state(state_path)
    if previous and previous["signature"] == signature:
        return False
    event_body = {**event, "watchdog_version": WATCHDOG_VERSION, "trading_authority": False}
    event_id = hashlib.sha256(_canonical(event_body).encode("utf-8")).hexdigest()
    alert_path = output_dir / "alerts.jsonl"
    alert_path.parent.mkdir(parents=True, exist_ok=True)
    with alert_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(_canonical({**event_body, "event_id": event_id}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    _atomic_json(state_path, {"signature": signature, "trading_authority": False})
    return True


def evaluate_and_persist(*, facts_path: Path, repository: Path, output_dir: Path,
                         as_of: datetime) -> dict:
    report = evaluate_sanitized_owner_facts(
        facts_path=facts_path, repository=repository, as_of=as_of)
    payload = json.loads(report_json(report))
    if payload.get("trading_authority") is not False:
        raise ValueError("watchdog report authority boundary mismatch")
    report_id = payload["report_id"]
    _atomic_json(output_dir / "reports" / f"{report_id}.json", payload)
    _atomic_json(output_dir / "latest-readiness.json", payload)
    readiness = payload["readiness"]
    _atomic_json(output_dir / "latest-watchdog-status.json", {
        "watchdog_version": WATCHDOG_VERSION, "observed_at": _utc(as_of),
        "state": readiness["state"], "ready_for_unattended_operation":
        readiness["ready_for_unattended_operation"], "report_id": report_id,
        "failure_reason": None, "trading_authority": False,
    })
    alert_basis = {
        "state": readiness["state"], "reasons": readiness["reasons"],
        "open_incident_ids": readiness["open_incident_ids"],
        "ready_for_unattended_operation": readiness["ready_for_unattended_operation"],
    }
    signature = hashlib.sha256(_canonical(alert_basis).encode("utf-8")).hexdigest()
    _append_transition(output_dir, signature=signature, event={
        "event": "READINESS_TRANSITION", "observed_at": _utc(as_of),
        "report_id": report_id, **alert_basis,
    })
    return payload


def record_failure(*, output_dir: Path, reason: str, as_of: datetime) -> bool:
    if reason not in FAILURE_REASONS:
        raise ValueError("unsupported watchdog failure reason")
    _atomic_json(output_dir / "latest-watchdog-status.json", {
        "watchdog_version": WATCHDOG_VERSION, "observed_at": _utc(as_of),
        "state": "UNHEALTHY", "ready_for_unattended_operation": False,
        "report_id": None, "failure_reason": reason, "trading_authority": False,
    })
    signature = hashlib.sha256(f"FAILURE:{reason}".encode("ascii")).hexdigest()
    return _append_transition(output_dir, signature=signature, event={
        "event": "WATCHDOG_FAILURE", "observed_at": _utc(as_of), "reason": reason,
        "state": "UNHEALTHY", "ready_for_unattended_operation": False,
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--record-failure", choices=FAILURE_REASONS)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if bool(args.facts) == bool(args.record_failure):
        parser.error("specify exactly one of --facts or --record-failure")
    if args.record_failure:
        record_failure(output_dir=args.output_dir, reason=args.record_failure, as_of=now)
    else:
        evaluate_and_persist(facts_path=args.facts, repository=args.repository,
                             output_dir=args.output_dir, as_of=now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
