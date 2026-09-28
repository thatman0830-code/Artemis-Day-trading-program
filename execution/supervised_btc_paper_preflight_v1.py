"""Read-only aggregate preflight for a supervised BTC paper session."""
from __future__ import annotations

import argparse,hashlib,json,subprocess
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from pathlib import Path

from execution.btc_archive_snapshot_source_v1 import read_btc_archive_snapshot
from execution.btc_perpetual_paper_economics_policy_v1 import read_policy
from execution.btc_perpetual_paper_risk_policy_v1 import read_risk_policy
from execution.btc_perpetual_public_evidence_collector_v1 import read_btc_perpetual_public_evidence
from execution.btc_perpetual_paper_specification_bundle_v1 import read_paper_specification_bundle
from execution.paper_reservation_checkpoint_v1 import PaperReservationCheckpointV1
from execution.supervised_paper_launch_evidence_v1 import (
    OwnerSupervisionConfirmationV1,evaluate_collected_launch_evidence,read_launch_evidence,
)
from execution.supervised_paper_launch_gate_v1 import SupervisedPaperLaunchPolicyV1
from execution.supervised_paper_launch_decision_v1 import (
    SESSION_DURATION,MAXIMUM_COMMANDS,MAXIMUM_ORDER_NOTIONAL,MAXIMUM_GROSS_EXPOSURE,
)

VERSION="supervised-btc-paper-preflight-v1"


@dataclass(frozen=True,slots=True)
class SupervisedBTCPaperPreflightV1:
    evaluated_at:datetime
    ready:bool
    reasons:tuple[str,...]
    repository_checkpoint:str
    archive_id:str|None
    public_evidence_id:str|None
    economic_gate_id:str|None
    reservation_state:str
    report_id:str
    trading_authority:bool=False

    def __post_init__(self):
        body=(VERSION,self.evaluated_at.isoformat(),self.ready,self.reasons,self.repository_checkpoint,
            self.archive_id,self.public_evidence_id,self.economic_gate_id,self.reservation_state,False)
        expected=hashlib.sha256(json.dumps(body,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
        if (self.ready is not (not self.reasons) or tuple(sorted(set(self.reasons)))!=self.reasons
                or self.report_id!=expected or self.trading_authority is not False):
            raise ValueError("preflight report identity or authority mismatch")


def evaluate_supervised_btc_paper_preflight(*,repository_checkpoint,repository_clean,
        expected_checkpoint,session_root,session_id,archive_root,evidence_path,confirmation,
        economics_policy_path,risk_policy_path,public_evidence_root,
        public_evidence_receipt_path,paper_specification_bundle_path,as_of):
    reasons=[];archive_id=public_id=gate_id=None;reservation_state="NEW"
    if repository_checkpoint!=expected_checkpoint:reasons.append("REPOSITORY_CHECKPOINT_MISMATCH")
    if repository_clean is not True:reasons.append("REPOSITORY_NOT_CLEAN")
    try:
        evidence=read_launch_evidence(evidence_path)
        policy=SupervisedPaperLaunchPolicyV1(expected_checkpoint,timedelta(minutes=5),
            timedelta(minutes=5),SESSION_DURATION,MAXIMUM_COMMANDS,MAXIMUM_ORDER_NOTIONAL,
            MAXIMUM_GROSS_EXPOSURE,allowed_markets=("BTC-PERP",))
        decision=evaluate_collected_launch_evidence(evidence=evidence,confirmation=confirmation,
            policy=policy,as_of=as_of)
        reasons.extend("LAUNCH_"+item.value for item in decision.reasons)
    except Exception as exc:reasons.append("LAUNCH_EVIDENCE_"+type(exc).__name__.upper())
    try:
        read_policy(economics_policy_path);read_risk_policy(risk_policy_path)
        public=read_btc_perpetual_public_evidence(output_root=public_evidence_root,
            receipt_path=public_evidence_receipt_path);public_id=public.receipt_id
        if not timedelta(0)<=as_of-public.captured_at<=timedelta(minutes=1):reasons.append("PUBLIC_EVIDENCE_STALE")
        gate,_=read_paper_specification_bundle(paper_specification_bundle_path,
            economics_policy_path=economics_policy_path,risk_policy_path=risk_policy_path,
            public_evidence_root=public_evidence_root,
            public_evidence_receipt_path=public_evidence_receipt_path);gate_id=gate.gate_id
    except Exception as exc:reasons.append("ECONOMICS_"+type(exc).__name__.upper())
    try:
        one=read_btc_archive_snapshot(archive_root,timeframe="1m",as_of=as_of)
        five=read_btc_archive_snapshot(archive_root,timeframe="5m",as_of=as_of)
        if (one.archive_id,one.manifest_sha256,one.manifest_updated_at)!=(
                five.archive_id,five.manifest_sha256,five.manifest_updated_at):
            reasons.append("ARCHIVE_STREAM_MISMATCH")
        archive_id=one.archive_id
    except Exception as exc:reasons.append("ARCHIVE_"+type(exc).__name__.upper())
    root=Path(session_root)
    if root.exists() and any(root.iterdir()):
        try:
            state=PaperReservationCheckpointV1(root,session_id).reconcile()
            reservation_state=state.state
            if state.state!="EMPTY":reasons.append("SESSION_ROOT_NOT_FRESH")
        except Exception as exc:reasons.append("RESERVATION_"+type(exc).__name__.upper())
    result=tuple(sorted(set(reasons)))
    body=(VERSION,as_of.isoformat(),not result,result,repository_checkpoint,archive_id,
        public_id,gate_id,reservation_state,False)
    report_id=hashlib.sha256(json.dumps(body,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    return SupervisedBTCPaperPreflightV1(as_of,not result,result,repository_checkpoint,
        archive_id,public_id,gate_id,reservation_state,report_id,False)


def _git_facts(repository):
    root=str(Path(repository).absolute())
    head=subprocess.run(["git","-c",f"safe.directory={root}","rev-parse","HEAD"],cwd=root,
        check=True,capture_output=True,text=True).stdout.strip()
    clean=not subprocess.run(["git","-c",f"safe.directory={root}","status","--porcelain"],cwd=root,
        check=True,capture_output=True,text=True).stdout
    return head,clean


def main():
    parser=argparse.ArgumentParser(description="Read-only supervised BTC paper preflight")
    for name in ("repository","session-root","archive-root","evidence","economics-policy","risk-policy",
            "public-evidence-root","public-evidence-receipt","paper-specification-bundle"):
        parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--expected-checkpoint",required=True)
    parser.add_argument("--session-id",required=True)
    parser.add_argument("--confirm-supervision",action="store_true")
    parser.add_argument("--confirm-stop-control",action="store_true")
    args=parser.parse_args();now=datetime.now(timezone.utc);head,clean=_git_facts(args.repository)
    confirmation=OwnerSupervisionConfirmationV1.create(confirmed_at=now,expires_at=now+timedelta(minutes=5),
        repository_checkpoint=args.expected_checkpoint,
        owner_supervision_confirmed=args.confirm_supervision,
        stop_control_verified=args.confirm_stop_control,
        maximum_session_seconds=int(SESSION_DURATION.total_seconds()),maximum_commands=5,
        maximum_order_notional=MAXIMUM_ORDER_NOTIONAL,maximum_gross_exposure=MAXIMUM_GROSS_EXPOSURE)
    report=evaluate_supervised_btc_paper_preflight(repository_checkpoint=head,repository_clean=clean,
        expected_checkpoint=args.expected_checkpoint,session_root=args.session_root,session_id=args.session_id,
        archive_root=args.archive_root,
        evidence_path=args.evidence,confirmation=confirmation,economics_policy_path=args.economics_policy,
        risk_policy_path=args.risk_policy,public_evidence_root=args.public_evidence_root,
        public_evidence_receipt_path=args.public_evidence_receipt,
        paper_specification_bundle_path=args.paper_specification_bundle,as_of=now)
    print(json.dumps({name:(value.isoformat()if isinstance(value,datetime)else list(value)if isinstance(value,tuple)else value)
        for name,value in ((n,getattr(report,n))for n in report.__dataclass_fields__)},sort_keys=True,separators=(",",":")))
    return 0 if report.ready else 2


if __name__=="__main__":raise SystemExit(main())
