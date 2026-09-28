"""Explicit launcher for one bounded, no-signal supervised BTC paper drill."""
from __future__ import annotations

import argparse
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import json,os,subprocess,sys,time,uuid
from pathlib import Path

from execution.supervised_btc_paper_session_assembly_v1 import assemble_supervised_btc_paper_session
from execution.supervised_btc_paper_session_controller_v1 import SupervisedBTCPaperSessionControllerV1
from execution.supervised_paper_launch_decision_v1 import (
    MAXIMUM_COMMANDS,MAXIMUM_GROSS_EXPOSURE,MAXIMUM_ORDER_NOTIONAL,SESSION_DURATION,
)
from execution.supervised_paper_launch_evidence_v1 import OwnerSupervisionConfirmationV1,read_launch_evidence
from execution.windows_btc_paper_cycle_health_v1 import read_windows_btc_paper_cycle_health
from execution.btc_canonical_paper_launcher_input_v1 import BTCCanonicalPaperLauncherInputV1
from execution.btc_canonical_strategy_worker_v1 import (
    BTCCanonicalStrategyWorkerV1,BTCStrategyWorkerState,
)
from execution.btc_perpetual_public_evidence_acquisition_v1 import acquire_once
from execution.btc_perpetual_paper_specification_bundle_v1 import compile_paper_specification_bundle

VERSION="supervised-btc-paper-launcher-v1"
CANONICAL_PRIME_TIMEOUT_SECONDS=60


class SupervisedBTCPaperLauncherError(RuntimeError):pass


def _verify_checkout(repository,expected_checkpoint):
    try:
        head=subprocess.run(["git","-c",f"safe.directory={repository.as_posix()}","-C",str(repository),
            "rev-parse","HEAD"],check=True,capture_output=True,text=True,timeout=5).stdout.strip()
        dirty=subprocess.run(["git","-c",f"safe.directory={repository.as_posix()}","-C",str(repository),
            "status","--porcelain","--untracked-files=all"],check=True,capture_output=True,text=True,timeout=5).stdout
    except (OSError,subprocess.SubprocessError) as exc:
        raise SupervisedBTCPaperLauncherError("repository state verification failed")from exc
    if head!=expected_checkpoint or dirty:
        raise SupervisedBTCPaperLauncherError("launch evidence does not match a clean current checkout")


def _confirmation(*,now,checkpoint,supervision,stop_control):
    if supervision is not True or stop_control is not True:
        raise SupervisedBTCPaperLauncherError("fresh supervision and stop-control confirmation required")
    return OwnerSupervisionConfirmationV1.create(confirmed_at=now,
        expires_at=now+timedelta(minutes=5),repository_checkpoint=checkpoint,
        owner_supervision_confirmed=True,stop_control_verified=True,
        maximum_session_seconds=int(SESSION_DURATION.total_seconds()),
        maximum_commands=MAXIMUM_COMMANDS,maximum_order_notional=MAXIMUM_ORDER_NOTIONAL,
        maximum_gross_exposure=MAXIMUM_GROSS_EXPOSURE)


def _run_collector(*,powershell,collector,output_path,repository,label,timeout_seconds=10,
        maximum_attempts=3):
    if not 1<=timeout_seconds<=45:
        raise SupervisedBTCPaperLauncherError("collector timeout is invalid")
    if not 1<=maximum_attempts<=3:
        raise SupervisedBTCPaperLauncherError("collector retry limit is invalid")
    for attempt in range(maximum_attempts):
        try:
            completed=subprocess.run([str(powershell),"-NoProfile","-File",str(collector),
                "-OutputPath",str(output_path)],cwd=repository,check=False,timeout=timeout_seconds)
            if completed.returncode==0:return
        except subprocess.TimeoutExpired:
            pass
        if attempt+1<maximum_attempts:time.sleep(.2)
    raise SupervisedBTCPaperLauncherError(f"{label} refresh failed")


def prepare_launcher(*,repository,session_root,launch_evidence_path,economics_policy_path,
        risk_policy_path,public_evidence_root,public_evidence_receipt_path,health_facts_path,
        supervision_confirmed,stop_control_verified,as_of,specification_bundle_path=None,
        paper_specification_bundle_path=None):
    repository=Path(repository).resolve();evidence=read_launch_evidence(launch_evidence_path)
    _verify_checkout(repository,evidence.repository_checkpoint)
    confirmation=_confirmation(now=as_of,checkpoint=evidence.repository_checkpoint,
        supervision=supervision_confirmed,stop_control=stop_control_verified)
    assembly=assemble_supervised_btc_paper_session(session_root=session_root,
        archive_root=repository/"data"/"backtests"/"btc_forward_archive_2",
        evidence_path=launch_evidence_path,confirmation=confirmation,
        expected_checkpoint=evidence.repository_checkpoint,session_id=uuid.uuid4().hex,
        economics_policy_path=economics_policy_path,risk_policy_path=risk_policy_path,
        public_evidence_root=public_evidence_root,
        public_evidence_receipt_path=public_evidence_receipt_path,as_of=as_of,
        specification_bundle_path=specification_bundle_path,
        specification_repository_root=repository if specification_bundle_path is not None else None,
        paper_specification_bundle_path=paper_specification_bundle_path)
    health=read_windows_btc_paper_cycle_health(facts_path=health_facts_path,
        repository=repository,as_of=as_of)
    return assembly,health


def main():
    parser=argparse.ArgumentParser(description="Preflight or execute one no-signal BTC paper drill")
    parser.add_argument("--mode",choices=("preflight","execute"),required=True)
    parser.add_argument("--repository",type=Path,required=True);parser.add_argument("--session-root",type=Path,required=True)
    parser.add_argument("--launch-evidence",type=Path,required=True);parser.add_argument("--economics-policy",type=Path,required=True)
    parser.add_argument("--risk-policy",type=Path,required=True);parser.add_argument("--public-evidence-root",type=Path,required=True)
    parser.add_argument("--public-evidence-receipt",type=Path,required=True);parser.add_argument("--health-facts",type=Path,required=True)
    parser.add_argument("--health-collector",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--launch-evidence-collector",type=Path)
    parser.add_argument("--specification-bundle",type=Path)
    parser.add_argument("--paper-specification-bundle",type=Path)
    parser.add_argument("--refresh-public-evidence",action="store_true")
    parser.add_argument("--strategy-mode",choices=("no-signal","canonical"),default="no-signal")
    parser.add_argument("--confirm-supervision",action="store_true");parser.add_argument("--confirm-stop-control",action="store_true")
    args=parser.parse_args();now=datetime.now(timezone.utc)
    repository=args.repository.resolve();collector=(repository/"scripts"/"collect_btc_paper_cycle_health.ps1")
    launch_collector=repository/"scripts"/"collect_supervised_paper_launch_evidence.ps1"
    if (args.health_collector.is_symlink()or not args.health_collector.resolve()==collector.resolve()):
        raise SupervisedBTCPaperLauncherError("exact repository health collector required")
    powershell=Path(os.environ.get("SystemRoot",r"C:\Windows"))/"System32"/"WindowsPowerShell"/"v1.0"/"powershell.exe"
    worker=None
    if args.strategy_mode=="canonical" and args.mode=="execute":
        if (args.launch_evidence_collector is None or args.launch_evidence_collector.is_symlink()
                or args.launch_evidence_collector.resolve()!=launch_collector.resolve()):
            raise SupervisedBTCPaperLauncherError("exact repository launch-evidence collector required")
        # Refresh the authoritative watchdog immediately before the bounded
        # prime.  Keeping the isolated worker alive while the watchdog audits
        # process/filesystem state can make that independent collection fail.
        _run_collector(powershell=powershell,collector=launch_collector,
            output_path=args.launch_evidence,repository=repository,label="launch evidence",
            timeout_seconds=45)
        snapshot_root=args.session_root.parent/(args.session_root.name+"-market-snapshots")
        worker=BTCCanonicalStrategyWorkerV1(
            archive_root=repository/"data"/"backtests"/"btc_forward_archive_2",
            snapshot_root=snapshot_root,
            status_path=args.health_facts.with_name(f"canonical-prelaunch-{uuid.uuid4().hex}.json"),
            status_history_path=args.session_root.parent/
                (args.session_root.name+"-canonical-strategy-history.jsonl"))
        deadline=time.monotonic()+CANONICAL_PRIME_TIMEOUT_SECONDS
        try:
            while True:
                status=worker.poll(as_of=datetime.now(timezone.utc))
                if status.state is BTCStrategyWorkerState.READY:break
                if status.state is BTCStrategyWorkerState.FAILED:
                    raise SupervisedBTCPaperLauncherError("canonical prelaunch observation failed")
                if time.monotonic()>=deadline:
                    raise SupervisedBTCPaperLauncherError("canonical prelaunch observation timed out")
                time.sleep(.1)
            # Priming is deliberately outside all session authority. Its measured
            # worst case remains well inside the watchdog heartbeat RPO.
            _run_collector(powershell=powershell,collector=collector,
                output_path=args.health_facts,repository=repository,label="operational health")
        except Exception:
            worker.close();raise
    if args.refresh_public_evidence:
        if (args.mode!="execute" or args.strategy_mode!="canonical"
                or args.specification_bundle is not None
                or args.paper_specification_bundle is None):
            if worker is not None:worker.close()
            raise SupervisedBTCPaperLauncherError("fresh public evidence mode is incompatible")
        try:
            public=acquire_once(output_root=args.public_evidence_root)
            args.public_evidence_receipt=(args.public_evidence_root/
                f"{public.receipt_id}.receipt.json")
            compile_paper_specification_bundle(
                economics_policy_path=args.economics_policy,
                risk_policy_path=args.risk_policy,
                public_evidence_root=args.public_evidence_root,
                public_evidence_receipt_path=args.public_evidence_receipt,
                as_of=datetime.now(timezone.utc),
                output_path=args.paper_specification_bundle)
        except Exception:
            if worker is not None:worker.close()
            raise
    try:
        now=datetime.now(timezone.utc)
        assembly,health=prepare_launcher(repository=repository,session_root=args.session_root,
            launch_evidence_path=args.launch_evidence,economics_policy_path=args.economics_policy,
            risk_policy_path=args.risk_policy,public_evidence_root=args.public_evidence_root,
            public_evidence_receipt_path=args.public_evidence_receipt,health_facts_path=args.health_facts,
            supervision_confirmed=args.confirm_supervision,stop_control_verified=args.confirm_stop_control,as_of=now,
            specification_bundle_path=args.specification_bundle,
            paper_specification_bundle_path=args.paper_specification_bundle)
    except Exception:
        if worker is not None:worker.close()
        raise
    if args.mode=="preflight":
        print(json.dumps({"state":"PREFLIGHT_ELIGIBLE","session_started":False,
            "assembly_id":assembly.assembly_id,"health_id":health.health_id,
            "maximum_gross_exposure":"100","trading_authority":False},sort_keys=True));return 0
    def operational_reader():
        _run_collector(powershell=powershell,collector=collector,
            output_path=args.health_facts,repository=repository,label="operational health")
        return read_windows_btc_paper_cycle_health(facts_path=args.health_facts,
            repository=repository,as_of=datetime.now(timezone.utc))
    cycle_reader=None
    if args.strategy_mode=="canonical":
        evidence=read_launch_evidence(args.launch_evidence)
        cycle_reader=BTCCanonicalPaperLauncherInputV1(assembly=assembly,
            evidence_id=evidence.evidence_id,
            status_path=args.session_root/"canonical-strategy-status.json",
            worker=worker)
    controller=SupervisedBTCPaperSessionControllerV1(assembly=assembly,
        operational_reader=operational_reader,cycle_input_reader=cycle_reader)
    result=controller.run(waiter=time.sleep,output_path=args.output)
    print(f"SUPERVISED_BTC_PAPER_SESSION_STOPPED:{result.runtime_id}");return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        try:
            index=sys.argv.index("--session-root")
            from execution.paper_attempt_failure_v1 import write_failure
            write_failure(Path(sys.argv[index+1]),exc)
        except Exception:
            pass
        raise
