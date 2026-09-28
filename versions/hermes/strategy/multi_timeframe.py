from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from exchange.market_data import MarketDataEngine

from strategy.market_structure import (
    MarketStructureEngine,
)

from strategy.models import (
    MarketStructure,
    MarketTrend,
)


class ConsensusTrend(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TimeframeStructure:
    timeframe: str
    structure: MarketStructure
    weight: float


@dataclass(frozen=True)
class MultiTimeframeResult:
    symbol: str

    structures: list[
        TimeframeStructure
    ]

    bullish_score: float
    bearish_score: float
    range_score: float

    consensus: ConsensusTrend


class MultiTimeframeStructureEngine:
    """
    Multi-timeframe structure aggregator.

    Responsibilities:
    - Load closed Hyperliquid candles
    - Analyze structure on each timeframe
    - Apply timeframe weights
    - Produce a directional consensus

    This module does NOT place trades.
    """

    DEFAULT_WEIGHTS = {
        "1m": 1.0,
        "5m": 1.5,
        "15m": 2.0,
        "1h": 3.0,
        "4h": 4.0,
    }

    def __init__(
        self,
        testnet: bool = True,
        swing_window: int = 2,
        minimum_swings: int = 2,
        timeframe_weights: dict[str, float] | None = None,
    ):
        self.market_data = MarketDataEngine(
            testnet=testnet
        )

        self.structure_engine = (
            MarketStructureEngine(
                swing_window=swing_window,
                minimum_swings=minimum_swings,
            )
        )

        self.timeframe_weights = (
            timeframe_weights
            if timeframe_weights is not None
            else self.DEFAULT_WEIGHTS
        )

    # ==========================================================
    # ANALYZE
    # ==========================================================

    def analyze(
        self,
        symbol: str,
    ) -> MultiTimeframeResult:

        market = (
            self.market_data
            .get_multi_timeframe(
                symbol=symbol
            )
        )

        structures: list[
            TimeframeStructure
        ] = []

        bullish_score = 0.0
        bearish_score = 0.0
        range_score = 0.0

        for timeframe, candles in market.items():

            if candles.empty:
                continue

            structure = (
                self.structure_engine
                .analyze(
                    symbol=symbol,
                    timeframe=timeframe,
                    candles=candles,
                )
            )

            weight = float(
                self.timeframe_weights.get(
                    timeframe,
                    1.0,
                )
            )

            structures.append(
                TimeframeStructure(
                    timeframe=timeframe,
                    structure=structure,
                    weight=weight,
                )
            )

            if (
                structure.trend
                == MarketTrend.BULLISH
            ):
                bullish_score += weight

            elif (
                structure.trend
                == MarketTrend.BEARISH
            ):
                bearish_score += weight

            elif (
                structure.trend
                == MarketTrend.RANGE
            ):
                range_score += weight

        consensus = (
            self._determine_consensus(
                bullish_score=(
                    bullish_score
                ),
                bearish_score=(
                    bearish_score
                ),
                range_score=(
                    range_score
                ),
            )
        )

        return MultiTimeframeResult(
            symbol=symbol.upper(),
            structures=structures,

            bullish_score=(
                bullish_score
            ),

            bearish_score=(
                bearish_score
            ),

            range_score=(
                range_score
            ),

            consensus=consensus,
        )

    # ==========================================================
    # CONSENSUS
    # ==========================================================

    @staticmethod
    def _determine_consensus(
        *,
        bullish_score: float,
        bearish_score: float,
        range_score: float,
    ) -> ConsensusTrend:

        total_directional = (
            bullish_score
            + bearish_score
        )

        if (
            total_directional == 0
            and range_score == 0
        ):
            return (
                ConsensusTrend.UNKNOWN
            )

        if (
            bullish_score
            > bearish_score
            and bullish_score
            > range_score
        ):
            return (
                ConsensusTrend.BULLISH
            )

        if (
            bearish_score
            > bullish_score
            and bearish_score
            > range_score
        ):
            return (
                ConsensusTrend.BEARISH
            )

        return ConsensusTrend.MIXED


# ==============================================================
# SELF TEST — REAL HYPERLIQUID DATA
# ==============================================================


if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " BTC MULTI-TIMEFRAME STRUCTURE"
    )
    print(
        "======================================"
    )
    print(
        "Network: TESTNET"
    )
    print(
        "Data: CLOSED CANDLES ONLY"
    )
    print(
        "--------------------------------------"
    )

    engine = (
        MultiTimeframeStructureEngine(
            testnet=True,
            swing_window=2,
            minimum_swings=2,
        )
    )

    result = engine.analyze(
        symbol="BTC"
    )

    if not result.structures:

        raise RuntimeError(
            "No timeframe structures "
            "were produced."
        )

    for item in result.structures:

        structure = (
            item.structure
        )

        print(
            item.timeframe.ljust(4),
            "| Trend:",
            structure.trend.value.ljust(8),
            "| Weight:",
            str(item.weight).ljust(4),
            "| Price:",
            str(
                round(
                    structure.current_price,
                    4,
                )
            ).ljust(12),
            "| Swing H:",
            str(
                structure.swing_high
            ).ljust(12),
            "| Swing L:",
            str(
                structure.swing_low
            ),
        )

    print(
        "--------------------------------------"
    )

    print(
        "Bullish Score:",
        result.bullish_score
    )

    print(
        "Bearish Score:",
        result.bearish_score
    )

    print(
        "Range Score:",
        result.range_score
    )

    print(
        "Consensus:",
        result.consensus.value
    )

    print(
        "--------------------------------------"
    )
    print(
        "MULTI-TIMEFRAME STRUCTURE TEST PASSED"
    )
    print(
        "======================================"
    )
    print()