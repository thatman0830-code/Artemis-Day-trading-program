from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ==============================================================
# ENUMS
# ==============================================================


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


class MarketTrend(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"


class SetupStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WAITING = "WAITING"


class SetupType(str, Enum):
    TREND_CONTINUATION = "TREND_CONTINUATION"
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    REVERSAL = "REVERSAL"
    RANGE = "RANGE"
    NONE = "NONE"


# ==============================================================
# MARKET STRUCTURE
# ==============================================================


@dataclass
class MarketStructure:

    symbol: str

    timeframe: str

    trend: MarketTrend

    current_price: float

    swing_high: Optional[float] = None

    swing_low: Optional[float] = None

    higher_high: Optional[float] = None

    higher_low: Optional[float] = None

    lower_high: Optional[float] = None

    lower_low: Optional[float] = None


# ==============================================================
# AREA OF INTEREST
# ==============================================================


@dataclass
class AreaOfInterest:

    lower_bound: float

    upper_bound: float

    touches: int

    timeframe: str

    label: str = "AOI"

    def contains(
        self,
        price: float,
    ) -> bool:

        return (
            self.lower_bound
            <= price
            <= self.upper_bound
        )


# ==============================================================
# STRATEGY SIGNAL
# ==============================================================


@dataclass
class StrategySignal:

    symbol: str

    direction: TradeDirection

    setup_type: SetupType

    status: SetupStatus

    timeframe: str

    entry_price: Optional[float]

    stop_price: Optional[float]

    target_price: Optional[float]

    risk_reward: Optional[float]

    confidence: float

    reason: str

    market_trend: MarketTrend

    aoi: Optional[AreaOfInterest] = None

    metadata: dict = field(
        default_factory=dict
    )


# ==============================================================
# HELPERS
# ==============================================================


def calculate_risk_reward(
    *,
    direction: TradeDirection,
    entry_price: float,
    stop_price: float,
    target_price: float,
) -> float:

    if direction == TradeDirection.LONG:

        risk = (
            entry_price
            - stop_price
        )

        reward = (
            target_price
            - entry_price
        )

    elif direction == TradeDirection.SHORT:

        risk = (
            stop_price
            - entry_price
        )

        reward = (
            entry_price
            - target_price
        )

    else:

        return 0.0

    if risk <= 0:
        return 0.0

    if reward <= 0:
        return 0.0

    return reward / risk


# ==============================================================
# SELF TEST
# ==============================================================


if __name__ == "__main__":

    print()
    print("======================================")
    print(" STRATEGY DATA MODEL TEST")
    print("======================================")

    structure = MarketStructure(
        symbol="BTC",
        timeframe="15m",
        trend=MarketTrend.BULLISH,
        current_price=80_000,
        swing_high=80_500,
        swing_low=79_500,
        higher_high=80_500,
        higher_low=79_500,
    )

    aoi = AreaOfInterest(
        lower_bound=79_700,
        upper_bound=80_000,
        touches=3,
        timeframe="15m",
        label="Bullish Pullback AOI",
    )

    rr = calculate_risk_reward(
        direction=TradeDirection.LONG,
        entry_price=80_000,
        stop_price=79_600,
        target_price=80_800,
    )

    signal = StrategySignal(
        symbol="BTC",
        direction=TradeDirection.LONG,
        setup_type=SetupType.PULLBACK,
        status=SetupStatus.VALID,
        timeframe="15m",
        entry_price=80_000,
        stop_price=79_600,
        target_price=80_800,
        risk_reward=rr,
        confidence=0.80,
        reason=(
            "Bullish structure with price "
            "inside validated AOI."
        ),
        market_trend=structure.trend,
        aoi=aoi,
    )

    assert structure.trend == MarketTrend.BULLISH

    assert aoi.contains(
        79_900
    )

    assert aoi.touches >= 3

    assert rr == 2.0

    assert (
        signal.direction
        == TradeDirection.LONG
    )

    assert signal.status == SetupStatus.VALID

    print("Symbol:", signal.symbol)
    print("Timeframe:", signal.timeframe)
    print("Trend:", signal.market_trend.value)
    print("Direction:", signal.direction.value)
    print("Setup:", signal.setup_type.value)
    print("Status:", signal.status.value)

    print(
        "AOI:",
        aoi.lower_bound,
        "-",
        aoi.upper_bound,
    )

    print("AOI Touches:", aoi.touches)

    print(
        "Entry:",
        signal.entry_price,
    )

    print(
        "Stop:",
        signal.stop_price,
    )

    print(
        "Target:",
        signal.target_price,
    )

    print(
        "Risk Reward:",
        signal.risk_reward,
    )

    print(
        "Confidence:",
        signal.confidence,
    )

    print("--------------------------------------")
    print("STRATEGY DATA MODEL TEST PASSED")
    print("======================================")
    print()