"""Unapproved MES/MNQ paper economics and risk proposal.

Official web facts are useful for owner review but are not durable runtime
evidence.  This proposal therefore never grants paper or live authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json

from execution.futures_micro_paper_scope_v1 import FuturesMicroPaperScopeV1


VERSION = "futures-micro-paper-policy-proposal-v1"
IBKR_COMMISSION_URL = "https://www.interactivebrokers.com/en/pricing/commissions-futures.php"
IBKR_CME_FEES_URL = "https://www.interactivebrokers.com/en/accounts/fees/CME.php"
IBKR_MARGIN_URL = "https://www.interactivebrokers.com/en/trading/margin-futures-fops.php"


class FuturesMicroPaperPolicyProposalError(RuntimeError):
    pass


@dataclass(frozen=True)
class FuturesMicroPaperPolicyProposalV1:
    proposal_id: str
    scope_id: str
    reviewed_as_of: date
    ibkr_commission_per_contract_per_side: Decimal
    exchange_and_regulatory_fees_per_contract_per_side: Decimal
    total_fees_per_contract_per_side: Decimal
    proposed_slippage_ticks_per_fill: Decimal
    proposed_maximum_contracts: int
    proposed_maximum_margin_utilization_percent: Decimal
    proposed_maximum_session_loss_usd: Decimal
    proposed_maximum_session_drawdown_usd: Decimal
    proposed_hold_overnight: bool
    proposed_regular_session_only: bool
    live_broker_margin_check_required: bool
    official_source_urls: tuple[str, ...]
    durable_runtime_evidence_complete: bool = False
    owner_approved: bool = False
    paper_execution_permitted: bool = False
    live_trading_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def create_conservative_micro_futures_policy_proposal(
    *, scope: FuturesMicroPaperScopeV1, reviewed_as_of: date,
) -> FuturesMicroPaperPolicyProposalV1:
    if not isinstance(scope, FuturesMicroPaperScopeV1):
        raise TypeError("typed micro-futures scope required")
    if not isinstance(reviewed_as_of, date):
        raise TypeError("evidence review date required")
    if scope.paper_execution_permitted or scope.live_trading_permitted or scope.trading_authority:
        raise FuturesMicroPaperPolicyProposalError("scope improperly grants trading authority")
    commission, passed_through = Decimal("0.25"), Decimal("0.35")
    values = {
        "version": VERSION, "scope_id": scope.scope_id,
        "reviewed_as_of": reviewed_as_of.isoformat(),
        "commission_per_contract_per_side": str(commission),
        "exchange_and_regulatory_fees_per_contract_per_side": str(passed_through),
        "total_fees_per_contract_per_side": str(commission + passed_through),
        "proposed_slippage_ticks_per_fill": "2",
        "proposed_maximum_contracts": 1,
        "proposed_maximum_margin_utilization_percent": "25",
        "proposed_maximum_session_loss_usd": "250",
        "proposed_maximum_session_drawdown_usd": "250",
        "proposed_hold_overnight": False, "proposed_regular_session_only": True,
        "live_broker_margin_check_required": True,
        "official_source_urls": [IBKR_COMMISSION_URL, IBKR_CME_FEES_URL, IBKR_MARGIN_URL],
    }
    proposal_id = hashlib.sha256(json.dumps(values, sort_keys=True,
        separators=(",", ":")).encode("ascii")).hexdigest()
    return FuturesMicroPaperPolicyProposalV1(
        proposal_id, scope.scope_id, reviewed_as_of, commission, passed_through,
        commission + passed_through, Decimal("2"), 1, Decimal("25"),
        Decimal("250"), Decimal("250"), False, True, True,
        (IBKR_COMMISSION_URL, IBKR_CME_FEES_URL, IBKR_MARGIN_URL),
    )
