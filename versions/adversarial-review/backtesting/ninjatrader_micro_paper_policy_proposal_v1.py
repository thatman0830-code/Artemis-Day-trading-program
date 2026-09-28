"""Three unapproved MES/MNQ sizing profiles for identical-data shadow comparison."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import hashlib,json
VERSION="ninjatrader-micro-paper-policy-proposal-v1"
class RiskProfile(str,Enum):CONSERVATIVE="CONSERVATIVE";MODERATE="MODERATE";AGGRESSIVE="AGGRESSIVE"
@dataclass(frozen=True)
class MicroPaperPolicyProposalV1:
 proposal_id:str;profile:RiskProfile;shadow_equity_usd:Decimal;maximum_contracts_total:int;maximum_positions_total:int;maximum_entry_orders_total:int;maximum_initial_risk_usd:Decimal;maximum_session_loss_usd:Decimal;maximum_session_drawdown_usd:Decimal;modeled_fee_per_contract_per_side_usd:Decimal;modeled_slippage_ticks_per_fill:int;stress_slippage_ticks_per_fill:int;maximum_spread_ticks:int;session_duration_minutes:int;correlated_mes_mnq_positions_prohibited:bool;stale_evidence_stops_session:bool;comparison_only:bool=True;approval_required:bool=True;approved:bool=False;paper_execution_permitted:bool=False;unattended_paper_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False;schema_version:str=VERSION
def _make(profile,contracts,risk,loss,duration,spread):
 values=(profile,Decimal("50000"),contracts,1,1,Decimal(risk),Decimal(loss),Decimal(loss),Decimal("1.00"),1,2,spread,duration,True,True);body={"version":VERSION,"values":[str(x.value if isinstance(x,Enum)else x)for x in values],"approved":False,"authority":False};identity=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest();return MicroPaperPolicyProposalV1(identity,*values)
def micro_paper_policy_proposals():
 return(_make(RiskProfile.CONSERVATIVE,1,"100","250",5,2),_make(RiskProfile.MODERATE,2,"250","500",15,2),_make(RiskProfile.AGGRESSIVE,4,"500","1000",30,3))
def verify_micro_paper_policy_proposals(values):
 expected=micro_paper_policy_proposals()
 if values!=expected or tuple(x.profile for x in values)!=tuple(RiskProfile)or any(x.approved is not False or x.comparison_only is not True or x.paper_execution_permitted is not False or x.trading_authority is not False for x in values):raise ValueError("exact unapproved comparison profiles required")
 if any(x.maximum_initial_risk_usd/x.shadow_equity_usd>Decimal("0.01")or x.maximum_session_loss_usd/x.shadow_equity_usd>Decimal("0.02")for x in values):raise ValueError("comparison profile exceeds bounded shadow risk")
 return expected
