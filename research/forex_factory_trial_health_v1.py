"""Fail-closed integrity and coverage gate for the five-day news shadow trial."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
@dataclass(frozen=True)
class TrialHealthV1:
 state:str;observed_at:datetime;source_age_seconds:float;source_hash_verified:bool
 expected_decision_count:int;covered_decision_count:int;coverage_percent:int
 five_day_boundary_verified:bool;reasons:tuple[str,...]
 order_influence_permitted:bool=False;trading_authority:bool=False
 schema_version:str="forex-factory-trial-health-v1"
def evaluate_trial_health(*,observed_at,source_observed_at,source_hash_verified,trial_days,expected_decision_ids,covered_decision_ids,maximum_age=timedelta(minutes=45)):
 if observed_at.tzinfo is None or observed_at.utcoffset()!=timedelta(0)or source_observed_at.tzinfo is None or source_observed_at.utcoffset()!=timedelta(0):raise ValueError("UTC times required")
 expected=set(expected_decision_ids);covered=set(covered_decision_ids);age=(observed_at-source_observed_at).total_seconds();reasons=[]
 boundary=len(trial_days)==5 and len(set(trial_days))==5
 if not boundary:reasons.append("TRIAL_BOUNDARY_INVALID")
 if not source_hash_verified:reasons.append("SOURCE_HASH_INVALID")
 if age<0 or age>maximum_age.total_seconds():reasons.append("SOURCE_STALE")
 if not expected.issubset(covered):reasons.append("DECISION_COVERAGE_INCOMPLETE")
 percent=100 if not expected else int(100*len(expected&covered)/len(expected))
 return TrialHealthV1("HEALTHY"if not reasons else"REJECTED",observed_at,age,source_hash_verified,len(expected),len(expected&covered),percent,boundary,tuple(reasons))
