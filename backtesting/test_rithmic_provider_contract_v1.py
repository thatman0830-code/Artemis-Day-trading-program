import pytest

from backtesting.rithmic_provider_contract_v1 import (
    RithmicConnectionConfig,
    RithmicMode,
    RithmicPaperAdapterV1,
    RithmicSessionStatus,
)


def test_rithmic_contract_is_fail_closed_until_all_checks_pass():
    adapter = RithmicPaperAdapterV1(RithmicConnectionConfig(RithmicMode.TEST))
    evidence = adapter.validate()
    assert evidence["paper_ready"] is False
    assert evidence["paper_execution_permitted"] is False
    assert evidence["trading_authority"] is False


def test_rithmic_contract_requires_one_authoritative_es_nq_connection():
    with pytest.raises(ValueError, match="one authoritative"):
        RithmicConnectionConfig(RithmicMode.TEST, single_authoritative_connection=False)
    with pytest.raises(ValueError, match="ES/NQ"):
        RithmicConnectionConfig(RithmicMode.TEST, symbols=("CL", "GC"))


def test_rithmic_paper_ready_requires_data_reconciliation_and_server_risk():
    status = RithmicSessionStatus(
        authenticated=True, subscription_acknowledged=True,
        symbol_mapping_verified=True, heartbeat_fresh=True,
        current_samples=1, positions_reconciled=True,
        working_orders_reconciled=True, server_risk_verified=True,
    )
    assert RithmicPaperAdapterV1(RithmicConnectionConfig(RithmicMode.EXCHANGE_SIMULATOR), status).status.paper_ready is True
