"""Fail-closed ingestion contract for an external Oracle research engine.

The adapter accepts observations only.  It deliberately exposes no wallet,
account, order, execution, or canonical-strategy mutation surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json


VERSION = "oracle-shadow-observation-v1"
ALLOWED_DIRECTIONS = frozenset({"BULLISH", "BEARISH", "NEUTRAL"})


@dataclass(frozen=True)
class OracleShadowObservationV1:
    observation_id: str
    engine_id: str
    instrument: str
    timeframe: str
    observed_at: datetime
    source_event_time: datetime
    direction: str
    confidence: Decimal | None
    source_payload_sha256: str
    comparison_only: bool = True
    canonical_strategy_influence_permitted: bool = False
    order_influence_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def _utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def parse_oracle_observation(raw: bytes, *, received_at: datetime) -> OracleShadowObservationV1:
    if received_at.tzinfo is None or received_at.utcoffset() != timedelta(0):
        raise ValueError("received_at must be UTC")
    try:
        payload = json.loads(raw.decode("utf-8"), parse_float=str)
    except Exception as exc:
        raise ValueError("invalid Oracle JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Oracle observation must be an object")
    required = {"schema_version", "engine_id", "instrument", "timeframe",
                "observed_at", "source_event_time", "direction"}
    if not required <= set(payload) or payload["schema_version"] != VERSION:
        raise ValueError("Oracle observation schema is incompatible")
    for field in ("engine_id", "instrument", "timeframe"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"{field} is required")
    direction = str(payload["direction"]).upper()
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError("Oracle direction is invalid")
    observed = _utc(payload["observed_at"], "observed_at")
    event_time = _utc(payload["source_event_time"], "source_event_time")
    if event_time > observed or observed > received_at:
        raise ValueError("Oracle observation chronology is invalid")
    confidence = None
    if payload.get("confidence") is not None:
        try:
            confidence = Decimal(str(payload["confidence"]))
        except InvalidOperation as exc:
            raise ValueError("Oracle confidence is invalid") from exc
        if not confidence.is_finite() or not Decimal(0) <= confidence <= Decimal(1):
            raise ValueError("Oracle confidence must be between zero and one")
    digest = sha256(raw).hexdigest()
    identity = sha256((VERSION + "\x1f" + payload["engine_id"] + "\x1f" +
                       payload["instrument"] + "\x1f" + payload["timeframe"] +
                       "\x1f" + observed.isoformat() + "\x1f" + digest).encode()).hexdigest()
    return OracleShadowObservationV1(
        identity, payload["engine_id"], payload["instrument"], payload["timeframe"],
        observed, event_time, direction, confidence, digest,
    )
