"""Offline reconciliation of ES/NQ archive gaps against retained schedules."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path

from .oos_evidence import MissingIntervalV1
from .specifications import canonical_fingerprint

SESSION_GAP_VERSION = "SESSION_GAP_RECONCILIATION_V1"


class GapClassification(str, Enum):
    SCHEDULED_NON_TRADING_INTERVAL = "SCHEDULED_NON_TRADING_INTERVAL"
    MISSING_OPEN_SESSION_DATA = "MISSING_OPEN_SESSION_DATA"
    MIXED_REQUIRES_SPLIT = "MIXED_REQUIRES_SPLIT"


class SessionGapError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SessionIntervalV1:
    session_date: str
    open_inclusive: datetime
    close_exclusive: datetime


@dataclass(frozen=True, slots=True)
class ReconciledGapV1:
    source_gap: MissingIntervalV1
    classification: GapClassification
    overlapping_sessions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionGapReconciliationV1:
    reconciliation_id: str
    market: str
    schedule_sha256: str
    schedule_manifest_sha256: str
    product_name: str
    schedule_start_inclusive: datetime
    schedule_end_exclusive: datetime
    sessions: tuple[SessionIntervalV1, ...]
    gaps: tuple[ReconciledGapV1, ...]
    version: str = SESSION_GAP_VERSION
    trading_authority: bool = False


def _relative(repository: Path, value: str) -> Path:
    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise SessionGapError("evidence path must be repository-relative")
    root = repository.resolve(strict=True); path = (root / normalized).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise SessionGapError("evidence path escapes repository or is not a file")
    return path


def _object(payload: bytes, label: str) -> dict:
    try: value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise SessionGapError(f"{label} is invalid") from exc
    if not isinstance(value, dict): raise SessionGapError(f"{label} must be an object")
    return value


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str): raise SessionGapError(f"{field} is invalid")
    try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise SessionGapError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0): raise SessionGapError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def _sessions(raw: dict, market: str, product_name: str) -> tuple[SessionIntervalV1, ...]:
    if raw.get("status") != "OK" or not isinstance(raw.get("results"), list) or raw.get("next_url"):
        raise SessionGapError("schedule response is incomplete")
    grouped: dict[str, dict[str, datetime]] = {}
    for item in raw["results"]:
        if not isinstance(item, dict): raise SessionGapError("schedule record is invalid")
        if item.get("product_code") != market or item.get("product_name") != product_name:
            continue
        if item.get("trading_venue") != "XCME": raise SessionGapError("schedule venue mismatch")
        event = item.get("event")
        if event not in {"pre_open", "open", "close"}: raise SessionGapError("unknown schedule event")
        day = item.get("session_end_date")
        try: date.fromisoformat(day)
        except (TypeError, ValueError) as exc: raise SessionGapError("session date is invalid") from exc
        events = grouped.setdefault(day, {})
        if event in events: raise SessionGapError("duplicate schedule event")
        events[event] = _utc(item.get("timestamp"), "schedule timestamp")
    if not grouped: raise SessionGapError("expected outright schedule is absent")
    sessions = []
    for day, events in sorted(grouped.items()):
        if set(events) != {"pre_open", "open", "close"} or not events["pre_open"] <= events["open"] < events["close"]:
            raise SessionGapError("session schedule is incomplete or contradictory")
        sessions.append(SessionIntervalV1(day, events["open"], events["close"]))
    ordered = tuple(sorted(sessions, key=lambda item: item.open_inclusive))
    if any(left.close_exclusive > right.open_inclusive for left, right in zip(ordered, ordered[1:])):
        raise SessionGapError("session schedules overlap")
    return ordered


def reconcile_session_gaps(*, repository: Path, schedule_relative_path: str,
                           manifest_relative_path: str, market: str, product_name: str,
                           gaps: tuple[MissingIntervalV1, ...]) -> SessionGapReconciliationV1:
    if market not in {"ES", "NQ"} or not product_name.strip(): raise SessionGapError("market or product is invalid")
    schedule_path = _relative(repository, schedule_relative_path)
    manifest_path = _relative(repository, manifest_relative_path)
    schedule_bytes = schedule_path.read_bytes(); manifest_bytes = manifest_path.read_bytes()
    manifest = _object(manifest_bytes, "schedule manifest")
    schedule_digest = sha256(schedule_bytes).hexdigest()
    required = {"schema_version","root","endpoint_class","http_status","raw_bytes",
                "raw_sha256","raw_relative_path","automatic_retry"}
    if (not required <= set(manifest) or manifest["root"] != market
            or manifest["endpoint_class"] != "futures_schedules" or manifest["http_status"] != 200
            or manifest["raw_bytes"] != len(schedule_bytes) or manifest["raw_sha256"] != schedule_digest
            or manifest["automatic_retry"] is not False
            or not schedule_relative_path.replace("\\", "/").endswith(manifest["raw_relative_path"])):
        raise SessionGapError("schedule manifest verification failed")
    sessions = _sessions(_object(schedule_bytes, "schedule response"), market, product_name)
    start, end = sessions[0].open_inclusive, sessions[-1].close_exclusive
    reconciled = []
    for gap in gaps:
        if gap.timeframe != "1m" or gap.start_inclusive < start or gap.end_exclusive > end:
            raise SessionGapError("gap is outside authoritative schedule coverage")
        overlaps = tuple(item for item in sessions
                         if item.open_inclusive < gap.end_exclusive and item.close_exclusive > gap.start_inclusive)
        overlap_seconds = sum((min(gap.end_exclusive, item.close_exclusive)
                               - max(gap.start_inclusive, item.open_inclusive)).total_seconds()
                              for item in overlaps)
        gap_seconds = (gap.end_exclusive - gap.start_inclusive).total_seconds()
        classification = (GapClassification.SCHEDULED_NON_TRADING_INTERVAL if overlap_seconds == 0
                          else GapClassification.MISSING_OPEN_SESSION_DATA if overlap_seconds == gap_seconds
                          else GapClassification.MIXED_REQUIRES_SPLIT)
        reconciled.append(ReconciledGapV1(gap, classification,
                                          tuple(item.session_date for item in overlaps)))
    manifest_digest = sha256(manifest_bytes).hexdigest()
    ident = canonical_fingerprint(SESSION_GAP_VERSION, market, schedule_digest, manifest_digest,
                                  product_name, sessions, tuple(reconciled), False)
    return SessionGapReconciliationV1(ident, market, schedule_digest, manifest_digest,
                                      product_name, start, end, sessions, tuple(reconciled))
