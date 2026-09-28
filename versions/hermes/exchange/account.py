from dataclasses import dataclass
from typing import Any

from config.settings import settings
from exchange.hyperliquid_client import HyperliquidClient


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    size: float
    entry_price: float | None
    mark_price: float | None
    unrealized_pnl: float
    leverage: float | None


@dataclass(frozen=True)
class OpenOrderSnapshot:
    symbol: str
    side: str
    price: float
    size: float
    order_id: int | None
    timestamp_ms: int | None


@dataclass(frozen=True)
class AccountSnapshot:
    address: str

    account_value: float
    total_margin_used: float
    withdrawable: float

    positions: list[PositionSnapshot]
    open_orders: list[OpenOrderSnapshot]


class HyperliquidAccountReader:
    """
    Read-only Hyperliquid account-state reader.

    Reads:
    - account value
    - margin usage
    - withdrawable balance
    - open perpetual positions
    - open orders

    A public account address is sufficient.
    This module does not require signing keys.
    """

    def __init__(
        self,
        address: str,
        testnet: bool = True,
    ):
        if not address:
            raise ValueError(
                "Hyperliquid account address is required."
            )

        self.address = address

        self.client = HyperliquidClient(
            testnet=testnet
        )

    @staticmethod
    def _optional_float(
        value: Any,
    ) -> float | None:

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_int(
        value: Any,
    ) -> int | None:

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _get_positions(
        self,
        raw_state: dict[str, Any],
    ) -> list[PositionSnapshot]:

        positions: list[
            PositionSnapshot
        ] = []

        for item in raw_state.get(
            "assetPositions",
            [],
        ):
            position = item.get(
                "position",
                {},
            )

            symbol = str(
                position.get(
                    "coin",
                    "",
                )
            )

            try:
                size = float(
                    position.get(
                        "szi",
                        0,
                    )
                )
            except (TypeError, ValueError):
                size = 0.0

            # Ignore zero-size entries.
            if size == 0:
                continue

            entry_price = (
                self._optional_float(
                    position.get(
                        "entryPx"
                    )
                )
            )

            mark_price = (
                self._optional_float(
                    position.get(
                        "markPx"
                    )
                )
            )

            try:
                unrealized_pnl = float(
                    position.get(
                        "unrealizedPnl",
                        0,
                    )
                )
            except (TypeError, ValueError):
                unrealized_pnl = 0.0

            leverage_info = (
                position.get(
                    "leverage",
                    {},
                )
            )

            leverage = None

            if isinstance(
                leverage_info,
                dict,
            ):
                leverage = (
                    self._optional_float(
                        leverage_info.get(
                            "value"
                        )
                    )
                )

            positions.append(
                PositionSnapshot(
                    symbol=symbol,
                    size=size,
                    entry_price=entry_price,
                    mark_price=mark_price,
                    unrealized_pnl=(
                        unrealized_pnl
                    ),
                    leverage=leverage,
                )
            )

        return positions

    def _get_open_orders(
        self,
    ) -> list[OpenOrderSnapshot]:

        raw_orders = (
            self.client.info.open_orders(
                self.address
            )
        )

        orders: list[
            OpenOrderSnapshot
        ] = []

        for order in raw_orders:

            symbol = str(
                order.get(
                    "coin",
                    "",
                )
            )

            side_raw = str(
                order.get(
                    "side",
                    "",
                )
            ).upper()

            if side_raw == "B":
                side = "BUY"
            elif side_raw == "A":
                side = "SELL"
            else:
                side = side_raw

            try:
                price = float(
                    order.get(
                        "limitPx",
                        0,
                    )
                )
            except (TypeError, ValueError):
                price = 0.0

            try:
                size = float(
                    order.get(
                        "sz",
                        0,
                    )
                )
            except (TypeError, ValueError):
                size = 0.0

            order_id = (
                self._optional_int(
                    order.get(
                        "oid"
                    )
                )
            )

            timestamp_ms = (
                self._optional_int(
                    order.get(
                        "timestamp"
                    )
                )
            )

            orders.append(
                OpenOrderSnapshot(
                    symbol=symbol,
                    side=side,
                    price=price,
                    size=size,
                    order_id=order_id,
                    timestamp_ms=(
                        timestamp_ms
                    ),
                )
            )

        return orders

    def get_account_state(
        self,
    ) -> AccountSnapshot:

        raw_state = (
            self.client.info.user_state(
                self.address
            )
        )

        margin_summary = (
            raw_state.get(
                "marginSummary",
                {},
            )
        )

        try:
            account_value = float(
                margin_summary.get(
                    "accountValue",
                    0,
                )
            )
        except (TypeError, ValueError):
            account_value = 0.0

        try:
            total_margin_used = float(
                margin_summary.get(
                    "totalMarginUsed",
                    0,
                )
            )
        except (TypeError, ValueError):
            total_margin_used = 0.0

        try:
            withdrawable = float(
                raw_state.get(
                    "withdrawable",
                    0,
                )
            )
        except (TypeError, ValueError):
            withdrawable = 0.0

        positions = (
            self._get_positions(
                raw_state
            )
        )

        open_orders = (
            self._get_open_orders()
        )

        return AccountSnapshot(
            address=self.address,
            account_value=account_value,
            total_margin_used=(
                total_margin_used
            ),
            withdrawable=withdrawable,
            positions=positions,
            open_orders=open_orders,
        )


if __name__ == "__main__":

    address = settings.account_address

    print()
    print(
        "======================================"
    )
    print(
        " HYPERLIQUID ACCOUNT STATE"
    )
    print(
        "======================================"
    )

    if not address:

        print(
            "No account address configured."
        )
        print(
            "Add HL_ACCOUNT_ADDRESS to .env."
        )
        print(
            "No private key is required."
        )
        print(
            "======================================"
        )
        print()

        raise SystemExit(0)

    testnet = (
        settings.network
        == "testnet"
    )

    print(
        "Network:",
        (
            "TESTNET"
            if testnet
            else "MAINNET"
        )
    )

    reader = (
        HyperliquidAccountReader(
            address=address,
            testnet=testnet,
        )
    )

    snapshot = (
        reader.get_account_state()
    )

    print(
        "Account Value:",
        snapshot.account_value
    )

    print(
        "Margin Used:",
        snapshot.total_margin_used
    )

    print(
        "Withdrawable:",
        snapshot.withdrawable
    )

    print(
        "--------------------------------------"
    )

    print(
        "OPEN POSITIONS:",
        len(snapshot.positions)
    )

    if not snapshot.positions:

        print(
            "None"
        )

    for position in snapshot.positions:

        direction = (
            "LONG"
            if position.size > 0
            else "SHORT"
        )

        print(
            position.symbol,
            "|",
            direction,
            "| Size:",
            abs(position.size),
            "| Entry:",
            position.entry_price,
            "| Mark:",
            position.mark_price,
            "| uPnL:",
            position.unrealized_pnl,
            "| Leverage:",
            position.leverage,
        )

    print(
        "--------------------------------------"
    )

    print(
        "OPEN ORDERS:",
        len(snapshot.open_orders)
    )

    if not snapshot.open_orders:

        print(
            "None"
        )

    for order in snapshot.open_orders:

        print(
            order.symbol,
            "|",
            order.side,
            "| Size:",
            order.size,
            "| Price:",
            order.price,
            "| OID:",
            order.order_id,
        )

    print(
        "--------------------------------------"
    )

    print(
        "Trading Enabled:",
        settings.trading_enabled
    )

    print(
        "Live Trading:",
        settings.live_trading_enabled
    )

    print(
        "======================================"
    )
    print()