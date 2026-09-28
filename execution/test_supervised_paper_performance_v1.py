from datetime import timedelta
from dataclasses import replace
import json
from decimal import Decimal

import pytest

from backtesting.execution_accounting_v2.accounting import PriceEvidenceV2
from execution.paper_exchange_adapter_v1 import PaperAdapterCommandV1
from execution.paper_performance_ledger_v1 import PaperPerformanceLedgerV1
from execution.supervised_paper_performance_v1 import (
    PaperPerformanceHaltUnconfirmedError,
    SupervisedPaperPerformanceError, SupervisedPaperPerformanceV1,
    VerifiedPaperFillV1,
)
from execution.supervised_paper_workflow_v1 import (
    SupervisedPaperCycleV1, SupervisedPaperPolicyV1, SupervisedPaperState,
    SupervisedPaperWorkflowV1,
)
from execution.test_paper_performance_ledger_v1 import T, H, accounting, gateway_fill
from execution.test_supervised_paper_workflow_v1 import initial


def coordinator(tmp_path, session="1" * 32):
    workflow = SupervisedPaperWorkflowV1(tmp_path,
        SupervisedPaperPolicyV1(timedelta(seconds=5)), initial(), session)
    workflow.acquire()
    return workflow, SupervisedPaperPerformanceV1(workflow, accounting())


def test_start_creates_atomic_performance_checkpoint(tmp_path):
    workflow, item = coordinator(tmp_path)
    try:
        adapter, ledger = item.start()
        assert item.store.load() == ledger
        assert ledger.gateway_snapshot_id == adapter.gateway.snapshot_id
        assert ledger.trading_authority is False
    finally:
        workflow.release()


def test_verified_fill_and_closed_mark_persist_and_reconcile(tmp_path):
    workflow, item = coordinator(tmp_path)
    try:
        adapter, _ = item.start()
        gateway, event, fill, costs = gateway_fill()
        # Use the evidence-producing gateway as the exact durable starting state.
        workflow.store.path.unlink()
        workflow.store.initialize(type(adapter).create(gateway))
        item.store.path.unlink()
        item.store.initialize(PaperPerformanceLedgerV1.create(accounting(), gateway))
        command = PaperAdapterCommandV1(H("fill-command"), gateway.snapshot_id,
                                        event=event)
        mark = PriceEvidenceV2("price-evidence-v2-1", H("cycle-mark"),
            "BTC", "BTC", None, T + timedelta(minutes=15),
            T + timedelta(minutes=15), Decimal("51000"), "MARK",
            H("mark-spec"), "btc-15m-archive-v1")
        updated, receipt, _, ledger = item.cycle(
            SupervisedPaperCycleV1(T + timedelta(minutes=15),
                                   T + timedelta(minutes=15), command),
            verified_fill=VerifiedPaperFillV1(event, fill, costs),
            closed_mark=mark)
        assert receipt.accepted
        assert item.store.load() == ledger
        assert ledger.gateway_snapshot_id == updated.gateway.snapshot_id
        assert ledger.snapshot.position.signed_quantity == Decimal("0.1")
        assert ledger.snapshot.equity == Decimal("10097")
    finally:
        workflow.release()


def test_accepted_fill_without_evidence_halts_durably(tmp_path):
    workflow, item = coordinator(tmp_path)
    try:
        adapter, _ = item.start()
        gateway, event, _, _ = gateway_fill()
        workflow.store.path.unlink()
        workflow.store.initialize(type(adapter).create(gateway))
        item.store.path.unlink()
        item.store.initialize(PaperPerformanceLedgerV1.create(accounting(), gateway))
        command = PaperAdapterCommandV1(H("missing-fill-command"),
                                        gateway.snapshot_id, event=event)
        with pytest.raises(SupervisedPaperPerformanceError, match="must correspond"):
            item.cycle(SupervisedPaperCycleV1(T, T, command))
        halted = workflow.store.load()
        assert halted.gateway.kill_switch_active
        assert not halted.gateway.connected
        assert SupervisedPaperState.HALTED_PERFORMANCE_PERSISTENCE.value in workflow.health_path.read_text("utf-8")
        assert workflow.alerts_path.is_file()
    finally:
        workflow.release()


def test_checkpoint_write_conflict_halts_adapter(tmp_path):
    workflow, item = coordinator(tmp_path)
    try:
        item.start()
        item.store.lock_path.write_text("held", "utf-8")
        mark = PriceEvidenceV2("price-evidence-v2-1", H("locked-mark"),
            "BTC", "BTC", None, T, T, Decimal("50000"), "MARK",
            H("mark-spec"), "btc-15m-archive-v1")
        with pytest.raises(SupervisedPaperPerformanceError, match="failed closed"):
            item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
        assert workflow.store.load().gateway.kill_switch_active
    finally:
        item.store.lock_path.unlink(missing_ok=True)
        workflow.release()


def test_restart_reconciles_both_checkpoints(tmp_path):
    first, item = coordinator(tmp_path, "1" * 32)
    item.start(); first.release()
    second = SupervisedPaperWorkflowV1(tmp_path,
        SupervisedPaperPolicyV1(timedelta(seconds=5)), initial(), "2" * 32)
    second.acquire()
    restarted = SupervisedPaperPerformanceV1(second, accounting())
    try:
        adapter, ledger = restarted.start()
        assert ledger.gateway_snapshot_id == adapter.gateway.snapshot_id
        assert ledger == restarted.store.load()
    finally:
        second.release()


def test_module_has_no_network_credentials_or_live_submission():
    from pathlib import Path
    source = Path(__file__).with_name(
        "supervised_paper_performance_v1.py").read_text("utf-8").lower()
    for word in ("requests", "httpx", "socket", "websocket", "private_key",
                 "api_key", "submit_live", "place_order", "subprocess"):
        assert word not in source


@pytest.mark.parametrize("observed,available", [(15, 15), (0, 15)])
def test_future_mark_rejected_without_persisting(tmp_path, observed, available):
    wf, item = coordinator(tmp_path)
    try:
        item.start()
        before = item.store.path.read_bytes()
        mark = PriceEvidenceV2("price-evidence-v2-1", H("future"), "BTC", "BTC",
            None, T + timedelta(minutes=observed), T + timedelta(minutes=available),
            Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
        with pytest.raises(SupervisedPaperPerformanceError, match="future"):
            item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
        assert item.store.path.read_bytes() == before
        assert wf.store.load().gateway.kill_switch_active
        assert not wf.store.load().gateway.connected
        assert json.loads(wf.health_path.read_text())["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
        alert = json.loads(wf.alerts_path.read_text().splitlines()[-1])
        assert alert["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
        assert alert["session_id"] == wf.session_id
        assert alert["kill_switch_active"] is True
    finally:
        wf.release()


def test_mark_equal_to_cycle_time_is_accepted(tmp_path):
    wf, item = coordinator(tmp_path)
    try:
        item.start()
        mark = PriceEvidenceV2("price-evidence-v2-1", H("equal"), "BTC", "BTC",
            None, T, T, Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
        _, _, _, ledger = item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
        assert item.store.load() == ledger
        assert ledger.snapshot.position.mark_price == Decimal("51000")
    finally:
        wf.release()


@pytest.mark.parametrize("existing", [False, True])
def test_startup_missing_accounted_fill_halts(tmp_path, existing):
    from execution.paper_exchange_adapter_v1 import PaperExchangeAdapterV1
    wf, item = coordinator(tmp_path)
    gateway, _, _, _ = gateway_fill()
    wf.initial = PaperExchangeAdapterV1.create(gateway)
    try:
        if existing:
            item.store.initialize(PaperPerformanceLedgerV1.create(accounting(), gateway))
        with pytest.raises(SupervisedPaperPerformanceError, match="startup"):
            item.start()
        assert item.store.path.exists() == existing
        halted = wf.store.load().gateway
        assert halted.records == gateway.records
        assert halted.kill_switch_active and not halted.connected
    finally:
        wf.release()


def prepared_fill(tmp_path):
    from execution.paper_exchange_adapter_v1 import PaperExchangeAdapterV1
    from execution.paper_gateway_v2 import PaperGatewaySnapshotV1, PaperSubmissionV1
    from backtesting.execution_accounting_v2.contracts import (
        OrderIntentV2, OrderType, TimeInForce,
    )
    wf, item = coordinator(tmp_path)
    filled_gateway, event, fill, costs = gateway_fill()
    wf.initial = PaperExchangeAdapterV1.create(
        PaperGatewaySnapshotV1.create(filled_gateway.policy))
    adapter, _ = item.start()
    intent = OrderIntentV2("order-intent-v2-1", fill.order_id, H("run"), H("action"),
        "BTC", "BTC", None, fill.side, fill.quantity, OrderType.MARKET,
        TimeInForce.IOC, None, None, T, T, None, None, None,
        "paper-config-v1", "paper-execution-v1")
    request = PaperSubmissionV1(H("submission"), intent, fill.economic_price,
        T, T, H("authorization"), True, False)
    command = PaperAdapterCommandV1(H("submit"), adapter.gateway.snapshot_id,
        submission=request)
    adapter, receipt, _, _ = item.cycle(SupervisedPaperCycleV1(T, T, command))
    assert receipt.accepted
    event = replace(event, paper_order_id=adapter.gateway.records[0].paper_order_id)
    command = PaperAdapterCommandV1(H("new-fill"), adapter.gateway.snapshot_id, event=event)
    return wf, item, SupervisedPaperCycleV1(event.occurred_at, event.occurred_at, command), VerifiedPaperFillV1(event, fill, costs)


@pytest.mark.parametrize("after_replace", [False, True])
def test_power_loss_between_checkpoints_requires_restart_reconciliation(tmp_path, monkeypatch, after_replace):
    class PowerLoss(BaseException):
        pass
    wf, item, cycle, evidence = prepared_fill(tmp_path)
    save = item.store.save
    def interrupted(ledger, **kwargs):
        if after_replace:
            save(ledger, **kwargs)
        raise PowerLoss()
    monkeypatch.setattr(item.store, "save", interrupted)
    try:
        with pytest.raises(PowerLoss):
            item.cycle(cycle, verified_fill=evidence)
        assert wf.store.load().gateway.records[0].filled_quantity == evidence.fill.quantity
    finally:
        wf.release()
    restarted_wf, restarted = coordinator(tmp_path, "2" * 32)
    try:
        if after_replace:
            adapter, ledger = restarted.start()
            assert adapter.gateway.reconciliation_required
            assert not adapter.gateway.connected
            assert len(ledger.fill_bindings) == 1
            assert ledger.snapshot.total_costs == evidence.economics.total
        else:
            with pytest.raises(SupervisedPaperPerformanceError, match="startup"):
                restarted.start()
            assert restarted_wf.store.load().gateway.kill_switch_active
            assert len(restarted.store.load().fill_bindings) == 0
    finally:
        restarted_wf.release()


def test_failed_halt_is_explicit_and_coordinator_latched(tmp_path, monkeypatch):
    wf, item = coordinator(tmp_path)
    try:
        item.start()
        item.store.path.write_bytes(b"corrupt")
        def cannot_halt():
            raise OSError("simulated disk failure")
        monkeypatch.setattr(wf.store, "halt", cannot_halt)
        with pytest.raises(PaperPerformanceHaltUnconfirmedError, match="unconfirmed") as error:
            item.cycle(SupervisedPaperCycleV1(T, T))
        assert isinstance(error.value.__cause__, OSError)
        with pytest.raises(SupervisedPaperPerformanceError, match="latched"):
            item.cycle(SupervisedPaperCycleV1(T, T))
        assert not wf.store.load().gateway.kill_switch_active
    finally:
        wf.release()


def test_replay_after_gateway_change_never_duplicates_accounting(tmp_path):
    wf, item, cycle, evidence = prepared_fill(tmp_path)
    try:
        _, _, _, ledger = item.cycle(cycle, verified_fill=evidence)
        disconnected = wf.store.restart()
        assert not disconnected.gateway.connected
        assert disconnected.gateway.reconciliation_required
        assert disconnected.gateway.snapshot_id != ledger.gateway_snapshot_id
        # Reconnect using exact retained records, creating intervening snapshots.
        adapter = wf.store.load()
        observations = tuple((r.paper_order_id, r.state, r.filled_quantity,
            r.remaining_quantity, r.version) for r in adapter.gateway.records)
        recovered, _, health, _ = item.cycle(SupervisedPaperCycleV1(cycle.now, cycle.now,
            reconciliation_observation=observations))
        assert recovered.gateway.connected
        assert not recovered.gateway.reconciliation_required
        assert health.state is SupervisedPaperState.HEALTHY
        _, _, _, replayed = item.cycle(cycle, verified_fill=evidence)
        assert replayed.accounting == ledger.accounting
        assert replayed.fill_bindings == ledger.fill_bindings
        assert item.store.load() == replayed
    finally:
        wf.release()


def test_replay_after_actual_additional_order_rejects_without_duplicate_fill(tmp_path):
    from execution.paper_gateway_v2 import PaperSubmissionV1
    from backtesting.execution_accounting_v2.contracts import (
        OrderIntentV2, OrderType, TimeInForce,
    )
    wf, item, cycle, evidence = prepared_fill(tmp_path)
    try:
        adapter, _, _, filled = item.cycle(cycle, verified_fill=evidence)
        intent = OrderIntentV2("order-intent-v2-1", H("second-order"), H("run"),
            H("second-action"), "BTC", "BTC", None, evidence.fill.side,
            Decimal("0.01"), OrderType.MARKET, TimeInForce.IOC, None, None,
            cycle.now, cycle.now, None, None, None, "paper-config-v1", "paper-execution-v1")
        request = PaperSubmissionV1(H("second-key"), intent, evidence.fill.economic_price,
            cycle.now, cycle.now, H("second-authorization"), True, False)
        command = PaperAdapterCommandV1(H("second-command"), adapter.gateway.snapshot_id,
            submission=request)
        changed, receipt, _, ledger = item.cycle(
            SupervisedPaperCycleV1(cycle.now, cycle.now, command))
        assert receipt.accepted
        assert len(changed.gateway.records) == 2
        assert changed.gateway.snapshot_id != adapter.gateway.snapshot_id
        assert ledger.accounting == filled.accounting
        before = item.store.path.read_bytes()
        # Ledger binding includes the original gateway snapshot: later-snapshot
        # replay safely rejects, rather than promising transparent idempotence.
        with pytest.raises(SupervisedPaperPerformanceError, match="failed closed") as error:
            item.cycle(cycle, verified_fill=evidence)
        assert "paper fill replay conflicts" in str(error.value.__cause__)
        assert item.store.path.read_bytes() == before
        assert item.store.load().fill_bindings == filled.fill_bindings
        assert item.store.load().snapshot.total_costs == evidence.economics.total
        halted = wf.store.load().gateway
        assert halted.records == changed.gateway.records
        assert halted.kill_switch_active and not halted.connected
    finally:
        wf.release()


@pytest.mark.parametrize("failed_writer", ["_write_health", "_append_alert"])
def test_health_and_alert_failure_are_separately_unconfirmed(tmp_path, monkeypatch, failed_writer):
    wf, item = coordinator(tmp_path)
    try:
        item.start()
        before = item.store.path.read_bytes()
        def cannot_write(*args, **kwargs):
            raise OSError("injected " + failed_writer + " failure")
        monkeypatch.setattr(wf, failed_writer, cannot_write)
        mark = PriceEvidenceV2("price-evidence-v2-1", H("future-write-failure"),
            "BTC", "BTC", None, T + timedelta(minutes=1), T + timedelta(minutes=1),
            Decimal("51000"), "MARK", H("mark-spec"), "btc-15m-archive-v1")
        with pytest.raises(PaperPerformanceHaltUnconfirmedError, match="unconfirmed") as error:
            item.cycle(SupervisedPaperCycleV1(T, T), closed_mark=mark)
        assert isinstance(error.value.__cause__, OSError)
        assert failed_writer in str(error.value.__cause__)
        halted = wf.store.load().gateway
        assert halted.kill_switch_active and not halted.connected
        assert item.store.path.read_bytes() == before
        assert not wf.alerts_path.exists()
        if failed_writer == "_write_health":
            assert not wf.health_path.exists()
        else:
            health = json.loads(wf.health_path.read_text())
            assert health["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
            assert health["gateway_snapshot_id"] == halted.snapshot_id
        with pytest.raises(SupervisedPaperPerformanceError, match="latched"):
            item.start()
        with pytest.raises(SupervisedPaperPerformanceError, match="latched"):
            item.cycle(SupervisedPaperCycleV1(T, T))
    finally:
        wf.release()


@pytest.mark.parametrize("after_replace", [False, True])
def test_write_error_before_or_after_replace_publishes_halt(tmp_path, monkeypatch, after_replace):
    wf, item, cycle, evidence = prepared_fill(tmp_path)
    replace_locked = item.store._replace_locked
    def failing_replace(ledger):
        if after_replace:
            replace_locked(ledger)
        raise OSError("injected checkpoint write failure")
    monkeypatch.setattr(item.store, "_replace_locked", failing_replace)
    try:
        with pytest.raises(SupervisedPaperPerformanceError, match="failed closed"):
            item.cycle(cycle, verified_fill=evidence)
        gateway = wf.store.load().gateway
        assert gateway.kill_switch_active and not gateway.connected
        assert gateway.records[0].filled_quantity == evidence.fill.quantity
        assert len(item.store.load().fill_bindings) == int(after_replace)
        health = json.loads(wf.health_path.read_text())
        alert = json.loads(wf.alerts_path.read_text().splitlines()[-1])
        assert health["state"] == alert["state"] == "HALTED_PERFORMANCE_PERSISTENCE"
        assert alert["gateway_snapshot_id"] == gateway.snapshot_id
        assert alert["kill_switch_active"] is True
    finally:
        wf.release()
