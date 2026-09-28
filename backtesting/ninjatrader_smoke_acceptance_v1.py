"""Immutable review attestation for a completed ES/NQ smoke maturity gate."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
import hashlib,json
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_history_v1 import read_ninjatrader_canonical_smoke_history
from backtesting.ninjatrader_smoke_maturity_gate_v1 import NinjaTraderSmokeMaturityGateV1

VERSION="ninjatrader-smoke-acceptance-v1"
REMAINING_GATES=("VERIFIED_INSTRUMENT_SPECIFICATIONS","PAPER_ECONOMICS_POLICY","PAPER_RISK_POLICY","SESSION_AND_ROLLOVER_POLICY","STOP_CONTROL","ACTIVE_SUPERVISION_AUTHORIZATION")
@dataclass(frozen=True)
class NinjaTraderSmokeAcceptanceV1:
 attestation_id:str;attested_at:datetime;gate_id:str;es_history_head_event_id:str;nq_history_head_event_id:str;es_report_count:int;nq_report_count:int;es_bar_count:int;nq_bar_count:int;es_outcome_counts:tuple[tuple[str,int],...];nq_outcome_counts:tuple[tuple[str,int],...];remaining_gates:tuple[str,...]=REMAINING_GATES
 supervised_paper_design_review_eligible:bool=True;supervised_paper_execution_permitted:bool=False;unattended_paper_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def attest_ninjatrader_smoke_acceptance(*,gate,history_root,attested_at):
 if not isinstance(gate,NinjaTraderSmokeMaturityGateV1)or gate.ready_for_supervised_paper_review is not True or gate.progress_percent!=100 or gate.reasons:raise ValueError("completed smoke maturity gate required")
 if not isinstance(attested_at,datetime)or attested_at.tzinfo is None or attested_at.utcoffset()!=timedelta(0)or attested_at<gate.evaluated_at:raise ValueError("valid UTC attestation time required")
 es=read_ninjatrader_canonical_smoke_history(history_root,market=FuturesCanonicalMarket.ES);nq=read_ninjatrader_canonical_smoke_history(history_root,market=FuturesCanonicalMarket.NQ)
 if(len(es)!=gate.es_report_count or len(nq)!=gate.nq_report_count or es[-1].report_id!=gate.latest_es_report_id or nq[-1].report_id!=gate.latest_nq_report_id or es[-1].report["source_bar_count"]!=gate.es_bar_count or nq[-1].report["source_bar_count"]!=gate.nq_bar_count):raise ValueError("gate and retained histories differ")
 if any(event.report.get("trading_authority")is not False or event.report.get("deterministic_repeat_verified")is not True for event in es+nq):raise ValueError("history contains ineligible report")
 def outcomes(rows):
  values={}
  for event in rows:values[event.latest_outcome]=values.get(event.latest_outcome,0)+1
  return tuple(sorted(values.items()))
 eo,no=outcomes(es),outcomes(nq);body={"version":VERSION,"at":attested_at.isoformat(),"gate":gate.gate_id,"heads":(es[-1].event_id,nq[-1].event_id),"counts":(len(es),len(nq)),"bars":(gate.es_bar_count,gate.nq_bar_count),"outcomes":(eo,no),"remaining":REMAINING_GATES,"authority":False};identity=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 return NinjaTraderSmokeAcceptanceV1(identity,attested_at,gate.gate_id,es[-1].event_id,nq[-1].event_id,len(es),len(nq),gate.es_bar_count,gate.nq_bar_count,eo,no)
