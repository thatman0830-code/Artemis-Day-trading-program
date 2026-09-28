from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class LiquiditySweepType(str, Enum):
    BUY_SIDE = "BUY_SIDE"
    SELL_SIDE = "SELL_SIDE"
    NONE = "NONE"


class LiquiditySweepStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    NOT_CONFIRMED = "NOT_CONFIRMED"


@dataclass(frozen=True)
class LiquiditySweep:
    sweep_type: LiquiditySweepType
    status: LiquiditySweepStatus

    reference_level: Optional[float]

    candle_high: float
    candle_low: float
    candle_close: float

    penetration: float
    penetration_pct: float

    reason: str


class LiquiditySweepEngine:
    """
    Deterministic liquidity sweep detector.

    A buy-side sweep occurs when price trades
    above a prior high and closes back below it.

    A sell-side sweep occurs when price trades
    below a prior low and closes back above it.

    This engine does NOT place trades.
    """

    def __init__(
        self,
        minimum_penetration_pct: float = 0.0,
    ):
        if minimum_penetration_pct < 0:
            raise ValueError(
                "minimum_penetration_pct cannot be negative."
            )

        self.minimum_penetration_pct = (
            minimum_penetration_pct
        )

    # ==========================================================
    # VALIDATION
    # ==========================================================

    @staticmethod
    def _validate_candles(
        candles: pd.DataFrame,
    ) -> None:

        required = {
            "h",
            "l",
            "c",
        }

        missing = (
            required
            - set(candles.columns)
        )

        if missing:
            raise ValueError(
                f"Missing candle columns: {sorted(missing)}"
            )

        if len(candles) < 2:
            raise ValueError(
                "At least two candles are required."
            )

    # ==========================================================
    # BUY-SIDE SWEEP
    # ==========================================================

    def detect_buy_side(
        self,
        *,
        candles: pd.DataFrame,
        reference_high: float,
    ) -> LiquiditySweep:

        self._validate_candles(
            candles
        )

        if reference_high <= 0:
            raise ValueError(
                "reference_high must be positive."
            )

        candle = candles.iloc[-1]

        high = float(
            candle["h"]
        )

        low = float(
            candle["l"]
        )

        close = float(
            candle["c"]
        )

        penetration = max(
            0.0,
            high - reference_high,
        )

        penetration_pct = (
            penetration
            / reference_high
            * 100
        )

        pierced = (
            high > reference_high
        )

        rejected = (
            close < reference_high
        )

        deep_enough = (
            penetration_pct
            >= self.minimum_penetration_pct
        )

        if (
            pierced
            and rejected
            and deep_enough
        ):

            return LiquiditySweep(
                sweep_type=(
                    LiquiditySweepType.BUY_SIDE
                ),

                status=(
                    LiquiditySweepStatus.CONFIRMED
                ),

                reference_level=(
                    reference_high
                ),

                candle_high=high,
                candle_low=low,
                candle_close=close,

                penetration=penetration,
                penetration_pct=(
                    penetration_pct
                ),

                reason=(
                    "Price swept above prior "
                    "high and closed back below."
                ),
            )

        return LiquiditySweep(
            sweep_type=(
                LiquiditySweepType.NONE
            ),

            status=(
                LiquiditySweepStatus.NOT_CONFIRMED
            ),

            reference_level=(
                reference_high
            ),

            candle_high=high,
            candle_low=low,
            candle_close=close,

            penetration=penetration,
            penetration_pct=(
                penetration_pct
            ),

            reason=(
                "No confirmed buy-side "
                "liquidity sweep."
            ),
        )

    # ==========================================================
    # SELL-SIDE SWEEP
    # ==========================================================

    def detect_sell_side(
        self,
        *,
        candles: pd.DataFrame,
        reference_low: float,
    ) -> LiquiditySweep:

        self._validate_candles(
            candles
        )

        if reference_low <= 0:
            raise ValueError(
                "reference_low must be positive."
            )

        candle = candles.iloc[-1]

        high = float(
            candle["h"]
        )

        low = float(
            candle["l"]
        )

        close = float(
            candle["c"]
        )

        penetration = max(
            0.0,
            reference_low - low,
        )

        penetration_pct = (
            penetration
            / reference_low
            * 100
        )

        pierced = (
            low < reference_low
        )

        rejected = (
            close > reference_low
        )

        deep_enough = (
            penetration_pct
            >= self.minimum_penetration_pct
        )

        if (
            pierced
            and rejected
            and deep_enough
        ):

            return LiquiditySweep(
                sweep_type=(
                    LiquiditySweepType.SELL_SIDE
                ),

                status=(
                    LiquiditySweepStatus.CONFIRMED
                ),

                reference_level=(
                    reference_low
                ),

                candle_high=high,
                candle_low=low,
                candle_close=close,

                penetration=penetration,
                penetration_pct=(
                    penetration_pct
                ),

                reason=(
                    "Price swept below prior "
                    "low and closed back above."
                ),
            )

        return LiquiditySweep(
            sweep_type=(
                LiquiditySweepType.NONE
            ),

            status=(
                LiquiditySweepStatus.NOT_CONFIRMED
            ),

            reference_level=(
                reference_low
            ),

            candle_high=high,
            candle_low=low,
            candle_close=close,

            penetration=penetration,
            penetration_pct=(
                penetration_pct
            ),

            reason=(
                "No confirmed sell-side "
                "liquidity sweep."
            ),
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
        " LIQUIDITY SWEEP ENGINE TEST"
    )
    print(
        "======================================"
    )

    engine = LiquiditySweepEngine(
        minimum_penetration_pct=0.0
    )

    # ----------------------------------------------------------
    # BUY-SIDE SWEEP TEST
    # ----------------------------------------------------------

    buy_side_candles = pd.DataFrame(
        {
            "h": [
                100.0,
                101.5,
            ],

            "l": [
                98.0,
                99.0,
            ],

            "c": [
                99.5,
                99.8,
            ],
        }
    )

    buy_result = (
        engine.detect_buy_side(
            candles=buy_side_candles,
            reference_high=100.0,
        )
    )

    print(
        "BUY-SIDE TEST"
    )

    print(
        "Status:",
        buy_result.status.value
    )

    print(
        "Type:",
        buy_result.sweep_type.value
    )

    print(
        "Reference:",
        buy_result.reference_level
    )

    print(
        "Penetration:",
        buy_result.penetration
    )

    print(
        "Reason:",
        buy_result.reason
    )

    assert (
        buy_result.status
        == LiquiditySweepStatus.CONFIRMED
    )

    assert (
        buy_result.sweep_type
        == LiquiditySweepType.BUY_SIDE
    )

    print(
        "--------------------------------------"
    )

    # ----------------------------------------------------------
    # SELL-SIDE SWEEP TEST
    # ----------------------------------------------------------

    sell_side_candles = pd.DataFrame(
        {
            "h": [
                102.0,
                101.0,
            ],

            "l": [
                100.0,
                98.5,
            ],

            "c": [
                101.0,
                100.2,
            ],
        }
    )

    sell_result = (
        engine.detect_sell_side(
            candles=sell_side_candles,
            reference_low=100.0,
        )
    )

    print(
        "SELL-SIDE TEST"
    )

    print(
        "Status:",
        sell_result.status.value
    )

    print(
        "Type:",
        sell_result.sweep_type.value
    )

    print(
        "Reference:",
        sell_result.reference_level
    )

    print(
        "Penetration:",
        sell_result.penetration
    )

    print(
        "Reason:",
        sell_result.reason
    )

    assert (
        sell_result.status
        == LiquiditySweepStatus.CONFIRMED
    )

    assert (
        sell_result.sweep_type
        == LiquiditySweepType.SELL_SIDE
    )

    print(
        "--------------------------------------"
    )

    # ----------------------------------------------------------
    # NO-SWEEP TEST
    # ----------------------------------------------------------

    no_sweep_candles = pd.DataFrame(
        {
            "h": [
                100.0,
                99.8,
            ],

            "l": [
                98.0,
                98.5,
            ],

            "c": [
                99.0,
                99.2,
            ],
        }
    )

    no_result = (
        engine.detect_buy_side(
            candles=no_sweep_candles,
            reference_high=100.0,
        )
    )

    print(
        "NO-SWEEP TEST"
    )

    print(
        "Status:",
        no_result.status.value
    )

    print(
        "Type:",
        no_result.sweep_type.value
    )

    print(
        "Reason:",
        no_result.reason
    )

    assert (
        no_result.status
        == LiquiditySweepStatus.NOT_CONFIRMED
    )

    assert (
        no_result.sweep_type
        == LiquiditySweepType.NONE
    )

    print(
        "--------------------------------------"
    )
    print(
        "LIQUIDITY SWEEP ENGINE TEST PASSED"
    )
    print(
        "======================================"
    )
    print()