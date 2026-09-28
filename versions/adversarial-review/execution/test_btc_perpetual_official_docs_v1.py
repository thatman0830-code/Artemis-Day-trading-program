from datetime import datetime,timezone
from email.message import Message
import io,pytest
from execution.btc_perpetual_official_docs_v1 import *
T=datetime(2026,9,4,tzinfo=timezone.utc)
class Response:
 def __init__(self,raw=b"<html>official</html>",status=200,kind="text/html"):
  self.raw=io.BytesIO(raw);self.status=status;self.headers=Message();self.headers["Content-Type"]=kind
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def getcode(self):return self.status
 def read(self,count):return self.raw.read(count)
class Opener:
 def __init__(self,response):self.response=response;self.calls=[]
 def open(self,request,timeout):self.calls.append((request,timeout));return self.response
def test_exact_get_has_no_credentials():
 opener=Opener(Response());raw=https_get(SOURCES["fees"],opener=opener);request,_=opener.calls[0]
 assert raw and request.method=="GET" and "Authorization" not in request.headers and request.full_url==SOURCES["fees"]
def test_acquisition_calls_each_source_once_and_is_unapproved(tmp_path):
 calls=[]
 def transport(url):calls.append(url);return ("<html>"+url+"</html>").encode()
 result=acquire(output_root=tmp_path,transport=transport,clock=lambda zone:T)
 assert calls==list(SOURCES.values())and len(result["records"])==3
 assert result["credentials_used"]is result["owner_approved"]is result["trading_authority"]is False
 for record in result["records"]:assert hashlib.sha256((tmp_path/record["relative_path"]).read_bytes()).hexdigest()==record["sha256"]
@pytest.mark.parametrize("url",["http://hyperliquid.gitbook.io/x","https://example.com"])
def test_alternate_sources_reject(url):
 with pytest.raises(BTCOfficialDocsError,match="boundary"):https_get(url,opener=Opener(Response()))
@pytest.mark.parametrize("response",[Response(status=302),Response(kind="application/json"),Response(b"x"*(MAXIMUM_BYTES+1))])
def test_invalid_responses_reject(response):
 with pytest.raises(BTCOfficialDocsError):https_get(SOURCES["fees"],opener=Opener(response))
