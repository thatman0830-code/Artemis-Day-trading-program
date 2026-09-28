from decimal import Decimal

import pytest

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.futures_micro_paper_scope_v1 import (
    FuturesMicroPaperScopeError, FuturesPaperBroker, VerifiedMicroContractV1,
    create_recommended_micro_futures_scope,
)


def test_recommended_scope_is_conservative_and_non_authoritative():
    scope = create_recommended_micro_futures_scope()
    assert scope.broker is FuturesPaperBroker.IBKR_PAPER
    assert scope.starting_equity == Decimal("50000")
    assert scope.max_concurrent_futures_positions == 1
    assert scope.shared_futures_portfolio and scope.btc_venue_unchanged
    assert scope.owner_direction_recorded and not scope.economics_complete
    assert scope.advisory_only
    assert scope.paper_execution_permitted is False
    assert scope.live_trading_permitted is False
    assert scope.trading_authority is False


def test_es_and_nq_map_only_to_micro_products_with_exact_terms():
    scope = create_recommended_micro_futures_scope()
    es, nq = scope.mapping_for(FuturesCanonicalMarket.ES), scope.mapping_for(FuturesCanonicalMarket.NQ)
    assert (es.execution_root, es.point_value, es.minimum_price_increment, es.tick_value) == (
        "MES", Decimal("5"), Decimal("0.25"), Decimal("1.25"))
    assert (nq.execution_root, nq.point_value, nq.minimum_price_increment, nq.tick_value) == (
        "MNQ", Decimal("2"), Decimal("0.25"), Decimal("0.50"))


@pytest.mark.parametrize("contract", [
    VerifiedMicroContractV1(FuturesCanonicalMarket.ES, "MESZ26", "202612", 123),
    VerifiedMicroContractV1(FuturesCanonicalMarket.NQ, "MNQH7", "202703", 456),
])
def test_exact_dated_ibkr_micro_contracts_validate(contract):
    scope = create_recommended_micro_futures_scope()
    assert scope.verify_contract(contract).research_market is contract.research_market


@pytest.mark.parametrize("symbol,expiry,contract_id", [
    ("MNQ1!", "202612", 1), ("NQZ26", "202612", 1),
    ("MNQM26", "202612", 1), ("MNQZ26", "202609", 1),
    ("MNQZ26", "202612", 0), ("MNQZ26", "202612", True),
])
def test_continuous_wrong_or_unresolved_contracts_fail_closed(symbol, expiry, contract_id):
    scope = create_recommended_micro_futures_scope()
    contract = VerifiedMicroContractV1(FuturesCanonicalMarket.NQ, symbol, expiry, contract_id)
    with pytest.raises(FuturesMicroPaperScopeError):
        scope.verify_contract(contract)


def test_owner_equity_is_exact_and_identity_is_deterministic():
    assert create_recommended_micro_futures_scope().scope_id == create_recommended_micro_futures_scope().scope_id
    with pytest.raises(TypeError):
        create_recommended_micro_futures_scope(starting_equity=50000)
    with pytest.raises(FuturesMicroPaperScopeError):
        create_recommended_micro_futures_scope(starting_equity=Decimal("50001"))
    with pytest.raises(TypeError):
        create_recommended_micro_futures_scope().mapping_for("NQ")
