"""Retain and reload sanitized, content-addressed TWS margin-preview evidence."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal,InvalidOperation
import hashlib,json,os,re
from pathlib import Path
from execution.futures_micro_paper_scope_v1 import VerifiedMicroContractV1
from execution.futures_micro_runtime_evidence_gates_v1 import MicroMarginPreviewEvidenceV1
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket

SCHEMA="futures-micro-margin-evidence-v1"
class FuturesMicroMarginEvidenceError(ValueError):pass
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _contained(root,path):
 root=Path(root).resolve();path=Path(path).resolve()
 if not path.is_relative_to(root):raise FuturesMicroMarginEvidenceError("evidence path escapes root")
 return root,path
def _atomic(path,payload):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(f".{path.name}.{os.getpid()}.tmp")
 try:tmp.write_bytes(payload);os.replace(tmp,path)
 finally:
  if tmp.exists():tmp.unlink()
def retain_margin_preview(*,evidence_root,long_screenshot_path,short_screenshot_path,contract,long_captured_at,short_captured_at,long_initial_margin_usd,
 short_initial_margin_usd,long_maintenance_margin_usd,short_maintenance_margin_usd):
 if not isinstance(contract,VerifiedMicroContractV1):raise TypeError("verified contract required")
 for captured in (long_captured_at,short_captured_at):
  if captured.tzinfo is None or captured.utcoffset().total_seconds()!=0:raise FuturesMicroMarginEvidenceError("capture times must be UTC")
 root=Path(evidence_root).resolve();sources=(Path(long_screenshot_path).resolve(),Path(short_screenshot_path).resolve())
 if any(not x.is_file()or x.is_symlink()for x in sources):raise FuturesMicroMarginEvidenceError("regular screenshots required")
 payloads=tuple(x.read_bytes()for x in sources)
 if any(not x for x in payloads):raise FuturesMicroMarginEvidenceError("empty screenshot")
 digests=tuple(hashlib.sha256(x).hexdigest()for x in payloads);images=tuple(root/f"{d}{s.suffix.lower()}"for d,s in zip(digests,sources))
 values=tuple(Decimal(str(x))for x in (long_initial_margin_usd,short_initial_margin_usd,long_maintenance_margin_usd,short_maintenance_margin_usd))
 if any(not x.is_finite()or x<=0 for x in values):raise FuturesMicroMarginEvidenceError("positive finite margins required")
 body={"schema_version":SCHEMA,"contract":{"market":contract.research_market.value,"local_symbol":contract.local_symbol,
  "expiry_yyyymm":contract.expiry_yyyymm,"con_id":contract.ibkr_contract_id},"long_captured_at":long_captured_at.isoformat(),"short_captured_at":short_captured_at.isoformat(),"quantity":1,
  "long_initial_margin_usd":str(values[0]),"short_initial_margin_usd":str(values[1]),
  "long_maintenance_margin_usd":str(values[2]),"short_maintenance_margin_usd":str(values[3]),
  "source":"IBKR_TWS_ORDER_PREVIEW","long_screenshot_sha256":digests[0],"short_screenshot_sha256":digests[1],
  "long_screenshot_relative_path":images[0].name,"short_screenshot_relative_path":images[1].name,
  "preview_only":True,"transmitted":False,"paper_only":True,"trading_authority":False}
 evidence_id=hashlib.sha256(_canonical(body)).hexdigest();document={**body,"evidence_id":evidence_id}
 for image,payload in zip(images,payloads):_atomic(image,payload)
 receipt=root/f"{evidence_id}.receipt.json";_atomic(receipt,_canonical(document)+b"\n")
 return receipt
def read_margin_preview(*,evidence_root,receipt_path):
 root,receipt=_contained(evidence_root,receipt_path)
 try:
  doc=json.loads(receipt.read_bytes());body={k:v for k,v in doc.items()if k!="evidence_id"}
  if doc["schema_version"]!=SCHEMA or doc["trading_authority"]is not False or doc["paper_only"]is not True:raise ValueError
  if hashlib.sha256(_canonical(body)).hexdigest()!=doc["evidence_id"]:raise ValueError
  pairs=((doc["long_screenshot_relative_path"],doc["long_screenshot_sha256"]),(doc["short_screenshot_relative_path"],doc["short_screenshot_sha256"]))
  for relative,digest in pairs:
   if not re.fullmatch(r"[0-9a-f]{64}",digest):raise ValueError
   _,image=_contained(root,root/relative)
   if image.is_symlink()or not image.is_file()or hashlib.sha256(image.read_bytes()).hexdigest()!=digest:raise ValueError
  c=doc["contract"];contract=VerifiedMicroContractV1(FuturesCanonicalMarket(c["market"]),c["local_symbol"],c["expiry_yyyymm"],c["con_id"])
  return MicroMarginPreviewEvidenceV1(contract,datetime.fromisoformat(doc["long_captured_at"]),datetime.fromisoformat(doc["short_captured_at"]),doc["quantity"],
   Decimal(doc["long_initial_margin_usd"]),Decimal(doc["short_initial_margin_usd"]),
   Decimal(doc["long_maintenance_margin_usd"]),Decimal(doc["short_maintenance_margin_usd"]),
   doc["source"],doc["long_screenshot_sha256"],doc["short_screenshot_sha256"],doc["preview_only"],doc["transmitted"])
 except(KeyError,TypeError,ValueError,InvalidOperation,OSError,json.JSONDecodeError)as exc:
  raise FuturesMicroMarginEvidenceError("margin evidence is invalid")from exc
