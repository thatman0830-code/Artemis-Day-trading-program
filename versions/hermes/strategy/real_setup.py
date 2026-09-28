from __future__ import annotations

from dataclasses import dataclass

from exchange.market_data import MarketDataEngine
from strategy.aoi import AOIStatus
from strategy.aoi_discovery import AOIDiscoveryEngine
from strategy.liquidity import LiquiditySweep, LiquiditySweepEngine
from strategy.market_structure import MarketStructureEngine
from strategy.models import MarketTrend, StrategySignal
from strategy.multi_timeframe import MultiTimeframeStructureEngine
from strategy.setup_engine import SetupEngine


@dataclass(frozen=True)
class RealSetupEvaluation:
    signal: StrategySignal
    candle_count: int
    discovered_aoi_count: int


class RealSetupEvaluator:
    """Read-only composition root for the current strategy scaffold."""

    def __init__(self, *, testnet: bool = True, minimum_risk_reward: float = 2.0):
        self.testnet = bool(testnet)
        self.minimum_risk_reward = float(minimum_risk_reward)
        self.market_data = None
        self.multi_timeframe_engine = None
        self.structure_engine = MarketStructureEngine(swing_window=2, minimum_swings=2)
        self.aoi_discovery = AOIDiscoveryEngine(
            minimum_touches=3,
            cluster_tolerance_pct=0.25,
            zone_padding_pct=0.05,
            maximum_zone_width_pct=1.0,
            swing_window=2,
        )
        self.liquidity_engine = LiquiditySweepEngine(minimum_penetration_pct=0.0)
        self.setup_engine = SetupEngine(minimum_risk_reward=minimum_risk_reward)

    def _initialize_market_clients(self) -> None:
        if self.market_data is None:
            self.market_data = MarketDataEngine(testnet=self.testnet)
        if self.multi_timeframe_engine is None:
            self.multi_timeframe_engine = MultiTimeframeStructureEngine(
                testnet=self.testnet, swing_window=2, minimum_swings=2
            )

    def evaluate(
        self, *, symbol: str = "BTC", timeframe: str = "15m", candle_limit: int = 300
    ) -> RealSetupEvaluation:
        if candle_limit < 10:
            raise ValueError("candle_limit must be at least 10.")

        timeframe_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}
        if timeframe not in timeframe_minutes:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        self._initialize_market_clients()

        candles = self.market_data.get_closed_candles(
            symbol=symbol,
            interval=timeframe,
            lookback_minutes=timeframe_minutes[timeframe] * candle_limit,
        )
        if candles.empty:
            raise RuntimeError("No closed candles returned.")

        structure = self.structure_engine.analyze(
            symbol=symbol, timeframe=timeframe, candles=candles
        )
        multi_timeframe = self.multi_timeframe_engine.analyze(symbol=symbol)
        discovered = self.aoi_discovery.discover(
            candles=candles, structure=structure, timeframe=timeframe
        )

        # Discovery results are already ranked VALID, WAITING, INVALID.
        aoi_candidate = discovered[0].candidate if discovered else None
        sweep: LiquiditySweep | None = None

        if structure.trend == MarketTrend.BULLISH and structure.swing_low is not None:
            sweep = self.liquidity_engine.detect_sell_side(
                candles=candles, reference_low=structure.swing_low
            )
        elif structure.trend == MarketTrend.BEARISH and structure.swing_high is not None:
            sweep = self.liquidity_engine.detect_buy_side(
                candles=candles, reference_high=structure.swing_high
            )

        signal = self.setup_engine.evaluate(
            structure=structure,
            multi_timeframe=multi_timeframe,
            aoi_candidate=aoi_candidate,
            sweep=sweep,
        )
        signal.metadata.update(
            data_mode="CLOSED_CANDLES_ONLY",
            network="TESTNET" if self.testnet else "MAINNET_READ_ONLY",
            aoi_status=(aoi_candidate.status.value if aoi_candidate else None),
            valid_aoi_available=(
                aoi_candidate is not None and aoi_candidate.status == AOIStatus.VALID
            ),
        )
        return RealSetupEvaluation(
            signal=signal,
            candle_count=len(candles),
            discovered_aoi_count=len(discovered),
        )


if __name__ == "__main__":
    result = RealSetupEvaluator(testnet=True).evaluate(symbol="BTC", timeframe="15m")
    signal = result.signal

    print()
    print("======================================")
    print(" REAL SETUP ENGINE EVALUATION")
    print("======================================")
    print("Network: TESTNET")
    print("Execution: DISABLED")
    print("Private Key: NOT USED")
    print("Data: CLOSED CANDLES ONLY")
    print("--------------------------------------")
    print("Symbol:", signal.symbol)
    print("Timeframe:", signal.timeframe)
    print("Candles:", result.candle_count)
    print("Trend:", signal.market_trend.value)
    print("AOIs Discovered:", result.discovered_aoi_count)
    print("Outcome:", signal.metadata["outcome"])
    print("Status:", signal.status.value)
    print("Direction:", signal.direction.value)
    print("Entry:", signal.entry_price)
    print("Stop:", signal.stop_price)
    print("Target:", signal.target_price)
    print("Risk Reward:", signal.risk_reward)
    print("Reason:", signal.reason)
    print("--------------------------------------")
    print("STRATEGY PROPOSAL ONLY — NO ORDER SENT")
    print("======================================")
    print()
