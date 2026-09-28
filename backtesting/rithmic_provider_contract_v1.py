"""Fail-closed contract for a future Rithmic ES/NQ provider adapter.

This module deliberately contains no Rithmic SDK, credentials, sockets, or order
submission. It defines the boundary that a provider implementation must satisfy
before it can be admitted to the provider-neutral paper pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

VERSION = "rithmic-provider-contract-v1"


class RithmicMode(str, Enum):
    TEST = "TEST"
    EXCHANGE_SIMULATOR = "EXCHANGE_SIMULATOR"


@dataclass(frozen=True, slots=True)
class RithmicConnectionConfig:
    mode: RithmicMode
    symbols: tuple[str, ...] = ("ES", "NQ")
    single_authoritative_connection: bool = True
    paper_only: bool = True
    trading_authority: bool = False

    def __post_init__(self) -> None:
        if self.symbols != ("ES", "NQ"):
            raise ValueError("Rithmic adapter is admitted only for ES/NQ")
        if not self.single_authoritative_connection:
            raise ValueError("one authoritative Rithmic connection is required")
        if not self.paper_only or self.trading_authority:
            raise ValueError("Rithmic contract cannot carry live authority")


@dataclass(frozen=True, slots=True)
class RithmicSessionStatus:
    authenticated: bool = False
    subscription_acknowledged: bool = False
    symbol_mapping_verified: bool = False
    heartbeat_fresh: bool = False
    current_samples: int = 0
    positions_reconciled: bool = False
    working_orders_reconciled: bool = False
    server_risk_verified: bool = False
    trading_authority: bool = False

    @property
    def paper_ready(self) -> bool:
        return all((self.authenticated, self.subscription_acknowledged,
                    self.symbol_mapping_verified, self.heartbeat_fresh,
                    self.current_samples > 0, self.positions_reconciled,
                    self.working_orders_reconciled, self.server_risk_verified,
                    not self.trading_authority))


@dataclass(frozen=True, slots=True)
class RithmicPaperAdapterV1:
    config: RithmicConnectionConfig
    status: RithmicSessionStatus = RithmicSessionStatus()
    provider: str = "RITHMIC"
    contract_version: str = VERSION

    def validate(self) -> dict[str, object]:
        """Return admission evidence; never enables orders or opens a connection."""
        return {
            "schema_version": VERSION,
            "provider": self.provider,
            "mode": self.config.mode.value,
            "symbols": list(self.config.symbols),
            "paper_ready": self.status.paper_ready,
            "paper_execution_permitted": False,
            "live_trading_permitted": False,
            "trading_authority": False,
        }
