from __future__ import annotations

from exchange.market_data import MarketDataEngine

from strategy.liquidity import (
    LiquiditySweepEngine,
    LiquiditySweepStatus,
)

from strategy.market_structure import (
    MarketStructureEngine,
)


if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " REAL HYPERLIQUID LIQUIDITY TEST"
    )
    print(
        "======================================"
    )

    print(
        "Network: TESTNET"
    )

    print(
        "Symbol: BTC"
    )

    print(
        "Timeframe: 15m"
    )

    print(
        "Data: CLOSED CANDLES ONLY"
    )

    print(
        "--------------------------------------"
    )

    # ==========================================================
    # LOAD CLOSED MARKET DATA
    # ==========================================================

    market_data = MarketDataEngine(
        testnet=True
    )

    candles = (
        market_data
        .get_closed_candles(
            symbol="BTC",
            interval="15m",
            lookback_minutes=(
                15 * 300
            ),
        )
    )

    if candles.empty:

        raise RuntimeError(
            "No closed BTC candles returned."
        )

    # ==========================================================
    # CURRENT STRUCTURE
    # ==========================================================

    structure_engine = (
        MarketStructureEngine(
            swing_window=2,
            minimum_swings=2,
        )
    )

    structure = (
        structure_engine.analyze(
            symbol="BTC",
            timeframe="15m",
            candles=candles,
        )
    )

    print(
        "Structure:",
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
        "--------------------------------------"
    )

    # ==========================================================
    # LIQUIDITY DETECTION
    # ==========================================================

    engine = LiquiditySweepEngine(
        minimum_penetration_pct=0.0
    )

    latest = candles.iloc[-1]

    print(
        "Latest Closed Candle"
    )

    print(
        "High:",
        float(latest["h"])
    )

    print(
        "Low:",
        float(latest["l"])
    )

    print(
        "Close:",
        float(latest["c"])
    )

    print(
        "--------------------------------------"
    )

    # ----------------------------------------------------------
    # BUY-SIDE LIQUIDITY
    # ----------------------------------------------------------

    buy_result = None

    if structure.swing_high is not None:

        buy_result = (
            engine.detect_buy_side(
                candles=candles,
                reference_high=(
                    structure.swing_high
                ),
            )
        )

        print(
            "BUY-SIDE LIQUIDITY"
        )

        print(
            "Reference:",
            buy_result.reference_level
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
            "Penetration:",
            round(
                buy_result.penetration,
                4,
            )
        )

        print(
            "Penetration %:",
            round(
                buy_result.penetration_pct,
                6,
            )
        )

        print(
            "Reason:",
            buy_result.reason
        )

        print(
            "--------------------------------------"
        )

    else:

        print(
            "No swing high available."
        )

        print(
            "--------------------------------------"
        )

    # ----------------------------------------------------------
    # SELL-SIDE LIQUIDITY
    # ----------------------------------------------------------

    sell_result = None

    if structure.swing_low is not None:

        sell_result = (
            engine.detect_sell_side(
                candles=candles,
                reference_low=(
                    structure.swing_low
                ),
            )
        )

        print(
            "SELL-SIDE LIQUIDITY"
        )

        print(
            "Reference:",
            sell_result.reference_level
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
            "Penetration:",
            round(
                sell_result.penetration,
                4,
            )
        )

        print(
            "Penetration %:",
            round(
                sell_result.penetration_pct,
                6,
            )
        )

        print(
            "Reason:",
            sell_result.reason
        )

        print(
            "--------------------------------------"
        )

    else:

        print(
            "No swing low available."
        )

        print(
            "--------------------------------------"
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    confirmed = []

    if (
        buy_result is not None
        and buy_result.status
        == LiquiditySweepStatus.CONFIRMED
    ):
        confirmed.append(
            "BUY_SIDE"
        )

    if (
        sell_result is not None
        and sell_result.status
        == LiquiditySweepStatus.CONFIRMED
    ):
        confirmed.append(
            "SELL_SIDE"
        )

    if confirmed:

        print(
            "Confirmed Sweep:",
            ", ".join(confirmed)
        )

    else:

        print(
            "Confirmed Sweep: NONE"
        )

        print(
            "NO LIQUIDITY TRIGGER is a valid result."
        )

    print(
        "--------------------------------------"
    )

    print(
        "REAL LIQUIDITY TEST PASSED"
    )

    print(
        "======================================"
    )

    print()