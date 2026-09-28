from datetime import datetime,timedelta,timezone
from decimal import Decimal
import json,pytest
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket as M
from backtesting.ninjatrader_shadow_profile_comparison_v1 import CompletedShadowTradeV1,ShadowSide
from backtesting.ninjatrader_completed_trade_history_v1 import *
T=datetime(2026,9,8,tzinfo=timezone.utc)
def trade(i=0):return CompletedShadowTradeV1(str(i)*64,M.ES if i%2==0 else M.NQ,ShadowSide.LONG,T+timedelta(minutes=i),T+timedelta(minutes=i+1),Decimal("100"),Decimal("99"),Decimal("102"),"a"*64)
def test_append_is_hash_chained_idempotent_and_comparison_ready(tmp_path):
 assert append_completed_shadow_trade(tmp_path,trade=trade())==trade();assert append_completed_shadow_trade(tmp_path,trade=trade())==trade();append_completed_shadow_trade(tmp_path,trade=trade(1));assert read_completed_shadow_trade_history(tmp_path)==(trade(),trade(1))
def test_tamper_and_signal_conflict_reject(tmp_path):
 append_completed_shadow_trade(tmp_path,trade=trade());path=tmp_path/"events"/"00000000000000000000.json";doc=json.loads(path.read_text());doc["trade"]["exit_price"]="500";path.write_text(json.dumps(doc))
 with pytest.raises(ValueError,match="chain"):read_completed_shadow_trade_history(tmp_path)
 clean=tmp_path/"clean";append_completed_shadow_trade(clean,trade=trade())
 from dataclasses import replace
 with pytest.raises(ValueError,match="conflict"):append_completed_shadow_trade(clean,trade=replace(trade(),exit_price=Decimal("101")))
def test_no_execution_surface():
 source=__import__('pathlib').Path(__file__).with_name('ninjatrader_completed_trade_history_v1.py').read_text();assert'from execution'not in source
 for word in('SubmitOrder','CreateOrder','trading_authority":True'):assert word not in source
