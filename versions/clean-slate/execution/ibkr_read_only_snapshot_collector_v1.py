"""Read-only IBKR evidence collection boundary; no order API is present."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
from typing import Mapping,Protocol
import hashlib,json,os,uuid
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from execution.futures_micro_paper_scope_v1 import FuturesMicroPaperScopeV1,VerifiedMicroContractV1
from execution.ibkr_micro_paper_preflight_v1 import IBKRReadOnlySnapshotV1,evaluate_ibkr_micro_paper_preflight

VERSION="ibkr-read-only-snapshot-collector-v1"
class IBKRReadOnlyCollectorError(RuntimeError):pass
class IBKRReadOnlyTransport(Protocol):
 def capture_read_only(self,*,host:str,port:int,client_id:int,timeout_seconds:int,market:FuturesCanonicalMarket)->Mapping[str,object]:...
@dataclass(frozen=True,slots=True)
class IBKRReadOnlyRequestV1:
 market:FuturesCanonicalMarket;host:str="127.0.0.1";port:int=7497;client_id:int=71;timeout_seconds:int=10
 def __post_init__(self):
  if (not isinstance(self.market,FuturesCanonicalMarket)or self.host!="127.0.0.1"or self.port!=7497
      or isinstance(self.client_id,bool)or not isinstance(self.client_id,int)or not 1<=self.client_id<=999
      or isinstance(self.timeout_seconds,bool)or not isinstance(self.timeout_seconds,int)or not 1<=self.timeout_seconds<=15):raise IBKRReadOnlyCollectorError("request escapes paper/read-only boundary")
def _decimal(v,name):
 try:value=Decimal(v)if isinstance(v,str)else v
 except InvalidOperation as exc:raise IBKRReadOnlyCollectorError(f"{name} is invalid")from exc
 if not isinstance(value,Decimal)or not value.is_finite()or value<0:raise IBKRReadOnlyCollectorError(f"{name} is invalid")
 return value
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def collect(*,scope:FuturesMicroPaperScopeV1,request:IBKRReadOnlyRequestV1,transport:IBKRReadOnlyTransport,evaluated_at:datetime|None,output_root,clock=None)->dict:
 if not isinstance(scope,FuturesMicroPaperScopeV1)or not isinstance(request,IBKRReadOnlyRequestV1):raise TypeError("typed scope and request required")
 if evaluated_at is not None and (evaluated_at.tzinfo is None or evaluated_at.utcoffset()!=timedelta(0)):raise IBKRReadOnlyCollectorError("evaluation time must be UTC")
 try:raw=transport.capture_read_only(host=request.host,port=request.port,client_id=request.client_id,timeout_seconds=request.timeout_seconds,market=request.market)
 except Exception as exc:raise IBKRReadOnlyCollectorError("read-only capture failed")from exc
 required={"captured_at","account_id","connected","api_read_only","order_placement_available","open_order_count","futures_position_count","market_data_type","market_data_live","bid","ask","local_symbol","expiry_yyyymm","ibkr_contract_id","initial_margin_usd","maintenance_margin_usd"}
 if not isinstance(raw,Mapping)or set(raw)!=required:raise IBKRReadOnlyCollectorError("capture schema is invalid")
 if evaluated_at is None:
  evaluated_at=(clock or (lambda:datetime.now(timezone.utc)))()
  if not isinstance(evaluated_at,datetime)or evaluated_at.tzinfo is None or evaluated_at.utcoffset()!=timedelta(0):raise IBKRReadOnlyCollectorError("evaluation clock is invalid")
 captured=raw["captured_at"]
 if not isinstance(captured,datetime):raise IBKRReadOnlyCollectorError("capture timestamp is invalid")
 contract=VerifiedMicroContractV1(request.market,str(raw["local_symbol"]),str(raw["expiry_yyyymm"]),raw["ibkr_contract_id"])
 snapshot=IBKRReadOnlySnapshotV1(captured,raw["account_id"],raw["connected"],raw["api_read_only"],raw["order_placement_available"],raw["open_order_count"],raw["futures_position_count"],raw["market_data_live"],contract,_decimal(raw["initial_margin_usd"],"initial margin"),_decimal(raw["maintenance_margin_usd"],"maintenance margin"))
 report=evaluate_ibkr_micro_paper_preflight(scope=scope,snapshot=snapshot,evaluated_at=evaluated_at)
 body={"schema_version":VERSION,"report_id":report.report_id,"scope_id":scope.scope_id,"market":request.market.value,
  "captured_at":captured.isoformat(),"evaluated_at":evaluated_at.isoformat(),"account_id_fingerprint":report.account_id_fingerprint,
  "local_symbol":contract.local_symbol,"expiry_yyyymm":contract.expiry_yyyymm,"ibkr_contract_id":contract.ibkr_contract_id,
  "initial_margin_usd":str(report.observed_initial_margin_usd),"maintenance_margin_usd":str(report.observed_maintenance_margin_usd),
  "market_data_type":raw["market_data_type"],"bid":None if raw["bid"]is None else str(_decimal(raw["bid"],"bid")),"ask":None if raw["ask"]is None else str(_decimal(raw["ask"],"ask")),
  "ready_for_policy_review":report.ready_for_policy_review,"blockers":list(report.blockers),"raw_account_id_retained":False,
  "read_only":True,"paper_execution_permitted":False,"live_trading_permitted":False,"trading_authority":False}
 result={**body,"receipt_id":hashlib.sha256(_canonical(body)).hexdigest()};root=Path(output_root).absolute()
 if root.is_symlink()or not root.is_dir():raise IBKRReadOnlyCollectorError("output root is unsafe")
 path=root/f"{result['receipt_id']}.ibkr-read-only.json";data=_canonical(result)+b"\n"
 if path.exists():
  if path.is_symlink()or path.read_bytes()!=data:raise IBKRReadOnlyCollectorError("receipt identity collision")
 else:
  temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
  try:
   with open(temporary,"xb")as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
   os.replace(temporary,path)
  finally:temporary.unlink(missing_ok=True)
 return result
