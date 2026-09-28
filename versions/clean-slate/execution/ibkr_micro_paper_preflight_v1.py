"""Pure read-only preflight over caller-captured IBKR paper evidence."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal
import hashlib,json
import re
from execution.futures_micro_paper_scope_v1 import (
 FuturesMicroPaperScopeV1,VerifiedMicroContractV1,FuturesMicroPaperScopeError)

VERSION="ibkr-micro-paper-preflight-v1"
class IBKRMicroPaperPreflightError(ValueError):pass
def _decimal(v,name):
 if not isinstance(v,Decimal):raise TypeError(f"{name} must be Decimal")
 if not v.is_finite()or v<0:raise IBKRMicroPaperPreflightError(f"{name} is invalid")
 return v
def _canonical(v):
 def enc(x):
  if isinstance(x,Decimal):return str(x)
  if isinstance(x,datetime):return x.isoformat()
  if hasattr(x,"value"):return x.value
  if hasattr(x,"__dataclass_fields__"):return {k:getattr(x,k)for k in x.__dataclass_fields__}
  raise TypeError(type(x).__name__)
 return json.dumps(v,sort_keys=True,separators=(",",":"),default=enc).encode()

@dataclass(frozen=True,slots=True)
class IBKRReadOnlySnapshotV1:
 captured_at:datetime;account_id:str;connected:bool;api_read_only:bool
 order_placement_available:bool;open_order_count:int;futures_position_count:int
 market_data_live:bool;contract:VerifiedMicroContractV1
 initial_margin_usd:Decimal;maintenance_margin_usd:Decimal

@dataclass(frozen=True,slots=True)
class IBKRMicroPaperPreflightV1:
 report_id:str;evaluated_at:datetime;scope_id:str;ready_for_policy_review:bool
 blockers:tuple[str,...];account_id_fingerprint:str;contract_id:int
 observed_initial_margin_usd:Decimal;observed_maintenance_margin_usd:Decimal
 read_only:bool=True;paper_execution_permitted:bool=False
 live_trading_permitted:bool=False;trading_authority:bool=False

def evaluate_ibkr_micro_paper_preflight(*,scope:FuturesMicroPaperScopeV1,
 snapshot:IBKRReadOnlySnapshotV1,evaluated_at:datetime)->IBKRMicroPaperPreflightV1:
 if not isinstance(scope,FuturesMicroPaperScopeV1)or not isinstance(snapshot,IBKRReadOnlySnapshotV1):raise TypeError("typed scope and snapshot required")
 if evaluated_at.tzinfo is None or evaluated_at.utcoffset()!=timedelta(0):raise IBKRMicroPaperPreflightError("evaluation time must be UTC")
 blockers=[]
 if snapshot.captured_at.tzinfo is None or snapshot.captured_at.utcoffset()!=timedelta(0)or snapshot.captured_at>evaluated_at or evaluated_at-snapshot.captured_at>timedelta(seconds=5):blockers.append("SNAPSHOT_NOT_CURRENT")
 if not isinstance(snapshot.account_id,str)or not re.fullmatch(r"DU[A-Z0-9]+",snapshot.account_id)or not any(x.isdigit()for x in snapshot.account_id[2:]):blockers.append("NOT_IBKR_PAPER_ACCOUNT")
 if snapshot.connected is not True:blockers.append("GATEWAY_DISCONNECTED")
 if snapshot.api_read_only is not True or snapshot.order_placement_available is not False:blockers.append("API_NOT_READ_ONLY")
 if isinstance(snapshot.open_order_count,bool)or not isinstance(snapshot.open_order_count,int)or snapshot.open_order_count!=0:blockers.append("OPEN_ORDERS_PRESENT_OR_INVALID")
 if isinstance(snapshot.futures_position_count,bool)or not isinstance(snapshot.futures_position_count,int)or snapshot.futures_position_count!=0:blockers.append("FUTURES_POSITIONS_PRESENT_OR_INVALID")
 if snapshot.market_data_live is not True:blockers.append("LIVE_MARKET_DATA_UNAVAILABLE")
 try:scope.verify_contract(snapshot.contract)
 except(TypeError,FuturesMicroPaperScopeError):blockers.append("CONTRACT_IDENTITY_INVALID")
 try:
  initial=_decimal(snapshot.initial_margin_usd,"initial margin");maintenance=_decimal(snapshot.maintenance_margin_usd,"maintenance margin")
  if initial<=0 or maintenance<=0 or maintenance>initial:blockers.append("MARGIN_VALUES_INVALID")
  if initial>scope.starting_equity*Decimal("0.25"):blockers.append("MARGIN_UTILIZATION_EXCEEDS_PROPOSAL")
 except(TypeError,IBKRMicroPaperPreflightError):
  initial=maintenance=Decimal(0);blockers.append("MARGIN_VALUES_INVALID")
 ordered=tuple(sorted(set(blockers)));account_hash=hashlib.sha256(snapshot.account_id.encode()).hexdigest() if isinstance(snapshot.account_id,str)and snapshot.account_id else ""
 contract_id=getattr(snapshot.contract,"ibkr_contract_id",0)
 body=(VERSION,evaluated_at,scope.scope_id,not ordered,ordered,account_hash,contract_id,initial,maintenance,True,False,False,False)
 report=hashlib.sha256(_canonical(body)).hexdigest()
 return IBKRMicroPaperPreflightV1(report,evaluated_at,scope.scope_id,not ordered,ordered,account_hash,contract_id,initial,maintenance)
