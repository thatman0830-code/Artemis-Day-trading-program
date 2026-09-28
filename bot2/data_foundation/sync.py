"""Deterministic ES/NQ synchronization without forward filling."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Sequence
from .contracts import MarketEvent
from .instruments import normalize_contract


@dataclass(frozen=True, slots=True)
class RootSynchronizationReport:
    schema_version: str
    es_observations: int
    nq_observations: int
    exact_matches: int
    es_unmatched: int
    nq_unmatched: int
    es_match_rate: float
    nq_match_rate: float
    contract_expiry_mismatch_pairs: int
    session_mismatch_events: int
    no_forward_fill: bool = True


def synchronize_contract_roots(es: Sequence[MarketEvent], nq: Sequence[MarketEvent]):
    """Pair only exact session/timestamp matches, retaining contract IDs.

    This routine intentionally has no tolerance, nearest-neighbor, or
    forward-fill behavior. Contracts can differ in expiry while still pairing
    at the same event timestamp; their exact identities remain in each event.
    """
    def keyed(events: Sequence[MarketEvent], expected_root: str):
        result = {}
        identities = {}
        for event in events:
            identity = normalize_contract(event.instrument, event.contract_id or event.instrument,
                                          reference_date=event.exchange_time.date())
            if identity.root_symbol != expected_root:
                raise ValueError(f"expected {expected_root} root, got {identity.root_symbol}")
            key = (event.session_id or event.exchange_time.date().isoformat(), event.exchange_time)
            if key in result:
                raise ValueError("duplicate root/session/event-time observation")
            result[key] = event
            identities[key] = identity
        return result, identities

    es_rows, es_ids = keyed(es, "ES")
    nq_rows, nq_ids = keyed(nq, "NQ")
    common = sorted(es_rows.keys() & nq_rows.keys())
    pairs = tuple((es_rows[key], nq_rows[key]) for key in common)
    exact = len(pairs)
    es_by_time = {event.exchange_time: event.session_id for event in es}
    nq_by_time = {event.exchange_time: event.session_id for event in nq}
    session_mismatch = sum(es_by_time[stamp] != nq_by_time[stamp]
                           for stamp in es_by_time.keys() & nq_by_time.keys())
    report = RootSynchronizationReport(
        "bot2-root-synchronization-v1", len(es), len(nq), exact,
        len(es) - exact, len(nq) - exact,
        exact / len(es) if es else 0.0, exact / len(nq) if nq else 0.0,
        sum(es_ids[key].expiry != nq_ids[key].expiry for key in common),
        session_mismatch, True)
    return pairs, report
from .validation import DataQualityError, QualityReason


def synchronize_es_nq(es: Sequence[MarketEvent], nq: Sequence[MarketEvent], *, max_skew: timedelta) -> tuple[tuple[MarketEvent, MarketEvent], ...]:
    """Pair each event with the nearest opposite-market event within max_skew.

    No synthetic event or future event is generated.  A missing pair fails closed.
    """
    pairs = []
    used: set[int] = set()
    for left in es:
        candidates = [(abs(left.exchange_time-right.exchange_time), i, right)
                      for i, right in enumerate(nq) if i not in used and abs(left.exchange_time-right.exchange_time) <= max_skew]
        if not candidates:
            report = {QualityReason.CROSS_MARKET_SKEW.value: 1}
            raise DataQualityError(__import__('bot2.data_foundation.contracts', fromlist=['DataQualityReport']).DataQualityReport(
                "UNSAFE", checked_events=len(es)+len(nq), reasons=(QualityReason.CROSS_MARKET_SKEW.value,),
                reason_counts=report, trading_authority=False))
        _, index, right = min(candidates, key=lambda x: (x[0], x[1]))
        used.add(index); pairs.append((left, right))
    return tuple(pairs)
