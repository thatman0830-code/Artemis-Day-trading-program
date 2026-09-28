"""Canonical, immutable attribution for supervised paper-session attempts.

This module reads local evidence only.  It does not score strategies, invent an
exit reason, or grant trading authority.  Missing or inconsistent evidence is
made explicit in the resulting attribution rather than silently inferred.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any


SCHEMA = "paper-session-attribution-v2"
ARTIFACT = "session-attribution-v2.json"
STRATEGY_HISTORY_SCHEMA = "btc-canonical-strategy-status-history-v1"
MAXIMUM_STRATEGY_HISTORY_BYTES = 8 * 1024 * 1024


class PaperSessionAttributionError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, None
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaperSessionAttributionError(f"unreadable evidence: {path.name}") from exc
    if type(value) is not dict:
        raise PaperSessionAttributionError(f"invalid evidence object: {path.name}")
    return value, _sha(raw)


def _read_strategy_history(path: Path, final_status: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file(): return None, None
    raw=path.read_bytes()
    if not raw or len(raw)>MAXIMUM_STRATEGY_HISTORY_BYTES:
        raise PaperSessionAttributionError("strategy history size is invalid")
    previous=None;first=None;last=None;count=0
    for sequence,line in enumerate(raw.splitlines()):
        try:event=json.loads(line)
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:
            raise PaperSessionAttributionError("strategy history is unreadable") from exc
        if (type(event) is not dict or event.get("schema_version")!=STRATEGY_HISTORY_SCHEMA
                or event.get("sequence")!=sequence or event.get("previous_event_id")!=previous
                or event.get("trading_authority") is not False):
            raise PaperSessionAttributionError("strategy history chain is invalid")
        event_id=event.get("event_id");body={key:value for key,value in event.items() if key!="event_id"}
        if type(event_id) is not str or event_id!=_sha(_canonical(body)):
            raise PaperSessionAttributionError("strategy history identity is invalid")
        if first is None:first=event
        last=event;previous=event_id;count+=1
    if final_status is not None and last.get("status_id")!=final_status.get("status_id"):
        raise PaperSessionAttributionError("strategy history final status mismatch")
    return {"event_count":count,"first_event_id":first["event_id"],
            "last_event_id":last["event_id"],"final_status_id":last.get("status_id")},_sha(raw)


def _verify_envelope(document: dict[str, Any] | None, name: str) -> None:
    if document is None:
        return
    if "payload" not in document or "payload_sha256" not in document:
        raise PaperSessionAttributionError(f"invalid checkpoint envelope: {name}")
    if _sha(_canonical(document["payload"])) != document["payload_sha256"]:
        raise PaperSessionAttributionError(f"checkpoint checksum mismatch: {name}")


def _tuple(value: Any) -> list[Any]:
    if type(value) is dict and set(value) == {"$tuple"} and type(value["$tuple"]) is list:
        return value["$tuple"]
    raise PaperSessionAttributionError("invalid canonical tuple")


def _decimal(value: Any, label: str) -> str:
    if type(value) is dict and set(value) == {"$decimal"} and type(value["$decimal"]) is str:
        return value["$decimal"]
    raise PaperSessionAttributionError(f"invalid canonical decimal: {label}")


def _time(value: Any, label: str) -> datetime:
    if type(value) is dict and set(value) == {"$datetime"}:
        value = value["$datetime"]
    if type(value) is not str:
        raise PaperSessionAttributionError(f"invalid timestamp: {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PaperSessionAttributionError(f"invalid timestamp: {label}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PaperSessionAttributionError(f"non-UTC timestamp: {label}")
    return parsed.astimezone(timezone.utc)


def _derive_protective_exit(receipts: list[Any], records: list[Any],
                            fills: list[Any]) -> str | None:
    """Prove stop/target from an accepted pair, atomic resolution and fill binding."""
    pairs = [item for item in receipts if type(item) is dict and item.get("accepted") is True
             and item.get("reason") == "CONTINGENT_PAIR_APPLIED"]
    resolutions = [item for item in receipts if type(item) is dict and item.get("accepted") is True
                   and item.get("reason") == "CONTINGENT_RESOLUTION_APPLIED"]
    proven = []
    bound_orders = {item.get("fields", {}).get("paper_order_id")
                    for item in fills if type(item) is dict}
    by_id = {item.get("paper_order_id"): item for item in records if type(item) is dict}
    for resolution in resolutions:
        order_ids = resolution.get("paper_order_ids")
        if type(order_ids) is not list or len(order_ids) != 2 or len(set(order_ids)) != 2:
            raise PaperSessionAttributionError("invalid contingent resolution receipt")
        pair = next((item for item in pairs if item.get("pair_id") == resolution.get("pair_id")
                     and item.get("paper_order_ids") == order_ids), None)
        retained = [by_id.get(order_id) for order_id in order_ids]
        if pair is None or any(item is None for item in retained):
            raise PaperSessionAttributionError("unbound contingent resolution receipt")
        filled = [index for index, item in enumerate(retained) if item.get("state") == "FILLED"]
        cancelled = [index for index, item in enumerate(retained) if item.get("state") == "CANCELLED"]
        if len(filled) != 1 or len(cancelled) != 1 or filled[0] == cancelled[0]:
            raise PaperSessionAttributionError("ambiguous contingent terminal state")
        winner = order_ids[filled[0]]
        if winner not in bound_orders:
            raise PaperSessionAttributionError("protective winner lacks accounting binding")
        # Pair admission canonically orders adverse STOP_MARKET first and favorable LIMIT second.
        proven.append("STOP_LOSS" if filled[0] == 0 else "PROFIT_TARGET")
    if len(proven) > 1:
        raise PaperSessionAttributionError("multiple protective exits in one session")
    return proven[0] if proven else None


def build_attribution(session_root: Path, *, attempt_exit_code: int) -> dict[str, Any]:
    if type(attempt_exit_code) is not int or attempt_exit_code < 0:
        raise PaperSessionAttributionError("invalid attempt exit code")
    root = session_root.resolve()
    if not root.is_dir():
        raise PaperSessionAttributionError("session root is unavailable")
    names = ("runtime-result.json", "canonical-strategy-status.json",
             "adapter-checkpoint.json", "performance-checkpoint.json",
             "latest-health.json", "attempt-failure.json")
    evidence: dict[str, dict[str, Any] | None] = {}
    hashes: dict[str, str | None] = {}
    for name in names:
        evidence[name], hashes[name] = _read(root / name)
    _verify_envelope(evidence["adapter-checkpoint.json"], "adapter-checkpoint.json")
    _verify_envelope(evidence["performance-checkpoint.json"], "performance-checkpoint.json")

    runtime = evidence["runtime-result.json"]
    strategy = evidence["canonical-strategy-status.json"]
    adapter = evidence["adapter-checkpoint.json"]
    performance = evidence["performance-checkpoint.json"]
    latest_health = evidence["latest-health.json"]
    failure = evidence["attempt-failure.json"]
    history,history_hash=_read_strategy_history(root.parent/
        (root.name+"-canonical-strategy-history.jsonl"),strategy)
    hashes["canonical-strategy-history.jsonl"]=history_hash
    if failure is not None:
        from execution.paper_attempt_failure_v1 import CODES
        _verify_envelope(failure,"attempt-failure.json")
        failure_payload=failure["payload"]
        if (failure.get("schema_version")!="paper-attempt-failure-v1"
                or failure_payload.get("session_directory")!=root.name
                or failure_payload.get("failure_code") not in CODES
                or failure_payload.get("trading_authority") is not False):
            raise PaperSessionAttributionError("invalid attempt failure evidence")
    else:failure_payload=None
    receipts: list[Any] = []
    fills: list[Any] = []
    final: dict[str, str] | None = None
    session_financials: dict[str, str] | None = None
    ledger_id = None
    gateway_snapshot_id = None
    for name, document in evidence.items():
        if document is not None and document.get("trading_authority") is True:
            raise PaperSessionAttributionError(f"trading authority present: {name}")
        if document is not None and type(document.get("payload")) is dict \
                and document["payload"].get("trading_authority") is True:
            raise PaperSessionAttributionError(f"trading authority present: {name}")
    if adapter is not None:
        receipts = adapter["payload"].get("receipts", [])
        if type(receipts) is not list:
            raise PaperSessionAttributionError("invalid adapter receipts")
        gateway_snapshot_id = adapter["payload"].get("gateway_checkpoint", {}).get("payload", {}).get("snapshot_id")
        gateway_records = adapter["payload"].get("gateway_checkpoint", {}).get("payload", {}).get("records", [])
        if type(gateway_records) is not list:
            raise PaperSessionAttributionError("invalid gateway records")
    else:
        gateway_records = []
    if performance is not None:
        ledger = performance["payload"].get("ledger", {}).get("fields", {})
        ledger_id = ledger.get("ledger_id")
        gateway_bound = ledger.get("gateway_snapshot_id")
        if gateway_snapshot_id is not None and gateway_bound != gateway_snapshot_id:
            raise PaperSessionAttributionError("gateway checkpoint binding mismatch")
        fills = _tuple(ledger.get("fill_bindings"))
        snapshots = _tuple(ledger.get("accounting", {}).get("fields", {}).get("snapshots"))
        if snapshots:
            if runtime is None or runtime.get("started_at") is None:
                baseline_item = snapshots[0]
            else:
                started = _time(runtime["started_at"], "runtime.started_at")
                eligible = [item for item in snapshots
                            if _time(item.get("fields", {}).get("as_of"), "snapshot.as_of") <= started]
                baseline_item = eligible[-1] if eligible else snapshots[0]
            baseline = baseline_item.get("fields", {})
            fields = snapshots[-1].get("fields", {})
            final = {
                "cash": _decimal(fields.get("cash"), "cash"),
                "equity": _decimal(fields.get("equity"), "equity"),
                "gross_realized_pnl": _decimal(fields.get("gross_realized_pnl"), "gross_realized_pnl"),
                "net_result": _decimal(fields.get("net_result"), "net_result"),
                "position_quantity": _decimal(fields.get("position", {}).get("fields", {}).get("signed_quantity"), "position_quantity"),
                "total_costs": _decimal(fields.get("total_costs"), "total_costs"),
                "unrealized_pnl": _decimal(fields.get("unrealized_pnl"), "unrealized_pnl"),
            }
            session_financials = {
                "baseline_snapshot_id": str(baseline.get("snapshot_id")),
                "final_snapshot_id": str(fields.get("snapshot_id")),
                "net_result": str(Decimal(final["net_result"]) - Decimal(_decimal(baseline.get("net_result"), "baseline.net_result"))),
                "total_costs": str(Decimal(final["total_costs"]) - Decimal(_decimal(baseline.get("total_costs"), "baseline.total_costs"))),
                "gross_realized_pnl": str(Decimal(final["gross_realized_pnl"]) - Decimal(_decimal(baseline.get("gross_realized_pnl"), "baseline.gross_realized_pnl"))),
            }

    missing = [name for name in (*names,"canonical-strategy-history.jsonl")
               if (history is None if name=="canonical-strategy-history.jsonl" else evidence[name] is None)
               and not (name == "attempt-failure.json" and attempt_exit_code == 0)]
    completed = attempt_exit_code == 0 and runtime is not None and runtime.get("state") == "STOPPED"
    if attempt_exit_code != 0:
        outcome, explanation = "FAILED_CLOSED", "Paper attempt returned a nonzero exit code."
    elif not completed:
        outcome, explanation = "INCOMPLETE", "Completion is not proven by STOPPED runtime evidence."
    elif not fills and runtime.get("commands") == 0:
        outcome, explanation = "NO_TRADE", "No paper command or verified fill was recorded."
    elif final is None or session_financials is None:
        outcome, explanation = "UNATTRIBUTED", "Financial outcome is unavailable."
    elif final["position_quantity"] != "0":
        outcome, explanation = "OPEN_EXPOSURE", "A non-flat final paper position remains."
    else:
        try:
            net = Decimal(session_financials["net_result"])
        except InvalidOperation as exc:
            raise PaperSessionAttributionError("invalid final net result") from exc
        outcome = "WIN" if net > 0 else "LOSS" if net < 0 else "BREAK_EVEN"
        explanation = "Classification is based on verified final net result after recorded costs."

    exit_reason = _derive_protective_exit(receipts, gateway_records, fills)
    if outcome == "NO_TRADE":
        exit_status = "NOT_APPLICABLE"
    elif exit_reason is not None:
        exit_status = "PROVEN"
    else:
        exit_status = "NOT_PROVEN"
    runtime_termination = None if runtime is None else runtime.get("termination_reason")
    health_terminations = {
        "HALTED_STALE_INPUT": "STALE_INPUT",
        "HALTED_FUTURE_INPUT": "FUTURE_INPUT_OR_CLOCK_FAILURE",
        "HALTED_PERFORMANCE_PERSISTENCE": "PERSISTENCE_FAILURE",
        "RECONCILIATION_REQUIRED": "RECONCILIATION_REQUIRED",
    }
    health_termination = health_terminations.get(
        None if latest_health is None else latest_health.get("state"))
    if runtime_termination in {"SUPERVISOR_STOP", "SESSION_DEADLINE", "CYCLE_LIMIT"}:
        termination_reason, termination_status = runtime_termination, "PROVEN"
    elif failure_payload is not None:
        termination_reason, termination_status = failure_payload.get("failure_code"), "PROVEN"
    elif health_termination is not None:
        termination_reason, termination_status = health_termination, "PROVEN"
    elif attempt_exit_code != 0:
        termination_reason, termination_status = "FAILED_CLOSED_UNCLASSIFIED", "NOT_PROVEN"
    else:
        termination_reason, termination_status = "LEGACY_UNSPECIFIED", "NOT_PROVEN"
    payload = {
        "schema_version": SCHEMA,
        "session_directory": root.name,
        "attempt_exit_code": attempt_exit_code,
        "runtime": None if runtime is None else {
            key: runtime.get(key) for key in ("runtime_id", "session_id", "started_at", "stopped_at", "state", "cycles", "commands", "termination_reason")},
        "strategy": None if strategy is None else {
            key: strategy.get(key) for key in ("observation_id", "result_id", "result_outcome", "decision_reason", "actionable", "qualification_present", "entry_zone_present")},
        "strategy_history": history,
        "evidence_sha256": hashes,
        "missing_evidence": missing,
        "ledger_id": ledger_id,
        "gateway_snapshot_id": gateway_snapshot_id,
        "receipt_count": len(receipts),
        "fill_count": len(fills),
        "final_accounting": final,
        "session_financials": session_financials,
        "outcome": outcome,
        "explanation": explanation,
        "exit_reason": exit_reason,
        "exit_reason_status": exit_status,
        "termination_reason": termination_reason,
        "termination_reason_status": termination_status,
        "advisory_only": True,
        "live_trading_permitted": False,
        "trading_authority": False,
    }
    return {"schema_version": SCHEMA, "payload": payload,
            "payload_sha256": _sha(_canonical(payload))}


def write_attribution(session_root: Path, *, attempt_exit_code: int,
                      output: Path | None = None) -> dict[str, Any]:
    document = build_attribution(session_root, attempt_exit_code=attempt_exit_code)
    path = output or session_root / ARTIFACT
    raw = _canonical(document) + b"\n"
    if path.exists():
        if path.read_bytes() == raw:
            return document
        raise PaperSessionAttributionError("immutable attribution already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise PaperSessionAttributionError("immutable attribution already exists") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-root", type=Path, required=True)
    parser.add_argument("--attempt-exit-code", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = write_attribution(args.session_root, attempt_exit_code=args.attempt_exit_code,
                                 output=args.output)
    print(json.dumps({"state": "ATTRIBUTION_RECORDED",
                      "outcome": document["payload"]["outcome"],
                      "payload_sha256": document["payload_sha256"],
                      "trading_authority": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
