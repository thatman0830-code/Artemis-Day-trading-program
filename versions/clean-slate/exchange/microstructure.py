import time
from dataclasses import dataclass

from exchange.hyperliquid_client import HyperliquidClient


@dataclass
class MicrostructureSnapshot:
    """
    Normalized snapshot of Hyperliquid
    order-book conditions.
    """

    symbol: str

    best_bid: float
    best_ask: float
    mid_price: float

    spread: float
    spread_pct: float
    spread_bps: float

    best_bid_size: float
    best_ask_size: float

    bid_depth: float
    ask_depth: float

    book_imbalance: float

    exchange_timestamp_ms: int
    local_timestamp_ms: int

    age_ms: int
    is_fresh: bool


class MicrostructureEngine:
    """
    Converts raw Hyperliquid L2 data into
    normalized execution metrics.
    """

    def __init__(
        self,
        testnet: bool = True,
        depth_levels: int = 10,
        max_age_ms: int = 5000,
    ):
        self.client = HyperliquidClient(
            testnet=testnet
        )

        self.depth_levels = depth_levels
        self.max_age_ms = max_age_ms

    @staticmethod
    def _price(level: dict) -> float:
        return float(
            level["px"]
        )

    @staticmethod
    def _size(level: dict) -> float:
        return float(
            level["sz"]
        )

    def get_snapshot(
        self,
        symbol: str,
    ) -> MicrostructureSnapshot:

        book = self.client.get_l2_book(
            symbol
        )

        if not book:
            raise RuntimeError(
                f"No L2 book returned for {symbol}."
            )

        levels = book.get(
            "levels"
        )

        if (
            not levels
            or len(levels) < 2
        ):
            raise RuntimeError(
                f"Invalid L2 book for {symbol}."
            )

        bids = levels[0]
        asks = levels[1]

        if not bids or not asks:
            raise RuntimeError(
                f"Empty bid/ask book for {symbol}."
            )

        best_bid = self._price(
            bids[0]
        )

        best_ask = self._price(
            asks[0]
        )

        best_bid_size = self._size(
            bids[0]
        )

        best_ask_size = self._size(
            asks[0]
        )

        mid_price = (
            best_bid + best_ask
        ) / 2

        spread = (
            best_ask - best_bid
        )

        spread_pct = (
            spread / mid_price
        ) * 100

        spread_bps = (
            spread / mid_price
        ) * 10000

        bid_levels = bids[
            :self.depth_levels
        ]

        ask_levels = asks[
            :self.depth_levels
        ]

        bid_depth = sum(
            self._size(level)
            for level in bid_levels
        )

        ask_depth = sum(
            self._size(level)
            for level in ask_levels
        )

        total_depth = (
            bid_depth + ask_depth
        )

        if total_depth > 0:
            book_imbalance = (
                bid_depth - ask_depth
            ) / total_depth
        else:
            book_imbalance = 0.0

        exchange_timestamp_ms = int(
            book.get(
                "time",
                0
            )
        )

        local_timestamp_ms = int(
            time.time() * 1000
        )

        if exchange_timestamp_ms > 0:
            age_ms = max(
                0,
                local_timestamp_ms
                - exchange_timestamp_ms,
            )
        else:
            age_ms = (
                self.max_age_ms + 1
            )

        is_fresh = (
            age_ms
            <= self.max_age_ms
        )

        return MicrostructureSnapshot(
            symbol=symbol,

            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,

            spread=spread,
            spread_pct=spread_pct,
            spread_bps=spread_bps,

            best_bid_size=best_bid_size,
            best_ask_size=best_ask_size,

            bid_depth=bid_depth,
            ask_depth=ask_depth,

            book_imbalance=book_imbalance,

            exchange_timestamp_ms=(
                exchange_timestamp_ms
            ),

            local_timestamp_ms=(
                local_timestamp_ms
            ),

            age_ms=age_ms,
            is_fresh=is_fresh,
        )


if __name__ == "__main__":

    engine = MicrostructureEngine(
        testnet=True,
        depth_levels=10,
        max_age_ms=5000,
    )

    snapshot = engine.get_snapshot(
        "BTC"
    )

    print()
    print(
        "======================================"
    )
    print(
        " HYPERLIQUID MICROSTRUCTURE ENGINE"
    )
    print(
        "======================================"
    )

    print(
        "Network: TESTNET"
    )

    print(
        "Symbol:",
        snapshot.symbol
    )

    print(
        "--------------------------------------"
    )

    print(
        "Best Bid:       ",
        snapshot.best_bid
    )

    print(
        "Best Ask:       ",
        snapshot.best_ask
    )

    print(
        "Mid Price:      ",
        snapshot.mid_price
    )

    print(
        "Spread:         ",
        snapshot.spread
    )

    print(
        "Spread %:       ",
        round(
            snapshot.spread_pct,
            6
        )
    )

    print(
        "Spread BPS:     ",
        round(
            snapshot.spread_bps,
            4
        )
    )

    print(
        "--------------------------------------"
    )

    print(
        "Best Bid Size:  ",
        snapshot.best_bid_size
    )

    print(
        "Best Ask Size:  ",
        snapshot.best_ask_size
    )

    print(
        "Bid Depth (10): ",
        snapshot.bid_depth
    )

    print(
        "Ask Depth (10): ",
        snapshot.ask_depth
    )

    print(
        "Book Imbalance: ",
        round(
            snapshot.book_imbalance,
            4
        )
    )

    print(
        "--------------------------------------"
    )

    print(
        "Book Age MS:    ",
        snapshot.age_ms
    )

    print(
        "Data Fresh:     ",
        snapshot.is_fresh
    )

    print(
        "======================================"
    )
    print()