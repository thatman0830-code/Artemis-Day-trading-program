from datetime import datetime,timedelta,timezone
from decimal import Decimal
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket as M
from backtesting.ninjatrader_shadow_profile_comparison_v1 import *
T=datetime(2026,9,8,tzinfo=timezone.utc)
def trade(i,market=M.ES,win=True):return CompletedShadowTradeV1(str(i)*64,market,ShadowSide.LONG,T+timedelta(minutes=i),T+timedelta(minutes=i+1),Decimal("100"),Decimal("95"),Decimal("110")if win else Decimal("96"),("a"if market is M.ES else"b")*64)
def test_empty_is_insufficient_and_never_selects():
 r=compare_shadow_profiles(trades=(),evaluated_at=T);assert r.selection_state is SelectionState.INSUFFICIENT_SAMPLE and r.candidate_profile is None and all(x.trade_count==0 for x in r.metrics);assert r.paper_execution_permitted is r.trading_authority is False
def test_all_profiles_receive_same_signals_but_scale_costs_and_pnl():
 trades=tuple(trade(i,M.ES if i%2==0 else M.NQ)for i in range(30));r=compare_shadow_profiles(trades=trades,evaluated_at=T+timedelta(hours=1));assert all(x.trade_count==30 for x in r.metrics);assert r.selection_state is SelectionState.CANDIDATE and r.candidate_profile is not None;assert r.metrics[0].fees_usd<r.metrics[1].fees_usd<r.metrics[2].fees_usd
def test_losses_do_not_select_profile():
 trades=tuple(trade(i,M.ES if i%2==0 else M.NQ,False)for i in range(30));r=compare_shadow_profiles(trades=trades,evaluated_at=T+timedelta(hours=1));assert r.selection_state is SelectionState.NO_POSITIVE_PROFILE and r.candidate_profile is None
def test_no_execution_surface():
 source=__import__('pathlib').Path(__file__).with_name('ninjatrader_shadow_profile_comparison_v1.py').read_text();assert'from execution'not in source
 for x in('SubmitOrder','CreateOrder','trading_authority:bool=True'):assert x not in source
