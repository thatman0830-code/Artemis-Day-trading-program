"""Map retained public BTC facts into an unapproved owner-intake draft."""
from __future__ import annotations

import argparse,copy,json
from decimal import Decimal
from pathlib import Path

from execution.btc_perpetual_public_evidence_collector_v1 import (
    BTCPerpetualPublicEvidenceV1,ENDPOINT,read_btc_perpetual_public_evidence,
)
from execution.btc_perpetual_specification_intake_v1 import (
    SCHEMA,create_blank_intake_template,read_intake_document,
)


class BTCPerpetualIntakeDraftError(ValueError): pass


def apply_public_evidence_to_intake(*,intake,receipt):
    if intake!=create_blank_intake_template(): raise BTCPerpetualIntakeDraftError("an unchanged blank intake template is required")
    if not isinstance(receipt,BTCPerpetualPublicEvidenceV1): raise BTCPerpetualIntakeDraftError("typed public evidence receipt required")
    receipt.__post_init__();result=copy.deepcopy(intake)
    common={"source_organization":"Hyperliquid","document_identity":receipt.receipt_id,
        "canonical_url":ENDPOINT,"local_snapshot_path":receipt.raw_relative_path,
        "snapshot_sha256":receipt.response_sha256,"retrieved_at":receipt.captured_at.isoformat(),
        "effective_from":receipt.captured_at.isoformat(),"effective_to":None,"owner_approved":False}
    step=format(Decimal(1).scaleb(-receipt.size_decimals),"f")
    values={
        "INSTRUMENT":{"quantity_step":step,"size_decimals":str(receipt.size_decimals),
            "venue_maximum_leverage":str(receipt.maximum_leverage)},
        "MARK_PRICE":{"mark_price":str(receipt.mark_price),"observed_at":receipt.captured_at.isoformat()},
        "ORACLE_PRICE":{"oracle_price":str(receipt.oracle_price),"observed_at":receipt.captured_at.isoformat()},
        "FUNDING":{"current_hourly_funding_rate":str(receipt.funding_rate),"observed_at":receipt.captured_at.isoformat()},
        "MARGIN_TIER":{"margin_table_id":str(receipt.margin_table_id),
            "venue_maximum_leverage":str(receipt.maximum_leverage),"observed_at":receipt.captured_at.isoformat()},
    }
    for record in result["records"]:
        kind=record["specification_type"]
        if kind in values:
            record.update(common);record["values"]=values[kind]
            record["assumptions_and_gaps"]=["PUBLIC_FACTS_RETAINED_OWNER_REVIEW_REQUIRED"]
    result["size_decimals"]=receipt.size_decimals
    return result


def write_public_intake_draft(path,value):
    path=Path(path)
    if path.parent.is_symlink() or not path.parent.is_dir(): raise BTCPerpetualIntakeDraftError("draft parent is unsafe")
    with open(path,"xb") as stream: stream.write(json.dumps(value,sort_keys=True,separators=(",",":")).encode()+b"\n")


def main():
    parser=argparse.ArgumentParser(description="Apply retained BTC public facts to an unapproved intake draft")
    parser.add_argument("--blank-intake",type=Path,required=True);parser.add_argument("--evidence-root",type=Path,required=True)
    parser.add_argument("--receipt",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();receipt=read_btc_perpetual_public_evidence(output_root=args.evidence_root,receipt_path=args.receipt)
    draft=apply_public_evidence_to_intake(intake=read_intake_document(args.blank_intake),receipt=receipt)
    write_public_intake_draft(args.output,draft);print(f"BTC_PERPETUAL_UNAPPROVED_INTAKE_DRAFT_WRITTEN:{args.output}")
    return 0


if __name__=="__main__": raise SystemExit(main())
