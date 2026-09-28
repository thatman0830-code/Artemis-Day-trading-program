from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.futures_micro_paper_scope_v1 import *
from execution.futures_micro_runtime_evidence_gates_v1 import *
NOW=datetime(2026,9,7,tzinfo=timezone.utc);C=VerifiedMicroContractV1(FuturesCanonicalMarket.NQ,"MNQU6","202609",793356225)
def q():return MicroLiveQuoteEvidenceV1("IBKR",C,NOW,Decimal("25000"),Decimal("25000.25"),MarketDataType.LIVE,True,True)
def m():return MicroMarginPreviewEvidenceV1(C,NOW,NOW,1,Decimal("3000"),Decimal("3200"),Decimal("2700"),Decimal("2900"),"IBKR_TWS_ORDER_PREVIEW","a"*64,"b"*64,True,False)
def test_complete_exact_runtime_evidence_is_review_ready_not_trade_authority():
 r=evaluate_runtime_evidence(scope=create_recommended_micro_futures_scope(),contract=C,quote=q(),margin=m(),as_of=NOW)
 assert r.ready_for_policy_review and r.conservative_initial_margin_usd==Decimal("3200")and r.conservative_maintenance_margin_usd==Decimal("2900")
 assert r.paper_execution_permitted is False and r.live_trading_permitted is False and r.trading_authority is False
@pytest.mark.parametrize("quote,blocker",[(replace(q(),data_type=MarketDataType.DELAYED),"QUOTE_NOT_LIVE"),(replace(q(),captured_at=NOW-timedelta(seconds=2)),"QUOTE_STALE"),(replace(q(),entitlement_confirmed=False),"QUOTE_ENTITLEMENT_INVALID"),(replace(q(),ask=Decimal("24999")),"QUOTE_CROSSED")])
def test_delayed_stale_unentitled_or_crossed_quote_blocks(quote,blocker):
 r=evaluate_runtime_evidence(scope=create_recommended_micro_futures_scope(),contract=C,quote=quote,margin=m(),as_of=NOW);assert blocker in r.blockers and not r.ready_for_policy_review
@pytest.mark.parametrize("margin,blocker",[(replace(m(),transmitted=True),"MARGIN_SOURCE_OR_TRANSMISSION_INVALID"),(replace(m(),quantity=True),"MARGIN_QUANTITY_INVALID"),(replace(m(),long_captured_at=NOW-timedelta(minutes=16)),"MARGIN_STALE"),(replace(m(),short_screenshot_sha256="bad"),"MARGIN_SCREENSHOT_INVALID"),(replace(m(),long_initial_margin_usd=Decimal("13000")),"MARGIN_LIMIT_INVALID")])
def test_unsafe_or_unverifiable_margin_evidence_blocks(margin,blocker):
 r=evaluate_runtime_evidence(scope=create_recommended_micro_futures_scope(),contract=C,quote=q(),margin=margin,as_of=NOW);assert blocker in r.blockers and not r.ready_for_policy_review
def test_full_size_or_continuous_contract_cannot_bridge_micro_gate():
 bad=replace(C,local_symbol="NQU6");r=evaluate_runtime_evidence(scope=create_recommended_micro_futures_scope(),contract=bad,quote=replace(q(),contract=bad),margin=replace(m(),contract=bad),as_of=NOW);assert "CONTRACT_INVALID"in r.blockers
