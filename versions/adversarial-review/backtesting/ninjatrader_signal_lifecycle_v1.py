"""Resolve genuine canonical futures signals against verified closed bars only."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal
from enum import Enum
import hashlib,json
from backtesting.market_data import HistoricalCandle
from backtesting.ninjatrader_canonical_smoke_v1 import NinjaTraderCanonicalSmokeV1
from backtesting.ninjatrader_shadow_profile_comparison_v1 import CompletedShadowTradeV1,ShadowSide
VERSION="ninjatrader-signal-lifecycle-v1"
class LifecycleOutcome(str,Enum):NO_SIGNAL="NO_SIGNAL";WAITING_ENTRY="WAITING_ENTRY";OPEN="OPEN";TARGET="TARGET";STOP="STOP";TIME_EXIT="TIME_EXIT"
@dataclass(frozen=True)
class SignalLifecycleResolutionV1:
 resolution_id:str;source_report_id:str;outcome:LifecycleOutcome;entry_bar_id:str|None;exit_bar_id:str|None;completed_trade:CompletedShadowTradeV1|None;bars_examined:int;ambiguous_bar_resolved_stop_first:bool=False;comparison_only:bool=True;paper_execution_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def resolve_signal_lifecycle(*,report,bars,max_holding_bars=30):
 if not isinstance(report,NinjaTraderCanonicalSmokeV1)or report.trading_authority is not False or not isinstance(bars,tuple)or any(not isinstance(x,HistoricalCandle)for x in bars)or max_holding_bars<1:raise ValueError("verified advisory lifecycle inputs required")
 fields=(report.qualified_signal_id,report.signal_side,report.signal_time,report.entry_price,report.stop_price,report.target_price)
 if all(x is None for x in fields):return _resolution(report,LifecycleOutcome.NO_SIGNAL,None,None,None,0,False)
 if any(x is None for x in fields)or report.signal_side not in("LONG","SHORT")or report.signal_time.tzinfo is None or report.signal_time.utcoffset()!=timedelta(0):raise ValueError("complete qualified signal facts required")
 relevant=tuple(x for x in bars if x.open_time>=report.signal_time)
 entry_bar=next((x for x in relevant if x.low<=report.entry_price<=x.high),None)
 if entry_bar is None:return _resolution(report,LifecycleOutcome.WAITING_ENTRY,None,None,None,len(relevant),False)
 after=relevant[relevant.index(entry_bar):relevant.index(entry_bar)+max_holding_bars]
 side=ShadowSide(report.signal_side);stop_first=False;exit_bar=None;exit_price=None;outcome=LifecycleOutcome.OPEN
 for bar in after:
  stop_hit=bar.low<=report.stop_price if side is ShadowSide.LONG else bar.high>=report.stop_price
  target_hit=bar.high>=report.target_price if side is ShadowSide.LONG else bar.low<=report.target_price
  if stop_hit:exit_bar=bar;exit_price=report.stop_price;outcome=LifecycleOutcome.STOP;stop_first=target_hit;break
  if target_hit:exit_bar=bar;exit_price=report.target_price;outcome=LifecycleOutcome.TARGET;break
 if exit_bar is None and len(after)==max_holding_bars:exit_bar=after[-1];exit_price=exit_bar.close;outcome=LifecycleOutcome.TIME_EXIT
 trade=None
 if exit_bar is not None:trade=CompletedShadowTradeV1(report.qualified_signal_id,report.market,side,entry_bar.close_time,exit_bar.close_time if exit_bar.close_time>entry_bar.close_time else entry_bar.close_time+timedelta(microseconds=1),report.entry_price,report.stop_price,exit_price,report.report_id)
 return _resolution(report,outcome,entry_bar,exit_bar,trade,len(relevant),stop_first)
def _resolution(report,outcome,entry,exit,trade,count,ambiguous):
 body={"version":VERSION,"report":report.report_id,"outcome":outcome.value,"entry":None if entry is None else entry.id,"exit":None if exit is None else exit.id,"trade":None if trade is None else trade.signal_id,"count":count,"ambiguous":ambiguous,"authority":False};identity=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest();return SignalLifecycleResolutionV1(identity,report.report_id,outcome,None if entry is None else entry.id,None if exit is None else exit.id,trade,count,ambiguous)
