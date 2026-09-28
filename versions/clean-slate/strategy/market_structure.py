from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from strategy.models import (
    MarketStructure,
    MarketTrend,
)


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: str


class MarketStructureEngine:
    """
    Deterministic market-structure classifier.

    Input:
    - Closed OHLC candles only.

    Output:
    - Bullish, bearish, range, or unknown structure.
    - Most recent swing high / swing low.
    - Higher-high / higher-low or lower-high / lower-low labels.

    This engine does NOT place trades.
    """

    def __init__(
        self,
        swing_window: int = 2,
        minimum_swings: int = 2,
    ):
        if swing_window < 1:
            raise ValueError(
                "swing_window must be at least 1."
            )

        if minimum_swings < 2:
            raise ValueError(
                "minimum_swings must be at least 2."
            )

        self.swing_window = swing_window
        self.minimum_swings = minimum_swings

    # ==========================================================
    # VALIDATION
    # ==========================================================

    @staticmethod
    def _validate_candles(
        df: pd.DataFrame,
    ) -> None:

        required = {
            "h",
            "l",
            "c",
        }

        missing = required - set(
            df.columns
        )

        if missing:
            raise ValueError(
                f"Missing candle columns: {sorted(missing)}"
            )

        if df.empty:
            raise ValueError(
                "Candle DataFrame is empty."
            )

    # ==========================================================
    # SWING DETECTION
    # ==========================================================

    def _detect_swing_highs(
        self,
        df: pd.DataFrame,
    ) -> list[SwingPoint]:

        highs = df["h"].astype(float)

        swings: list[SwingPoint] = []

        w = self.swing_window

        for i in range(
            w,
            len(df) - w,
        ):
            current = highs.iloc[i]

            left = highs.iloc[
                i - w:i
            ]

            right = highs.iloc[
                i + 1:i + w + 1
            ]

            if (
                current > left.max()
                and current > right.max()
            ):
                swings.append(
                    SwingPoint(
                        index=i,
                        price=float(current),
                        kind="HIGH",
                    )
                )

        return swings

    def _detect_swing_lows(
        self,
        df: pd.DataFrame,
    ) -> list[SwingPoint]:

        lows = df["l"].astype(float)

        swings: list[SwingPoint] = []

        w = self.swing_window

        for i in range(
            w,
            len(df) - w,
        ):
            current = lows.iloc[i]

            left = lows.iloc[
                i - w:i
            ]

            right = lows.iloc[
                i + 1:i + w + 1
            ]

            if (
                current < left.min()
                and current < right.min()
            ):
                swings.append(
                    SwingPoint(
                        index=i,
                        price=float(current),
                        kind="LOW",
                    )
                )

        return swings

    # ==========================================================
    # CLASSIFICATION
    # ==========================================================

    def analyze(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: pd.DataFrame,
    ) -> MarketStructure:

        self._validate_candles(
            candles
        )

        swing_highs = (
            self._detect_swing_highs(
                candles
            )
        )

        swing_lows = (
            self._detect_swing_lows(
                candles
            )
        )

        current_price = float(
            candles.iloc[-1]["c"]
        )

        latest_high: Optional[
            SwingPoint
        ] = (
            swing_highs[-1]
            if swing_highs
            else None
        )

        latest_low: Optional[
            SwingPoint
        ] = (
            swing_lows[-1]
            if swing_lows
            else None
        )

        higher_high = None
        higher_low = None
        lower_high = None
        lower_low = None

        trend = MarketTrend.UNKNOWN

        # Need at least two highs and two lows
        # for meaningful HH/HL or LH/LL structure.

        if (
            len(swing_highs)
            >= self.minimum_swings
            and len(swing_lows)
            >= self.minimum_swings
        ):
            previous_high = (
                swing_highs[-2]
            )

            current_high = (
                swing_highs[-1]
            )

            previous_low = (
                swing_lows[-2]
            )

            current_low = (
                swing_lows[-1]
            )

            bullish_high = (
                current_high.price
                > previous_high.price
            )

            bullish_low = (
                current_low.price
                > previous_low.price
            )

            bearish_high = (
                current_high.price
                < previous_high.price
            )

            bearish_low = (
                current_low.price
                < previous_low.price
            )

            if (
                bullish_high
                and bullish_low
            ):
                trend = MarketTrend.BULLISH

                higher_high = (
                    current_high.price
                )

                higher_low = (
                    current_low.price
                )

            elif (
                bearish_high
                and bearish_low
            ):
                trend = MarketTrend.BEARISH

                lower_high = (
                    current_high.price
                )

                lower_low = (
                    current_low.price
                )

            else:
                trend = MarketTrend.RANGE

        return MarketStructure(
            symbol=symbol.upper(),
            timeframe=timeframe,
            trend=trend,
            current_price=current_price,

            swing_high=(
                latest_high.price
                if latest_high
                else None
            ),

            swing_low=(
                latest_low.price
                if latest_low
                else None
            ),

            higher_high=higher_high,
            higher_low=higher_low,

            lower_high=lower_high,
            lower_low=lower_low,
        )


# ==============================================================
# SELF TEST
# ==============================================================

if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " MARKET STRUCTURE ENGINE TEST"
    )
    print(
        "======================================"
    )

    # ----------------------------------------------------------
    # Synthetic bullish example
    # ----------------------------------------------------------

    bullish_data = pd.DataFrame(
        {
            "h": [
                100,
                102,
                101,
                104,
                103,
                106,
                105,
                108,
                107,
                109,
            ],
            "l": [
                98,
                99,
                97,
                100,
                99,
                102,
                101,
                104,
                103,
                105,
            ],
            "c": [
                99,
                101,
                100,
                103,
                102,
                105,
                104,
                107,
                106,
                108,
            ],
        }
    )

    engine = MarketStructureEngine(
        swing_window=1,
        minimum_swings=2,
    )

    structure = engine.analyze(
        symbol="BTC",
        timeframe="15m",
        candles=bullish_data,
    )

    print(
        "Symbol:",
        structure.symbol
    )

    print(
        "Timeframe:",
        structure.timeframe
    )

    print(
        "Trend:",
        structure.trend.value
    )

    print(
        "Current Price:",
        structure.current_price
    )

    print(
        "Swing High:",
        structure.swing_high
    )

    print(
        "Swing Low:",
        structure.swing_low
    )

    print(
        "Higher High:",
        structure.higher_high
    )

    print(
        "Higher Low:",
        structure.higher_low
    )

    assert (
        structure.trend
        == MarketTrend.BULLISH
    )

    assert (
        structure.higher_high
        is not None
    )

    assert (
        structure.higher_low
        is not None
    )

    print(
        "--------------------------------------"
    )
    print(
        "MARKET STRUCTURE ENGINE TEST PASSED"
    )
    print(
        "======================================"
    )
    print()