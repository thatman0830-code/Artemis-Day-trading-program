"""Restart-safe one-cycle controller for bounded BTC L2 research sampling."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime,timedelta
import json,os,uuid
from pathlib import Path

from execution.btc_perpetual_l2_aggregate_v1 import (
    BTCL2AggregateError,MINIMUM_SNAPSHOTS,aggregate_verified_receipts,load_verified_receipt,
)
from execution.btc_perpetual_l2_acquisition_v1 import acquire_once

VERSION="btc-perpetual-l2-sampling-v1"
INTERVAL=timedelta(minutes=20)
SCHEDULER_EARLY_TOLERANCE=timedelta(seconds=5)


class BTCL2SamplingError(RuntimeError):pass


def _acquire_lock(path):
    stream=open(path,"a+b");stream.seek(0)
    if stream.read(1)==b"":stream.write(b"0");stream.flush()
    stream.seek(0)
    try:
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (OSError,BlockingIOError) as exc:
        stream.close();raise BTCL2SamplingError("sampling cycle is already active") from exc
    return stream


def _release_lock(stream):
    try:
        stream.seek(0)
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    finally:stream.close()


@dataclass(frozen=True,slots=True)
class BTCL2SamplingStatusV1:
    observed_at:datetime
    verified_count:int
    next_due_at:datetime|None
    acquired_receipt_id:str|None
    evidence_sufficient:bool
    complete:bool
    maximum_requests_this_cycle:int=1
    policy_approved:bool=False
    trading_authority:bool=False


def _receipts(root):
    paths=tuple(sorted(root.glob("*.receipt.json")))
    try:return tuple(load_verified_receipt(root,path) for path in paths)
    except BTCL2AggregateError as exc:raise BTCL2SamplingError("retained L2 evidence failed verification") from exc


def _is_due(now,next_due):return now+SCHEDULER_EARLY_TOLERANCE>=next_due


def _write_status(root,status):
    document={name:(value.isoformat() if isinstance(value,datetime) else value)
        for name,value in ((field,getattr(status,field)) for field in status.__dataclass_fields__)}
    data=json.dumps({"version":VERSION,**document},sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()+b"\n"
    target=root/"sampling-status.json";temporary=root/f".sampling-status.{uuid.uuid4().hex}.tmp"
    try:
        with open(temporary,"xb") as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)


def run_sampling_cycle(*,output_root,now,acquire):
    root=Path(output_root).absolute()
    if root.is_symlink() or not root.is_dir():raise BTCL2SamplingError("sampling root is unsafe")
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset()!=timedelta(0):
        raise BTCL2SamplingError("sampling time must be UTC")
    if not callable(acquire):raise BTCL2SamplingError("acquisition dependency is invalid")
    lock_stream=_acquire_lock(root/"sampling.lock")
    try:
        before=_receipts(root);acquired=None
        if before:
            latest=max(item.observed_at for item in before)
            if latest>now:raise BTCL2SamplingError("retained observation is future-dated")
            next_due=latest+INTERVAL
        else:next_due=now
        if len(before)<MINIMUM_SNAPSHOTS or not aggregate_verified_receipts(
                root=root,receipt_paths=(root/f"{item.receipt_id}.receipt.json" for item in before)).evidence_sufficient:
            if _is_due(now,next_due):
                result=acquire(output_root=root)
                acquired=result.receipt_id
        after=_receipts(root)
        if acquired is not None and (len(after)!=len(before)+1 or acquired not in {item.receipt_id for item in after}):
            raise BTCL2SamplingError("acquisition did not retain exactly one new receipt")
        sufficient=False
        if after:
            aggregate=aggregate_verified_receipts(root=root,
                receipt_paths=(root/f"{item.receipt_id}.receipt.json" for item in after))
            sufficient=aggregate.evidence_sufficient
            next_due=max(item.observed_at for item in after)+INTERVAL if not sufficient else None
        status=BTCL2SamplingStatusV1(now,len(after),next_due,acquired,sufficient,sufficient)
        _write_status(root,status);return status
    finally:_release_lock(lock_stream)


def main():
    parser=argparse.ArgumentParser(description="Restart-safe one-cycle BTC L2 sampler")
    parser.add_argument("--output-root",type=Path,required=True);parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.output_root.is_dir() or args.output_root.is_symlink():raise BTCL2SamplingError("sampling root is unsafe")
    if not args.execute:
        print("BTC_PERPETUAL_L2_SAMPLER_PREFLIGHT_ONLY");return 0
    from datetime import timezone
    status=run_sampling_cycle(output_root=args.output_root,now=datetime.now(timezone.utc),acquire=acquire_once)
    state="COMPLETE" if status.complete else "COLLECTING"
    receipt=status.acquired_receipt_id or "NOT_DUE"
    print(f"BTC_PERPETUAL_L2_SAMPLER_{state}:{status.verified_count}:{receipt}");return 0


if __name__=="__main__":raise SystemExit(main())
