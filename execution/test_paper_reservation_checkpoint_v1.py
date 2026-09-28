from dataclasses import replace
import json

import pytest

from execution.paper_reservation_checkpoint_v1 import PaperReservationCheckpointV1, PaperReservationError, _hash
from execution.paper_performance_checkpoint_v1 import PaperPerformanceCheckpointStoreV1
from execution.paper_exchange_adapter_checkpoint_v1 import PaperAdapterCheckpointStoreV1
from execution.test_strategy_paper_pretrade_v1 import setup, rebuilt, D
from execution.test_supervised_paper_workflow_v1 import initial
from execution.strategy_paper_pretrade_v1 import plan_strategy_paper_pretrade
from execution.paper_gateway_v2 import PaperSubmissionV1
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.test_paper_performance_ledger_v1 import H


def fixture(tmp_path):
    args=setup()
    PaperAdapterCheckpointStoreV1(tmp_path/"adapter-checkpoint.json").initialize(initial())
    PaperPerformanceCheckpointStoreV1(tmp_path/"performance-checkpoint.json").initialize(args["performance"])
    store=PaperReservationCheckpointV1(tmp_path,"a"*32)
    empty=store.initialize()
    return store,args,empty["checkpoint_id"]


def test_prepare_reload_and_idempotent_retry_without_adapter_change(tmp_path):
    store,args,expected=fixture(tmp_path)
    before=(tmp_path/"adapter-checkpoint.json").read_bytes()
    prepared=store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    assert prepared["body"]["state"]=="PREPARED"
    assert D(prepared["body"]["reservation"]["reserved_cash"])==D("101.5")
    assert prepared["body"]["submission_authorized"] is False
    assert prepared["body"]["trading_authority"] is False
    reopened=PaperReservationCheckpointV1(tmp_path,"a"*32)
    assert reopened.load()==prepared
    assert reopened.prepare(pretrade_inputs=args,expected_checkpoint_id=prepared["checkpoint_id"])==prepared
    assert (tmp_path/"adapter-checkpoint.json").read_bytes()==before
    assert not store.lock_path.exists()


def test_prepared_reservation_commits_only_from_durable_accepted_order(tmp_path):
    store,args,expected=fixture(tmp_path)
    prepared=store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    plan=plan_strategy_paper_pretrade(**args);intent=plan.strategy_intent.intent
    submission=PaperSubmissionV1(H("reservation-submission"),intent,intent.limit_price,
        intent.submitted_at,intent.submitted_at,H("reservation-authorization"),True,False)
    command=PaperAdapterCommandV1(H("reservation-command"),args["gateway"].snapshot_id,
        submission=submission)
    PaperAdapterCheckpointStoreV1(tmp_path/"adapter-checkpoint.json").execute(command)
    committed=store.commit(expected_checkpoint_id=prepared["checkpoint_id"])
    assert committed["body"]["state"]=="COMMITTED"
    assert committed["body"]["reservation"]["order_id"]==intent.order_id
    assert store.commit(expected_checkpoint_id=committed["checkpoint_id"])==committed


def test_commit_without_durable_acceptance_fails_closed(tmp_path):
    store,args,expected=fixture(tmp_path)
    prepared=store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    with pytest.raises(PaperReservationError,match="unique durable accepted"):
        store.commit(expected_checkpoint_id=prepared["checkpoint_id"])
    assert store.load()==prepared


def test_startup_reconciliation_classifies_empty_and_prepared_without_order(tmp_path):
    store,args,expected=fixture(tmp_path)
    empty=store.reconcile()
    assert empty.state=="EMPTY" and not empty.order_present and not empty.recovery_applied
    prepared=store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    waiting=store.reconcile()
    assert waiting.state=="PREPARED_NO_ORDER" and waiting.checkpoint_id==prepared["checkpoint_id"]


def test_startup_reconciliation_recovers_and_revalidates_commit(tmp_path):
    store,args,expected=fixture(tmp_path)
    store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    plan=plan_strategy_paper_pretrade(**args);intent=plan.strategy_intent.intent
    submission=PaperSubmissionV1(H("reconcile-submission"),intent,intent.limit_price,
        intent.submitted_at,intent.submitted_at,H("reconcile-authorization"),True,False)
    command=PaperAdapterCommandV1(H("reconcile-command"),args["gateway"].snapshot_id,
        submission=submission)
    adapter_store=PaperAdapterCheckpointStoreV1(tmp_path/"adapter-checkpoint.json")
    adapter_store.execute(command);adapter=adapter_store.load()
    performance_store=PaperPerformanceCheckpointStoreV1(tmp_path/"performance-checkpoint.json")
    before=performance_store.load();after=before.reconcile_gateway(adapter.gateway)
    performance_store.save(after,expected_ledger_id=before.ledger_id)
    recovered=store.reconcile()
    assert recovered.state=="COMMITTED" and recovered.order_present and recovered.recovery_applied
    stable=store.reconcile()
    assert stable.state=="COMMITTED" and stable.order_present and not stable.recovery_applied


@pytest.mark.parametrize("after_replace",[False,True])
def test_interrupted_commit_acknowledgement_recovers_from_durable_order(tmp_path,monkeypatch,after_replace):
    import execution.paper_reservation_checkpoint_v1 as module
    store,args,expected=fixture(tmp_path)
    prepared=store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    plan=plan_strategy_paper_pretrade(**args);intent=plan.strategy_intent.intent
    submission=PaperSubmissionV1(H("interrupted-submission"),intent,intent.limit_price,
        intent.submitted_at,intent.submitted_at,H("interrupted-authorization"),True,False)
    command=PaperAdapterCommandV1(H("interrupted-command"),args["gateway"].snapshot_id,
        submission=submission)
    PaperAdapterCheckpointStoreV1(tmp_path/"adapter-checkpoint.json").execute(command)
    real=module.os.replace
    def fail(source,target):
        if after_replace:real(source,target)
        raise OSError("simulated interrupted commitment acknowledgement")
    with monkeypatch.context() as patch:
        patch.setattr(module.os,"replace",fail)
        with pytest.raises(OSError):store.commit(expected_checkpoint_id=prepared["checkpoint_id"])
    recovered=store.load()
    assert recovered["body"]["state"]==("COMMITTED" if after_replace else "PREPARED")
    committed=store.commit(expected_checkpoint_id=recovered["checkpoint_id"])
    assert committed["body"]["state"]=="COMMITTED"


def test_duplicate_conflict_and_stale_cas_preserve_original(tmp_path):
    store,args,expected=fixture(tmp_path)
    prepared=store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    original=store.path.read_bytes()
    with pytest.raises(PaperReservationError,match="compare-and-swap"):
        store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    args["sizing_policy"]=replace(args["sizing_policy"],maximum_planned_loss=D("1.006"))
    with pytest.raises(PaperReservationError,match="reservation conflict"):
        store.prepare(pretrade_inputs=args,expected_checkpoint_id=prepared["checkpoint_id"])
    assert store.path.read_bytes()==original


def test_risk_rejection_does_not_reserve(tmp_path):
    store,args,expected=fixture(tmp_path)
    args["limits"]=rebuilt(args["limits"],max_gross_exposure=D(1))
    with pytest.raises(PaperReservationError,match="risk rejected"):
        store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    assert store.load()["body"]["state"]=="EMPTY"


def test_changed_durable_gateway_blocks_cached_plan(tmp_path):
    store,args,expected=fixture(tmp_path)
    PaperAdapterCheckpointStoreV1(tmp_path/"adapter-checkpoint.json").halt()
    with pytest.raises(PaperReservationError,match="durable checkpoints"):
        store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    assert store.load()["body"]["state"]=="EMPTY"


def test_writer_lock_is_not_removed_by_competing_writer(tmp_path):
    store,args,expected=fixture(tmp_path)
    store.lock_path.write_text("retained lock")
    with pytest.raises(PaperReservationError,match="writer lock"):
        store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    assert store.lock_path.read_text()=="retained lock"


@pytest.mark.parametrize("after_replace",[False,True])
def test_write_failure_before_or_after_atomic_replace(tmp_path,monkeypatch,after_replace):
    import execution.paper_reservation_checkpoint_v1 as module
    store,args,expected=fixture(tmp_path)
    real=module.os.replace
    def fail(source,target):
        if after_replace: real(source,target)
        raise OSError("simulated interrupted acknowledgement")
    with monkeypatch.context() as patch:
        patch.setattr(module.os,"replace",fail)
        with pytest.raises(OSError): store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    recovered=store.load()
    assert recovered["body"]["state"]==("PREPARED" if after_replace else "EMPTY")
    confirmed=store.prepare(pretrade_inputs=args,expected_checkpoint_id=recovered["checkpoint_id"])
    assert confirmed["body"]["state"]=="PREPARED"
    assert not store.lock_path.exists()
    assert not list(tmp_path.glob(".reservation-*.tmp"))


@pytest.mark.parametrize("fault",["missing","corrupt","duplicate","oversized","authority","quantity"])
def test_corrupt_or_missing_checkpoint_never_resets(tmp_path,fault):
    store,args,expected=fixture(tmp_path)
    prepared=store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    if fault=="missing": store.path.unlink()
    elif fault=="corrupt": store.path.write_bytes(b"bad")
    elif fault=="duplicate": store.path.write_bytes(b'{"body":{},"body":{}}')
    elif fault=="oversized": store.path.write_bytes(b"x"*16385)
    else:
        if fault=="authority": prepared["body"]["submission_authorized"]=True
        else: prepared["body"]["reservation"]["quantity"]="NaN"
        prepared["checkpoint_id"]=_hash(prepared["body"])
        store.path.write_text(json.dumps(prepared))
    with pytest.raises(PaperReservationError):
        store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    assert not store.lock_path.exists()


def test_reinitialization_and_session_relabel_reject(tmp_path):
    store,_,_=fixture(tmp_path)
    with pytest.raises(PaperReservationError,match="already exists"): store.initialize()
    with pytest.raises(PaperReservationError,match="session"):
        PaperReservationCheckpointV1(tmp_path,"b"*32).load()


def test_checkpoint_change_during_preparation_rejects(tmp_path,monkeypatch):
    import execution.paper_reservation_checkpoint_v1 as module
    store,args,expected=fixture(tmp_path)
    original=module.plan_strategy_paper_pretrade
    def changed(**kwargs):
        result=original(**kwargs)
        PaperAdapterCheckpointStoreV1(tmp_path/"adapter-checkpoint.json").halt()
        return result
    monkeypatch.setattr(module,"plan_strategy_paper_pretrade",changed)
    with pytest.raises(PaperReservationError,match="changed during"):
        store.prepare(pretrade_inputs=args,expected_checkpoint_id=expected)
    assert store.load()["body"]["state"]=="EMPTY"
