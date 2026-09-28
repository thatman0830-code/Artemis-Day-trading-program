"""Deterministic evaluation of immutable supervised-paper attributions."""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from execution.paper_session_attribution_v1 import SCHEMA as ATTRIBUTION_SCHEMA
from execution.paper_strategy_history_binding_v1 import read_binding


SCHEMA = "paper-attribution-cohort-v1"
OUTCOMES = {"WIN", "LOSS", "BREAK_EVEN", "NO_TRADE", "OPEN_EXPOSURE",
            "INCOMPLETE", "FAILED_CLOSED", "UNATTRIBUTED"}


class PaperAttributionCohortError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _decimal(value: Any, label: str) -> Decimal:
    if type(value) is not str:
        raise PaperAttributionCohortError(f"invalid decimal: {label}")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise PaperAttributionCohortError(f"invalid decimal: {label}") from exc
    if not result.is_finite():
        raise PaperAttributionCohortError(f"non-finite decimal: {label}")
    return result


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaperAttributionCohortError(f"unreadable attribution: {path}") from exc
    if type(document) is not dict or set(document) != {"schema_version", "payload", "payload_sha256"}:
        raise PaperAttributionCohortError(f"invalid attribution envelope: {path}")
    payload = document["payload"]
    if document["schema_version"] != ATTRIBUTION_SCHEMA or type(payload) is not dict \
            or payload.get("schema_version") != ATTRIBUTION_SCHEMA:
        raise PaperAttributionCohortError(f"unsupported attribution schema: {path}")
    if _sha(_canonical(payload)) != document["payload_sha256"]:
        raise PaperAttributionCohortError(f"attribution checksum mismatch: {path}")
    if payload.get("trading_authority") is not False or payload.get("live_trading_permitted") is not False:
        raise PaperAttributionCohortError(f"attribution authority violation: {path}")
    if payload.get("outcome") not in OUTCOMES:
        raise PaperAttributionCohortError(f"invalid attribution outcome: {path}")
    return payload, _sha(raw)


def evaluate(sessions_root: Path, *, minimum_finalized_trades: int = 200) -> dict[str, Any]:
    if type(minimum_finalized_trades) is not int or minimum_finalized_trades < 1:
        raise PaperAttributionCohortError("minimum finalized trades must be positive")
    paths = sorted(sessions_root.glob("*/session-attribution-v2.json"))
    records = []
    seen = set()
    for path in paths:
        payload, file_hash = _load(path);binding_hash=read_binding(path)
        session = payload.get("session_directory")
        if type(session) is not str or session != path.parent.name or session in seen:
            raise PaperAttributionCohortError("duplicate or mismatched session identity")
        seen.add(session)
        stopped = (payload.get("runtime") or {}).get("stopped_at") or ""
        records.append((stopped, session, payload, file_hash,binding_hash))
    records.sort(key=lambda item: (item[0], item[1]))

    counts = Counter(record[2]["outcome"] for record in records)
    reasons = Counter((record[2].get("strategy") or {}).get("decision_reason") or "UNAVAILABLE"
                      for record in records)
    terminations = Counter(record[2].get("termination_reason") or "UNAVAILABLE"
                           for record in records)
    finalized = [record for record in records if record[2]["outcome"] in {"WIN", "LOSS", "BREAK_EVEN"}]
    values = [_decimal(record[2].get("session_financials", {}).get("net_result"),
                       f"{record[1]}.net_result") for record in finalized]
    wins = counts["WIN"]; losses = counts["LOSS"]
    gross_profit = sum((value for value in values if value > 0), Decimal(0))
    gross_loss = -sum((value for value in values if value < 0), Decimal(0))
    net = sum(values, Decimal(0))
    equity = Decimal(0); peak = Decimal(0); max_drawdown = Decimal(0)
    loss_streak = 0; longest_loss_streak = 0
    for record, value in zip(finalized, values):
        equity += value; peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        if record[2]["outcome"] == "LOSS":
            loss_streak += 1; longest_loss_streak = max(longest_loss_streak, loss_streak)
        else:
            loss_streak = 0
    complete_exit = all(record[2].get("exit_reason_status") in {"PROVEN", "NOT_APPLICABLE"}
                        for record in records)
    complete_termination = all(record[2].get("termination_reason_status") == "PROVEN"
                               for record in records)
    no_unresolved = not any(counts[key] for key in ("OPEN_EXPOSURE", "INCOMPLETE", "UNATTRIBUTED"))
    minimum_met = len(finalized) >= minimum_finalized_trades
    payload = {
        "schema_version": SCHEMA,
        "attribution_schema": ATTRIBUTION_SCHEMA,
        "session_count": len(records),
        "finalized_trade_session_count": len(finalized),
        "outcome_counts": {key: counts[key] for key in sorted(OUTCOMES)},
        "strategy_reason_counts": dict(sorted(reasons.items())),
        "termination_reason_counts": dict(sorted(terminations.items())),
        "performance": {
            "net_result": str(net),
            "gross_profit": str(gross_profit),
            "gross_loss": str(gross_loss),
            "expectancy_per_finalized_trade": None if not finalized else str(net / len(finalized)),
            "win_rate": None if not finalized else str(Decimal(wins) / len(finalized)),
            "profit_factor": None if gross_loss == 0 else str(gross_profit / gross_loss),
            "maximum_session_sequence_drawdown": str(max_drawdown),
            "longest_loss_streak": longest_loss_streak,
        },
        "evidence_gate": {
            "minimum_finalized_trades_required": minimum_finalized_trades,
            "minimum_sample_met": minimum_met,
            "complete_exit_attribution": complete_exit,
            "complete_termination_attribution": complete_termination,
            "no_unresolved_sessions": no_unresolved,
            "untouched_oos_eligibility": minimum_met and complete_exit and complete_termination and no_unresolved,
        },
        "attributions": [{"session_directory": record[1], "file_sha256": record[3],
                          "payload_sha256": _sha(_canonical(record[2])),
                          "strategy_history_binding_sha256":record[4]} for record in records],
        "advisory_only": True,
        "live_trading_permitted": False,
        "trading_authority": False,
    }
    return {"schema_version": SCHEMA, "payload": payload,
            "payload_sha256": _sha(_canonical(payload))}


def write_evaluation(sessions_root: Path, output_root: Path,
                     *, minimum_finalized_trades: int = 200) -> Path:
    document = evaluate(sessions_root, minimum_finalized_trades=minimum_finalized_trades)
    output_root.mkdir(parents=True, exist_ok=True)
    identity = document["payload_sha256"]
    path = output_root / f"{identity}.json"
    raw = _canonical(document) + b"\n"
    if path.exists() and path.read_bytes() != raw:
        raise PaperAttributionCohortError("content-addressed evaluation collision")
    if not path.exists():
        with path.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    pointer = {"schema_version": "paper-attribution-cohort-latest-v1",
               "evaluation_file": path.name, "evaluation_sha256": _sha(raw),
               "payload_sha256": identity, "trading_authority": False}
    temporary = output_root / f".latest.{os.getpid()}.tmp"
    temporary.write_bytes(_canonical(pointer) + b"\n")
    temporary.replace(output_root / "latest.json")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--minimum-finalized-trades", type=int, default=200)
    args = parser.parse_args()
    path = write_evaluation(args.sessions_root, args.output_root,
                            minimum_finalized_trades=args.minimum_finalized_trades)
    document = json.loads(path.read_text())
    print(json.dumps({"state": "COHORT_EVALUATED", "path": str(path),
                      "finalized_trade_session_count": document["payload"]["finalized_trade_session_count"],
                      "untouched_oos_eligibility": document["payload"]["evidence_gate"]["untouched_oos_eligibility"],
                      "trading_authority": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
