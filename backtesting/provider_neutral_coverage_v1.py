"""Coverage audit for the owned ES/NQ paper-trial window."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

VERSION = "provider-neutral-coverage-v1"


@dataclass(frozen=True, slots=True)
class CoverageRowV1:
    session_date: str
    feed_bars_es: int
    feed_bars_nq: int
    signals_es: int
    signals_nq: int
    completed_trades: int
    completed_signal_trades: int
    status: str


def audit_coverage(*, configured_days: tuple[str, ...], feed_bars: dict[str, dict[str, int]],
                   signal_counts: dict[str, dict[str, int]], completed_by_day: dict[str, int],
                   completed_by_signal_day: dict[str, int] | None = None) -> tuple[CoverageRowV1, ...]:
    if not configured_days or tuple(sorted(set(configured_days))) != configured_days:
        raise ValueError("configured days must be ordered and distinct")
    rows = []
    completed_by_signal_day = completed_by_signal_day or {}
    for day in configured_days:
        es_bars = int(feed_bars.get(day, {}).get("ES", 0))
        nq_bars = int(feed_bars.get(day, {}).get("NQ", 0))
        es_signals = int(signal_counts.get(day, {}).get("ES", 0))
        nq_signals = int(signal_counts.get(day, {}).get("NQ", 0))
        completed = int(completed_by_day.get(day, 0))
        completed_signal = int(completed_by_signal_day.get(day, 0))
        if es_bars == 0 or nq_bars == 0:
            status = "MISSING_FEED"
        elif es_signals + nq_signals == 0:
            status = "NO_SIGNALS"
        elif completed_signal > 0 and completed == 0:
            status = "COVERED_NEXT_ENTRY_SESSION"
        elif completed == 0:
            status = "NO_COMPLETED_TRADES"
        else:
            status = "COVERED"
        rows.append(CoverageRowV1(day, es_bars, nq_bars, es_signals, nq_signals, completed, completed_signal, status))
    return tuple(rows)


def coverage_document(*, evaluated_at: str, configured_days: tuple[str, ...],
                      rows: tuple[CoverageRowV1, ...], trading_authority: bool = False) -> dict:
    if trading_authority:
        raise ValueError("coverage audit cannot carry trading authority")
    return {
        "schema_version": VERSION,
        "evaluated_at": evaluated_at,
        "configured_days": list(configured_days),
        "rows": [asdict(row) for row in rows],
        # A complete, validated session with no strategy signals is still a
        # valid observation under the explicit no-signal-day policy.  Keep the
        # row status as NO_SIGNALS so downstream scorecards cannot mistake it
        # for a traded day, but do not report it as a coverage gap.
        "covered_days": sum(row.status in {"COVERED", "COVERED_NEXT_ENTRY_SESSION", "NO_SIGNALS"} for row in rows),
        "missing_or_unqualified_days": [row.session_date for row in rows
                                        if row.status not in {"COVERED", "COVERED_NEXT_ENTRY_SESSION", "NO_SIGNALS"}],
        "comparison_only": True,
        "trading_authority": False,
    }
