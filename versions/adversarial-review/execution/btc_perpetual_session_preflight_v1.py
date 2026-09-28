"""Pure, caller-supplied preflight for one supervised BTC perpetual paper command."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json
from pathlib import Path
from execution.btc_perpetual_paper_economics_policy_v1 import read_policy

from execution.paper_file_valuation_v1 import PaperSnapshotReferenceV1
from execution.paper_gateway_v2 import PaperGatewaySnapshotV1
from execution.strategy_paper_pretrade_v1 import PaperPretradePlanV1
from execution.supervised_btc_paper_runtime_v1 import (
    SupervisedPaperRuntimeInputV1, prepare_btc_perpetual_runtime_input,
)

VERSION="btc-perpetual-session-preflight-v1"


class BTCPerpetualSessionPreflightError(ValueError): pass


def _canonical(value):
    def encode(item):
        if isinstance(item,datetime): return item.isoformat()
        if isinstance(item,timedelta): return item.total_seconds()
        if isinstance(item,Decimal): return str(item)
        if isinstance(item,Enum): return item.value
        if hasattr(item,"__dataclass_fields__"):
            return {name:getattr(item,name) for name in item.__dataclass_fields__}
        raise TypeError(type(item).__name__)
    return json.dumps(value,sort_keys=True,separators=(",",":"),default=encode).encode()


@dataclass(frozen=True,slots=True)
class BTCPerpetualSessionPreflightV1:
    evaluated_at: datetime
    ready: bool
    blockers: tuple[str,...]
    runtime_input: SupervisedPaperRuntimeInputV1 | None
    plan_id: str
    gateway_snapshot_id: str
    source_sha256: str
    economics_policy_id: str
    report_id: str
    advisory_only: bool=True
    live_trading_permitted: bool=False
    trading_authority: bool=False

    def __post_init__(self):
        if (self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset()!=timedelta(0)
                or self.ready!=(not self.blockers) or self.ready!=(self.runtime_input is not None)
                or tuple(sorted(set(self.blockers)))!=self.blockers
                or self.advisory_only is not True or self.live_trading_permitted is not False
                or self.trading_authority is not False):
            raise BTCPerpetualSessionPreflightError("preflight report fields are invalid")
        body=(VERSION,self.evaluated_at,self.ready,self.blockers,self.runtime_input,self.plan_id,
            self.gateway_snapshot_id,self.source_sha256,self.economics_policy_id,True,False,False)
        if self.report_id!=hashlib.sha256(_canonical(body)).hexdigest():
            raise BTCPerpetualSessionPreflightError("preflight report identity mismatch")


def evaluate_btc_perpetual_session_preflight(*,plan:PaperPretradePlanV1,launch:dict,
        gateway:PaperGatewaySnapshotV1,reference:PaperSnapshotReferenceV1,
        economics_policy_path:Path,as_of:datetime,market_data_at:datetime)->BTCPerpetualSessionPreflightV1:
    if as_of.tzinfo is None or as_of.utcoffset()!=timedelta(0):
        raise BTCPerpetualSessionPreflightError("as_of must be UTC")
    blockers=[];runtime_input=None
    policy_id=""
    try:policy_id=read_policy(economics_policy_path)["policy_id"]
    except (OSError,TypeError,ValueError):blockers.append("ECONOMICS_POLICY_INVALID")
    try: gateway=PaperGatewaySnapshotV1.resume(gateway)
    except (TypeError,ValueError): blockers.append("GATEWAY_INTEGRITY_INVALID")
    else:
        if not gateway.connected: blockers.append("GATEWAY_DISCONNECTED")
        if gateway.kill_switch_active: blockers.append("KILL_SWITCH_ACTIVE")
        if gateway.reconciliation_required: blockers.append("RECONCILIATION_REQUIRED")
    if not isinstance(reference,PaperSnapshotReferenceV1):
        blockers.append("SNAPSHOT_REFERENCE_INVALID")
    elif reference.available_at>as_of or as_of-reference.available_at>timedelta(seconds=5):
        blockers.append("SNAPSHOT_NOT_CURRENT")
    if not blockers:
        try:
            runtime_input=prepare_btc_perpetual_runtime_input(plan=plan,launch=launch,
                reference=reference,expected_gateway_snapshot_id=gateway.snapshot_id,
                requested_at=as_of,market_data_at=market_data_at)
        except (TypeError,ValueError,RuntimeError):
            blockers.append("PLAN_LAUNCH_OR_RUNTIME_BINDING_INVALID")
    ordered=tuple(sorted(set(blockers)))
    plan_id=getattr(plan,"plan_id","")
    gateway_id=getattr(gateway,"snapshot_id","")
    source=getattr(reference,"sha256","")
    body=(VERSION,as_of,not ordered,ordered,runtime_input,plan_id,gateway_id,source,policy_id,True,False,False)
    report_id=hashlib.sha256(_canonical(body)).hexdigest()
    return BTCPerpetualSessionPreflightV1(as_of,not ordered,ordered,runtime_input,
        plan_id,gateway_id,source,policy_id,report_id,True,False,False)
