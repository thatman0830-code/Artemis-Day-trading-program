"""Offline evidence for process-isolated canonical prelaunch computation."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib,json,os,time,uuid
from pathlib import Path

from execution.btc_canonical_strategy_worker_v1 import (
    BTCCanonicalStrategyWorkerV1,BTCStrategyWorkerState,
)

VERSION="btc-canonical-prelaunch-benchmark-v1"


class BTCCanonicalPrelaunchBenchmarkError(RuntimeError):pass


def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":")).encode()


def run_benchmark(*,repository,output_path,timeout_seconds=60,clock=time.perf_counter,
        utc_reader=lambda:datetime.now(timezone.utc),waiter=time.sleep,worker_factory=None):
    repository=Path(repository).resolve();output_path=Path(output_path).resolve()
    if not 0<timeout_seconds<=60:raise BTCCanonicalPrelaunchBenchmarkError("timeout is invalid")
    status_path=output_path.with_name(output_path.stem+".status.json")
    snapshot_root=output_path.with_name(output_path.stem+"-snapshots")
    factory=worker_factory or BTCCanonicalStrategyWorkerV1
    worker=factory(archive_root=repository/"data/backtests/btc_forward_archive_2",
        snapshot_root=snapshot_root,status_path=status_path)
    started=clock();deadline=started+timeout_seconds;ready=None;observation=None
    try:
        while clock()<deadline:
            status,observation=worker.ready_observation(as_of=utc_reader())
            if status.state is BTCStrategyWorkerState.READY:ready=status;break
            if status.state is BTCStrategyWorkerState.FAILED:
                raise BTCCanonicalPrelaunchBenchmarkError("isolated observation failed")
            waiter(.05)
        if ready is None or observation is None:
            raise BTCCanonicalPrelaunchBenchmarkError("isolated observation timed out")
        cold_seconds=clock()-started;reuse_started=clock()
        reused,reused_observation=worker.ready_observation(as_of=utc_reader())
        reuse_seconds=clock()-reuse_started
        process_isolated=bool(getattr(worker,"_process",None) is not None and worker._process.is_alive())
        if (reused.state is not BTCStrategyWorkerState.READY
                or reused_observation is not observation or not process_isolated):
            raise BTCCanonicalPrelaunchBenchmarkError("prelaunch reuse or isolation rejected")
        body={"schema_version":VERSION,"measured_at":utc_reader().isoformat(),
            "cold_ready_seconds":round(cold_seconds,6),"unchanged_reuse_seconds":round(reuse_seconds,6),
            "observation_id":observation.observation_id,"result_id":observation.result.id,
            "one_minute_sha256":observation.one_minute.reference.sha256,
            "five_minute_sha256":observation.five_minute.reference.sha256,
            "candle_count":observation.candle_count,"actionable":observation.actionable,
            "process_isolated":True,"paper_session_started":False,"command_count":0,
            "reservation_created":False,"trading_authority":False}
    finally:
        worker.close()
    body["worker_stopped"]=not bool(getattr(worker,"_process",None))
    document={**body,"benchmark_id":hashlib.sha256(_canonical(body)).hexdigest()}
    output_path.parent.mkdir(parents=True,exist_ok=True)
    temporary=output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary,"xb")as stream:
            stream.write(_canonical(document)+b"\n");stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,output_path)
    finally:temporary.unlink(missing_ok=True)
    return document


def main():
    parser=argparse.ArgumentParser(description="Benchmark isolated canonical BTC prelaunch observation")
    parser.add_argument("--repository",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--timeout-seconds",type=int,default=60)
    args=parser.parse_args();result=run_benchmark(repository=args.repository,
        output_path=args.output,timeout_seconds=args.timeout_seconds)
    print(json.dumps(result,sort_keys=True));return 0


if __name__=="__main__":raise SystemExit(main())
