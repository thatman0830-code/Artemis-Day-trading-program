from __future__ import annotations

from datetime import datetime, timezone
import subprocess
from typing import Sequence
from bot2.data_foundation.contracts import MarketEvent

UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def commit_id() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "UNKNOWN"


def ordered(events: Sequence[MarketEvent]) -> list[MarketEvent]:
    result = list(events)
    for left, right in zip(result, result[1:]):
        if right.exchange_time <= left.exchange_time:
            raise ValueError("feature/label input must be strictly exchange-time ordered")
        if right.receive_timestamp_available and right.receipt_time is not None and right.receipt_time < right.exchange_time:
            raise ValueError("receipt time cannot precede exchange time")
        if right.price <= 0 or right.volume < 0:
            raise ValueError("invalid source price or volume")
    return result


def session(event: MarketEvent) -> str:
    return event.session_id or event.exchange_time.date().isoformat()


def log_return(a: float, b: float) -> float:
    import math
    return math.log(a / b)
