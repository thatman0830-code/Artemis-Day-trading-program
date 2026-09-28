import time

import pandas as pd

from exchange.hyperliquid_client import HyperliquidClient


class MarketDataEngine:
    """
    Historical market-data engine for Hyperliquid.

    Responsibilities:
    - Retrieve OHLCV candle data
    - Convert raw Hyperliquid data into pandas DataFrames
    - Identify completed vs. forming candles
    - Provide closed-candle data for strategy analysis
    - Load multiple timeframes
    """

    def __init__(self, testnet: bool = True):
        self.client = HyperliquidClient(
            testnet=testnet
        )

    def get_candles(
        self,
        symbol: str,
        interval: str = "1m",
        lookback_minutes: int = 100,
    ) -> pd.DataFrame:
        """
        Retrieve historical candles from Hyperliquid.

        Includes both completed candles and the
        currently forming candle when returned
        by the API.
        """

        end_ms = int(
            time.time() * 1000
        )

        start_ms = end_ms - (
            lookback_minutes
            * 60
            * 1000
        )

        candles = (
            self.client.info.candles_snapshot(
                symbol,
                interval,
                start_ms,
                end_ms,
            )
        )

        df = pd.DataFrame(
            candles
        )

        if df.empty:
            return df

        # Hyperliquid candle fields:
        #
        # t = candle open timestamp
        # T = candle close timestamp
        # s = symbol
        # i = interval
        # o = open
        # c = close
        # h = high
        # l = low
        # v = volume
        # n = number of trades

        numeric_columns = [
            "o",
            "h",
            "l",
            "c",
            "v",
        ]

        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        # Convert candle opening timestamp.

        if "t" in df.columns:

            df["datetime"] = (
                pd.to_datetime(
                    df["t"],
                    unit="ms",
                    utc=True,
                )
            )

        # Convert candle closing timestamp
        # and determine whether candle is final.

        if "T" in df.columns:

            df["close_datetime"] = (
                pd.to_datetime(
                    df["T"],
                    unit="ms",
                    utc=True,
                )
            )

            now_ms = int(
                time.time() * 1000
            )

            df["is_closed"] = (
                df["T"] <= now_ms
            )

        return df

    def get_closed_candles(
        self,
        symbol: str,
        interval: str,
        lookback_minutes: int,
    ) -> pd.DataFrame:
        """
        Return completed candles only.

        Strategy confirmation should use this
        method rather than a currently forming
        candle.
        """

        df = self.get_candles(
            symbol=symbol,
            interval=interval,
            lookback_minutes=lookback_minutes,
        )

        if df.empty:
            return df

        if "is_closed" not in df.columns:

            raise ValueError(
                "Candle close-state unavailable."
            )

        closed_df = df[
            df["is_closed"]
        ].copy()

        return closed_df

    def get_multi_timeframe(
        self,
        symbol: str,
        timeframes: dict | None = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Retrieve completed candles across
        multiple trading timeframes.
        """

        if timeframes is None:

            timeframes = {
                "1m": 300,
                "5m": 1500,
                "15m": 4500,
                "1h": 18000,
                "4h": 72000,
            }

        market_data = {}

        for (
            interval,
            lookback_minutes,
        ) in timeframes.items():

            df = self.get_closed_candles(
                symbol=symbol,
                interval=interval,
                lookback_minutes=lookback_minutes,
            )

            market_data[
                interval
            ] = df

        return market_data


if __name__ == "__main__":

    engine = MarketDataEngine(
        testnet=True
    )

    market = (
        engine.get_multi_timeframe(
            symbol="BTC"
        )
    )

    print()
    print(
        "======================================"
    )
    print(
        " HYPERLIQUID MULTI-TIMEFRAME ENGINE"
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
        "Data mode: CLOSED CANDLES ONLY"
    )
    print(
        "--------------------------------------"
    )

    for (
        timeframe,
        df,
    ) in market.items():

        if df.empty:

            print(
                timeframe,
                "| NO CLOSED DATA"
            )

            continue

        latest = df.iloc[-1]

        print(
            timeframe.ljust(4),
            "| Candles:",
            str(
                len(df)
            ).ljust(5),
            "| Close:",
            str(
                latest["c"]
            ).ljust(12),
            "| Open Time:",
            latest["datetime"],
        )

    print(
        "======================================"
    )
    print()