from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

import pandas as pd

from backtesting.market_data import CanonicalTimeframe, HistoricalCandle, HistoricalDataset
from strategy.trading_brain import INTERFACE_CONTRACT_VERSION, PUBLIC_ENGINE_ENTRY_POINTS
from strategy.trading_brain.p11_cisd_confirmation import DeliveryCandle
from strategy.trading_brain.p29_1_entry_execution import EntryCandle
from strategy.trading_brain.p29_4_exit_resolution import ExitMarketData, PriceObservation


def _epoch_milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=value.tzinfo)
    delta = value - epoch
    return (delta.days * 86_400 + delta.seconds) * 1_000 + delta.microseconds // 1_000


class TradingBrainMarketDataAdapter:
    """One-way adapter to frozen Trading Brain candle inputs; never invokes logic."""

    contract_version = INTERFACE_CONTRACT_VERSION

    def __init__(self, dataset: HistoricalDataset):
        if not isinstance(dataset, HistoricalDataset):
            raise TypeError("dataset must be a validated HistoricalDataset.")
        if dataset.validation_status.value not in {"VALID", "VALID_WITH_GAPS"}:
            raise ValueError("A validated historical dataset is required.")
        if "#19" not in PUBLIC_ENGINE_ENTRY_POINTS or "#25" not in PUBLIC_ENGINE_ENTRY_POINTS:
            raise RuntimeError("Required frozen Trading Brain candle interfaces are unavailable.")
        self._dataset = dataset

    def _eligible(self, *, symbol: str, timeframe: CanonicalTimeframe,
                  as_of: datetime) -> tuple[HistoricalCandle, ...]:
        if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
            raise ValueError("as_of must be UTC timezone-aware.")
        return tuple(c for c in self._dataset.candles
                     if c.symbol == symbol and c.timeframe is timeframe and c.close_time <= as_of)

    @staticmethod
    def _row(candle: HistoricalCandle) -> dict[str, object]:
        return {
            "id": candle.id, "t": _epoch_milliseconds(candle.open_time),
            "T": _epoch_milliseconds(candle.close_time), "s": candle.symbol,
            "i": candle.timeframe.value, "o": candle.open, "h": candle.high,
            "l": candle.low, "c": candle.close, "v": candle.volume,
            "is_closed": True,
        }

    def to_mechanical_swing_frame(self, *, symbol: str, timeframe: CanonicalTimeframe,
                                  as_of: datetime) -> pd.DataFrame:
        """Canonical #19 path: DataFrame with object-backed Decimal columns."""
        rows = [self._row(candle) for candle in self._eligible(symbol=symbol, timeframe=timeframe, as_of=as_of)]
        return pd.DataFrame(rows, columns=("id", "t", "T", "s", "i", "o", "h", "l", "c", "v", "is_closed"), dtype=object)

    def to_candle_mappings(self, *, symbol: str, timeframe: CanonicalTimeframe,
                           as_of: datetime) -> tuple[Mapping[str, object], ...]:
        """Canonical #20/#25 path: immutable mappings with the same values/IDs."""
        return tuple(MappingProxyType(self._row(candle))
                     for candle in self._eligible(symbol=symbol, timeframe=timeframe, as_of=as_of))

    def to_delivery_candles(self, *, symbol: str, as_of: datetime) -> tuple[DeliveryCandle, ...]:
        """Canonical #11 path from the same validated, published 1M history."""
        return tuple(
            DeliveryCandle(
                id=candle.id, timeframe=candle.timeframe.value,
                open=candle.open, high=candle.high, low=candle.low,
                close=candle.close, close_time=_epoch_milliseconds(candle.close_time),
                is_closed=True,
            )
            for candle in self._eligible(
                symbol=symbol, timeframe=CanonicalTimeframe.M1, as_of=as_of,
            )
        )

    @staticmethod
    def to_entry_candle(candle: HistoricalCandle) -> EntryCandle:
        """Exact one-candle #29.1 input; no fill or strategy logic lives here."""
        if not isinstance(candle, HistoricalCandle) or not candle.is_closed:
            raise ValueError("A validated closed historical candle is required.")
        return EntryCandle(
            candle.id, candle.symbol, candle.timeframe.value,
            _epoch_milliseconds(candle.open_time), _epoch_milliseconds(candle.close_time),
            candle.open, candle.high, candle.low, candle.close,
        )

    @staticmethod
    def to_exit_market_data(
        candle: HistoricalCandle, *, input_version: str | None = None,
        observations: tuple[PriceObservation, ...] = (),
    ) -> ExitMarketData:
        """Exact #29.4 market input; optional observations must prove their own order."""
        if not isinstance(candle, HistoricalCandle) or not candle.is_closed:
            raise ValueError("A validated closed historical candle is required.")
        if not isinstance(observations, tuple) or any(not isinstance(x, PriceObservation) for x in observations):
            raise TypeError("observations must be an immutable tuple of PriceObservation facts.")
        return ExitMarketData(
            candle.id, candle.symbol, candle.timeframe.value,
            _epoch_milliseconds(candle.open_time), _epoch_milliseconds(candle.close_time),
            candle.open, candle.high, candle.low, candle.close,
            input_version or candle.schema_version, observations,
        )
