"""Immutable owner-approved risk limits for supervised BTC paper sessions."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import uuid

from execution.btc_perpetual_paper_economics_policy_v1 import read_policy
from execution.btc_perpetual_public_evidence_collector_v1 import (
    read_btc_perpetual_public_evidence,
)

VERSION = "btc-perpetual-paper-risk-policy-v1"
APPROVAL = ("approve the recommended conservative BTC paper risk specification: $1 price "
    "increment, 100% notional collateral with no leverage credit, $100 maximum total "
    "exposure, one position and one entry order at a time, $5 maximum session loss, and "
    "$5 maximum session drawdown. Stale funding, mark, oracle, clock, recorder, or "
    "reconciliation evidence must stop the session. This applies only to supervised paper "
    "trading and grants no live-trading authority.")
VALUES = {
    "price_increment_usd":"1", "collateral_fraction":"1",
    "leverage_credit":"0", "maximum_total_exposure_usd":"100",
    "maximum_positions":1, "maximum_entry_orders":1,
    "maximum_session_loss_usd":"5", "maximum_session_drawdown_usd":"5",
    "fail_closed_evidence":["CLOCK","FUNDING","MARK","ORACLE","RECONCILIATION","RECORDER"],
}


class BTCPaperRiskPolicyError(ValueError): pass


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()


def issue_policy(*, economics_policy_path, public_evidence_root,
        public_evidence_receipt_path, owner_approval):
    if owner_approval != APPROVAL:
        raise BTCPaperRiskPolicyError("exact owner approval is required")
    economics = read_policy(economics_policy_path)
    public = read_btc_perpetual_public_evidence(output_root=public_evidence_root,
        receipt_path=public_evidence_receipt_path)
    body={"schema_version":VERSION,"market":"BTC-PERP","values":copy.deepcopy(VALUES),
        "source_ids":[economics["policy_id"],public.receipt_id],
        "scope":"SUPERVISED_PAPER_ONLY","owner_approved":True,
        "paper_use_permitted":True,"live_trading_permitted":False,
        "trading_authority":False}
    return {**body,"policy_id":hashlib.sha256(_canonical(body)).hexdigest()}


def read_risk_policy(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 65536:
        raise BTCPaperRiskPolicyError("risk policy artifact is unsafe")
    try: document=json.loads(path.read_bytes())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise BTCPaperRiskPolicyError("risk policy artifact is unreadable") from exc
    required={"schema_version","market","values","source_ids","scope","owner_approved",
        "paper_use_permitted","live_trading_permitted","trading_authority","policy_id"}
    body={key:document[key] for key in document if key!="policy_id"}
    if (set(document)!=required or document["schema_version"]!=VERSION
            or document["market"]!="BTC-PERP" or document["values"]!=VALUES
            or not isinstance(document["source_ids"],list) or len(document["source_ids"])!=2
            or any(not isinstance(x,str) or len(x)!=64 for x in document["source_ids"])
            or document["scope"]!="SUPERVISED_PAPER_ONLY"
            or document["owner_approved"] is not True
            or document["paper_use_permitted"] is not True
            or document["live_trading_permitted"] is not False
            or document["trading_authority"] is not False
            or hashlib.sha256(_canonical(body)).hexdigest()!=document["policy_id"]):
        raise BTCPaperRiskPolicyError("risk policy fields or identity are invalid")
    return document


def write_policy(*,output_path,**values):
    result=issue_policy(**values);path=Path(output_path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary,"xb") as stream:
            stream.write(_canonical(result)+b"\n");stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally: temporary.unlink(missing_ok=True)
    if read_risk_policy(path)!=result: raise BTCPaperRiskPolicyError("written policy verification failed")
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--economics-policy",type=Path,required=True)
    parser.add_argument("--public-evidence-root",type=Path,required=True)
    parser.add_argument("--public-evidence-receipt",type=Path,required=True)
    parser.add_argument("--approval",required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();result=write_policy(output_path=args.output,
        economics_policy_path=args.economics_policy,public_evidence_root=args.public_evidence_root,
        public_evidence_receipt_path=args.public_evidence_receipt,owner_approval=args.approval)
    print("BTC_PAPER_RISK_POLICY_WRITTEN:"+result["policy_id"]);return 0


if __name__=="__main__": raise SystemExit(main())
