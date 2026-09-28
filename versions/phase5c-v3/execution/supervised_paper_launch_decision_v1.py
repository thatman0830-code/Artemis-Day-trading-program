"""Create an advisory launch decision from collected evidence and explicit owner acknowledgements."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from execution.supervised_paper_launch_evidence_v1 import (
    OwnerSupervisionConfirmationV1, evaluate_collected_launch_evidence, read_launch_evidence,
)
from execution.supervised_paper_launch_gate_v1 import SupervisedPaperLaunchPolicyV1

DECISION_ENVELOPE_VERSION="supervised-paper-launch-decision-envelope-v1"
SESSION_DURATION=timedelta(minutes=5)
MAXIMUM_COMMANDS=5
MAXIMUM_ORDER_NOTIONAL=Decimal("100")
MAXIMUM_GROSS_EXPOSURE=Decimal("100")


def _canonical(value: object) -> str:
    return json.dumps(value,sort_keys=True,separators=(",",":"))


def create_launch_decision(*,evidence_path:Path,as_of:datetime,
        owner_supervision_confirmed:bool,stop_control_verified:bool)->dict:
    if as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0):
        raise ValueError("as_of must be UTC")
    if owner_supervision_confirmed is not True or stop_control_verified is not True:
        raise ValueError("explicit owner supervision and stop-control acknowledgements are required")
    evidence=read_launch_evidence(evidence_path)
    policy=SupervisedPaperLaunchPolicyV1(evidence.repository_checkpoint,timedelta(minutes=5),
        timedelta(minutes=5),SESSION_DURATION,MAXIMUM_COMMANDS,MAXIMUM_ORDER_NOTIONAL,
        MAXIMUM_GROSS_EXPOSURE,allowed_markets=("BTC-PERP",))
    confirmation=OwnerSupervisionConfirmationV1.create(confirmed_at=as_of,
        expires_at=as_of+timedelta(minutes=5),repository_checkpoint=evidence.repository_checkpoint,
        owner_supervision_confirmed=True,stop_control_verified=True,
        maximum_session_seconds=int(SESSION_DURATION.total_seconds()),maximum_commands=MAXIMUM_COMMANDS,
        maximum_order_notional=MAXIMUM_ORDER_NOTIONAL,maximum_gross_exposure=MAXIMUM_GROSS_EXPOSURE)
    decision=evaluate_collected_launch_evidence(evidence=evidence,confirmation=confirmation,
        policy=policy,as_of=as_of)
    body={"schema_version":DECISION_ENVELOPE_VERSION,"evaluated_at":as_of.isoformat(),
        "evidence_id":evidence.evidence_id,"confirmation_id":confirmation.confirmation_id,
        "launch_id":decision.launch_id,"eligible":decision.eligible,
        "reasons":[reason.value for reason in decision.reasons],
        "expires_at":None if decision.expires_at is None else decision.expires_at.isoformat(),
        "permitted_markets":list(decision.permitted_markets),
        "maximum_session_seconds":int(decision.maximum_session_duration.total_seconds()),
        "maximum_commands":decision.maximum_commands,
        "maximum_order_notional":str(decision.maximum_order_notional),
        "maximum_gross_exposure":str(decision.maximum_gross_exposure),
        "advisory_only":decision.advisory_only,"live_trading_permitted":decision.live_trading_permitted,
        "trading_authority":decision.trading_authority}
    return {**body,"decision_envelope_id":hashlib.sha256(_canonical(body).encode()).hexdigest()}


def write_launch_decision(path:Path,value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(_canonical(value)+"\n",encoding="utf-8",newline="\n")
    os.replace(temporary,path)


def main()->int:
    parser=argparse.ArgumentParser(description="Evaluate an advisory supervised paper launch")
    parser.add_argument("--evidence",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--confirm-supervision",action="store_true")
    parser.add_argument("--confirm-stop-control",action="store_true")
    args=parser.parse_args();value=create_launch_decision(evidence_path=args.evidence,
        as_of=datetime.now(timezone.utc),owner_supervision_confirmed=args.confirm_supervision,
        stop_control_verified=args.confirm_stop_control);write_launch_decision(args.output,value)
    print(f"SUPERVISED_PAPER_LAUNCH_DECISION_WRITTEN:{args.output}")
    return 0


if __name__=="__main__":raise SystemExit(main())
