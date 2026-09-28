import time
from dataclasses import dataclass
from enum import Enum

from exchange.websocket import HyperliquidWebSocket


class MarketHealthStatus(str, Enum):
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DISCONNECTED = "DISCONNECTED"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class MarketHealthReport:
    symbol: str
    status: MarketHealthStatus

    connected: bool
    fresh: bool
    complete: bool

    age_ms: int | None
    message_count: int

    best_bid: float | None
    best_ask: float | None
    mid_price: float | None

    trading_data_approved: bool
    reason: str


class MarketDataHealthGate:
    """
    Fail-closed market-data safety gate.

    No strategy or execution component should
    consider realtime data tradable unless this
    gate explicitly approves it.
    """

    def __init__(
        self,
        realtime: HyperliquidWebSocket,
        max_age_ms: int = 10_000,
        minimum_messages: int = 2,
    ):
        self.realtime = realtime
        self.max_age_ms = max_age_ms
        self.minimum_messages = minimum_messages

    def evaluate(self) -> MarketHealthReport:
        state = self.realtime.state

        with state.lock:
            connected = state.connected
            message_count = state.message_count

            best_bid = state.best_bid
            best_ask = state.best_ask
            mid_price = state.mid_price

        age_ms = state.age_ms()

        fresh = (
            age_ms is not None
            and age_ms <= self.max_age_ms
        )

        complete = all(
            value is not None
            for value in (
                best_bid,
                best_ask,
                mid_price,
            )
        )

        warmed_up = (
            message_count
            >= self.minimum_messages
        )

        prices_valid = (
            complete
            and best_bid > 0
            and best_ask > 0
            and mid_price > 0
            and best_ask >= best_bid
        )

        if not connected:

            status = (
                MarketHealthStatus.DISCONNECTED
            )

            reason = (
                "WebSocket is disconnected."
            )

        elif not fresh:

            status = (
                MarketHealthStatus.STALE
            )

            reason = (
                "Realtime market data is stale."
            )

        elif not complete:

            status = (
                MarketHealthStatus.INCOMPLETE
            )

            reason = (
                "Realtime market state is incomplete."
            )

        elif not warmed_up:

            status = (
                MarketHealthStatus.STARTING
            )

            reason = (
                "Waiting for sufficient market-data messages."
            )

        elif not prices_valid:

            status = (
                MarketHealthStatus.INCOMPLETE
            )

            reason = (
                "Realtime prices failed validation."
            )

        else:

            status = (
                MarketHealthStatus.HEALTHY
            )

            reason = (
                "Realtime market data is healthy."
            )

        trading_data_approved = (
            status
            == MarketHealthStatus.HEALTHY
        )

        return MarketHealthReport(
            symbol=state.symbol,
            status=status,

            connected=connected,
            fresh=fresh,
            complete=complete,

            age_ms=age_ms,
            message_count=message_count,

            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,

            trading_data_approved=(
                trading_data_approved
            ),

            reason=reason,
        )


if __name__ == "__main__":

    realtime = HyperliquidWebSocket(
        symbol="BTC",
        testnet=True,
        stale_after_ms=10_000,
    )

    gate = MarketDataHealthGate(
        realtime=realtime,
        max_age_ms=10_000,
        minimum_messages=2,
    )

    print()
    print(
        "======================================"
    )
    print(
        " MARKET DATA HEALTH GATE"
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
        "Policy: FAIL CLOSED"
    )
    print(
        "--------------------------------------"
    )

    # Test before connection.
    before = gate.evaluate()

    print(
        "BEFORE CONNECTION"
    )
    print(
        "Status:  ",
        before.status.value
    )
    print(
        "Approved:",
        before.trading_data_approved
    )
    print(
        "Reason:  ",
        before.reason
    )

    print(
        "--------------------------------------"
    )

    realtime.start()

    try:

        for _ in range(15):

            time.sleep(1)

            report = (
                gate.evaluate()
            )

            print(
                "Status:",
                report.status.value.ljust(12),
                "| Approved:",
                str(
                    report.trading_data_approved
                ).ljust(5),
                "| Connected:",
                str(
                    report.connected
                ).ljust(5),
                "| Fresh:",
                str(
                    report.fresh
                ).ljust(5),
                "| Msg:",
                report.message_count,
                "| Age:",
                report.age_ms,
                "|",
                report.reason,
            )

    except KeyboardInterrupt:

        print(
            "\nManual shutdown requested."
        )

    finally:

        realtime.stop()

        after = gate.evaluate()

        print(
            "--------------------------------------"
        )
        print(
            "AFTER SHUTDOWN"
        )
        print(
            "Status:  ",
            after.status.value
        )
        print(
            "Approved:",
            after.trading_data_approved
        )
        print(
            "Reason:  ",
            after.reason
        )
        print(
            "======================================"
        )
        print()