"""Controlled retention of official IBKR micro-futures economics pages."""
from __future__ import annotations
import hashlib,json,os,urllib.error,urllib.parse,urllib.request,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path

VERSION="futures-micro-official-docs-v1";MAXIMUM_BYTES=8*1024*1024
SOURCES={
 "commissions":"https://www.interactivebrokers.com/en/pricing/commissions-futures.php",
 "cme_fees":"https://www.interactivebrokers.com/en/accounts/fees/CME.php",
 "margins":"https://www.interactivebrokers.com/en/trading/margin-futures-fops.php"}
ALLOWED_REDIRECTS={
 (SOURCES["margins"],"https://www.interactivebrokers.com/en/trading/margin-requirements.php#margin-requirements")}
class FuturesMicroOfficialDocsError(RuntimeError):pass
class _OfficialRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  old,new=urllib.parse.urlparse(req.full_url),urllib.parse.urlparse(newurl)
  if (new.scheme!="https" or new.hostname not in ("www.interactivebrokers.com","portal.interactivebrokers.com")
      or (new.path!=old.path and (req.full_url,newurl)not in ALLOWED_REDIRECTS)):
   raise FuturesMicroOfficialDocsError("official redirect boundary violation")
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
def _retain(path,data):
 if path.exists():
  if path.is_symlink()or path.read_bytes()!=data:raise FuturesMicroOfficialDocsError("retained document conflict")
  return
 temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
 try:
  with open(temporary,"xb")as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(temporary,path)
 finally:temporary.unlink(missing_ok=True)
def https_get(url,*,timeout_seconds=20,opener=None):
 if url not in SOURCES.values()or type(timeout_seconds)is not int or not 1<=timeout_seconds<=30:raise FuturesMicroOfficialDocsError("official request boundary violation")
 request=urllib.request.Request(url,headers={"Accept":"text/html","User-Agent":"MES-MNQ-paper-evidence/1"},method="GET")
 client=urllib.request.build_opener(_OfficialRedirect())if opener is None else opener
 try:
  with client.open(request,timeout=timeout_seconds)as response:
   status=response.getcode();kind=response.headers.get_content_type();payload=response.read(MAXIMUM_BYTES+1)
   final=urllib.parse.urlparse(response.geturl())
 except(OSError,urllib.error.URLError,urllib.error.HTTPError)as exc:raise FuturesMicroOfficialDocsError("official request failed")from exc
 if (status!=200 or kind not in("text/html","application/xhtml+xml")or not 0<len(payload)<=MAXIMUM_BYTES
     or final.scheme!="https"or final.hostname not in ("www.interactivebrokers.com","portal.interactivebrokers.com")):
  raise FuturesMicroOfficialDocsError("official response is invalid")
 return payload
def acquire(*,output_root,transport=https_get,clock=datetime.now):
 root=Path(output_root).absolute()
 if root.is_symlink()or not root.is_dir():raise FuturesMicroOfficialDocsError("evidence root is unsafe")
 records=[]
 for name,url in SOURCES.items():
  payload=transport(url);captured=clock(timezone.utc)
  if captured.tzinfo is None or captured.utcoffset()!=timedelta(0):raise FuturesMicroOfficialDocsError("capture clock is invalid")
  digest=hashlib.sha256(payload).hexdigest();raw=root/f"ibkr_{name}_{digest}.html";_retain(raw,payload)
  records.append({"name":name,"canonical_url":url,"captured_at":captured.isoformat(),"sha256":digest,"relative_path":raw.name})
 body={"schema_version":VERSION,"records":records,"credentials_used":False,"owner_approved":False,"paper_execution_permitted":False,"live_trading_permitted":False,"trading_authority":False}
 result={**body,"evidence_id":hashlib.sha256(_canonical(body)).hexdigest()}
 _retain(root/f"ibkr_micro_{result['evidence_id']}.json",_canonical(result)+b"\n");return result
