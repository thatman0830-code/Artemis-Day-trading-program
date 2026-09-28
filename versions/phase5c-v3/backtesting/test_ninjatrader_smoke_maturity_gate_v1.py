from datetime import timedelta
from dataclasses import asdict,replace
from decimal import Decimal
import json
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket as M
from backtesting.ninjatrader_canonical_smoke_history_v1 import append_ninjatrader_canonical_smoke
from backtesting.ninjatrader_canonical_smoke_v1 import evaluate_ninjatrader_canonical_smoke
from backtesting.ninjatrader_closed_bar_dataset_v1 import read_closed_bar_dataset
from backtesting.ninjatrader_smoke_maturity_gate_v1 import *
from backtesting.test_ninjatrader_closed_bar_dataset_v1 import NOW,build
def histories(root,count=2,step=60):
 reports=[]
 for m in M:
  source=root/("source"+m.value);build(source,m);e=read_closed_bar_dataset(source,market=m,day="2026-09-08",as_of=NOW+timedelta(minutes=4));base=evaluate_ninjatrader_canonical_smoke(evidence=e,minimum_tick=Decimal(".25"),instrument_specification_id=("a"if m is M.ES else"b")*64,as_of=NOW+timedelta(minutes=4))
  for i in range(count):append_ninjatrader_canonical_smoke(root/"history",report=replace(base,report_id=__import__('hashlib').sha256(f'{m.value}{i}'.encode()).hexdigest(),dataset_fingerprint=__import__('hashlib').sha256(f'd{m.value}{i}'.encode()).hexdigest(),source_chain_head_sha256=__import__('hashlib').sha256(f's{m.value}{i}'.encode()).hexdigest(),evaluated_at=base.evaluated_at+timedelta(minutes=i*step),source_bar_count=120))
  reports.append({"market":m.value,"report_id":__import__('hashlib').sha256(f'{m.value}{count-1}'.encode()).hexdigest(),"deterministic_repeat_verified":True,"trading_authority":False})
 at=base.evaluated_at+timedelta(minutes=(count-1)*step)
 return {"state":"COMPLETE","observed_at":at.isoformat(),"reports":reports,"trading_authority":False},at
def test_incomplete_gate_reports_exact_progress_and_no_authority(tmp_path):
 status,at=histories(tmp_path,count=2,step=5);gate=evaluate_ninjatrader_smoke_maturity(history_root=tmp_path/"history",task_status=status,as_of=at)
 assert not gate.ready_for_supervised_paper_review and gate.progress_percent==5
 assert set(gate.reasons)=={MaturityReason.INSUFFICIENT_REPORTS,MaturityReason.INSUFFICIENT_SPAN}
 assert gate.paper_execution_permitted is gate.trading_authority is False
def test_mature_bound_histories_pass_review_only(tmp_path):
 status,at=histories(tmp_path,count=24,step=5);gate=evaluate_ninjatrader_smoke_maturity(history_root=tmp_path/"history",task_status=status,as_of=at)
 assert gate.ready_for_supervised_paper_review and gate.progress_percent==100 and not gate.reasons
 assert gate.paper_execution_permitted is False
def test_stale_or_unbound_status_fails_closed(tmp_path):
 status,at=histories(tmp_path,count=24,step=5);status["reports"][0]["report_id"]="0"*64
 gate=evaluate_ninjatrader_smoke_maturity(history_root=tmp_path/"history",task_status=status,as_of=at+timedelta(minutes=11))
 assert MaturityReason.TASK_STATUS_STALE in gate.reasons and MaturityReason.TASK_STATUS_UNBOUND in gate.reasons
