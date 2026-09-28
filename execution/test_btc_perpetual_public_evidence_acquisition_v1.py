from datetime import timezone
from email.message import Message
import io
import pytest

from execution.btc_perpetual_public_evidence_acquisition_v1 import *
from execution.test_btc_perpetual_public_evidence_collector_v1 import payload,T


class Response:
    def __init__(self,raw,status=200,content_type="application/json"):
        self.raw=io.BytesIO(raw);self.status=status;self.headers=Message();self.headers["Content-Type"]=content_type
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def getcode(self):return self.status
    def read(self,count):return self.raw.read(count)


class Opener:
    def __init__(self,response):self.response=response;self.calls=[]
    def open(self,request,timeout):self.calls.append((request,timeout));return self.response


def test_transport_is_exact_post_without_credentials():
    opener=Opener(Response(payload()))
    status,raw=public_https_transport(ENDPOINT,REQUEST_BYTES,{"Content-Type":"application/json"},10,opener=opener)
    request,timeout=opener.calls[0]
    assert status==200 and raw==payload() and request.full_url==ENDPOINT and request.method=="POST"
    assert request.data==REQUEST_BYTES and set(request.headers)=={"Content-type"} and timeout==10


def test_preflight_does_not_call_transport_and_acquire_calls_once(tmp_path):
    value=preflight_public_acquisition(tmp_path)
    assert value["maximum_requests"]==1 and not value["credentials_used"] and not value["trading_authority"]
    calls=[]
    def transport(*args):calls.append(args);return 200,payload()
    result=acquire_once(output_root=tmp_path,utc_reader=lambda zone:T,transport=transport)
    assert len(calls)==1 and result.captured_at==T and not result.trading_authority


@pytest.mark.parametrize("endpoint,body,headers",[
    ("https://example.com",REQUEST_BYTES,{"Content-Type":"application/json"}),
    (ENDPOINT,b'{"type":"userFees"}',{"Content-Type":"application/json"}),
    (ENDPOINT,REQUEST_BYTES,{"Authorization":"secret"}),
])
def test_alternate_endpoint_body_or_headers_reject(endpoint,body,headers):
    with pytest.raises(BTCPerpetualPublicAcquisitionError,match="boundary"):
        public_https_transport(endpoint,body,headers,10,opener=Opener(Response(payload())))


@pytest.mark.parametrize("response",[Response(payload(),302),Response(payload(),200,"text/html"),Response(b"x"*(MAXIMUM_BYTES+1))])
def test_status_content_type_and_size_fail_closed(response):
    with pytest.raises(BTCPerpetualPublicAcquisitionError):
        public_https_transport(ENDPOINT,REQUEST_BYTES,{"Content-Type":"application/json"},10,opener=Opener(response))
