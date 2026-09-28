from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from futures_data.forward_collector import ForwardCollectorError, ForwardSession


EXPECTED_SCHEMA = "es-nq-verified-forward-sessions-v1"
TICKER_PATTERN = re.compile(r"^(ES|NQ)[HMUZ][0-9]{1,2}$")


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_configuration(path: Path, *, repository: Path | None = None, manifest_path: Path | None = None) -> tuple[ForwardSession, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        raise ForwardCollectorError("forward configuration schema rejected")
    if payload.get("finalized") is not True:
        raise ForwardCollectorError("forward configuration is not finalized")
    if not isinstance(payload.get("source_id"), str) or not payload["source_id"]:
        raise ForwardCollectorError("forward configuration source identity rejected")
    if not isinstance(payload.get("schedule_version"), str) or not payload["schedule_version"]:
        raise ForwardCollectorError("forward configuration schedule version rejected")
    items = payload.get("sessions")
    if not isinstance(items, list):
        raise ForwardCollectorError("forward configuration sessions rejected")
    history = payload.get("history")
    if not isinstance(history, list):
        raise ForwardCollectorError("forward configuration history rejected")
    coverage = payload.get("verified_coverage")
    if not isinstance(coverage, dict) or not all(isinstance(coverage.get(x), str) for x in ("start_inclusive", "end_exclusive", "last_session")):
        raise ForwardCollectorError("forward configuration coverage rejected")
    if coverage["last_session"] >= coverage["end_exclusive"]:
        raise ForwardCollectorError("forward configuration coverage chronology rejected")
    if payload.get("pending_session_count") != len(items):
        raise ForwardCollectorError("forward configuration pending count rejected")
    material = dict(payload); config_id = material.pop("configuration_id", None)
    canonical = (json.dumps(material, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if not isinstance(config_id, str) or sha256(canonical).hexdigest() != config_id:
        raise ForwardCollectorError("forward configuration identity rejected")
    history_ids = set()
    latest_history_session = None
    for item in history:
        identity = (item.get("root"), item.get("session_date"), item.get("ticker"), item.get("contract_id"))
        if item.get("root") not in ("ES", "NQ") or item.get("state") != "ARCHIVED_IMMUTABLE" or identity in history_ids:
            raise ForwardCollectorError("forward configuration history identity rejected")
        if item.get("session_date") >= coverage["end_exclusive"]:
            raise ForwardCollectorError("forward history exceeds verified coverage")
        latest_history_session=max(latest_history_session or item["session_date"],item["session_date"])
        history_ids.add(identity)
    if repository is not None:
        repository = repository.resolve()
        manifest_path = manifest_path or path.with_name("es_nq_forward_sessions.manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("configuration_id") != config_id or manifest.get("configuration_sha256") != _hash(path):
            raise ForwardCollectorError("forward configuration manifest rejected")
        for fact in payload.get("evidence", []):
            evidence_path = (repository / fact["path"]).resolve()
            if repository not in evidence_path.parents or _hash(evidence_path) != fact["sha256"]:
                raise ForwardCollectorError("forward configuration provenance rejected")

    sessions: list[ForwardSession] = []
    identities: set[tuple[str, str, str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ForwardCollectorError("forward session record rejected")
        root = item["root"]
        ticker = item["ticker"]
        if not isinstance(ticker, str) or not TICKER_PATTERN.fullmatch(ticker) or not ticker.startswith(root):
            raise ForwardCollectorError("forward session ticker rejected")
        if not isinstance(item["contract_id"], str) or not item["contract_id"]:
            raise ForwardCollectorError("forward session contract identity rejected")
        intervals_value = item.get("active_intervals")
        if not isinstance(intervals_value, list) or not intervals_value:
            raise ForwardCollectorError("forward session intervals rejected")
        intervals = tuple(
            (
                datetime.fromisoformat(value["start_utc"].replace("Z", "+00:00")),
                datetime.fromisoformat(value["end_exclusive_utc"].replace("Z", "+00:00")),
            )
            for value in intervals_value
        )
        session = ForwardSession(
            root,
            item["session_date"],
            ticker,
            item["contract_id"],
            intervals,
            payload["source_id"],
            payload["schedule_version"],
            item.get("rollover_pair_id"),
            item.get("rollover_leg", "ACTIVE"),
        )
        identity = (session.root, session.session_date, session.ticker, session.rollover_leg)
        if identity in identities:
            raise ForwardCollectorError("duplicate forward session rejected")
        identities.add(identity)
        if latest_history_session is not None and session.session_date <= latest_history_session:
            raise ForwardCollectorError("archived session cannot re-enter pending queue")
        sessions.append(session)
    return tuple(sessions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from futures_data.forward_reference_refresh import resolve_current
        repository=args.repository.resolve();requested=args.configuration.resolve()
        if requested==repository/"config/es_nq_forward_sessions.json":configuration,manifest=resolve_current(repository,requested)
        else:configuration,manifest=requested,requested.with_name("es_nq_forward_sessions.manifest.json")
        validate_configuration(configuration, repository=repository,manifest_path=manifest)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, ForwardCollectorError) as error:
        print(f"BLOCKED: offline ES/NQ forward configuration validation failed ({type(error).__name__})", file=sys.stderr)
        return 2
    print("FORWARD_CONFIGURATION_VALIDATED_OFFLINE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
