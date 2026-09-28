from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from execution.futures_micro_paper_policy_proposal_v1 import (
    FuturesMicroPaperPolicyProposalError,
    create_conservative_micro_futures_policy_proposal,
)
from execution.futures_micro_paper_scope_v1 import create_recommended_micro_futures_scope


def test_proposal_records_verified_costs_and_conservative_limits():
    value = create_conservative_micro_futures_policy_proposal(
        scope=create_recommended_micro_futures_scope(), reviewed_as_of=date(2026, 9, 6))
    assert value.ibkr_commission_per_contract_per_side == Decimal("0.25")
    assert value.exchange_and_regulatory_fees_per_contract_per_side == Decimal("0.35")
    assert value.total_fees_per_contract_per_side == Decimal("0.60")
    assert value.proposed_slippage_ticks_per_fill == Decimal("2")
    assert value.proposed_maximum_contracts == 1
    assert value.proposed_maximum_margin_utilization_percent == Decimal("25")
    assert value.proposed_maximum_session_loss_usd == Decimal("250")
    assert value.proposed_maximum_session_drawdown_usd == Decimal("250")
    assert value.proposed_regular_session_only and not value.proposed_hold_overnight
    assert value.live_broker_margin_check_required


def test_web_review_is_not_durable_evidence_or_trading_authority():
    value = create_conservative_micro_futures_policy_proposal(
        scope=create_recommended_micro_futures_scope(), reviewed_as_of=date(2026, 9, 6))
    assert not value.durable_runtime_evidence_complete
    assert not value.owner_approved
    assert not value.paper_execution_permitted
    assert not value.live_trading_permitted
    assert not value.trading_authority
    assert len(value.official_source_urls) == 3


def test_proposal_is_deterministic_and_rejects_unsafe_scope():
    scope = create_recommended_micro_futures_scope()
    first = create_conservative_micro_futures_policy_proposal(
        scope=scope, reviewed_as_of=date(2026, 9, 6))
    second = create_conservative_micro_futures_policy_proposal(
        scope=scope, reviewed_as_of=date(2026, 9, 6))
    assert first == second
    with pytest.raises(FuturesMicroPaperPolicyProposalError):
        create_conservative_micro_futures_policy_proposal(
            scope=replace(scope, paper_execution_permitted=True),
            reviewed_as_of=date(2026, 9, 6))
    with pytest.raises(TypeError):
        create_conservative_micro_futures_policy_proposal(scope=scope, reviewed_as_of="2026-09-06")
