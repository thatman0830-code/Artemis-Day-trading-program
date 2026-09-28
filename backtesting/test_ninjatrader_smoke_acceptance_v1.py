from datetime import timedelta
from dataclasses import replace
import pytest
from backtesting.ninjatrader_smoke_acceptance_v1 import *
from backtesting.ninjatrader_smoke_maturity_gate_v1 import evaluate_ninjatrader_smoke_maturity
from backtesting.test_ninjatrader_smoke_maturity_gate_v1 import histories
def test_completed_gate_attests_review_only(tmp_path):
 status,at=histories(tmp_path,count=24,step=5);gate=evaluate_ninjatrader_smoke_maturity(history_root=tmp_path/"history",task_status=status,as_of=at);value=attest_ninjatrader_smoke_acceptance(gate=gate,history_root=tmp_path/"history",attested_at=at)
 assert value.es_report_count==value.nq_report_count==24 and value.es_bar_count==value.nq_bar_count==120
 assert value.es_outcome_counts==value.nq_outcome_counts==(("NO_SETUP",24),)
 assert value.supervised_paper_design_review_eligible is True
 assert value.supervised_paper_execution_permitted is value.unattended_paper_permitted is value.trading_authority is False
def test_incomplete_or_changed_evidence_rejects(tmp_path):
 status,at=histories(tmp_path,count=24,step=5);gate=evaluate_ninjatrader_smoke_maturity(history_root=tmp_path/"history",task_status=status,as_of=at)
 with pytest.raises(ValueError,match="completed"):attest_ninjatrader_smoke_acceptance(gate=replace(gate,progress_percent=99),history_root=tmp_path/"history",attested_at=at)
 with pytest.raises(ValueError,match="differ"):attest_ninjatrader_smoke_acceptance(gate=replace(gate,es_bar_count=121),history_root=tmp_path/"history",attested_at=at)
def test_acceptance_has_no_execution_surface():
 source=__import__('pathlib').Path(__file__).with_name('ninjatrader_smoke_acceptance_v1.py').read_text()
 assert 'from execution'not in source
 for word in('SubmitOrder','CreateOrder','trading_authority:bool=True'):assert word not in source
