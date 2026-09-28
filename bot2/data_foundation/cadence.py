"""Elapsed-time cadence audits; never infer continuity from adjacent rows."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping

from .contracts import MarketEvent

EXPECTED_BAR_INTERVAL = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class CadenceGap:
    instrument: str
    contract_id: str
    session_id: str
    previous_timestamp: str
    next_timestamp: str
    expected_interval_seconds: int
    actual_elapsed_seconds: float
    missing_interval_count: int
    cadence_valid: bool
    reason_code: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CadenceAudit:
    expected_interval_seconds: int
    observation_count: int
    checked_adjacent_pairs: int
    cadence_valid_pairs: int
    cadence_invalid_pairs: int
    gap_count: int
    missing_interval_count: int
    gap_size_distribution: Mapping[str, int]
    reason_counts: Mapping[str, int]
    sessions_affected: int
    gaps: tuple[CadenceGap, ...]
    excluded_calendar_boundary_pairs: int = 0

    def to_dict(self):
        return asdict(self) | {"gaps": [gap.to_dict() for gap in self.gaps]}


def audit_cadence(events: Iterable[MarketEvent], *, expected_interval: timedelta = EXPECTED_BAR_INTERVAL,
                  active_intervals: Mapping[str, Iterable[tuple[datetime, datetime]]] | None = None) -> CadenceAudit:
    if expected_interval.total_seconds() <= 0:
        raise ValueError("expected cadence must be positive")
    groups: dict[tuple[str, str, str, int | None], list[MarketEvent]] = defaultdict(list)
    interval_index: dict[tuple[str, str, str], int] = {}
    for event in events:
        if not event.session_id:
            raise ValueError("cadence audit requires explicit session_id")
        boundary_id = None
        if active_intervals is not None:
            intervals = tuple(active_intervals.get(event.session_id, ()))
            # Input timestamps are bar-close times. Active intervals describe
            # [bar-open, bar-close) windows; include a close exactly at end.
            matches = [i for i, (start, end) in enumerate(intervals)
                       if start < event.exchange_time <= end]
            if len(matches) != 1:
                raise ValueError("bar close must map to exactly one archived active interval")
            boundary_id = matches[0]
        group_key = (event.instrument, event.contract_id or event.instrument, event.session_id, boundary_id)
        groups[group_key].append(event)
        interval_index[(event.instrument, event.contract_id or event.instrument,
                        event.session_id, event.exchange_time.isoformat())] = boundary_id
    gaps: list[CadenceGap] = []
    reasons: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    pairs = valid = missing_total = 0
    affected: set[str] = set()
    excluded_boundaries = 0
    expected_seconds = int(expected_interval.total_seconds())
    for (instrument, contract, session_id, _boundary_id), rows in sorted(groups.items()):
        rows.sort(key=lambda row: row.exchange_time)
        for left, right in zip(rows, rows[1:]):
            actual = (right.exchange_time - left.exchange_time).total_seconds()
            if actual <= 0:
                raise ValueError("duplicate or regressing timestamp must be rejected before cadence audit")
            pairs += 1
            if actual == expected_seconds:
                valid += 1
                continue
            missing = max(0, int((actual + expected_seconds - 1) // expected_seconds) - 1)
            code = "MISSING_INTERVALS" if actual > expected_seconds and actual % expected_seconds == 0 else "CADENCE_VIOLATION"
            gaps.append(CadenceGap(instrument, contract, session_id,
                left.exchange_time.isoformat().replace("+00:00", "Z"),
                right.exchange_time.isoformat().replace("+00:00", "Z"), expected_seconds,
                actual, missing, False, code))
            reasons[code] += 1
            if missing:
                sizes[str(missing)] += 1
                missing_total += missing
            affected.add(session_id)
    if active_intervals is not None:
        # Count consecutive observations that straddle a calendar-declared
        # inactive interval, but do not call the closed time a data gap.
        session_groups: dict[tuple[str, str, str], list[MarketEvent]] = defaultdict(list)
        for (instrument, contract, session_id, _), rows in groups.items():
            session_groups[(instrument, contract, session_id)].extend(rows)
        for (instrument, contract, session_id), rows in session_groups.items():
            rows.sort(key=lambda row: row.exchange_time)
            for left, right in zip(rows, rows[1:]):
                left_id = interval_index[(instrument, contract, session_id, left.exchange_time.isoformat())]
                right_id = interval_index[(instrument, contract, session_id, right.exchange_time.isoformat())]
                if left_id != right_id:
                    excluded_boundaries += 1

    return CadenceAudit(expected_seconds, sum(len(rows) for rows in groups.values()), pairs,
        valid, len(gaps), len(gaps), missing_total, dict(sorted(sizes.items())),
        dict(sorted(reasons.items())), len(affected), tuple(gaps), excluded_boundaries)


def is_contiguous_window(timestamps: Iterable[datetime], *, expected_interval: timedelta = EXPECTED_BAR_INTERVAL) -> bool:
    values = tuple(timestamps)
    return all((right - left) == expected_interval for left, right in zip(values, values[1:]))
