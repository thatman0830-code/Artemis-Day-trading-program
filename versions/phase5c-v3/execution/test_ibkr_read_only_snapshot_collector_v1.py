from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal
import json,pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.futures_micro_paper_scope_v1 import create_recommended_micro_futures_scope
from execution.ibkr_read_only_snapshot_collector_v1 import *
NOW=datetime(2026,9,6,18,tzinfo=timezone.utc)
class Transport:
 def __init__(self,mutate=None):self.mutate=mutate or {}
 def capture_read_only(self,**kwargs):
  assert kwargs=={"host":"127.0.0.1","port":7497,"client_id":71,"timeout_seconds":10,"market":FuturesCanonicalMarket.NQ}
  return {"captured_at":NOW,"account_id":"DU123456","connected":True,"api_read_only":True,"order_placement_available":False,"open_order_count":0,"futures_position_count":0,"market_data_type":1,"market_data_live":True,"bid":"25000","ask":"25000.25","local_symbol":"MNQZ26","expiry_yyyymm":"202612","ibkr_contract_id":777,"initial_margin_usd":"3000","maintenance_margin_usd":"2700",**self.mutate}
def test_collects_sanitized_durable_read_only_receipt(tmp_path):
 result=collect(scope=create_recommended_micro_futures_scope(),request=IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ),transport=Transport(),evaluated_at=NOW,output_root=tmp_path)
 assert result["ready_for_policy_review"]and result["raw_account_id_retained"]is False
 assert result["paper_execution_permitted"]is False and result["trading_authority"]is False
 assert "DU123456"not in json.dumps(result)and len(list(tmp_path.glob("*.json")))==1
 assert collect(scope=create_recommended_micro_futures_scope(),request=IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ),transport=Transport(),evaluated_at=NOW,output_root=tmp_path)==result
def test_unhealthy_capture_is_retained_as_blocked_evidence(tmp_path):
 result=collect(scope=create_recommended_micro_futures_scope(),request=IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ),transport=Transport({"market_data_live":False}),evaluated_at=NOW,output_root=tmp_path)
 assert not result["ready_for_policy_review"]and result["blockers"]==["LIVE_MARKET_DATA_UNAVAILABLE"]
@pytest.mark.parametrize("values",[{"host":"localhost"},{"port":7496},{"client_id":True},{"timeout_seconds":30}])
def test_request_cannot_escape_local_paper_boundary(values):
 with pytest.raises(IBKRReadOnlyCollectorError):IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ,**values)
def test_schema_transport_and_output_fail_closed(tmp_path):
 with pytest.raises(IBKRReadOnlyCollectorError,match="schema"):collect(scope=create_recommended_micro_futures_scope(),request=IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ),transport=Transport({"extra":1}),evaluated_at=NOW,output_root=tmp_path)
 class Broken:
  def capture_read_only(self,**kwargs):raise OSError("down")
 with pytest.raises(IBKRReadOnlyCollectorError,match="capture failed"):collect(scope=create_recommended_micro_futures_scope(),request=IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ),transport=Broken(),evaluated_at=NOW,output_root=tmp_path)
 with pytest.raises(IBKRReadOnlyCollectorError,match="output root"):collect(scope=create_recommended_micro_futures_scope(),request=IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ),transport=Transport(),evaluated_at=NOW,output_root=tmp_path/"missing")
def test_real_time_ordering_uses_post_capture_evaluation_clock(tmp_path):
 result=collect(scope=create_recommended_micro_futures_scope(),request=IBKRReadOnlyRequestV1(FuturesCanonicalMarket.NQ),transport=Transport(),evaluated_at=None,clock=lambda:NOW,output_root=tmp_path)
 assert result["ready_for_policy_review"]
