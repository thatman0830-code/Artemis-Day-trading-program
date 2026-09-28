"""Crash-safe immutable history for ES/NQ canonical research evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import os
from pathlib import Path

from backtesting.futures_canonical_evaluation_v1 import FuturesCanonicalEvaluationV1
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket


VERSION = "futures-canonical-evaluation-history-v1"


class FuturesCanonicalHistoryError(RuntimeError):
    pass


def _canonical_value(value):
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise FuturesCanonicalHistoryError("history timestamp must be UTC")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in sorted(value.items())}
    return value


def _bytes(value: dict) -> bytes:
    return json.dumps(_canonical_value(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _payload(report: FuturesCanonicalEvaluationV1) -> dict:
    return {name: _canonical_value(getattr(report, name))
            for name in report.__dataclass_fields__}


@dataclass(frozen=True)
class FuturesCanonicalHistoryEventV1:
    event_id: str
    sequence: int
    previous_event_id: str | None
    market: FuturesCanonicalMarket
    evaluated_at: datetime
    report_id: str
    lane_id: str
    dataset_fingerprint: str
    latest_outcome: str
    report: dict
    schema_version: str = VERSION


def _decode(raw: bytes, *, expected_sequence: int,
            previous_event_id: str | None, market: FuturesCanonicalMarket
            ) -> FuturesCanonicalHistoryEventV1:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FuturesCanonicalHistoryError("history event is unreadable") from exc
    required = {"schema_version", "event_id", "sequence", "previous_event_id",
                "market", "evaluated_at", "report_id", "lane_id",
                "dataset_fingerprint", "latest_outcome", "report"}
    if not isinstance(value, dict) or set(value) != required:
        raise FuturesCanonicalHistoryError("history event schema is invalid")
    try:
        evaluated_at = datetime.fromisoformat(value["evaluated_at"].replace("Z", "+00:00"))
        parsed_market = FuturesCanonicalMarket(value["market"])
    except (TypeError, ValueError) as exc:
        raise FuturesCanonicalHistoryError("history event identity is invalid") from exc
    identity_payload = dict(value); claimed = identity_payload.pop("event_id")
    expected_id = hashlib.sha256(_bytes(identity_payload)).hexdigest()
    report = value["report"]
    if (value["schema_version"] != VERSION or value["sequence"] != expected_sequence
            or value["previous_event_id"] != previous_event_id
            or parsed_market is not market or claimed != expected_id
            or not isinstance(report, dict)
            or report.get("report_id") != value["report_id"]
            or report.get("lane_id") != value["lane_id"]
            or report.get("market") != market.value
            or report.get("evaluated_at") != value["evaluated_at"]
            or report.get("dataset_fingerprint") != value["dataset_fingerprint"]
            or report.get("latest_outcome") != value["latest_outcome"]):
        raise FuturesCanonicalHistoryError("history event chain or report binding is invalid")
    return FuturesCanonicalHistoryEventV1(claimed, expected_sequence,
        previous_event_id, parsed_market, evaluated_at, value["report_id"],
        value["lane_id"], value["dataset_fingerprint"], value["latest_outcome"], report)


def read_futures_canonical_history(
    root, *, market: FuturesCanonicalMarket
) -> tuple[FuturesCanonicalHistoryEventV1, ...]:
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ history market required")
    directory = Path(root).absolute() / market.value / "events"
    if not directory.exists():
        return ()
    if not directory.is_dir() or directory.is_symlink():
        raise FuturesCanonicalHistoryError("history event path is unsafe")
    paths = sorted(directory.iterdir(), key=lambda item: item.name)
    expected_names = [f"{index:020d}.json" for index in range(len(paths))]
    if [path.name for path in paths] != expected_names or any(
            not path.is_file() or path.is_symlink() for path in paths):
        raise FuturesCanonicalHistoryError("history event inventory is invalid")
    events = []; previous = None; last_time = None
    for sequence, path in enumerate(paths):
        event = _decode(path.read_bytes(), expected_sequence=sequence,
                        previous_event_id=previous, market=market)
        if last_time is not None and event.evaluated_at < last_time:
            raise FuturesCanonicalHistoryError("history chronology regressed")
        events.append(event); previous = event.event_id; last_time = event.evaluated_at
    return tuple(events)


def append_futures_canonical_evaluation(
    root, *, report: FuturesCanonicalEvaluationV1
) -> FuturesCanonicalHistoryEventV1:
    if not isinstance(report, FuturesCanonicalEvaluationV1):
        raise TypeError("canonical futures evaluation report required")
    if (report.advisory_only is not True or report.paper_execution_permitted is not False
            or report.live_trading_permitted is not False
            or report.trading_authority is not False):
        raise FuturesCanonicalHistoryError("authoritative evaluation cannot enter research history")
    base = Path(root).absolute()
    if base.exists() and (not base.is_dir() or base.is_symlink()):
        raise FuturesCanonicalHistoryError("history root is unsafe")
    events = read_futures_canonical_history(base, market=report.market)
    exact = tuple(event for event in events if event.report_id == report.report_id)
    if exact:
        if len(exact) != 1 or exact[0].report != _payload(report):
            raise FuturesCanonicalHistoryError("report identity conflicts with retained history")
        return exact[0]
    if events and report.evaluated_at < events[-1].evaluated_at:
        raise FuturesCanonicalHistoryError("evaluation chronology regressed")
    directory = base / report.market.value / "events"
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or directory.parent.is_symlink():
        raise FuturesCanonicalHistoryError("history directory is unsafe")
    body = {"schema_version": VERSION, "sequence": len(events),
        "previous_event_id": events[-1].event_id if events else None,
        "market": report.market.value,
        "evaluated_at": _canonical_value(report.evaluated_at),
        "report_id": report.report_id, "lane_id": report.lane_id,
        "dataset_fingerprint": report.dataset_fingerprint,
        "latest_outcome": report.latest_outcome, "report": _payload(report)}
    event_id = hashlib.sha256(_bytes(body)).hexdigest()
    document = {**body, "event_id": event_id}
    target = directory / f"{len(events):020d}.json"
    temporary = target.with_suffix(".json.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(_bytes(document)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return read_futures_canonical_history(base, market=report.market)[-1]

