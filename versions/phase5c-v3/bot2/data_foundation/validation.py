"""Fail-closed validation for normalized market events."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib, json
from typing import Iterable, Sequence

from .contracts import DataQualityReport, MarketEvent, QualityReason


def _hash(events: Sequence[MarketEvent]) -> str:
    payload = "\n".join(json.dumps(e.to_dict(), sort_keys=True, separators=(",", ":")) for e in events)
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_events(
    events: Iterable[MarketEvent], *, as_of: datetime | None = None,
    max_age: timedelta = timedelta(seconds=5), expected_interval: timedelta | None = None,
    require_contiguous_sequence: bool = False,
) -> tuple[tuple[MarketEvent, ...], DataQualityReport]:
    rows = tuple(events)
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None or as_of.utcoffset() != timezone.utc.utcoffset(as_of):
        raise ValueError("as_of must be UTC")
    reasons: Counter[str] = Counter()
    seen: set[tuple[object, ...]] = set()
    accepted: list[MarketEvent] = []
    previous_time: datetime | None = None
    previous_sequence: int | None = None
    max_latency: float | None = None
    for event in rows:
        if not isinstance(event, MarketEvent):
            reasons[QualityReason.INVALID_SCHEMA.value] += 1; continue
        if event.identity in seen:
            reasons[QualityReason.DUPLICATE_EVENT.value] += 1; continue
        seen.add(event.identity)
        valid = True
        if event.price <= 0: reasons[QualityReason.INVALID_PRICE.value] += 1; valid = False
        if event.volume < 0: reasons[QualityReason.INVALID_VOLUME.value] += 1; valid = False
        if event.exchange_time > as_of:
            reasons[QualityReason.FUTURE_EVENT.value] += 1; valid = False
        if as_of - event.exchange_time > max_age:
            reasons[QualityReason.STALE_EVENT.value] += 1; valid = False
        if previous_time is not None:
            if event.exchange_time < previous_time:
                reasons[QualityReason.TIMESTAMP_REGRESSION.value] += 1; valid = False
            if expected_interval is not None and event.exchange_time - previous_time > expected_interval:
                reasons[QualityReason.INTERVAL_GAP.value] += 1; valid = False
        if event.sequence is not None and previous_sequence is not None:
            if event.sequence <= previous_sequence:
                reasons[QualityReason.SEQUENCE_REGRESSION.value] += 1; valid = False
            elif require_contiguous_sequence and event.sequence != previous_sequence + 1:
                reasons[QualityReason.SEQUENCE_GAP.value] += 1; valid = False
        if event.receive_timestamp_available:
            if event.receipt_time is None or event.receipt_time < event.exchange_time:
                reasons[QualityReason.INVALID_SCHEMA.value] += 1; valid = False
            else:
                latency = (event.receipt_time - event.exchange_time).total_seconds()
                max_latency = latency if max_latency is None else max(max_latency, latency)
        elif event.receipt_time is not None:
            reasons[QualityReason.INVALID_SCHEMA.value] += 1; valid = False
        previous_time = event.exchange_time
        if event.sequence is not None: previous_sequence = event.sequence
        if valid: accepted.append(event)
    if not rows: reasons[QualityReason.EMPTY_DATASET.value] += 1
    state = "HEALTHY" if rows and not reasons else ("UNSAFE" if reasons else "HEALTHY")
    report = DataQualityReport(state=state, checked_events=len(rows), accepted_events=len(accepted),
        reason_counts=dict(sorted(reasons.items())), reasons=tuple(sorted(reasons)),
        first_exchange_time=accepted[0].exchange_time.isoformat() if accepted else None,
        last_exchange_time=accepted[-1].exchange_time.isoformat() if accepted else None,
        max_latency_seconds=max_latency, event_hash=_hash(accepted), trading_authority=False)
    if reasons:
        raise DataQualityError(report)
    return tuple(accepted), report


class DataQualityError(ValueError):
    def __init__(self, report: DataQualityReport):
        self.report = report
        super().__init__("data-quality validation failed: " + ",".join(report.reasons))


def validate_synchronized_events(es: Sequence[MarketEvent], nq: Sequence[MarketEvent], *, max_skew: timedelta) -> DataQualityReport:
    if not es or not nq:
        report = DataQualityReport("UNSAFE", reasons=(QualityReason.EMPTY_DATASET.value,),
                                   reason_counts={QualityReason.EMPTY_DATASET.value: 1}, trading_authority=False)
        raise DataQualityError(report)
    skew = abs(es[-1].exchange_time - nq[-1].exchange_time)
    if skew > max_skew:
        report = DataQualityReport("UNSAFE", checked_events=len(es)+len(nq), accepted_events=0,
            reasons=(QualityReason.CROSS_MARKET_SKEW.value,),
            reason_counts={QualityReason.CROSS_MARKET_SKEW.value: 1}, trading_authority=False)
        raise DataQualityError(report)
    return DataQualityReport("HEALTHY", checked_events=len(es)+len(nq), accepted_events=len(es)+len(nq),
        reasons=(), reason_counts={}, first_exchange_time=min(es[0].exchange_time,nq[0].exchange_time).isoformat(),
        last_exchange_time=max(es[-1].exchange_time,nq[-1].exchange_time).isoformat(), trading_authority=False)
