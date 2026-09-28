from dataclasses import replace
from decimal import Decimal
import pytest
from backtesting.ninjatrader_micro_paper_policy_proposal_v1 import *
def test_three_profiles_are_ordered_fair_and_nonexecutable():
 c,m,a=verify_micro_paper_policy_proposals(micro_paper_policy_proposals())
 assert tuple(x.profile for x in(c,m,a))==tuple(RiskProfile)
 assert[c.maximum_contracts_total,m.maximum_contracts_total,a.maximum_contracts_total]==[1,2,4]
 assert[c.maximum_initial_risk_usd,m.maximum_initial_risk_usd,a.maximum_initial_risk_usd]==[Decimal("100"),Decimal("250"),Decimal("500")]
 assert len({x.modeled_fee_per_contract_per_side_usd for x in(c,m,a)})==1
 assert all(x.comparison_only and x.approved is x.paper_execution_permitted is x.trading_authority is False for x in(c,m,a))
def test_modified_or_forged_suite_rejects():
 values=micro_paper_policy_proposals()
 for changed in((replace(values[0],approved=True),*values[1:]),tuple(reversed(values))):
  with pytest.raises(ValueError):verify_micro_paper_policy_proposals(changed)
def test_no_execution_dependency():
 source=__import__('pathlib').Path(__file__).with_name('ninjatrader_micro_paper_policy_proposal_v1.py').read_text();assert'from execution'not in source
