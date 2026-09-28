from hyperliquid.info import Info
from hyperliquid.utils import constants


class HyperliquidClient:
    """
    Hyperliquid read-only API client.

    Responsibilities:
    - Connect to testnet or mainnet
    - Retrieve midpoint prices
    - Retrieve L2 order-book data
    - Retrieve exchange metadata
    """

    def __init__(
        self,
        testnet: bool = True,
    ):
        self.testnet = testnet

        self.base_url = (
            constants.TESTNET_API_URL
            if testnet
            else constants.MAINNET_API_URL
        )

        self.info = Info(
            self.base_url,
            skip_ws=True,
        )

    def get_all_mids(self):
        """
        Return current midpoint prices
        for all available markets.
        """

        return self.info.all_mids()

    def get_l2_book(
        self,
        symbol: str,
    ):
        """
        Return Hyperliquid L2 order book
        for one symbol.
        """

        return self.info.l2_snapshot(
            symbol
        )

    def get_meta(self):
        """
        Return exchange metadata.

        Includes available markets and
        contract information.
        """

        return self.info.meta()


if __name__ == "__main__":

    client = HyperliquidClient(
        testnet=True
    )

    print()
    print(
        "======================================"
    )
    print(
        " HYPERLIQUID CLIENT TEST"
    )
    print(
        "======================================"
    )

    mids = client.get_all_mids()

    print(
        "Network: TESTNET"
    )

    print(
        "BTC Mid:",
        mids.get("BTC")
    )

    print(
        "ETH Mid:",
        mids.get("ETH")
    )

    print(
        "SOL Mid:",
        mids.get("SOL")
    )

    print(
        "--------------------------------------"
    )

    book = client.get_l2_book(
        "BTC"
    )

    print(
        "BTC L2 Book received:",
        bool(book)
    )

    meta = client.get_meta()

    print(
        "Exchange metadata received:",
        bool(meta)
    )

    print(
        "======================================"
    )
    print()