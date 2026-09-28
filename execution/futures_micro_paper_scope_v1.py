"""Conservative, non-authoritative scope for future MES/MNQ paper execution.

This records owner direction without making the still-incomplete futures
economics specification executable.  Research remains rooted in ES/NQ while
any eventual paper orders must use an exact IBKR micro-futures contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket


VERSION = "futures-micro-paper-scope-v1"
STARTING_EQUITY = Decimal("50000")
_MONTH_NUMBER = {"H": "03", "M": "06", "U": "09", "Z": "12"}


class FuturesMicroPaperScopeError(RuntimeError):
    pass


class FuturesPaperBroker(str, Enum):
    IBKR_PAPER = "IBKR_PAPER"


@dataclass(frozen=True)
class MicroProductMappingV1:
    research_market: FuturesCanonicalMarket
    execution_root: str
    point_value: Decimal
    minimum_price_increment: Decimal
    tick_value: Decimal


@dataclass(frozen=True)
class VerifiedMicroContractV1:
    research_market: FuturesCanonicalMarket
    local_symbol: str
    expiry_yyyymm: str
    ibkr_contract_id: int


@dataclass(frozen=True)
class FuturesMicroPaperScopeV1:
    scope_id: str
    broker: FuturesPaperBroker
    starting_equity: Decimal
    mappings: tuple[MicroProductMappingV1, ...]
    max_concurrent_futures_positions: int = 1
    shared_futures_portfolio: bool = True
    btc_venue_unchanged: bool = True
    owner_direction_recorded: bool = True
    economics_complete: bool = False
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION

    def mapping_for(self, market: FuturesCanonicalMarket) -> MicroProductMappingV1:
        if not isinstance(market, FuturesCanonicalMarket):
            raise TypeError("explicit ES or NQ research market required")
        return next(item for item in self.mappings if item.research_market is market)

    def verify_contract(self, contract: VerifiedMicroContractV1) -> MicroProductMappingV1:
        if not isinstance(contract, VerifiedMicroContractV1):
            raise TypeError("verified IBKR micro contract required")
        mapping = self.mapping_for(contract.research_market)
        symbol = contract.local_symbol.strip().upper()
        if "!" in symbol or not re.fullmatch(rf"{mapping.execution_root}[HMUZ]\d{{1,2}}", symbol):
            raise FuturesMicroPaperScopeError("continuous, synthetic, or wrong execution symbol")
        if not re.fullmatch(r"20\d{4}", contract.expiry_yyyymm):
            raise FuturesMicroPaperScopeError("exact YYYYMM contract expiry required")
        month_code = symbol[len(mapping.execution_root)]
        if contract.expiry_yyyymm[4:] != _MONTH_NUMBER[month_code]:
            raise FuturesMicroPaperScopeError("symbol month and contract expiry differ")
        year_code = symbol[len(mapping.execution_root) + 1:]
        if not contract.expiry_yyyymm[:4].endswith(year_code):
            raise FuturesMicroPaperScopeError("symbol year and contract expiry differ")
        if isinstance(contract.ibkr_contract_id, bool) or not isinstance(contract.ibkr_contract_id, int) \
                or contract.ibkr_contract_id <= 0:
            raise FuturesMicroPaperScopeError("positive IBKR contract identity required")
        return mapping


def create_recommended_micro_futures_scope(
    *, starting_equity: Decimal = STARTING_EQUITY,
) -> FuturesMicroPaperScopeV1:
    if not isinstance(starting_equity, Decimal):
        raise TypeError("starting equity must be an exact Decimal")
    if not starting_equity.is_finite() or starting_equity != STARTING_EQUITY:
        raise FuturesMicroPaperScopeError("owner-authorized futures equity must equal 50000 USD")
    mappings = (
        MicroProductMappingV1(FuturesCanonicalMarket.ES, "MES", Decimal("5"),
                              Decimal("0.25"), Decimal("1.25")),
        MicroProductMappingV1(FuturesCanonicalMarket.NQ, "MNQ", Decimal("2"),
                              Decimal("0.25"), Decimal("0.50")),
    )
    identity = {
        "version": VERSION, "broker": FuturesPaperBroker.IBKR_PAPER.value,
        "starting_equity": str(starting_equity), "max_positions": 1,
        "mappings": [[x.research_market.value, x.execution_root,
                      str(x.point_value), str(x.minimum_price_increment), str(x.tick_value)]
                     for x in mappings],
    }
    scope_id = hashlib.sha256(json.dumps(identity, sort_keys=True,
        separators=(",", ":")).encode("ascii")).hexdigest()
    return FuturesMicroPaperScopeV1(scope_id, FuturesPaperBroker.IBKR_PAPER,
                                    starting_equity, mappings)
