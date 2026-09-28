"""Controlled retention of exact official BTC perpetual economics documents."""
from __future__ import annotations
import argparse,hashlib,json,os,urllib.error,urllib.request,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path

VERSION="btc-perpetual-official-docs-v1";MAXIMUM_BYTES=4*1024*1024
SOURCES={
 "fees":"https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees",
 "funding":"https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding",
 "contract_specifications":"https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications"}

class BTCOfficialDocsError(RuntimeError):pass
class _NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _retain(path,data):
 if path.exists():
  if path.is_symlink()or path.read_bytes()!=data:raise BTCOfficialDocsError("retained document conflict")
  return
 temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
 try:
  with open(temporary,"xb")as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,path)
 finally:temporary.unlink(missing_ok=True)

def https_get(url,*,timeout_seconds=15,opener=None):
 if url not in SOURCES.values() or type(timeout_seconds)is not int or not 1<=timeout_seconds<=20:raise BTCOfficialDocsError("official-document request boundary violation")
 request=urllib.request.Request(url,headers={"Accept":"text/html","User-Agent":"BTC-paper-evidence/1"},method="GET")
 client=urllib.request.build_opener(_NoRedirect()) if opener is None else opener
 try:
  with client.open(request,timeout=timeout_seconds)as response:
   status=response.getcode();kind=response.headers.get_content_type();payload=response.read(MAXIMUM_BYTES+1)
 except(OSError,urllib.error.URLError,urllib.error.HTTPError)as exc:raise BTCOfficialDocsError("official-document request failed")from exc
 if status!=200 or kind not in("text/html","application/xhtml+xml")or not 0<len(payload)<=MAXIMUM_BYTES:raise BTCOfficialDocsError("official-document response is invalid")
 return payload

def preflight(output_root):
 root=Path(output_root).absolute()
 if root.is_symlink()or not root.is_dir():raise BTCOfficialDocsError("evidence root is unsafe")
 return {"version":VERSION,"sources":SOURCES,"maximum_requests":3,"credentials_used":False,"owner_approved":False,"trading_authority":False}

def acquire(*,output_root,transport=https_get,clock=datetime.now):
 preflight(output_root);root=Path(output_root).absolute();records=[]
 for name,url in SOURCES.items():
  payload=transport(url);captured=clock(timezone.utc)
  if captured.tzinfo is None or captured.utcoffset()!=timedelta(0):raise BTCOfficialDocsError("capture clock is invalid")
  digest=hashlib.sha256(payload).hexdigest();raw=root/f"{digest}.html"
  _retain(raw,payload)
  records.append({"name":name,"canonical_url":url,"captured_at":captured.isoformat(),"sha256":digest,"relative_path":raw.name})
 body={"schema_version":VERSION,"records":records,"credentials_used":False,"owner_approved":False,"trading_authority":False}
 document={**body,"evidence_id":hashlib.sha256(_canonical(body)).hexdigest()}
 _retain(root/f"{document['evidence_id']}.json",_canonical(document)+b"\n");return document

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--output-root",type=Path,required=True);parser.add_argument("--execute",action="store_true");args=parser.parse_args();preflight(args.output_root)
 if not args.execute:print("BTC_OFFICIAL_DOCS_PREFLIGHT_ONLY");return 0
 print("BTC_OFFICIAL_DOCS_RETAINED:"+acquire(output_root=args.output_root)["evidence_id"]);return 0
if __name__=="__main__":raise SystemExit(main())
