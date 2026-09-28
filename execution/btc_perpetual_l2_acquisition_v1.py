"""Controlled one-shot acquisition of public BTC L2 research evidence."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from pathlib import Path
import urllib.error
import urllib.request

from execution.btc_perpetual_l2_evidence_v1 import (
    ENDPOINT,MAXIMUM_BYTES,REQUEST_BYTES,BTCL2EvidenceError,
    collect_btc_l2_evidence,
)

VERSION="btc-perpetual-l2-acquisition-v1"


class BTCL2AcquisitionError(RuntimeError):pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None


def public_https_transport(endpoint,body,headers,timeout_seconds,*,opener=None):
    if endpoint!=ENDPOINT or body!=REQUEST_BYTES or headers!={"Content-Type":"application/json"}:
        raise BTCL2AcquisitionError("public L2 request boundary violation")
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=15:
        raise BTCL2AcquisitionError("request timeout is invalid")
    request=urllib.request.Request(endpoint,data=body,headers=headers,method="POST")
    client=urllib.request.build_opener(_NoRedirect()) if opener is None else opener
    try:
        with client.open(request,timeout=timeout_seconds) as response:
            status=response.getcode();content_type=response.headers.get_content_type()
            payload=response.read(MAXIMUM_BYTES+1)
    except (OSError,urllib.error.URLError,urllib.error.HTTPError) as exc:
        raise BTCL2AcquisitionError("public L2 request failed") from exc
    if status!=200 or content_type not in ("application/json","text/json") or len(payload)>MAXIMUM_BYTES:
        raise BTCL2AcquisitionError("public L2 response status, type, or size is invalid")
    return status,payload


def preflight_l2_acquisition(output_root):
    root=Path(output_root).absolute()
    if root.is_symlink() or not root.is_dir():raise BTCL2AcquisitionError("L2 evidence root is unsafe")
    return {"version":VERSION,"endpoint":ENDPOINT,"request":REQUEST_BYTES.decode(),
        "maximum_requests":1,"credentials_used":False,"policy_approved":False,
        "trading_authority":False}


def acquire_once(*,output_root,utc_reader=None,transport=None):
    preflight_l2_acquisition(output_root)
    clock=datetime.now if utc_reader is None else utc_reader
    sender=public_https_transport if transport is None else transport
    try:
        return collect_btc_l2_evidence(transport=sender,output_root=output_root,
            captured_at=clock,timeout_seconds=10)
    except BTCL2EvidenceError as exc:
        raise BTCL2AcquisitionError("public L2 validation or retention failed") from exc


def main():
    parser=argparse.ArgumentParser(description="Controlled one-shot BTC L2 evidence acquisition")
    parser.add_argument("--output-root",type=Path,required=True);parser.add_argument("--execute",action="store_true")
    args=parser.parse_args();preflight_l2_acquisition(args.output_root)
    if not args.execute:
        print("BTC_PERPETUAL_L2_EVIDENCE_PREFLIGHT_ONLY");return 0
    result=acquire_once(output_root=args.output_root)
    print(f"BTC_PERPETUAL_L2_EVIDENCE_RETAINED:{result.receipt_id}");return 0


if __name__=="__main__":raise SystemExit(main())
