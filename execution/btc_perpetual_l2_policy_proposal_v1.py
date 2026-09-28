"""Create an unapproved BTC paper-only policy proposal from verified L2 evidence."""
from __future__ import annotations

import argparse,hashlib,json,os,uuid
from decimal import Decimal
from pathlib import Path

from execution.btc_perpetual_l2_aggregate_v1 import aggregate_verified_receipts

VERSION="btc-perpetual-l2-policy-proposal-v1"
SLIPPAGE_FLOOR_BPS=Decimal("2")
PAPER_ORDER_NOTIONAL_CAP=Decimal("100")
PARTICIPATION_LIMIT_PERCENT=Decimal("0.01")


class BTCL2PolicyProposalError(ValueError):pass


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()


def create_l2_policy_proposal(*,root,receipt_paths):
    aggregate=aggregate_verified_receipts(root=root,receipt_paths=receipt_paths)
    if not aggregate.evidence_sufficient:raise BTCL2PolicyProposalError("L2 evidence gate is incomplete")
    observed_max=max(aggregate.maximum_buy_impact_bps_100,aggregate.maximum_sell_impact_bps_100)
    proposed_slippage=max(SLIPPAGE_FLOOR_BPS,observed_max*Decimal(2))
    aggregate_body={
        "receipt_ids":list(aggregate.receipt_ids),"first_observed_at":aggregate.first_observed_at.isoformat(),
        "last_observed_at":aggregate.last_observed_at.isoformat(),"hour_bucket_count":aggregate.hour_bucket_count,
        "maximum_spread_bps":str(aggregate.maximum_spread_bps),"p95_spread_bps":str(aggregate.p95_spread_bps),
        "maximum_buy_impact_bps_100":str(aggregate.maximum_buy_impact_bps_100),
        "p95_buy_impact_bps_100":str(aggregate.p95_buy_impact_bps_100),
        "maximum_sell_impact_bps_100":str(aggregate.maximum_sell_impact_bps_100),
        "p95_sell_impact_bps_100":str(aggregate.p95_sell_impact_bps_100),
        "minimum_bid_depth_notional":str(aggregate.minimum_bid_depth_notional),
        "minimum_ask_depth_notional":str(aggregate.minimum_ask_depth_notional),
    }
    aggregate_id=hashlib.sha256(_canonical(aggregate_body)).hexdigest()
    body={"schema_version":VERSION,"market":"BTC-PERP","aggregate_id":aggregate_id,
        "aggregate":aggregate_body,"proposed_paper_only_values":{
            "slippage_bps_per_fill":str(proposed_slippage),
            "maximum_order_notional_usd":str(PAPER_ORDER_NOTIONAL_CAP),
            "participation_limit_percent":str(PARTICIPATION_LIMIT_PERCENT)},
        "method":{
            "slippage":"max(2 bps conservative floor, 2 * worst observed $100 one-way midpoint impact)",
            "order_notional":"fixed initial supervised-paper cap; not inferred from venue capacity",
            "participation":"fixed 0.01% cap, checked against minimum retained displayed side depth"},
        "remaining_blockers":["OWNER_APPROVED_FEE_TIER","OWNER_APPROVED_FUNDING_METHOD",
            "OWNER_APPROVED_COMPLETE_SPECIFICATION_BUNDLE"],
        "evidence_sufficient":True,"owner_approved":False,"paper_use_permitted":False,
        "live_trading_permitted":False,"trading_authority":False}
    return {**body,"proposal_id":hashlib.sha256(_canonical(body)).hexdigest()}


def write_l2_policy_proposal(*,root,output_path):
    evidence_root=Path(root).absolute();output=Path(output_path).absolute()
    if output.parent.is_symlink() or not output.parent.is_dir():raise BTCL2PolicyProposalError("proposal output parent is unsafe")
    proposal=create_l2_policy_proposal(root=evidence_root,receipt_paths=evidence_root.glob("*.receipt.json"))
    data=_canonical(proposal)+b"\n";temporary=output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary,"xb") as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,output)
    finally:temporary.unlink(missing_ok=True)
    return proposal


def main():
    parser=argparse.ArgumentParser(description="Generate unapproved BTC L2 paper-policy proposal")
    parser.add_argument("--evidence-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();proposal=write_l2_policy_proposal(root=args.evidence_root,output_path=args.output)
    print(f"BTC_PERPETUAL_L2_POLICY_PROPOSAL_WRITTEN:{proposal['proposal_id']}");return 0


if __name__=="__main__":raise SystemExit(main())
