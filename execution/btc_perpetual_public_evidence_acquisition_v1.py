"""One-shot credential-free acquisition for public BTC perpetual evidence."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from pathlib import Path
import urllib.error
import urllib.request

from execution.btc_perpetual_public_evidence_collector_v1 import (
    ENDPOINT,MAXIMUM_BYTES,REQUEST_BYTES,BTCPerpetualPublicEvidenceError,
    collect_btc_perpetual_public_evidence,
)

VERSION="btc-perpetual-public-evidence-acquisition-v1"


class BTCPerpetualPublicAcquisitionError(RuntimeError): pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl): return None


def public_https_transport(endpoint,body,headers,timeout_seconds,*,opener=None):
    if endpoint!=ENDPOINT or body!=REQUEST_BYTES or headers!={"Content-Type":"application/json"}:
        raise BTCPerpetualPublicAcquisitionError("public request boundary violation")
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=15:
        raise BTCPerpetualPublicAcquisitionError("request timeout is invalid")
    request=urllib.request.Request(endpoint,data=body,headers=headers,method="POST")
    client=urllib.request.build_opener(_NoRedirect()) if opener is None else opener
    try:
        with client.open(request,timeout=timeout_seconds) as response:
            status=response.getcode();content_type=response.headers.get_content_type()
            payload=response.read(MAXIMUM_BYTES+1)
    except (OSError,urllib.error.URLError,urllib.error.HTTPError) as exc:
        raise BTCPerpetualPublicAcquisitionError("public evidence request failed") from exc
    if status!=200 or content_type not in ("application/json","text/json") or len(payload)>MAXIMUM_BYTES:
        raise BTCPerpetualPublicAcquisitionError("public response status, type, or size is invalid")
    return status,payload


def preflight_public_acquisition(output_root):
    root=Path(output_root).absolute()
    if root.is_symlink() or not root.is_dir(): raise BTCPerpetualPublicAcquisitionError("evidence root is unsafe")
    return {"version":VERSION,"endpoint":ENDPOINT,"request":REQUEST_BYTES.decode(),
        "maximum_requests":1,"credentials_used":False,"trading_authority":False}


def acquire_once(*,output_root,utc_reader=None,transport=None):
    preflight_public_acquisition(output_root)
    clock=datetime.now if utc_reader is None else utc_reader
    captured_at=clock(timezone.utc)
    sender=public_https_transport if transport is None else transport
    try:
        return collect_btc_perpetual_public_evidence(transport=sender,output_root=output_root,
            captured_at=captured_at,timeout_seconds=10)
    except BTCPerpetualPublicEvidenceError as exc:
        raise BTCPerpetualPublicAcquisitionError("public evidence validation or retention failed") from exc


def main():
    parser=argparse.ArgumentParser(description="Controlled one-shot BTC public evidence acquisition")
    parser.add_argument("--output-root",type=Path,required=True);parser.add_argument("--execute",action="store_true")
    args=parser.parse_args();preflight_public_acquisition(args.output_root)
    if not args.execute:
        print("BTC_PERPETUAL_PUBLIC_EVIDENCE_PREFLIGHT_ONLY");return 0
    result=acquire_once(output_root=args.output_root)
    print(f"BTC_PERPETUAL_PUBLIC_EVIDENCE_RETAINED:{result.receipt_id}");return 0


if __name__=="__main__": raise SystemExit(main())
