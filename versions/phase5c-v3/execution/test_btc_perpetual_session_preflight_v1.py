from dataclasses import replace
from datetime import timedelta

from execution.btc_perpetual_session_preflight_v1 import evaluate_btc_perpetual_session_preflight
from execution.paper_file_valuation_v1 import PaperSnapshotReferenceV1
from execution.test_btc_perpetual_paper_gateway_bridge_v1 import perpetual_components,launch
from execution.btc_perpetual_paper_economics_policy_v1 import APPROVAL,issue_policy,_canonical
import hashlib,json


def values(tmp_path):
    plan,gateway,now,_=perpetual_components(tmp_path)
    reference=PaperSnapshotReferenceV1("BTC_1m.csv",plan.strategy_intent.source_sha256,now)
    def artifact(path,id_name,body):
        doc={**body,id_name:hashlib.sha256(_canonical(body)).hexdigest()};path.write_bytes(_canonical(doc)+b"\n");return path
    l2=artifact(tmp_path/"l2.json","proposal_id",{"evidence_sufficient":True,"proposed_paper_only_values":{"maximum_order_notional_usd":"100","participation_limit_percent":"0.01","slippage_bps_per_fill":"2"},"trading_authority":False})
    econ=artifact(tmp_path/"econ.json","draft_id",{"facts":{"base_perpetual_taker_fee_bps":"4.5"},"trading_authority":False})
    policy=issue_policy(l2_proposal_path=l2,economics_draft_path=econ,owner_approval=APPROVAL);policy_path=tmp_path/"policy.json";policy_path.write_bytes(_canonical(policy)+b"\n")
    return dict(plan=plan,launch=launch(now),gateway=gateway,reference=reference,economics_policy_path=policy_path,
        as_of=now,market_data_at=now)


def test_ready_preflight_is_deterministic_advisory_and_non_mutating(tmp_path):
    args=values(tmp_path);before=args["gateway"]
    result=evaluate_btc_perpetual_session_preflight(**args)
    assert result.ready and not result.blockers and result.runtime_input is not None
    assert result==evaluate_btc_perpetual_session_preflight(**args)
    assert args["gateway"]==before and not before.records
    assert result.advisory_only and not result.live_trading_permitted and not result.trading_authority


def test_unhealthy_gateway_reports_exact_blockers_without_command(tmp_path):
    args=values(tmp_path)
    args["gateway"]=args["gateway"].disconnect().activate_kill_switch()
    result=evaluate_btc_perpetual_session_preflight(**args)
    assert not result.ready and result.runtime_input is None
    assert result.blockers==("GATEWAY_DISCONNECTED","KILL_SWITCH_ACTIVE","RECONCILIATION_REQUIRED")


def test_stale_snapshot_and_bad_launch_fail_closed(tmp_path):
    args=values(tmp_path);now=args["as_of"]
    args["reference"]=replace(args["reference"],available_at=now-timedelta(seconds=6))
    result=evaluate_btc_perpetual_session_preflight(**args)
    assert result.blockers==("SNAPSHOT_NOT_CURRENT",)
    args=values(tmp_path);args["launch"]["eligible"]=False
    result=evaluate_btc_perpetual_session_preflight(**args)
    assert result.blockers==("PLAN_LAUNCH_OR_RUNTIME_BINDING_INVALID",)

def test_missing_or_tampered_economics_policy_blocks(tmp_path):
    args=values(tmp_path);args["economics_policy_path"]=tmp_path/"missing.json"
    assert evaluate_btc_perpetual_session_preflight(**args).blockers==("ECONOMICS_POLICY_INVALID",)
