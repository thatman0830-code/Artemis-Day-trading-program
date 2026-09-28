"""Identical-signal, cost-aware comparison of three non-executable risk profiles."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal,ROUND_FLOOR
from enum import Enum
import hashlib,json
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_micro_instrument_specs_v1 import verified_micro_instrument_specifications
from backtesting.ninjatrader_micro_paper_policy_proposal_v1 import RiskProfile,micro_paper_policy_proposals,verify_micro_paper_policy_proposals
VERSION="ninjatrader-shadow-profile-comparison-v1"
class ShadowSide(str,Enum):LONG="LONG";SHORT="SHORT"
class SelectionState(str,Enum):INSUFFICIENT_SAMPLE="INSUFFICIENT_SAMPLE";NO_POSITIVE_PROFILE="NO_POSITIVE_PROFILE";CANDIDATE="CANDIDATE"
@dataclass(frozen=True)
class CompletedShadowTradeV1:
 signal_id:str;market:FuturesCanonicalMarket;side:ShadowSide;entry_time:datetime;exit_time:datetime;entry_price:Decimal;stop_price:Decimal;exit_price:Decimal;source_report_id:str;trading_authority:bool=False
@dataclass(frozen=True)
class ShadowProfileMetricsV1:
 profile:RiskProfile;trade_count:int;mes_trade_count:int;mnq_trade_count:int;gross_pnl_usd:Decimal;fees_usd:Decimal;slippage_usd:Decimal;net_pnl_usd:Decimal;net_expectancy_usd:Decimal;win_rate:Decimal;maximum_drawdown_usd:Decimal;worst_trade_usd:Decimal;profit_factor:Decimal|None
@dataclass(frozen=True)
class ShadowProfileComparisonV1:
 comparison_id:str;evaluated_at:datetime;input_trade_count:int;selection_state:SelectionState;candidate_profile:RiskProfile|None;minimum_total_trades:int;minimum_trades_per_market:int;metrics:tuple[ShadowProfileMetricsV1,...];identical_signal_set_verified:bool=True;comparison_only:bool=True;paper_execution_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def _trade_pnl(trade,policy,spec):
 risk_per_contract=abs(trade.entry_price-trade.stop_price)*spec.contract_multiplier
 if risk_per_contract<=0:raise ValueError("positive stop distance required")
 quantity=min(policy.maximum_contracts_total,int((policy.maximum_initial_risk_usd/risk_per_contract).to_integral_value(rounding=ROUND_FLOOR)))
 if quantity<1:return None
 points=(trade.exit_price-trade.entry_price)*(Decimal(1)if trade.side is ShadowSide.LONG else Decimal(-1));gross=points*spec.contract_multiplier*quantity;fees=policy.modeled_fee_per_contract_per_side_usd*2*quantity;slippage=spec.tick_value*policy.modeled_slippage_ticks_per_fill*2*quantity;return gross,fees,slippage,gross-fees-slippage
def compare_shadow_profiles(*,trades,evaluated_at,minimum_total_trades=30,minimum_trades_per_market=10):
 if not isinstance(trades,tuple)or len({x.signal_id for x in trades})!=len(trades):raise ValueError("unique immutable shadow trades required")
 if not isinstance(evaluated_at,datetime)or evaluated_at.tzinfo is None or evaluated_at.utcoffset()!=timedelta(0):raise ValueError("UTC evaluation time required")
 if any(not isinstance(x,CompletedShadowTradeV1)or x.trading_authority is not False or x.entry_time.tzinfo is None or x.entry_time.utcoffset()!=timedelta(0)or x.exit_time<=x.entry_time or x.exit_time>evaluated_at for x in trades):raise ValueError("invalid completed shadow trade")
 specs={x.market:x for x in verified_micro_instrument_specifications()};policies=verify_micro_paper_policy_proposals(micro_paper_policy_proposals());results=[]
 for policy in policies:
  pnls=[];gross=fees=slippage=Decimal(0)
  for trade in trades:
   value=_trade_pnl(trade,policy,specs[trade.market])
   if value is None:continue
   g,f,s,n=value;gross+=g;fees+=f;slippage+=s;pnls.append(n)
  equity=peak=drawdown=Decimal(0)
  for pnl in pnls:equity+=pnl;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
  wins=sum(x>0 for x in pnls);positive=sum((x for x in pnls if x>0),Decimal(0));negative=-sum((x for x in pnls if x<0),Decimal(0));count=len(pnls)
  results.append(ShadowProfileMetricsV1(policy.profile,count,sum(x.market is FuturesCanonicalMarket.ES for x in trades),sum(x.market is FuturesCanonicalMarket.NQ for x in trades),gross,fees,slippage,sum(pnls,Decimal(0)),sum(pnls,Decimal(0))/count if count else Decimal(0),Decimal(wins)/count if count else Decimal(0),drawdown,min(pnls)if pnls else Decimal(0),positive/negative if negative else None))
 enough=bool(trades)and len(trades)>=minimum_total_trades and all(sum(x.market is m for x in trades)>=minimum_trades_per_market for m in FuturesCanonicalMarket)
 positive=[x for x in results if x.net_expectancy_usd>0]
 state=SelectionState.INSUFFICIENT_SAMPLE if not enough else SelectionState.NO_POSITIVE_PROFILE if not positive else SelectionState.CANDIDATE
 candidate=max(positive,key=lambda x:(x.net_expectancy_usd/(x.maximum_drawdown_usd or Decimal(1)),x.net_pnl_usd,-list(RiskProfile).index(x.profile))).profile if state is SelectionState.CANDIDATE else None
 body={"version":VERSION,"at":evaluated_at.isoformat(),"signals":[x.signal_id for x in trades],"state":state.value,"candidate":None if candidate is None else candidate.value,"metrics":[str(x)for x in results],"authority":False};identity=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 return ShadowProfileComparisonV1(identity,evaluated_at,len(trades),state,candidate,minimum_total_trades,minimum_trades_per_market,tuple(results))
