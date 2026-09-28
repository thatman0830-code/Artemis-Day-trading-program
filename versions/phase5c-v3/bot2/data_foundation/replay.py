"""Deterministic, cutoff-bounded replay."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib, json
from typing import Callable, Iterable
from .contracts import MarketEvent


def deterministic_replay(events: Iterable[MarketEvent], *, cutoff: datetime,
                         on_event: Callable[[MarketEvent], object] | None = None) -> dict:
    """Replay only events at or before cutoff, preserving source order.

    Future events are excluded rather than hidden by sorting or forward filling.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() != timezone.utc.utcoffset(cutoff):
        raise ValueError("cutoff must be UTC")
    source = tuple(events)
    rows = tuple(event for event in source if event.exchange_time <= cutoff)
    outputs = tuple(on_event(event) for event in rows) if on_event else tuple(event.to_dict() for event in rows)
    digest = hashlib.sha256(json.dumps(outputs, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": "bot2-deterministic-replay-v1", "cutoff": cutoff.isoformat(),
            "event_count": len(rows), "output_sha256": digest, "outputs": outputs,
            "future_events_excluded": sum(1 for event in source if event.exchange_time > cutoff),
            "trading_authority": False}
