from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.futures_micro_paper_scope_v1 import VerifiedMicroContractV1,create_recommended_micro_futures_scope
from execution.ibkr_micro_paper_preflight_v1 import *

NOW=datetime(2026,9,6,18,tzinfo=timezone.utc)
def snap():return IBKRReadOnlySnapshotV1(NOW,"DU123456",True,True,False,0,0,True,VerifiedMicroContractV1(FuturesCanonicalMarket.NQ,"MNQZ26","202612",777),Decimal("3000"),Decimal("2700"))
def test_healthy_read_only_snapshot_is_ready_only_for_policy_review():
 r=evaluate_ibkr_micro_paper_preflight(scope=create_recommended_micro_futures_scope(),snapshot=snap(),evaluated_at=NOW)
 assert r.ready_for_policy_review and not r.blockers and r.read_only
 assert r.paper_execution_permitted is False and r.live_trading_permitted is False and r.trading_authority is False
 assert r.account_id_fingerprint and "DU123456"not in repr(r)
def test_report_is_deterministic_and_supports_exact_mes_contract():
 scope=create_recommended_micro_futures_scope();mes=replace(snap(),contract=VerifiedMicroContractV1(FuturesCanonicalMarket.ES,"MESZ26","202612",888))
 assert evaluate_ibkr_micro_paper_preflight(scope=scope,snapshot=mes,evaluated_at=NOW)==evaluate_ibkr_micro_paper_preflight(scope=scope,snapshot=mes,evaluated_at=NOW)
@pytest.mark.parametrize("change,blocker",[
 ({"account_id":"U123"},"NOT_IBKR_PAPER_ACCOUNT"),({"connected":False},"GATEWAY_DISCONNECTED"),
 ({"api_read_only":False},"API_NOT_READ_ONLY"),({"order_placement_available":True},"API_NOT_READ_ONLY"),
 ({"open_order_count":1},"OPEN_ORDERS_PRESENT_OR_INVALID"),({"futures_position_count":1},"FUTURES_POSITIONS_PRESENT_OR_INVALID"),
 ({"market_data_live":False},"LIVE_MARKET_DATA_UNAVAILABLE"),({"captured_at":NOW-timedelta(seconds=6)},"SNAPSHOT_NOT_CURRENT"),
 ({"initial_margin_usd":Decimal("13000")},"MARGIN_UTILIZATION_EXCEEDS_PROPOSAL"),
 ({"maintenance_margin_usd":Decimal("3100")},"MARGIN_VALUES_INVALID")])
def test_unsafe_account_contract_market_or_margin_fails_closed(change,blocker):
 r=evaluate_ibkr_micro_paper_preflight(scope=create_recommended_micro_futures_scope(),snapshot=replace(snap(),**change),evaluated_at=NOW)
 assert not r.ready_for_policy_review and blocker in r.blockers
def test_continuous_contract_and_float_margin_reject():
 bad=replace(snap(),contract=replace(snap().contract,local_symbol="MNQ1!"),initial_margin_usd=3000.0)
 r=evaluate_ibkr_micro_paper_preflight(scope=create_recommended_micro_futures_scope(),snapshot=bad,evaluated_at=NOW)
 assert set(("CONTRACT_IDENTITY_INVALID","MARGIN_VALUES_INVALID")).issubset(r.blockers)
def test_bool_spoofing_and_untyped_contract_fail_closed():
 bad=replace(snap(),connected=1,api_read_only=1,order_placement_available=0,market_data_live=1,contract="MNQZ26")
 r=evaluate_ibkr_micro_paper_preflight(scope=create_recommended_micro_futures_scope(),snapshot=bad,evaluated_at=NOW)
 assert not r.ready_for_policy_review
 assert {"GATEWAY_DISCONNECTED","API_NOT_READ_ONLY","LIVE_MARKET_DATA_UNAVAILABLE","CONTRACT_IDENTITY_INVALID"}.issubset(r.blockers)
def test_ibkr_simulated_dut_account_identifier_is_accepted():
 r=evaluate_ibkr_micro_paper_preflight(scope=create_recommended_micro_futures_scope(),snapshot=replace(snap(),account_id="DUT096651"),evaluated_at=NOW)
 assert r.ready_for_policy_review
