"""Deterministic, non-executable association of strategy decisions with news context."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime,timedelta
import hashlib,json
from research.forex_factory_shadow_trial_v1 import NewsEventV1,POLICIES,classify_news_context
VERSION="news-decision-diagnostic-v1"
@dataclass(frozen=True)
class DecisionFactV1: decision_id:str;market:str;decided_at:datetime;outcome:str
@dataclass(frozen=True)
class NewsDecisionDiagnosticV1:
 diagnostic_id:str;decision:DecisionFactV1;source_snapshot_id:str;contexts:tuple[dict,...]
 baseline_preserved:bool=True;directional_signal_permitted:bool=False
 order_influence_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def associate(*,decision:DecisionFactV1,events:tuple[NewsEventV1,...],source_snapshot_id:str):
 if decision.market not in{"ES","NQ","BTC-PERP"}or decision.decided_at.tzinfo is None or decision.decided_at.utcoffset()!=timedelta(0):raise ValueError("valid UTC decision required")
 contexts=tuple(asdict(classify_news_context(events=events,as_of=decision.decided_at,policy=p))for p in POLICIES)
 identity=hashlib.sha256(json.dumps((VERSION,decision.decision_id,source_snapshot_id),separators=(",",":")).encode()).hexdigest()
 return NewsDecisionDiagnosticV1(identity,decision,source_snapshot_id,contexts)
def scorecard(*,diagnostics:tuple[NewsDecisionDiagnosticV1,...],trial_days:tuple[str,...],as_of:datetime):
 metrics=[]
 for name in("CONSERVATIVE","MODERATE","AGGRESSIVE"):
  rows=[next(x for x in d.contexts if x["profile"]==name)for d in diagnostics]
  metrics.append({"profile":name,"decision_count":len(rows),"shadow_block_count":sum(x["new_entry_recommendation"]=="SHADOW_BLOCK"for x in rows),"completed_trade_outcomes":sum(d.decision.outcome in{"WIN","LOSS","BREAK_EVEN","STOP"}for d in diagnostics)})
 complete=as_of.date().isoformat()>trial_days[-1]
 return {"schema_version":"forex-factory-five-day-scorecard-v1","state":"COMPLETE_PENDING_REVIEW"if complete else"COLLECTING","trial_days":list(trial_days),"decision_count":len(diagnostics),"metrics":metrics,"winner":None,"automatic_policy_change_permitted":False,"order_influence_permitted":False,"trading_authority":False}
