"""Exact Hyperliquid perpetual price and size precision rules.

This module validates paper economics only.  It does not format, sign, or submit
orders and it owns no network transport.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json


VERSION = "hyperliquid-perpetual-precision-v1"
MAXIMUM_SIGNIFICANT_FIGURES = 5
PERPETUAL_MAXIMUM_DECIMALS = 6


class HyperliquidPerpetualPrecisionError(ValueError):
    pass


def _exact_positive(value: Decimal, name: str) -> None:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise HyperliquidPerpetualPrecisionError(f"{name} must be a positive exact Decimal")


def quantity_step(*, size_decimals: int) -> Decimal:
    if isinstance(size_decimals, bool) or not isinstance(size_decimals, int):
        raise HyperliquidPerpetualPrecisionError("size_decimals must be an integer")
    if not 0 <= size_decimals <= PERPETUAL_MAXIMUM_DECIMALS:
        raise HyperliquidPerpetualPrecisionError("size_decimals is outside the perpetual range")
    return Decimal(1).scaleb(-size_decimals)


def price_step(*, price: Decimal, size_decimals: int) -> Decimal:
    """Return the strictest local step implied by the documented px rules.

    Integer prices remain permitted regardless of significant figures. Below
    five integer digits, the five-significant-figure rule and the perpetual
    decimal cap are both applied.
    """
    _exact_positive(price, "price")
    quantity_step(size_decimals=size_decimals)
    adjusted = price.adjusted()
    if adjusted >= MAXIMUM_SIGNIFICANT_FIGURES - 1:
        return Decimal("1")
    significant_step = Decimal(1).scaleb(adjusted - (MAXIMUM_SIGNIFICANT_FIGURES - 1))
    decimal_cap_step = Decimal(1).scaleb(-(PERPETUAL_MAXIMUM_DECIMALS - size_decimals))
    return max(significant_step, decimal_cap_step)


def is_valid_price(*, price: Decimal, size_decimals: int) -> bool:
    try:
        step = price_step(price=price, size_decimals=size_decimals)
    except HyperliquidPerpetualPrecisionError:
        return False
    return price % step == 0


def is_valid_quantity(*, quantity: Decimal, size_decimals: int) -> bool:
    try:
        _exact_positive(quantity, "quantity")
        step = quantity_step(size_decimals=size_decimals)
    except HyperliquidPerpetualPrecisionError:
        return False
    return quantity % step == 0


@dataclass(frozen=True, slots=True)
class HyperliquidBTCPerpetualPrecisionV1:
    size_decimals: int
    quantity_step: Decimal
    source_evidence_ids: tuple[str, ...]
    precision_id: str
    trading_authority: bool = False

    def __post_init__(self):
        expected_step = quantity_step(size_decimals=self.size_decimals)
        if self.quantity_step != expected_step:
            raise HyperliquidPerpetualPrecisionError("quantity step conflicts with size decimals")
        if (not self.source_evidence_ids
                or any(not isinstance(item, str) or len(item) != 64
                       or any(char not in "0123456789abcdef" for char in item)
                       for item in self.source_evidence_ids)
                or len(set(self.source_evidence_ids)) != len(self.source_evidence_ids)):
            raise HyperliquidPerpetualPrecisionError("immutable source evidence is required")
        if self.trading_authority is not False:
            raise HyperliquidPerpetualPrecisionError("precision evidence cannot grant authority")
        body = {"version": VERSION, "market": "BTC-PERP", "size_decimals": self.size_decimals,
            "quantity_step": format(self.quantity_step, "f"),
            "source_evidence_ids": list(self.source_evidence_ids), "trading_authority": False}
        expected = hashlib.sha256(json.dumps(body, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        if self.precision_id != expected:
            raise HyperliquidPerpetualPrecisionError("precision identity mismatch")

    @classmethod
    def create(cls, *, size_decimals: int,
               source_evidence_ids: tuple[str, ...]):
        step = quantity_step(size_decimals=size_decimals)
        body = {"version": VERSION, "market": "BTC-PERP", "size_decimals": size_decimals,
            "quantity_step": format(step, "f"),
            "source_evidence_ids": list(source_evidence_ids), "trading_authority": False}
        identity = hashlib.sha256(json.dumps(body, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        return cls(size_decimals, step, source_evidence_ids, identity, False)

    def validate_order_geometry(self, *, entry: Decimal, stop: Decimal,
                                target: Decimal, quantity: Decimal) -> None:
        if not all(is_valid_price(price=value, size_decimals=self.size_decimals)
                   for value in (entry, stop, target)):
            raise HyperliquidPerpetualPrecisionError("price violates perpetual precision")
        if not is_valid_quantity(quantity=quantity, size_decimals=self.size_decimals):
            raise HyperliquidPerpetualPrecisionError("quantity violates perpetual precision")
