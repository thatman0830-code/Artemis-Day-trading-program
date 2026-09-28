import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Central configuration for the trading engine."""

    network: str = os.getenv("HL_NETWORK", "testnet")

    account_address: str = os.getenv(
        "HL_ACCOUNT_ADDRESS",
        ""
    )

    api_wallet_private_key: str = os.getenv(
        "HL_API_WALLET_PRIVATE_KEY",
        ""
    )

    trading_enabled: bool = (
        os.getenv("TRADING_ENABLED", "false").lower()
        == "true"
    )

    live_trading_enabled: bool = (
        os.getenv(
            "LIVE_TRADING_ENABLED",
            "false"
        ).lower()
        == "true"
    )

    max_risk_per_trade_pct: float = float(
        os.getenv(
            "MAX_RISK_PER_TRADE_PCT",
            "0.25"
        )
    )

    max_daily_loss_pct: float = float(
        os.getenv(
            "MAX_DAILY_LOSS_PCT",
            "1.00"
        )
    )

    max_consecutive_losses: int = int(
        os.getenv(
            "MAX_CONSECUTIVE_LOSSES",
            "3"
        )
    )


settings = Settings()