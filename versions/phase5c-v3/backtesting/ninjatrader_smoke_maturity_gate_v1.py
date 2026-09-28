"""Fail-closed maturity gate over retained ES/NQ canonical smoke evidence."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from enum import Enum
import hashlib,json

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.ninjatrader_canonical_smoke_history_v1 import read_ninjatrader_canonical_smoke_history

VERSION="ninjatrader-smoke-maturity-gate-v1"
class MaturityReason(str,Enum):
 INSUFFICIENT_REPORTS="INSUFFICIENT_REPORTS";INSUFFICIENT_BARS="INSUFFICIENT_BARS";INSUFFICIENT_SPAN="INSUFFICIENT_SPAN";TASK_STATUS_STALE="TASK_STATUS_STALE";TASK_STATUS_UNBOUND="TASK_STATUS_UNBOUND"
@dataclass(frozen=True)
class NinjaTraderSmokeMaturityPolicyV1:
 minimum_reports_per_market:int=24;minimum_bars_per_market:int=120;minimum_observation_span:timedelta=timedelta(minutes=90);maximum_task_status_age:timedelta=timedelta(minutes=10);schema_version:str="ninjatrader-smoke-maturity-policy-v1"
@dataclass(frozen=True)
class NinjaTraderSmokeMaturityGateV1:
 gate_id:str;evaluated_at:datetime;ready_for_supervised_paper_review:bool;progress_percent:int;reasons:tuple[MaturityReason,...];es_report_count:int;nq_report_count:int;es_bar_count:int;nq_bar_count:int;es_span_seconds:int;nq_span_seconds:int;latest_es_report_id:str;latest_nq_report_id:str;task_status_observed_at:datetime
 advisory_only:bool=True;paper_execution_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def evaluate_ninjatrader_smoke_maturity(*,history_root,task_status,as_of,policy=NinjaTraderSmokeMaturityPolicyV1()):
 if not isinstance(as_of,datetime)or as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0):raise ValueError("UTC as_of required")
 if not isinstance(policy,NinjaTraderSmokeMaturityPolicyV1)or policy.minimum_reports_per_market<2 or policy.minimum_bars_per_market<1 or policy.minimum_observation_span<=timedelta(0)or policy.maximum_task_status_age<=timedelta(0):raise ValueError("valid maturity policy required")
 histories={m:read_ninjatrader_canonical_smoke_history(history_root,market=m)for m in FuturesCanonicalMarket}
 if any(not rows for rows in histories.values()):raise ValueError("both ES and NQ histories are required")
 es,nq=histories[FuturesCanonicalMarket.ES],histories[FuturesCanonicalMarket.NQ]
 try:status_at=datetime.fromisoformat(task_status["observed_at"].replace("Z","+00:00"));reports={row["market"]:row for row in task_status["reports"]}
 except (KeyError,TypeError,ValueError)as exc:raise ValueError("task status schema invalid")from exc
 reasons=[]
 if(task_status.get("state")!="COMPLETE"or task_status.get("trading_authority")is not False or status_at>as_of or as_of-status_at>policy.maximum_task_status_age):reasons.append(MaturityReason.TASK_STATUS_STALE)
 if(set(reports)!={"ES","NQ"}or reports["ES"].get("report_id")!=es[-1].report_id or reports["NQ"].get("report_id")!=nq[-1].report_id or any(row.get("trading_authority")is not False or row.get("deterministic_repeat_verified")is not True for row in reports.values())):reasons.append(MaturityReason.TASK_STATUS_UNBOUND)
 counts=(len(es),len(nq));bars=(es[-1].report["source_bar_count"],nq[-1].report["source_bar_count"]);spans=(int((es[-1].evaluated_at-es[0].evaluated_at).total_seconds()),int((nq[-1].evaluated_at-nq[0].evaluated_at).total_seconds()))
 if min(counts)<policy.minimum_reports_per_market:reasons.append(MaturityReason.INSUFFICIENT_REPORTS)
 if min(bars)<policy.minimum_bars_per_market:reasons.append(MaturityReason.INSUFFICIENT_BARS)
 if min(spans)<int(policy.minimum_observation_span.total_seconds()):reasons.append(MaturityReason.INSUFFICIENT_SPAN)
 ratios=(min(counts)/policy.minimum_reports_per_market,min(bars)/policy.minimum_bars_per_market,min(spans)/policy.minimum_observation_span.total_seconds())
 progress=max(0,min(100,int(min(ratios)*100)))
 body={"version":VERSION,"evaluated_at":as_of.isoformat(),"ready":not reasons,"progress":progress,"reasons":[r.value for r in reasons],"counts":counts,"bars":bars,"spans":spans,"latest":(es[-1].report_id,nq[-1].report_id),"status_at":status_at.isoformat(),"trading_authority":False}
 gate_id=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 return NinjaTraderSmokeMaturityGateV1(gate_id,as_of,not reasons,progress,tuple(reasons),*counts,*bars,*spans,es[-1].report_id,nq[-1].report_id,status_at)
