"""Aggregate verified BTC L2 receipts without approving a trading policy."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta
from decimal import Decimal,InvalidOperation
import hashlib,json
from pathlib import Path

from execution.btc_perpetual_l2_evidence_v1 import (
    BTCL2EvidenceError,BTCL2EvidenceV1,validate_btc_l2_response,
)

VERSION="btc-perpetual-l2-aggregate-v1"
MINIMUM_SNAPSHOTS=24
MINIMUM_SPAN=timedelta(hours=6)
MINIMUM_HOUR_BUCKETS=4


class BTCL2AggregateError(ValueError):pass


def _decimal(value,name):
    if not isinstance(value,str):raise BTCL2AggregateError(f"{name} encoding is invalid")
    try:result=Decimal(value)
    except InvalidOperation as exc:raise BTCL2AggregateError(f"{name} is invalid") from exc
    if not result.is_finite():raise BTCL2AggregateError(f"{name} is invalid")
    return result


def _datetime(value,name):
    if not isinstance(value,str):raise BTCL2AggregateError(f"{name} encoding is invalid")
    try:result=datetime.fromisoformat(value)
    except ValueError as exc:raise BTCL2AggregateError(f"{name} is invalid") from exc
    return result


def load_verified_receipt(root,receipt_path):
    evidence_root=Path(root).absolute();path=Path(receipt_path).absolute()
    if evidence_root.is_symlink() or not evidence_root.is_dir() or path.is_symlink() or not path.is_file():
        raise BTCL2AggregateError("evidence path is unsafe")
    if not path.resolve().is_relative_to(evidence_root.resolve()):raise BTCL2AggregateError("receipt escapes evidence root")
    try:document=json.loads(path.read_bytes())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:raise BTCL2AggregateError("receipt is unreadable") from exc
    expected=set(BTCL2EvidenceV1.__dataclass_fields__)
    if not isinstance(document,dict) or set(document)!=expected:raise BTCL2AggregateError("receipt fields are invalid")
    raw_relative=document["raw_relative_path"]
    if not isinstance(raw_relative,str):raise BTCL2AggregateError("raw path encoding is invalid")
    raw=evidence_root/Path(raw_relative)
    if raw.is_symlink() or not raw.is_file() or not raw.resolve().is_relative_to(evidence_root.resolve()):
        raise BTCL2AggregateError("raw evidence path is unsafe")
    try:payload=raw.read_bytes()
    except OSError as exc:raise BTCL2AggregateError("raw evidence is unreadable") from exc
    captured=_datetime(document["captured_at"],"captured_at")
    try:verified=validate_btc_l2_response(payload=payload,captured_at=captured,raw_relative_path=raw_relative)
    except BTCL2EvidenceError as exc:raise BTCL2AggregateError("raw evidence validation failed") from exc
    supplied=dict(document)
    for name in ("best_bid","best_ask","midpoint","spread_bps","buy_vwap_100","sell_vwap_100",
            "buy_impact_bps_100","sell_impact_bps_100","bid_depth_notional","ask_depth_notional",
            "maximum_observed_participation_percent"):
        supplied[name]=_decimal(supplied[name],name)
    supplied["captured_at"]=captured;supplied["observed_at"]=_datetime(supplied["observed_at"],"observed_at")
    try:receipt=BTCL2EvidenceV1(**supplied)
    except (TypeError,BTCL2EvidenceError) as exc:raise BTCL2AggregateError("receipt validation failed") from exc
    if path.name!=f"{receipt.receipt_id}.receipt.json":raise BTCL2AggregateError("receipt filename identity mismatch")
    if receipt!=verified or hashlib.sha256(payload).hexdigest()!=receipt.response_sha256:
        raise BTCL2AggregateError("receipt does not match retained raw evidence")
    return receipt


def _nearest_rank_95(values):
    ordered=sorted(values);index=(95*len(ordered)+99)//100-1
    return ordered[index]


@dataclass(frozen=True,slots=True)
class BTCL2AggregateV1:
    receipt_ids:tuple[str,...]
    first_observed_at:datetime
    last_observed_at:datetime
    hour_bucket_count:int
    maximum_spread_bps:Decimal
    p95_spread_bps:Decimal
    maximum_buy_impact_bps_100:Decimal
    p95_buy_impact_bps_100:Decimal
    maximum_sell_impact_bps_100:Decimal
    p95_sell_impact_bps_100:Decimal
    minimum_bid_depth_notional:Decimal
    minimum_ask_depth_notional:Decimal
    evidence_sufficient:bool
    policy_approved:bool=False
    trading_authority:bool=False


def aggregate_verified_receipts(*,root,receipt_paths):
    paths=tuple(receipt_paths)
    if not paths:raise BTCL2AggregateError("at least one receipt is required")
    receipts=tuple(load_verified_receipt(root,path) for path in paths)
    ordered=tuple(sorted(receipts,key=lambda item:(item.observed_at,item.receipt_id)))
    ids=tuple(item.receipt_id for item in ordered)
    if len(ids)!=len(set(ids)):raise BTCL2AggregateError("duplicate receipt identity")
    observed=tuple(item.observed_at for item in ordered)
    if len(observed)!=len(set(observed)):raise BTCL2AggregateError("duplicate observation time")
    buckets=len({value.replace(minute=0,second=0,microsecond=0) for value in observed})
    sufficient=(len(ordered)>=MINIMUM_SNAPSHOTS and observed[-1]-observed[0]>=MINIMUM_SPAN
        and buckets>=MINIMUM_HOUR_BUCKETS)
    spreads=tuple(item.spread_bps for item in ordered)
    buys=tuple(item.buy_impact_bps_100 for item in ordered)
    sells=tuple(item.sell_impact_bps_100 for item in ordered)
    return BTCL2AggregateV1(ids,observed[0],observed[-1],buckets,max(spreads),_nearest_rank_95(spreads),
        max(buys),_nearest_rank_95(buys),max(sells),_nearest_rank_95(sells),
        min(item.bid_depth_notional for item in ordered),min(item.ask_depth_notional for item in ordered),
        sufficient,False,False)
