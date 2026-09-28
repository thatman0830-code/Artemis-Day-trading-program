from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from execution.hyperliquid_perpetual_precision_v1 import (
    HyperliquidBTCPerpetualPrecisionV1, HyperliquidPerpetualPrecisionError,
    is_valid_price, is_valid_quantity, price_step, quantity_step,
)


EVIDENCE = ("a" * 64, "b" * 64)


def test_btc_size_decimals_produce_exact_quantity_step():
    precision = HyperliquidBTCPerpetualPrecisionV1.create(
        size_decimals=5, source_evidence_ids=EVIDENCE)
    assert precision.quantity_step == Decimal("0.00001")
    assert quantity_step(size_decimals=5) == Decimal("0.00001")
    assert is_valid_quantity(quantity=Decimal("0.00001"), size_decimals=5)
    assert not is_valid_quantity(quantity=Decimal("0.000001"), size_decimals=5)
    assert precision.trading_authority is False


@pytest.mark.parametrize("price,step,valid", [
    ("123456", "1", True), ("12345.6", "1", False),
    ("1234.5", "0.1", True), ("1234.56", "0.1", False),
    ("12.3", "0.1", True), ("12.34", "0.1", False),
])
def test_dynamic_perpetual_price_precision(price, step, valid):
    value = Decimal(price)
    assert price_step(price=value, size_decimals=5) == Decimal(step)
    assert is_valid_price(price=value, size_decimals=5) is valid


def test_geometry_validation_is_fail_closed():
    precision = HyperliquidBTCPerpetualPrecisionV1.create(
        size_decimals=5, source_evidence_ids=EVIDENCE)
    precision.validate_order_geometry(entry=Decimal("123456"), stop=Decimal("123400"),
        target=Decimal("124000"), quantity=Decimal("0.00001"))
    with pytest.raises(HyperliquidPerpetualPrecisionError, match="price"):
        precision.validate_order_geometry(entry=Decimal("12345.6"), stop=Decimal("12300"),
            target=Decimal("12400"), quantity=Decimal("0.00001"))
    with pytest.raises(HyperliquidPerpetualPrecisionError, match="quantity"):
        precision.validate_order_geometry(entry=Decimal("12345"), stop=Decimal("12300"),
            target=Decimal("12400"), quantity=Decimal("0.000001"))


def test_precision_record_is_immutable_content_addressed_and_evidence_bound():
    value = HyperliquidBTCPerpetualPrecisionV1.create(
        size_decimals=5, source_evidence_ids=EVIDENCE)
    assert value == HyperliquidBTCPerpetualPrecisionV1.create(
        size_decimals=5, source_evidence_ids=EVIDENCE)
    with pytest.raises(FrozenInstanceError): value.size_decimals = 4
    with pytest.raises(HyperliquidPerpetualPrecisionError, match="identity"):
        replace(value, precision_id="c" * 64)
    with pytest.raises(HyperliquidPerpetualPrecisionError, match="evidence"):
        HyperliquidBTCPerpetualPrecisionV1.create(size_decimals=5,
                                                  source_evidence_ids=())


@pytest.mark.parametrize("value", [-1, 7, True, "5"])
def test_invalid_size_decimal_configuration_rejects(value):
    with pytest.raises(HyperliquidPerpetualPrecisionError):
        quantity_step(size_decimals=value)
