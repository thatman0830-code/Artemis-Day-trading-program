"""End-to-end local acceptance of one supervised BTC perpetual paper entry."""
from execution.btc_canonical_paper_cycle_input_v1 import BTCCanonicalPaperCycleInputV1
from execution.btc_canonical_strategy_worker_v1 import BTCCanonicalStrategyWorkerV1
from execution.supervised_paper_workflow_v1 import SupervisedPaperCycleV1
from execution.test_btc_canonical_paper_reservation_bridge_v1 import running,actionable,T
from execution.test_btc_perpetual_paper_gateway_bridge_v1 import launch


def test_actionable_worker_result_reaches_durable_gateway_then_controlled_stop(tmp_path):
    assembly=running(tmp_path);observation=actionable(assembly)
    worker=BTCCanonicalStrategyWorkerV1(archive_root=assembly.archive_root,
        snapshot_root=assembly.snapshot_root,status_path=tmp_path/"strategy-status.json",
        evaluator=lambda **_:observation,
        probe=lambda **_:(observation.one_minute.reference.sha256,
            observation.five_minute.reference.sha256))
    decision=assembly.session.launch_decision
    permit=launch(T,launch_id=decision.launch_id,
        confirmation_id=assembly.session.confirmation.confirmation_id,
        maximum_order_notional="100",maximum_gross_exposure="100")
    reader=BTCCanonicalPaperCycleInputV1(assembly=assembly,worker=worker,launch=permit)

    pending=reader(assembly=assembly,as_of=T)
    assert pending.command is None
    worker._thread.join(timeout=5)
    admitted=reader(assembly=assembly,as_of=T)
    assert admitted.command is not None

    adapter,receipt,health,performance=assembly.session.step(
        SupervisedPaperCycleV1(T,T,admitted.command))
    assert receipt.accepted is True
    assert len(adapter.gateway.records)==1
    record=adapter.gateway.records[0]
    assert record.order_id==admitted.strategy_intent.intent.order_id
    assert record.market=="BTC-PERP"
    assert admitted.strategy_intent.intent.instrument_id=="BTC"
    assert performance.gateway_snapshot_id==adapter.gateway.snapshot_id
    assert not performance.accounting.events
    assert health.state.value=="HEALTHY" and health.trading_authority is False
    assert assembly.session.workflow.store.load()==adapter
    assert assembly.session.bridge.store.load()==performance
    reservation=assembly.session.reservation.load()
    assert reservation["body"]["state"]=="COMMITTED"
    assert reservation["body"]["reservation"]["order_id"]==record.order_id
    assert reservation["body"]["reservation"]["paper_order_id"]==record.paper_order_id
    assert assembly.session.reservation.commit(
        expected_checkpoint_id=reservation["checkpoint_id"])==reservation

    stopped=assembly.session.stop(T)
    assert stopped.state=="STOPPED" and stopped.commands==1
    assert stopped.trading_authority is False and not assembly.session.active
    assert not assembly.session.workflow.lock_path.exists()
