import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import websocket

from hyperliquid.utils import constants


@dataclass
class RealtimeMarketState:
    """
    Shared realtime market state.

    The trading engine will later use this
    state to determine whether realtime
    market data is healthy enough to trust.
    """

    symbol: str

    best_bid: float | None = None
    best_ask: float | None = None
    mid_price: float | None = None

    last_trade_price: float | None = None

    message_count: int = 0
    last_message_ms: int = 0

    connected: bool = False

    reconnect_count: int = 0

    lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
    )

    def record_message(self):
        """
        Record receipt of valid WebSocket data.
        """

        with self.lock:

            self.message_count += 1

            self.last_message_ms = int(
                time.time() * 1000
            )

    def age_ms(self) -> int | None:
        """
        Return milliseconds since the
        last valid market-data message.
        """

        with self.lock:

            if self.last_message_ms == 0:
                return None

            return (
                int(time.time() * 1000)
                - self.last_message_ms
            )

    def is_fresh(
        self,
        max_age_ms: int,
    ) -> bool:
        """
        Determine whether realtime market
        data is fresh enough to trust.
        """

        age = self.age_ms()

        if age is None:
            return False

        return age <= max_age_ms

    def is_healthy(
        self,
        max_age_ms: int,
    ) -> bool:
        """
        Connection must be active AND
        market data must be fresh.
        """

        with self.lock:
            connected = self.connected

        return (
            connected
            and self.is_fresh(
                max_age_ms
            )
        )


class HyperliquidWebSocket:
    """
    Resilient read-only Hyperliquid
    realtime market-data engine.

    Features:
    - Trades subscription
    - L2 order-book subscription
    - Market-state tracking
    - Data freshness monitoring
    - Automatic reconnection
    - Exponential reconnect delay
    - Graceful shutdown
    """

    def __init__(
        self,
        symbol: str = "BTC",
        testnet: bool = True,
        stale_after_ms: int = 10_000,
        reconnect_min_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
    ):
        self.symbol = symbol
        self.testnet = testnet

        self.stale_after_ms = (
            stale_after_ms
        )

        self.reconnect_min_seconds = (
            reconnect_min_seconds
        )

        self.reconnect_max_seconds = (
            reconnect_max_seconds
        )

        api_url = (
            constants.TESTNET_API_URL
            if testnet
            else constants.MAINNET_API_URL
        )

        self.ws_url = (
            api_url.replace(
                "https://",
                "wss://",
            )
            + "/ws"
        )

        self.state = RealtimeMarketState(
            symbol=symbol
        )

        self.ws = None

        self.thread = None

        self.stop_event = (
            threading.Event()
        )

    def _subscribe(
        self,
        ws,
    ):
        """
        Subscribe to realtime trades
        and L2 order-book updates.
        """

        subscriptions = [
            {
                "method": "subscribe",
                "subscription": {
                    "type": "trades",
                    "coin": self.symbol,
                },
            },
            {
                "method": "subscribe",
                "subscription": {
                    "type": "l2Book",
                    "coin": self.symbol,
                },
            },
        ]

        for subscription in subscriptions:

            ws.send(
                json.dumps(
                    subscription
                )
            )

    def _on_open(
        self,
        ws,
    ):
        with self.state.lock:

            self.state.connected = True

        print(
            "[WS] Connected to Hyperliquid."
        )

        self._subscribe(
            ws
        )

    def _on_message(
        self,
        ws,
        message,
    ):
        try:

            payload = json.loads(
                message
            )

            channel = payload.get(
                "channel"
            )

            data = payload.get(
                "data"
            )

            # Only count actual market-data
            # channels as freshness updates.

            if channel == "trades":

                self._handle_trades(
                    data
                )

                self.state.record_message()

            elif channel == "l2Book":

                self._handle_l2_book(
                    data
                )

                self.state.record_message()

        except Exception as error:

            print(
                "[WS] Message error:",
                error
            )

    def _handle_trades(
        self,
        data: Any,
    ):
        if not data:
            return

        trades = (
            data
            if isinstance(
                data,
                list,
            )
            else [data]
        )

        latest = trades[-1]

        price = latest.get(
            "px"
        )

        if price is None:
            return

        with self.state.lock:

            self.state.last_trade_price = (
                float(price)
            )

    def _handle_l2_book(
        self,
        data: Any,
    ):
        if not data:
            return

        levels = data.get(
            "levels"
        )

        if (
            not levels
            or len(levels) < 2
        ):
            return

        bids = levels[0]
        asks = levels[1]

        if not bids or not asks:
            return

        best_bid = float(
            bids[0]["px"]
        )

        best_ask = float(
            asks[0]["px"]
        )

        mid_price = (
            best_bid
            + best_ask
        ) / 2

        with self.state.lock:

            self.state.best_bid = (
                best_bid
            )

            self.state.best_ask = (
                best_ask
            )

            self.state.mid_price = (
                mid_price
            )

    def _on_error(
        self,
        ws,
        error,
    ):
        if not self.stop_event.is_set():

            print(
                "[WS] Error:",
                error
            )

    def _on_close(
        self,
        ws,
        close_status_code,
        close_message,
    ):
        with self.state.lock:

            self.state.connected = False

        if not self.stop_event.is_set():

            print(
                "[WS] Connection lost."
            )

    def _connection_loop(
        self,
    ):
        """
        Maintain the WebSocket connection.

        If disconnected unexpectedly,
        reconnect automatically using
        exponential backoff.
        """

        reconnect_delay = (
            self.reconnect_min_seconds
        )

        while not self.stop_event.is_set():

            try:

                self.ws = (
                    websocket.WebSocketApp(
                        self.ws_url,
                        on_open=self._on_open,
                        on_message=(
                            self._on_message
                        ),
                        on_error=self._on_error,
                        on_close=self._on_close,
                    )
                )

                self.ws.run_forever(
                    ping_interval=20,
                    ping_timeout=10,
                )

            except Exception as error:

                if not self.stop_event.is_set():

                    print(
                        "[WS] Connection loop error:",
                        error
                    )

            with self.state.lock:

                self.state.connected = False

            if self.stop_event.is_set():
                break

            with self.state.lock:

                self.state.reconnect_count += 1

                reconnect_number = (
                    self.state.reconnect_count
                )

            print(
                "[WS] Reconnect attempt",
                reconnect_number,
                "in",
                round(
                    reconnect_delay,
                    2,
                ),
                "seconds...",
            )

            if self.stop_event.wait(
                reconnect_delay
            ):
                break

            reconnect_delay = min(
                reconnect_delay * 2,
                self.reconnect_max_seconds,
            )

            # After a successful connection,
            # _on_open will mark connected.
            #
            # The delay remains bounded and
            # will be improved later with
            # connection-duration tracking.

    def start(
        self,
    ):
        """
        Start the persistent realtime
        connection in the background.
        """

        if (
            self.thread
            and self.thread.is_alive()
        ):
            return

        self.stop_event.clear()

        self.thread = threading.Thread(
            target=self._connection_loop,
            daemon=True,
        )

        self.thread.start()

    def stop(
        self,
    ):
        """
        Gracefully stop realtime data.
        """

        self.stop_event.set()

        if self.ws:

            try:
                self.ws.close()
            except Exception:
                pass

        if self.thread:

            self.thread.join(
                timeout=5
            )

        with self.state.lock:

            self.state.connected = False


if __name__ == "__main__":

    engine = HyperliquidWebSocket(
        symbol="BTC",
        testnet=True,
        stale_after_ms=10_000,
    )

    print()
    print(
        "======================================"
    )
    print(
        " HYPERLIQUID WEBSOCKET HEALTH TEST"
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
        "Mode: READ ONLY"
    )

    print(
        "Stale threshold: 10000 MS"
    )

    print(
        "--------------------------------------"
    )

    engine.start()

    try:

        time.sleep(2)

        for _ in range(30):

            with engine.state.lock:

                connected = (
                    engine.state.connected
                )

                bid = (
                    engine.state.best_bid
                )

                ask = (
                    engine.state.best_ask
                )

                mid = (
                    engine.state.mid_price
                )

                last_trade = (
                    engine.state.last_trade_price
                )

                messages = (
                    engine.state.message_count
                )

                reconnects = (
                    engine.state.reconnect_count
                )

            age = (
                engine.state.age_ms()
            )

            fresh = (
                engine.state.is_fresh(
                    engine.stale_after_ms
                )
            )

            healthy = (
                engine.state.is_healthy(
                    engine.stale_after_ms
                )
            )

            print(
                "Connected:",
                str(connected).ljust(5),
                "| Fresh:",
                str(fresh).ljust(5),
                "| Healthy:",
                str(healthy).ljust(5),
                "| Bid:",
                str(bid).ljust(10),
                "| Ask:",
                str(ask).ljust(10),
                "| Mid:",
                str(mid).ljust(10),
                "| Last:",
                str(last_trade).ljust(10),
                "| Msg:",
                messages,
                "| Age:",
                age,
                "| Reconnects:",
                reconnects,
            )

            time.sleep(1)

    except KeyboardInterrupt:

        print()
        print(
            "Manual shutdown requested."
        )

    finally:

        engine.stop()

        print(
            "--------------------------------------"
        )

        print(
            "Realtime engine stopped."
        )

        print(
            "======================================"
        )

        print()