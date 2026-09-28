"""Fail-closed live-quote and non-transmitted margin evidence gates."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal
from enum import Enum
import re
from execution.futures_micro_paper_scope_v1 import FuturesMicroPaperScopeV1,VerifiedMicroContractV1,FuturesMicroPaperScopeError

class FuturesRuntimeEvidenceError(ValueError):pass
class MarketDataType(str,Enum):LIVE="LIVE";DELAYED="DELAYED";FROZEN="FROZEN"
def _utc(v,name):
 if not isinstance(v,datetime)or v.tzinfo is None or v.utcoffset()!=timedelta(0):raise FuturesRuntimeEvidenceError(f"{name} must be UTC")
 return v
def _positive(v,name):
 if not isinstance(v,Decimal):raise TypeError(f"{name} must be Decimal")
 if not v.is_finite()or v<=0:raise FuturesRuntimeEvidenceError(f"{name} must be positive")
 return v
@dataclass(frozen=True,slots=True)
class MicroLiveQuoteEvidenceV1:
 provider:str;contract:VerifiedMicroContractV1;captured_at:datetime;bid:Decimal;ask:Decimal
 data_type:MarketDataType;entitlement_confirmed:bool;decision_use_permitted:bool
@dataclass(frozen=True,slots=True)
class MicroMarginPreviewEvidenceV1:
 contract:VerifiedMicroContractV1;long_captured_at:datetime;short_captured_at:datetime;quantity:int
 long_initial_margin_usd:Decimal;short_initial_margin_usd:Decimal
 long_maintenance_margin_usd:Decimal;short_maintenance_margin_usd:Decimal
 source:str;long_screenshot_sha256:str;short_screenshot_sha256:str;preview_only:bool;transmitted:bool
@dataclass(frozen=True,slots=True)
class FuturesRuntimeEvidenceGateV1:
 ready_for_policy_review:bool;blockers:tuple[str,...]
 conservative_initial_margin_usd:Decimal;conservative_maintenance_margin_usd:Decimal
 paper_execution_permitted:bool=False;live_trading_permitted:bool=False;trading_authority:bool=False
def evaluate_runtime_evidence(*,scope:FuturesMicroPaperScopeV1,contract:VerifiedMicroContractV1,
 quote:MicroLiveQuoteEvidenceV1,margin:MicroMarginPreviewEvidenceV1,as_of:datetime)->FuturesRuntimeEvidenceGateV1:
 if not all(isinstance(x,t)for x,t in ((scope,FuturesMicroPaperScopeV1),(contract,VerifiedMicroContractV1),(quote,MicroLiveQuoteEvidenceV1),(margin,MicroMarginPreviewEvidenceV1))):raise TypeError("typed runtime evidence required")
 _utc(as_of,"as_of");blockers=[]
 try:scope.verify_contract(contract)
 except(TypeError,FuturesMicroPaperScopeError):blockers.append("CONTRACT_INVALID")
 if quote.contract!=contract:blockers.append("QUOTE_CONTRACT_MISMATCH")
 try:
  _utc(quote.captured_at,"quote time");bid=_positive(quote.bid,"bid");ask=_positive(quote.ask,"ask")
  if ask<bid:blockers.append("QUOTE_CROSSED")
  if quote.captured_at>as_of or as_of-quote.captured_at>timedelta(seconds=1):blockers.append("QUOTE_STALE")
 except(TypeError,FuturesRuntimeEvidenceError):blockers.append("QUOTE_INVALID")
 if quote.data_type is not MarketDataType.LIVE:blockers.append("QUOTE_NOT_LIVE")
 if quote.entitlement_confirmed is not True or quote.decision_use_permitted is not True:blockers.append("QUOTE_ENTITLEMENT_INVALID")
 if not isinstance(quote.provider,str)or not quote.provider.strip():blockers.append("QUOTE_PROVIDER_INVALID")
 if margin.contract!=contract:blockers.append("MARGIN_CONTRACT_MISMATCH")
 values=[]
 try:
  _utc(margin.long_captured_at,"long margin time");_utc(margin.short_captured_at,"short margin time")
  values=[_positive(x,"margin")for x in (margin.long_initial_margin_usd,margin.short_initial_margin_usd,margin.long_maintenance_margin_usd,margin.short_maintenance_margin_usd)]
  if any(x>as_of or as_of-x>timedelta(minutes=15)for x in (margin.long_captured_at,margin.short_captured_at)):blockers.append("MARGIN_STALE")
 except(TypeError,FuturesRuntimeEvidenceError):blockers.append("MARGIN_INVALID")
 if isinstance(margin.quantity,bool)or margin.quantity!=1:blockers.append("MARGIN_QUANTITY_INVALID")
 if margin.source!="IBKR_TWS_ORDER_PREVIEW"or margin.preview_only is not True or margin.transmitted is not False:blockers.append("MARGIN_SOURCE_OR_TRANSMISSION_INVALID")
 if any(not re.fullmatch(r"[0-9a-f]{64}",x)for x in (margin.long_screenshot_sha256,margin.short_screenshot_sha256)):blockers.append("MARGIN_SCREENSHOT_INVALID")
 initial=max(values[:2],default=Decimal(0));maintenance=max(values[2:],default=Decimal(0))
 if values and (maintenance>initial or initial>scope.starting_equity*Decimal("0.25")):blockers.append("MARGIN_LIMIT_INVALID")
 ordered=tuple(sorted(set(blockers)))
 return FuturesRuntimeEvidenceGateV1(not ordered,ordered,initial,maintenance)
