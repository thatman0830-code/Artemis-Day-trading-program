"""Fail-closed gate for the first synchronized, gap-free MES/MNQ UTC archive."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset

VERSION = "ninjatrader-clean-day-gate-v1"


@dataclass(frozen=True)
class NinjaTraderCleanDayGateV1:
    state: str
    day: str
    minimum_bars_per_market: int
    es_bar_count: int
    nq_bar_count: int
    latest_close_time_utc: datetime | None
    reasons: tuple[str, ...]
    canonical_evaluation_permitted: bool
    paper_execution_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def evaluate_ninjatrader_clean_day_gate(
    *, archive_root, as_of: datetime, minimum_bars_per_market: int = 30,
    maximum_staleness: timedelta = timedelta(minutes=2),
) -> NinjaTraderCleanDayGateV1:
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("UTC as_of required")
    if minimum_bars_per_market < 1 or maximum_staleness <= timedelta(0):
        raise ValueError("positive gate thresholds required")
    day = as_of.date().isoformat()
    datasets = {}
    reasons = []
    for market in FuturesCanonicalMarket:
        try:
            datasets[market] = read_closed_bar_dataset(
                archive_root, market=market, day=day, as_of=as_of
            )
        except (OSError, ValueError, TypeError) as exc:
            reasons.append(f"{market.value}_EVIDENCE_REJECTED:{type(exc).__name__}")
    if reasons:
        return NinjaTraderCleanDayGateV1(
            "REJECTED", day, minimum_bars_per_market,
            datasets.get(FuturesCanonicalMarket.ES).record_count if FuturesCanonicalMarket.ES in datasets else 0,
            datasets.get(FuturesCanonicalMarket.NQ).record_count if FuturesCanonicalMarket.NQ in datasets else 0,
            None, tuple(reasons), False,
        )
    es, nq = (datasets[FuturesCanonicalMarket.ES], datasets[FuturesCanonicalMarket.NQ])
    es_latest = es.dataset.candles[-1].close_time
    nq_latest = nq.dataset.candles[-1].close_time
    if es_latest != nq_latest:
        reasons.append("MARKETS_NOT_SYNCHRONIZED")
    latest = min(es_latest, nq_latest)
    if as_of - latest > maximum_staleness:
        reasons.append("LATEST_BAR_STALE")
    if es.record_count < minimum_bars_per_market or nq.record_count < minimum_bars_per_market:
        reasons.append("MINIMUM_CLEAN_WINDOW_NOT_MET")
    hard_rejection = any(reason != "MINIMUM_CLEAN_WINDOW_NOT_MET" for reason in reasons)
    state = "REJECTED" if hard_rejection else ("COLLECTING" if reasons else "READY")
    return NinjaTraderCleanDayGateV1(
        state, day, minimum_bars_per_market, es.record_count, nq.record_count,
        latest, tuple(reasons), state == "READY",
    )
