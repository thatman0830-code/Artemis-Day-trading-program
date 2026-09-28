"""Verified replay feed interface independent of any charting platform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from backtesting.databento_research_dataset_v1 import read_databento_research_days
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import CanonicalTimeframe, HistoricalCandle

VERSION = "provider-neutral-market-feed-v1"


@dataclass(frozen=True, slots=True)
class ProviderNeutralReplayFeedV1:
    market: FuturesCanonicalMarket
    days: tuple[str, ...]
    bars: tuple[HistoricalCandle, ...]
    dataset_id: str
    fingerprint: str
    source_sha256: str
    live: bool = False
    trading_authority: bool = False

    def __post_init__(self):
        if not self.days or tuple(sorted(set(self.days))) != self.days:
            raise ValueError("ordered distinct replay days required")
        if not self.bars or any(x.timeframe is not CanonicalTimeframe.M1 for x in self.bars):
            raise ValueError("closed one-minute bars required")
        if self.live or self.trading_authority:
            raise ValueError("replay feed cannot carry live or trading authority")


def read_provider_neutral_replay(root, *, market: FuturesCanonicalMarket,
                                 days: tuple[str, ...], as_of: datetime) -> ProviderNeutralReplayFeedV1:
    evidence = read_databento_research_days(root, market=market, days=days, as_of=as_of)
    bars = tuple(x for x in evidence.dataset.candles if x.timeframe is CanonicalTimeframe.M1)
    return ProviderNeutralReplayFeedV1(market, days, bars, evidence.dataset.dataset_id,
        evidence.dataset.fingerprint, evidence.chain_head_sha256)
