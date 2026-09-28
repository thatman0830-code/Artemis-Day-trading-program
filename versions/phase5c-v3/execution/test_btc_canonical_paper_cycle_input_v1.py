import pytest

from execution.btc_canonical_paper_cycle_input_v1 import BTCCanonicalPaperCycleInputV1
from execution.btc_canonical_strategy_worker_v1 import BTCCanonicalStrategyWorkerV1
from execution.btc_canonical_paper_cycle_input_v1 import BTCCanonicalPaperCycleInputError
from execution.test_btc_canonical_paper_reservation_bridge_v1 import running,actionable,T
from execution.test_btc_perpetual_paper_gateway_bridge_v1 import launch


def test_worker_to_reservation_to_runtime_input_is_single_issue(tmp_path):
    assembly=running(tmp_path);observation=actionable(assembly)
    worker=BTCCanonicalStrategyWorkerV1(archive_root=assembly.archive_root,
        snapshot_root=assembly.snapshot_root,status_path=tmp_path/"worker-status.json",
        evaluator=lambda **_:observation,
        probe=lambda **_:(observation.one_minute.reference.sha256,
            observation.five_minute.reference.sha256))
    decision=assembly.session.launch_decision
    permit=launch(T,launch_id=decision.launch_id,
        confirmation_id=assembly.session.confirmation.confirmation_id,
        maximum_order_notional="100",maximum_gross_exposure="100")
    reader=BTCCanonicalPaperCycleInputV1(assembly=assembly,worker=worker,launch=permit)
    first=reader(assembly=assembly,as_of=T)
    assert first.command is None
    worker._thread.join(timeout=5)
    second=reader(assembly=assembly,as_of=T)
    assert second.command is not None and second.strategy_intent is not None
    assert assembly.session.reservation.load()["body"]["state"]=="PREPARED"
    assert not assembly.session.workflow.store.load().gateway.records
    third=reader(assembly=assembly,as_of=T)
    assert third.command is None and reader.issued_observation_id==observation.observation_id


def test_cycle_input_source_has_no_provider_or_live_order_surface():
    source=__import__("inspect").getsource(
        __import__("execution.btc_canonical_paper_cycle_input_v1",fromlist=["*"])).lower()
    for prohibited in ("requests","urllib","websocket","private_key","submit_order","place_order"):
        assert prohibited not in source


def test_worker_failure_is_not_misreported_as_no_signal(tmp_path):
    assembly=running(tmp_path);observation=actionable(assembly)
    worker=BTCCanonicalStrategyWorkerV1(archive_root=assembly.archive_root,
        snapshot_root=assembly.snapshot_root,status_path=tmp_path/"worker-status.json",
        evaluator=lambda **_:(_ for _ in ()).throw(RuntimeError("failed")),
        probe=lambda **_:(observation.one_minute.reference.sha256,
            observation.five_minute.reference.sha256))
    decision=assembly.session.launch_decision
    permit=launch(T,launch_id=decision.launch_id,
        confirmation_id=assembly.session.confirmation.confirmation_id,
        maximum_order_notional="100",maximum_gross_exposure="100")
    reader=BTCCanonicalPaperCycleInputV1(assembly=assembly,worker=worker,launch=permit)
    assert reader(assembly=assembly,as_of=T).command is None
    worker._thread.join(timeout=5)
    with pytest.raises(BTCCanonicalPaperCycleInputError,match="evaluation failed"):
        reader(assembly=assembly,as_of=T)
