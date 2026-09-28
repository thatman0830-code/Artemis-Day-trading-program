from dataclasses import replace
from datetime import timedelta
import hashlib,json

import pytest

from backtesting.orchestrator import EvaluationOutcome
from execution.btc_canonical_paper_reservation_bridge_v1 import (
    BTCCanonicalPaperReservationError,prepare_btc_canonical_paper_reservation,
    prepare_reserved_btc_paper_runtime_input,
)
from execution.btc_canonical_strategy_observation_v1 import observe_btc_canonical_strategy,_observation
from execution.test_supervised_btc_paper_session_assembly_v1 import prepared,T
from execution.test_supervised_paper_launch_evidence_v1 import document
from strategy.trading_brain.test_p29_1_entry_execution import inputs


def actionable(assembly):
    observed=observe_btc_canonical_strategy(archive_root=assembly.archive_root,
        snapshot_root=assembly.snapshot_root,as_of=T)
    q,s,_,_=inputs();ms=int(T.timestamp()*1000)
    q=replace(q,finalized_time=ms)
    s=replace(s,eligibility_time=ms-1000,selection_time=ms-1000,minimum_tick=assembly.economic_gate.instrument.tick_size)
    fact=replace(observed.result.setup_fact,entry_zone=s,final_qualification=q,evaluation_time=T)
    result=replace(observed.result,outcome=EvaluationOutcome.ARMED_CONTINUATION,
        setup_fact=fact,context=replace(observed.result.context,evaluation_time=T))
    return _observation(observed.one_minute,observed.five_minute,result,observed.candle_count)


def running(tmp_path):
    assembly,_=prepared(tmp_path)
    import execution.test_btc_canonical_strategy_observation_v1 as canonical_fixture
    canonical_fixture.BASE=T-timedelta(minutes=15)
    strategy_archive=tmp_path/"strategy-archive";canonical_fixture.archive(strategy_archive)
    values=dict(economics_policy_path=tmp_path/"economics-policy.json",risk_policy_path=tmp_path/"risk.json",
        public_evidence_root=tmp_path/"public",public_evidence_receipt_path=next((tmp_path/"public").glob("*.receipt.json")))
    from execution.btc_perpetual_paper_specification_bundle_v1 import compile_paper_specification_bundle
    bundle=tmp_path/"paper-bundle.json";compile_paper_specification_bundle(**values,as_of=T,output_path=bundle)
    from execution.supervised_btc_paper_session_assembly_v1 import assemble_supervised_btc_paper_session
    assembly=assemble_supervised_btc_paper_session(session_root=tmp_path/"running",archive_root=strategy_archive,
        evidence_path=tmp_path/"launch-evidence.json",confirmation=assembly.session.confirmation,
        expected_checkpoint="a"*64,session_id="9"*32,**values,as_of=T,paper_specification_bundle_path=bundle)
    evidence=document();evidence.update(collected_at=T.isoformat(),btc_heartbeat_at=T.isoformat(),
        repository_checkpoint="a"*64);evidence.pop("evidence_id")
    evidence["evidence_id"]=hashlib.sha256(json.dumps(evidence,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    (tmp_path/"launch-evidence.json").write_text(json.dumps(evidence))
    assembly.session.start(T)
    return assembly


def test_actionable_observation_creates_prepared_only_durable_reservation(tmp_path):
    assembly=running(tmp_path);observation=actionable(assembly)
    empty=assembly.session.reservation.load()
    result=prepare_btc_canonical_paper_reservation(assembly=assembly,observation=observation,as_of=T,
        expected_reservation_checkpoint_id=empty["checkpoint_id"])
    durable=assembly.session.reservation.load()
    assert durable["body"]["state"]=="PREPARED"
    assert durable["body"]["submission_authorized"] is False
    assert result.trading_authority is False
    assert not assembly.session.workflow.store.load().gateway.records
    replay=prepare_btc_canonical_paper_reservation(assembly=assembly,observation=observation,as_of=T,
        expected_reservation_checkpoint_id=result.checkpoint_id)
    assert replay==result


def test_nonactionable_observation_and_stale_public_evidence_fail_closed(tmp_path):
    assembly=running(tmp_path)
    observed=observe_btc_canonical_strategy(archive_root=assembly.archive_root,
        snapshot_root=tmp_path/"nonactionable",as_of=T)
    with pytest.raises(BTCCanonicalPaperReservationError,match="not actionable"):
        prepare_btc_canonical_paper_reservation(assembly=assembly,observation=observed,as_of=T,
            expected_reservation_checkpoint_id=assembly.session.reservation.load()["checkpoint_id"])
    with pytest.raises(BTCCanonicalPaperReservationError,match="fresh public"):
        prepare_btc_canonical_paper_reservation(assembly=assembly,observation=actionable(assembly),
            as_of=T+timedelta(seconds=61),expected_reservation_checkpoint_id=assembly.session.reservation.load()["checkpoint_id"])


def test_exact_current_reservation_forms_snapshot_bound_runtime_command(tmp_path):
    from execution.test_btc_perpetual_paper_gateway_bridge_v1 import launch
    assembly=running(tmp_path);observation=actionable(assembly)
    empty=assembly.session.reservation.load()
    reservation=prepare_btc_canonical_paper_reservation(assembly=assembly,observation=observation,as_of=T,
        expected_reservation_checkpoint_id=empty["checkpoint_id"])
    decision=assembly.session.launch_decision
    permit=launch(T,launch_id=decision.launch_id,
        confirmation_id=assembly.session.confirmation.confirmation_id,
        maximum_order_notional="100",maximum_gross_exposure="100")
    runtime_input=prepare_reserved_btc_paper_runtime_input(assembly=assembly,reservation=reservation,
        launch=permit,requested_at=T)
    assert runtime_input.reference==reservation.reference
    assert runtime_input.strategy_intent==reservation.plan.strategy_intent
    assert runtime_input.command.submission.intent==reservation.plan.strategy_intent.intent
    assert not assembly.session.workflow.store.load().gateway.records
    with pytest.raises(BTCCanonicalPaperReservationError,match="reservation identity"):
        prepare_reserved_btc_paper_runtime_input(assembly=assembly,
            reservation=replace(reservation,checkpoint_id="f"*64),launch=permit,requested_at=T)
    altered=launch(T,launch_id=decision.launch_id,
        confirmation_id=assembly.session.confirmation.confirmation_id,
        maximum_order_notional="100",maximum_gross_exposure="100",maximum_commands=4)
    with pytest.raises(BTCCanonicalPaperReservationError,match="launch limits"):
        prepare_reserved_btc_paper_runtime_input(assembly=assembly,reservation=reservation,
            launch=altered,requested_at=T)


def test_bridge_has_no_submission_or_network_surface():
    source=__import__("inspect").getsource(
        __import__("execution.btc_canonical_paper_reservation_bridge_v1",fromlist=["*"])).lower()
    for prohibited in ("requests","urllib","websocket","private_key","submit_order","place_order"):
        assert prohibited not in source
    assert "trading authority" in source
